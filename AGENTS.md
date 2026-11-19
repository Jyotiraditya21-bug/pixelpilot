# PixelPilot agent rules
- Python 3.11, uv, async Playwright, pydantic v2, typer.
- Commands: `make check` (ruff+mypy strict+pytest non-vlm), `make demo`, `make up`.
- Never hardcode selectors in src/pixelpilot/agents. Locators come from cache, a11y, DOM text, or the VLM.
- VLM calls: temperature 0, JSON-only, parse with vision/parsing.py.
- Never log typed secrets; redact password fields.
- Small typed functions. No TODOs, no stubs, no dead code.
- Record decisions in docs/DECISIONS.md. Commit per milestone (conventional commits).
- ZERO-SPACE MODE: system Chrome only (channel="chrome"), never run `playwright install`. No numpy/scipy/imagehash. Keep total repo+venv under 400 MB.
