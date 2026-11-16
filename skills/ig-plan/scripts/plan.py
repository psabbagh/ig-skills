#!/usr/bin/env python3
"""Work out the evidence for a creator's week on Instagram from their own data.

    plan.py [--research PATH ...] [--log FILE] [--me HANDLE] [--posts N] [--start DATE]
            [--active FILE] [--recent-days 28] [--creators 8] [--today DATE] [--json]
            [--remember] [--config FILE]

--research: research CSVs written by ig-research (research-<idea>-<date>.csv), or folders
to search for them (recursively). When an idea was researched more than once, the newest
file is used. Default: the folders saved with --remember, else the working folder.
--log: the posting log kept by postlog.py (default: IG_PLAN_LOG, else posted.csv in the
config folder: $XDG_CONFIG_HOME/ig-plan, else ~/.config/ig-plan).
--me: the creator's own handle, left out of the accounts to engage with.
--posts N: also draft N slots for the seven days from --start (default: today, or the next
day with nothing logged as posted).
--active FILE: the followers' most active times from Instagram's insights, as text.
--remember: save --research folders, --me and --active to the settings file for next time.
--config FILE: the settings file (default: config.json in the config folder).

What it works out, all from the files, nothing invented:
  1. Research ideas ranked the way ig-research ranks Reels (Instagram's stated order: sends
     per reach, then likes, then watch time). Each idea scores the median shares per 1,000
     views of its top 5 ranked Reels, so one outlier can't carry it. A Reel is ranked when
     it has 10K+ views and a share count and its likes + comments are at least 2% of its
     views; views are Instagram-only plays where known. Same constants as ig-research.
  2. Which of those ideas the creator already covered (log rows whose `idea` is the research
     slug, or whose topic shares most of its words), and which they covered recently; and
     which angles make a promise the creator already posted (by the log's topics and hooks).
  3. The creator's own numbers: shares per 1,000 reached (or viewed) by format and by post,
     their median, and their winners. Posts under 7 days old are still climbing: counted as
     covered, left out of the averages.
  4. Their best days and time bands from their own views (each post's views over their
     median), named only with 8+ settled posts and 2+ posts in the bucket; else their
     followers' active times (--active); else a published default, labelled as a default
     (references/default-times.md).
  5. Accounts worth engaging with: the creators behind the top ranked on-topic Reels of the
     ideas, the ones that recur across ideas first. Reels ig-research's hooks file explicitly
     marked off topic are left out of everything; a Reel it only skipped or didn't read is not.
  6. The distinct angles in each idea's winners (one per creator and per promise: Reels that
     promise the same thing in other words are one angle), so one research run can fill
     several slots, and how many slots the research fills.
  7. With --posts, a draft week: the best uncovered ideas and angles on the best days, each
     with its evidence and where it came from. A starting point for the creator's judgement,
     not a schedule.

Exit 3 when there is neither research nor a log with posts in it: it prints what it needs.
Standard library only. Never posts or schedules anything.
"""
import argparse
import csv
import datetime
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import postlog  # noqa: E402

RANK_MIN_VIEWS = 10_000   # as in ig-research: below this a share rate is noise
LOW_REACTIONS_PCT = 2.0   # as in ig-research: likes + comments under 2% of views -> maybe bought
TOP_PER_IDEA = 5          # an idea's score is the median rate of its top 5 ranked Reels
THIN = 3                  # fewer ranked Reels than this and the idea's evidence is thin
WAVE_DAYS = 90            # newest ranked Reel older than this: the wave may have passed
CLIMBING_DAYS = 7         # own posts younger than this: views not settled
MIN_TIMING_POSTS = 8      # settled posts with views needed before naming best days/times
MIN_BUCKET = 2            # posts needed in a day or time band to rank it
WINNER_X = 1.5            # an own post at 1.5x the creator's median share rate is a winner
STALE_RESEARCH_DAYS = 30  # research older than this gets a note
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
BANDS = [("06-10", 6, 10), ("10-13", 10, 13), ("13-17", 13, 17), ("17-21", 17, 21)]
NIGHT = "21-06"
# Not the creator's evidence: a published default, used until their own numbers or their
# followers' active times can say. Source and caveats: references/default-times.md.
DEFAULT_DAY_ORDER = [2, 3, 1, 6, 0, 4, 5]  # Wed, Thu, Tue (best), Sun, Mon (moderate), Fri, Sat (low)
DEFAULT_TIMES = {0: "19:00", 1: "19:00", 2: "12:00", 3: "09:00", 4: "22:00", 5: "21:00", 6: "21:00"}
DEFAULT_SOURCE = ("default, not your data: Buffer's study of 9.6M Instagram posts (2024-2025), "
                  "best days Wed, Thu, Tue, each at that day's top hour (references/default-times.md)")
ACTIVE_HOWTO = ("Your own answer is in the Instagram app: professional dashboard > Total followers > "
                "Most active times (Hours and Days). Write what it shows into a text file, e.g. "
                "\"Tue Thu Sun\" and \"6p 9p\" (or paste day/hour counts), and pass --active FILE "
                "(with --remember to keep it)")
CODE_RE = re.compile(r"(?:instagram\.com/(?:[\w.]+/)?(?:reels?|p)/|tiktok\.com/@[\w.]+/video/)([A-Za-z0-9_-]+)")
# Only an explicit off-topic or drift mark leaves a Reel out. "Skipped" alone is not one:
# ig-research also skips Reels it didn't read (past its top 8) or marked ⚠ low reactions.
OFF_RE = re.compile(r"off[ -]?topic|not on[ -]topic|\bdrift(?:ed|s|ing)?\b|\bunrelated\b|"
                    r"different (?:idea|topic)|not (?:about )?(?:this|the) idea", re.I)
NOT_OFF_RE = re.compile(r"not read|unread|low reactions|⚠|\btop \d+ only\b|bought|"
                        r"didn'?t read|no caption", re.I)
REF_RE = re.compile(r"#\d|@[\w.]|instagram\.com/|tiktok\.com/")
ANGLES_FROM = 10          # an idea's angles come from its top 10 on-topic ranked Reels
STOP = set("""a all an and any anything are as at be best by can every for from get got how i
if in into is it its just make my new no not now of on one or our out so start stop that the
their them thing this to top turn up use using was way we what when why with you your yours
vs via""".split())
COMMON_SHARE = 0.3        # a word in 30%+ of the idea names (3+ of 5+) names the niche, not a topic
COMMON = set()            # filled by main() from the creator's own idea names
NAME_RE = re.compile(r"^research-(.+)-(\d{4}-\d{2}-\d{2})\.csv$")


def num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s:
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f.is_integer() else f


def per_1k(n, base):
    return round(1000 * n / base, 2) if n is not None and base else None


def short(n):
    if n is None:
        return "–"
    for div, suf in ((1_000_000, "M"), (1_000, "K")):
        if n >= div:
            return f"{n / div:.1f}".rstrip("0").rstrip(".") + suf
    return str(int(n))


