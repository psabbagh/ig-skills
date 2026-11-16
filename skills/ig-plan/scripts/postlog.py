#!/usr/bin/env python3
"""The creator's posting log: what they posted, when, in which format, on which topic,
and its numbers once they paste them from Instagram's insights.

    postlog.py add --at "2026-11-10 18:30" --format reel --topic "TOPIC" \
                   [--hook "OPENING LINE"] [--idea SLUG] [--url URL] [--views N] [--reach N] [--likes N] \
                   [--comments N] [--shares N] [--saves N] [--watch SECONDS]
    postlog.py insights [--id N | --url URL | --topic TEXT] [--file FILE]   (text on stdin)
    postlog.py list [--json]
    postlog.py path

The log is one CSV, ~/.config/ig-plan/posted.csv by default ($XDG_CONFIG_HOME/ig-plan/ when
that is set); IG_PLAN_LOG or --log picks another. Columns are LOG_COLS below. Unknown columns in an existing file are kept, so a
newer version can add columns without breaking an older file.

`insights` reads the text of a post's insights screen, pasted as is ("Views 12,345",
"Accounts reached" with its number on the next line, "Average watch time 7 sec",
"1.2K"), finds the numbers it recognises, and writes them onto one post: the one named by
--id, --url or --topic, or else the most recent post that has no views yet. It prints
what it read, so a misread label shows before anything is planned on it. Numbers a paste
does not mention are left as they were.

Standard library only. Never posts or schedules anything.
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys
import tempfile
from pathlib import Path

LOG_COLS = ["id", "posted_at", "format", "topic", "idea", "url", "views", "reach", "likes",
            "comments", "shares", "saves", "avg_watch_s", "logged", "hook"]
NUM_COLS = ["views", "reach", "likes", "comments", "shares", "saves", "avg_watch_s"]
FORMATS = ["reel", "carousel", "photo", "story", "live"]

# Labels as Instagram's insights screens word them, longest first so "Accounts reached"
# wins over "Reach" and "Average watch time" over "Watch time".
LABELS = [
    ("avg_watch_s", ["average watch time", "avg. watch time", "avg watch time"]),
    ("reach", ["accounts reached", "reach"]),
    ("views", ["views", "plays"]),
    ("likes", ["likes"]),
    ("comments", ["comments"]),
    ("shares", ["shares", "sends"]),
    ("saves", ["saves"]),
]
NUM_RE = r"(\d[\d,.\u202f\xa0]*\d|\d)\s*([kKmM]\b)?"


def config_dir():
    """$XDG_CONFIG_HOME/ig-plan, or ~/.config/ig-plan, as the other skills do."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base).expanduser() / "ig-plan"


def default_log():
    env = os.environ.get("IG_PLAN_LOG")
    if env:
        return Path(env).expanduser()
    return config_dir() / "posted.csv"


def parse_number(text, suffix=None):
    """'12,345' -> 12345, '1.2K' -> 1200, '3.4M' -> 3400000, '1 234' -> 1234."""
    t = text.strip().replace(" ", "").replace(" ", "").replace("\xa0", "")
    if not t:
        return None
    mult = 1
    if suffix:
        mult = 1000 if suffix.lower() == "k" else 1_000_000
    if mult > 1:
        t = t.replace(",", ".") if t.count(",") == 1 and "." not in t else t.replace(",", "")
        try:
            return int(round(float(t) * mult))
        except ValueError:
            return None
    # Without a suffix, separators are thousands separators ("12,345" or "12.345").
    digits = re.sub(r"[,.]", "", t)
    return int(digits) if digits.isdigit() else None


def parse_duration(text):
    """'7 sec', '7s', '1m 5s', '1 min 5 sec', '0:07', '12.5 s' -> seconds (float)."""
    t = text.strip().lower()
    m = re.match(r"^(\d+):(\d{2})(?::(\d{2}))?", t)
    if m:
        a, b, c = m.groups()
        return float(int(a) * 3600 + int(b) * 60 + int(c)) if c else float(int(a) * 60 + int(b))
    total, found = 0.0, False
    for num, unit in re.findall(r"(\d+(?:[.,]\d+)?)\s*(h|hr|hours?|m|min|mins|minutes?|s|sec|secs|seconds?)\b", t):
        v = float(num.replace(",", "."))
        total += v * (3600 if unit.startswith("h") else 60 if unit.startswith("m") else 1)
        found = True
    return round(total, 1) if found else None


def parse_insights(text):
    """Numbers found in a pasted insights screen, as {column: value}."""
    out = {}
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n")]
    lines = [ln for ln in lines if ln]
    used = set()
    for col, names in LABELS:
        if col in out:
            continue
        for i, ln in enumerate(lines):
            low = ln.lower().rstrip(":")
            for name in names:
                if not low.startswith(name):
                    continue
                rest = ln[len(name):].strip(" :\t-")
                # "Reach" must not swallow "Reached" etc.; the next char must not be a letter.
                if rest[:1].isalpha():
                    continue
                if not rest and i + 1 < len(lines) and (i + 1) not in used:
                    rest = lines[i + 1]
                    used.add(i + 1)
                if col == "avg_watch_s":
                    val = parse_duration(rest)
                else:
                    m = re.match(NUM_RE, rest)
                    val = parse_number(m.group(1), m.group(2)) if m else None
                if val is not None:
                    out[col] = val
                    used.add(i)
                    break
            if col in out:
                break
    return out


