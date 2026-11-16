#!/usr/bin/env python3
"""
score_profile.py - score an Instagram profile against our rubric.

Three commands, standard library only, no network. It never touches Instagram.

  rubric                 Print the rubric: parts, criteria, points, and whether each
                         rests on a platform fact or on judgement.
  check PROFILE.json     Count what can be counted in a profile (or in a rewrite of
                         one): bio length against the 150 limit, URLs typed into the
                         bio, fancy letters search may not match, handle shape, link
                         and pin counts, emoji-only highlight titles, days since the
                         last post, search words present. Facts for the rating; it
                         decides nothing.
  score RATINGS.json     Turn a rating of every criterion (met, partly, missed,
                         unseen) into a score out of 100, each part's points with the
                         reasons, and the fix-first list: criteria ordered by points
                         lost.

The rubric lives in references/rubric.json and its sources in references/sources.md.
Every run checks that the rubric's points add to exactly 100, that ids are unique,
and that every platform criterion names a source that exists in sources.md.

Exit status: 0 fine, 1 a check failed (check command only), 2 bad input or a
broken rubric.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
RUBRIC_PATH = os.path.join(SKILL, "references", "rubric.json")
SOURCES_PATH = os.path.join(SKILL, "references", "sources.md")

# --- limits (sources in references/sources.md) -------------------------------

LIMITS = {
    "bio_chars": 150,       # ig-help-bio, confirmed
    "links": 5,             # ig-help-website, confirmed
    "pinned": 3,            # ig-help-pin, confirmed
    "name_chars": 30,       # name-length-guides, third-party only: warn, never fail
    "handle_chars": 30,     # name-length-guides, third-party only
    "recent_days": 14,      # our own judgement (posting.recent_regular)
    "stale_days": 30,       # our own judgement
}

VALUES = {"met": 1.0, "partly": 0.5, "missed": 0.0}
BASES = ("platform", "judgement")

URL_RE = re.compile(
    r"(https?://\S+|www\.\S+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|co|ai|app|dev|me|ly|gg|tv|link|page|site|shop|store|xyz|info|biz|bio)(?:/\S*)?\b)",
    re.IGNORECASE,
)
HANDLE_RE = re.compile(r"^[a-z0-9._]+$")


class RubricError(Exception):
    pass


# --- rubric --------------------------------------------------------------------

def source_ids(path=SOURCES_PATH):
    """Ids are the first word of each '## id: ...' heading; 'a and b' headings give both."""
    ids = set()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("## "):
                    head = line[3:].split(":", 1)[0]
                    for part in head.split(" and "):
                        part = part.strip()
                        if re.fullmatch(r"[a-z0-9-]+", part):
                            ids.add(part)
    except OSError:
        pass
    return ids


def load_rubric(path=RUBRIC_PATH, sources_path=SOURCES_PATH):
    try:
        with open(path, encoding="utf-8") as f:
            rubric = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise RubricError(f"cannot read rubric {path}: {e}")
    validate_rubric(rubric, source_ids(sources_path))
    return rubric


def validate_rubric(rubric, known_sources):
    problems = []
    seen = set()
    total = 0
    parts = rubric.get("parts") or []
    if not parts:
        problems.append("no parts")
    for part in parts:
        if not part.get("criteria"):
            problems.append(f"part {part.get('id')!r} has no criteria")
        for c in part.get("criteria", []):
            cid = c.get("id")
            if not cid or cid in seen:
                problems.append(f"missing or duplicate criterion id {cid!r}")
            seen.add(cid)
            pts = c.get("points")
            if not isinstance(pts, int) or pts <= 0:
                problems.append(f"{cid}: points must be a positive whole number")
            else:
                total += pts
            if c.get("basis") not in BASES:
                problems.append(f"{cid}: basis must be one of {BASES}")
            srcs = c.get("sources", [])
            if c.get("basis") == "platform" and not srcs:
                problems.append(f"{cid}: a platform criterion needs at least one source")
            for s in srcs:
                if s not in known_sources:
                    problems.append(f"{cid}: source {s!r} is not a heading in references/sources.md")
            for key in ("check", "met", "partly", "missed"):
                if not c.get(key):
                    problems.append(f"{cid}: missing {key!r}")
    if total != 100:
        problems.append(f"points add to {total}, not 100")
    if problems:
        raise RubricError("rubric is broken:\n  " + "\n  ".join(problems))


def criteria(rubric):
    for part in rubric["parts"]:
        for c in part["criteria"]:
            yield part, c


def render_rubric(rubric):
    out = [f"Rubric v{rubric.get('version')} (sources checked {rubric.get('checked')}), 100 points.", ""]
    for part in rubric["parts"]:
        pts = sum(c["points"] for c in part["criteria"])
        out.append(f"{part['title']} ({pts})")
        for c in part["criteria"]:
            tag = "platform" if c["basis"] == "platform" else "judgement"
            src = f" [{', '.join(c['sources'])}]" if c["sources"] else ""
            out.append(f"  {c['points']:>2}  {c['id']:<32} {tag}{src}")
            out.append(f"      {c['check']}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# --- check: count what can be counted -------------------------------------------

def is_emoji(ch):
    cp = ord(ch)
    return (
        0x1F000 <= cp <= 0x1FAFF
        or 0x2600 <= cp <= 0x27BF
        or 0x2B00 <= cp <= 0x2BFF
        or cp in (0x200D, 0xFE0F, 0x20E3)
        or 0x1F1E6 <= cp <= 0x1F1FF
    )


def only_emoji_or_symbols(text):
    t = [ch for ch in text if not ch.isspace()]
    return bool(t) and all(is_emoji(ch) or unicodedata.category(ch).startswith(("S", "P")) for ch in t)


def fancy_letters(text):
    """Letters from the Mathematical Alphanumeric block and similar 'font' tricks."""
    out = []
    for ch in text:
        cp = ord(ch)
        if 0x1D400 <= cp <= 0x1D7FF or 0xFF21 <= cp <= 0xFF5A or 0x24B6 <= cp <= 0x24E9:
            out.append(ch)
    return out


def utf16_len(text):
    return len(text.encode("utf-16-le")) // 2


def norm_words(text):
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[^\w\s]", " ", text)


def contains_phrase(haystack, phrase):
    h = " " + " ".join(norm_words(haystack).split()) + " "
    p = " ".join(norm_words(phrase).split())
    return bool(p) and f" {p} " in h


def parse_date(value):
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def voice_profile_path():
    env = os.environ.get("IG_VOICE_PROFILE")
    if env:
        return env
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "ig-voice", "voice.md")


def check_profile(p, keywords=(), today=None):
    """Return a list of (status, field, message). status: PASS, WARN, FAIL, INFO."""
    today = today or dt.date.today()
    res = []
    add = lambda s, f, m: res.append((s, f, m))

    name = p.get("name") or ""
    handle = (p.get("handle") or "").lstrip("@")
    bio = p.get("bio") or ""

    # name
    if not name.strip():
        add("WARN", "name", "Name field is empty; it is one of the fields search matches.")
    else:
        n = len(name)
        if n > LIMITS["name_chars"]:
            add("WARN", "name", f"{n} characters; guides put the limit near {LIMITS['name_chars']} (not confirmed by Instagram).")
        else:
            add("PASS", "name", f"{n} characters.")
        squash = lambda t: re.sub(r"[\W_]", "", unicodedata.normalize("NFKC", t).lower())
        if handle and squash(name) == squash(handle):
            add("WARN", "name", "Name field repeats the handle, so it adds no search words.")
        if fancy_letters(name):
            add("WARN", "name", "Uses 'font' letters; search matches typed text and may not match these.")
        if only_emoji_or_symbols(name):
            add("WARN", "name", "Name field is only emoji or symbols.")

    # handle
    if handle:
        h = handle.lower()
        if len(h) > LIMITS["handle_chars"] or not HANDLE_RE.match(h):
            add("FAIL", "handle", "Handles are letters, numbers, dots and underscores, about 30 at most.")
        awkward = h.count(".") + h.count("_") + sum(ch.isdigit() for ch in h)
        if awkward >= 2:
            add("WARN", "handle", f"{awkward} dots, underscores or digits: hard to spell from hearing it.")
        elif awkward == 1:
            add("INFO", "handle", "One dot, underscore or digit; fine if people already know it.")
        else:
            add("PASS", "handle", "Plain letters, easy to say and spell.")

    # bio
    if not bio.strip():
        add("WARN", "bio", "Bio is empty.")
    else:
        n = len(bio)
        if n > LIMITS["bio_chars"]:
            add("FAIL", "bio", f"{n} of {LIMITS['bio_chars']} characters: Instagram will not accept it.")
        elif utf16_len(bio) > LIMITS["bio_chars"]:
            add("WARN", "bio", f"{n} characters, {utf16_len(bio)} if emoji count double; trim to be safe.")
        else:
            add("PASS", "bio", f"{n} of {LIMITS['bio_chars']} characters.")
        lines = bio.splitlines()
        if any(only_emoji_or_symbols(l) for l in lines if l.strip()):
            add("WARN", "bio", "A line holds only emoji or symbols; it spends characters and says nothing.")
        if len([l for l in lines if l.strip()]) > 5:
            add("WARN", "bio", "More than 5 lines; hard to scan.")
        if URL_RE.search(bio):
            add("WARN", "bio", "A URL is typed into the bio text; it is not clickable there. Use Links.")
        if fancy_letters(bio):
            add("WARN", "bio", "Uses 'font' letters; search and screen readers may not read them.")

    # keywords
    for kw in keywords:
        where = [f for f, t in (("name", name), ("bio", bio)) if contains_phrase(t, kw)]
        if where:
            add("PASS", "search words", f"'{kw}' is in the {' and '.join(where)}.")
        elif "#" + "".join(norm_words(kw).split()) in unicodedata.normalize("NFKC", bio).lower():
            add("WARN", "search words", f"'{kw}' is only a hashtag; write it as words too.")
        else:
            add("WARN", "search words", f"'{kw}' is not in the name or bio.")

    # links
    links = p.get("links")
    if links is not None:
        k = len(links)
        if k > LIMITS["links"]:
            add("FAIL", "links", f"{k} links; Instagram allows {LIMITS['links']}.")
        elif k == 0:
            add("WARN", "links", "No link in the Links section.")
        else:
            first = links[0]
            title = first.get("title") if isinstance(first, dict) else None
            add("PASS", "links", f"{k} of {LIMITS['links']}. First (the one shown in full): "
                f"{(first.get('url') if isinstance(first, dict) else first) or '?'}"
                + (f", titled '{title}'" if title else ", no title"))

    # highlights
    hl = p.get("highlights")
    if hl is not None:
        if not hl:
            add("WARN", "highlights", "No highlights.")
        else:
            bad = [t for t in hl if not str(t).strip() or only_emoji_or_symbols(str(t))]
            if bad:
                add("WARN", "highlights", f"{len(bad)} title(s) are emoji or empty: a newcomer can't tell what's inside.")
            else:
                add("PASS", "highlights", f"{len(hl)}: " + ", ".join(str(t) for t in hl))

    # pinned
    pins = p.get("pinned")
    if pins is not None:
        k = len(pins)
        if k > LIMITS["pinned"]:
            add("FAIL", "pinned", f"{k} pinned; Instagram allows {LIMITS['pinned']}.")
        elif k == 0:
            add("WARN", "pinned", "Nothing pinned.")
        else:
            add("PASS", "pinned", f"{k} of {LIMITS['pinned']}.")

    # posting
    last = parse_date(p.get("last_post"))
    if last:
        days = (today - last).days
        if days > LIMITS["stale_days"]:
            add("WARN", "posting", f"Last post {days} day{'s' if days != 1 else ''} ago.")
        elif days > LIMITS["recent_days"]:
            add("INFO", "posting", f"Last post {days} days ago (over {LIMITS['recent_days']}).")
        else:
            add("PASS", "posting", f"Last post {days} day{'s' if days != 1 else ''} ago.")

    # ig-voice
    vp = voice_profile_path()
    if os.path.isfile(vp):
        add("INFO", "voice", f"ig-voice profile found at {vp}: write the bio in that voice.")
    else:
        add("INFO", "voice", "No ig-voice profile found; write the bio plainly.")
    return res


def render_check(res):
    out = ["Profile facts (counted, not judged):"]
    for s, f, m in res:
        out.append(f"  {s:<4}  {f:<12}  {m}")
    fails = sum(1 for s, _, _ in res if s == "FAIL")
    out.append("")
    out.append("Result: " + (f"{fails} limit(s) broken; fix before using." if fails else "within Instagram's limits."))
    return "\n".join(out) + "\n"


# --- score ---------------------------------------------------------------------

def read_rating(entry):
    """Accept 'met', {'rating': 'met', 'reason': ...}, or a number 1 / 0.5 / 0."""
    reason = ""
    if isinstance(entry, dict):
        reason = str(entry.get("reason") or "")
        entry = entry.get("rating")
    if isinstance(entry, bool):
        raise ValueError("rating cannot be true/false")
    if isinstance(entry, (int, float)):
        for k, v in VALUES.items():
            if float(entry) == v:
                return k, reason
        raise ValueError(f"number rating must be 1, 0.5 or 0, got {entry}")
    if isinstance(entry, str) and entry.lower() in (*VALUES, "unseen"):
        return entry.lower(), reason
    raise ValueError(f"rating must be met, partly, missed or unseen, got {entry!r}")


def score(rubric, ratings):
    given = ratings.get("ratings", ratings)
    if not isinstance(given, dict):
        raise ValueError("ratings must be an object keyed by criterion id")
    ids = {c["id"] for _, c in criteria(rubric)}
    unknown = sorted(set(given) - ids)
    missing = sorted(ids - set(given))
    if unknown or missing:
        msg = []
        if unknown:
            msg.append("unknown criterion id(s): " + ", ".join(unknown))
        if missing:
            msg.append("not rated: " + ", ".join(missing) + " (use \"unseen\" if you could not see it)")
        raise ValueError("; ".join(msg))

    rows, parts = [], []
    for part in rubric["parts"]:
        p_rows = []
        for c in part["criteria"]:
            rating, reason = read_rating(given[c["id"]])
            earned = 0.0 if rating == "unseen" else c["points"] * VALUES[rating]
            row = {
                "id": c["id"], "part": part["id"], "part_title": part["title"],
                "points": c["points"], "rating": rating, "earned": earned,
                "lost": 0.0 if rating == "unseen" else c["points"] - earned,
                "basis": c["basis"], "sources": c["sources"], "check": c["check"], "reason": reason,
            }
            p_rows.append(row)
            rows.append(row)
        parts.append({
            "id": part["id"], "title": part["title"],
            "max": sum(r["points"] for r in p_rows),
            "earned": sum(r["earned"] for r in p_rows),
            "unseen": sum(r["points"] for r in p_rows if r["rating"] == "unseen"),
        })
    total = sum(r["earned"] for r in rows)
    seen_max = sum(r["points"] for r in rows if r["rating"] != "unseen")
    fix = sorted((r for r in rows if r["lost"] > 0), key=lambda r: (-r["lost"], -r["points"], r["id"]))
    return {
        "total": total,
        "max": 100,
        "seen_max": seen_max,
        "scaled": round(total * 100 / seen_max, 1) if seen_max else None,
        "parts": parts,
        "fix_first": fix,
        "unseen": [r for r in rows if r["rating"] == "unseen"],
        "criteria": rows,
    }


def fmt(x):
    return f"{x:g}"


def render_score(res):
    out = [f"Score: {fmt(res['total'])} / 100"]
    if res["unseen"]:
        out[0] += (f"  ({fmt(res['seen_max'])} points could be seen; on those, "
                   f"{fmt(res['scaled'])} / 100. Unseen parts count as 0 until checked.)")
    out.append("")
    w = max(len(p["title"]) for p in res["parts"])
    out.append(f"  {'Part':<{w}}  {'Points':>7}  Why points were lost")
    by_part = {}
    for r in res["criteria"]:
        by_part.setdefault(r["part"], []).append(r)
    for p in res["parts"]:
        lost = [r for r in by_part[p["id"]] if r["lost"] > 0 or r["rating"] == "unseen"]
        why = "; ".join(
            (f"{r['id'].split('.', 1)[1]} {r['rating']}" + (f": {r['reason']}" if r["reason"] else ""))
            for r in lost) or "full marks"
        pts = f"{fmt(p['earned'])}/{p['max']}"
        out.append(f"  {p['title']:<{w}}  {pts:>7}  {why}")
    out.append("")
    if res["fix_first"]:
        out.append("Fix first (most points lost first):")
        for i, r in enumerate(res["fix_first"], 1):
            tag = "platform" if r["basis"] == "platform" else "judgement"
            out.append(f"  {i}. -{fmt(r['lost'])}  {r['part_title']}: {r['id']} ({r['rating']}, {tag})")
            out.append(f"       {r['check']}")
            if r["reason"]:
                out.append(f"       Seen: {r['reason']}")
    else:
        out.append("Nothing to fix: full marks on everything that could be seen.")
    if res["unseen"]:
        out.append("")
        out.append("Could not see (check these, then score again): " + ", ".join(r["id"] for r in res["unseen"]))
    return "\n".join(out) + "\n"


# --- cli -----------------------------------------------------------------------

def read_json(path):
    try:
        if path == "-":
            return json.load(sys.stdin)
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"cannot read {path}: {e}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Score an Instagram profile against the ig-profile rubric.")
    ap.add_argument("--rubric", default=RUBRIC_PATH, help=argparse.SUPPRESS)
    ap.add_argument("--sources", default=SOURCES_PATH, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rubric", help="print the rubric")
    r.add_argument("--json", action="store_true")
    c = sub.add_parser("check", help="count what can be counted in a profile or a rewrite")
    c.add_argument("profile")
    c.add_argument("--keywords", default="", help="comma-separated search words to look for")
    c.add_argument("--today", help="YYYY-MM-DD, for days since the last post")
    c.add_argument("--json", action="store_true")
    s = sub.add_parser("score", help="score a rating of every criterion")
    s.add_argument("ratings")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        rubric = load_rubric(a.rubric, a.sources)
    except RubricError as e:
        print(e, file=sys.stderr)
        return 2

    try:
        if a.cmd == "rubric":
            print(json.dumps(rubric, indent=2) if a.json else render_rubric(rubric), end="" if not a.json else "\n")
            return 0
        if a.cmd == "check":
            profile = read_json(a.profile)
            kws = [k.strip() for k in a.keywords.split(",") if k.strip()]
            today = parse_date(a.today) if a.today else None
            res = check_profile(profile, kws, today)
            if a.json:
                print(json.dumps([{"status": s, "field": f, "message": m} for s, f, m in res], indent=2))
            else:
                print(render_check(res), end="")
            return 1 if any(s == "FAIL" for s, _, _ in res) else 0
        if a.cmd == "score":
            res = score(rubric, read_json(a.ratings))
            print(json.dumps(res, indent=2) if a.json else render_score(res), end="" if not a.json else "\n")
            return 0
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
