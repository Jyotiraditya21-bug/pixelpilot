from __future__ import annotations

import asyncio
import io
import subprocess
import sys
import time
from pathlib import Path

import httpx
from PIL import Image
from playwright.async_api import async_playwright

from scripts.seed_demo_runs import seed_demo_runs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "docs" / "assets"
RUNS_DIR = PROJECT_ROOT / "runs"

DEMO_URL = "http://127.0.0.1:8000"
DASHBOARD_URL = "http://127.0.0.1:8100"


def _is_url_ready(url: str) -> bool:
    try:
        res = httpx.get(url, timeout=1.0)
        return res.status_code < 500
    except Exception:
        return False


def _ensure_servers() -> tuple[subprocess.Popen[bytes] | None, subprocess.Popen[bytes] | None]:
    demo_proc = None
    dashboard_proc = None

    if not _is_url_ready(f"{DEMO_URL}/ready"):
        print("Starting demo server on :8000...")
        demo_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "demo_app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    if not _is_url_ready(f"{DASHBOARD_URL}/"):
        print("Starting dashboard server on :8100...")
        dashboard_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "pixelpilot.dashboard.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8100",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        demo_ok = _is_url_ready(f"{DEMO_URL}/ready") or _is_url_ready(f"{DEMO_URL}/")
        dash_ok = _is_url_ready(f"{DASHBOARD_URL}/")
        if demo_ok and dash_ok:
            break
        time.sleep(0.3)
    else:
        if demo_proc:
            demo_proc.terminate()
        if dashboard_proc:
            dashboard_proc.terminate()
        raise RuntimeError("Servers failed to start within 15 seconds")

    return demo_proc, dashboard_proc


def _save_downscaled(png_bytes: bytes, target_path: Path, width: int, height: int) -> None:
    img = Image.open(io.BytesIO(png_bytes))
    resized = img.resize((width, height), Image.Resampling.LANCZOS)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    resized.save(target_path, "PNG", optimize=True)
    size_kb = target_path.stat().st_size / 1024
    print(f"Saved {target_path.name} ({width}x{height}, {size_kb:.1f} KB)")


