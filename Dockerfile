# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy required files
COPY requirements.txt .
COPY oscpInsights.py .
COPY config.yaml .
COPY dashboard.py .
COPY .env .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Streamlit port
EXPOSE 8501

# Command to run both collector and dashboard
CMD ["sh", "-c", "python oscpInsights.py && streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0"]