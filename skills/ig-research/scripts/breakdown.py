#!/usr/bin/env python3
"""Write the "why they worked" breakdown of the top Reels into the hooks file.

    breakdown.py --csv research-<idea>-<date>.csv --notes notes.json \
                 [--hooks research-<idea>-<date>-hooks.md]

notes.json is what the model read in step 4, one entry per Reel, in the order to show:

    {"reels": [
      {"code": "DaN0yYtPzjY",
       "hook": {"text": "Claude Code skills has over [number] of uses", "basis": "heard", "at": 0},
       "hook_type": {"text": "a big number", "basis": "inferred", "from": "heard"},
       "first_frames": {"text": "Title card 'Claude Code Skills' over the creator talking to camera", "basis": "seen", "at": 0.5},
       "structure": {"kind": "list", "text": "five skills, one per beat", "basis": "inferred", "from": "heard"},
       "payoff": {"text": "the fifth skill, saved for last", "basis": "heard", "at": 35},
       "ask": {"text": "Comment SKILLS and I'll send the list", "basis": "heard", "at": 41},
       "send_to": {"text": "a teammate setting up Claude Code: 'install these'", "basis": "inferred"}}
    ]}

(the same example as references/breakdown.md)

Every part says how it is known, and the block prints it:
  seen      on screen in a frame that was paused and screenshotted ("at" = that second)
  heard     in Instagram's own caption track of the audio ("at" = the cue's second)
  caption   in the post's written caption
  inferred  a judgement from the above ("from" = what it rests on: seen, heard or caption)
  unread    not read: no caption track, the frame wasn't checked, and so on. Say so
            rather than guess.
The hook type, the structure and "would send to" are always judgements, so they must be
"inferred". The length comes from the CSV (Instagram's own duration), never from notes.

The breakdown goes into the hooks file under "## Why they worked", after the hooks table,
replacing an earlier breakdown there; the table is left as it is. Without --hooks it
goes to <csv stem>-hooks.md. The blocks are also printed. Standard library only.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

BASES = ("seen", "heard", "caption", "inferred", "unread")
JUDGEMENTS = ("hook_type", "structure", "send_to")
KINDS = ("list", "story", "demo", "before/after", "tutorial", "reaction", "talking head", "other")
FIELDS = ("hook", "hook_type", "first_frames", "structure", "payoff", "ask", "send_to")
MAX_TEXT = 220
START = "## Why they worked"
END = "<!-- end of breakdown -->"
LABELS = {"hook": "Hook", "first_frames": "First frames", "structure": "Structure",
          "payoff": "Payoff", "ask": "Ask at the end", "send_to": "Would send to"}


def clock(t):
    t = float(t)
    s = f"{int(t // 60)}:{int(t % 60):02d}"
    frac = round(t % 1, 1)
    return s + (f".{int(frac * 10)}" if frac else "")


def short(n):
    if n is None:
        return "–"
    for div, suffix in ((1_000_000, "M"), (1_000, "K")):
        if n >= div:
            return f"{n / div:.1f}".rstrip("0").rstrip(".") + suffix
    return str(int(n))


def code_of(url):
    m = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]+)", url or "")
    return m.group(1) if m else None


def num(x, kind=float):
    try:
        return kind(x) if x not in ("", None) else None
    except ValueError:
        return None


def load_csv(path):
    rows = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            c = code_of(r.get("url"))
            if c and r.get("platform") == "Instagram":
                rows[c] = r
    return rows


def check(entry, rows):
    """Problems with one Reel's notes, as sentences. Empty when it can be written."""
    code = entry.get("code")
    if not code:
        return ["an entry has no code"]
    probs = []
    if code not in rows:
        probs.append(f"{code}: not an Instagram row of the CSV")
    for f in FIELDS:
        part = entry.get(f)
        if not isinstance(part, dict):
            probs.append(f"{code}: {f} is missing (use basis \"unread\" when it wasn't read)")
            continue
        b = part.get("basis")
        if b not in BASES:
            probs.append(f"{code}: {f} basis must be one of {', '.join(BASES)}, not {b!r}")
            continue
        text = (part.get("text") or "").strip()
        if b != "unread" and not text:
            probs.append(f"{code}: {f} has no text")
        if len(text) > MAX_TEXT:
            probs.append(f"{code}: {f} is {len(text)} characters; keep it under {MAX_TEXT}")
        if f in JUDGEMENTS and b not in ("inferred", "unread"):
            probs.append(f"{code}: {f} is a judgement, so its basis is \"inferred\", not {b!r}")
        if b == "seen" and part.get("at") is None:
            probs.append(f"{code}: {f} is seen, so give \"at\": the second of the frame it was seen in")
        if part.get("at") is not None and num(part.get("at")) is None:
            probs.append(f"{code}: {f} \"at\" must be a number of seconds")
        if b == "inferred" and part.get("from") not in (None, "seen", "heard", "caption"):
            probs.append(f"{code}: {f} \"from\" must be seen, heard or caption")
        if f == "structure" and b != "unread" and part.get("kind") not in KINDS:
            probs.append(f"{code}: structure kind must be one of {', '.join(KINDS)}")
    return probs