def stem(w):
    """Plural to singular, roughly: videos -> video, watches -> watch, skills -> skill."""
    if len(w) > 4 and w.endswith(("ches", "shes", "sses", "xes")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def words(text, ignore=()):
    out = set()
    for w in re.split(r"[^a-z0-9]+", (text or "").lower()):
        if w and w not in STOP and (len(w) >= 3 or w.isdigit()):
            w = stem(w)
            if w not in ignore:
                out.add(w)
    return out


def common_words(titles):
    """Words that name the creator's niche (in 30%+ of their idea names) rather than a topic:
    "claude" for someone whose every idea is about Claude. Needs 5+ ideas to say."""
    if len(titles) < 5:
        return set()
    counts = {}
    for t in titles:
        for w in words(t):
            counts[w] = counts.get(w, 0) + 1
    return {w for w, n in counts.items() if n >= 3 and n / len(titles) >= COMMON_SHARE}


def same_topic(a, b):
    """Two topics are the same when they share 2+ content words making up 60%+ of the shorter
    and 40%+ of both together. Words in COMMON (the creator's niche) don't count. The second
    test keeps a short name from matching a long one on two generic words ("find holes in your
    business" is not "find clients for your business with a sales expert")."""
    wa, wb = words(a, COMMON), words(b, COMMON)
    if not wa or not wb:
        return False
    common = len(wa & wb)
    return common >= 2 and common / min(len(wa), len(wb)) >= 0.6 and common / len(wa | wb) >= 0.4


def date_of(text):
    try:
        return datetime.date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


# ---------- research ----------

def find_research(paths):
    """research-<idea>-<date>.csv files under paths; the newest per idea."""
    found = []
    for p in paths:
        p = Path(p).expanduser()
        if p.is_file():
            found.append(p)
        elif p.is_dir():
            found.extend(sorted(p.rglob("research-*.csv")))
    best = {}
    for f in found:
        m = NAME_RE.match(f.name)
        if not m:
            continue
        slug, d = m.group(1), m.group(2)
        if slug not in best or d > best[slug][1]:
            best[slug] = (f, d)
    return [(slug, f, d) for slug, (f, d) in sorted(best.items())]


def reel_row(r, today):
    platform = r.get("platform") or "Instagram"
    views, ig = num(r.get("views")), num(r.get("ig_only_views"))
    base = ig if platform == "Instagram" and ig else views
    likes, comments, shares = num(r.get("likes")), num(r.get("comments")), num(r.get("shares"))
    react = round(100 * (likes + (comments or 0)) / base, 2) if base and likes is not None else None
    low = bool(base and base >= RANK_MIN_VIEWS and react is not None and react < LOW_REACTIONS_PCT)
    spk = per_1k(shares, base)
    posted = date_of(r.get("posted"))
    url = r.get("url") or ""
    m = CODE_RE.search(url)
    return {
        "platform": platform, "account": (r.get("account") or "").strip().lstrip("@"), "url": url,
        "code": m.group(1) if m else url,
        "views": views, "base": base, "likes": likes, "shares": shares,
        "shares_per_1k": spk, "likes_per_1k": per_1k(likes, base), "low_reactions": low,
        "posted": posted.isoformat() if posted else "",
        "age_days": (today - posted).days if posted else None,
        "ranked": bool(base and base >= RANK_MIN_VIEWS and spk is not None and not low),
        "caption": (r.get("caption") or "").replace("\n", " ")[:200],
        "off_topic": False, "hook": None,
    }


def split_cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def off_clauses(line):
    """The parts of a hooks-file line that mark Reels off topic. A line is split into sentences
    and each sentence into clauses at ";". A clause counts when it says off topic (or drift)
    itself, or when its sentence opens with such a mark ("Off topic: #3 @a; #5 @b") and the
    clause gives no other reason. A clause saying the Reel wasn't read, or was skipped for low
    reactions, never counts: "#9 @x not read (top 8 only)" is not "off topic"."""
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z#@])", line):
        clauses = [c for c in sentence.split(";") if c.strip()]
        if not clauses:
            continue
        m = REF_RE.search(clauses[0])
        lead = clauses[0][: m.start()] if m else clauses[0]
        lead_off = bool(OFF_RE.search(lead)) and not NOT_OFF_RE.search(lead)
        for c in clauses:
            own = c.replace(lead, "", 1) if c is clauses[0] else c
            if NOT_OFF_RE.search(own):
                continue
            if OFF_RE.search(own) or lead_off:
                out.append(own)
    return out


def off_codes(clause, rows):
    """The Reels a clause names: by link, by "#N" (its row in the report table) or "@creator"."""
    out = set(CODE_RE.findall(clause))
    placed = set()
    for nums, handle in re.findall(r"#(\d+(?:\s*(?:,|and|&)\s*#?\d+)*)(?:\s*\(?@([\w.]*\w))?", clause):
        ks = [int(k) for k in re.findall(r"\d+", nums)]
        for k in ks:
            if 1 <= k <= len(rows):
                r = rows[k - 1]
                if not handle or len(ks) > 1 or r["account"].lower() == handle.lower():
                    out.add(r["code"])
                    placed.add(r["account"].lower())
    for handle in re.findall(r"(?<![\w#/])@([\w.]*\w)", clause):
        if handle.lower() not in placed:
            out.update(r["code"] for r in rows if r["account"].lower() == handle.lower())
    return out


def read_hooks(path, rows):
    """What ig-research's hooks step decided about the idea's Reels, from
    research-<idea>-<date>-hooks.md. Reels in its table were judged on topic (with their spoken
    hook, text hook and, when present, any other column such as why it worked). Reels named on
    a line that says off topic or skipped were left out of the idea: by link, by "#N" (the
    Reel's position in the report table, which is the CSV's row order) and by "@creator".
    Returns ({code: hook columns}, {codes left out})."""
    on, off, header = {}, set(), None
    why, code, in_why = {}, None, False
    for line in path.read_text(encoding="utf-8").splitlines():
        st = line.strip()
        if st.startswith("## "):
            in_why = st.lower().startswith("## why they worked")
            continue
        if in_why:  # ig-research's breakdown: one block per Reel, its link on its own line
            found = CODE_RE.findall(st)
            if st.startswith("### ") or (found and not st.startswith("-")):
                code = found[0] if found else None
                continue
            m = re.match(r"-\s*\*\*(structure|payoff)\*\*\s*(?:\([^)]*\))?\s*:\s*(.+)", st, re.I)
            if code and m and "(not read)" not in st:
                why.setdefault(code, []).append(f"{m.group(1).lower()}: {m.group(2).strip()}")
            continue
        if st.startswith("|"):
            cells = split_cells(st)
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            codes = [m for c in cells for m in CODE_RE.findall(c)]
            if not codes:
                header = [c.lower() for c in cells]
                continue
            rec = {}
            for h, c in zip(header or [], cells):
                if "spoken" in h:
                    rec["spoken"] = c
                elif "text hook" in h or h == "text":
                    rec["text"] = c
                elif "send" in h:
                    rec["send_to"] = c
                elif "why" in h:
                    rec["why"] = c
            on.setdefault(codes[0], rec)
        elif OFF_RE.search(st):
            for clause in off_clauses(st):
                off.update(off_codes(clause, rows))
    for c, parts in why.items():
        if c in on and not on[c].get("why"):
            on[c]["why"] = "; ".join(parts)
    return on, off - set(on)


def strip_md(text):
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text or "")
    t = re.sub(r"[\[\]\"“”*_`]", "", t)
    return " ".join(t.split())


CTA_RE = re.compile(r"\b(comment|dm me|type)\b\s+\S+(\s+(and|&)\s+i('| wi)?ll\s+(send|dm)[^.!?]*)?", re.I)


