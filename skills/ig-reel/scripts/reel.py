#!/usr/bin/env python3
"""reel.py - the counting parts of writing a Reel. The writing itself is the model's job.

    reel.py skills
        Which of the pack's other skills are installed (ig-research, ig-script, ig-voice,
        ig-caption), so each step can say what it will run and what it will skip.

    reel.py evidence <folder | research CSV | hooks file> [--idea "IDEA"] [--top 8] [--json]
        Reads what ig-research left for an idea: its research-<idea>-<date>.csv and the
        research-<idea>-<date>-hooks.md beside it. Prints the winners in the research's own
        order (shares per 1,000 views) with each one's spoken hook, text hook and who a
        viewer would send it to, skipping Reels the research marked for low reactions.
        Given a folder, it takes the newest research files in it (or under it), matched to
        --idea when given.

    reel.py check <draft.md> [--wps 2.5] [--target SECONDS] [--json]
        Reads a draft in the shape SKILL.md describes (## Hook, ## Script, ## On-screen
        text) and prints the length, when each line starts, the words heard by 0:03, every
        {{placeholder}} still to fill, problems with the on-screen timings (overlaps,
        order, after the end, a card more than 1.5 s before the spoken line it backs up,
        too long to read), how far the length is from --target, and the copy-ready block.
        Exit 0: ready to record. Exit 1: placeholders or problems left. Exit 2: the draft
        could not be read.

Times are estimates from word count at a fixed speaking rate (2.5 words a second unless
--wps says otherwise). Words are counted by one rule shared with ig-script's timeline.py
(see spoken_words): a {{placeholder}} is one word, "$18,000" is three, and a word is
heard by 0:03 once it has been said in full. Hooks are scored in hooks.py, before a script exists; nothing here
judges the writing.

Standard library only. No network.
"""
import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

SIBLINGS = ("ig-research", "ig-script", "ig-voice", "ig-caption")
SKILL_ROOTS = ("~/.claude/skills", "~/.codex/skills", "~/.agents/skills")

HOOK_WINDOW = 3.0       # seconds: what the viewer has heard when most decide to stay
READ_WPS = 3.0          # on-screen words a viewer can read per second, alongside the voice
EARLY_CARD = 1.5        # seconds: a card this much before the line it backs up gives it away
RANK_MIN_VIEWS = 10_000
PLACEHOLDER = re.compile(r"\{\{[^{}]*\}\}")
TIMECODE = r"(\d+):(\d{1,2}(?:\.\d+)?)"
CUE = re.compile(rf"^\s*[-*]?\s*{TIMECODE}\s*(?:-|–|to)\s*{TIMECODE}\s*[:|]?\s*(.*)$")
CUE_OPEN = re.compile(rf"^\s*[-*]?\s*{TIMECODE}\s*(?:-|–|to)\s*(?:end)?\s*[:|]?\s*(.*)$", re.I)


# ---------------------------------------------------------------- skills

def find_skill(name, here=None):
    """Where a sibling skill is installed, or None. Looks next to this skill first, then in
    the usual skills folders. Never required: every step works without it."""
    here = Path(here or Path(__file__).resolve().parent.parent)
    candidates = [here.parent / name] + [Path(os.path.expanduser(r)) / name for r in SKILL_ROOTS]
    for c in candidates:
        if (c / "SKILL.md").is_file():
            return str(c)
    return None


def cmd_skills(a):
    found = {n: find_skill(n) for n in SIBLINGS}
    if a.json:
        print(json.dumps(found, indent=2))
        return 0
    for n, path in found.items():
        print(f"{n}: " + (f"installed ({path})" if path else "not found"))
    return 0


# ---------------------------------------------------------------- evidence

def _num(s):
    try:
        return float(str(s).replace(",", "")) if str(s).strip() != "" else None
    except ValueError:
        return None


def _reel_code(text):
    m = re.search(r"instagram\.com/(?:[^/\s]+/)?(?:reels?|p)/([A-Za-z0-9_-]+)", text or "")
    return m.group(1) if m else None


def read_hooks(path):
    """The hooks table ig-research writes, keyed by Reel code. The table is written by a
    model, so columns are found by their header words, not by position."""
    rows = {}
    header = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            header = None if not s else header
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(set(c) <= set(":- ") for c in cells):
            continue
        rec = dict(zip(header, cells))

        def col(*words):
            for h, v in rec.items():
                if all(w in h for w in words):
                    return v
            return ""

        code = _reel_code(" ".join(cells))
        if not code:
            continue
        rows[code] = {
            "spoken_hook": col("spoken"),
            "text_hook": col("text"),
            "would_send_to": col("send"),
        }
    return rows


