"""Record the landing-page tutorial: a narrated, step-by-step walk through Spend Shadow.

Dev tool only (not part of the app). The subtitles, spotlight, step chip, camera moves and cursor
are drawn into the page by this script while recording; the app itself never shows them. Uses the
fictional sample CSV only. The voice-over comes from tools/narration.py (Andrew, edge-tts); each
step is held for exactly as long as its line, so picture and voice stay in sync.
Needs Playwright with Chrome, edge-tts and imageio-ffmpeg:
    python tools/record_tutorial.py http://localhost:8544
Writes assets/tutorial.mp4 (1920x1080 H.264 with AAC audio; the app fills the whole frame).
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
# Playwright captures frames in CSS pixels, so record at the viewport size (a bigger record size only
# pads the frame with grey) and scale up to 1080p in ffmpeg.
OUT_W, OUT_H = 1920, 1080
PAD = 0.35                            # breath after each line, seconds
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
    #tut-chip { position: fixed; left: 28px; top: 88px; z-index: 100000; padding: 8px 16px;
      border-radius: 999px; background: rgba(255,255,255,.82); color: #1A1D1B; backdrop-filter: blur(12px);
      border: 1px solid rgba(10,113,108,.25); box-shadow: 0 8px 24px rgba(10,20,32,.12);
      font: 600 15px/1 Geist, "Segoe UI", Arial, sans-serif; letter-spacing: .02em;
      transition: opacity .4s; opacity: 0; }
    #tut-chip b { color: #0A716C; margin-right: 6px; }
    #tut-spot { position: fixed; z-index: 99990; border-radius: 22px; pointer-events: none; opacity: 0;
      box-shadow: 0 0 0 3px #34E0D6, 0 0 0 9px rgba(52,224,214,.22), 0 0 0 200vmax rgba(10,20,32,.22);
      transition: left .7s cubic-bezier(.2,.8,.2,1), top .7s cubic-bezier(.2,.8,.2,1),
                  width .7s cubic-bezier(.2,.8,.2,1), height .7s cubic-bezier(.2,.8,.2,1), opacity .5s; }
    #tut-cur { position: fixed; z-index: 100000; width: 22px; height: 22px; margin: -11px 0 0 -11px;
      border-radius: 50%; background: rgba(10,20,32,.85); border: 3px solid #fff; pointer-events: none;
      box-shadow: 0 6px 18px rgba(10,20,32,.3); left: 640px; top: 420px;
      transition: left .9s cubic-bezier(.25,.9,.25,1), top .9s cubic-bezier(.25,.9,.25,1), transform .15s; }
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
    + '<p style="font:400 24px/1.4 Segoe UI,Arial,sans-serif;color:#4F5752;margin:0">How to use it, in under two minutes</p>';
  document.body.appendChild(d); });"""