def _build_social_preview_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  :root {
    --bg: #f4efe4;
    --surface: #fbf7ee;
    --border: #ddd5c7;
    --ink: #171813;
    --ink-muted: #5d6058;
    --rule: #77786f;
    --rule-soft: #d3ccbd;
    --signal: #8b3b18;
    --pass: #2c5e3b;
    --teal: #1f5f5b;
    --ochre: #8a5a00;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1280px;
    height: 640px;
    background-color: var(--bg);
    background-image:
      linear-gradient(to right, var(--rule-soft) 1px, transparent 1px),
      linear-gradient(to bottom, var(--rule-soft) 1px, transparent 1px);
    background-size: 32px 32px;
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
      "Helvetica Neue", sans-serif;
    padding: 36px 44px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    position: relative;
    overflow: hidden;
  }
  .card-border {
    position: absolute;
    inset: 16px;
    border: 1px solid var(--rule);
    pointer-events: none;
  }
  .corner-mark {
    position: absolute;
    width: 12px;
    height: 12px;
    border: 1px solid var(--signal);
  }
  .corner-tl { top: 12px; left: 12px; border-right: none; border-bottom: none; }
  .corner-tr { top: 12px; right: 12px; border-left: none; border-bottom: none; }
  .corner-bl { bottom: 12px; left: 12px; border-right: none; border-top: none; }
  .corner-br { bottom: 12px; right: 12px; border-left: none; border-top: none; }

  header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    border-bottom: 2px solid var(--ink);
    padding-bottom: 14px;
  }
  .brand-group {
    display: flex;
    align-items: baseline;
    gap: 16px;
  }
  .brand-title {
    font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
    font-size: 38px;
    font-weight: 800;
    letter-spacing: -0.04em;
    color: var(--ink);
  }
  .brand-badge {
    font-family: ui-monospace, monospace;
    font-size: 13px;
    font-weight: 700;
    background: var(--signal);
    color: #fff;
    padding: 3px 8px;
    border-radius: 2px;
    letter-spacing: 0.05em;
  }
  .tagline {
    font-size: 17px;
    color: var(--ink-muted);
    font-weight: 500;
  }
  .specs {
    font-family: ui-monospace, monospace;
    font-size: 13px;
    color: var(--ink-muted);
    letter-spacing: 0.03em;
  }

  main {
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: 28px;
    align-items: stretch;
    margin: 18px 0;
  }

  .left-pane {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 20px 24px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  .section-label {
    font-family: ui-monospace, monospace;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--ink-muted);
    letter-spacing: 0.1em;
    margin-bottom: 12px;
  }

  .ladder {
    display: flex;
    flex-direction: column;
    gap: 7px;
  }
  .ladder-step {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 12px;
    border: 1px solid var(--border);
    background: var(--bg);
    font-family: ui-monospace, monospace;
    font-size: 12px;
  }
  .ladder-step.active {
    border-color: var(--signal);
    background: #fbf0e8;
  }
  .step-name { font-weight: 700; }
  .step-note { color: var(--ink-muted); font-size: 11px; }

  .proof-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid var(--border);
  }
  .stat-card {
    text-align: left;
  }
  .stat-val {
    font-family: ui-monospace, monospace;
    font-size: 26px;
    font-weight: 800;
    color: var(--ink);
    line-height: 1;
  }
  .stat-val.signal { color: var(--signal); }
  .stat-val.pass { color: var(--pass); }
  .stat-lbl {
    font-size: 11px;
    color: var(--ink-muted);
    margin-top: 4px;
    font-weight: 500;
  }

  .right-pane {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 20px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  .instrument-box {
    border: 1px dashed var(--rule);
    background: var(--bg);
    padding: 14px;
    position: relative;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  .box-header {
    display: flex;
    justify-content: space-between;
    font-family: ui-monospace, monospace;
    font-size: 11px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
  }
  .target-preview {
    margin: 16px 0;
    position: relative;
    border: 1px solid var(--border);
    background: #fff;
    height: 120px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-image:
      linear-gradient(to right, #f4efe4 1px, transparent 1px),
      linear-gradient(to bottom, #f4efe4 1px, transparent 1px);
    background-size: 16px 16px;
  }
  .reticle {
    position: absolute;
    width: 140px;
    height: 38px;
    border: 2px solid var(--signal);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .reticle::before {
    content: "TARGET";
    position: absolute;
    top: -20px;
    left: -2px;
    background: var(--signal);
    color: #fff;
    font-family: ui-monospace, monospace;
    font-weight: 700;
    font-size: 10px;
    padding: 2px 6px;
    letter-spacing: 0.05em;
  }
  .reticle-label {
    font-family: ui-monospace, monospace;
    font-size: 11px;
    color: var(--signal);
    font-weight: 700;
  }
  .box-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-family: ui-monospace, monospace;
    font-size: 12px;
    border-top: 1px solid var(--border);
    padding-top: 8px;
  }
  .badge-healed {
    background: #e5ece6;
    color: var(--pass);
    padding: 2px 8px;
    border-radius: 2px;
    font-weight: 700;
  }
  .badge-tier {
    color: var(--signal);
    font-weight: 700;
  }

  footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid var(--rule);
    padding-top: 10px;
    font-family: ui-monospace, monospace;
    font-size: 12px;
    color: var(--ink-muted);
  }
  .footer-links {
    display: flex;
    gap: 20px;
  }
</style>
</head>
<body>
  <div class="card-border"></div>
  <div class="corner-mark corner-tl"></div>
  <div class="corner-mark corner-tr"></div>
  <div class="corner-mark corner-bl"></div>
  <div class="corner-mark corner-br"></div>

  <header>
    <div class="brand-group">
      <h1 class="brand-title">PIXELPILOT</h1>
      <span class="brand-badge">OPEN SOURCE</span>
      <span class="tagline">Self-healing Playwright agents using visual grounding</span>
    </div>
    <div class="specs">PYTHON 3.11+ · UV · MIT</div>
  </header>

  <main>
    <div class="left-pane">
      <div>
        <div class="section-label">01 / Resilient Fallback Architecture</div>
        <div class="ladder">
          <div class="ladder-step">
            <span class="step-name">(a) Cached Locator</span>
            <span class="step-note">0 ms instant hit</span>
          </div>
          <div class="ladder-step">
            <span class="step-name">(b) Semantic Snapshot</span>
            <span class="step-note">ARIA accessibility tree</span>
          </div>
          <div class="ladder-step">
            <span class="step-name">(c) Role & Accessible Name</span>
            <span class="step-note">Playwright get_by_role</span>
          </div>
          <div class="ladder-step">
            <span class="step-name">(d) Visible DOM Text</span>
            <span class="step-note">get_by_text content match</span>
          </div>
          <div class="ladder-step active">
            <span class="step-name">(e) Multimodal Vision</span>
            <span class="step-note">Gemini bbox grounding & heal</span>
          </div>
        </div>
      </div>
      <div class="proof-stats">
        <div class="stat-card">
          <div class="stat-val pass">100%</div>
          <div class="stat-lbl">Healed under mutation</div>
        </div>
        <div class="stat-card">
          <div class="stat-val signal">0 ms</div>
          <div class="stat-lbl">Run 2 cache replay</div>
        </div>
        <div class="stat-card">
          <div class="stat-val">&lt;400 MB</div>
          <div class="stat-lbl">Zero-space system Chrome</div>
        </div>
      </div>
    </div>

    <div class="right-pane">
      <div class="section-label">02 / Live Visual Telemetry</div>
      <div class="instrument-box">
        <div class="box-header">
          <span>SEED01VLMHEAL · STEP 02</span>
          <span>1280 × 900</span>
        </div>
        <div class="target-preview">
          <div class="reticle">
            <span class="reticle-label">#coupon-input</span>
          </div>
        </div>
        <div class="box-footer">
          <span class="badge-tier">TIER: vlm_bbox · 1042ms</span>
          <span class="badge-healed">✓ HEALED</span>
        </div>
      </div>
    </div>
  </main>

  <footer>
    <div class="footer-links">
      <span>Zero npm dependencies</span>
      <span>•</span>
      <span>No browser downloads</span>
      <span>•</span>
      <span>OpenTelemetry traces</span>
    </div>
    <div>github.com/jyotiraditya/pixelpilot</div>
  </footer>
</body>
</html>"""


async def capture_assets() -> None:
    demo_proc, dashboard_proc = _ensure_servers()
    try:
        print("Seeding demo runs...")
        await seed_demo_runs()

        ASSETS_DIR.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            print("Launching system Chrome...")
            browser = await p.chromium.launch(channel="chrome", headless=True)

            # 1. Desktop Context (1440x900 @ 2x)
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=2,
            )
            page = await context.new_page()

            # Dashboard Light
            print("Capturing dashboard-light.png...")
            await page.goto(f"{DASHBOARD_URL}/", wait_until="networkidle")
            await page.wait_for_selector(".history-item")
            await page.evaluate("applyTheme('light')")
            await page.evaluate(
                "async () => { await loadReplay('seed02cachhit'); stopReplay(); selectStep(1); }"
            )
            await page.wait_for_timeout(800)
            buf = await page.screenshot(full_page=False)
            _save_downscaled(buf, ASSETS_DIR / "dashboard-light.png", 1440, 900)

            # Dashboard Dark
            print("Capturing dashboard-dark.png...")
            await page.evaluate("applyTheme('dark')")
            await page.wait_for_timeout(400)
            buf = await page.screenshot(full_page=False)
            _save_downscaled(buf, ASSETS_DIR / "dashboard-dark.png", 1440, 900)

            # Ground View (bounding box overlay on step 1 of seed01vlmheal)
            print("Capturing ground-view.png...")
            await page.evaluate("applyTheme('light')")
            await page.evaluate(
                "async () => { await loadReplay('seed01vlmheal'); stopReplay(); selectStep(1); }"
            )
            await page.wait_for_timeout(1400)  # Wait for target drawing animation to fully complete
            buf = await page.screenshot(full_page=False)
            _save_downscaled(buf, ASSETS_DIR / "ground-view.png", 1440, 900)

            # Compare View (comparing seed01vlmheal and seed02cachhit)
            print("Capturing compare-view.png...")
            await page.evaluate("""async () => {
                const cbs = document.querySelectorAll('.compare-select');
                cbs.forEach(cb => {
                    cb.checked = (cb.value === 'seed01vlmheal' || cb.value === 'seed02cachhit');
                });
                if (cbs.length > 0) updateCompareSelection(cbs[0]);
                await compareSelected();
            }""")
            await page.wait_for_selector('#comparePanel[data-visible="true"]')
            await page.wait_for_timeout(600)
            buf = await page.screenshot(full_page=False)
            _save_downscaled(buf, ASSETS_DIR / "compare-view.png", 1440, 900)

            # Report Page
            print("Capturing report-page.png...")
            await page.goto(
                f"{DASHBOARD_URL}/api/runs/seed01vlmheal/report", wait_until="networkidle"
            )
            await page.wait_for_timeout(600)
            buf = await page.screenshot(full_page=False)
            _save_downscaled(buf, ASSETS_DIR / "report-page.png", 1440, 900)

            await page.close()
            await context.close()

            # Mobile View (390x844 @ 2x)
            print("Capturing mobile-390.png...")
            mobile_context = await browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
            )
            mobile_page = await mobile_context.new_page()
            await mobile_page.goto(f"{DASHBOARD_URL}/", wait_until="networkidle")
            await mobile_page.wait_for_selector(".history-item")
            await mobile_page.evaluate(
                "async () => { await loadReplay('seed02cachhit'); stopReplay(); selectStep(1); }"
            )
            await mobile_page.wait_for_timeout(800)
            buf = await mobile_page.screenshot(full_page=False)
            _save_downscaled(buf, ASSETS_DIR / "mobile-390.png", 390, 844)
            await mobile_page.close()
            await mobile_context.close()

            # Social Preview (1280x640 @ 2x)
            print("Capturing social-preview.png...")
            social_context = await browser.new_context(
                viewport={"width": 1280, "height": 640},
                device_scale_factor=2,
            )
            social_page = await social_context.new_page()
            await social_page.set_content(_build_social_preview_html(), wait_until="load")
            await social_page.wait_for_timeout(300)
            buf = await social_page.screenshot(full_page=False)
            _save_downscaled(buf, ASSETS_DIR / "social-preview.png", 1280, 640)
            await social_page.close()
            await social_context.close()

            # Demo GIF (20 to 30 frames, 960px wide, palette-quantized)
            print("Capturing demo.gif frames...")
            gif_context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                device_scale_factor=1,
            )
            gif_page = await gif_context.new_page()
            await gif_page.goto(f"{DASHBOARD_URL}/", wait_until="networkidle")
            await gif_page.wait_for_selector(".history-item")
            await gif_page.evaluate("applyTheme('light')")
            await gif_page.evaluate(
                "async () => { await loadReplay('seed01vlmheal'); stopReplay(); selectStep(0); }"
            )
            await gif_page.wait_for_timeout(400)

            raw_frames: list[Image.Image] = []

            # Step 0: Overview
            for _ in range(3):
                frame_buf = await gif_page.screenshot()
                raw_frames.append(Image.open(io.BytesIO(frame_buf)))
                await gif_page.wait_for_timeout(100)

            # Step 1: The vision healing step with bbox animation
            await gif_page.evaluate("selectStep(1)")
            # Sample across the animation progress
            for _ in range(8):
                await gif_page.wait_for_timeout(120)
                frame_buf = await gif_page.screenshot()
                raw_frames.append(Image.open(io.BytesIO(frame_buf)))

            # Hold on completed Step 1
            for _ in range(3):
                frame_buf = await gif_page.screenshot()
                raw_frames.append(Image.open(io.BytesIO(frame_buf)))
                await gif_page.wait_for_timeout(100)

            # Step 2: Typing coupon
            await gif_page.evaluate("selectStep(2)")
            await gif_page.wait_for_timeout(300)
            for _ in range(3):
                frame_buf = await gif_page.screenshot()
                raw_frames.append(Image.open(io.BytesIO(frame_buf)))
                await gif_page.wait_for_timeout(100)

            # Step 3: Apply coupon
            await gif_page.evaluate("selectStep(3)")
            await gif_page.wait_for_timeout(300)
            for _ in range(3):
                frame_buf = await gif_page.screenshot()
                raw_frames.append(Image.open(io.BytesIO(frame_buf)))
                await gif_page.wait_for_timeout(100)

            # Step 4: Checkout verify passed
            await gif_page.evaluate("selectStep(4)")
            await gif_page.wait_for_timeout(400)
            for _ in range(5):
                frame_buf = await gif_page.screenshot()
                raw_frames.append(Image.open(io.BytesIO(frame_buf)))
                await gif_page.wait_for_timeout(100)

            await gif_page.close()
            await gif_context.close()
            await browser.close()

            # Process GIF frames: resize to 960x600, quantize to 128 colors
            print(f"Processing {len(raw_frames)} GIF frames...")
            quantized_frames: list[Image.Image] = []
            target_w = 960
            target_h = int(960 * (800 / 1280))  # 600

            for frame in raw_frames:
                resized = frame.resize((target_w, target_h), Image.Resampling.LANCZOS)
                # Convert to palette mode with adaptive palette
                p_frame = resized.convert("RGB").convert(
                    "P", palette=Image.Palette.ADAPTIVE, colors=128
                )
                quantized_frames.append(p_frame)

            gif_path = ASSETS_DIR / "demo.gif"
            quantized_frames[0].save(
                gif_path,
                save_all=True,
                append_images=quantized_frames[1:],
                duration=280,
                loop=0,
                optimize=True,
            )
            gif_size_mb = gif_path.stat().st_size / (1024 * 1024)
            print(f"Saved demo.gif ({len(quantized_frames)} frames, 960x600, {gif_size_mb:.2f} MB)")

    finally:
        if demo_proc is not None:
            demo_proc.terminate()
            demo_proc.wait(timeout=5)
        if dashboard_proc is not None:
            dashboard_proc.terminate()
            dashboard_proc.wait(timeout=5)


def main() -> None:
    asyncio.run(capture_assets())


if __name__ == "__main__":
    main()
