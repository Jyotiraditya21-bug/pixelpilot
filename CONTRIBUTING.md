# Contributing to PixelPilot

Thank you for your interest in contributing to PixelPilot!

## Development Guidelines

1. **Python & Tooling**:
   - Python 3.11+ required.
   - Use `uv` for fast, deterministic dependency management.
   - Run `make check` to run `ruff` (linter and formatter), `mypy` (strict mode), and `pytest -m "not vlm"`.

2. **Zero-Space Mode**:
   - PixelPilot is designed to run in zero-space mode.
   - Use system Google Chrome (`channel="chrome"`). Never run `playwright install`.
   - Avoid adding heavy packages (`numpy`, `scipy`, `imagehash`). Keep repository and virtual environment under 400 MB.

3. **No Live Model Calls in Automated Tests**:
   - All tests in `tests/` must use mocked grounders and mocked responses.
   - Do not make live Gemini API calls in unit or integration tests.
   - Never log or commit `.env` files or secret keys.

4. **Code Quality**:
   - Small, typed, modular functions.
   - No TODOs, no stubs, no dead code.
   - All new features must include corresponding test coverage.

5. **Conventional Commits**:
   - Follow conventional commit conventions: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.

## Getting Started Locally

```bash
# Clone the repository
git clone https://github.com/jyotiraditya/pixelpilot.git
cd pixelpilot

# Install dependencies using uv
uv sync

# Run verification checks
make check

# Start demo store and dashboard
make demo   # in terminal 1 (http://127.0.0.1:8000)
make ui     # in terminal 2 (http://127.0.0.1:8100)
```

## Pull Request Process

1. Fork the repository and create your feature branch from `main`.
2. Ensure `make check` passes cleanly.
3. If modifying dashboard or visuals, run `make assets` and verify visual quality against tokens in `docs/DESIGN.md`.
4. Open a pull request against `main` describing your changes and verification steps.
