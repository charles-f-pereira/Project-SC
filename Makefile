.PHONY: check frontend backend format lint test

check: frontend backend

# --- Frontend (Vite/React) ---
frontend:
	cd frontend && npm run check

# --- Backend (FastAPI/Python) ---
backend:
	cd backend && ruff format . && ruff check . --fix && pyright && pytest

# Optional convenience targets
format:
	cd frontend && npm run format
	cd backend && ruff format .

lint:
	cd frontend && npm run lint
	cd backend && ruff check .

test:
	cd backend && pytest