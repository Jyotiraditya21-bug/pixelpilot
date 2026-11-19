.RECIPEPREFIX := >
.PHONY: check lint type test demo up
check: lint type test
lint:
> uv run ruff check . && uv run ruff format --check .
type:
> uv run mypy
test:
> uv run pytest -m "not vlm" -q
demo:
> uv run uvicorn demo_app.main:app --port 8000
up:
> docker compose up -d
