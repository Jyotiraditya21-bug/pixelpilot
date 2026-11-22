# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-22

### Added
- 5-tier resilient locator engine:
  - Tier (a): Local cache hit (`0.0 ms`).
  - Tier (b): ARIA accessibility snapshot inspection.
  - Tier (c): Role and accessible name matching via Playwright.
  - Tier (d): Visible text content fallback.
  - Tier (e): Multimodal vision grounding via Gemini structured JSON (`vlm_bbox`).
- SQLite-backed healing cache that auto-records healed locators and replays them on subsequent runs with 0 grounding calls.
- Zero-space execution mode utilizing system Chrome (`channel="chrome"`), maintaining repository and environment under 400 MB.
- Local real-time instrument dashboard on port 8100 with step timeline, live canvas overlay with animated target bounding box, run replay scrubbing, run comparison diff view, and HTML evidence reports.
- Comprehensive benchmark harness comparing scripted Playwright baselines against PixelPilot across DOM mutations.
- Fixture test suites for scroll, modal, ambiguous targets, and icon-only controls.
- Automatic secret redaction for sensitive fields and API tokens in traces and logs.