class Director:
    """Drives the page and keeps a log of when each voice line starts."""

    def __init__(self, page, clips, t0):
        self.page, self.clips, self.t0 = page, clips, t0
        self.cues = []      # (seconds from video start, mp3 path)
        self.cuts = []      # (start, end) stretches of page loading, removed in the edit
        self.clicked = None
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

    def load(self, selector=None, until=None, top=True, timeout=60000):
        """Wait out a page load or re-render with no voice playing; that stretch is cut from the video."""
        self.wait_out()
        start = time.monotonic() - self.t0
        if self.clicked is not None:      # cut from the click itself, so no half-drawn frame shows
            start, self.clicked = min(start, self.clicked), None
        self.page.wait_for_timeout(250)
        if until:
            self.page.wait_for_function(until, timeout=timeout)
        if selector:
            self.page.wait_for_selector(selector, timeout=timeout)
        # Streamlit greys out the previous run's elements until the rerun finishes; wait for none
        self.page.wait_for_function("() => !document.querySelector('[data-stale=\"true\"]') && "
                                    "!document.querySelector('[data-testid=\"stSpinner\"]')", timeout=timeout)
        if top:
            self.page.evaluate("""() => { for (const el of [document.scrollingElement,
                document.querySelector('[data-testid="stMain"]'),
                document.querySelector('[data-testid="stAppViewContainer"]')]) if (el) el.scrollTop = 0; }""")
        self.page.evaluate(OVERLAY_JS)
        self.page.wait_for_timeout(900)   # charts finish drawing and fonts settle
        self.cuts.append((start + 0.05, time.monotonic() - self.t0 - 0.1))

    # visuals ------------------------------------------------------------
    def chip(self, n, name):
        self.page.evaluate("([n, s, t]) => { const c = document.getElementById('tut-chip'); "
                           "c.innerHTML = '<b>Step ' + n + ' of ' + s + '</b>' + t; c.style.opacity = 1; }",
                           [n, STEPS, name])

    def chip_off(self):
        self.page.evaluate("() => { document.getElementById('tut-chip').style.opacity = 0; }")

    def caption_off(self):
        self.page.evaluate("() => document.getElementById('tut-cap').classList.remove('on')")

    def spot(self, selector, pad=10, settle=0):
        """Ease the page so the block sits in the middle, then glide the spotlight onto it."""
        self.page.evaluate("""([sel, pad]) => new Promise(done => {
            const e = document.querySelector(sel); const s = document.getElementById('tut-spot');
            if (!e) { s.style.opacity = 0; return done(); }
            let box = e.parentElement;
            while (box && box !== document.body && !(box.scrollHeight > box.clientHeight + 2 &&
                   /(auto|scroll)/.test(getComputedStyle(box).overflowY))) box = box.parentElement;
            const scroller = (box && box !== document.body) ? box : document.scrollingElement;
            const view = scroller === document.scrollingElement ? window.innerHeight : scroller.clientHeight;
            const r = e.getBoundingClientRect();
            const from = scroller.scrollTop;
            const max = scroller.scrollHeight - view;
            const to = Math.max(0, Math.min(max, from + r.top + r.height / 2 - view / 2 - 20));
            const dur = Math.abs(to - from) < 4 ? 0 : 900;
            const t0 = performance.now();
            const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
            const place = () => { const c = e.getBoundingClientRect();
                Object.assign(s.style, {left: (c.left - pad) + 'px', top: (c.top - pad) + 'px',
                  width: (c.width + 2 * pad) + 'px', height: (c.height + 2 * pad) + 'px', opacity: 1}); };
            const step = now => {
                const k = dur ? Math.min(1, (now - t0) / dur) : 1;
                scroller.scrollTop = from + (to - from) * ease(k);
                if (k < 1) requestAnimationFrame(step); else { place(); setTimeout(done, 750); }
            };
            requestAnimationFrame(step);
        })""", [selector, pad])
        if settle:
            self.page.wait_for_timeout(settle)

    def unspot(self):
        self.page.evaluate("() => { document.getElementById('tut-spot').style.opacity = 0; }")
        self.page.wait_for_timeout(450)

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
        self.caption_off()
        self.chip_off()
        sel = f"a[href*='{slug}']"
        self.point(sel)
        self.press()
        self.page.wait_for_timeout(200)   # let the press read on screen
        self.clicked = time.monotonic() - self.t0
        self.page.click(sel)

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
    ctx = browser.new_context(viewport=VIEW, record_video_dir=video_dir, record_video_size=VIEW)
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
    d.spot(".st-key-upload_source", settle=400)
    d.point('[data-testid="stFileUploaderDropzone"] button')
    d.wait_out()
    d.press()
    page.set_input_files('[data-testid="stFileUploaderDropzoneInput"]', SAMPLE)
    d.unspot()
    d.load(".st-key-column_mapper", top=False)

    # 2. columns
    d.chip(2, "Check the columns")
    d.line("columns")
    d.spot(".st-key-column_mapper", settle=1400)
    d.spot(".st-key-load_btn")
    d.point(".st-key-load_btn button")
    d.wait_out()
    d.press()
    d.hold(200)
    d.clicked = time.monotonic() - t0
    page.click(".st-key-load_btn button")
    d.unspot()
    d.load(".st-key-loaded_summary", top=False)
    d.line("loaded")
    d.spot(".st-key-loaded_summary", settle=2600)
    d.spot(".st-key-use_sample")
    d.point(".st-key-use_sample button")
    d.wait_out()

    # 3. spending
    d.nav("spending")
    d.load(".st-key-spend_kpis")
    d.chip(3, "Spending")
    d.line("spending")
    d.spot(".st-key-spend_kpis", settle=2200)
    d.spot(".st-key-chart_by_category")
    d.wait_out()

    # 4. shadow
    d.nav("shadow")
    d.load(".st-key-shadow_compare [data-testid='stDataFrame']")
    d.chip(4, "Shadow portfolio")
    d.line("shadow")
    d.spot(".st-key-shadow_kpis", settle=2200)
    d.spot(".st-key-chart_shadow")
    d.wait_out()
    d.spot(".st-key-shadow_chip")
    d.point(".st-key-shadow_chip button", "SCHD")
    d.press()
    d.hold(200)
    d.clicked = time.monotonic() - t0
    page.locator(".st-key-shadow_chip button", has_text="SCHD").first.click()
    d.unspot()
    d.load(until="() => [...document.querySelectorAll('.st-key-shadow_kpis [data-testid=\"stMetricLabel\"]')]"
                 ".some(e => e.innerText.includes('SCHD'))", top=False)
    d.line("compare")
    d.spot(".st-key-shadow_kpis", settle=1800)
    d.spot(".st-key-shadow_compare")
    d.wait_out()

    # 5. roth
    d.nav("roth")
    d.load(".st-key-roth_mc_kpis")
    d.chip(5, "Roth calculator")
    d.line("roth")
    d.spot(".st-key-roth_inputs")
    d.wait_out()
    d.line("redirect")
    d.spot(".st-key-roth_redirect")
    d.wait_out()

    # 6. proof
    d.nav("proof")
    d.load(".st-key-proof_download")
    d.chip(6, "Proof")
    d.line("proof")
    d.spot(".st-key-proof_checks", settle=2600)
    d.spot(".st-key-proof_download")
    d.wait_out()

    d.unspot()
    d.chip_off()
    d.caption_off()
    d.card("Try it now", "Upload your CSV, or click Use sample data", 600)
    d.line("outro")
    d.wait_out()
    d.hold(500)

    total = time.monotonic() - t0
    path = page.video.path()
    ctx.close()
    return path, d.cues, d.cuts, skip, total


