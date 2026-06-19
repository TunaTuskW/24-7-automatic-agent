FROM python:3.11-slim

# Install system dependencies if required by scipy/numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip cache purge

COPY src/ ./src/
COPY config/ ./config/
COPY models/ ./models/

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["sh", "-c", "python3 src/scheduler.py & uvicorn src.api:app --host 0.0.0.0 --port 8000 --workers 1"]
