#!/usr/bin/env python3
"""ig-engage: sort the comments under your post, list keyword DMs, check and log your comments.

Standard library only. Reads files you give it and, for `log`, one small Markdown file.
It never posts, comments, likes, follows or sends anything: every output is text you post
yourself.

  python3 engage.py sort comments.txt --keyword GUIDE [--me yourhandle] [--json]
  python3 engage.py replies comments.txt --keyword GUIDE --me yourhandle            # what to answer
  python3 engage.py replies comments.txt --keyword GUIDE --me yourhandle --drafts replies.txt
  python3 engage.py dms comments.txt --keyword GUIDE --link https://... \
          --message "Hey! Here's the guide: {link}" [--message "..."] [--csv out.csv | --csv folder/]
  python3 engage.py read post.json                     # caption + top comments of a post
  python3 engage.py check --kind comment|reply|dm [--account h] [--post post.json] [--to "..."] TEXT|-
  python3 engage.py log add --account h --post URL TEXT|-
  python3 engage.py log show [--last 20]

Comments come in three shapes, detected automatically:
  * the browser reader's dump (scripts/instagram-comments.js): a JSON array of
    tab-separated lines, or the same lines in a plain file;
  * one comment per line, "handle: text" (indent a line, or start it with ">", to make it
    a reply to the comment above);
  * text copied from the comment section of instagram.com (handle, age, text, "Reply").
"""

import argparse
import csv
import datetime as dt
import difflib
import io
import json
import os
import re
import string
import subprocess
import sys

# ---------------------------------------------------------------- loading comments

HANDLE = r"[A-Za-z0-9._]{1,30}"
AGE_RE = re.compile(r"^(?:edited\s*[·•]\s*)?\d{1,3}\s?(?:s|m|h|d|w|y|sec|min|hr|hrs|wk|wks|mo)$", re.I)
UI_RE = re.compile(
    r"^(?:reply|like|liked|see translation|hide replies|see more|more|verified|author|creator|"
    r"\d[\d,.]*k?\s*likes?|view (?:all )?\d+ (?:more )?repl(?:y|ies)|view replies(?: \(\d+\))?|"
    r"[-—–]+\s*view (?:all )?\d+ repl(?:y|ies)|liked by (?:author|creator)|pinned|load more comments)$",
    re.I,
)
LIKED_BY_CREATOR_RE = re.compile(r"^liked by (?:author|creator)$", re.I)


class Comment:
    __slots__ = ("id", "parent", "user", "ts", "likes", "text", "order", "category", "tags",
                 "why", "replied", "liked_by_creator", "said_sent")

    def __init__(self, id, parent, user, ts, likes, text, order):
        self.id, self.parent, self.user = str(id), str(parent or ""), user.lstrip("@").lower()
        self.ts, self.likes, self.text, self.order = int(ts or 0), int(likes or 0), text, order
        self.category, self.tags, self.why = None, [], ""
        self.replied, self.liked_by_creator, self.said_sent = False, False, False

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


def djb2(text):
    """Same hash as the browser reader's checksum(): over UTF-16 code units."""
    h = 5381
    data = text.encode("utf-16-le")
    for i in range(0, len(data), 2):
        h = (h * 33 + (data[i] | data[i + 1] << 8)) & 0xFFFFFFFF
    return f"{h:08x}"


def read_text(path):
    if path == "-":
        return sys.stdin.read()
    with open(os.path.expanduser(path), encoding="utf-8") as f:
        return f.read()


def load(paths, want_lines=None, want_hash=None):
    """Return (post or None, [Comment]). post = dict(code, owner, ts, comments, caption)."""
    texts = [read_text(p) for p in paths]
    lines = []
    dump = True
    for t in texts:
        s = t.strip()
        if s.startswith("["):
            try:
                arr = json.loads(s)
                if all(isinstance(x, str) for x in arr):
                    lines.extend(arr)
                    continue
            except json.JSONDecodeError:
                pass
        lines.extend(t.splitlines())
    tsv = [l for l in lines if l.strip()]
    dump = bool(tsv) and all(l.count("\t") >= 5 for l in tsv)
    if dump:
        if want_lines is not None or want_hash:
            got = djb2("\n".join(tsv))
            if (want_lines is not None and len(tsv) != want_lines) or (want_hash and got != want_hash.lower()):
                sys.exit(f"MISMATCH: the copy has {len(tsv)} lines, hash {got}; the browser has "
                         f"{want_lines} lines, hash {want_hash}. Dump again and save the parts verbatim.")
        return parse_dump(tsv)
    text = "\n".join(texts)
    if want_lines is not None or want_hash:
        print("note: --lines/--hash only apply to the browser reader's dump; ignored.", file=sys.stderr)
    simple = parse_simple(text)
    return (None, simple) if simple is not None else (None, parse_copied(text))


def parse_dump(lines):
    post, out = None, []
    for i, l in enumerate(lines):
        f = l.split("\t", 5)
        if f[0] == "#more":  # continuation of the line above (long caption or comment)
            if out:
                out[-1].text += f[5]
            elif post:
                post["caption"] += f[5]
            continue
        if f[0] == "#post":
            post = {"code": f[1], "owner": f[2].lower(), "ts": int(f[3] or 0),
                    "comments": int(f[4] or 0), "caption": f[5]}
            continue
        out.append(Comment(f[0], f[1], f[2], f[3] or 0, f[4] or 0, f[5], i))
    return post, out


SIMPLE_RE = re.compile(r"^(\s+|>\s*|↳\s*)?@?(" + HANDLE + r")\s*[:：]\s*(.*)$")


def parse_simple(text):
    """'handle: text' per line. Returns None unless most non-empty lines look like that."""
    rows = [l for l in text.splitlines() if l.strip()]
    if not rows:
        return []
    hits = [SIMPLE_RE.match(l) for l in rows]
    if sum(1 for h in hits if h) < max(1, 0.8 * len(rows)):
        return None
    out, last_top = [], None
    for i, m in enumerate(hits):
        if not m:  # a wrapped line: belongs to the comment above
            if out:
                out[-1].text += " " + rows[i].strip()
            continue
        reply = bool(m.group(1))
        c = Comment(f"p{i}", last_top if reply and last_top else "", m.group(2), 0, 0, m.group(3).strip(), i)
        if not reply:
            last_top = c.id
        out.append(c)
    return out