def load(path):
    if not path.exists():
        return [], list(LOG_COLS)
    with path.open(newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        cols = list(rd.fieldnames or LOG_COLS)
        rows = list(rd)
    for c in LOG_COLS:
        if c not in cols:
            cols.append(c)
    return rows, cols


def save(path, rows, cols):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".posted-", suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    os.replace(tmp, path)


def parse_when(text):
    """'2026-11-10 18:30', '2026-11-10T18:30', '2026-11-10' -> 'YYYY-MM-DD HH:MM' (time may be absent)."""
    t = text.strip().replace("T", " ")
    for fmt, has_time in (("%Y-%m-%d %H:%M", True), ("%Y-%m-%d %H:%M:%S", True), ("%Y-%m-%d", False)):
        try:
            d = datetime.datetime.strptime(t, fmt)
            return d.strftime("%Y-%m-%d %H:%M") if has_time else d.strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError(f"can't read the date {text!r}: use YYYY-MM-DD HH:MM (24-hour, your local time)")


def fmt_num(v):
    if isinstance(v, float) and not v.is_integer():
        return str(v)
    return str(int(v))


def pick(rows, a):
    """The post an insights paste belongs to."""
    if a.id:
        hits = [r for r in rows if r.get("id") == str(a.id)]
    elif a.url:
        key = a.url.rstrip("/").split("?")[0]
        hits = [r for r in rows if r.get("url", "").rstrip("/").split("?")[0] == key]
    elif a.topic:
        hits = [r for r in rows if a.topic.lower() in r.get("topic", "").lower()]
        if len(hits) > 1:
            names = "; ".join(f'#{r["id"]} {r["topic"]}' for r in hits)
            sys.exit(f"error: --topic matches {len(hits)} posts ({names}); use --id")
    else:
        hits = [r for r in rows if not r.get("views")]
        hits = sorted(hits, key=lambda r: r.get("posted_at", ""))[-1:]
        if not hits:
            sys.exit("error: every post already has views; say which one with --id, --url or --topic")
    if not hits:
        sys.exit("error: no post in the log matches; add it first with `postlog.py add`")
    return hits[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", type=Path, default=None, help="log file (default: IG_PLAN_LOG, else $XDG_CONFIG_HOME/ig-plan/posted.csv, else ~/.config/ig-plan/posted.csv)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ad = sub.add_parser("add", help="add a post")
    ad.add_argument("--at", required=True, help="when it went up, YYYY-MM-DD HH:MM local time")
    ad.add_argument("--format", required=True, choices=FORMATS)
    ad.add_argument("--topic", required=True, help="what it was about, in a few words")
    ad.add_argument("--hook", default="", help="its opening line (spoken or on screen), so a later "
                    "plan can tell when an idea makes the same promise")
    ad.add_argument("--idea", default="", help="the research idea slug it came from, if any")
    ad.add_argument("--url", default="")
    for c in ["views", "reach", "likes", "comments", "shares", "saves"]:
        ad.add_argument(f"--{c}", type=int)
    ad.add_argument("--watch", type=float, dest="avg_watch_s", help="average watch time in seconds")

    ins = sub.add_parser("insights", help="import a pasted insights screen (stdin or --file)")
    g = ins.add_mutually_exclusive_group()
    g.add_argument("--id", type=int)
    g.add_argument("--url")
    g.add_argument("--topic")
    ins.add_argument("--file", type=Path)

    ls = sub.add_parser("list", help="show the log")
    ls.add_argument("--json", action="store_true")
    sub.add_parser("path", help="print where the log is")

    a = ap.parse_args(argv)
    path = (a.log or default_log()).expanduser()

    if a.cmd == "path":
        print(path)
        return 0

    rows, cols = load(path)

    if a.cmd == "add":
        try:
            when = parse_when(a.at)
        except ValueError as e:
            sys.exit(f"error: {e}")
        if a.url and any(r.get("url") == a.url for r in rows):
            sys.exit(f"error: {a.url} is already in the log")
        nid = max([int(r["id"]) for r in rows if str(r.get("id", "")).isdigit()] or [0]) + 1
        row = {"id": str(nid), "posted_at": when, "format": a.format, "topic": a.topic.strip(),
               "idea": a.idea.strip(), "url": a.url.strip(), "hook": a.hook.strip(),
               "logged": datetime.date.today().isoformat()}
        for c in NUM_COLS:
            v = getattr(a, c, None)
            row[c] = "" if v is None else fmt_num(v)
        rows.append(row)
        save(path, rows, cols)
        print(f"added #{nid}: {when} {a.format} \"{row['topic']}\" -> {path}")
        return 0

    if a.cmd == "insights":
        text = a.file.read_text(encoding="utf-8") if a.file else sys.stdin.read()
        got = parse_insights(text)
        if not got:
            sys.exit("error: no numbers recognised; paste the insights screen text "
                     "(lines like 'Views 12,345', 'Shares 80')")
        if not rows:
            sys.exit("error: the log is empty; add the post first with `postlog.py add`")
        r = pick(rows, a)
        for c, v in got.items():
            r[c] = fmt_num(v)
        save(path, rows, cols)
        read = ", ".join(f"{c}={fmt_num(v)}" for c, v in got.items())
        missing = [c for c in NUM_COLS if c not in got]
        print(f"#{r['id']} {r['posted_at']} \"{r['topic']}\": read {read}")
        if missing:
            print("not in the paste (left as they were): " + ", ".join(missing))
        return 0

    if a.cmd == "list":
        if a.json:
            print(json.dumps(rows, indent=1, ensure_ascii=False))
            return 0
        if not rows:
            print(f"(empty log: {path})")
            return 0
        print(f"{len(rows)} posts in {path}")
        for r in sorted(rows, key=lambda r: r.get("posted_at", "")):
            nums = " ".join(f"{c}={r[c]}" for c in NUM_COLS if r.get(c))
            print(f"#{r['id']:>3} {r['posted_at']:<16} {r['format']:<8} {r['topic']}  {nums or '(no numbers yet)'}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
