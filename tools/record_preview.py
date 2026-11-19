"""Record the landing-page preview video: a scripted tour of the app on the fictional sample.

Dev tool only (not part of the app). Needs Playwright with Chrome; mp4 conversion needs
imageio-ffmpeg (pip install imageio-ffmpeg). Run against a local server:
    python tools/record_preview.py http://localhost:8542
Writes assets/preview.mp4 (H.264, no audio). Only the fictional sample data is shown.
"""
import os
import shutil
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8542"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "preview.mp4")
SIZE = dict(width=1280, height=720)
MAIN = "document.querySelector('[data-testid=\"stMain\"]')"


def go(page, label):
    page.evaluate(f"""() => [...document.querySelectorAll('a')]
        .find(a => a.textContent.trim().endsWith({label!r})).click()""")


def glide(page, to, ms=1600):
    """Smooth scroll of Streamlit's main container to `to` px."""
    page.evaluate(f"() => {MAIN}.scrollTo({{top: {to}, behavior: 'smooth'}})")
    page.wait_for_timeout(ms)


def load_sample(page):
    page.goto(URL)
    page.wait_for_selector(".st-key-use_sample button", timeout=60000)
    page.wait_for_timeout(1200)
    page.click(".st-key-use_sample button")
    page.wait_for_selector(".st-key-loaded_summary", timeout=30000)


def warm(browser):
    """Visit the price pages once so the recording doesn't show loading spinners."""
    ctx = browser.new_context(viewport=SIZE)
    page = ctx.new_page()
    load_sample(page)
    for label, wait in (("Shadow portfolio", 14000), ("Roth calculator", 6000), ("Proof", 14000)):
        go(page, label)
        page.wait_for_timeout(wait)
    ctx.close()


def tour(browser, video_dir):
    ctx = browser.new_context(viewport=SIZE, record_video_dir=video_dir, record_video_size=SIZE)
    page = ctx.new_page()
    load_sample(page)
    page.wait_for_timeout(2200)

    go(page, "Spending breakdown")
    page.wait_for_timeout(2500)
    glide(page, 520)
    page.wait_for_timeout(1200)

    go(page, "Shadow portfolio")
    page.wait_for_timeout(4000)
    glide(page, 560)
    page.wait_for_timeout(1500)
    glide(page, 1200)
    page.wait_for_timeout(1500)

    go(page, "Roth calculator")
    page.wait_for_timeout(3000)
    glide(page, 560)
    page.wait_for_timeout(2500)
    glide(page, 0, 1200)
    page.get_by_text("Redirect discretionary spending", exact=True).click()
    page.wait_for_timeout(2500)
    glide(page, 380)
    page.wait_for_timeout(2500)

    go(page, "Proof")
    page.wait_for_timeout(4000)
    glide(page, 160)
    page.wait_for_timeout(2500)

    path = page.video.path()
    ctx.close()
    return path


def to_mp4(src, dst):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    # skip the first 4 s (the empty Upload page), so the video opens on the loaded sample
    subprocess.run([ff, "-y", "-ss", "4", "-i", src, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "28",
                    "-preset", "slow", "-movflags", "+faststart", "-an", dst], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    tmp = tempfile.mkdtemp(prefix="spend-shadow-preview-")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        warm(browser)
        webm = tour(browser, tmp)
        browser.close()
    to_mp4(webm, OUT)
    shutil.rmtree(tmp, ignore_errors=True)
    print("saved", os.path.abspath(OUT), f"{os.path.getsize(OUT) / 1e6:.1f} MB")