def to_mp4(src, dst, cues, cuts, skip, total):
    """Trim the loading, jump-cut the page loads, add fades, and lay each voice line at its cue."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    keep, pos = [], skip
    for a, b in sorted(cuts):
        if b - a > 0.3:
            keep.append((pos, a))
            pos = b
    keep.append((pos, total))

    def remap(t):  # original time -> edited time
        return sum(max(0.0, min(b, t) - a) for a, b in keep)

    length = remap(total)
    args = [ff, "-y", "-i", src]
    for _, path in cues:
        args += ["-i", path]
    parts = [f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{k}]" for k, (a, b) in enumerate(keep)]
    parts.append("".join(f"[v{k}]" for k in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=0[vc]")
    parts.append(f"[vc]scale={OUT_W}:{OUT_H}:flags=lanczos,fade=t=in:st=0:d=0.8:color=black,fade=t=out:st={length - 1.0:.2f}:d=1.0,"
                 f"fps=30,format=yuv420p[vout]")
    for i, (at, _) in enumerate(cues, start=1):
        ms = int(remap(at) * 1000)
        parts.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(1, len(cues) + 1))
    parts.append(f"{mix}amix=inputs={len(cues)}:normalize=0,afade=t=out:st={length - 1.0:.2f}:d=1.0[aout]")
    args += ["-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]", "-t", f"{length:.3f}",
             "-c:v", "libx264", "-crf", "30", "-preset", "slow", "-c:a", "aac", "-b:a", "64k",
             "-movflags", "+faststart", dst]
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return length


if __name__ == "__main__":
    tmp = tempfile.mkdtemp(prefix="spend-shadow-tutorial-")
    clips = narration.render(os.path.join(tmp, "voice"))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        warm(browser)
        webm, cues, cuts, skip, total = tutorial(browser, tmp, clips)
        browser.close()
    length = to_mp4(webm, OUT, cues, cuts, skip, total)
    shutil.rmtree(tmp, ignore_errors=True)
    print("saved", os.path.abspath(OUT), f"{os.path.getsize(OUT) / 1e6:.1f} MB, {length:.0f} s, {len(cuts)} cuts")
