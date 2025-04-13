# Use a lightweight Python base image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements file (create one if needed)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code
COPY . .

# Expose the Prometheus exporter port
EXPOSE 18000

# Run the telemetry exporter
CMD ["python", "app.py"]
