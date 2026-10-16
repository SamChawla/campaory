.PHONY: setup dev test e2e lint
setup:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
	cd frontend && npm ci
dev:
	(cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev)
test:
	cd backend && . .venv/bin/activate && pytest -q
	cd frontend && npm test --silent
e2e:
	cd frontend && npx playwright test
lint:
	cd backend && . .venv/bin/activate && ruff check . && ruff format --check .
	cd frontend && npm run lint
