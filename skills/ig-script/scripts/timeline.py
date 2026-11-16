#!/usr/bin/env python3
"""
timeline.py - time a Reel script line by line, the way a cold viewer hears it.

Input: the spoken lines, one per line, exactly as they go to the cold listener
(numbers like "L3." or "3." at the start are ignored). Output: when each line
starts, how long it takes to say, and four pointers for the coherence check:

  - what the viewer has heard by 0:03 (the hook window) and by 0:07 (by then
    they should know who the video is for and why it matters);
  - the midpoint, so a hook's promise answered after it can be named in
    seconds rather than in line numbers;
  - lines too long to take in on one hearing;
  - runs of three or more lines with no number, name or other checkable marker.

These are pointers, not verdicts. Times come from word count at a fixed rate,
so they are estimates; set --wps from a recorded take when one exists. The
concreteness test sees digits, spoken numbers and capitalised names, and is
blind to concrete everyday nouns ("gym", "phone"), so a flagged run still needs
a person's judgement: can the viewer picture or check anything in it? There is
deliberately no hook score: this tool checks whether a script can be followed,
and writing or scoring hooks is a writer's job (see references/what-it-checks.md).

Words are counted by the same rule as ig-reel's reel.py (see spoken_words
below), so both timers give the same length and the same words heard by 0:03
for the same lines.

Usage
  python3 timeline.py lines.txt
  python3 timeline.py lines.txt --target 60
  python3 timeline.py lines.txt --wps 2.7 --json
  pbpaste | python3 timeline.py -
"""

import argparse
import json
import re
import sys

PUNCT = ".,;:!?\"“”()[]…"
# A capitalised word that does not start the line and does not follow a
# sentence end: a name, a product, a place.
PROPER_RE = re.compile(r"(?<![.!?:]\s)(?<!^)\b[A-Z][A-Za-z]+\b")
SPOKEN_NUMBERS = {
    "zero", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "fifteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "hundred", "thousand", "million", "billion", "dozen", "half",
    "twice", "dollars", "dollar", "bucks", "grand", "percent", "minutes",
    "hours", "days", "weeks", "months", "years",
}
NOT_NAMES = {"I", "I'm", "I’m", "I've", "I’ve", "I'll", "I’ll", "I'd", "I’d", "AI", "OK"}
LEAD_NUMBER = re.compile(r"^\s*(?:L?\d+[.):]\s+)")

HOOK_WINDOW = 3.0    # seconds: skip rate is measured on the first three
STAKE_WINDOW = 7.0   # seconds: who it is for and why it matters, by here
LONG_LINE = 8.0      # seconds: 20 words at 2.5 a second
ABSTRACT_RUN = 3     # lines in a row with nothing checkable


# ---- Spoken word count. The same rule, in the same words, is in ig-reel's
# scripts/reel.py, so the two timers agree on the same lines; a test runs both.
#   - Tokens are split on whitespace; punctuation at either end is dropped; a token with
#     no letter or digit is not said.
#   - A {{placeholder}} is one token and counts as one word, however many words it holds:
#     what goes there is usually one figure or one name.
#   - A figure counts as it is said: 1, plus 1 for a currency sign ($ EUR GBP), plus 1 for
#     %, plus 1 per thousands separator, plus 1 for a k/m/bn suffix. "$18,000" is
#     "eighteen thousand dollars": 3. "30%" is 2. "60" is 1.
#   - A word is heard by a time t once it has been said in full: the words whose running
#     count is at most t x words-per-second.
SPOKEN_TOKEN = re.compile(r"\{\{[^{}]*\}\}|\S+")
EDGE_PUNCT = "\"'“”‘’()[]<>.,;:!?…*_"


def spoken_words(text):
    """[(token, words it counts as)] for one line, by the rule above."""
    out = []
    for tok in SPOKEN_TOKEN.findall(text or ""):
        if tok.startswith("{{") and tok.endswith("}}"):
            out.append((tok, 1))
            continue
        tok = tok.strip(EDGE_PUNCT)
        if not any(ch.isalnum() for ch in tok):
            continue
        n = 1
        if any(ch.isdigit() for ch in tok):
            n += bool(re.search("[$€£]", tok)) + ("%" in tok)
            n += len(re.findall(r"\d,\d{3}", tok))
            n += bool(re.search(r"\d(?:k|m|bn|b)$", tok, re.I))
        out.append((tok, n))
    return out


def spoken_count(text):
    return sum(n for _, n in spoken_words(text))


def words_heard_by(lines, t, wps):
    """The words said in full by t seconds, across the lines in order."""
    heard, acc, limit = [], 0, t * wps + 1e-9
    for line in lines:
        for tok, n in spoken_words(line):
            if acc + n > limit:
                return " ".join(heard)
            acc += n
            heard.append(tok)
    return " ".join(heard)


def words(text):
    """The spoken tokens of a line, one per token (see spoken_words for how they count)."""
    return [tok for tok, _ in spoken_words(text)]


def concrete(text):
    found = [w for w in words(text) if any(ch.isdigit() for ch in w)]
    found += [w for w in PROPER_RE.findall(text) if w not in NOT_NAMES]
    found += [w for w in words(text) if w.lower() in SPOKEN_NUMBERS]
    seen, out = set(), []
    for f in found:
        if f.lower() not in seen:
            seen.add(f.lower())
            out.append(f)
    return out


