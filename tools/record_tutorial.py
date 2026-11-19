"""Record the landing-page tutorial: a narrated, step-by-step walk through Spend Shadow.

Dev tool only (not part of the app). The subtitles, spotlight, step chip, camera moves and cursor
are drawn into the page by this script while recording; the app itself never shows them. Uses the
fictional sample CSV only. The voice-over comes from tools/narration.py (Andrew, edge-tts); each
step is held for exactly as long as its line, so picture and voice stay in sync.
Needs Playwright with Chrome, edge-tts and imageio-ffmpeg:
    python tools/record_tutorial.py http://localhost:8544
Writes assets/tutorial.mp4 (1920x1080 H.264 with AAC audio).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import narration  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8544"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAMPLE = os.path.join(ROOT, "sample_data", "sample_transactions.csv")
OUT = os.path.join(ROOT, "assets", "tutorial.mp4")
VIEW = dict(width=1280, height=720)   # CSS pixels
SCALE = 1.5                           # device pixels -> 1920x1080 frames, crisp text
FRAME = dict(width=1920, height=1080)
PAD = 0.55                            # breath after each line, seconds
STEPS = 6

# Overlay drawn on top of the page during recording only. Colors follow DESIGN.md.
OVERLAY_JS = r"""
() => {
  if (document.getElementById('tut-cap')) return;
  const css = document.createElement('style');
  css.textContent = `
    #tut-cap { position: fixed; left: 50%; bottom: 30px; transform: translateX(-50%) translateY(8px);
      max-width: 960px; width: max-content; padding: 13px 24px; border-radius: 16px; z-index: 99999;
      background: rgba(10,20,32,.86); color: #fff; font: 500 20px/1.45 Geist, "Segoe UI", Arial, sans-serif;
      text-align: center; box-shadow: 0 18px 50px rgba(10,20,32,.28); backdrop-filter: blur(10px);
      transition: opacity .4s, transform .4s; opacity: 0; }
    #tut-cap.on { opacity: 1; transform: translateX(-50%) translateY(0); }
    #tut-chip { position: fixed; left: 28px; top: 22px; z-index: 99999; padding: 8px 16px;
      border-radius: 999px; background: rgba(255,255,255,.82); color: #1A1D1B; backdrop-filter: blur(12px);
      border: 1px solid rgba(10,113,108,.25); box-shadow: 0 8px 24px rgba(10,20,32,.12);
      font: 600 15px/1 Geist, "Segoe UI", Arial, sans-serif; letter-spacing: .02em;
      transition: opacity .4s; opacity: 0; }
    #tut-chip b { color: #0A716C; margin-right: 6px; }
    #tut-spot { position: fixed; z-index: 99990; border-radius: 22px; pointer-events: none; opacity: 0;
      box-shadow: 0 0 0 3px #34E0D6, 0 0 0 9px rgba(52,224,214,.22), 0 0 0 200vmax rgba(10,20,32,.38);
      transition: left .7s cubic-bezier(.2,.8,.2,1), top .7s cubic-bezier(.2,.8,.2,1),
                  width .7s cubic-bezier(.2,.8,.2,1), height .7s cubic-bezier(.2,.8,.2,1), opacity .5s; }
    #tut-cur { position: fixed; z-index: 100000; width: 22px; height: 22px; margin: -11px 0 0 -11px;
      border-radius: 50%; background: rgba(10,20,32,.85); border: 3px solid #fff; pointer-events: none;
      box-shadow: 0 6px 18px rgba(10,20,32,.3); left: 640px; top: 420px;
      transition: left .9s cubic-bezier(.25,.9,.25,1), top .9s cubic-bezier(.25,.9,.25,1), transform .15s; }
    [data-testid="stAppViewContainer"] { transition: transform 1.4s cubic-bezier(.25,.9,.25,1); }
    #tut-card { position: fixed; inset: 0; z-index: 100001; display: flex; flex-direction: column;
      align-items: center; justify-content: center; gap: 16px; color: #1A1D1B; transition: opacity .7s;
      background: radial-gradient(1200px 600px at 50% 40%, #FFFFFF 0%, #EAF4F8 55%, #DCEBF2 100%); }
    #tut-card h1 { font: 400 64px/1.05 Georgia, serif; margin: 0; letter-spacing: -.01em; }
    #tut-card p { font: 400 24px/1.4 "Segoe UI", Arial, sans-serif; color: #4F5752; margin: 0; }
    #tut-card i { width: 64px; height: 3px; background: #0A716C; border-radius: 3px; }
    .st-key-landing_preview { display: none !important; }`;
  document.head.appendChild(css);
  for (const id of ['tut-cap', 'tut-chip', 'tut-spot', 'tut-cur']) {
    const d = document.createElement('div'); d.id = id; document.body.appendChild(d);
  }
}
"""

# Shown from the first painted frame, so the video never opens on a half-loaded app.
INIT_CARD = """document.addEventListener('DOMContentLoaded', () => {
  const d = document.createElement('div'); d.id = 'tut-card';
  d.style.cssText = 'position:fixed;inset:0;z-index:100001;display:flex;flex-direction:column;align-items:center;'
    + 'justify-content:center;gap:16px;color:#1A1D1B;transition:opacity .7s;'
    + 'background:radial-gradient(1200px 600px at 50% 40%,#FFFFFF 0%,#EAF4F8 55%,#DCEBF2 100%)';
  d.innerHTML = '<h1 style="font:400 64px/1.05 Georgia,serif;margin:0">Spend Shadow</h1>'
    + '<i style="width:64px;height:3px;background:#0A716C;border-radius:3px"></i>'
    + '<p style="font:400 24px/1.4 Segoe UI,Arial,sans-serif;color:#4F5752;margin:0">How to use it, in about a minute</p>';
  document.body.appendChild(d); });"""


class Director:
    """Drives the page and keeps a log of when each voice line starts."""

    def __init__(self, page, clips, t0):
        self.page, self.clips, self.t0 = page, clips, t0
        self.cues = []      # (seconds from video start, mp3 path)
        self._end = 0.0

    # timing -------------------------------------------------------------
    def line(self, key):
        """Start a voice line now: subtitle on, cue logged. Returns when the line is due to finish."""
        self.wait_out()
        path, dur = self.clips[key]
        self.cues.append((time.monotonic() - self.t0, path))
        self.page.evaluate("(t) => { const c = document.getElementById('tut-cap'); c.textContent = t; "
                           "c.classList.add('on'); }", narration.LINES[key])
        self._end = time.monotonic() + dur + PAD

    def wait_out(self):
        left = self._end - time.monotonic()
        if left > 0:
            self.page.wait_for_timeout(int(left * 1000))

    def hold(self, ms):
        self.page.wait_for_timeout(ms)

    # visuals ------------------------------------------------------------
    def chip(self, n, name):
        self.page.evaluate("([n, s, t]) => { const c = document.getElementById('tut-chip'); "
                           "c.innerHTML = '<b>Step ' + n + ' of ' + s + '</b>' + t; c.style.opacity = 1; }",
                           [n, STEPS, name])

    def chip_off(self):
        self.page.evaluate("() => { document.getElementById('tut-chip').style.opacity = 0; }")

    def caption_off(self):
        self.page.evaluate("() => document.getElementById('tut-cap').classList.remove('on')")

    def spot(self, selector, pad=10, zoom=1.0):
        """Scroll the block to the middle, push the camera in a touch, then spotlight it."""
        self.page.evaluate("""([sel, pad, zoom]) => {
            const e = document.querySelector(sel); const s = document.getElementById('tut-spot');
            const app = document.querySelector('[data-testid="stAppViewContainer"]');
            if (!e) { s.style.opacity = 0; return; }
            app.style.transform = 'none';
            e.scrollIntoView({block: 'center', behavior: 'smooth'});
            setTimeout(() => {
              const b = e.getBoundingClientRect();
              app.style.transformOrigin = (b.left + b.width / 2) + 'px ' + (b.top + b.height / 2) + 'px';
              app.style.transform = 'scale(' + zoom + ')';
              setTimeout(() => { const c = e.getBoundingClientRect();
                Object.assign(s.style, {left: (c.left - pad) + 'px', top: (c.top - pad) + 'px',
                  width: (c.width + 2 * pad) + 'px', height: (c.height + 2 * pad) + 'px', opacity: 1}); }, 1450);
            }, 700); }""", [selector, pad, zoom])
        self.page.wait_for_timeout(2300)

    def unspot(self):
        self.page.evaluate("""() => { document.getElementById('tut-spot').style.opacity = 0;
            document.querySelector('[data-testid="stAppViewContainer"]').style.transform = 'none'; }""")
        self.page.wait_for_timeout(700)

    def point(self, selector, text=None):
        """Glide the cursor to an element (optionally the first one whose text matches)."""
        self.page.evaluate("""([sel, text]) => {
            let e = [...document.querySelectorAll(sel)].find(x => !text || x.innerText.trim().startsWith(text));
            if (!e) return; const b = e.getBoundingClientRect(); const c = document.getElementById('tut-cur');
            c.style.left = (b.left + b.width / 2) + 'px'; c.style.top = (b.top + b.height / 2) + 'px'; }""",
                           [selector, text])
        self.page.wait_for_timeout(950)

    def press(self):
        self.page.evaluate("() => { const c = document.getElementById('tut-cur'); c.style.transform = 'scale(.7)'; "
                           "setTimeout(() => c.style.transform = 'scale(1)', 180); }")

    def nav(self, slug):
        self.unspot()
        sel = f"a[href*='{slug}']"
        self.point(sel)
        self.press()
        self.page.click(sel)
        self.page.wait_for_timeout(1600)
        self.page.evaluate("() => document.querySelector('[data-testid=\"stMain\"]').scrollTo({top: 0})")

    def card(self, title, sub, ms):
        self.page.evaluate("""([t, s]) => { const d = document.createElement('div'); d.id = 'tut-card';
            d.style.opacity = 0; d.innerHTML = '<h1>' + t + '</h1><i></i><p>' + s + '</p>';
            document.body.appendChild(d); requestAnimationFrame(() => d.style.opacity = 1); }""", [title, sub])
        self.page.wait_for_timeout(ms)


def warm(browser):
    """Fetch prices once (server cache) so the recording shows no loading spinners."""
    ctx = browser.new_context(viewport=VIEW)
    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_selector(".st-key-use_sample button", timeout=90000)
    page.click(".st-key-use_sample button")
    page.wait_for_selector(".st-key-loaded_summary", timeout=30000)
    for slug, wait in (("shadow", 14000), ("roth", 6000), ("proof", 14000)):
        page.click(f"a[href*='{slug}']")
        page.wait_for_timeout(wait)
    page.click("a[href*='shadow']")
    page.wait_for_timeout(3000)
    page.locator(".st-key-shadow_chip button", has_text="SCHD").first.click()
    page.wait_for_timeout(8000)
    ctx.close()


def tutorial(browser, video_dir, clips):
    ctx = browser.new_context(viewport=VIEW, device_scale_factor=SCALE, record_video_dir=video_dir,
                              record_video_size=FRAME)
    ctx.add_init_script(INIT_CARD)
    t0 = time.monotonic()
    page = ctx.new_page()
    d = Director(page, clips, t0)
    page.goto(URL)
    page.wait_for_selector(".st-key-use_sample button", timeout=90000)
    page.evaluate(OVERLAY_JS)
    page.wait_for_timeout(1200)
    skip = time.monotonic() - t0      # everything before this is loading; trimmed off later

    d.line("intro")
    d.wait_out()
    page.evaluate("() => { const c = document.getElementById('tut-card'); c.style.opacity = 0; "
                  "setTimeout(() => c.remove(), 700); }")
    d.hold(800)

    # 1. upload
    d.chip(1, "Upload")
    d.line("upload")
    d.spot(".st-key-upload_source", zoom=1.04)
    d.point('[data-testid="stFileUploaderDropzone"] button')
    d.wait_out()
    page.set_input_files('[data-testid="stFileUploaderDropzoneInput"]', SAMPLE)
    page.wait_for_selector(".st-key-column_mapper", timeout=30000)
    d.hold(500)

    # 2. columns
    d.chip(2, "Check the columns")
    d.line("columns")
    d.spot(".st-key-column_mapper", zoom=1.03)
    d.hold(1200)
    d.spot(".st-key-load_btn", zoom=1.0)
    d.point(".st-key-load_btn button")
    d.wait_out()
    d.press()
    page.click(".st-key-load_btn button")
    page.wait_for_selector(".st-key-loaded_summary", timeout=30000)
    d.hold(400)
    d.line("loaded")
    d.spot(".st-key-loaded_summary", zoom=1.03)
    d.hold(2600)
    d.spot(".st-key-use_sample", zoom=1.0)
    d.point(".st-key-use_sample button")
    d.wait_out()

    # 3. spending
    d.nav("spending")
    page.evaluate(OVERLAY_JS)
    d.chip(3, "Spending")
    d.line("spending")
    d.spot(".st-key-spend_kpis", zoom=1.05)
    d.hold(1800)
    d.spot(".st-key-chart_by_category", zoom=1.02)
    d.wait_out()

    # 4. shadow
    d.nav("shadow")
    page.wait_for_selector(".st-key-shadow_kpis", timeout=30000)
    d.chip(4, "Shadow portfolio")
    d.line("shadow")
    d.spot(".st-key-shadow_kpis", zoom=1.05)
    d.hold(1500)
    d.spot(".st-key-chart_shadow", zoom=1.02)
    d.wait_out()
    d.line("compare")
    d.spot(".st-key-shadow_chip", zoom=1.0)
    d.point(".st-key-shadow_chip button", "SCHD")
    d.press()
    page.locator(".st-key-shadow_chip button", has_text="SCHD").first.click()
    d.hold(2200)
    d.spot(".st-key-shadow_compare", zoom=1.0)
    d.wait_out()

    # 5. roth
    d.nav("roth")
    page.wait_for_selector(".st-key-roth_inputs", timeout=30000)
    d.chip(5, "Roth calculator")
    d.line("roth")
    d.spot(".st-key-roth_inputs", zoom=1.02)
    d.wait_out()
    d.line("redirect")
    d.spot(".st-key-roth_redirect", zoom=1.03)
    d.wait_out()
    d.hold(600)

    # 6. proof
    d.nav("proof")
    page.wait_for_selector(".st-key-proof_checks", timeout=60000)
    d.chip(6, "Proof")
    d.line("proof")
    d.spot(".st-key-proof_checks", zoom=1.02)
    d.hold(2400)
    d.spot(".st-key-proof_download", zoom=1.04)
    d.wait_out()

    d.unspot()
    d.chip_off()
    d.caption_off()
    d.card("Try it now", "Upload your CSV, or click Use sample data", 600)
    d.line("outro")
    d.wait_out()
    d.hold(900)

    total = time.monotonic() - t0
    path = page.video.path()
    ctx.close()
    return path, d.cues, skip, total


def to_mp4(src, dst, cues, skip, total):
    """Trim the loading, add fades, and lay each voice line at the moment it was cued."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    length = total - skip
    args = [ff, "-y", "-ss", f"{skip:.3f}", "-i", src]
    for _, path in cues:
        args += ["-i", path]
    parts = []
    for i, (at, _) in enumerate(cues, start=1):
        ms = max(int((at - skip) * 1000), 0)
        parts.append(f"[{i}:a]adelay={ms}|{ms},volume=1.0[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(1, len(cues) + 1))
    parts.append(f"{mix}amix=inputs={len(cues)}:normalize=0,afade=t=out:st={length - 1.0:.2f}:d=1.0[aout]")
    parts.append(f"[0:v]fade=t=in:st=0:d=0.8:color=black,fade=t=out:st={length - 1.0:.2f}:d=1.0,"
                 f"fps=30,format=yuv420p[vout]")
    args += ["-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]", "-t", f"{length:.3f}",
             "-c:v", "libx264", "-crf", "26", "-preset", "slow", "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart", dst]
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    tmp = tempfile.mkdtemp(prefix="spend-shadow-tutorial-")
    clips = narration.render(os.path.join(tmp, "voice"))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        warm(browser)
        webm, cues, skip, total = tutorial(browser, tmp, clips)
        browser.close()
    to_mp4(webm, OUT, cues, skip, total)
    shutil.rmtree(tmp, ignore_errors=True)
    print("saved", os.path.abspath(OUT), f"{os.path.getsize(OUT) / 1e6:.1f} MB, {total - skip:.0f} s")
