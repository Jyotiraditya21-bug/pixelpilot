.PHONY: check lint type test demo up clean
check: lint type test
lint:
	uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
type:
	uv run --no-sync mypy
test:
	uv run --no-sync pytest -m "not vlm" -q
demo:
	uv run --no-sync uvicorn demo_app.main:app --port 8000
up:
	docker compose up -d
clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf runs/ .pytest_cache/ .mypy_cache/ .ruff_cache/
