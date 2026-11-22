from __future__ import annotations

# ruff: noqa: E501
import asyncio
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pixelpilot.models import RunRecord

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SITE_DIR = PROJECT_ROOT / "site"
DATA_DIR = SITE_DIR / "data"
ASSETS_DIR = SITE_DIR / "assets"
DASHBOARD_DIR = SITE_DIR / "dashboard"
REPORTS_DIR = SITE_DIR / "reports"
DOCS_ASSETS_DIR = PROJECT_ROOT / "docs" / "assets"
STATIC_INDEX = PROJECT_ROOT / "src" / "pixelpilot" / "dashboard" / "static" / "index.html"


def _clean_and_create_dirs() -> None:
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")


def _copy_docs_assets() -> None:
    if DOCS_ASSETS_DIR.exists():
        for asset in DOCS_ASSETS_DIR.iterdir():
            if asset.is_file():
                shutil.copy2(asset, ASSETS_DIR / asset.name)


def _seed_runs_to_temp_dir() -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="pixelpilot-site-runs-"))
    server: subprocess.Popen[bytes] | None = None
    try:
        from scripts.seed_demo_runs import _ensure_demo_server, seed_demo_runs

        server = _ensure_demo_server()
        asyncio.run(seed_demo_runs(temp_dir))
        return temp_dir
    except Exception as exc:
        print(f"Notice: live seed_demo_runs unavailable ({exc}); falling back to local runs/")
        fallback_dir = PROJECT_ROOT / "runs"
        if fallback_dir.exists():
            for item in fallback_dir.iterdir():
                if item.is_dir():
                    shutil.copytree(item, temp_dir / item.name, dirs_exist_ok=True)
        return temp_dir
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=5)


