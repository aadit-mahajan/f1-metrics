import requests
from requests.adapters import HTTPAdapter
from prometheus_client import start_http_server, Gauge, Counter
import time
import os
from dotenv import load_dotenv
import json

# Environment setup
load_dotenv()
base_url = os.getenv("BASE_URL")
if not base_url:
    raise ValueError("BASE_URL environment variable not set")

# Configure connection pooling
session = requests.Session()
adapter = HTTPAdapter(pool_connections=20, pool_maxsize=100, max_retries=3)
session.mount('https://', adapter)
session.mount('http://', adapter)

# Prometheus metrics with proper driver labels
metrics = {
    'sector1_time': Gauge('sector1_time', 'Sector 1 times', ['driver']),
    'sector2_time': Gauge('sector2_time', 'Sector 2 times', ['driver']),
    'sector3_time': Gauge('sector3_time', 'Sector 3 times', ['driver']),
    'speed_trap': Gauge('speed_trap', 'Speed trap data', ['driver']),
    'lap_count': Gauge('lap_count', 'Number of laps', ['driver']),
    'lap_time': Gauge('lap_time', 'Lap times', ['driver']),
    'gap_to_leader': Gauge('gap_to_leader', 'Gap to leader', ['driver']),
    'interval': Gauge('interval', 'Interval data', ['driver']),
    'position': Gauge('position', 'Driver positions', ['driver']),

}

# Cache session type to reduce API load
last_session_check = 0
session_type_cache = None

def get_session_type():
    global last_session_check, session_type_cache
    if time.time() - last_session_check < 30 and session_type_cache:
        return session_type_cache
    try:
        response = session.get(f"{base_url}sessions?session_key=latest", timeout=5)
        if response.ok:
            session_type_cache = response.json()[0].get('session_type')
            last_session_check = time.time()
            return session_type_cache
    except requests.RequestException as e:
        print(f"Session fetch error: {e}")
    return None

def fetch_lap_data():
    try:
        response = session.get(
            f"{base_url}laps?session_key=latest",
            headers={'Accept': 'application/json'},
            timeout=10
        )
        return response.json() if response.ok else None
    except requests.RequestException as e:
        print(f"Telemetry fetch error: {e}")
        return None
    
def fetch_interval_data():
    try:
        response = session.get(
            f'{base_url}intervals?session_key=latest', 
            headers={'Accept': 'application/json'},
            timeout=10
        )
        return response.json() if response.ok else None
    except requests.RequestException as e:
        print(f"Telemetry fetch error: {e}")
        return None
    
def fetch_driver_positions():
    try:
        response = session.get(
            f'{base_url}position?session_key=latest', 
            headers={'Accept': 'application/json'},
            timeout=10
        )
        return response.json() if response.ok else None
    except requests.RequestException as e:
        print(f"Telemetry fetch error: {e}")
        return None

def update_lap_metrics(lap_data, driver_mapping):
    
    for datapt in lap_data:
        driver_number = datapt.get('driver_number', '16')
        driver = driver_mapping[driver_number]['code']
        if datapt['is_pit_out_lap']:
            continue

        for (key, value) in datapt.items():
            if value is None:
                datapt[key] = 0.0
        
        # Update available metrics only if data is valid
        metrics['lap_count'].labels(driver=driver).set(datapt['lap_number'])
        metrics['sector1_time'].labels(driver=driver).set(datapt['duration_sector_1'])
        metrics['sector2_time'].labels(driver=driver).set(datapt['duration_sector_2'])
        metrics['sector3_time'].labels(driver=driver).set(datapt['duration_sector_3'])

        if 'lap_duration' in datapt:
            metrics['lap_time'].labels(driver=driver).set(datapt['lap_duration'])
        if 'speed_trap' in datapt:
            metrics['speed_trap'].labels(driver=driver).set(datapt['speed_trap'])

def update_race_metrics(lap_data, interval_data, driver_positions, driver_mapping):

    for datapt in lap_data:
        driver_number = datapt.get('driver_number', '16')
        driver = driver_mapping[driver_number]['code']
        if datapt['is_pit_out_lap']:
            continue

        for (key, value) in datapt.items():
            if value is None:
                datapt[key] = 0.0
        
        # Update available metrics only if data is valid
        metrics['lap_count'].labels(driver=driver).set(datapt['lap_number'])
        metrics['sector1_time'].labels(driver=driver).set(datapt['duration_sector_1'])
        metrics['sector2_time'].labels(driver=driver).set(datapt['duration_sector_2'])
        metrics['sector3_time'].labels(driver=driver).set(datapt['duration_sector_3'])

    for datapt in interval_data:
        driver_number = datapt.get('driver_number', '16')
        driver = driver_mapping[driver_number]['code']
        
        for (key, value) in datapt.items():
            if value is None:
                datapt[key] = 0.0
        
        # Update available metrics only if data is valid
        metrics['gap_to_leader'].labels(driver=driver).set(datapt.get('gap_to_leader', 0.0))
        metrics['interval'].labels(driver=driver).set(datapt.get('interval', 0.0))

    for datapt in driver_positions:
        driver_number = datapt.get('driver_number', '16')
        driver = driver_mapping[driver_number]['code']
        
        for (key, value) in datapt.items():
            if value is None:
                datapt[key] = 0.0
        
        # Update available metrics only if data is valid
        metrics['position'].labels(driver=driver).set(datapt.get('position', 0.0))

def main():
    start_http_server(18000)
    print("Telemetry exporter running on port 18000")
    
    with open("driver_mapping.json") as f:
        driver_mapping = json.load(f)

    session_type = None
    while session_type is None:
        session_type = get_session_type()
        if not session_type:
            time.sleep(10)

    print(f"Session type: {session_type}")
    while True:
        if session_type == "Qualifying":
            lap_data = fetch_lap_data()
            update_lap_metrics(lap_data, driver_mapping)
            print(f"Updated qualifying metrics for drivers")
        
        if session_type == "Race" or session_type == "Sprint":
            lap_data = fetch_lap_data()
            interval_data = fetch_interval_data()
            driver_positions = fetch_driver_positions()
            update_race_metrics(lap_data, interval_data, driver_positions, driver_mapping)
            print(f"Updated race metrics for drivers")
        # Race = faster loop, else slower to reduce API calls
        time.sleep(2 if session_type in ['Race', 'Sprint'] else 10)

if __name__ == "__main__":
    main()
