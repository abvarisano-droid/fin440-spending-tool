"""Record the landing-page tutorial video: how to use Spend Shadow, step by step.

Dev tool only (not part of the app). The step captions, highlight ring and cursor are drawn into
the page by this script while recording; the app itself never shows them. Uses the fictional
sample CSV only. Needs Playwright with Chrome and imageio-ffmpeg:
    python tools/record_tutorial.py http://localhost:8544
Writes assets/tutorial.mp4 (H.264, no audio).
"""
import os
import shutil
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8544"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAMPLE = os.path.join(ROOT, "sample_data", "sample_transactions.csv")
OUT = os.path.join(ROOT, "assets", "tutorial.mp4")
SIZE = dict(width=1280, height=720)
MAIN = "document.querySelector('[data-testid=\"stMain\"]')"

# Overlay drawn on top of the page during recording only. Colors follow DESIGN.md v3.
OVERLAY_JS = r"""
() => {
  if (document.getElementById('tut-cap')) return;
  const css = document.createElement('style');
  css.textContent = `
    #tut-cap { position: fixed; left: 50%; bottom: 28px; transform: translateX(-50%);
      max-width: 900px; padding: 14px 22px; border-radius: 18px; z-index: 99999;
      background: rgba(10,20,32,.92); color: #fff; font: 500 19px/1.4 Geist, Arial, sans-serif;
      box-shadow: 0 12px 40px rgba(10,20,32,.25); transition: opacity .35s; opacity: 0; }
    #tut-cap b { color: #34E0D6; font-weight: 600; margin-right: 8px; }
    #tut-ring { position: fixed; z-index: 99998; border: 3px solid #34E0D6; border-radius: 20px;
      box-shadow: 0 0 0 6px rgba(52,224,214,.22); pointer-events: none; opacity: 0;
      transition: all .45s cubic-bezier(.2,.8,.2,1); }
    #tut-cur { position: fixed; z-index: 100000; width: 22px; height: 22px; margin: -11px 0 0 -11px;
      border-radius: 50%; background: rgba(10,20,32,.85); border: 3px solid #fff; pointer-events: none;
      left: 640px; top: 360px; transition: left .7s cubic-bezier(.2,.8,.2,1), top .7s cubic-bezier(.2,.8,.2,1), transform .15s; }
    #tut-card { position: fixed; inset: 0; z-index: 100001; display: flex; flex-direction: column;
      align-items: center; justify-content: center; gap: 14px; background: #F0F6FA; color: #1A1D1B;
      transition: opacity .5s; }
    #tut-card h1 { font: 400 54px/1.1 Georgia, serif; margin: 0; }
    #tut-card p { font: 400 22px/1.4 Arial, sans-serif; color: #4F5752; margin: 0; }
    .st-key-landing_preview { display: none !important; }`;
  document.head.appendChild(css);
  for (const id of ['tut-cap', 'tut-ring', 'tut-cur']) {
    const d = document.createElement('div'); d.id = id; document.body.appendChild(d);
  }
}
"""


def overlay(page):
    page.evaluate(OVERLAY_JS)


def caption(page, step, text, ms=0):
    page.evaluate("""([s, t]) => { const c = document.getElementById('tut-cap');
        c.innerHTML = (s ? '<b>' + s + '</b>' : '') + t; c.style.opacity = 1; }""", [step, text])
    page.wait_for_timeout(ms)


def card(page, title, sub, ms):
    page.evaluate("""([t, s]) => { const d = document.createElement('div'); d.id = 'tut-card';
        d.innerHTML = '<h1>' + t + '</h1><p>' + s + '</p>'; document.body.appendChild(d); }""", [title, sub])
    page.wait_for_timeout(ms)
    page.evaluate("() => { const d = document.getElementById('tut-card'); d.style.opacity = 0; "
                  "setTimeout(() => d.remove(), 500); }")
    page.wait_for_timeout(500)