def research_files(target, idea=None):
    """(csv, hooks) for a folder, a CSV or a hooks file. In a folder, the newest research
    CSV (by the date in its name, then by modification time), matched to the idea when
    given; the hooks file is the one with the same stem."""
    p = Path(target).expanduser()
    if p.is_file():
        if p.name.endswith("-hooks.md"):
            stem = p.name[: -len("-hooks.md")]
            c = p.with_name(stem + ".csv")
            return (c if c.is_file() else None), p
        h = p.with_name(p.stem + "-hooks.md")
        return p, (h if h.is_file() else None)
    if not p.is_dir():
        return None, None
    cands = [c for c in p.rglob("research-*.csv")]
    if idea:
        words = [w for w in re.split(r"[^a-z0-9]+", idea.lower()) if len(w) > 2]
        if words:
            def score(c):
                return sum(w in c.name.lower() for w in words)
            best = max((score(c) for c in cands), default=0)
            cands = [c for c in cands if best and score(c) == best]
    if not cands:
        hooks = sorted(p.rglob("research-*-hooks.md"), key=lambda h: h.stat().st_mtime)
        return (None, hooks[-1]) if hooks else (None, None)

    def key(c):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", c.name)
        return (m.group(1) if m else "", c.stat().st_mtime)

    c = max(cands, key=key)
    h = c.with_name(c.stem + "-hooks.md")
    return c, (h if h.is_file() else None)


def evidence(csv_path, hooks_path, top=8):
    hooks = read_hooks(hooks_path) if hooks_path else {}
    out = {"csv": str(csv_path) if csv_path else None,
           "hooks": str(hooks_path) if hooks_path else None,
           "winners": [], "skipped_low_reactions": 0, "without_hook": 0}
    if not csv_path:
        # Only a hooks file: keep its own order.
        for code, h in hooks.items():
            out["winners"].append({"code": code, "url": f"https://www.instagram.com/reel/{code}/", **h})
        out["winners"] = out["winners"][:top]
        return out
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ranked = []
    for r in rows:
        if r.get("platform", "Instagram") != "Instagram":
            continue
        if "low_reactions" not in r:
            # Research from before the flag: likes + comments under 2% of 10K+ views.
            v, lk = _num(r.get("ig_only_views")) or _num(r.get("views")), _num(r.get("likes"))
            if v and v >= RANK_MIN_VIEWS and lk is not None and (lk + (_num(r.get("comments")) or 0)) < 0.02 * v:
                r["low_reactions"] = "yes"
        if (r.get("low_reactions") or "").strip():
            out["skipped_low_reactions"] += 1
            continue
        if _num(r.get("shares_per_1k_views")) is None:
            # Research from before the rate column: work it out the same way.
            v = _num(r.get("ig_only_views")) or _num(r.get("views"))
            sh = _num(r.get("shares"))
            if v and sh is not None:
                r["shares_per_1k_views"] = round(1000 * sh / v, 2)
        ranked.append(r)

    def order(r):
        sr = _num(r.get("send_rank"))
        if sr is not None:
            return (0, sr)
        spk = _num(r.get("shares_per_1k_views"))
        v = _num(r.get("views")) or 0
        if spk is not None and v >= RANK_MIN_VIEWS:
            return (1, -spk)
        return (2, -v)

    ranked.sort(key=order)
    if hooks:
        # The hooks file is the research's own pick of on-topic winners: lead with those.
        ranked.sort(key=lambda r: 0 if _reel_code(r.get("url")) in hooks else 1)
    for r in ranked[:top]:
        code = _reel_code(r.get("url"))
        h = hooks.get(code, {})
        if not h:
            out["without_hook"] += 1
        out["winners"].append({
            "code": code, "url": r.get("url"), "account": r.get("account"),
            "views": _num(r.get("views")), "shares_per_1k_views": _num(r.get("shares_per_1k_views")),
            "posted": r.get("posted"), "age_days": _num(r.get("age_days")),
            "spoken_hook": h.get("spoken_hook", ""), "text_hook": h.get("text_hook", ""),
            "would_send_to": h.get("would_send_to", ""),
            "caption": (r.get("caption") or "")[:120],
        })
    return out


def _short(n):
    if n is None:
        return ""
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}K"
    return f"{n:.0f}"


def _cell(s):
    return (s or "").replace("|", "/").replace("\n", " ").strip()


