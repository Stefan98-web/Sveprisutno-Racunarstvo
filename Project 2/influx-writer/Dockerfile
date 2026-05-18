FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    paho-mqtt \
    influxdb-client

COPY app.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]