def ring(page, selector, ms=0, pad=8):
    """Scroll the target into view and draw the highlight ring around it."""
    page.evaluate("""([sel, pad]) => { const e = document.querySelector(sel); const r = document.getElementById('tut-ring');
        if (!e) { r.style.opacity = 0; return; }
        e.scrollIntoView({block: 'center', behavior: 'smooth'});
        setTimeout(() => { const b = e.getBoundingClientRect();
          Object.assign(r.style, {left: (b.left - pad) + 'px', top: (b.top - pad) + 'px',
            width: (b.width + 2 * pad) + 'px', height: (b.height + 2 * pad) + 'px', opacity: 1}); }, 650); }""",
                  [selector, pad])
    page.wait_for_timeout(900 + ms)


def unring(page):
    page.evaluate("() => { document.getElementById('tut-ring').style.opacity = 0; }")


def point(page, selector):
    """Glide the cursor to the middle of an element."""
    page.evaluate("""(sel) => { const e = document.querySelector(sel); if (!e) return;
        const b = e.getBoundingClientRect(); const c = document.getElementById('tut-cur');
        c.style.left = (b.left + b.width / 2) + 'px'; c.style.top = (b.top + b.height / 2) + 'px'; }""", selector)
    page.wait_for_timeout(800)


def click(page, selector):
    point(page, selector)
    page.evaluate("() => { const c = document.getElementById('tut-cur'); c.style.transform = 'scale(.7)'; "
                  "setTimeout(() => c.style.transform = 'scale(1)', 180); }")
    page.click(selector)


def nav(page, label):
    sel = f"a[href*='{label}']"
    point(page, sel)
    page.evaluate("() => { const c = document.getElementById('tut-cur'); c.style.transform = 'scale(.7)'; "
                  "setTimeout(() => c.style.transform = 'scale(1)', 180); }")
    page.click(sel)


def glide(page, to, ms=1400):
    page.evaluate(f"() => {MAIN}.scrollTo({{top: {to}, behavior: 'smooth'}})")
    page.wait_for_timeout(ms)


def warm(browser):
    """Fetch prices once (server cache) so the recording shows no loading spinners."""
    ctx = browser.new_context(viewport=SIZE)
    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_selector(".st-key-use_sample button", timeout=60000)
    page.click(".st-key-use_sample button")
    page.wait_for_selector(".st-key-loaded_summary", timeout=30000)
    for slug, wait in (("shadow", 14000), ("roth", 6000), ("proof", 14000)):
        page.click(f"a[href*='{slug}']")
        page.wait_for_timeout(wait)
    ctx.close()