def render_evidence(ev):
    lines = []
    if not ev["winners"]:
        lines.append("No research found. The hooks will be unproven: offer to run ig-research first.")
        return "\n".join(lines)
    lines.append(f"Research: {ev['csv'] or '(no CSV)'}")
    lines.append(f"Hooks:    {ev['hooks'] or 'none yet: run ig-research step 4 (hooks of the top Reels) before writing'}")
    lines.append("")
    lines.append("| # | Reel | Creator | Views | Shares/1K | Age | Spoken hook | Text hook | Would send to |")
    lines.append("|---:|---|---|---:|---:|---|---|---|---|")
    for i, w in enumerate(ev["winners"], 1):
        age = f"{w['age_days']:.0f} d" if w.get("age_days") is not None else ""
        spk = f"{w['shares_per_1k_views']:.1f}" if w.get("shares_per_1k_views") is not None else ""
        lines.append(f"| {i} | [Reel]({w['url']}) | @{_cell(w.get('account'))} | {_short(w.get('views'))} | "
                     f"{spk} | {age} | {_cell(w['spoken_hook']) or '?'} | {_cell(w['text_hook']) or '?'} | "
                     f"{_cell(w['would_send_to']) or '?'} |")
    notes = []
    if ev["skipped_low_reactions"]:
        notes.append(f"{ev['skipped_low_reactions']} Reel(s) marked for low reactions left out")
    if ev["without_hook"]:
        notes.append(f"{ev['without_hook']} winner(s) with no hook read yet (marked ?)")
    if notes:
        lines.append("")
        lines.append("Note: " + "; ".join(notes) + ".")
    return "\n".join(lines)


def cmd_evidence(a):
    csv_path, hooks_path = research_files(a.target, a.idea)
    ev = evidence(csv_path, hooks_path, a.top) if (csv_path or hooks_path) else \
        {"csv": None, "hooks": None, "winners": [], "skipped_low_reactions": 0, "without_hook": 0}
    print(json.dumps(ev, indent=2, ensure_ascii=False) if a.json else render_evidence(ev))
    return 0


# ---------------------------------------------------------------- draft check

def unquote(s):
    """Drop quotes around a whole value ("like this"), but keep a quote inside one
    (Dana: "cleanest month")."""
    s = (s or "").strip()
    if len(s) > 1 and s[0] in "\"“" and s[-1] in "\"”" and not re.search("[\"“”]", s[1:-1]):
        return s[1:-1].strip()
    return s


def parse_draft(text):
    """Split a draft into its sections. Headings are matched loosely: '## Hook',
    '## Script', '## On-screen text' (or 'On screen', 'Text on screen')."""
    sections, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^\s{0,3}#{1,4}\s+(.*?)\s*#*\s*$", line)
        if m:
            h = m.group(1).lower()
            if "screen" in h:
                cur = "onscreen"
            elif "hook" in h:
                cur = "hook"
            elif "script" in h:
                cur = "script"
            else:
                cur = None
            if cur:
                sections.setdefault(cur, [])
            continue
        if cur:
            sections[cur].append(line)
    hook = {"spoken": "", "onscreen": ""}
    for line in sections.get("hook", []):
        m = re.match(r"^\s*[-*]?\s*(spoken|said|on[- ]?screen|text)\s*:\s*(.*)$", line, re.I)
        if m:
            k = "spoken" if m.group(1).lower() in ("spoken", "said") else "onscreen"
            hook[k] = unquote(m.group(2))
    script = []
    for line in sections.get("script", []):
        s = re.sub(r"^\s*(?:[-*]|L?\d+[.):])\s+", "", line).strip()
        if s:
            script.append(s)
    cues, bad = [], []
    for line in sections.get("onscreen", []):
        if not line.strip():
            continue
        m = CUE.match(line)
        if m:
            start = int(m.group(1)) * 60 + float(m.group(2))
            end = int(m.group(3)) * 60 + float(m.group(4))
            cues.append({"start": start, "end": end, "text": unquote(m.group(5))})
            continue
        m = CUE_OPEN.match(line)
        if m:
            start = int(m.group(1)) * 60 + float(m.group(2))
            cues.append({"start": start, "end": None, "text": unquote(m.group(3))})
            continue
        bad.append(line.strip())
    return {"hook": hook, "script": script, "cues": cues, "unparsed_cues": bad,
            "has": {k: k in sections for k in ("hook", "script", "onscreen")}}


# ---- Spoken word count. The same rule, in the same words, is in ig-script's
# scripts/timeline.py, so the two timers agree on the same lines; a test runs both.
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
    """Tokens a viewer reads (for on-screen text): one per word, figures included."""
    return [tok for tok, _ in spoken_words(text)]


