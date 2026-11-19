# Architecture decisions

## M2 — deterministic semantics under visual mutation

The demo shop stores carts by an HTTP-only session cookie and renders HTML on the server. Mutation changes generated classes and IDs, product order, flex direction, and the primary color on every load while preserving accessible names and business behavior. This makes brittle selectors fail without making the user story ambiguous.

## M3 — browser boundary and observation budget

Playwright always launches installed Chrome through `channel="chrome"`. Page observations are capped at 250 visible semantic elements and 12,000 body-text characters. Screenshots are viewport JPEGs at quality 60, downscaled to a 1024-pixel longest side. Run retention is ten directories.

## M4 — strict vision boundary

Ollama chat requests use temperature zero and JSON mode. Responses may be raw JSON or one complete JSON fence; prose around JSON is rejected. Qwen2.5-VL receives an aspect-preserving image no larger than 1280 pixels and returns absolute resized-image pixels, which are scaled back to source coordinates explicitly.

## M5 — semantic-first agent pipeline

Plans contain intents and accessible role/name/text targets rather than selectors. Grounding escalates through cached locator, role plus accessible name, visible DOM text, then VLM bounding-box center. The actor permits one replanned attempt. Verification extracts concrete DOM facts first and spends a VLM call only when those facts are insufficient.

## M6 — conservative healing cache

SQLite cache identity is `(site, intent)`. Reuse requires a weighted semantic and visual fingerprint match. Fingerprints contain tag, role, normalized text, a small region digest, and a Pillow-only 8×8 average hash; no NumPy, SciPy, or imagehash dependency is used.

## M7 — bounded orchestration

Runs are capped at 25 planned steps. Each attempt has a 20-second timeout and at most two retries. Every run writes a typed JSON record beneath its run directory. The CLI exposes `run`, `bench`, `report`, and `doctor`; doctor checks the exact macOS system-Chrome application and Ollama without installing anything.

## M8 — tracing and sensitive artifact handling

Each run has one root span, with step spans and agent child spans. Step attributes record story context, intent, tier, healing, model, VLM duration, confidence, and pass status. Screenshot paths are span events only. The optional OTLP gRPC exporter targets Jaeger when installed; the console exporter is the dependency-free fallback.

## M9 — self-contained run evidence

The HTML report is generated from the typed run record and uses only sibling screenshots. It shows outcome evidence, trace ID, grounding tier, healing events, confidence, and action details. VLM bounding boxes are scaled from the fixed 1280×900 browser viewport onto retained screenshots.

## M10 — benchmark scope

Each condition runs all three stories three times by default. The baseline intentionally targets stable IDs and classes, while PixelPilot uses its production semantic pipeline. Both use installed Chrome against the same local server. Results are always overwritten with observed counts, including misses and their architectural cause.

## M11 — documentation and claims

README results are copied from the generated benchmark artifact and distinguish semantic mutation resilience from general VLM accuracy. Quickstart instructions never install Playwright browsers. Known integration gaps are listed explicitly so measured demo success is not presented as broader production reliability.