def angle_of(r):
    """The angle a winning Reel takes, in its own words: its text hook, else its spoken hook
    (from the hooks file), else the first sentence of its caption without the comment-keyword
    call to action."""
    h = r.get("hook") or {}
    text = strip_md(h.get("text", ""))
    spoken = strip_md(h.get("spoken", ""))
    if text.lower().startswith(("none", "no text", "–", "-")) or not text:
        text = ""
    if spoken.lower().startswith(("no caption", "none", "–")):
        spoken = ""
    if text or spoken:
        show = text if text and len(text.split()) >= 3 else (spoken or text)
        return show, f"{text} {spoken}"
    cap = CTA_RE.sub(" ", re.sub(r"[^\w\s'.,:!?&+-]", " ", r.get("caption") or ""))
    parts = [p.strip() for p in re.split(r"[.!?\n]+|\s{2,}", cap) if len(p.split()) >= 3]
    first = parts[0] if parts else cap.strip()
    # Research CSVs keep only the start of a caption: a sentence running into the cut is marked.
    if first and parts and first == parts[-1] and not cap.rstrip().endswith((".", "!", "?")):
        first += "…"
    return first, " ".join(parts[:2]) or first


def caption_said(r):
    """The start of a Reel's caption without its comment-keyword ask: often says the promise
    plainly where the hooks don't ("got tired of paying for comment-to-DM automation...")."""
    cap = CTA_RE.sub(" ", re.sub(r"[^\w\s'.,:!?&+-]", " ", r.get("caption") or ""))
    parts = [p.strip() for p in re.split(r"[.!?\n]+|\s{2,}", cap) if len(p.split()) >= 3]
    return " ".join(parts[:2])


def short_text(t, n=90):
    t = " ".join(t.split())
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


# A hook's promise is what it says the viewer gets, not its wording. These words carry no
# promise of their own (hook filler: "did you know", "someone built", "the entire", "for
# exactly"), and these synonyms are one word for the comparison ("100 buyers" and "100 fake
# customers" are the same promise; "without spending a dollar" and "for $0" too).
FILLER = set("""able actually already also another anyone anything because been before being
could did didn doe does doesn don done during else entire even ever everyone everything exactly
fake few here haven isn know knew less like literally look lot many more most much need needed
needs never nobody noticed once only other own people pretty quite real really same see should
single somebody someone something still sure than then there these they thing those though
through today together very want wasn were where which while who whole whose will without won
would yet built inside after""".split())
SYNONYMS = {
    "buyer": "customer", "client": "customer", "prospect": "customer",
    "startup": "business", "company": "business",
    "validate": "test", "validated": "test", "tested": "test", "testing": "test",
    "spend": "free", "spending": "free", "spent": "free", "dollar": "free", "cost": "free",
    "cheap": "free", "zero": "free", "pay": "free", "paying": "free", "paid": "free",
    "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10",
}
FREE_RE = re.compile(r"\$\s?0(?![\d.,])|\bfor nothing\b", re.I)


def canon(w):
    return SYNONYMS.get(w, w)


def promise_words(text, ignore=()):
    """The words that carry a hook's promise: content words, plurals as singulars, synonyms as
    one word, hook filler and the words in `ignore` (the idea's own name, the niche) left out."""
    ign = {canon(w) for w in ignore}
    out = set()
    for w in words(FREE_RE.sub(" free ", text or "")):
        w = canon(w)
        if w not in FILLER and w not in ign:
            out.add(w)
    return out


def same_angle(a, b):
    """Two angles are one promise when their promise words overlap: 2+ words in common making
    up half of the shorter. "Test entire businesses inside Claude without spending a dollar" and
    "Claude can test your business idea on 100 buyers before you spend a dollar" are one promise
    (test + free, the idea's own word "business" aside), not two."""
    if not a or not b:
        return True
    common = len(a & b)
    return a == b or (common >= 2 and common / min(len(a), len(b)) >= 0.5)


def idea_ignore(i):
    """Words that don't tell one angle of an idea from another: the idea's name and the niche."""
    return COMMON | words(i["title"])


def same_promise(texts_a, texts_b, ignore):
    """Whether any text of one angle (its hook, or the hooks of the Reels folded into it) makes
    the same promise as any text of the other: a log row's topic and hook, or another angle."""
    keys_b = [promise_words(t, ignore) for t in texts_b if t]
    for ta in texts_a:
        ka = promise_words(ta, ignore)
        if len(ka) < 2:
            continue
        for kb in keys_b:
            if len(kb) >= 2 and same_angle(ka, kb):
                return True
    return False


def angles(i):
    """Distinct angles in an idea's winners: one per creator and per promise, best Reel first.
    Only Reels judged on topic when a hooks file exists; the first is the idea itself. A Reel
    making the promise of an angle already found is folded into it (its hook kept in `said`),
    so the angle can be matched with the posting log through any of its Reels' wordings."""
    # Reels the hooks file judged on topic first; then the ones it didn't read, marked unchecked.
    pool = sorted(i["top"][:ANGLES_FROM], key=lambda r: r.get("hook") is None)
    ign = idea_ignore(i)
    out, seen_accounts = [], set()
    for r in pool:
        if r["account"].lower() in seen_accounts:
            continue
        show, said = angle_of(r)
        key = promise_words(said, ign)
        twin = next((a for a in out if any(same_angle(key, k) for k in a["keys"])), None) if out else None
        if twin is not None:
            twin["keys"].append(key)
            twin["said"].append(said)
            twin["log_said"] += [said, caption_said(r), f"{said} {caption_said(r)}"]
            twin["folded"].append(r)
            continue
        if out and len(key) < 2:
            continue
        seen_accounts.add(r["account"].lower())
        rank = i["top"].index(r) + 1
        why = (r.get("hook") or {}).get("why")
        why = short_text(strip_md(why), 160) if why else None
        # Against the posting log, an angle is matched through its hooks and its caption: a hook can
        # say "This 17 year old fixed ManyChat's biggest problem" while the caption names the promise.
        out.append({"angle": short_text(show), "key": key, "keys": [key], "said": [said],
                    "log_said": [said, caption_said(r), f"{said} {caption_said(r)}"],
                    "folded": [], "reel": r, "rank": rank, "checked": r.get("hook") is not None,
                    "why": why})
    return out


def load_idea(slug, path, rdate, today):
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [reel_row(r, today) for r in csv.DictReader(fh)]
    hp = path.with_name(path.stem + "-hooks.md")
    on, off = read_hooks(hp, rows) if hp.exists() else ({}, set())
    for r in rows:
        if r["code"] in on:
            r["hook"] = on[r["code"]]
        if r["code"] in off:
            r["off_topic"] = True
            r["ranked"] = False
    ranked = sorted([r for r in rows if r["ranked"]],
                    key=lambda r: (-r["shares_per_1k"], -(r["likes_per_1k"] or 0), -(r["views"] or 0)))
    top = ranked[:TOP_PER_IDEA]
    score = round(statistics.median([r["shares_per_1k"] for r in top]), 2) if top else None
    ages = [r["age_days"] for r in ranked if r["age_days"] is not None]
    newest = min(ages) if ages else None
    if len(ranked) < THIN:
        state = "thin"
    elif newest is not None and newest > WAVE_DAYS:
        state = "wave passed?"
    else:
        state = "live"
    rd = date_of(rdate)
    return {"idea": slug, "title": slug.replace("-", " "), "file": str(path), "researched": rdate,
            "research_age_days": (today - rd).days if rd else None,
            "reels": len(rows), "ranked": len(ranked), "low_reactions": sum(r["low_reactions"] for r in rows),
            "score": score, "newest_ranked_age_days": newest, "state": state, "top": ranked[:10],
            "hooks_file": str(hp) if hp.exists() else None, "on_topic_checked": bool(on),
            "off_topic": [f"@{r['account']} ({r['url']})" for r in rows if r["off_topic"]]}


