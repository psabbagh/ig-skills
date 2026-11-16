#!/usr/bin/env python3
"""hooks.py - the 26 hook formulas, which ones the research backs, and a filter for weak hooks.

    hooks.py list [--json]
        The 26 formulas in references/hooks.json: name, move, template, example, the
        on-screen version and when to use it.

    hooks.py pick <folder | research CSV | hooks file> [--idea "IDEA"] [--top 8] [--json]
        Matches each winner's spoken and on-screen hook (from ig-research's output, read
        the same way as reel.py evidence) to the formulas it resembles, and ranks the
        formulas by the shares per 1,000 views of the winners that used them. A winner
        whose spoken hook is missing ("no captions") is matched on its on-screen hook. A
        formula matches only on its defining feature, so a hook that fits none is listed
        as unmatched, with both its hooks, rather than given a wrong name. Read the
        matches as suggestions and correct them from the hooks themselves. With no
        research, says so and lists nothing as proven.

    hooks.py score <hooks.txt | -> [--topic "words"] [--facts FILE] [--json]
        Scores candidate hooks out of 100 and ranks them. One hook per block, blocks
        separated by a blank line; in a block, a line starting "On screen:" is that hook's
        on-screen text, a line starting "Formula:" names its formula, a note about the hook
        ("Sendable to:", "Why:", "Evidence:", "Notes:") is left out, the rest is spoken.
        --facts is a plain-text file of the creator's own facts (what happened, their
        numbers, names, times, quotes, results). A number earns points only when it is in
        that file; a number that isn't is flagged and the hook marked WEAK. Without
        --facts, numbers earn nothing and the output says so: the score never rewards a
        number nobody has vouched for. A {{placeholder}} earns the points the real fact
        would, and the hook is marked NOT READY until it is filled.
        --topic gives the idea's words. Besides checking they arrive early, they are
        discounted from specificity, with the platform and tool names the whole niche
        uses ("Claude", "Code", "ChatGPT", "Instagram"): saying the topic is not a detail.

What the score is, and isn't. It is a filter: it catches hooks that are weak for reasons
text can show (a greeting or preamble, nothing concrete, too long to say in about three
seconds, nothing the viewer can picture, the topic arriving late). It is not a predictor:
among hooks that pass, a higher score does not mean more views or shares, and two good
hooks a few points apart are a tie. Specificity (a number, a name, something checkable)
weighs most because it is the one text signal that has held up in tests of hooks against
results, and it only counts when the detail is the creator's own: their numbers, names,
times, quotes or results, not the words of the topic itself. Choosing between hooks that
pass is for the evidence and the person.

Standard library only. No network.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORMULAS = HERE.parent / "references" / "hooks.json"
sys.path.insert(0, str(HERE))
import reel  # noqa: E402  same skill, same folder: the shared spoken-word count

SPEAK_WPS = 2.5          # spoken words per second
HOOK_SECONDS = reel.HOOK_WINDOW   # 0:03, what the viewer has heard when most decide to stay
# Length grading only: a hook of up to 8 counted words is "said in about 3 s". What counts as
# heard in the first 3 seconds (a detail, the topic) is heard_by_window(), the 0:03 window
# reel.py check and ig-script's timeline.py use.
EARLY_WORDS = int(SPEAK_WPS * HOOK_SECONDS) + 1
READ_SECONDS = 2.5       # time to read the on-screen hook before the voice moves on
READ_WPS = 3.0

# "one" and "once" are left out: they are mostly an article ("one free skill"), not a figure.
NUMBER_WORDS = {
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
    "twelve", "fifteen", "twenty", "thirty", "forty", "fifty", "hundred", "thousand", "million",
    "billion", "half", "dozen", "once", "twice",
}
NUMBER_VALUES = {
    "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20",
    "thirty": "30", "forty": "40", "fifty": "50", "hundred": "100", "thousand": "1000",
    "million": "1000000", "billion": "1000000000", "dozen": "12", "twice": "2", "half": "0.5",
}
# A time of day or week is checkable on its own. A unit ("hours", "dollars") is not: it
# only says there is a number somewhere, so it earns nothing without one.
TIMES = {
    "am", "pm", "overnight", "midnight", "tonight", "yesterday", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday",
}
# Names the whole niche says. On their own they are the topic, not a detail.
NICHE_NAMES = {
    "ai", "chatgpt", "gpt", "claude", "code", "gemini", "copilot", "openai", "anthropic", "codex",
    "cursor", "google", "apple", "meta", "instagram", "insta", "ig", "reels", "reel", "tiktok",
    "youtube", "shorts", "facebook", "linkedin", "twitter", "threads", "iphone", "android", "mac",
    "macbook", "windows", "excel", "notion", "canva", "zapier", "midjourney", "perplexity",
}
NOT_NAMES = {"I", "I'm", "I've", "I'll", "I'd", "AI", "OK", "If", "So", "This", "The", "My",
             "You", "Your", "It", "And", "But", "Then", "When", "How", "What", "Why", "Stop"}
WARMUPS = [
    r"^(hey|hi|hello|yo|what'?s up)\b", r"\bwelcome (back|to)\b", r"\bin (this|today'?s) (video|reel)\b",
    r"^so,? today\b", r"\btoday i('m| am| want| wanna)\b", r"\bi want(ed)? to (talk|share|show you)\b",
    r"\blet me (tell|show) you\b", r"\bhere'?s the thing\b", r"^(okay|ok|alright|so)\s*,?\s*(so|guys)\b",
    r"\bguys\b", r"\bbefore (we|i) (start|begin)\b", r"\bdon'?t forget to (like|follow|subscribe)\b",
    r"\bquick (video|one)\b",
]
# Words for things a viewer can see: objects, places, people, screens. Not exhaustive; a hook
# with a number or a name usually gives a picture anyway.
PICTURE = {
    "phone", "laptop", "screen", "app", "car", "kitchen", "fridge", "oven", "desk", "office",
    "gym", "door", "camera", "photo", "video", "reel", "reels", "email", "inbox", "calendar",
    "receipt", "receipts", "bill", "card", "wallet", "bed", "train", "plane", "flight", "airport",
    "store", "shop", "restaurant", "menu", "street", "house", "room", "baby", "kid", "kids",
    "dog", "cat", "boss", "client", "customer", "friend", "mom", "dad", "neighbour", "neighbor",
    "doctor", "teacher", "team", "meeting", "race", "game", "match", "session", "qualifying",
    "sneakers", "earbuds", "keys", "ring", "parcel", "package", "website", "spreadsheet",
    "chart", "flag", "notification", "text", "message", "map", "tv", "watch", "macbook", "browser",
    "invoice", "invoices", "bakery", "cafe", "salon", "truck", "van", "warehouse", "counter", "till",
}
STOPWORDS = {"and", "the", "for", "with", "how", "you", "your", "that", "this", "from", "into",
             "about", "what", "when", "can", "are", "was", "has", "have", "its", "it's", "me", "my"}
ACTION_START = re.compile(r"^(i|my|we|our|this (guy|girl|woman|man|person)|she|he|they)\b", re.I)
PAST_VERB = re.compile(r"\b\w+ed\b|\b(got|ran|made|sent|told|found|lost|left|took|gave|saw|built|"
                       r"bought|sold|went|came|broke|caught|kept|wrote|read|paid)\b", re.I)


# ---------------------------------------------------------------- formulas

def load_formulas(path=FORMULAS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["formulas"]


def cmd_list(a):
    fs = load_formulas()
    if a.json:
        print(json.dumps(fs, indent=2, ensure_ascii=False))
        return 0
    print(f"{len(fs)} hook formulas (source: research = seen in top Reels; craft = general practice)\n")
    for i, f in enumerate(fs, 1):
        print(f"{i:>2}. {f['name']} [{f['source']}]  ({f['id']})")
        print(f"    Move:      {f['move']}")
        print(f"    Template:  {f['template']}")
        print(f"    Example:   {f['example']}")
        print(f"    On screen: {f['on_screen']}")
        print(f"    Use when:  {f['use_when']}")
    return 0


NO_HOOK = re.compile(r"(?i)^(no captions?|no caption track|none|n/?a|no text( hook)?|no hook|nothing|\?|-+|—)$")


def clean_hook(text):
    """A hook as ig-research's table writes it, reduced to the words themselves. Drops
    notes in trailing brackets ("(typed headline)", "(no track; frames)"), keeps the words
    in [square brackets] without the brackets, takes the quoted words when a note sits
    beside them ('"100 fake customers" banner'), and returns "" for "no captions", "None",
    "?" and the like, so a missing hook never matches and never hides the other one."""
    t = (text or "").strip().replace("’", "'")
    while True:
        u = re.sub(r"\s*\([^()]*\)\s*$", "", t)
        if u == t:
            break
        t = u
    m = re.match(r'^["“]([^"”]+)["”]', t)
    if m:
        t = m.group(1)
    t = re.sub(r"\[([^\]]*)\]", r"\1", t)
    t = re.sub(r"(\.\.\.|…)$", "", t).strip().strip('"“”').strip()
    return "" if not t or NO_HOOK.match(t) else t


def match_formulas(text, formulas):
    """Ids of the formulas whose cues appear in a hook's text. Each cue needs the formula's
    defining feature, so a hook that fits none matches none: better no name than a wrong one."""
    t = clean_hook(text).lower()
    if not t:
        return []
    return [f["id"] for f in formulas if any(re.search(c, t) for c in f.get("cues", []))]


def pick(ev, formulas, recent_days=60):
    by_id = {f["id"]: {"id": f["id"], "name": f["name"], "winners": [], "weight": 0.0} for f in formulas}
    unmatched = []
    for w in ev["winners"]:
        said, shown = match_formulas(w.get("spoken_hook"), formulas), match_formulas(w.get("text_hook"), formulas)
        rate = w.get("shares_per_1k_views") or 0.0
        recent = w.get("age_days") is not None and w["age_days"] <= recent_days
        label = f"@{w.get('account') or '?'} ({rate:.1f}/1K{', recent' if recent else ''})"
        if not (said or shown):
            unmatched.append({"winner": label, "spoken_hook": clean_hook(w.get("spoken_hook")) or "(none)",
                              "text_hook": clean_hook(w.get("text_hook")) or "(none)"})
        for i in said + [x for x in shown if x not in said]:
            # Say where the match came from when it was the on-screen hook alone.
            by_id[i]["winners"].append(label if i in said else f"{label} on screen")
            by_id[i]["weight"] += rate * (1.5 if recent else 1.0)
    ranked = sorted((v for v in by_id.values() if v["winners"]), key=lambda v: -v["weight"])
    for v in ranked:
        v["weight"] = round(v["weight"], 1)
    return {"backed": ranked, "unmatched": unmatched}


def cmd_pick(a):
    csv_path, hooks_path = reel.research_files(a.target, a.idea)
    if not (csv_path or hooks_path):
        print("No research found: none of the 26 formulas is backed by evidence for this idea. "
              "Pick three different moves from `hooks.py list` and label the hooks unproven, "
              "or run ig-research first.")
        return 0
    ev = reel.evidence(csv_path, hooks_path, a.top)
    with_hooks = [w for w in ev["winners"] if clean_hook(w.get("spoken_hook")) or clean_hook(w.get("text_hook"))]
    if not with_hooks:
        print("Research found, but no hooks read yet: run ig-research's hooks step first.")
        return 0
    ev["winners"] = with_hooks
    res = pick(ev, load_formulas())
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    print(f"Formulas the winners used, weighted by shares per 1,000 views (recent x1.5), from {len(with_hooks)} winners:\n")
    for v in res["backed"]:
        print(f"  {v['weight']:>6}  {v['name']} ({v['id']}): {', '.join(v['winners'])}")
    if res["unmatched"]:
        print("\nNo formula matched, spoken or on screen (name their move yourself, or map them by hand):")
        for u in res["unmatched"]:
            print(f"  {u['winner']}: said: {u['spoken_hook']} | on screen: {u['text_hook']}")
    print("\nThe match is a rough pattern match. Check each against the hooks before relying on it.")
    return 0


# ---------------------------------------------------------------- score

def words(text):
    """Tokens of a hook, a {{placeholder}} being one; the same rule as reel.py's."""
    return reel.words(text)


