.RECIPEPREFIX = >
.PHONY: install api lint typecheck test check

install:
> cd services/api && uv sync

api:
> cd services/api && uv run uvicorn nudge.web.main:create_app --factory --reload --port 8000

lint:
> cd services/api && uv run ruff check . && uv run ruff format --check .

typecheck:
> cd services/api && uv run pyright

test:
> cd services/api && uv run pytest

check: lint typecheck test