# ---------- the creator's own posts ----------

def load_posts(log, today):
    rows, _ = postlog.load(log)
    posts = []
    for r in rows:
        when = (r.get("posted_at") or "").strip()
        d = date_of(when)
        if not d:
            continue
        hm = when[11:16] if len(when) >= 16 else ""
        views, reach = num(r.get("views")), num(r.get("reach"))
        base, basis = (reach, "reach") if reach else (views, "views")
        shares = num(r.get("shares"))
        age = (today - d).days
        posts.append({
            "id": r.get("id", ""), "date": d.isoformat(), "time": hm, "weekday": d.weekday(),
            "format": (r.get("format") or "").strip().lower() or "reel",
            "topic": (r.get("topic") or "").strip(), "idea": (r.get("idea") or "").strip(),
            "hook": (r.get("hook") or "").strip(),
            "url": r.get("url", ""), "views": views, "reach": reach, "shares": shares,
            "saves": num(r.get("saves")), "likes": num(r.get("likes")),
            "avg_watch_s": num(r.get("avg_watch_s")),
            "shares_per_1k": per_1k(shares, base), "basis": basis, "age_days": age,
            "settled": age >= CLIMBING_DAYS,
        })
    return sorted(posts, key=lambda p: (p["date"], p["time"]))


def own_numbers(posts):
    settled = [p for p in posts if p["settled"] and p["shares_per_1k"] is not None]
    med = round(statistics.median([p["shares_per_1k"] for p in settled]), 2) if settled else None
    formats = {}
    for p in settled:
        formats.setdefault(p["format"], []).append(p)
    by_format = []
    for f, ps in formats.items():
        rates = [p["shares_per_1k"] for p in ps]
        vs = [p["views"] for p in ps if p["views"] is not None]
        by_format.append({"format": f, "posts": len(ps), "median_shares_per_1k": round(statistics.median(rates), 2),
                          "median_views": int(statistics.median(vs)) if vs else None,
                          "enough": len(ps) >= MIN_BUCKET})
    by_format.sort(key=lambda x: (not x["enough"], -x["median_shares_per_1k"]))
    best = sorted(settled, key=lambda p: -p["shares_per_1k"])
    winners = [p for p in best if med and len(settled) >= THIN and p["shares_per_1k"] >= WINNER_X * med]
    return {"settled_with_shares": len(settled), "median_shares_per_1k": med,
            "by_format": by_format, "posts_by_rate": best, "winners": winners,
            "climbing": [p for p in posts if not p["settled"]]}


def band_of(hm):
    if not hm:
        return None
    h = int(hm[:2])
    for name, lo, hi in BANDS:
        if lo <= h < hi:
            return name
    return NIGHT


def timing(posts):
    """Best weekdays and time bands from the creator's views. Index = views / median views."""
    ps = [p for p in posts if p["settled"] and p["views"]]
    out = {"posts": len(ps), "enough": len(ps) >= MIN_TIMING_POSTS, "days": [], "bands": [],
           "best_days": [], "best_time": None}
    if not ps:
        return out
    med = statistics.median(p["views"] for p in ps)

    def table(key, names):
        rows = []
        for k in names:
            grp = [p for p in ps if key(p) == k]
            if grp:
                idx = round(statistics.median(p["views"] for p in grp) / med, 2) if med else None
                rows.append({"name": DAYS[k] if isinstance(k, int) else k, "key": k, "posts": len(grp),
                             "index": idx, "ranked": len(grp) >= MIN_BUCKET})
        return sorted(rows, key=lambda r: (not r["ranked"], -(r["index"] or 0)))

    out["median_views"] = int(med)
    out["days"] = table(lambda p: p["weekday"], range(7))
    out["bands"] = table(lambda p: band_of(p["time"]), [b[0] for b in BANDS] + [NIGHT])
    if out["enough"]:
        out["best_days"] = [r["key"] for r in out["days"] if r["ranked"] and r["index"] >= 1.0]
        bands = [r for r in out["bands"] if r["ranked"] and r["key"] is not None]
        if bands and bands[0]["index"] >= 1.0:
            b = bands[0]["key"]
            mins = [int(p["time"][:2]) * 60 + int(p["time"][3:5]) for p in ps
                    if p["time"] and band_of(p["time"]) == b]
            # The true median: with an even count, halfway between the middle two, to the minute.
            # The night band runs past midnight: 01:00 counts as 25:00 so 23:00 and 01:00 give 00:00.
            mins = [x + 1440 if b == NIGHT and x < 360 else x for x in mins]
            m = int(statistics.median(mins) + 0.5) % 1440
            out["best_time"] = f"{m // 60:02d}:{m % 60:02d}"
            out["best_band"] = b
    return out


# ---------- coverage, creators, the week ----------

def coverage(ideas, posts, today, recent_days):
    for i in ideas:
        hits = [p for p in posts if (p["idea"] and p["idea"] == i["idea"]) or
                (p["topic"] and same_topic(p["topic"], i["title"]))]
        i["covered"] = [{"id": p["id"], "date": p["date"], "topic": p["topic"],
                         "shares_per_1k": p["shares_per_1k"]} for p in hits]
        last = max((p["date"] for p in hits), default=None)
        i["last_covered"] = last
        i["covered_recently"] = bool(last and (today - date_of(last)).days <= recent_days)


def creators(ideas, me, limit):
    me = (me or "").lstrip("@").lower()
    acc = {}
    for i in ideas:
        if i["state"] == "wave passed?":
            continue
        for pos, r in enumerate(i["top"], 1):
            a = r["account"]
            if not a or a.lower() == me:
                continue
            k = (r["platform"], a)
            c = acc.setdefault(k, {"account": a, "platform": r["platform"], "ideas": [], "top_reels": 0,
                                   "best_shares_per_1k": 0, "best_reel": "", "best_views": None})
            c["top_reels"] += 1
            if i["idea"] not in c["ideas"]:
                c["ideas"].append(i["idea"])
            if r["shares_per_1k"] > c["best_shares_per_1k"]:
                c.update(best_shares_per_1k=r["shares_per_1k"], best_reel=r["url"], best_views=r["views"])
    out = sorted(acc.values(), key=lambda c: (-len(c["ideas"]), -c["top_reels"], -c["best_shares_per_1k"]))
    for c in out:
        c["profile"] = (f"https://www.instagram.com/{c['account']}/" if c["platform"] == "Instagram"
                        else f"https://www.tiktok.com/@{c['account']}")
    return out[:limit]


STATE_ORDER = {"live": 0, "thin": 1, "wave passed?": 2}


def reel_evidence(r):
    return (f"@{r['account']} {short(r['views'])} views, {r['shares_per_1k']} shares/1K ({r['url']})")


def post_texts(p):
    return [t for t in (p.get("topic"), p.get("hook")) if t]


def post_label(p):
    return f"#{p['id']} on {p['date']} \"{p['topic'] or p.get('hook') or ''}\""