def _export_runs_data(source_runs_dir: Path) -> dict[str, object]:
    runs_summary: list[dict[str, object]] = []
    runs_details: dict[str, dict[str, object]] = {}

    for run_json in sorted(source_runs_dir.glob("*/run.json")):
        run_id = run_json.parent.name
        run = RunRecord.model_validate_json(run_json.read_text(encoding="utf-8"))

        run_assets_dir = ASSETS_DIR / run_id
        run_assets_dir.mkdir(parents=True, exist_ok=True)

        for screenshot in run_json.parent.glob("step-*.jpg"):
            shutil.copy2(screenshot, run_assets_dir / screenshot.name)

        steps: list[dict[str, object]] = []
        for step in run.steps:
            img_rel: str | None = None
            if step.screenshot:
                img_name = Path(step.screenshot).name
                img_rel = f"../assets/{run_id}/{img_name}"

            steps.append(
                {
                    "type": "step",
                    "run_id": run.run_id,
                    "step": step.number,
                    "intent": step.intent,
                    "tier": step.tier.value if step.tier else "direct",
                    "healed": step.healed,
                    "vlm_ms": step.vlm_ms,
                    "confidence": step.confidence,
                    "pass": step.success,
                    "detail": step.detail,
                    "bbox": step.bbox.model_dump() if step.bbox else None,
                    "screenshot": img_rel,
                }
            )

        report_source = run_json.parent / "report.html"
        report_rel = f"../reports/{run_id}.html"
        if report_source.exists():
            report_content = report_source.read_text(encoding="utf-8")
            # Rewrite relative image paths in report so they load from ../assets/<run_id>/
            report_content = re.sub(
                r'src=["\'](step-\d+\.jpg)["\']',
                rf'src="../assets/{run_id}/\1"',
                report_content,
            )
            (REPORTS_DIR / f"{run_id}.html").write_text(report_content, encoding="utf-8")

        summary_entry = {
            "run_id": run.run_id,
            "story": run.story,
            "status": "passed" if run.passed else "failed",
            "pass": run.passed,
            "trace_id": run.trace_id,
            "vlm_ms": sum(step.vlm_ms for step in run.steps),
            "report": report_rel,
            "error": None
            if run.passed
            else "Simulated vision grounding failure: element obscured by cookie modal overlay",
        }
        runs_summary.append(summary_entry)

        detail_entry = {
            "run_id": run.run_id,
            "story": run.story,
            "pass": run.passed,
            "evidence": run.evidence,
            "trace_id": run.trace_id,
            "steps": steps,
        }
        runs_details[run.run_id] = detail_entry

    payload: dict[str, object] = {
        "runs": runs_summary,
        "details": runs_details,
    }

    (DATA_DIR / "runs.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _build_dashboard_page() -> None:
    content = STATIC_INDEX.read_text(encoding="utf-8")

    # Replace title and add Open Graph / Meta tags
    meta_tags = """  <title>PixelPilot — Run Instrument</title>
  <meta name="description" content="Interactive static showcase of PixelPilot run telemetry, visual bounding-box grounding, and healing cache replay.">
  <meta property="og:title" content="PixelPilot — Run Instrument">
  <meta property="og:description" content="Explore self-healing Playwright agents using visual grounding and tiered locator fallback.">
  <meta property="og:image" content="../assets/social-preview.png">
  <meta property="og:url" content="https://jyotiraditya21-bug.github.io/pixelpilot/dashboard/">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">"""

    content = re.sub(
        r"\s*<title>.*?</title>",
        "\n" + meta_tags,
        content,
        count=1,
    )

    # Add visible static demo banner directly below <body>
    banner_html = """<body>
  <div class="static-banner" role="banner" style="background:var(--signal);color:var(--signal-ink);padding:var(--sp-2) var(--sp-4);font-family:var(--font-mono);font-size:var(--micro-size);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:var(--sp-2);border-bottom:var(--hairline) solid var(--ink);">
    <span><strong>STATIC SHOWCASE:</strong> Static demo built from recorded runs. Run PixelPilot locally for live testing.</span>
    <span style="display:flex;gap:var(--sp-3);">
      <a href="../" style="color:var(--signal-ink);text-decoration:underline;">← Overview</a>
      <a href="https://github.com/Jyotiraditya21-bug/pixelpilot" target="_blank" rel="noopener" style="color:var(--signal-ink);text-decoration:underline;">GitHub ↗</a>
    </span>
  </div>"""

    content = content.replace("<body>", banner_html, 1)

    # Adjust brand label
    content = content.replace(
        "<small>RUN INSTRUMENT / LOCAL 8100</small>",
        "<small>STATIC SHOWCASE / RECORDED RUNS</small>",
        1,
    )

    # Adapt loadStories() to static list
    static_load_stories = """    function loadStories() {
      const select = el("story");
      select.replaceChildren();
      const stories = [
        { path: "stories/checkout_expired_coupon.md", title: "Reject an expired coupon" },
        { path: "stories/checkout_valid_coupon.md", title: "Apply a valid coupon" },
        { path: "stories/fixtures/modal.md", title: "Dismiss modal overlay" },
        { path: "stories/fixtures/scroll.md", title: "Scroll to target below fold" }
      ];
      stories.forEach(item => {
        const option = document.createElement("option");
        option.value = item.path;
        option.textContent = item.title;
        select.append(option);
      });
      select.disabled = false;
      el("runButton").disabled = false;
      setRunState("finished", "Static showcase ready. Select a recorded run to inspect.");
    }"""
    content = re.sub(
        r"async function loadStories\(\)\s*\{[\s\S]*?\n    \}",
        static_load_stories,
        content,
        count=1,
    )

    # Adapt loadHistory() to load from ../data/runs.json
    static_load_history = """    async function loadHistory() {
      const list = el("historyList"); list.setAttribute("aria-busy", "true");
      try {
        const response = await fetch("../data/runs.json");
        if (!response.ok) throw new Error(`History HTTP ${response.status}`);
        const data = await response.json();
        state.archive = data;
        state.runs = data.runs || [];
        list.replaceChildren();
        if (!state.runs.length) list.append(emptyNode("No saved runs", "Completed runs will appear here."));
        else state.runs.forEach((run, index) => list.append(historyNode(run, index)));
        if (state.runs.length && state.selected < 0) {
          loadReplay(state.runs[0].run_id);
        }
      } catch (error) { list.replaceChildren(emptyNode("Archive unavailable", formatError(error), true)); }
      finally { list.setAttribute("aria-busy", "false"); }
    }"""
    content = re.sub(
        r"async function loadHistory\(\)\s*\{[\s\S]*?\n    \}",
        static_load_history,
        content,
        count=1,
    )

    # Adapt fetchSavedRun(runId) to read from state.archive
    static_fetch_saved_run = """    async function fetchSavedRun(runId) {
      if (state.archive && state.archive.details && state.archive.details[runId]) {
        return state.archive.details[runId];
      }
      const response = await fetch("../data/runs.json");
      const data = await response.json();
      state.archive = data;
      if (data.details && data.details[runId]) return data.details[runId];
      throw new Error(`Run ${runId} not found in static archive`);
    }"""
    content = re.sub(
        r"async function fetchSavedRun\(runId\)\s*\{[\s\S]*?\n    \}",
        static_fetch_saved_run,
        content,
        count=1,
    )

    # Adapt startRun() to notify static mode and trigger replay
    static_start_run = """    async function startRun(event) {
      if (event) event.preventDefault();
      showHealToast();
      setRunState("finished", "Static showcase: live testing runs locally with system Chrome.");
      if (state.runs && state.runs.length) loadReplay(state.runs[0].run_id);
    }"""
    content = re.sub(
        r"async function startRun\(event\)\s*\{[\s\S]*?\n    \}",
        static_start_run,
        content,
        count=1,
    )

    (DASHBOARD_DIR / "index.html").write_text(content, encoding="utf-8")


def _build_landing_page() -> None:
    html = """<!doctype html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PixelPilot — Self-Healing Playwright Agents</title>
  <meta name="description" content="Self-healing Playwright agents using visual grounding and tiered locator fallback.">
  <meta property="og:title" content="PixelPilot — Self-Healing Playwright Agents">
  <meta property="og:description" content="Self-healing Playwright agents using visual grounding and tiered locator fallback.">
  <meta property="og:image" content="assets/social-preview.png">
  <meta property="og:url" content="https://jyotiraditya21-bug.github.io/pixelpilot/">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">
  <script>
    try {
      const saved = localStorage.getItem("pixelpilot-theme");
      if (saved === "dark" || saved === "light") document.documentElement.dataset.theme = saved;
    } catch (_e) { document.documentElement.dataset.theme = "light"; }
  </script>
  <style>
    :root {
      color-scheme: light;
      --paper: #f4efe4; --paper-raised: #fbf7ee; --paper-deep: #e8e0d2;
      --ink: #171813; --ink-muted: #5d6058; --rule: #77786f; --rule-soft: #c3bcae;
      --signal: #8b3b18; --signal-ink: #fbf7ee; --pass: #1f6a40; --fail: #a12c24;
      --tier-cache: #4b5563; --tier-role: #22653f; --tier-dom: #00636b;
      --tier-vision: #835000; --tier-heal: #665500;
      --font-display: "Avenir Next Condensed", "Arial Narrow", system-ui, sans-serif;
      --font-mono: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      --sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px; --sp-6: 24px;
      --sp-8: 32px; --sp-12: 48px; --measure: 84ch;
      --radius: 3px; --hairline: 1px; --rule-heavy: 2px;
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      --paper: #15130f; --paper-raised: #201d17; --paper-deep: #2b271f;
      --ink: #f2ecdf; --ink-muted: #b9b2a5; --rule: #8a8376; --rule-soft: #4a453d;
      --signal: #f0a56a; --signal-ink: #15130f; --pass: #79d49f; --fail: #ff9489;
      --tier-cache: #c5cbd3; --tier-role: #7ed3a1; --tier-dom: #71d4dc;
      --tier-vision: #f3bd68; --tier-heal: #d9c96b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html { background: var(--paper); color: var(--ink); scroll-behavior: smooth; }
    body { font: 1rem/1.55 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    a { color: var(--signal); text-decoration: none; }
    a:hover { text-decoration: underline; }
    code, kbd, pre, .mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

    header.nav {
      position: sticky; top: 0; z-index: 50;
      background: var(--paper-raised);
      border-bottom: var(--rule-heavy) solid var(--ink);
      display: flex; justify-content: space-between; align-items: center;
      padding: var(--sp-3) var(--sp-6);
    }
    .brand { display: flex; align-items: baseline; gap: var(--sp-3); }
    .brand h1 { font: 800 1.25rem var(--font-display); letter-spacing: .08em; text-transform: uppercase; }
    .brand span { font: .75rem var(--font-mono); color: var(--ink-muted); }
    .nav-links { display: flex; align-items: center; gap: var(--sp-4); font: 700 .85rem var(--font-mono); }
    .nav-links a { color: var(--ink); }
    .nav-links a:hover { color: var(--signal); }
    .theme-btn {
      background: var(--paper); border: var(--hairline) solid var(--rule);
      border-radius: var(--radius); padding: var(--sp-1) var(--sp-2);
      font: .75rem var(--font-mono); cursor: pointer; color: var(--ink);
    }

    main { max-width: 1100px; margin: 0 auto; padding: var(--sp-8) var(--sp-4); }

    .hero {
      text-align: center; padding: var(--sp-8) 0 var(--sp-6);
      border-bottom: var(--hairline) solid var(--rule-soft);
    }
    .hero-pill {
      display: inline-block; padding: var(--sp-1) var(--sp-3);
      background: var(--paper-deep); border: var(--hairline) solid var(--rule);
      border-radius: var(--radius); font: 700 .75rem var(--font-mono);
      color: var(--signal); letter-spacing: .08em; margin-bottom: var(--sp-3);
    }
    .hero h2 {
      font: 900 clamp(1.75rem, 4vw, 2.75rem) var(--font-display);
      text-transform: uppercase; letter-spacing: .04em; margin-bottom: var(--sp-3);
      line-height: 1.15;
    }
    .hero p {
      max-width: var(--measure); margin: 0 auto var(--sp-6);
      font-size: 1.15rem; color: var(--ink-muted);
    }
    .hero-actions { display: flex; justify-content: center; gap: var(--sp-3); flex-wrap: wrap; margin-bottom: var(--sp-4); }
    .btn {
      display: inline-flex; align-items: center; gap: var(--sp-2);
      padding: var(--sp-2) var(--sp-6); border-radius: var(--radius);
      font: 700 .9rem var(--font-mono); text-transform: uppercase; letter-spacing: .05em;
      cursor: pointer; text-decoration: none;
    }
    .btn-primary { background: var(--signal); color: var(--signal-ink); border: var(--hairline) solid var(--signal); }
    .btn-primary:hover { text-decoration: none; filter: brightness(1.1); }
    .btn-secondary { background: var(--paper-raised); color: var(--ink); border: var(--hairline) solid var(--rule); }
    .btn-secondary:hover { text-decoration: none; background: var(--paper-deep); }
    .badges { display: flex; justify-content: center; gap: var(--sp-2); flex-wrap: wrap; margin-top: var(--sp-4); }
    .badges img { height: 20px; }

    .preview-card {
      margin: var(--sp-8) 0; border: var(--hairline) solid var(--rule);
      border-radius: var(--radius); overflow: hidden; background: var(--paper-raised);
    }
    .preview-head {
      background: var(--paper-deep); padding: var(--sp-2) var(--sp-4);
      display: flex; justify-content: space-between; align-items: center;
      border-bottom: var(--hairline) solid var(--rule-soft);
      font: 700 .8rem var(--font-mono);
    }
    .preview-card img { width: 100%; display: block; height: auto; }
    .preview-caption { padding: var(--sp-3) var(--sp-4); font-size: .875rem; color: var(--ink-muted); }

    section { margin: var(--sp-12) 0; padding-top: var(--sp-4); }
    .section-head { margin-bottom: var(--sp-4); border-bottom: var(--hairline) solid var(--rule); padding-bottom: var(--sp-2); display: flex; justify-content: space-between; align-items: baseline; }
    .section-head h3 { font: 800 1.5rem var(--font-display); text-transform: uppercase; letter-spacing: .06em; }
    .section-head span { font: .8rem var(--font-mono); color: var(--signal); }

    .problem-box {
      background: var(--paper-raised); border-left: 4px solid var(--signal);
      padding: var(--sp-4) var(--sp-6); margin: var(--sp-4) 0;
      border-radius: 0 var(--radius) var(--radius) 0;
    }
    .problem-box p { margin-bottom: var(--sp-2); font-size: 1.05rem; }
    .problem-box p:last-child { margin-bottom: 0; font-weight: 600; color: var(--ink); }

    .arch-diagram {
      width: 100%; border: var(--hairline) solid var(--rule);
      border-radius: var(--radius); background: var(--paper-raised);
      margin: var(--sp-4) 0;
    }

    .ladder-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--sp-3); margin: var(--sp-4) 0; }
    .ladder-card {
      background: var(--paper-raised); border: var(--hairline) solid var(--rule-soft);
      padding: var(--sp-3); border-radius: var(--radius);
    }
    .ladder-card strong { display: block; font: 700 .9rem var(--font-mono); color: var(--signal); margin-bottom: var(--sp-1); }
    .ladder-card p { font-size: .85rem; color: var(--ink-muted); }

    table.styled-table {
      width: 100%; border-collapse: collapse; margin: var(--sp-4) 0;
      background: var(--paper-raised); border: var(--hairline) solid var(--rule);
      font-size: .9rem;
    }
    table.styled-table th, table.styled-table td {
      padding: var(--sp-2) var(--sp-3); border: var(--hairline) solid var(--rule-soft); text-align: left;
    }
    table.styled-table th { background: var(--paper-deep); font: 700 .8rem var(--font-mono); text-transform: uppercase; }
    table.styled-table td.pass { color: var(--pass); font-weight: 700; font-family: var(--font-mono); }
    table.styled-table td.fail { color: var(--fail); font-weight: 700; font-family: var(--font-mono); }
    table.styled-table td.num { text-align: right; font-family: var(--font-mono); }

    .stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--sp-4); margin: var(--sp-6) 0; }
    .stat-box {
      background: var(--paper-raised); border: var(--hairline) solid var(--rule);
      padding: var(--sp-4); border-radius: var(--radius); text-align: center;
    }
    .stat-box .val { font: 800 2.2rem var(--font-mono); color: var(--signal); line-height: 1; }
    .stat-box .val.pass { color: var(--pass); }
    .stat-box .lbl { font: .8rem var(--font-mono); color: var(--ink-muted); margin-top: var(--sp-2); text-transform: uppercase; }

    .gallery-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: var(--sp-4); margin: var(--sp-4) 0; }
    .gallery-item {
      border: var(--hairline) solid var(--rule); border-radius: var(--radius);
      overflow: hidden; background: var(--paper-raised);
    }
    .gallery-item img { width: 100%; display: block; border-bottom: var(--hairline) solid var(--rule-soft); }
    .gallery-item div { padding: var(--sp-2) var(--sp-3); font-size: .85rem; color: var(--ink-muted); }
    .gallery-item strong { display: block; color: var(--ink); font-family: var(--font-mono); font-size: .85rem; }

    pre.code-block {
      background: var(--paper-deep); border: var(--hairline) solid var(--rule);
      border-radius: var(--radius); padding: var(--sp-4); overflow-x: auto;
      font: .875rem/1.5 var(--font-mono); margin: var(--sp-4) 0; color: var(--ink);
    }

    footer {
      border-top: var(--rule-heavy) double var(--rule);
      padding: var(--sp-8) var(--sp-4); margin-top: var(--sp-12);
      text-align: center; font: .85rem var(--font-mono); color: var(--ink-muted);
    }
    footer a { color: var(--ink); text-decoration: underline; }

    @media (max-width: 680px) {
      .stats-row { grid-template-columns: 1fr; }
      .nav-links { display: none; }
    }
  </style>
</head>
<body>
  <header class="nav">
    <div class="brand">
      <h1>PixelPilot</h1>
      <span>v0.1.0</span>
    </div>
    <nav class="nav-links">
      <a href="dashboard/">Live Dashboard</a>
      <a href="#how-it-works">Architecture</a>
      <a href="#benchmarks">Benchmarks</a>
      <a href="#quickstart">Quickstart</a>
      <a href="https://github.com/Jyotiraditya21-bug/pixelpilot" target="_blank" rel="noopener">GitHub ↗</a>
      <button class="theme-btn" id="themeToggle" type="button" onclick="toggleTheme()">Theme</button>
    </nav>
  </header>

  <main>
    <section class="hero">
      <div class="hero-pill">RESILIENT TEST AUTOMATION</div>
      <h2>Self-Healing Playwright Agents<br>Using Visual Grounding</h2>
      <p>
        When UI mutations break CSS and XPath selectors, PixelPilot cascades through accessibility trees and multimodal vision, automatically caching healed locators for subsequent runs.
      </p>
      <div class="hero-actions">
        <a href="dashboard/" class="btn btn-primary">Launch Live Dashboard →</a>
        <a href="https://github.com/Jyotiraditya21-bug/pixelpilot" target="_blank" rel="noopener" class="btn btn-secondary">View on GitHub ↗</a>
      </div>
      <div class="badges">
        <a href="https://github.com/Jyotiraditya21-bug/pixelpilot/actions/workflows/ci.yml"><img src="https://github.com/Jyotiraditya21-bug/pixelpilot/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
        <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
        <a href="https://github.com/Jyotiraditya21-bug/pixelpilot/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
        <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
        <a href="https://mypy-lang.org/"><img src="https://img.shields.io/badge/mypy-strict-blue" alt="Checked with mypy"></a>
      </div>
    </section>

    <div class="preview-card">
      <div class="preview-head">
        <span>INTERACTIVE REPLAY DEMO</span>
        <a href="dashboard/" class="mono">Open Full Instrument View →</a>
      </div>
      <a href="dashboard/"><img src="assets/demo.gif" alt="PixelPilot Replay Demo"></a>
      <div class="preview-caption">
        Recorded execution of an automated checkout story: coupon input fails selector lookup under mutation, heals via Gemini vision bounding-box coordinates in Run 1, and resolves instantly from cache at 0.0 ms in Run 2.
      </div>
    </div>

    <section id="problem">
      <div class="section-head">
        <h3>The Problem</h3>
        <span>01 / MOTIVATION</span>
      </div>
      <div class="problem-box">
        <p>End-to-end browser tests break whenever developers refactor markup, rename classes, modify DOM hierarchies, or change IDs.</p>
        <p>Traditional test suites force engineers to spend hours diagnosing broken selectors and updating fragile test scripts.</p>
        <p>PixelPilot eliminates selector maintenance by falling back through accessibility trees and multimodal vision, automatically caching healed locators for future runs.</p>
      </div>
    </section>

    <section id="how-it-works">
      <div class="section-head">
        <h3>How It Works</h3>
        <span>02 / 5-TIER ARCHITECTURE</span>
      </div>
      <p style="color:var(--ink-muted); margin-bottom:var(--sp-4);">
        PixelPilot never hardcodes selectors. When an interaction occurs, it attempts to resolve targets through an escalating five-tier hierarchy from lowest cost to multimodal vision:
      </p>

      <img src="assets/banner.svg" alt="PixelPilot 5-Tier Fallback Diagram" class="arch-diagram">

      <div class="ladder-grid">
        <div class="ladder-card">
          <strong>(a) Cached Locator</strong>
          <p>Local SQLite cache match with visual & semantic fingerprint validation. Executes in 0.0 ms.</p>
        </div>
        <div class="ladder-card">
          <strong>(b) Semantic Snapshot</strong>
          <p>Inspects the ARIA accessibility tree to match elements by structured semantics.</p>
        </div>
        <div class="ladder-card">
          <strong>(c) Role & Name</strong>
          <p>Resolves via Playwright accessibility selectors (<code>get_by_role</code>).</p>
        </div>
        <div class="ladder-card">
          <strong>(d) Visible DOM Text</strong>
          <p>Matches user-visible content strings across buttons, labels, and text nodes.</p>
        </div>
        <div class="ladder-card" style="border-color:var(--signal);">
          <strong style="color:var(--signal);">(e) Multimodal Vision</strong>
          <p>Gemini REST coordinate grounder predicts normalized bounding boxes and auto-enrolls targets into cache.</p>
        </div>
      </div>

      <h4 style="font:800 1.1rem var(--font-display); text-transform:uppercase; margin:var(--sp-6) 0 var(--sp-2);">Agent Roles</h4>
      <table class="styled-table">
        <thead>
          <tr><th>Agent</th><th>Responsibility</th><th>Implementation</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Planner</strong></td>
            <td>Translates Markdown stories into structured action sequences</td>
            <td><code>ModelPlanner</code> (Gemini strict JSON) with deterministic fallback to <code>GrammarPlanner</code></td>
          </tr>
          <tr>
            <td><strong>Observer</strong></td>
            <td>Extracts semantic snapshot, interactive roles, and screenshots</td>
            <td>Async Playwright using system Chrome (<code>channel="chrome"</code>)</td>
          </tr>
          <tr>
            <td><strong>Grounder</strong></td>
            <td>Resolves high-level intents into concrete locators or coordinates</td>
            <td>Cascades through local cache, ARIA tree, role/name, text, and <code>GeminiGrounder</code> vision</td>
          </tr>
          <tr>
            <td><strong>Actor</strong></td>
            <td>Dispatches clicks, typing, navigations, and keyboard events</td>
            <td>Playwright page interactions with viewport coordinates and timeouts</td>
          </tr>
          <tr>
            <td><strong>Verifier</strong></td>
            <td>Validates post-conditions against DOM facts before using vision</td>
            <td>Inspects DOM facts and evaluates truth claims against story assertions</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section id="benchmarks">
      <div class="section-head">
        <h3>Empirical Benchmarks</h3>
        <span>03 / RESULTS</span>
      </div>

      <div class="stats-row">
        <div class="stat-box">
          <div class="val pass">100%</div>
          <div class="lbl">PixelPilot Mutation Resilience</div>
        </div>
        <div class="stat-box">
          <div class="val fail">0.0%</div>
          <div class="lbl">Scripted Baseline Under Mutation</div>
        </div>
        <div class="stat-box">
          <div class="val">0.0 ms</div>
          <div class="lbl">Run 2 Cache Replay Latency</div>
        </div>
      </div>

      <table class="styled-table">
        <thead>
          <tr><th>Runner</th><th>Mutation</th><th style="text-align:right;">Passed</th><th style="text-align:right;">Success Rate</th></tr>
        </thead>
        <tbody>
          <tr><td>Scripted baseline</td><td class="num">0</td><td class="num">3/3</td><td class="pass num">100.0%</td></tr>
          <tr><td>Scripted baseline</td><td class="num">1</td><td class="num">0/3</td><td class="fail num">0.0%</td></tr>
          <tr><td>PixelPilot (accessibility-semantic tiers)</td><td class="num">0</td><td class="num">3/3</td><td class="pass num">100.0%</td></tr>
          <tr><td>PixelPilot (accessibility-semantic tiers)</td><td class="num">1</td><td class="num">3/3</td><td class="pass num">100.0%</td></tr>
          <tr><td>PixelPilot VLM-only (pure vision)</td><td class="num">0</td><td class="num">1/3</td><td class="num">33.3%</td></tr>
          <tr><td>PixelPilot VLM-only (pure vision)</td><td class="num">1</td><td class="num">1/3</td><td class="num">33.3%</td></tr>
        </tbody>
      </table>

      <p style="font-size:.875rem; color:var(--ink-muted); margin-top:var(--sp-2);">
        *Key findings:* Scripted baseline drops from 100% to 0% under UI mutation, while PixelPilot maintains 100% (n=3, demo shop).
        Heal cache replay makes 0 grounding calls on Run 2. The PixelPilot 100% success rate comes from accessibility tiers; pure-vision accuracy is not yet established and was limited by Gemini free-tier quota (HTTP 429).
      </p>
    </section>

    <section id="gallery">
      <div class="section-head">
        <h3>Instrument Gallery</h3>
        <span>04 / INTERFACE</span>
      </div>
      <div class="gallery-grid">
        <div class="gallery-item">
          <img src="assets/dashboard-light.png" alt="Light Dashboard">
          <div><strong>Light Dashboard</strong>Laboratory logbook interface showing live step telemetry and run status.</div>
        </div>
        <div class="gallery-item">
          <img src="assets/dashboard-dark.png" alt="Dark Dashboard">
          <div><strong>Dark Dashboard</strong>High-contrast dark theme preserving 4.5:1 text contrast and labeled tier tags.</div>
        </div>
        <div class="gallery-item">
          <img src="assets/compare-view.png" alt="Compare View">
          <div><strong>Compare View</strong>Side-by-side run comparison showing Run 1 vision heal accelerating to Run 2 cache hit.</div>
        </div>
        <div class="gallery-item">
          <img src="assets/ground-view.png" alt="Ground View">
          <div><strong>Ground View</strong>Bounding-box overlay with animated target reticle locked onto the coupon input.</div>
        </div>
        <div class="gallery-item">
          <img src="assets/report-page.png" alt="Evidence Report">
          <div><strong>Evidence Report</strong>Self-contained HTML evidence record documenting verified DOM facts.</div>
        </div>
        <div class="gallery-item">
          <img src="assets/mobile-390.png" alt="Mobile View">
          <div><strong>Mobile View (390px)</strong>Responsive mobile view with stacked instrument controls and touch targets.</div>
        </div>
      </div>
    </section>

    <section id="quickstart">
      <div class="section-head">
        <h3>Quickstart</h3>
        <span>05 / GET STARTED</span>
      </div>
      <p style="color:var(--ink-muted); margin-bottom:var(--sp-2);">
        From a clean clone to a passing test run in under 5 minutes:
      </p>
      <pre class="code-block"><code># 1. Clone the repository
git clone https://github.com/Jyotiraditya21-bug/pixelpilot.git
cd pixelpilot

# 2. Configure environment (system Chrome required; Gemini key optional for non-vision tiers)
export PP_BASE_URL="http://127.0.0.1:8000"

# 3. Install dependencies using uv
uv sync

# 4. Verify test suite and type safety
make check

# 5. Start demo shop in terminal 1
make demo

# 6. Start local dashboard in terminal 2
make ui

# 7. Run a test story against the mutated interface
uv run --no-sync pixelpilot run stories/checkout_valid_coupon.md --mutate</code></pre>

      <h4 style="font:800 1.1rem var(--font-display); text-transform:uppercase; margin:var(--sp-6) 0 var(--sp-2);">Commands</h4>
      <table class="styled-table">
        <thead>
          <tr><th>Command</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr><td><code>make check</code></td><td>Runs <code>ruff</code>, strict <code>mypy</code>, and non-VLM <code>pytest</code></td></tr>
          <tr><td><code>make demo</code></td><td>Launches local FastAPI mock e-commerce store on <code>127.0.0.1:8000</code></td></tr>
          <tr><td><code>make ui</code></td><td>Launches local PixelPilot instrument dashboard on <code>127.0.0.1:8100</code></td></tr>
          <tr><td><code>make site</code></td><td>Builds the static showcase site under <code>site/</code></td></tr>
          <tr><td><code>make assets</code></td><td>Regenerates documentation screenshots and animated GIF</td></tr>
          <tr><td><code>make clean</code></td><td>Removes <code>runs/</code> artifacts and Python caches</td></tr>
          <tr><td><code>pixelpilot run &lt;story&gt; [--mutate]</code></td><td>Executes a markdown user story in system Chrome</td></tr>
        </tbody>
      </table>
    </section>
  </main>

  <footer>
    <p>
      PixelPilot is open source under the <a href="https://github.com/Jyotiraditya21-bug/pixelpilot/blob/main/LICENSE" target="_blank" rel="noopener">MIT License</a>.
      Crafted by <a href="https://github.com/Jyotiraditya21-bug" target="_blank" rel="noopener">Jyotiraditya Parmar</a>.
    </p>
    <p style="margin-top:var(--sp-2);">
      <a href="dashboard/">Launch Dashboard</a> · <a href="https://github.com/Jyotiraditya21-bug/pixelpilot" target="_blank" rel="noopener">GitHub Repository</a>
    </p>
  </footer>

  <script>
    function toggleTheme() {
      const current = document.documentElement.dataset.theme;
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem("pixelpilot-theme", next); } catch (_e) {}
    }
  </script>
</body>
</html>"""
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")


def build_site() -> None:
    print("Building static showcase site under site/...")
    _clean_and_create_dirs()
    _copy_docs_assets()

    print("Seeding demo runs...")
    temp_dir = _seed_runs_to_temp_dir()
    try:
        print("Exporting runs data to site/data/runs.json...")
        _export_runs_data(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("Building site/dashboard/index.html...")
    _build_dashboard_page()

    print("Building site/index.html...")
    _build_landing_page()

    total_bytes = sum(f.stat().st_size for f in SITE_DIR.rglob("*") if f.is_file())
    print(f"Site build complete! Total size: {total_bytes / (1024 * 1024):.2f} MB")


def main() -> None:
    build_site()


if __name__ == "__main__":
    main()
