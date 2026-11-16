#!/usr/bin/env python3
"""Transcribe the Reels in an archive from instagram-audio.js, with Parakeet, on this Mac.

    transcribe.py --archive ~/Downloads/ig-research-audio-<id>.tar --out <transcripts dir>

Waits for Chrome to finish saving the archive, moves it out of Downloads into a fresh
temporary folder, and for each <code>.m4a (or .mp4) inside:
  ffmpeg -> 16 kHz mono WAV -> fluidaudiocli (Parakeet TDT 0.6B v3, word timestamps) -> JSON
then writes <out>/<code>.md, a plain transcript in timestamped paragraphs. The archive,
audio, WAV and JSON are deleted at the end, whatever happens.

Needs macOS on Apple Silicon, ffmpeg, and FluidAudio's command-line tool (setup in
references/transcripts.md). The tool is found through IG_RESEARCH_PARAKEET_CLI, else
`fluidaudiocli` on the PATH. Everything runs on this computer; nothing is uploaded.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

CLI = Path(os.environ.get("IG_RESEARCH_PARAKEET_CLI") or shutil.which("fluidaudiocli") or "fluidaudiocli")
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
NAME = re.compile(r"^[A-Za-z0-9_-]{6,40}\.(m4a|mp4)$")
MAX_BYTES = 200 * 1024 * 1024
PARA_SECONDS, PAUSE_SECONDS = 45.0, 2.5

# Names the model mishears in AI-tool Reels.
# "Cloud Code": on 2026-11-06 Parakeet wrote it 4 times out of 4 where @jens.heitmann
# says Claude Code (his caption confirms), while plain "Claude" came out right. Other
# misses seen that day are left alone, because no fixed rule is safe for them: "hormose's"
# for Hormozi's, "GitHub Studio" for Google AI Studio, "Come and watch" for "Comment WATCH".
# Also from 2026-11-06: "clot" for Claude 6 times in @abhishek.devini's Reel (accent),
# and "F ompeg" / "YTDLP" for the tools in @buildwith.conrad's. Safe in this niche
# (AI tool Reels); revisit if transcribing other topics.
CORRECTIONS = [
    (re.compile(r"\b[CK]?allaway\b", re.I), "Kallaway"),
    (re.compile(r"\bsand ?castle(s?)\b", re.I), r"Sandcastle\1"),
    (re.compile(r"\b(?:cloud|claude|clot) code\b", re.I), "Claude Code"),
    (re.compile(r"\b[Cc]lot\b"), "Claude"),
    (re.compile(r"\bF ?F? ?ompeg\b|\bffmpeg\b", re.I), "FFmpeg"),
    (re.compile(r"\bYT ?DLP\b", re.I), "yt-dlp"),
]


def correct(text):
    for pattern, repl in CORRECTIONS:
        text = pattern.sub(repl, text)
    return text


def stamp(seconds):
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def paragraphs(words):
    paras, current, start, prev_end = [], [], None, None
    for w in words:
        text = str(w.get("word", "")).strip()
        if not text:
            continue
        if current and prev_end is not None and w["startTime"] - prev_end > PAUSE_SECONDS:
            paras.append((start, current))
            current, start = [], None
        if start is None:
            start = w["startTime"]
        current.append(text)
        prev_end = w["endTime"]
        if text[-1] in ".?!" and w["endTime"] - start >= PARA_SECONDS:
            paras.append((start, current))
            current, start = [], None
    if current:
        paras.append((start, current))
    return paras


def wait_for(path, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if path.exists() and not Path(str(path) + ".crdownload").exists():
            size = path.stat().st_size
            time.sleep(1)
            if path.stat().st_size == size:
                return True
        time.sleep(1)
    return False


def unpack(archive, into):
    out = []
    with tarfile.open(archive) as tf:
        for m in tf.getmembers():
            if not (m.isfile() and NAME.match(m.name) and m.size <= MAX_BYTES):
                print(f"skipped archive entry {m.name!r}", file=sys.stderr)
                continue
            dest = into / m.name
            with tf.extractfile(m) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            out.append(dest)
    return out


def transcribe(media, work, out_dir):
    code = media.stem
    wav, js, log = work / f"{code}.wav", work / f"{code}.json", work / f"{code}.log"
    subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-y", "-i", str(media),
                    "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)], check=True)
    t0 = time.time()
    with open(log, "w") as lf:
        r = subprocess.run([str(CLI), "transcribe", str(wav), "--model-version", "v3",
                            "--word-timestamps", "--output-json", str(js)], stdout=lf, stderr=subprocess.STDOUT)
    if r.returncode != 0 or not js.exists():
        raise RuntimeError("fluidaudiocli failed: " + log.read_text()[-300:])
    took = time.time() - t0
    data = json.loads(js.read_text())
    words = data.get("wordTimings") or []
    dur = float(data.get("duration") or (words[-1]["endTime"] if words else 0))
    lines = [
        f"# {code} (transcript)",
        "",
        f"Reel: https://www.instagram.com/reel/{code}/ ({stamp(dur)})  ",
        f"Transcribed: {datetime.date.today().isoformat()}, on this Mac with Parakeet TDT 0.6B v3. "
        "Machine transcript: names and terms may be misheard, and anything shown only on screen is missing.",
        "",
    ]
    paras = paragraphs(words)
    if paras:
        for start, ws in paras:
            lines += [f"**[{stamp(start)}]** " + correct(" ".join(ws)), ""]
    else:
        lines += [correct(str(data.get("text", "")).strip()) or "(no speech found)", ""]
    (out_dir / f"{code}.md").write_text("\n".join(lines), encoding="utf-8")
    return code, dur, len(words), took


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True, help="folder for the <code>.md transcripts")
    ap.add_argument("--wait", type=int, default=60, help="seconds to wait for Chrome to finish saving")
    a = ap.parse_args()
    if not CLI.exists():
        sys.exit(f"error: Parakeet CLI not found at {CLI}; set IG_RESEARCH_PARAKEET_CLI "
                 "(see references/transcripts.md)")
    if not wait_for(a.archive, a.wait):
        sys.exit(f"error: {a.archive} did not appear within {a.wait}s")
    a.out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="ig-research-audio-"))
    try:
        moved = work / a.archive.name
        shutil.move(str(a.archive), moved)  # out of Downloads at once
        media = unpack(moved, work)
        if not media:
            sys.exit("error: no audio in the archive")
        for m in media:
            try:
                code, dur, n, took = transcribe(m, work, a.out)
                print(f"{code}: {dur:.0f}s of audio, {n} words, transcribed in {took:.1f}s -> {a.out / (code + '.md')}")
            except (subprocess.CalledProcessError, RuntimeError, ValueError, KeyError) as e:
                print(f"{m.stem}: failed: {e}", file=sys.stderr)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    left = [p for p in (a.archive, work) if p.exists()]
    print("audio deleted" if not left else f"warning: still present: {left}")


if __name__ == "__main__":
    main()