def candidates(ideas, own, posts=(), today=None, recent_days=28):
    """What to post next, best first. Each idea gives one slot per distinct promise in its
    winners (see angles()); the week takes every idea's best angle first, by idea (live before
    thin before stale, then score), then every idea's second angle, and so on. Ideas covered
    recently are left out; then the creator's best own winner as a follow-up.

    Each angle is also checked against the posting log by its promise, through the topic and
    hook of every post and every wording of the angle: an angle making the promise of a post
    from the last `recent_days` is left out (listed in the idea's `already_posted`); one that
    makes the promise of the own winner being followed up goes into that follow-up slot as its
    research, so the week holds that promise once and says it is a deliberate follow-up; an
    older match stays, with a note that it needs a new angle. Two ideas' angles that make the
    same promise fill one slot, not two."""
    today = today or datetime.date.today()
    follow = next((w for w in own["winners"][:1] if w["age_days"] >= CLIMBING_DAYS), None)
    folded_into_follow = []
    done = [i["title"] for i in ideas if i["covered_recently"]]
    fresh = [i for i in ideas if i["score"] is not None and not i["covered_recently"]
             and not any(same_topic(i["title"], t) for t in done)]
    groups = []  # one per idea: its angles, best first
    for i in sorted(fresh, key=lambda i: (STATE_ORDER[i["state"]], -i["score"])):
        best = i["top"][0]
        ev = (f"research {i['researched']}: {i['ranked']} ranked Reels, top-{min(TOP_PER_IDEA, i['ranked'])} "
              f"median {i['score']} shares/1K views; best {reel_evidence(best)}")
        if i["state"] != "live":
            ev += f"; caution: {i['state']}"
            if i["newest_ranked_age_days"] is not None:
                ev += f" (newest ranked Reel {i['newest_ranked_age_days']} days old)"
        if i["last_covered"]:
            ev += f"; you covered it on {i['last_covered']}, so it needs a new angle"
        twin = next((g for g in groups if same_topic(g["title"], i["title"])), None)
        if twin:  # the same idea researched under another wording: one slot, not two
            twin["also"].append(i["idea"])
            if twin["items"]:
                twin["items"][0]["evidence"] += f"; also researched as \"{i['title']}\" (score {i['score']})"
            continue
        ign = idea_ignore(i)
        i["already_posted"] = []
        kept = []
        for a in angles(i):
            hits = [p for p in posts if same_promise(a["log_said"], post_texts(p), ign)]
            if follow is not None and any(p["id"] == follow["id"] for p in hits):
                folded_into_follow.append((i, a))
                continue
            recent = [p for p in hits if (today - date_of(p["date"])).days <= recent_days]
            if recent:
                i["already_posted"].append({"angle": a["angle"], "reel": a["reel"]["url"],
                                            "posts": [post_label(p) for p in recent]})
                continue
            a["older"] = [post_label(p) for p in hits]
            kept.append(a)
        items = []
        for k, a in enumerate(kept):
            r = a["reel"]
            checked = ("on topic per its hooks file" if a["checked"] else
                       "on topic not checked: its hooks file didn't read this Reel, so read it before you use it"
                       if i["on_topic_checked"] else
                       "on topic not checked: no hooks file, so read the Reel before you use it")
            src = f"{Path(i['file']).name}, Reel #{a['rank']} of its ranked Reels ({checked})"
            e = ev if k == 0 else (f"another winner in the same research ({i['researched']}): "
                                   f"{reel_evidence(r)}; a different promise from the idea's other slots")
            if k == 0 and r is not best:
                e += f"; this slot's Reel: {reel_evidence(r)}"
            if a["folded"]:
                e += "; the same promise also won for " + ", ".join(
                    f"@{f['account']} ({f['shares_per_1k']}/1K)" for f in a["folded"])
            if a["older"]:
                e += ("; you made this promise before (" + "; ".join(a["older"])
                      + "), so give it a new angle")
            if a["why"]:
                e += f"; why it worked: {a['why']}"
            items.append({"kind": "research", "idea": i["idea"], "title": i["title"], "format": "reel",
                          "angle": a["angle"], "angle_no": k + 1, "reel": r["url"],
                          "state": i["state"], "score": i["score"] if k == 0 else r["shares_per_1k"],
                          "file": i["file"], "source": src, "evidence": e,
                          "_said": a["said"], "_ign": ign})
        groups.append({"title": i["title"], "also": [], "items": items})
    cands = []
    for k in range(max((len(g["items"]) for g in groups), default=0)):
        for g in groups:
            if k < len(g["items"]):
                c = g["items"][k]
                if any(same_promise(c["_said"], o["_said"], c["_ign"] | o["_ign"]) for o in cands):
                    continue  # another idea's slot already makes this promise
                if g["also"]:
                    c["also"] = g["also"]
                cands.append(c)
    for c in cands:
        c.pop("_said", None)
        c.pop("_ign", None)
    if follow is not None:
        w = follow
        ev = (f"a deliberate follow-up to your own winner: post #{w['id']} on {w['date']} got "
              f"{w['shares_per_1k']} shares/1K {w['basis']}, "
              f"{round(w['shares_per_1k'] / own['median_shares_per_1k'], 1)}x your median "
              f"{own['median_shares_per_1k']}")
        if folded_into_follow:
            reels = []
            for _, a in folded_into_follow:
                for r in [a["reel"]] + a["folded"]:
                    reels.append(f"@{r['account']} \"{short_text(angle_of(r)[0], 60)}\" "
                                 f"{r['shares_per_1k']}/1K ({r['url']})")
            ev += ("; the research's winners on the same promise, folded into this slot instead "
                   "of slots of their own: " + "; ".join(reels)
                   + ". Say what this one adds that your first post didn't")
        c = {"kind": "follow-up", "idea": w["idea"] or "", "title": f"follow-up: {w['topic']}",
             "format": w["format"], "angle": None, "state": "own winner",
             "score": w["shares_per_1k"], "source": f"your posting log, post #{w['id']}",
             "evidence": ev}
        if folded_into_follow:
            i, a = folded_into_follow[0]
            c.update(reel=a["reel"]["url"], file=i["file"])
        cands.append(c)
    return cands


def capacity(cands, ideas):
    research = [c for c in cands if c["kind"] == "research"]
    return {"research_files": len(ideas), "ideas": len({c["idea"] for c in research}),
            "angles": len(research), "follow_ups": len(cands) - len(research), "slots": len(cands)}


# ---------- follower activity, pasted from Instagram ----------

DAY_RE = re.compile(r"\b(mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?|"
                    r"fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b\.?", re.I)
HOUR_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a|p)\b|\b(\d{1,2}):(\d{2})\b", re.I)
COUNT_RE = re.compile(r"(?<![\w:])(\d[\d,. \xa0]*)\s*([kKmM])?(?![\w:])")


def _hours(line):
    out = []
    for m in HOUR_RE.finditer(line):
        if m.group(1):
            h = int(m.group(1)) % 12
            if m.group(3).lower().startswith("p"):
                h += 12
        else:
            h = int(m.group(4))
        if 0 <= h <= 23:
            out.append(h)
    return out


def _days(line):
    return [DAYS.index(m.group(1)[:3].title()) for m in DAY_RE.finditer(line)]


def _counts(line):
    rest = DAY_RE.sub(" ", HOUR_RE.sub(" ", line))
    out = []
    for m in COUNT_RE.finditer(rest):
        v = postlog.parse_number(m.group(1), m.group(2))
        if v is not None:
            out.append(v)
    return out