def heard_by_window(text, seconds=HOOK_SECONDS, wps=SPEAK_WPS):
    """How many of words(text) are heard in full by `seconds`: the shared rule of
    reel.words_heard_by (a figure counts as it is said, so "$18,000" takes 3 words of time)."""
    n, acc, limit = 0, 0, seconds * wps + 1e-9
    for _, k in reel.spoken_words(text):
        if acc + k > limit:
            break
        acc += k
        n += 1
    return n


def _bare(w):
    return re.sub(r"^[^\w$]+|[^\w%]+$", "", w)


def _num_key(tok):
    """A figure reduced so "$10,219", "10219" and "10,219" compare equal, and "ten" == "10"."""
    t = tok.lower().replace(",", "")
    if t in NUMBER_VALUES:
        return NUMBER_VALUES[t]
    m = re.search(r"\d+(?:\.\d+)?(?:k|m|bn)?", t)
    return m.group(0) if m else t


def load_facts(text):
    """What the creator vouched for: their figures, and every word, for names and quotes."""
    toks = re.findall(r"[$€£]?\d[\d,.]*(?:k|m|bn)?%?|[A-Za-z][\w'’-]*", text or "")
    nums = {_num_key(t) for t in toks if re.search(r"\d", t) or t.lower() in NUMBER_VALUES}
    # Names: capitalised words that don't start a sentence, as in a hook.
    names = {m.group(0).lower().replace("’", "'")
             for m in re.finditer(r"[A-Z][\w'’-]*", text or "")
             if m.start() and not re.search(r"(^|[.!?:\n])\W*$", (text or "")[:m.start()])}
    return {"numbers": nums, "words": {t.lower().replace("’", "'") for t in toks}, "names": names,
            "text": " ".join(re.sub(r"[^\w\s]", " ", (text or "").lower()).split())}


