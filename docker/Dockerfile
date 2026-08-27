FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      openjdk-21-jre-headless \
      gcc \
      curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY dbt /app/dbt
COPY dashboards /app/dashboards
COPY data_quality /app/data_quality
COPY spark /app/spark
COPY ml /app/ml
COPY cosmetics.csv /app/cosmetics.csv

RUN pip install --no-cache-dir -e ".[dashboard,dbt]"

EXPOSE 8088 8501
CMD ["python", "-m", "skincare_platform.cli", "--help"]