CARD_STOP = {"the", "and", "for", "you", "your", "this", "that", "with", "from", "into", "then",
             "just", "what", "how", "it's", "its", "are", "was", "one", "now", "not", "all", "but"}


def _content(text):
    out = set()
    for tok in words(text):
        t = tok.lower().replace("’", "'")
        if PLACEHOLDER.fullmatch(tok) or re.search(r"\d", t) or (len(t) > 2 and t not in CARD_STOP):
            out.add(re.sub(r"'s$", "", t))
    return out


def spoken_line_for(card, timed):
    """Index of the spoken line an on-screen card backs up: the line sharing most of the
    card's content words (at least half of them), earliest on a tie. None if no line
    clearly matches; then the card isn't tied to one line and isn't timed against one."""
    cw = {w for w in _content(card) if not re.fullmatch(r"\d+", w)}  # "1." step numbers aren't said
    if not cw:
        return None
    best, best_n = None, 0
    for i, x in enumerate(timed):
        n = len(cw & _content(x["text"]))
        if n > best_n:
            best, best_n = i, n
    return best if best_n and best_n * 2 >= len(cw) else None


def tc(seconds):
    seconds = max(0.0, seconds)
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:04.1f}"


def check(d, wps=2.5, target=None):
    problems, warnings = [], []
    if not d["script"]:
        return {"error": "no script lines found under a '## Script' heading"}
    t, timed = 0.0, []
    for line in d["script"]:
        dur = spoken_count(line) / wps
        timed.append({"start": t, "dur": dur, "text": line})
        t += dur
    length = t
    placeholders = []
    for where, text in ([("hook (spoken)", d["hook"]["spoken"]), ("hook (on screen)", d["hook"]["onscreen"])]
                        + [(f"line {i}", s) for i, s in enumerate(d["script"], 1)]
                        + [(f"on screen {tc(c['start'])}", c["text"]) for c in d["cues"]]):
        for p in PLACEHOLDER.findall(text or ""):
            placeholders.append({"where": where, "placeholder": p})

    sp = d["hook"]["spoken"]
    if not sp:
        problems.append("no spoken hook ('Spoken:' under '## Hook')")
    elif _norm(d["script"][0]) != _norm(sp) and not _norm(" ".join(d["script"])).startswith(_norm(sp)):
        problems.append("the script does not open with the chosen spoken hook")
    if not d["hook"]["onscreen"]:
        warnings.append("no on-screen hook ('On screen:' under '## Hook'); write 'None' if that is the choice")

    cues = d["cues"]
    for b in d["unparsed_cues"]:
        problems.append(f"on-screen line without a timing (use '0:00-0:03 Text'): {b}")
    if not d["has"]["onscreen"]:
        warnings.append("no '## On-screen text' section")
    if cues:
        if cues[0]["start"] > 0.5:
            warnings.append(f"first on-screen text starts at {tc(cues[0]['start'])}, not 0:00")
        oh = d["hook"]["onscreen"]
        if oh and oh.lower() != "none" and _norm(cues[0]["text"]) != _norm(oh):
            warnings.append("the first on-screen cue is not the on-screen hook")
        for i, c in enumerate(cues):
            end = c["end"] if c["end"] is not None else length
            if c["end"] is not None and c["end"] <= c["start"]:
                problems.append(f"on screen {tc(c['start'])}: ends before it starts")
                continue
            if i and c["start"] < (cues[i - 1]["end"] if cues[i - 1]["end"] is not None else length) - 0.05:
                problems.append(f"on screen {tc(c['start'])}: overlaps the cue before it")
            if i and c["start"] < cues[i - 1]["start"]:
                problems.append(f"on screen {tc(c['start'])}: out of order")
            if c["start"] > length + 0.5:
                problems.append(f"on screen {tc(c['start'])}: starts after the script ends ({tc(length)})")
            n = len(words(c["text"]))
            need = n / READ_WPS
            if n and end - c["start"] < need:
                warnings.append(f"on screen {tc(c['start'])}: {n} words in {end - c['start']:.1f} s, "
                                f"about {need:.1f} s to read")
            if i:
                said = spoken_line_for(c["text"], timed)
                if said is not None and c["start"] < timed[said]["start"] - EARLY_CARD:
                    problems.append(
                        f"on screen {tc(c['start'])}: appears {timed[said]['start'] - c['start']:.1f} s before "
                        f"its spoken line (L{said + 1} at {tc(timed[said]['start'])}); move it to about "
                        f"{tc(timed[said]['start'])} so it doesn't give the line away")
    target_note = None
    if target:
        diff = length - target
        margin = max(5.0, 0.15 * target)
        side = "over" if diff > 0 else "under"
        target_note = (f"Target {tc(target)}: about {abs(diff):.0f} s {side}" if abs(diff) >= 0.5
                       else f"Target {tc(target)}: on it")
        if abs(diff) > margin:
            warnings.append(f"length {tc(length)} against a target of {tc(target)} "
                            f"({abs(diff):.0f} s {side}, more than the {margin:.0f} s margin)")
        else:
            target_note += f", inside the {margin:.0f} s margin"
    return {"length_s": round(length, 1), "words": sum(spoken_count(s) for s in d["script"]),
            "target_note": target_note,
            "wps": wps, "lines": [{"start": round(x["start"], 1), "dur": round(x["dur"], 1),
                                   "text": x["text"]} for x in timed],
            "heard_by_3s": words_heard_by(d["script"], HOOK_WINDOW, wps), "placeholders": placeholders,
            "problems": problems, "warnings": warnings,
            "ready": not problems and not placeholders}


