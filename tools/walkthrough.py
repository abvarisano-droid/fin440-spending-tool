"""Walk every page with the sample data at desktop (1280) and phone (390) width, frame by frame.

Dev tool only (not part of the app). Needs Playwright and Chrome:
    pip install playwright
    python tools/walkthrough.py http://localhost:8533 run1 [out_dir]

Frames go to out_dir/<tag>/ (default: the system temp folder, never the repo).
Per page it prints the frame count, Streamlit exceptions, and elements that stick out past the
viewport. Internal scrollers (chart SVG, table canvas, KaTeX, multiselect pills) can show up in
that list without being a page-level sideways scroll; check the frames before calling it a bug.
"""
import os
import sys
import tempfile

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8533"
TAG = sys.argv[2] if len(sys.argv) > 2 else "run"
BASE = sys.argv[3] if len(sys.argv) > 3 else os.path.join(tempfile.gettempdir(), "spend-shadow-walkthrough")
OUT = os.path.join(BASE, TAG)
os.makedirs(OUT, exist_ok=True)
PAGES = [("Spending breakdown", "spending", 5), ("Shadow portfolio", "shadow", 12),
         ("Roth calculator", "roth", 8), ("Proof", "proof", 14)]
VIEWS = {"desktop": dict(width=1280, height=860), "phone": dict(width=390, height=844)}
SCROLLER = "document.querySelector('[data-testid=\"stMain\"]') || document.scrollingElement"


def frames(page, name, maxn=12):
    """Scroll Streamlit's main scroll container one viewport at a time, one screenshot per step."""
    page.wait_for_timeout(600)
    total, view = page.evaluate(f"() => {{ const m = {SCROLLER}; m.scrollTop = 0; return [m.scrollHeight, m.clientHeight]; }}")
    n, y = 0, 0
    while n < maxn:
        page.screenshot(path=os.path.join(OUT, f"{name}_{n:02d}.png"))
        n += 1
        y += int(view * 0.85)
        if y >= total - 10:
            break
        page.evaluate(f"() => {{ const m = {SCROLLER}; m.scrollTop = {y}; }}")
        page.wait_for_timeout(400)
    return n


def go(page, label):
    """Client-side nav so the session (and the loaded sample) survives."""
    return page.evaluate(f"""() => {{
        const a = [...document.querySelectorAll('a')].find(a => a.textContent.trim().endsWith({label!r}));
        if (a) {{ a.click(); return true; }} return false; }}""")


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    for vname, vp in VIEWS.items():
        phone = vname == "phone"
        ctx = browser.new_context(viewport=vp, device_scale_factor=1, is_mobile=phone, has_touch=phone)
        page = ctx.new_page()
        page.goto(URL)
        page.wait_for_selector(".st-key-use_sample button", timeout=60000)
        page.wait_for_timeout(1500)
        frames(page, f"{vname}_upload_empty", 3)
        page.click(".st-key-use_sample button")
        page.wait_for_selector(".st-key-loaded_summary", timeout=30000)
        page.wait_for_timeout(1000)
        frames(page, f"{vname}_upload_loaded", 4)
        for label, slug, wait in PAGES:
            if not go(page, label):
                print("nav link not found:", vname, label)
                continue
            page.wait_for_timeout(wait * 1000)
            n = frames(page, f"{vname}_{slug}")
            errs = page.evaluate("() => document.querySelectorAll('[data-testid=\"stException\"]').length")
            overflow = page.evaluate("""() => { const w = document.documentElement.clientWidth;
                return [...document.querySelectorAll('[data-testid="stMain"] *')]
                  .filter(e => e.getBoundingClientRect().right > w + 1 && getComputedStyle(e).position !== 'fixed')
                  .slice(0, 5).map(e => (e.dataset.testid || e.className || e.tagName).toString().slice(0, 50)); }""")
            print(f"{vname:7s} {slug:9s} frames={n} exceptions={errs} overflow={overflow}")
        ctx.close()
    browser.close()
print("saved to", OUT)
