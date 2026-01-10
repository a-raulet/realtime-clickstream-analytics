# Dockerfile for Kafka Producer (lightweight Python image)
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    kafka-python==2.0.2 \
    pyyaml==6.0.1 \
    pandas==2.1.4

CMD ["python", "/app/src/producer/kafka_producer.py"]
