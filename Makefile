.PHONY: help install pipeline ingest silver gold dbt quality test lint \
	generate api dashboard up down smoke export-powerbi

PYTHON ?= python3
EVENTS ?= 100000
PRICE_DAYS ?= 90

help:
	@echo "Skincare Intelligence Data Platform"
	@echo ""
	@echo "  make install         Install Python package (core + dbt + dev)"
	@echo "  make pipeline        Run full Bronze → Silver → Gold batch pipeline"
	@echo "  make ingest          Ingest all sources into Bronze"
	@echo "  make silver          Spark Bronze → Silver"
	@echo "  make gold            Load warehouse + dbt marts + ML features"
	@echo "  make quality         Run data-quality gates"
	@echo "  make test            pytest + ruff"
	@echo "  make smoke           Small end-to-end smoke (5k events)"
	@echo "  make generate        Build synthetic prices + events"
	@echo "  make api             Run local product API"
	@echo "  make dashboard       Run Streamlit analytics app"
	@echo "  make export-powerbi  Export Gold CSVs for Power BI"
	@echo "  make up / down       Docker Compose platform"

install:
	$(PYTHON) -m pip install -e ".[dev,dbt,dashboard]"

generate:
	$(PYTHON) -m skincare_platform.cli generate --events $(EVENTS) --price-days $(PRICE_DAYS)

ingest:
	$(PYTHON) -m skincare_platform.cli ingest

silver:
	$(PYTHON) -m skincare_platform.cli silver

gold:
	$(PYTHON) -m skincare_platform.cli gold

quality:
	$(PYTHON) -m skincare_platform.cli quality

pipeline:
	$(PYTHON) -m skincare_platform.cli run-pipeline --events $(EVENTS) --price-days $(PRICE_DAYS)

smoke:
	$(PYTHON) -m skincare_platform.cli run-pipeline --events 5000 --price-days 14
	$(PYTHON) -m pytest -q tests

test:
	$(PYTHON) -m ruff check src tests airflow spark
	$(PYTHON) -m pytest -q tests

lint:
	$(PYTHON) -m ruff check src tests airflow spark

api:
	$(PYTHON) -m skincare_platform.cli serve-api --host 0.0.0.0 --port 8088

dashboard:
	$(PYTHON) -m streamlit run dashboards/app.py --server.address 0.0.0.0 --server.port 8501

export-powerbi:
	$(PYTHON) -m skincare_platform.cli export-powerbi

up:
	docker compose up --build -d

down:
	docker compose down
