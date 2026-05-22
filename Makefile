.PHONY: up down init ingest quality test lint format

up:
	docker compose up -d

down:
	docker compose down

init:
	python -m src.db.init_db

ingest:
	python -m src.pipeline --symbols AAPL MSFT TSLA --start 2024-01-01 --end 2024-12-31

quality:
	python -m src.quality.runner

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	ruff check src/ tests/

format:
	black src/ tests/