def topic_words(topic):
    return {w for w in re.split(r"[^a-z0-9]+", (topic or "").lower()) if len(w) > 1 and w not in STOPWORDS}


def specifics(text, topic=None, facts=None):
    """The details in a hook a viewer could check, each with whether it earns points.

    kind: number, time, name, quote or slot (a {{placeholder}}).
    status: "counts"; "slot" (counts, but must be filled); "topic" (the topic's own word or a
    name the whole niche uses: not a detail); "unchecked" (a number with no --facts: earns
    nothing); "not in facts" (with --facts, not in them: earns nothing, and a number makes
    the hook WEAK)."""
    found = []
    ws = words(text)
    # The same tokens with their punctuation, to see where a sentence ended.
    raw = [t for t in reel.SPOKEN_TOKEN.findall(text or "")
           if reel.PLACEHOLDER.fullmatch(t) or any(c.isalnum() for c in t.strip(reel.EDGE_PUNCT))]
    tw = topic_words(topic) | NICHE_NAMES
    for i, w in enumerate(ws):
        if reel.PLACEHOLDER.fullmatch(w):
            found.append({"i": i, "text": w, "kind": "slot", "status": "slot"})
            continue
        b = _bare(w)
        lb = b.lower().replace("’", "'")
        if re.search(r"\d", b) or lb in NUMBER_WORDS:
            if facts is None:
                status = "unchecked"
            else:
                status = "counts" if _num_key(b) in facts["numbers"] else "not in facts"
            found.append({"i": i, "text": b, "kind": "number", "status": status})
        elif lb in TIMES:
            found.append({"i": i, "text": b, "kind": "time", "status": "counts"})
        elif b[:1].isupper() and b not in NOT_NAMES and (
                (i > 0 and not re.search(r"[.!?:]['\"\u2019\u201d)]*$", raw[i - 1]))
                or (facts is not None and lb in facts["names"])):
            if lb in tw or lb.rstrip("s") in tw:
                status = "topic"
            elif facts is not None and lb not in facts["words"]:
                status = "not in facts"
            else:
                status = "counts"
            found.append({"i": i, "text": b, "kind": "name", "status": status})
    for m in re.finditer(r"[\"“][^\"”]{3,}[\"”]", text or ""):
        q = " ".join(re.sub(r"[^\w\s]", " ", m.group(0).lower()).split())
        status = "counts" if facts is None or q in facts["text"] else "not in facts"
        found.append({"i": len(words((text or "")[: m.start()])), "text": m.group(0), "kind": "quote",
                      "status": status})
    return found


