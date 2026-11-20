"""Voice-over script for the landing-page tutorial, and a helper that turns it into audio.

Dev tool only. Uses edge-tts (Microsoft neural voices); only these lines of text are sent to the
voice service, never any transaction data. Voice picked by Ashton on 2026-11-19: Andrew.
    python tools/narration.py <out_dir>     # writes one mp3 per line and prints durations
"""
import asyncio
import os
import subprocess
import sys

VOICE = "en-US-AndrewMultilingualNeural"
RATE = "-4%"

LINES = {
    "intro": "Hi! This is Spend Shadow. Give me under two minutes, and I'll show you how it works.",
    "upload": "Start by downloading a CSV of your transactions from your bank or card website. "
              "Then drop it right here.",
    "columns": "Spend Shadow finds the date, merchant and amount columns for you. "
               "Give them a quick look, and hit Load transactions.",
    "loaded": "Your file stays in this browser tab. Nothing is saved, and nothing is sent anywhere. "
              "No file handy? The sample data works just as well.",
    "spending": "First, your spending breakdown. What you spent, your monthly average, "
                "and how much went to wants, like dining out and shopping.",
    "shadow": "Now the fun part. The shadow portfolio pretends every purchase bought an index fund "
              "that same day, and shows what it would be worth today.",
    "compare": "Tap a fund to try it, and see four mixes side by side. "
               "Every dollar you spend is a dollar you could put to work.",
    "roth": "The Roth calculator starts from your own spending. What you spent on wants becomes "
            "your starting balance, and it suggests a monthly amount that fits how you spend.",
    "redirect": "And this is where your coffee habit turns into a retirement number.",
    "proof": "Finally, Proof. The key numbers are rechecked against independent math, "
             "and you can download the Excel workbook to check them yourself.",
    "outro": "That's it. Upload your statement, or try the sample, and see what your spending could become.",
}


async def _speak(text: str, path: str) -> None:
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(path)


def duration(path: str) -> float:
    """Seconds of audio, read with the ffmpeg that ships with imageio-ffmpeg."""
    import imageio_ffmpeg
    out = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", path], capture_output=True, text=True).stderr
    hms = out.split("Duration: ")[1].split(",")[0]
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def render(out_dir: str) -> dict[str, tuple[str, float]]:
    os.makedirs(out_dir, exist_ok=True)
    clips = {}
    for key, text in LINES.items():
        path = os.path.join(out_dir, f"{key}.mp3")
        asyncio.run(_speak(text, path))
        clips[key] = (path, duration(path))
    return clips


if __name__ == "__main__":
    clips = render(sys.argv[1] if len(sys.argv) > 1 else "narration")
    for k, (_, d) in clips.items():
        print(f"{k:9} {d:5.1f}s")
    print(f"total    {sum(d for _, d in clips.values()):5.1f}s")
