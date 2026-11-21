# Handoff
Project: PixelPilot (see AGENTS.md, README.md, docs/DECISIONS.md). Python 3.11, uv, async Playwright with system Chrome, Gemini REST VLM (PP_GEMINI_API_KEY in .env, never print it).
Run: `make demo` (port 8000), `make check`, `uv run --no-sync pixelpilot run stories/checkout_expired_coupon.md --url http://localhost:8000 --mutate`, `uv run --no-sync pixelpilot bench --n 3`.
Status: make check passes. Benchmark: scripted baseline 100%/0% (mutate 0/1), PixelPilot 100%/100% (semantic tiers), PixelPilot VLM-only 3/9 and 3/9, identical to before the key was set, so a bug or quota failure is suspected.
Open task 1: find the root cause of VLM-only 3/9. Check swallowed exceptions, box_2d order [ymin,xmin,ymax,xmax] scaled 0-1000, click coordinates (viewport vs resized image), empty responses from model thinking budget, rate limiter and 429 retries. Fix, rerun bench N=3, update benchmarks/RESULTS.md honestly.
Open task 2: prove cache replay: run 1 uses VLM tier and caches the heal, run 2 hits tier (a) with zero grounding calls.
Open task 3: paste final table into docs/LINKEDIN.md, finish README.
Rules: no git commands, no make clean while a bench runs, keep disk use small, no new heavy dependencies.