def parse_active(text):
    """The followers' most active times, as the creator read them off Instagram's 'Most active
    times' chart: lists of top days and hours ("Tue Thu Sun", "6p 9p", "Wed 12pm 6pm"), or counts
    (a "Mon 1,234" line per day, a "6p 812" line per hour, or a row of hour labels with a row of
    counts under it). Returns {"days": {weekday: weight}, "hours": {hour: weight},
    "day_hours": {weekday: {hour: weight}}}."""
    days, hours, dh = {}, {}, {}
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    skip = False
    for n, ln in enumerate(lines):
        if skip:
            skip = False
            continue
        ds, hs, cs = _days(ln), _hours(ln), _counts(ln)
        nxt = lines[n + 1] if n + 1 < len(lines) else ""
        if not cs and nxt and not _days(nxt) and not _hours(nxt):
            ncs = _counts(nxt)
            if len(hs) >= 3 and not ds and len(ncs) == len(hs):
                for h, c in zip(hs, ncs):
                    hours[h] = hours.get(h, 0) + c
                skip = True
                continue
            if len(ds) >= 3 and not hs and len(ncs) == len(ds):
                for d, c in zip(ds, ncs):
                    days[d] = days.get(d, 0) + c
                skip = True
                continue
        if cs:
            if len(ds) == 1 and len(hs) == len(cs) and len(hs) > 1:
                for h, c in zip(hs, cs):
                    dh.setdefault(ds[0], {})[h] = dh.get(ds[0], {}).get(h, 0) + c
            elif len(cs) == 1:
                c = cs[0]
                if ds and hs:
                    for d in ds:
                        for h in hs:
                            dh.setdefault(d, {})[h] = dh.get(d, {}).get(h, 0) + c
                elif ds:
                    for d in ds:
                        days[d] = days.get(d, 0) + c
                elif hs:
                    for h in hs:
                        hours[h] = hours.get(h, 0) + c
            continue
        # A plain list: the first named is the busiest. Weights only order them.
        if ds and hs:
            for d in ds:
                for k, h in enumerate(hs):
                    dh.setdefault(d, {})[h] = dh.get(d, {}).get(h, 0) + (len(hs) - k)
        elif ds:
            for k, d in enumerate(ds):
                days[d] = days.get(d, 0) + (len(ds) - k)
        elif hs:
            for k, h in enumerate(hs):
                hours[h] = hours.get(h, 0) + (len(hs) - k)
    return {"days": days, "hours": hours, "day_hours": dh}


def active_summary(act):
    if not act:
        return None
    dayw = dict(act["days"])
    if not dayw:
        for d, hs in act["day_hours"].items():
            dayw[d] = sum(hs.values())
    allh = dict(act["hours"])
    for hs in act["day_hours"].values():
        for h, v in hs.items():
            allh.setdefault(h, 0)
            if not act["hours"]:
                allh[h] += v
    best_days = sorted(dayw, key=lambda d: (-dayw[d], d))
    peak = min(allh, key=lambda h: (-allh[h], h)) if allh else None
    per_day = {d: min(hs, key=lambda h: (-hs[h], h)) for d, hs in act["day_hours"].items() if hs}
    if not best_days and peak is None:
        return None
    return {"best_days": best_days, "peak_hour": peak, "peak_by_day": per_day}


# ---------- the week ----------

def first_free_day(today, posts):
    """Today, or the first day after it with nothing logged as posted."""
    taken = {p["date"] for p in posts}
    d = today
    while d.isoformat() in taken:
        d += datetime.timedelta(days=1)
    return d


def week(n, start, cands, tim, act=None, posts=()):
    """Seven days from start. Days in order of preference: the creator's best days by index,
    else their followers' most active days (pasted), else the published default order; then
    the rest, with days their own numbers show as weak last and days they already posted on
    after that. The best candidate gets the best day; an own winner's follow-up takes the third
    date so new ideas lead; the slots are listed by date."""
    span = [start + datetime.timedelta(days=k) for k in range(7)]
    date_of_wd = {d.weekday(): d for d in span}
    taken = {date_of(p["date"]).weekday() for p in posts if date_of(p["date"]) in span}
    weak = {r["key"] for r in tim["days"] if r["ranked"] and r["index"] < 1.0} if tim["enough"] else set()
    days = []
    if tim["enough"] and tim["best_days"]:
        days, source = [d for d in tim["best_days"] if d not in taken][:n], "your numbers"
    elif act and act["best_days"]:
        days, source = [d for d in act["best_days"] if d not in taken][:n], \
            "your followers' most active days (from Instagram, as you gave them)"
    else:
        source = DEFAULT_SOURCE
    primary = source
    fill = ([d for d in DEFAULT_DAY_ORDER if d not in weak and d not in taken]
            + [d for d in DEFAULT_DAY_ORDER if d in weak and d not in taken]
            + [d for d in DEFAULT_DAY_ORDER if d in taken])
    for d in fill:
        if len(days) >= n:
            break
        if d not in days:
            days.append(d)
            if source == primary and primary != DEFAULT_SOURCE:
                source = primary + ", the rest from the default order (references/default-times.md)"
    if weak:
        source += " (avoiding " + ", ".join(DAYS[d] for d in sorted(weak)) + ": below your median)"
    if taken & set(days):
        source += " (a day you already posted on had to be used)"

    def time_for(d):
        if tim["enough"] and tim.get("best_time"):
            return tim["best_time"], f"your best band {tim['best_band']} (median time of your posts in it)"
        if act and (d in act["peak_by_day"] or act["peak_hour"] is not None):
            h = act["peak_by_day"].get(d, act["peak_hour"])
            return f"{h:02d}:00", "your followers' busiest hour (from Instagram, as you gave it)"
        return DEFAULT_TIMES[d], "default, not your data: that day's top hour in Buffer's study (references/default-times.md)"

    research = [c for c in cands if c["kind"] == "research"]
    follow = [c for c in cands if c["kind"] == "follow-up"]
    by_date = sorted(days, key=lambda d: date_of_wd[d])
    plan_for = {}
    if follow and n >= 3:
        plan_for[by_date[2]] = follow[0]
    elif follow and len(research) < n:
        plan_for[by_date[-1]] = follow[0]
    queue = iter(research)
    for d in days:  # preference order: the best candidate on the best day
        if d not in plan_for:
            plan_for[d] = next(queue, None)
    slots = []
    for d in by_date:
        c = plan_for.get(d)
        t, tsrc = time_for(d)
        slots.append({"date": date_of_wd[d].isoformat(), "day": DAYS[d], "time": t,
                      "day_source": source, "time_source": tsrc,
                      "idea": c["title"] if c else None, "idea_slug": c["idea"] if c else None,
                      "angle": c.get("angle") if c else None, "reel": c.get("reel") if c else None,
                      "format": c["format"] if c else None, "file": c.get("file") if c else None,
                      "source": c["source"] if c else None,
                      "evidence": c["evidence"] if c else
                      "every on-topic winner in your research is already in this week: "
                      "run ig-research on a new idea to fill this slot"})
    for k, s in enumerate(slots, 1):
        s["slot"] = k
    return slots


# ---------- output ----------