def how(part):
    """'(seen at 0:00.5)', '(heard at 0:31)', '(from the post caption)', '(inferred from what was heard)'."""
    b = part["basis"]
    at = f" at {clock(part['at'])}" if part.get("at") is not None else ""
    if b == "seen":
        return f"(seen{at})"
    if b == "heard":
        return f"(heard{at}, Instagram's captions)"
    if b == "caption":
        return "(from the post caption)"
    if b == "unread":
        return "(not read)"
    src = {"seen": "what was seen", "heard": "what was heard", "caption": "the post caption"}.get(part.get("from"))
    return f"(inferred from {src})" if src else "(inferred)"


def block(i, entry, row):
    code = entry["code"]
    views = num(row.get("views"), int)
    spk = num(row.get("shares_per_1k_views"))
    dur = num(row.get("duration_s"))
    head = f"### {i}. @{row.get('account', '')}: {short(views)} views"
    if spk is not None:
        head += f", {spk:g} shares per 1K"
    if row.get("low_reactions") == "yes":
        head += " ⚠ low reactions"
    out = [head, "", f"https://www.instagram.com/reel/{code}/", ""]

    def line(f, extra=""):
        p = entry[f]
        text = (p.get("text") or "").strip() if p["basis"] != "unread" else "not read"
        out.append(f"- **{LABELS[f]}** {how(p)}: {text}{extra}")

    hook, ht = entry["hook"], entry["hook_type"]
    kind = f" Type: {ht['text'].strip()} {how(ht)}." if ht["basis"] != "unread" else ""
    if hook["basis"] == "unread":
        out.append(f"- **Hook** (not read).{kind}")
    else:
        said = hook["text"].strip()
        # A hook that already ends a sentence gets no second full stop after the quote.
        stop = "" if re.search(r"[.!?…]$", said) else "."
        out.append(f"- **Hook** {how(hook)}: \"{said}\"{stop}{kind}")
    line("first_frames")
    out.append(f"- **Length** (Instagram's data): {int(round(dur))} s" if dur else "- **Length**: unknown")
    st = entry["structure"]
    if st["basis"] == "unread":
        out.append("- **Structure** (not read)")
    else:
        out.append(f"- **Structure** {how(st)}: {st['kind']}, {st['text'].strip()}")
    line("payoff")
    line("ask")
    line("send_to")
    return out


def section(entries, rows):
    lines = [START, "",
             "Each part says how it is known. Seen: on screen in a frame paused at that second. "
             "Heard: Instagram's own captions of the audio, which mishear names. Caption: the "
             "post's written caption. Inferred: a judgement from those, not a fact about the "
             "Reel. Nobody watched these Reels end to end; a few frames and the captions were read.", ""]
    for i, e in enumerate(entries, 1):
        lines += block(i, e, rows[e["code"]]) + [""]
    return lines + [END]


def write_into(hooks, text):
    """Put the section after the hooks table, replacing an earlier one; keep everything else."""
    old = hooks.read_text(encoding="utf-8") if hooks.exists() else ""
    if START in old:
        before, rest = old.split(START, 1)
        after = rest.split(END, 1)[1] if END in rest else ""
        new = before.rstrip() + "\n\n" + text + after
    else:
        new = (old.rstrip() + "\n\n" if old.strip() else "") + text + "\n"
    hooks.write_text(new, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--notes", type=Path, required=True)
    ap.add_argument("--hooks", type=Path)
    a = ap.parse_args()
    rows = load_csv(a.csv)
    try:
        entries = json.loads(a.notes.read_text(encoding="utf-8"))["reels"]
    except (ValueError, KeyError, TypeError) as e:
        sys.exit(f"error: {a.notes} must be JSON with a \"reels\" list ({e})")
    probs = [p for e in entries for p in check(e, rows)]
    if probs:
        print("Not written. Fix the notes:", *("- " + p for p in probs), sep="\n", file=sys.stderr)
        sys.exit(2)
    hooks = a.hooks or a.csv.with_name(a.csv.stem + "-hooks.md")
    text = "\n".join(section(entries, rows))
    write_into(hooks, text)
    print(text)
    print(f"\nWritten into {hooks}")


if __name__ == "__main__":
    main()