def score_hook(spoken, on_screen="", topic=None, facts=None):
    """Score one hook out of 100 and say why. A filter, not a forecast: see the module notes.
    facts: load_facts() of the creator's own facts, or None if none were given."""
    ws = words(spoken)
    lower = (spoken or "").lower().replace("’", "'")
    checks, weak, warnings = [], [], []

    found = specifics(spoken, topic, facts)
    sp = [x for x in found if x["status"] in ("counts", "slot")]
    n_early = heard_by_window(spoken)   # words heard by 0:03, as reel.py check counts them
    early = [x for x in sp if x["i"] < n_early]
    if early:
        pts = 40 if len(sp) >= 2 else 32
        note = "the creator's own detail in the first 3 seconds: " + ", ".join(x["text"] for x in sp[:4])
    elif sp:
        pts, note = 20, "the creator's own detail, but only after the first 3 seconds: " + ", ".join(x["text"] for x in sp[:4])
    else:
        pts, note = 0, "nothing of the creator's own: no number, name, time or quote of theirs"
    discounted = [x["text"] for x in found if x["status"] == "topic"]
    if discounted:
        note += "; not counted, the topic's own words: " + ", ".join(dict.fromkeys(discounted))
    checks.append({"check": "specific", "points": pts, "of": 40, "note": note})

    invented = [x["text"] for x in found if x["kind"] == "number" and x["status"] == "not in facts"]
    if invented:
        weak.append("number not in your facts: " + ", ".join(invented))
    unchecked = [x["text"] for x in found if x["status"] == "unchecked"]
    if unchecked:
        warnings.append("number not checked, so it earns nothing: " + ", ".join(unchecked)
                        + ". Pass --facts with the creator's real numbers, or use a {{placeholder}}")
    for x in found:
        if x["kind"] != "number" and x["status"] == "not in facts":
            warnings.append(f"{x['kind']} not in your facts, so it earns nothing: {x['text']}. Is it true?")

    warm = [p for p in WARMUPS if re.search(p, lower)]
    if warm:
        checks.append({"check": "no warm-up", "points": 0, "of": 15,
                       "note": "opens with a greeting or preamble instead of the video"})
        weak.append("warm-up")
    else:
        checks.append({"check": "no warm-up", "points": 15, "of": 15, "note": "starts on the content"})

    n = reel.spoken_count(spoken)
    secs = n / SPEAK_WPS
    if n <= EARLY_WORDS:
        pts = 20
    elif n <= 13:
        pts = 14
    elif n <= 18:
        pts = 7
    else:
        pts = 0
        weak.append("too long")
    checks.append({"check": "said in about 3 s", "points": pts, "of": 20,
                   "note": f"{n} words, about {secs:.1f} s"})

    bare = {_bare(w).lower() for w in ws}
    pic = sorted(bare & PICTURE)
    action = bool(ACTION_START.search(spoken.strip().strip('"“')) and PAST_VERB.search(spoken))
    if pic or action or sp:
        why = []
        if pic:
            why.append("something to see: " + ", ".join(pic[:3]))
        if action:
            why.append("someone doing something")
        if not why:
            why.append("a number or name to hold on to")
        checks.append({"check": "something to picture", "points": 15, "of": 15, "note": "; ".join(why)})
    else:
        checks.append({"check": "something to picture", "points": 0, "of": 15,
                       "note": "no object, place, person or action a viewer could see"})

    if topic:
        tw = topic_words(topic)
        first = {re.sub(r"[^a-z0-9]", "", w.lower()) for w in ws[:n_early]}
        hit = sorted(tw & first) or sorted(t for t in tw if any(f.startswith(t[:5]) for f in first if len(t) > 4))
        heard = " ".join(ws[:n_early])
        checks.append({"check": "topic early", "points": 10 if hit else 0, "of": 10,
                       "note": (f"topic in the first 3 seconds (heard by 0:03: \"{heard}\"): " + ", ".join(hit))
                       if hit else f"none of the topic's words in the first 3 seconds (heard by 0:03: \"{heard}\")"})

    if not sp and not (pic or action):
        weak.append("nothing concrete")

    total = sum(c["points"] for c in checks)
    out_of = sum(c["of"] for c in checks)
    to_fill = [x["text"] for x in found if x["status"] == "slot"]
    result = {"spoken": spoken, "score": round(100 * total / out_of), "checks": checks,
              "weak": weak, "warnings": warnings, "to_fill": to_fill}
    if on_screen and on_screen.strip().lower() != "none":
        ow = words(on_screen)
        if len(ow) / READ_WPS > READ_SECONDS:
            warnings.append(f"on screen: {len(ow)} words, more than can be read in about {READ_SECONDS:g} s")
        if re.sub(r"\W+", " ", on_screen.lower()).strip() == re.sub(r"\W+", " ", lower).strip():
            warnings.append("on screen repeats the spoken line word for word")
        screen = specifics(on_screen, topic, facts)
        bad = [x["text"] for x in screen if x["kind"] == "number" and x["status"] == "not in facts"]
        if bad:
            weak.append("on-screen number not in your facts: " + ", ".join(bad))
        to_fill += [x["text"] for x in screen if x["status"] == "slot" and x["text"] not in to_fill]
    elif not on_screen:
        warnings.append("no on-screen line given")
    return result


