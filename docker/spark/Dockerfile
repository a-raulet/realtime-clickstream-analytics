# Dockerfile for Spark Streaming
FROM bitnami/spark:latest

USER root

# Install Python dependencies
RUN pip install --no-cache-dir \
    kafka-python==2.0.2 \
    pyyaml==6.0.1 \
    delta-spark==3.1.0 \
    pandas==2.1.4

# Create app directory
WORKDIR /app

# Switch back to non-root user
USER 1001
