.PHONY: setup dev test e2e lint

ifeq ($(OS),Windows_NT)
  VENV_BIN := .venv/Scripts
else
  VENV_BIN := .venv/bin
endif
PY := $(VENV_BIN)/python

setup:
	cd backend && python -m venv .venv && $(PY) -m pip install -e ".[dev]"
	cd backend && $(VENV_BIN)/alembic upgrade head
	cd frontend && npm ci

dev:
	cd backend && $(VENV_BIN)/alembic upgrade head
	(cd backend && $(PY) -m uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev)

test:
	cd backend && $(PY) -m pytest -q
	cd frontend && npm test --silent

e2e:
	cd frontend && npx playwright test

lint:
	cd backend && $(VENV_BIN)/ruff check . && $(VENV_BIN)/ruff format --check .
	cd frontend && npm run lint && npx tsc --noEmit