def _norm(s):
    """Lowercase words only, so punctuation and quotes don't decide a match."""
    return " ".join(re.sub(r"[^a-z0-9{}' ]+", " ", (s or "").lower().replace("’", "'")).split())


def copy_block(d, r):
    out = ["```text", f"HOOK (said): {d['hook']['spoken']}",
           f"HOOK (on screen): {d['hook']['onscreen'] or 'None'}", "", "SCRIPT"]
    out += d["script"]
    out += ["", "ON-SCREEN TEXT"]
    for c in d["cues"]:
        end = tc(c["end"]) if c["end"] is not None else "end"
        out.append(f"{tc(c['start'])}-{end}  {c['text']}")
    if not d["cues"]:
        out.append("(none)")
    out += ["", f"LENGTH: about {tc(r['length_s'])} ({r['words']} words at {r['wps']:g} words a second)", "```"]
    return "\n".join(out)


def render_check(d, r):
    out = [f"Length: about {tc(r['length_s'])}, {r['words']} words at {r['wps']:g} words a second "
           "(an estimate; time a real take to know)."]
    if r.get("target_note"):
        out.append(r["target_note"] + ".")
    out.append(f"Heard by 0:03: \"{r['heard_by_3s']}\" (whole words said by 0:03)")
    out.append("")
    out.append("Timeline:")
    for i, x in enumerate(r["lines"], 1):
        out.append(f"  L{i:<2} {tc(x['start'])}  ({x['dur']:.1f} s)  {x['text']}")
    out.append("")
    if r["placeholders"]:
        out.append(f"To fill in ({len(r['placeholders'])}): only the person knows these. Never guess them.")
        for p in r["placeholders"]:
            out.append(f"  - {p['where']}: {p['placeholder']}")
    for p in r["problems"]:
        out.append(f"PROBLEM  {p}")
    for w in r["warnings"]:
        out.append(f"WARN     {w}")
    out.append("")
    if r["ready"]:
        out.append("READY TO RECORD")
    else:
        todo = (["fill the placeholders"] if r["placeholders"] else []) + \
               (["fix the problems above"] if r["problems"] else [])
        out.append("NOT READY: " + " and ".join(todo) + ".")
    out.append("")
    out.append(copy_block(d, r))
    return "\n".join(out)


def cmd_check(a):
    try:
        text = Path(a.draft).read_text(encoding="utf-8") if a.draft != "-" else sys.stdin.read()
    except OSError as e:
        print(f"cannot read draft: {e}", file=sys.stderr)
        return 2
    d = parse_draft(text)
    r = check(d, a.wps, a.target)
    if "error" in r:
        print(r["error"], file=sys.stderr)
        return 2
    if a.json:
        r["copy_block"] = copy_block(d, r)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(render_check(d, r))
    return 0 if r["ready"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="The counting parts of writing a Reel.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("skills", help="which sibling skills are installed")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_skills)
    e = sub.add_parser("evidence", help="the winners and their hooks from ig-research output")
    e.add_argument("target", help="a folder, a research CSV, or a -hooks.md file")
    e.add_argument("--idea", help="pick the research files whose name matches this idea")
    e.add_argument("--top", type=int, default=8)
    e.add_argument("--json", action="store_true")
    e.set_defaults(fn=cmd_evidence)
    c = sub.add_parser("check", help="time a draft, list placeholders, print the copy block")
    c.add_argument("draft", help="the draft file, or - for stdin")
    c.add_argument("--wps", type=float, default=2.5, help="spoken words per second (default 2.5)")
    c.add_argument("--target", type=float, help="target length in seconds")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_check)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