def tc(seconds):
    whole = int(seconds // 60)
    return f"{whole}:{seconds - whole * 60:04.1f}"


def analyse(raw, wps=2.5, target=None):
    lines = [LEAD_NUMBER.sub("", l).strip() for l in raw.splitlines()]
    lines = [l for l in lines if l]
    if not lines:
        return None

    rows, clock = [], 0.0
    for i, text in enumerate(lines, 1):
        n = spoken_count(text)
        dur = n / wps
        rows.append({"n": i, "start": round(clock, 2), "end": round(clock + dur, 2),
                     "dur": round(dur, 2), "words": n, "text": text,
                     "concrete": concrete(text), "flags": []})
        clock += dur
    total = clock
    mid = total / 2

    def heard_by(t):
        # Lines finished by t, plus the line still being said at t.
        return [r["n"] for r in rows if r["start"] < t]

    def words_by(t):
        return words_heard_by(lines, t, wps)

    notes = []
    by3, by7 = heard_by(HOOK_WINDOW), heard_by(STAKE_WINDOW)
    first = rows[0]
    if first["dur"] > HOOK_WINDOW:
        first["flags"].append(f"still going at 0:03 ({first['dur']:.1f}s)")
        notes.append(f"L1 takes {first['dur']:.1f}s. At 0:03 the viewer has heard about: "
                     f"\"{words_by(HOOK_WINDOW)}\". "
                     "Ask whether that much says what the video is about.")
    else:
        notes.append(f"By 0:03 the viewer has heard L{by3[0]}"
                     + (f"-L{by3[-1]}" if len(by3) > 1 else "") + ".")
    notes.append(f"By 0:07 the viewer has heard L{by7[0]}"
                 + (f"-L{by7[-1]}" if len(by7) > 1 else "")
                 + ". Do they know who this is for and why it matters to them?")

    mid_row = next(r for r in rows if r["start"] <= mid < r["end"] or r is rows[-1])
    mid_row["flags"].append(f"midpoint {tc(mid)}")
    notes.append(f"Midpoint {tc(mid)}, inside L{mid_row['n']}. A promise from the opening "
                 "that is answered after this line is answered late.")

    long_lines = [r for r in rows if r["dur"] > LONG_LINE]
    for r in long_lines:
        r["flags"].append(f"{r['dur']:.1f}s, long for one hearing")
    if long_lines:
        notes.append("Long for one hearing: " + ", ".join(
            f"L{r['n']} ({r['words']} words, {r['dur']:.1f}s)" for r in long_lines)
            + ". Check each holds one idea; if it holds two, split it.")

    run = []
    for r in rows + [None]:
        if r is not None and not r["concrete"]:
            run.append(r["n"])
            continue
        if len(run) >= ABSTRACT_RUN:
            notes.append(f"L{run[0]}-L{run[-1]}: no number or name in {len(run)} lines in a "
                         "row. Can the viewer picture or check anything in them?")
        run = []

    if target:
        delta = total - target
        if abs(delta) <= target * 0.1:
            notes.append(f"On target: {total:.0f}s against {target:.0f}s.")
        elif delta > 0:
            notes.append(f"{delta:.0f}s over the {target:.0f}s target, about "
                         f"{int(delta * wps)} words.")
        else:
            notes.append(f"{-delta:.0f}s under the {target:.0f}s target.")

    return {"wps": wps, "target": target, "total_seconds": round(total, 1),
            "heard_by_3s": words_by(HOOK_WINDOW), "heard_by_7s": words_by(STAKE_WINDOW),
            "total_words": sum(r["words"] for r in rows), "midpoint": round(mid, 1),
            "lines": rows, "notes": notes}


def render(a, out=sys.stdout):
    head = (f"TIMELINE · {a['total_words']} words · about {a['total_seconds']:.0f}s "
            f"at {a['wps']:g} words a second"
            + (f" · target {a['target']:g}s" if a["target"] else ""))
    print(head, file=out)
    print("=" * min(max(len(head), 60), 100), file=out)
    for r in a["lines"]:
        text = r["text"] if len(r["text"]) <= 70 else r["text"][:67] + "..."
        mark = " " if r["concrete"] else "·"
        print(f"L{r['n']:<3} {tc(r['start'])} {r['dur']:4.1f}s {mark} {text}", file=out)
        for f in r["flags"]:
            print(f"{'':>22}^ {f}", file=out)
    print("-" * 60, file=out)
    print("· = no number or name in the line", file=out)
    print(f"Heard by 0:03: \"{a['heard_by_3s']}\"", file=out)
    print(f"Heard by 0:07: \"{a['heard_by_7s']}\"", file=out)
    for n in a["notes"]:
        print(f"- {n}", file=out)


def main():
    ap = argparse.ArgumentParser(description="Time a script line by line for a cold listener.")
    ap.add_argument("input", nargs="?", default="-", help="file with one spoken line per line, or -")
    ap.add_argument("--wps", type=float, default=2.5, help="spoken words per second (default 2.5)")
    ap.add_argument("--target", type=float, help="target length in seconds")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    a = analyse(raw, wps=args.wps, target=args.target)
    if not a:
        print("no lines", file=sys.stderr)
        sys.exit(2)
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)


if __name__ == "__main__":
    main()
