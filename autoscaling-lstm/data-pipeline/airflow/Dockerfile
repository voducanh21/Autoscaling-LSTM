FROM apache/airflow:3.1.0-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc git curl build-essential libpq-dev libsasl2-dev && \
    rm -rf /var/lib/apt/lists/*

USER airflow
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
