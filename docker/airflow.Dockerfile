FROM apache/airflow:2.10.4-python3.12

USER root
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

USER airflow
WORKDIR /opt/airflow
COPY --chown=airflow:root pyproject.toml README.md requirements.txt /opt/airflow/
COPY --chown=airflow:root src /opt/airflow/src
RUN pip install --no-cache-dir -e ".[dbt]"