def parse_copied(text):
    """Text copied from instagram.com's comment list: handle, age, text..., Reply."""
    rows = [l.strip() for l in text.splitlines()]
    rows = [l for l in rows if l]
    out, i, n = [], 0, 0
    handle_line = re.compile(r"^@?(" + HANDLE + r")(?:\s+(?:verified|author|creator))?$", re.I)
    while i < len(rows):
        m = handle_line.match(rows[i])
        nxt = rows[i + 1] if i + 1 < len(rows) else ""
        if m and AGE_RE.match(nxt):
            user, j, body, likes, liked = m.group(1), i + 2, [], 0, False
            while j < len(rows):
                if handle_line.match(rows[j]) and j + 1 < len(rows) and AGE_RE.match(rows[j + 1]):
                    break
                lm = re.match(r"^(\d[\d,]*)\s*likes?$", rows[j], re.I)
                if lm:
                    likes = int(lm.group(1).replace(",", ""))
                elif LIKED_BY_CREATOR_RE.match(rows[j]):
                    liked = True
                elif not UI_RE.match(rows[j]):
                    body.append(rows[j])
                j += 1
            c = Comment(f"c{n}", "", user, 0, likes, " ".join(body), n)
            c.liked_by_creator = liked
            out.append(c)
            n += 1
            i = j
        else:
            i += 1
    return out


# ---------------------------------------------------------------- sorting

CATEGORIES = ["keyword", "lead", "question", "substance", "praise", "noise"]
LABEL = {"keyword": "used the keyword", "lead": "possible lead", "question": "question",
         "substance": "worth a real reply", "praise": "praise", "noise": "spam or noise"}

SPAM_RE = re.compile(
    r"https?://|www\.|\b[a-z0-9-]+\.(?:com|net|io|co|shop|store|xyz|link|ly)\b|bit\.ly|"
    r"link in (?:my )?bio|check (?:out )?my (?:page|profile|bio|account|reels?|content)|"
    r"(?:dm|message|text) (?:us|me)\b.{0,20}\b(?:collab|promot|feature|ambassador|grow|followers)|"
    r"\bpromot(?:e|ion|ing)\b|\bambassador\b|\bgiveaway\b|\bcrypto\b|\bbitcoin\b|\bforex\b|"
    r"\binvest(?:ment)? (?:with|opportunit)|\bfollow (?:me|back|4|for follow)|\bf4f\b|\bl4l\b|"
    r"\bsub4sub\b|\bearn \$|\bmake \$\d|\bonlyfans\b|\btelegram\b|whatsapp|\bsend (?:it|pics?) to @|"
    r"\bgrow your (?:page|account|followers)\b|\bboost your\b|\bfree followers\b",
    re.I,
)
LEAD_RE = re.compile(
    r"\bhow much\b(?!\s+(?:time|work|effort|faster|better|longer|easier|more|less|of|did|does|has|have|can|could)\b)|\bpric(?:e|es|ing)\b|\bcosts?\b|\brates?\b|\bcharge\b|\bquote\b|\bbudget\b|"
    r"\bhir(?:e|ing)\b|\bfreelanc|\bconsult|\byour services?\b|\bdo you (?:offer|do|build|make|take)\b|"
    r"\bwork (?:with|together)\b|\bwork for (?:you|me|us)\b|\bcollab(?:orate|oration)?\b|\bpartner(?:ship)?\b|"
    r"\bbook (?:a|an)\b|\b(?:a|on a) call\b|\bcan you (?:build|make|set ?up|do) (?:this|it|one|that|something)\b|"
    r"\bfor (?:my|our) (?:business|company|team|clients?|agency|brand|store|startup|shop)\b|"
    r"\b(?:email|dm|message) you\b|\bpay you\b|\bcoaching\b|\bmentor(?:ing|ship)?\b|\bavailable for\b",
    re.I,
)
QUESTION_START = re.compile(
    r"^(?:how|what|whats|what's|why|where|when|which|who|can|could|does|do|did|is|are|was|will|would|"
    r"should|any|anyone|anybody|is there|have you|has anyone|wdym|idk how)\b",
    re.I,
)
PRAISE_RE = re.compile(
    r"\b(?:love[ds]?|loving|good|so real|true|great|amazing|awesome|fire|insane|nice|cool|brilliant|genius|helpful|useful|"
    r"thanks?|thank you|thx|ty|so true|facts|needed this|game ?changer|legend|goat|wow|beautiful|perfect|"
    r"incredible|underrated|banger|clean|sick|dope|gem|valuable|great tip|well said|spot on|exactly|"
    r"this is it|love it|saving this|saved)\b",
    re.I,
)
SUBSTANCE_RE = re.compile(
    r"\bi (?:tried|use|used|built|did|had|found|think|disagree|agree|wish|switched|made|run)\b|"
    r"\bin my (?:experience|case|opinion)\b|\bbut\b|\bactually\b|\bthe problem\b|\bwhat about\b|"
    r"\bdisagree\b|\bdepends\b|\binstead\b|\bdoesn'?t\b|\bwon'?t\b|\bcan'?t\b|\d",
    re.I,
)
POSITIVE_EMOJI = set("🔥❤😍🙌👏💯🤯👍💪✨🙏😮🤩🥹😂🤣💙💜💚🧡🖤🤍♥⭐🚀🎉👌😊☺🫶")
WORD_RE = re.compile(r"[^\W_]+(?:'[^\W_]+)?", re.U)


def words(text):
    return WORD_RE.findall(text.lower())


def strip_mentions(text):
    return re.sub(r"@" + HANDLE, " ", text)


