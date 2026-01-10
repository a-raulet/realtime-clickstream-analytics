# Dockerfile for Streamlit Dashboard
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    streamlit==1.31.0 \
    pandas==2.1.4 \
    plotly==5.18.0 \
    delta-spark==3.1.0 \
    pyspark==3.5.0 \
    pyarrow==15.0.0 \
    pyyaml==6.0.1 \
    deltalake==0.15.1

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Run Streamlit
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