def needs_text(log):
    return f"""Nothing to plan from yet: no research CSV and no posts in the log ({log}).

To plan a week from real numbers it needs at least one of:
  1. Research: run the ig-research skill on an idea you are considering. Each run writes
     research-<idea>-<date>.csv, and one run usually holds several winning angles, so it can
     fill several slots. Point this at them with --research <file or folder>.
  2. Your own posts: log what you posted, then paste each post's insights screen:
       postlog.py add --at "YYYY-MM-DD HH:MM" --format reel --topic "what it was about"
       postlog.py insights --id N < pasted.txt
     With 8+ posts a week old or more, it can name your own best days and times.
"""


def capacity_text(cap, asked=None):
    if not cap["research_files"]:
        return None
    t = (f"Your {cap['research_files']} research file{'s' if cap['research_files'] != 1 else ''} "
         f"hold{'s' if cap['research_files'] == 1 else ''} {cap['angles']} distinct winning angle"
         f"{'s' if cap['angles'] != 1 else ''} across {cap['ideas']} idea{'s' if cap['ideas'] != 1 else ''}"
         + (f", plus {cap['follow_ups']} follow-up of your own winner" if cap["follow_ups"] else "")
         + f": enough for {cap['slots']} slot{'s' if cap['slots'] != 1 else ''}.")
    if asked is not None:
        if asked > cap["slots"]:
            t += (f" You asked for {asked}: the last {asked - cap['slots']} need new research "
                  "(run ig-research on another idea).")
        else:
            t += f" You asked for {asked}, so this research covers the week."
    return t


def md(res):
    out = []
    t = res["today"]
    out.append(f"# Week plan evidence ({t})\n")
    for n in res["notes"]:
        out.append(f"- {n}")
    if res["notes"]:
        out.append("")

    ideas = res["ideas"]
    if ideas:
        out.append("## Research ideas, ranked by shares per 1,000 views\n")
        out.append("| # | Idea | Score | Ranked Reels | Angles | Newest ranked | State | Covered | Best Reel |")
        out.append("|---|---|---|---|---|---|---|---|---|")
        n_angles = {}
        for c in res["candidates"]:
            if c["kind"] == "research":
                n_angles[c["idea"]] = n_angles.get(c["idea"], 0) + 1
        for k, i in enumerate(sorted(ideas, key=lambda i: (i["score"] is None, -(i["score"] or 0))), 1):
            b = i["top"][0] if i["top"] else None
            best = f"[@{b['account']}]({b['url']}) {short(b['views'])}, {b['shares_per_1k']}/1K" if b else "–"
            cov = ("recently, " + i["last_covered"]) if i["covered_recently"] else (i["last_covered"] or "no")
            newest = f"{i['newest_ranked_age_days']} d" if i["newest_ranked_age_days"] is not None else "–"
            out.append(f"| {k} | {i['title']} | {i['score'] if i['score'] is not None else '–'} | "
                       f"{i['ranked']}/{i['reels']} | {n_angles.get(i['idea'], 0)} | {newest} | {i['state']} | "
                       f"{cov} | {best} |")
        out.append("\nScore: median shares per 1,000 views of the idea's top 5 ranked Reels "
                   "(10K+ views, a share count, likes + comments at least 2% of views). Angles: distinct "
                   "winning Reels in it (one per creator and per promise), each able to fill a slot.\n")
        cap = capacity_text(res["capacity"], len(res["week"]) if res.get("week") else None)
        if cap:
            out.append(cap + "\n")
        dropped = [(i["title"], i["off_topic"]) for i in ideas if i["off_topic"]]
        for title, offs in dropped:
            out.append(f"Left out of \"{title}\" as off topic (ig-research's hooks file): " + ", ".join(offs))
        posted = [(i["title"], x) for i in ideas for x in i.get("already_posted") or []]
        for title, x in posted:
            out.append(f"Left out of \"{title}\" as a promise you already posted recently: \"{x['angle']}\" "
                       f"({x['reel']}), the same promise as your post " + "; ".join(x["posts"]))
        folded = next((c for c in res["candidates"] if c["kind"] == "follow-up" and c.get("reel")), None)
        if folded:
            out.append(f"Folded into the follow-up of your own winner ({folded['source']}), not given slots "
                       "of their own: the research's winners that make that post's promise (see its evidence).")
        unchecked = [i["title"] for i in ideas if not i["on_topic_checked"] and i["ranked"]]
        if unchecked:
            out.append("No hooks file, so on-topic not checked (read the Reels before using them): "
                       + ", ".join(unchecked))
        if dropped or unchecked or posted or folded:
            out.append("")

    own = res["own"]
    out.append("## Your posts\n")
    if not res["posts"]:
        out.append("No posts in the log yet.\n")
    else:
        out.append(f"{len(res['posts'])} posts logged, {own['settled_with_shares']} settled (7+ days) with shares. "
                   f"Median: {own['median_shares_per_1k'] if own['median_shares_per_1k'] is not None else '–'} "
                   "shares per 1,000 reached (views where reach wasn't pasted).\n")
        if own["by_format"]:
            out.append("| Format | Posts | Median shares/1K | Median views |")
            out.append("|---|---|---|---|")
            for f in own["by_format"]:
                flag = "" if f["enough"] else " (1 post: not enough to compare)"
                out.append(f"| {f['format']}{flag} | {f['posts']} | {f['median_shares_per_1k']} | {short(f['median_views'])} |")
            out.append("")
        if own["posts_by_rate"]:
            out.append("Best and worst by shares per 1,000:\n")
            ps = own["posts_by_rate"]
            show = ps[:3] + ([p for p in ps[-2:] if p not in ps[:3]] if len(ps) > 3 else [])
            for p in show:
                out.append(f"- #{p['id']} {p['date']} {p['format']} \"{p['topic']}\": {p['shares_per_1k']} "
                           f"per 1K {p['basis']}, {short(p['views'])} views"
                           + (" (winner)" if p in own["winners"] else ""))
            out.append("")
        if own["climbing"]:
            out.append("Still climbing (under 7 days, left out of the averages): " +
                       ", ".join(f"#{p['id']} {p['topic']}" for p in own["climbing"]) + "\n")

    tim, act = res["timing"], res.get("active")
    out.append("## When to post\n")
    if tim["enough"]:
        out.append(f"From your {tim['posts']} settled posts with views (index = the bucket's median views "
                   f"over your median, {short(tim.get('median_views'))}; 2+ posts needed to rank a bucket):\n")
        out.append("Days: " + ", ".join(f"{d['name']} {d['index']} ({d['posts']})" + ("" if d["ranked"] else "*")
                                         for d in tim["days"]))
        out.append("Times: " + ", ".join(f"{b['name']} {b['index']} ({b['posts']})" + ("" if b["ranked"] else "*")
                                          for b in tim["bands"] if b["name"]))
        out.append("(* one post only: not ranked)\n")
        if not tim["best_days"]:
            out.append("No day beats your median yet; the draft fills the days from "
                       + ("your followers' active days." if act else "the default.") + "\n")
    else:
        out.append(f"Your own posts can't say yet: {tim['posts']} settled posts with views, "
                   f"{MIN_TIMING_POSTS} needed.\n")
    if act:
        bits = []
        if act["best_days"]:
            bits.append("days " + ", ".join(DAYS[d] for d in act["best_days"]))
        if act["peak_hour"] is not None:
            bits.append(f"busiest hour {act['peak_hour']:02d}:00")
        if act["peak_by_day"]:
            bits.append("by day " + ", ".join(f"{DAYS[d]} {h:02d}:00" for d, h in sorted(act["peak_by_day"].items())))
        out.append("Your followers' most active times (from Instagram, as you gave them): " + "; ".join(bits)
                   + (". Used for the days and times." if not tim["enough"] else
                      ". Your own numbers take precedence where they name a day or time.") + "\n")
    elif not tim["enough"]:
        out.append("**Using a default, not your data**: Buffer's study of 9.6M Instagram posts (Jan 2024 to "
                   "Dec 2025, engagement across all post types) ranks Wed, Thu and Tue best and Fri and Sat "
                   "lowest, with a top hour per day: Mon 19:00, Tue 19:00, Wed 12:00, Thu 09:00, Fri 22:00, "
                   "Sat 21:00, Sun 21:00 (your local time). Source and caveats: references/default-times.md.\n")
        out.append(ACTIVE_HOWTO + ".\n")

    out.append("## Accounts to engage with this week\n")
    if res["creators"]:
        out.append("| Account | Ideas | Top-10 Reels | Best Reel |")
        out.append("|---|---|---|---|")
        for c in res["creators"]:
            out.append(f"| [@{c['account']}]({c['profile']}) | {', '.join(c['ideas'])} | {c['top_reels']} | "
                       f"[{short(c['best_views'])} views, {c['best_shares_per_1k']}/1K]({c['best_reel']}) |")
        out.append("\nOnly creators of on-topic Reels: any ig-research left out as off topic are not listed.\n")
    else:
        out.append("None: no research with ranked Reels.\n")

    if res.get("week"):
        out.append(f"## Draft week from {res['week_start']} ({len(res['week'])} posts)\n")
        out.append("| Date | Day | Time | Format | Idea | Angle | From | Evidence |")
        out.append("|---|---|---|---|---|---|---|---|")
        for s in res["week"]:
            angle = f"\"{s['angle']}\"" if s.get("angle") else "–"
            out.append(f"| {s['date']} | {s['day']} | {s['time']} | {s['format'] or '–'} | {s['idea'] or '–'} | "
                       f"{angle} | {s['source'] or '–'} | {s['evidence']} |")
        s0 = res["week"][0]
        out.append(f"\nDays: {s0['day_source']}.")
        tsrcs = list(dict.fromkeys(s["time_source"] for s in res["week"]))
        out.append(f"Time: {'; '.join(tsrcs)}.")
    elif res["candidates"]:
        out.append("## Ideas to post next, best first\n")
        for k, c in enumerate(res["candidates"], 1):
            angle = f" angle \"{c['angle']}\"" if c.get("angle") else ""
            out.append(f"{k}. {c['title']} ({c['format']}){angle}: {c['evidence']} [from {c['source']}]")
    return "\n".join(out) + "\n"