# Notes written beside a hook (SKILL.md asks for "Sendable to:"), never part of what is said.
NOTE_LINE = re.compile(r"(?i)^(sendable|shareable|send(?:s|able)?(?: it)?|shares?|who(?:'d| would) send(?: it)?"
                       r"|why|notes?|angle|evidence|winners?|backed by|source|score)(?:\s+(?:to|with))?\s*:")


def parse_candidates(text):
    blocks = [b for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    out = []
    for b in blocks:
        spoken, screen, formula = [], "", ""
        for line in b.splitlines():
            s = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
            m = re.match(r"(?i)^(on[- ]?screen|text)\s*:\s*(.*)$", s)
            f = re.match(r"(?i)^formula\s*:\s*(.*)$", s)
            sp = re.match(r"(?i)^(spoken|said)\s*:\s*(.*)$", s)
            if m:
                screen = reel.unquote(m.group(2))
            elif f:
                formula = f.group(1).strip()
            elif NOTE_LINE.match(s):
                continue
            elif sp:
                spoken.append(reel.unquote(sp.group(2)))
            elif s:
                spoken.append(reel.unquote(s))
        if spoken:
            out.append({"spoken": " ".join(spoken), "on_screen": screen, "formula": formula})
    return out


def cmd_score(a):
    try:
        text = sys.stdin.read() if a.hooks == "-" else Path(a.hooks).read_text(encoding="utf-8")
    except OSError as e:
        print(f"cannot read hooks: {e}", file=sys.stderr)
        return 2
    cands = parse_candidates(text)
    if not cands:
        print("no hooks found", file=sys.stderr)
        return 2
    facts = None
    if a.facts:
        try:
            facts = load_facts(Path(a.facts).read_text(encoding="utf-8"))
        except OSError as e:
            print(f"cannot read facts: {e}", file=sys.stderr)
            return 2
    results = []
    for c in cands:
        r = score_hook(c["spoken"], c["on_screen"], a.topic, facts)
        r["formula"], r["on_screen"] = c["formula"], c["on_screen"]
        results.append(r)
    ranked = sorted(range(len(results)), key=lambda i: (bool(results[i]["weak"]), -results[i]["score"]))
    if a.json:
        print(json.dumps([results[i] for i in ranked], indent=2, ensure_ascii=False))
        return 0
    print("Hook filter: catches weak hooks, does not predict which good one wins. Within a few points is a tie.")
    print("Facts: " + (a.facts if facts else "none given, so no number earns points (pass --facts)") + "\n")
    for rank, i in enumerate(ranked, 1):
        r = results[i]
        tag = "WEAK (" + ", ".join(r["weak"]) + ")" if r["weak"] else "passes"
        print(f"{rank}. {r['score']}/100  {tag}" + (f"  · {r['formula']}" if r["formula"] else ""))
        print(f"   Spoken:    {r['spoken']}")
        print(f"   On screen: {r['on_screen'] or '(none)'}")
        for c in r["checks"]:
            print(f"     {c['points']:>2}/{c['of']:<2} {c['check']}: {c['note']}")
        for w in r["warnings"]:
            print(f"     WARN {w}")
        if r["to_fill"]:
            print(f"     NOT READY until the creator fills: {', '.join(dict.fromkeys(r['to_fill']))}")
        print()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Hook formulas, research-backed picks and a weak-hook filter.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list", help="the 26 formulas")
    l.add_argument("--json", action="store_true")
    l.set_defaults(fn=cmd_list)
    p = sub.add_parser("pick", help="which formulas the research's winners used")
    p.add_argument("target", help="a folder, a research CSV, or a -hooks.md file")
    p.add_argument("--idea")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_pick)
    s = sub.add_parser("score", help="score and rank candidate hooks")
    s.add_argument("hooks", help="file with one hook per block, or -")
    s.add_argument("--topic", help="the idea's key words: checked to arrive in the first 3 seconds, "
                   "and not counted as a detail")
    s.add_argument("--facts", help="plain-text file of the creator's own facts; only numbers in it earn points")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_score)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