def tutorial(browser, video_dir):
    ctx = browser.new_context(viewport=SIZE, record_video_dir=video_dir, record_video_size=SIZE)
    ctx.add_init_script("""document.addEventListener('DOMContentLoaded', () => {
        const d = document.createElement('div'); d.id = 'tut-card';
        d.style.cssText = 'position:fixed;inset:0;z-index:100001;display:flex;flex-direction:column;align-items:center;'
          + 'justify-content:center;gap:14px;background:#F0F6FA;color:#1A1D1B;transition:opacity .5s';
        d.innerHTML = '<h1 style="font:400 54px/1.1 Georgia,serif;margin:0">How to use Spend Shadow</h1>'
          + '<p style="font:400 22px/1.4 Arial,sans-serif;color:#4F5752;margin:0">Six steps, about a minute</p>';
        document.body.appendChild(d); });""")
    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_selector(".st-key-use_sample button", timeout=60000)
    overlay(page)
    page.wait_for_timeout(2400)
    page.evaluate("() => { const d = document.getElementById('tut-card'); d.style.opacity = 0; "
                  "setTimeout(() => d.remove(), 500); }")
    page.wait_for_timeout(600)

    # 1. upload
    caption(page, "1", "Export a CSV of your transactions from your bank or card website, then upload it here.")
    ring(page, ".st-key-upload_source", 1200)
    point(page, '[data-testid="stFileUploaderDropzone"] button')
    page.set_input_files('[data-testid="stFileUploaderDropzoneInput"]', SAMPLE)
    page.wait_for_selector(".st-key-column_mapper", timeout=30000)
    page.wait_for_timeout(800)

    # 2. columns
    caption(page, "2", "Check the columns. They're detected for you; fix any that look wrong.")
    ring(page, ".st-key-column_mapper", 2600)
    caption(page, "2", "Then click Load transactions.")
    ring(page, ".st-key-load_btn", 400)
    click(page, ".st-key-load_btn button")
    page.wait_for_selector(".st-key-loaded_summary", timeout=30000)
    page.wait_for_timeout(600)
    caption(page, "", "Loaded. Your file stays in this browser session: nothing is saved or sent anywhere.")
    ring(page, ".st-key-loaded_summary", 2800)
    caption(page, "Tip", "No file handy? Click Use sample data to try it with a made-up statement.")
    ring(page, ".st-key-use_sample", 2400)
    unring(page)

    # 3. spending
    nav(page, "spending")
    page.wait_for_timeout(1500)
    overlay(page)
    caption(page, "3", "Spending breakdown: your total, monthly average and how much went to wants.")
    ring(page, ".st-key-spend_kpis", 2600)
    caption(page, "3", "See it by category and by month.")
    ring(page, ".st-key-chart_by_category", 2400)
    unring(page)

    # 4. shadow
    nav(page, "shadow")
    page.wait_for_timeout(3000)
    caption(page, "4", "Shadow portfolio: what every purchase would be worth today if it had bought an index fund.")
    ring(page, ".st-key-shadow_kpis", 3000)
    caption(page, "4", "Compare the same purchases in four portfolios, from all stocks to all bonds.")
    ring(page, ".st-key-shadow_compare", 2800)
    unring(page)

    # 5. roth
    nav(page, "roth")
    page.wait_for_timeout(2500)
    caption(page, "5", "Roth calculator: set your age, monthly amount and expected return.")
    ring(page, ".st-key-roth_inputs", 2400)
    unring(page)
    caption(page, "5", "Or redirect your wants spending into the Roth.")
    ring(page, ".st-key-roth_source", 600)
    point(page, ".st-key-roth_source label:last-of-type")
    page.get_by_text("Redirect discretionary spending", exact=True).click()
    page.wait_for_timeout(1800)
    unring(page)
    caption(page, "5", "See what your wants spending could become by retirement.")
    ring(page, ".st-key-roth_redirect", 3600)
    unring(page)

    # 6. proof
    nav(page, "proof")
    page.wait_for_timeout(3500)
    caption(page, "6", "Proof: the key numbers are re-checked live against independent math.")
    ring(page, ".st-key-proof_checks", 3200)
    caption(page, "6", "Download the Excel workbook to check the formulas yourself.")
    ring(page, ".st-key-proof_download", 2600)
    unring(page)
    page.evaluate("() => { document.getElementById('tut-cap').style.opacity = 0; }")
    card(page, "Try it now", "Upload your CSV, or click Use sample data", 2800)

    path = page.video.path()
    ctx.close()
    return path


def to_mp4(src, dst, skip=0.3):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run([ff, "-y", "-ss", str(skip), "-i", src, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "27",
                    "-preset", "slow", "-movflags", "+faststart", "-an", dst], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    tmp = tempfile.mkdtemp(prefix="spend-shadow-tutorial-")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        warm(browser)
        webm = tutorial(browser, tmp)
        browser.close()
    to_mp4(webm, OUT)
    shutil.rmtree(tmp, ignore_errors=True)
    print("saved", os.path.abspath(OUT), f"{os.path.getsize(OUT) / 1e6:.1f} MB")
