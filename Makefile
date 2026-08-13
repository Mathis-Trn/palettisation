.PHONY: backend-sync backend-lint backend-typecheck backend-test backend-run backend-openapi \
        frontend-install frontend-lint frontend-typecheck frontend-test frontend-build frontend-e2e \
        up down build

backend-sync:
	cd backend && uv sync --dev

backend-lint:
	cd backend && uv run ruff check .

backend-typecheck:
	cd backend && uv run mypy src

backend-test:
	cd backend && uv run pytest --cov=src/palletizer

backend-run:
	cd backend && uv run uvicorn palletizer.api.main:app --reload --port 8000

backend-openapi:
	cd backend && uv run python -c "import json; from palletizer.api.main import create_app; json.dump(create_app().openapi(), open('../contracts/openapi.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)"

frontend-install:
	cd frontend && npm ci

frontend-lint:
	cd frontend && npm run lint

frontend-typecheck:
	cd frontend && npm run typecheck

frontend-test:
	cd frontend && npm test

frontend-build:
	cd frontend && npm run build

frontend-e2e:
	cd frontend && npm run test:e2e

build:
	docker compose build

up:
	docker compose up --build

down:
	docker compose down
