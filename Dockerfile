# Use official Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Install system dependencies + SSL certificates
RUN apt-get update && apt-get install -y \
    gcc \
    ca-certificates \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Set SSL certificate environment variables
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_DIR=/etc/ssl/certs
ENV PYTHONHTTPSVERIFY=0

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies + Google Cloud Storage + SSL certificates
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir google-cloud-storage certifi && \
    python -m certifi

# Copy application code
COPY . .

# Create data directories for ephemeral storage
RUN mkdir -p /tmp/data/reports /tmp/data/training /tmp/data/runs

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health').read()"

# Run Gunicorn server
CMD exec gunicorn --bind :$PORT --workers 4 --timeout 120 --access-logfile - --error-logfile - app:app
