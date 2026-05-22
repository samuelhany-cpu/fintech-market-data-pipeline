"""
Capture animated GIFs of the Streamlit dashboard using Playwright.

Prerequisites:
    pip install playwright pillow
    playwright install chromium

Usage:
    python scripts/capture_demo.py

Output:
    docs/demo_price_chart.gif
    docs/demo_analytics.gif
    docs/demo_quality.gif
"""

import io
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

STREAMLIT_PORT = 8502
STREAMLIT_URL = f"http://localhost:{STREAMLIT_PORT}"
DOCS_DIR = Path(__file__).parent.parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)

GIF_DURATION = 180  # ms per frame in output GIF


def _wait_for_streamlit(timeout_s: int = 40) -> None:
    import requests

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if requests.get(STREAMLIT_URL, timeout=2).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(f"Streamlit did not start within {timeout_s}s")


def _scroll_shots(page, steps: int = 6, delay: float = 0.45) -> list[bytes]:
    frames: list[bytes] = []
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.3)
    for i in range(steps):
        frames.append(page.screenshot(full_page=False))
        page.evaluate(f"window.scrollBy(0, {180 * (i + 1)})")
        time.sleep(delay)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.3)
    frames.append(page.screenshot(full_page=False))
    return frames


def _save_gif(frames: list[bytes], path: Path) -> None:
    images = [Image.open(io.BytesIO(f)).convert("RGB") for f in frames]
    images[0].save(
        path,
        save_all=True,
        append_images=images[1:],
        loop=0,
        duration=GIF_DURATION,
        optimize=True,
    )
    print(f"  Saved {path}  ({len(images)} frames)")


def _click_tab(page, label: str) -> None:
    page.get_by_role("tab", name=label).click()
    time.sleep(2.5)  # wait for Plotly charts to render


def capture(page) -> None:
    page.set_viewport_size({"width": 1400, "height": 860})
    page.goto(STREAMLIT_URL, wait_until="networkidle")
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=20_000)
    time.sleep(3)

    print("Capturing: Price Chart tab...")
    _click_tab(page, "📊 Price Chart")
    _save_gif(_scroll_shots(page, steps=5), DOCS_DIR / "demo_price_chart.gif")

    print("Capturing: Analytics tab...")
    _click_tab(page, "📉 Analytics")
    _save_gif(_scroll_shots(page, steps=6), DOCS_DIR / "demo_analytics.gif")

    print("Capturing: Data Quality tab...")
    _click_tab(page, "✅ Data Quality")
    time.sleep(1)
    _save_gif(_scroll_shots(page, steps=4), DOCS_DIR / "demo_quality.gif")


def main() -> None:
    print("Starting Streamlit server...")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            "src/dashboard/app.py",
            "--server.port", str(STREAMLIT_PORT),
            "--server.headless", "true",
            "--server.runOnSave", "false",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_streamlit()
        print(f"Streamlit ready at {STREAMLIT_URL}")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            capture(browser.new_page())
            browser.close()
        print("\nAll GIFs saved to docs/")
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
