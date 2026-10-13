.PHONY: help setup test ui run-finance demo demo-all reset clean

PYTHON ?= .venv/bin/python
UV ?= uv

help:
	@echo "Available commands:"
	@echo "  make setup       Install dependencies, playwright chromium, and seed db"
	@echo "  make run-finance Start mock Finance App on port 8000"
	@echo "  make ui          Start UI Dashboard on port 8001"
	@echo "  make demo        Run Scenario 1 (happy path)"
	@echo "  make demo-all    Run Scenario 2 (full mixed 12 claims)"
	@echo "  make test        Run test suite with pytest"
	@echo "  make reset       Reset SQLite databases and test artifacts"

setup:
	$(UV) venv --python 3.12 .venv || true
	$(UV) pip install -e ".[dev]"
	$(PYTHON) -m playwright install chromium
	test -f .env || cp .env.example .env
	$(PYTHON) finance_app/seed.py --reset

run-finance:
	$(PYTHON) -m uvicorn finance_app.app:app --host 0.0.0.0 --port 8000 --reload

ui:
	$(PYTHON) -m uvicorn ui.server:app --host 0.0.0.0 --port 8001 --reload

demo:
	$(PYTHON) scenarios/s1_happy_path.py

demo-all:
	$(PYTHON) scenarios/s2_full_mixed.py

test:
	$(PYTHON) -m pytest tests/ -v

reset:
	$(PYTHON) finance_app/seed.py --reset
	rm -f reports/*.db reports/*.json reports/screenshots/*