def config_path():
    return postlog.config_dir() / "config.json"


def read_active(arg):
    if arg == "-":
        return sys.stdin.read()
    p = Path(arg).expanduser()
    if not p.is_file():
        sys.exit(f"error: --active {arg}: no such file (write what Instagram's 'Most active times' shows into a text file)")
    return p.read_text(encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--research", nargs="*", default=None, help="research CSVs or folders holding them")
    ap.add_argument("--log", type=Path, default=None, help="the posting log (default: IG_PLAN_LOG, else <config dir>/posted.csv)")
    ap.add_argument("--me", default=None, help="your handle, left out of the accounts to engage with")
    ap.add_argument("--posts", type=int, default=None, help="draft this many slots (1 to 7)")
    ap.add_argument("--start", default=None, help="first day of the week, YYYY-MM-DD (default: today, or the next day with nothing posted)")
    ap.add_argument("--active", default=None, metavar="FILE",
                    help="your followers' most active times from Instagram's insights, as text (- for stdin)")
    ap.add_argument("--recent-days", type=int, default=28)
    ap.add_argument("--creators", type=int, default=8)
    ap.add_argument("--today", default=None, help="pretend today is YYYY-MM-DD")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--remember", action="store_true", help="save --research, --me and --active for next time")
    ap.add_argument("--config", type=Path, default=None,
                    help="settings file (default: $XDG_CONFIG_HOME/ig-plan/config.json, else ~/.config/ig-plan/config.json)")
    a = ap.parse_args(argv)

    cfgp = (a.config or config_path()).expanduser()
    cfg = {}
    if cfgp.exists():
        try:
            cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        except ValueError:
            cfg = {}
    active_text = read_active(a.active) if a.active else None
    if a.remember:
        if a.research:
            cfg["research"] = [str(Path(p).expanduser().resolve()) for p in a.research]
        if a.me:
            cfg["me"] = a.me.lstrip("@")
        if active_text:
            cfg["active"] = active_text
        cfgp.parent.mkdir(parents=True, exist_ok=True)
        cfgp.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    research_paths = a.research if a.research else cfg.get("research") or [str(Path.cwd())]
    me = a.me or cfg.get("me")
    act = active_summary(parse_active(active_text or cfg.get("active") or ""))
    log = (a.log or postlog.default_log()).expanduser()
    today = date_of(a.today) if a.today else datetime.date.today()
    if a.posts is not None and not 1 <= a.posts <= 7:
        sys.exit("error: --posts is 1 to 7 for one week")
    if a.start and not date_of(a.start):
        sys.exit("error: --start takes a date, YYYY-MM-DD")
    if (active_text or cfg.get("active")) and not act:
        sys.exit("error: no days or hours recognised in the active times; write them like "
                 "\"Tue Thu Sun\" and \"6p 9p\", or \"Mon 1,234\" per day")

    files = find_research(research_paths)
    ideas = [load_idea(s, f, d, today) for s, f, d in files]
    COMMON.clear()
    COMMON.update(common_words([i["title"] for i in ideas]))
    posts = load_posts(log, today)
    if not ideas and not posts:
        print(needs_text(log))
        return 3

    notes = []
    if not ideas:
        notes.append("No research CSV found in " + ", ".join(research_paths) +
                     ": new ideas need ig-research runs. Planning from your own posts only.")
    if not posts:
        notes.append(f"No posts in the log ({log}): coverage, your own winners and your best times "
                     "are unknown. Log posts and paste insights to fill them in.")
    stale = [i["idea"] for i in ideas if (i["research_age_days"] or 0) > STALE_RESEARCH_DAYS]
    if stale:
        notes.append(f"Research older than {STALE_RESEARCH_DAYS} days (the numbers have moved since): " + ", ".join(stale))
    coverage(ideas, posts, today, a.recent_days)
    own = own_numbers(posts)
    tim = timing(posts)
    cands = candidates(ideas, own, posts, today, a.recent_days)
    res = {"today": today.isoformat(), "notes": notes, "research_files": [str(f) for _, f, _ in files],
           "log": str(log), "ideas": ideas, "posts": posts, "own": own, "timing": tim, "active": act,
           "creators": creators(ideas, me, a.creators), "candidates": cands,
           "capacity": capacity(cands, ideas)}
    if a.posts:
        start = date_of(a.start) if a.start else first_free_day(today, posts)
        res["week_start"] = start.isoformat()
        res["week"] = week(a.posts, start, cands, tim, act, posts)
    if a.json:
        print(json.dumps(res, indent=1, ensure_ascii=False, default=lambda o: sorted(o) if isinstance(o, set) else str(o)))
    else:
        print(md(res), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
