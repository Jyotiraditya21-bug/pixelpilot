UV_CACHE_DIR ?= /private/tmp/pixelpilot-uv-cache
export UV_CACHE_DIR

.PHONY: check lint type test demo ui up clean assets
check: lint type test
lint:
	uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
type:
	uv run --no-sync mypy
test:
	uv run --no-sync pytest -m "not vlm" -q
demo:
	uv run --no-sync uvicorn demo_app.main:app --host 127.0.0.1 --port 8000
ui:
	uv run --no-sync pixelpilot dashboard
assets:
	uv run --no-sync python scripts/capture_assets.py
up:
	docker compose up -d
clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf runs/ .pytest_cache/ .mypy_cache/ .ruff_cache/
