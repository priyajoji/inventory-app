FROM docker.io/library/python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    LOW_STOCK_THRESHOLD=10

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Database lives here; mount a Podman volume on it for persistence
RUN mkdir -p /data
VOLUME /data

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