def edit1(a, b):
    """True when a and b differ by at most one insert, delete or substitution."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = diff = 0
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            diff += 1
            if diff > 1:
                return False
            if len(a) == len(b):
                i += 1
            j += 1
        else:
            i += 1
            j += 1
    return diff + (len(b) - j) <= 1


def keyword_hit(text, keywords):
    """Return the keyword used, or None. Whole words; plurals; a one-letter typo only when the
    comment is little more than the word itself."""
    toks = words(strip_mentions(text))
    joined = " " + " ".join(toks) + " "
    for kw in keywords:
        k = words(kw)
        if not k:
            continue
        phrase = " ".join(k)
        if f" {phrase} " in joined or f" {phrase}s " in joined or f" {phrase}es " in joined:
            return kw
        if len(k) == 1 and len(k[0]) >= 4 and len(toks) <= 3:
            if any(edit1(t, k[0]) for t in toks):
                return kw
        # "COMMENT G U I D E" style
        if len(k) == 1 and "".join(toks) == k[0]:
            return kw
    return None


def only_emoji(text):
    t = re.sub(r"[\s‍️]", "", strip_mentions(text))
    return bool(t) and not WORD_RE.search(t)


def classify(c, keywords):
    """Set c.category, c.tags and c.why. Order: spam, keyword, lead, question, substance, praise, noise."""
    text = c.text.strip()
    bare = strip_mentions(text).strip()
    w = words(bare)
    is_q = "?" in text or bool(QUESTION_START.match(bare))
    is_lead = bool(LEAD_RE.search(text))
    if SPAM_RE.search(text):
        c.category, c.why = "noise", "spam: link, promotion or follow bait"
        return
    kw = keyword_hit(text, keywords) if keywords else None
    if kw:
        c.category, c.why = "keyword", f"commented {kw}"
        if is_lead:
            c.tags.append("lead")
        if is_q and len(w) > 2:
            c.tags.append("question")
        return
    if not bare:
        c.category = "noise"
        c.why = "tagged a friend (a share; no reply needed)" if "@" in text else "empty"
        return
    if is_lead:
        c.category, c.why = "lead", "asks about price, services or working together"
        if is_q:
            c.tags.append("question")
        return
    if is_q and len(w) >= 2:
        c.category, c.why = "question", "asks something"
        return
    if keywords and len(w) == 1 and not PRAISE_RE.search(bare) and not only_emoji(text):
        c.category, c.why = "noise", "one word, not the keyword"
        c.tags.append("maybe-keyword")
        return
    if only_emoji(text):
        if any(ch in POSITIVE_EMOJI for ch in text):
            c.category, c.why = "praise", "emoji"
        else:
            c.category, c.why = "noise", "emoji only"
        return
    praise = bool(PRAISE_RE.search(bare)) or any(ch in POSITIVE_EMOJI for ch in text)
    if len(w) >= 8 or (len(w) >= 5 and SUBSTANCE_RE.search(bare)):
        c.category, c.why = "substance", "says something of their own"
        if praise:
            c.tags.append("praise")
        return
    if praise:
        c.category, c.why = "praise", "short and positive"
        return
    if is_q:
        c.category, c.why = "question", "asks something"
        return
    c.category, c.why = ("substance", "says something of their own") if len(w) >= 4 else ("noise", "too short to answer")


SENT_RE = re.compile(r"\b(?:sent|sending|check your (?:dms?|inbox|requests)|in your dms?|dm'?d you)\b", re.I)


def mark_replied(comments, me):
    """A comment counts as answered when `me` replied in its thread, or wrote a comment that
    starts with @its-author after it."""
    if not me:
        return
    me = me.lstrip("@").lower()
    by_id = {c.id: c for c in comments}
    for c in comments:
        if c.user != me:
            continue
        says_sent = bool(SENT_RE.search(c.text))
        if c.parent and c.parent in by_id:
            by_id[c.parent].replied = True
            by_id[c.parent].said_sent = by_id[c.parent].said_sent or says_sent
        for m in re.findall(r"@(" + HANDLE + r")", c.text[:80]):
            m = m.lower().rstrip(".")
            for o in comments:
                if o.user == m and o.order < c.order and (not c.parent or o.parent == c.parent or o.id == c.parent):
                    o.replied = True
                    o.said_sent = o.said_sent or says_sent


BASE = {"lead": 100, "question": 80, "substance": 60, "keyword": 40, "praise": 20, "noise": 0}


def score(c):
    s = BASE[c.category]
    if "lead" in c.tags:
        s += 70
    if "question" in c.tags:
        s += 45
    return s + min(c.likes, 40) * 0.5


def sort_comments(post, comments, keywords, me=None):
    me = (me or (post or {}).get("owner") or "").lstrip("@").lower()
    for c in comments:
        if c.user == me:
            c.category, c.why = "yours", "your own comment"
            continue
        classify(c, keywords)
    mark_replied(comments, me)
    theirs = [c for c in comments if c.category != "yours"]
    # replies inside threads that are not yours: classify, but they rarely need their own answer
    counts = {k: sum(1 for c in theirs if c.category == k) for k in CATEGORIES}
    answered = {k: sum(1 for c in theirs if c.category == k and c.replied) for k in CATEGORIES}
    todo, kw_seen = [], set()
    for c in theirs:
        if c.category == "noise" or c.replied:
            continue
        if c.category == "keyword" and not c.tags:  # one keyword reply per person is enough
            if c.user in kw_seen:
                continue
            kw_seen.add(c.user)
        todo.append(c)
    todo.sort(key=lambda c: (-score(c), c.ts or 0, c.order))
    return {
        "me": me, "post": post, "keywords": keywords, "comments": comments,
        "counts": counts, "answered": answered, "yours": len(comments) - len(theirs),
        "order": todo,
        "done": [c for c in theirs if c.replied],
        "noise": [c for c in theirs if c.category == "noise"],
    }


def short(text, n=90):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def count_note(post, comments):
    """What was read against what Instagram reports, explained in plain words."""
    total = len(comments)
    replies = sum(1 for c in comments if c.parent)
    split = f"{total - replies} comments and {replies} replies" if replies else f"{total} comments"
    head = f"Post {post['code']} by @{post['owner']}: read {split}, everything that loads on the post's page."
    reported = post.get("comments") or 0
    if reported <= total:
        return [head]
    return [head,
            f"Instagram shows {reported} as the comment count. That number also counts comments nobody can load: "
            f"ones Instagram's filter hid, ones caught by your hidden words, ones from restricted accounts, "
            f"and ones that were deleted. The {reported - total} missing are those, not a reading error."]


def render_sort(res, top=40):
    out = []
    post = res["post"]
    total = len(res["comments"])
    if post:
        out.extend(count_note(post, res["comments"]))
    else:
        out.append(f"Read {total} comments" + (f", yours as @{res['me']}" if res["me"] else
                                              " (no --me given, so replies you made can't be told apart)") + ".")
    out.append("Keyword: " + (", ".join(res["keywords"]) if res["keywords"] else "none given"))
    out.append("")
    out.append("Counts")
    for k in CATEGORIES:
        a = res["answered"][k]
        out.append(f"  {LABEL[k]:<20}{res['counts'][k]:>5}" + (f"   ({a} already answered)" if a else ""))
    out.append(f"  {'yours':<20}{res['yours']:>5}")
    out.append("")
    order = res["order"]
    out.append(f"Reply order, not yet answered ({len(order)}" + (f", top {top} shown" if len(order) > top else "") + ")")
    for i, c in enumerate(order[:top], 1):
        tags = (" +" + "+".join(c.tags)) if c.tags else ""
        likes = f" {c.likes}♥" if c.likes else ""
        thread = " (in a thread)" if c.parent else ""
        out.append(f"  {i:>3}. {c.category + tags:<22} @{c.user}{likes}{thread}: \"{short(c.text)}\"")
    if not order:
        out.append("  nothing waiting")
    kw = [c for c in res["comments"] if c.category == "keyword"]
    if kw:
        out.append("")
        out.append(f"Keyword DMs: {len({c.user for c in kw})} people. Run `dms` with the link to get the list.")
    maybe = {}
    for c in res["comments"]:
        if "maybe-keyword" in c.tags:
            maybe.setdefault(c.text.strip().strip(".!").upper(), []).append(c)
    if maybe:
        out.append("")
        out.append("One-word comments that aren't the keyword (people often comment the word from another Reel, "
                   "or a near one): " + "; ".join(f"{w} x{len(cs)}" for w, cs in sorted(maybe.items(), key=lambda x: -len(x[1]))) +
                   ". If they meant the keyword, run again with another --keyword.")
    if res["noise"]:
        out.append("")
        out.append(f"Spam or noise, no reply ({len(res['noise'])}): " +
                   "; ".join(f"@{c.user} ({c.why})" for c in res["noise"][:12]) +
                   (" …" if len(res["noise"]) > 12 else ""))
    out.append("")
    out.append("Sorted by rules on the words (references/sorting.md); skim the list before replying.")
    return "\n".join(out)


# ---------------------------------------------------------------- reply drafts

HOW = {
    "lead": "thank them briefly and move it to DMs; no price unless the creator gave one",
    "question": "the answer itself, short; a gap [ ] where a fact is missing",
    "substance": "respond to their point: agree with a reason, add a detail, or ask one thing back",
    "keyword": "the DM sends the link; answer the question they also asked",
    "praise": "a short, specific thanks",
}


def worth_answering(res, include_praise=False):
    """Comments from the reply order that get a drafted reply: leads, questions, comments with
    substance, and keyword comments that also asked something. Same order as the reply order."""
    out = []
    for c in res["order"]:
        if c.category in ("lead", "question", "substance") or set(c.tags) & {"lead", "question"}:
            out.append(c)
        elif include_praise and c.category == "praise":
            out.append(c)
    return out


DRAFT_RE = re.compile(r"^\s*(?:(\d{1,3})[.)]|@?(" + HANDLE + r")\s*[:：])\s*(.*)$")


def parse_drafts(text, wanted):
    """Match drafted replies to the comments in `wanted`. Lines are `@handle: reply` or `N. reply`
    (N from the worksheet); a line that starts neither way continues the reply above (a bare
    `word:` that is nobody's handle does too). Several
    drafts for the same handle go to that person's comments in order. Returns ({comment id: reply},
    [unmatched lines])."""
    entries = []
    handles = {c.user for c in wanted}
    for line in text.splitlines():
        if not line.strip():
            continue
        m = DRAFT_RE.match(line)
        if m and (m.group(1) or line.lstrip().startswith("@") or m.group(2).lower().rstrip(".") in handles):
            entries.append([m.group(1), (m.group(2) or "").lower().rstrip("."), m.group(3).strip()])
        elif entries:
            entries[-1][2] += "\n" + line.strip()
        else:
            entries.append([None, "", line.strip()])
    drafts, unmatched = {}, []
    for num, handle, reply in entries:
        target = None
        if num:
            i = int(num) - 1
            if 0 <= i < len(wanted) and wanted[i].id not in drafts:
                target = wanted[i]
        elif handle:
            target = next((c for c in wanted if c.user == handle and c.id not in drafts), None)
        if target and reply.strip():
            drafts[target.id] = reply.strip()
        else:
            unmatched.append((f"{num}." if num else f"@{handle}:" if handle else "") + " " + reply)
    return drafts, unmatched


def render_worksheet(wanted, res):
    out = [f"Replies to draft: {len(wanted)}, in reply order (leads, questions, then comments with something in them).",
           "Write one reply each in the creator's voice, save them one per line as `@handle: reply`, "
           "then run this again with --drafts <file>.", ""]
    for i, c in enumerate(wanted, 1):
        tags = (" +" + "+".join(c.tags)) if c.tags else ""
        thread = " (in a thread)" if c.parent else ""
        out.append(f"{i:>3}. @{c.user} [{LABEL[c.category]}{tags}]{thread}: \"{short(c.text, 200)}\"")
        out.append(f"     how: {HOW.get('question' if 'question' in c.tags and c.category == 'keyword' else c.category, '')}")
    if not wanted:
        out.append("  nothing worth a written reply is waiting (leads, questions and substance are all answered).")
    rest = [c for c in res["order"] if c not in wanted]
    if rest:
        out.append("")
        out.append(f"Not drafted ({len(rest)}): plain keyword comments (the DM is the answer) and praise "
                   "(a like is enough; --with-praise drafts those too).")
    return "\n".join(out)


def check_drafts(wanted, drafts, unmatched, use_voice=True, verbose=False):
    """Check every draft. Returns (text, ok)."""
    script, where, notes = (find_voice_info(verbose) if use_voice else (None, "", []))
    out, ready, ok = [], [], True
    for i, c in enumerate(wanted, 1):
        head = f"{i:>3}. @{c.user} [{LABEL[c.category]}]: \"{short(c.text, 140)}\""
        reply = drafts.get(c.id)
        out.append(head)
        if not reply:
            out.append("     no draft yet")
            ok = False
            continue
        res = check_text(reply, "reply", to=c.text)
        bad = [r for r in res if r[0] in ("FAIL", "REFUSE")]
        voice = run_voice(reply, "reply", script) if script else None
        out.append(f"     reply: \"{reply}\"")
        for level, name, msg in res:
            if level != "PASS":
                out.append(f"     {level:<6} {name}: {msg}")
        if use_voice and script:
            for line in summarize_voice(voice, where=None)[1:]:
                out.append("     " + line.strip())
        if bad:
            out.append("     -> rewrite: " + "; ".join(r[1] for r in bad))
            ok = False
        elif voice_flagged(voice):
            out.append("     -> ig-voice could not check this; fix ig-voice, or check again with --no-voice"
                       if "error" in voice else "     -> rewrite the lines ig-voice lists, then check again")
            ok = False
        else:
            ready.append((i, c, (voice or {}).get("cleaned", "").strip() if (voice or {}).get("fixed") else reply))
    if unmatched:
        out.append("")
        out.append("Drafts that match no comment waiting for a reply (already answered under the post, or check the handle or number): " +
                   "; ".join(short(u, 60) for u in unmatched))
    out.append("")
    if not use_voice:
        out.append("ig-voice: skipped (--no-voice).")
    elif not script:
        out.extend(summarize_voice(None, notes=notes))
    else:
        out.append(f"ig-voice: every reply was checked with the copy at {where}.")
        out.extend(f"  note: {n}" for n in notes)
    out.append("")
    out.append(f"Ready to paste ({len(ready)} of {len(wanted)}). You post each reply yourself; nothing was posted.")
    for i, c, reply in ready:
        out.append(f"{i}. @{c.user}: \"{short(c.text, 100)}\"")
        out.append("   " + reply.replace("\n", "\n   "))
    return "\n".join(out).rstrip() + "\n", ok


# ---------------------------------------------------------------- keyword DMs

def dm_rows(res, messages, link=None, skip=(), new_only=False):
    skip = {s.strip().lstrip("@").lower() for s in skip if s.strip()}
    seen, rows = {}, []
    for c in sorted(res["comments"], key=lambda c: (c.ts or 0, c.order)):
        if c.category != "keyword" or c.user in skip or c.user == res["me"]:
            continue
        if c.user in seen:
            seen[c.user]["comment"] += " / " + c.text
            seen[c.user]["replied"] = seen[c.user]["replied"] or c.replied
            seen[c.user]["said_sent"] = seen[c.user]["said_sent"] or c.said_sent
            continue
        kw = c.why.replace("commented ", "")
        r = {"handle": c.user, "comment": c.text, "replied": c.replied, "said_sent": c.said_sent,
             "also": "+".join(c.tags), "keyword": kw}
        seen[c.user] = r
        rows.append(r)
    if new_only:
        rows = [r for r in rows if not r["said_sent"]]
    for i, r in enumerate(rows):
        tpl = messages[i % len(messages)]
        r["dm"] = tpl.format_map(_Fill(handle=r["handle"], keyword=r["keyword"], link=link or ""))
        r["n"] = i + 1
    return rows


class _Fill(dict):
    def __missing__(self, key):
        raise SystemExit(f"error: unknown placeholder {{{key}}} in --message; use {{handle}}, {{keyword}} or {{link}}")


DM_FIELDS = ("handle", "keyword", "link")


def dm_template_problem(text):
    """([placeholders dms fills], problem or None). Uses the same str.format rules as dms, so
    anything check passes, dms can fill, and anything dms would reject, check fails."""
    try:
        fields = [f for _, f, _, _ in string.Formatter().parse(text) if f is not None]
    except ValueError as e:
        return [], (f"a {{ or }} dms can't read ({e}); write {{{{ or }}}} for a literal brace, "
                    "or use {link}, {handle} or {keyword}")
    unknown = sorted(set(f for f in fields if f not in DM_FIELDS))
    if unknown:
        return [], ("unknown " + ", ".join("{" + u + "}" for u in unknown) +
                    "; dms only fills {link}, {handle} and {keyword}")
    try:
        text.format(**{k: "x" for k in DM_FIELDS})
    except (ValueError, IndexError, KeyError, AttributeError) as e:
        return [], f"dms can't fill this ({e}); use plain {{link}}, {{handle}} or {{keyword}}"
    return sorted(set(fields)), None


def render_dms(rows, link):
    said = sum(1 for r in rows if r["said_sent"])
    out = [f"Keyword DMs: {len(rows)}" + (f", {said} of them already sent by your own account (your reply says so)" if said else "") +
           ". This tool sent nothing; open each person's profile and send it yourself.", ""]
    for r in rows:
        extra = []
        if r["also"]:
            extra.append("also " + r["also"].replace("+", " and ") + ": answer that too")
        if r["said_sent"]:
            extra.append("your reply under the post says you sent it; skip unless you didn't")
        elif r["replied"]:
            extra.append("you already replied under the post")
        out.append(f"{r['n']}. @{r['handle']}   https://www.instagram.com/{r['handle']}/")
        out.append(f"   their comment: \"{short(r['comment'], 120)}\"" + (f"   [{'; '.join(extra)}]" if extra else ""))
        out.append("   " + r["dm"].replace("\n", "\n   "))
        out.append("")
    if not rows:
        out.append("Nobody to send to (no keyword comments, or all left out by --skip or --new-only).")
    return "\n".join(out).rstrip() + "\n"


def csv_target(path, post=None, keywords=()):
    """A CSV file path from --csv: a file, or a folder (existing, or ending in /) to write
    dms-<post code or keyword>.csv into."""
    path = os.path.expanduser(path)
    if os.path.isdir(path) or path.endswith(("/", os.sep)):
        name = (post or {}).get("code") or re.sub(r"[^a-z0-9]+", "-", (keywords[0] if keywords else "keyword").lower()).strip("-")
        path = os.path.join(path, f"dms-{name or 'keyword'}.csv")
    return path


def write_csv(rows, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n", "handle", "profile", "their_comment", "also_asked", "replied_under_post", "reply_says_sent", "dm"])
        for r in rows:
            w.writerow([r["n"], "@" + r["handle"], f"https://www.instagram.com/{r['handle']}/", r["comment"],
                        r["also"], "yes" if r["replied"] else "", "yes" if r["said_sent"] else "", r["dm"]])


# ---------------------------------------------------------------- comment log

def log_path(override=None):
    if override:
        return os.path.expanduser(override)
    if os.environ.get("IG_ENGAGE_LOG"):
        return os.path.expanduser(os.environ["IG_ENGAGE_LOG"])
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "ig-engage", "log.md")


LOG_HEAD = ("# ig-engage comment log\n\n"
            "Comments you posted on other accounts, newest last, so new ones don't repeat a line or a shape.\n"
            "One per line: `- date | @account | post link | comment`. Edit or delete lines freely.\n\n")


def read_log(path):
    entries = []
    if not os.path.exists(path):
        return entries
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("- "):
                continue
            parts = line[2:].rstrip("\n").split(" | ", 3)
            if len(parts) == 4:
                entries.append({"date": parts[0].strip(), "account": parts[1].strip().lstrip("@"),
                                "post": parts[2].strip(), "text": parts[3].strip()})
    return entries


def add_log(path, account, post, text, date=None):
    date = date or dt.date.today().isoformat()
    text = " ".join(text.split()).replace(" | ", " / ")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write(LOG_HEAD)
        f.write(f"- {date} | @{account.lstrip('@')} | {post or '-'} | {text}\n")


STOP = set("""a an the and or but so if then than that this these those it its it's i i'm im me my mine
you you're youre your yours we our us he she they them their is are was were be been being am do does did
done have has had having of to in on at for with from by as about into over just really very so too also
not no yes all any some more most much many one can could would should will wont won't don't dont didn't
cant can't isn't what how why when where who which there here out up down get got like love lol
actually few once off each every part thing things make made way still even only""".split())


def norm_words(text):
    return [w for w in words(strip_mentions(text))]


def skeleton(text):
    out = []
    for w in norm_words(text):
        tok = w if w in STOP else "_"
        if not (tok == "_" and out and out[-1] == "_"):
            out.append(tok)
    end = text.strip()[-1:] if text.strip() else ""
    out.append({"?": "?", "!": "!"}.get(end, "."))
    return out


def content(text):
    return {w for w in norm_words(text) if w not in STOP and len(w) >= 3}


def log_issues(text, entries, account=None):
    """[(level, message)] for a new comment against the log. level is REFUSE or WARN."""
    issues = []
    nw = norm_words(text)
    if not nw:
        return issues
    sk, cw = skeleton(text), content(text)
    for e in reversed(entries):
        ew = norm_words(e["text"])
        where = f"your comment on @{e['account']} ({e['date']}): \"{short(e['text'], 70)}\""
        if ew == nw:
            issues.append(("REFUSE", "same line as " + where))
            continue
        ratio = difflib.SequenceMatcher(None, ew, nw).ratio()
        ec = content(e["text"])
        jac = len(cw & ec) / len(cw | ec) if (cw and ec) else 0
        if ratio >= 0.8 or (jac >= 0.6 and len(cw) >= 3 and len(ec) >= 3):
            issues.append(("REFUSE", "nearly the same line as " + where))
            continue
        if len(nw) >= 4 and len(ew) >= 3 and nw[:3] == ew[:3]:
            issues.append(("REFUSE", f"opens with the same three words (\"{' '.join(nw[:3])}\") as " + where))
            continue
        esk = skeleton(e["text"])
        if len(sk) >= 5 and len(esk) >= 5 and difflib.SequenceMatcher(None, sk, esk).ratio() >= 0.85:
            issues.append(("REFUSE", f"same shape ({' '.join(sk)}) as " + where))
            continue
        if len(nw) >= 5 and len(ew) >= 3 and nw[-3:] == ew[-3:]:
            issues.append(("WARN", f"ends with the same words (\"{' '.join(nw[-3:])}\") as " + where))
    recent = entries[-9:] + [{"text": text}]
    if len(recent) >= 5:
        firsts = [norm_words(e["text"])[:1] for e in recent]
        top = max(firsts, key=firsts.count)
        if top and top == nw[:1] and firsts.count(top) / len(recent) >= 0.5:
            issues.append(("WARN", f"{firsts.count(top)} of your last {len(recent)} comments start with \"{top[0]}\""))
        qs = sum(1 for e in recent if e["text"].strip().endswith("?"))
        if text.strip().endswith("?") and qs / len(recent) >= 0.6:
            issues.append(("WARN", f"{qs} of your last {len(recent)} comments end on a question; vary it"))
    if account:
        n = sum(1 for e in entries[-30:] if e["account"].lower() == account.lstrip("@").lower())
        if n >= 3:
            issues.append(("WARN", f"you commented on @{account.lstrip('@')} {n} times in your last 30 comments"))
    return issues


# ---------------------------------------------------------------- checking a comment, reply or DM

GENERIC_RE = re.compile(
    r"^(?:great|nice|awesome|amazing|love (?:this|it)|so true|this is (?:great|amazing|so good|fire)|"
    r"well said|great (?:post|content|video|reel|tips?)|thanks for sharing|so helpful|facts|"
    r"needed this|100%?|fire|this|wow|yes)[\s!.🔥🙌👏💯❤️]*$",
    re.I,
)

def all_generic(t):
    """True when every clause of a comment is stock praise ("Great post, love this!", "Love this, so
    helpful!", "This is amazing, thanks for sharing"): nothing in it is about this post."""
    parts = [p.strip() for p in re.split(r"[,.!;:&]+|\band\b", t) if p.strip(" 🔥🙌👏💯❤️")]
    return len(parts) > 1 and all(GENERIC_RE.match(p) for p in parts)


SELF_PROMO_RE = re.compile(
    r"check (?:out )?my|my (?:page|profile|account|reels?|channel|newsletter|course)|link in (?:my )?bio|"
    r"\b(?:dm|message) me\b|follow me|i (?:also )?(?:post|make|teach) (?:about|content)",
    re.I,
)


def post_words(post, comments=()):
    text = (post or {}).get("caption", "") + " " + " ".join(c.text for c in comments[:20])
    return content(text)


def check_text(text, kind, entries=(), account=None, post=None, post_comments=(), to=None):
    """[(level, check, message)] with level FAIL/REFUSE/WARN/PASS."""
    res = []
    t = text.strip()
    w = norm_words(t)
    if not t:
        return [("FAIL", "empty", "nothing to check")]
    if re.search(r"https?://|www\.", t) and kind != "dm":
        res.append(("FAIL", "link", "a link in a comment reads as spam and is not clickable; put it in a DM"))
    if kind == "comment":
        if SELF_PROMO_RE.search(t):
            res.append(("FAIL", "self-promotion", "talks about you or your page; a comment on someone else's post is about their post"))
        if GENERIC_RE.match(t) or only_emoji(t) or all_generic(t):
            res.append(("FAIL", "generic", "could go under any post; say one thing about this one"))
        if post is not None:
            shared = content(t) & post_words(post, post_comments)
            if not shared and len(w) >= 3:
                res.append(("WARN", "about the post", "shares no word with the caption or top comments; make sure it's about what the post says"))
            elif shared:
                res.append(("PASS", "about the post", "mentions " + ", ".join(sorted(shared)[:5])))
        if len(t) > 300:
            res.append(("WARN", "length", f"{len(t)} characters; comments past about two lines get cut with \"more\""))
        if "#" in t:
            res.append(("WARN", "hashtags", "hashtags in a comment read as spam"))
        for level, msg in log_issues(t, list(entries), account):
            res.append((level, "log", msg))
        if not any(r[2] for r in res if r[1] == "log"):
            res.append(("PASS", "log", f"no repeat among {len(entries)} logged comments"))
    if kind == "reply":
        if to and ("?" in to or QUESTION_START.match(to.strip())) and len(w) <= 3:
            res.append(("WARN", "answers it", "they asked a question; a reply of three words or fewer probably doesn't answer it"))
        if SELF_PROMO_RE.search(t) and not (to and LEAD_RE.search(to)):
            res.append(("WARN", "selling", "a sales line in a reply to someone who didn't ask"))
    if kind == "dm":
        known, problem = dm_template_problem(t)
        if problem:
            res.append(("FAIL", "placeholder", problem))
        elif known:
            res.append(("PASS", "placeholder", ", ".join("{" + k + "}" for k in known) +
                        " gets filled in for each person by dms"))
        if "{link}" not in t and not re.search(r"https?://|www\.", t):
            res.append(("WARN", "link", "no {link} and no link: the DM doesn't send what the Reel promised"))
    if re.search(r"\[\s*\]|\[\.\.\.\]|\[…\]", t):
        res.append(("FAIL", "gap", "a [ ] gap is still in it: get the missing fact from the creator first"))
    if t.isupper() and len(w) > 2:
        res.append(("WARN", "caps", "all capitals reads as shouting"))
    return res


def tilde(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path == home or path.startswith(home + os.sep) else path


def find_voice_info(verbose=False):
    """(voice.py path or None, where it came from, [notes]). Looks in $IG_VOICE_SKILL_DIR (the
    ig-voice skill folder; $IG_VOICE_DIR is its old name, still read), then the ig-voice folder
    next to this skill in the same pack, then the usual skills folders. Never required."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cands, notes = [], []
    for var in ("IG_VOICE_SKILL_DIR", "IG_VOICE_DIR"):
        if os.environ.get(var):
            cands.append((os.path.expanduser(os.environ[var]), f"from ${var}", var))
    cands.append((os.path.join(os.path.dirname(here), "ig-voice"), "next to ig-engage, same pack", None))
    for root in ("~/.claude/skills", "~/.codex/skills", "~/.agents/skills"):
        cands.append((os.path.join(os.path.expanduser(root), "ig-voice"), f"from {root}", None))
    found = None
    for folder, how, var in cands:
        script = os.path.join(folder, "scripts", "voice.py")
        if os.path.isfile(script):
            if found is None:
                found = (script, how)
            elif verbose and os.path.realpath(script) != os.path.realpath(found[0]):
                notes.append(f"another ig-voice copy is at {tilde(folder)} (not used)")
        elif var:
            notes.append(f"${var} is set to {tilde(folder)}, which has no scripts/voice.py, so it was ignored. "
                         f"It must be the ig-voice skill folder; the voice profile file is set with $IG_VOICE_PROFILE")
    if found is None:
        return None, "", notes
    return found[0], f"{tilde(os.path.dirname(os.path.dirname(found[0])))} ({found[1]})", notes


def find_voice():
    return find_voice_info()[0]


def run_voice(text, kind, script=None):
    """Run ig-voice's checker; return its JSON result, or None when it isn't installed."""
    script = script or find_voice()
    if not script:
        return None
    vkind = {"reply": "comment"}.get(kind, kind)
    try:
        p = subprocess.run([sys.executable, "-B", script, "check", "-", "--kind", vkind, "--json"],
                           input=text, capture_output=True, text=True, timeout=60)
        return json.loads(p.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return {"error": str(e)}


def summarize_voice(v, where=None, notes=()):
    if v is None:
        return ["ig-voice: not installed. This would be better with it: it learns your voice from your own posts "
                "and flags lines that don't sound like you."] + [f"  note: {n}" for n in notes]
    if "error" in v:
        return [f"ig-voice: could not run ({v['error']})."]
    out = []
    fixed = v.get("fixed") or []
    out.append("ig-voice: " + ("profile used" if v.get("profile") else "no voice profile yet, so only general checks ran "
                                "(set one up with ig-voice learn)") + "." + (f" Copy used: {where}." if where else ""))
    out.extend(f"  note: {n}" for n in notes)
    for f in fixed[:6]:
        out.append(f"  fixed: {f.get('what')} ({f.get('count', 1)})" if isinstance(f, dict) else f"  fixed: {f}")
    unlike = "least like you" if v.get("profile") else "look at"
    for key, label in (("rewrite", "rewrite"), ("unlike_you", unlike)):
        for item in (v.get(key) or [])[:4]:
            line = item.get("sentence") or item.get("line_text") or ""
            why = "; ".join(map(str, item.get("reasons") or []))
            out.append(f"  {label}: \"{short(line, 80)}\"" + (f" ({why})" if why else ""))
    for note in (v.get("draft") or [])[:3]:
        out.append(f"  note: {note}")
    if fixed and v.get("cleaned"):
        out.append("  cleaned text: " + v["cleaned"].strip())
    return out


def voice_flagged(v):
    """Not ready while ig-voice lists anything to rewrite or look at (with or without a profile), or while
    it could not check the text at all: an unchecked draft is not a passed one."""
    if not v:
        return False
    if "error" in v:
        return True
    return bool(v.get("rewrite") or v.get("unlike_you"))


# ---------------------------------------------------------------- read a post

def render_post(post, comments, top=10):
    if not post:
        return "No post header in this file: it isn't the browser reader's dump."
    out = [f"@{post['owner']}, post {post['code']}, {post['comments']} comments",
           f"https://www.instagram.com/p/{post['code']}/", "", "Caption:", post["caption"] or "(no caption)", ""]
    tops = sorted([c for c in comments if not c.parent], key=lambda c: (-c.likes, c.order))[:top]
    if tops:
        out.append(f"Top comments ({len(tops)}):")
        for c in tops:
            out.append(f"  @{c.user} ({c.likes}♥): {short(c.text, 140)}")
    return "\n".join(out)


# ---------------------------------------------------------------- CLI

def text_arg(parts):
    if parts == ["-"] or not parts:
        return sys.stdin.read()
    if len(parts) == 1 and os.path.isfile(os.path.expanduser(parts[0])):
        return read_text(parts[0])
    return " ".join(parts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def comments_args(p):
        p.add_argument("inputs", nargs="+", help="comment files (browser dump parts, pasted text) or -")
        p.add_argument("--keyword", "-k", action="append", default=[], help="the word the Reel asked for; repeat for several")
        p.add_argument("--me", help="your handle (default: the post owner from the browser dump)")
        p.add_argument("--lines", type=int, help="line count from __igcomments.checksum()")
        p.add_argument("--hash", help="hash from __igcomments.checksum()")

    sp = sub.add_parser("sort", help="sort comments and print counts and a reply order")
    comments_args(sp)
    sp.add_argument("--top", type=int, default=40)
    sp.add_argument("--json", action="store_true")

    rpl = sub.add_parser("replies", help="the comments worth a written reply, or check your drafted replies")
    comments_args(rpl)
    rpl.add_argument("--drafts", help="file of drafted replies, one per line: `@handle: reply` (or `N. reply`)")
    rpl.add_argument("--with-praise", action="store_true", help="also draft replies to praise")
    rpl.add_argument("--no-voice", action="store_true", help="skip ig-voice even if installed")
    rpl.add_argument("--verbose", "-v", action="store_true", help="also list other ig-voice copies found but not used")

    dp = sub.add_parser("dms", help="keyword commenters with a drafted DM each")
    comments_args(dp)
    dp.add_argument("--message", "-m", action="append", default=[],
                    help="DM text with {link}, {keyword}, {handle}; repeat to rotate several versions")
    dp.add_argument("--link", help="the link or resource you promised")
    dp.add_argument("--skip", help="file of handles already sent to, one per line")
    dp.add_argument("--new-only", action="store_true", help="leave out people your reply says you already sent it to")
    dp.add_argument("--csv", help="also write a CSV: a file name, or a folder to write dms-<post>.csv into")

    rp = sub.add_parser("read", help="caption and top comments of a post (browser dump)")
    rp.add_argument("inputs", nargs="+")
    rp.add_argument("--top", type=int, default=10)
    rp.add_argument("--lines", type=int)
    rp.add_argument("--hash")

    cp = sub.add_parser("check", help="check a comment, reply or DM before you post it")
    cp.add_argument("text", nargs="*", help="the text, a file, or - for stdin")
    cp.add_argument("--kind", choices=["comment", "reply", "dm"], default="comment")
    cp.add_argument("--account", help="whose post a comment goes on")
    cp.add_argument("--post", help="that post's browser dump, to check the comment is about it")
    cp.add_argument("--to", help="for a reply: the comment it answers")
    cp.add_argument("--log", help="log file (default $IG_ENGAGE_LOG or ~/.config/ig-engage/log.md)")
    cp.add_argument("--no-voice", action="store_true", help="skip ig-voice even if installed")
    cp.add_argument("--verbose", "-v", action="store_true", help="also list other ig-voice copies found but not used")
    cp.add_argument("--json", action="store_true")

    lp = sub.add_parser("log", help="the log of comments you posted on other accounts")
    lsub = lp.add_subparsers(dest="lcmd", required=True)
    la = lsub.add_parser("add", help="record a comment after you posted it")
    la.add_argument("text", nargs="*")
    la.add_argument("--account", required=True)
    la.add_argument("--post", default="-")
    la.add_argument("--date")
    la.add_argument("--log")
    ls = lsub.add_parser("show")
    ls.add_argument("--last", type=int, default=20)
    ls.add_argument("--log")
    lw = lsub.add_parser("path")
    lw.add_argument("--log")

    a = ap.parse_args(argv)

    if a.cmd in ("sort", "dms", "replies"):
        post, comments = load(a.inputs, a.lines, a.hash)
        if not comments:
            sys.exit("error: no comments found in the input. Use the browser dump, 'handle: text' lines, "
                     "or text copied from the comment section.")
        res = sort_comments(post, comments, a.keyword, a.me)
        if a.cmd == "sort":
            if a.json:
                json.dump({**{k: v for k, v in res.items() if k not in ("comments", "order", "done", "noise")},
                           "comments": [c.as_dict() for c in comments],
                           "order": [c.id for c in res["order"]]}, sys.stdout, ensure_ascii=False, indent=1)
                print()
            else:
                print(render_sort(res, a.top))
            return 0
        if a.cmd == "replies":
            wanted = worth_answering(res, a.with_praise)
            if not a.drafts:
                print(render_worksheet(wanted, res))
                return 0
            drafts, unmatched = parse_drafts(read_text(a.drafts), wanted)
            text, ok = check_drafts(wanted, drafts, unmatched, not a.no_voice, a.verbose)
            print(text, end="")
            return 0 if ok else 2
        if not a.keyword:
            sys.exit("error: dms needs --keyword (the word the Reel asked people to comment)")
        msgs = a.message or ["Hey! Here's the {keyword} you asked for: {link}"]
        for m in msgs:
            problem = dm_template_problem(m)[1]
            if problem:
                sys.exit(f"error: --message \"{short(m, 60)}\": {problem}")
        if a.link and not any("{link}" in m for m in msgs):
            print("warning: --link given but no message contains {link}", file=sys.stderr)
        if any("{link}" in m for m in msgs) and not a.link:
            sys.exit("error: the message has {link}; pass --link with the link or resource you promised")
        skip = read_text(a.skip).splitlines() if a.skip else ()
        rows = dm_rows(res, msgs, a.link, skip, a.new_only)
        print(render_dms(rows, a.link), end="")
        if a.csv:
            path = csv_target(a.csv, post, a.keyword)
            write_csv(rows, path)
            print(f"CSV: {path}")
        return 0

    if a.cmd == "read":
        post, comments = load(a.inputs, a.lines, a.hash)
        print(render_post(post, comments, a.top))
        return 0

    if a.cmd == "check":
        text = text_arg(a.text)
        entries = read_log(log_path(a.log)) if a.kind == "comment" else []
        post, pcs = (load([a.post]) if a.post else (None, []))
        res = check_text(text, a.kind, entries, a.account, post, pcs, a.to)
        vscript, vwhere, vnotes = (None, "", []) if a.no_voice else find_voice_info(a.verbose)
        voice = run_voice(text, a.kind, vscript) if vscript else None
        bad = [r for r in res if r[0] in ("FAIL", "REFUSE")]
        vflag = voice_flagged(voice)
        if a.json:
            json.dump({"results": res, "voice": voice, "voice_skill": vwhere or None, "voice_flagged": vflag,
                       "ok": not bad and not vflag}, sys.stdout, ensure_ascii=False, indent=1)
            print()
        else:
            print(f"{a.kind}: \"{short(text, 120)}\"")
            for level, name, msg in res:
                print(f"  {level:<6} {name:<15} {msg}")
            for line in (["ig-voice: skipped (--no-voice)."] if a.no_voice else summarize_voice(voice, vwhere, vnotes)):
                print(line)
            if bad:
                print("Result: rewrite it: " + "; ".join(r[1] for r in bad))
            elif vflag and "error" in voice:
                print("Result: not checked: ig-voice could not run. Fix it, or check again with --no-voice")
            elif vflag:
                print("Result: rewrite the lines ig-voice lists, then check again")
            else:
                print("Result: ok to post (you post it yourself)")
        return 2 if bad or vflag else 0

    if a.cmd == "log":
        path = log_path(a.log)
        if a.lcmd == "path":
            print(path)
        elif a.lcmd == "show":
            es = read_log(path)
            print(f"{len(es)} comments logged in {path}")
            for e in es[-a.last:]:
                print(f"  {e['date']}  @{e['account']}: {e['text']}")
        else:
            text = text_arg(a.text)
            issues = [i for i in log_issues(text, read_log(path), a.account) if i[0] == "REFUSE"]
            add_log(path, a.account, a.post, text, a.date)
            print(f"Logged in {path}.")
            for _, msg in issues:
                print(f"  note: {msg}")
        return 0
    return 1


def cli():
    """main() with no tracebacks: file problems become one plain line."""
    try:
        return main()
    except IsADirectoryError as e:
        sys.exit(f"error: {e.filename} is a folder; give a file there")
    except FileNotFoundError as e:
        sys.exit(f"error: no such file or folder: {e.filename}")
    except PermissionError as e:
        sys.exit(f"error: not allowed to read or write {e.filename}")
    except UnicodeDecodeError:
        sys.exit("error: an input file isn't UTF-8 text; save it as plain text and try again")
    except OSError as e:
        sys.exit(f"error: {e.strerror or e}" + (f": {e.filename}" if getattr(e, "filename", None) else ""))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    sys.exit(cli())
