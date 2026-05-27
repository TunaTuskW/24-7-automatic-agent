FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if required by scipy/numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set PYTHONPATH to the root directory
ENV PYTHONPATH=/app

CMD ["python3", "src/fetch_market_data.py"]
