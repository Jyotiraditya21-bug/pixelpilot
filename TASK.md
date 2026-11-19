Read AGENTS.md. The scaffold, deps, Makefile, docker-compose and .env already exist; do not recreate them. Implement the empty files in this order, run `make check` and commit after each:
M2 demo_app (FastAPI shop: products, cart, checkout, coupon SAVE10 valid / OLD50 expired, confirmation; ?mutate=1 randomizes CSS classes/ids, element order, button positions/colors per load) + 3 stories.
M3 browser/ (session, pruned DOM+a11y snapshot with role/name/text/bbox, actions).
M4 vision/ (ollama client, prompts, strict-JSON parser with fence handling, coords conversion for Qwen2.5-VL absolute pixels on resized image <=1280px) + unit tests.
M5 agents planner, observer, grounder, actor (tiers: cached locator, role+name, DOM text, VLM bbox center, replan once), verifier (DOM facts first, VLM for visual).
M6 healing/ (fingerprint: tag, role, text, region hash, phash of crop; SQLite cache keyed by site+intent) + healer.
M7 orchestrator (MAX_STEPS 25, 20s step timeout, 2 retries) + CLI: run, bench, report, doctor.
M8 OpenTelemetry: root span per run, child spans per agent/step, attrs (story, step, intent, tier, healed, model, vlm_ms, confidence, pass), OTLP to Jaeger, console fallback, screenshot path as event only.
M9 HTML report with bbox overlays, tiers, heal events, evidence, trace ID.
M10 benchmarks: scripted baseline vs PixelPilot, N runs, mutate 0/1, write benchmarks/RESULTS.md (target: baseline <30% under mutation, PixelPilot >=85%; otherwise document honest numbers and causes).
M11 README (Mermaid diagram, quickstart, results).
Use mocked Grounder for integration tests; one @pytest.mark.vlm test for real Ollama. Do not ask questions. Finish with: what was built, how to run, benchmark numbers, limitations, next 3 improvements.

ZERO-SPACE OVERRIDES (highest priority):
- Launch Playwright with channel="chrome". Never download browsers. doctor checks /Applications/Google Chrome.app exists.
- No imagehash/numpy: implement the perceptual hash in healing/fingerprint.py with Pillow only (grayscale, resize 8x8, average hash, hamming distance).
- Screenshots: JPEG quality 60, longest side <=1024 px, saved under runs/<run_id>/. After each run keep only the newest 10 run folders.
- Add `make clean` that deletes runs/, .pytest_cache, .mypy_cache, .ruff_cache, __pycache__.
- Benchmark default N=3 per condition. Free-tier Gemini rate limits apply.
