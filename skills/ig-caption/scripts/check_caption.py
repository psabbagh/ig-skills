#!/usr/bin/env python3
"""
check_caption.py - check an Instagram caption before it is posted.

Reads a plain-text caption from a file (or "-" for stdin) and prints:

  1. what the feed and the Reels screen show before the "... more" cut, as boxes
  2. one line per check: PASS, WARN or FAIL, with the reason
  3. the caption as a copy-ready block

Standard library only, no network. It never posts anything.

Every platform number is a setting with a default. The defaults and where each
one comes from are in references/facts.md; change them with the flags below
when Instagram changes, without editing this file.

Exit status: 0 when nothing failed, 1 when at least one check failed, 2 on bad
input.
"""

import argparse
import json
import os
import re
import sys
import textwrap
import unicodedata

# --- defaults (see references/facts.md for sources and dates) ---------------

DEFAULTS = {
    # Meta's Graph API reference for the caption parameter: "Maximum 2200
    # characters". Confirmed.
    "max_chars": 2200,
    # Instagram's @creators account, 18 Dec 2025: captions on posts and Reels
    # go down to five hashtags, rolled out gradually. Meta's API reference
    # still says 30. Default follows the newer, stricter rule.
    "max_hashtags": 5,
    # Where the cut falls is not published by Instagram. These are estimates
    # from third-party guides; they move with screen width, font size and app
    # version. Treat the boxes as an approximation.
    "feed_chars": 125,
    "feed_lines": 2,
    "reel_chars": 60,
    "reel_lines": 1,
    # Our own house rule, not a platform limit.
    "emoji_per_100_words": 4,
    # Width used only to draw the boxes, roughly a phone in portrait.
    "box_width": 44,
}

# --- patterns ----------------------------------------------------------------

HASHTAG_RE = re.compile(r"(?<![\w&])#(\w+)", re.UNICODE)
MENTION_RE = re.compile(r"(?<![\w.])@([A-Za-z0-9._]+)")
LINK_RE = re.compile(
    r"(https?://\S+"
    r"|www\.\S+"
    r"|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|co|ai|app|dev|me|ly|gg|tv|link|page|site|shop|store|xyz|info|biz)(?:/\S*)?\b)",
    re.IGNORECASE,
)

# Phrases that ask the viewer to do something. Matched per sentence, after
# quoted text is taken out, so two matches in one sentence count as one ask and
# a quoted prompt ("Tell Claude 'save this as a skill'") is not an ask. Each
# pattern has a kind, used to compare the caption's ask with the Reel script's.
# Verbs that also appear in how-to steps (download, join, sign up, tell, save)
# only count with words that point the ask at the viewer and this post.
QUOTED_RE = re.compile(r'"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’|(?<!\w)\'[^\'\n]*\'(?!\w)')
QUOTE_MARK = " QUOTED "
CTA_KINDS = [
    ("comment", r"\bcomment\b(?:\s+(?:the\s+word\s+)?(?:(?-i:[A-Z]{2,})|QUOTED)"
                r"|\s+(?:below|down below|with|your|if|which|what)\b)"),
    ("comment", r"\b(?:drop|leave)\s+(?:a|an|your)\s+(?:comment|emoji|\S+ (?:below|in the comments))"),
    ("comment", r"\blet me know\b"),
    ("comment", r"\btell me\s+(?:in the comments|below|what|which|how|if|your|why)\b"),
    ("save", r"\bsave\s+(?:this|it|the post)(?:\s+(?:post|reel|video|carousel|one))?"
             r"(?=\s*(?:[.!,]|$|\bfor\b|\bso\b|\bbefore\b|\band\b|\bif\b|\bto come back\b))"),
    ("save", r"\bsave\s+(?:this|it)\s+(?:post|reel|video|carousel)\b"),
    ("send", r"\b(?:send|share)\s+(?:this|it)\s+(?:post\s+|reel\s+|video\s+)?(?:to|with)\b"),
    ("send", r"\bsend\s+(?:this|it)\s*(?:[.!]|$)"),
    ("send", r"\bshare\s+(?:this|it)\s*(?:[.!]|$)"),
    ("send", r"\btag\s+(?:a|an|your|someone)\b"),
    ("follow", r"\bfollow\s+(?:me|for|along|@)"),
    ("link", r"\blink\s+in\s+(?:my\s+|the\s+)?bio\b"),
    ("link", r"\b(?:click|tap)\s+(?:the|my)\s+(?:link|bio)\b"),
    ("dm", r"\b(?:dm|message)\s+me\b"),
    ("signup", r"\b(?:subscribe|sign up|register|download|join|grab|book)\b"
               r"(?=.*\b(?:bio|link|newsletter|waitlist|my|free|below|here)\b)"),
]
CTA_KIND_RES = [(k, re.compile(rx, re.IGNORECASE)) for k, rx in CTA_KINDS]
# A step of a how-to ("1. Tell Claude...", "Step 2: open...") or an instruction
# aimed at a tool rather than the viewer is not the post's ask.
INSTRUCTION_RE = re.compile(
    r"^(?:step\s*\d+\b|\d+[.)]\s|(?:tell|ask|type|paste|prompt|run|open|write|say)\s+(?!me\b|us\b)\S)",
    re.IGNORECASE)


def ask_kinds(sentence):
    """The kinds of ask in one sentence, or an empty list when it is not an ask."""
    plain = QUOTED_RE.sub(QUOTE_MARK, sentence).strip()
    if INSTRUCTION_RE.match(plain):
        return []
    kinds = []
    for kind, rx in CTA_KIND_RES:
        if rx.search(plain) and kind not in kinds:
            kinds.append(kind)
    return kinds


def find_asks(text):
    """[(sentence, kinds)] for every sentence that asks the viewer to do something."""
    out = []
    for sent in sentences(HASHTAG_RE.sub("", text)):
        kinds = ask_kinds(sent)
        if kinds:
            out.append((sent, kinds))
    return out


# A standing footer: many creators end every caption with the same block, a
# separator line, a "Follow @handle to learn more..." line, hashtags. It is
# part of every post, not this post's ask, so its "Follow @..." line is not
# counted as a second call to action. ig-voice reads footers the same way.
# A separator is a line of punctuation only: "—", "–", "---", "___", "* * *",
# ".", "~~~". Underscore counts, although regex calls it a word character.
SEPARATOR_RE = re.compile(r"^(?:[^\w\s#@]|_){1,12}$")
HASHTAG_LINE_RE = re.compile(r"^(?:#[\w.]+[\s,.]*)+$")
FOOTER_LINE_RE = re.compile(
    r"(?<![\w.])@[A-Za-z0-9._]+|^follow\b|\blink\s+in\s+(?:my\s+|the\s+)?bio\b", re.IGNORECASE)
FOOTER_MAX_LINES = 6  # a footer is a short block; ig-voice looks at the last 6 lines too


def is_separator(line):
    t = line.replace(" ", "").strip()
    return bool(t) and bool(SEPARATOR_RE.match(t))


def split_footer(text):
    """(body, footer). The footer is a separator line followed, to the end of the
    caption, only by short lines that are hashtags, a mention or "Follow ..." line,
    or "link in bio", with at least one that is not hashtags. Otherwise footer is ""."""
    lines = text.rstrip().split("\n")
    i = len(lines)
    kept = 0
    while i > 0:
        t = lines[i - 1].strip()
        if not t:
            i -= 1
            continue
        if is_separator(t):
            break
        if HASHTAG_LINE_RE.match(t) or FOOTER_LINE_RE.search(t):
            kept += 1
            i -= 1
            continue
        return text, ""
    if i == 0 or kept == 0 or kept > FOOTER_MAX_LINES:
        return text, ""
    tail = [l.strip() for l in lines[i:] if l.strip()]
    if all(HASHTAG_LINE_RE.match(t) for t in tail):
        return text, ""  # hashtags under a separator: no ask in it, nothing to set apart
    body = "\n".join(lines[:i - 1]).rstrip()
    if not words(body):
        return text, ""
    return body, "\n".join(lines[i - 1:]).strip("\n")


HEADING_RE = re.compile(r"^\s{0,3}#{1,4}\s+(.*?)\s*#*\s*$")
CUE_PREFIX_RE = re.compile(r"^\s*(?:[-*]\s+)?\d+:\d+(?:\.\d+)?\s*(?:[-–—]\s*(?:\d+:\d+(?:\.\d+)?)?)?\s*")
LINE_MARK_RE = re.compile(r"^\s*(?:[-*]|L?\d+[.):])\s+")


def script_parts(script):
    """{"spoken": text, "onscreen": text} from a Reel script.

    A draft in ig-reel's shape has '## Script' (what is said) and '## On-screen
    text' sections, matched loosely as reel.py does. Without a Script section,
    the whole file, headings left out, is taken as what is said."""
    sections, cur = {}, None
    for line in script.replace("\r\n", "\n").split("\n"):
        m = HEADING_RE.match(line)
        if m:
            h = m.group(1).lower()
            cur = "onscreen" if "screen" in h else "hook" if "hook" in h else "spoken" if "script" in h else None
            if cur:
                sections.setdefault(cur, [])
            continue
        if cur:
            sections[cur].append(line)
    if "spoken" in sections:
        spoken = [LINE_MARK_RE.sub("", l) for l in sections["spoken"]]
    else:
        spoken = [LINE_MARK_RE.sub("", l) for l in script.split("\n") if not HEADING_RE.match(l)]
    onscreen = [CUE_PREFIX_RE.sub("", l) for l in sections.get("onscreen", [])]
    return {"spoken": "\n".join(spoken), "onscreen": "\n".join(onscreen)}


def comment_keyword(sentence):
    m = re.search(r"\bcomment\s+(?:the\s+word\s+)?[\"“']?((?-i:[A-Z][A-Z0-9]+))", sentence, re.IGNORECASE)
    return m.group(1) if m else None


# Unfilled template slots: {{N}}, {{the weekly job}}, {name}. A caption with
# one of these was never finished.
PLACEHOLDER_RE = re.compile(r"\{\{[^{}\n]*\}\}|\{[^{}\n]{1,80}\}")


# Openers that announce a caption instead of saying something. Our own list;
# a first line that starts this way usually has no picture in it yet.
VAGUE_OPENERS = [
    r"^here'?s (what|why|how|the thing|my)\b",
    r"^this is (what|why|how|the)\b",
    r"^so,? ",
    r"^okay,? so\b",
    r"^let'?s talk\b",
    r"^we need to talk\b",
    r"^you won'?t believe\b",
    r"^(ever|have you ever) (wonder|thought)",
    r"^the truth about\b",
    r"^nobody (talks|is talking) about\b",
    r"^(a )?quick (one|thought|reminder|tip)\b",
    r"^some thoughts\b",
    r"^new (post|reel|video)\b",
    r"^in this (post|reel|video)\b",
    r"^thoughts\??$",
    r"^game[- ]?changer\b",
    r"^(guys|friends|everyone)[,!]",
]
VAGUE_RE = re.compile("|".join(VAGUE_OPENERS), re.IGNORECASE)

ZWJ = 0x200D
VS16 = 0xFE0F
KEYCAP = 0x20E3


def is_emoji_base(cp):
    return (
        0x1F300 <= cp <= 0x1FAFF
        or 0x1F000 <= cp <= 0x1F0FF
        or 0x2600 <= cp <= 0x27BF
        or 0x2B00 <= cp <= 0x2BFF
        or 0x1F1E6 <= cp <= 0x1F1FF
        or cp in (0x203C, 0x2049, 0x2122, 0x2139, 0x231A, 0x231B, 0x2328, 0x23CF)
        or 0x23E9 <= cp <= 0x23FA
    )


def is_modifier(cp):
    return cp in (ZWJ, VS16, KEYCAP) or 0x1F3FB <= cp <= 0x1F3FF or 0xE0020 <= cp <= 0xE007F


def emoji_clusters(text):
    """Return a list of (start_index, cluster_text) for each emoji as a reader sees it.

    A family or a flag made of several code points counts once.
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        cp = ord(text[i])
        if is_emoji_base(cp):
            start = i
            regional = 0x1F1E6 <= cp <= 0x1F1FF
            i += 1
            if regional and i < n and 0x1F1E6 <= ord(text[i]) <= 0x1F1FF:
                i += 1
            while i < n:
                c = ord(text[i])
                if c == ZWJ and i + 1 < n:
                    i += 2  # joiner plus the next piece
                elif is_modifier(c):
                    i += 1
                else:
                    break
            out.append((start, text[start:i]))
        else:
            i += 1
    return out


def normalise(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def words(s):
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)?", s, re.UNICODE)


def sentences(s):
    parts = re.split(r"(?<=[.!?])\s+|\n+", s)
    return [p.strip() for p in parts if p.strip()]


def stem(word):
    """A rough singular, base form: skills -> skill, planning -> plan, stories -> story.

    Only for matching search terms, so "Claude Code skill" finds "claude code skills".
    """
    w = word.lower().replace("’", "'")
    if w.endswith("'s"):
        w = w[:-2]
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith(("sses", "shes", "ches", "xes", "zes")):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiouls":
        w = w[:-1]  # planning -> plann -> plan
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]  # make / making -> mak
    return w


def stems(text):
    return [stem(w) for w in words(text)]


def contains_term(text_stems, term_stems):
    n = len(term_stems)
    if not n:
        return False
    return any(text_stems[i:i + n] == term_stems for i in range(len(text_stems) - n + 1))


def sentence_case(s):
    return s[:1].upper() + s[1:]


def utf16_len(s):
    return len(s.encode("utf-16-le")) // 2


# --- the feed preview ----------------------------------------------------------


def preview(text, handle, max_chars, max_lines):
    """Estimate what shows before "... more".

    The caption is cut at whichever comes first: max_chars characters
    (counting the handle shown in front of it), or the end of the
    max_lines-th line, where a line break in the caption ends a line.
    Returns (visible_text, was_cut).
    """
    budget = max_chars - (len(handle) + 1 if handle else 0)
    budget = max(budget, 0)
    lines = text.split("\n")
    kept = []
    used = 0
    cut = False
    for idx, line in enumerate(lines):
        if idx >= max_lines:
            cut = True
            break
        room = budget - used
        if len(line) > room:
            piece = line[:room]
            # back up to a word boundary so the box does not show half a word
            if " " in piece and room < len(line) and not line[room:room + 1].isspace():
                piece = piece[: piece.rfind(" ")]
            kept.append(piece.rstrip())
            cut = True
            break
        kept.append(line)
        used += len(line) + 1
    visible = "\n".join(kept).rstrip()
    if not cut and visible != text.rstrip():
        cut = True
    return visible, cut


def box(title, visible, cut, handle, width):
    inner = width - 4
    body = (handle + " " if handle else "") + visible
    if cut:
        body = body.rstrip() + "... more"
    rows = []
    for para in body.split("\n"):
        wrapped = textwrap.wrap(para, inner, break_long_words=True, replace_whitespace=False) or [""]
        rows.extend(wrapped)
    top = "┌─ " + title + " " + "─" * max(0, width - 5 - len(title)) + "┐"
    lines = [top]
    for r in rows:
        lines.append("│ " + r + " " * max(0, inner - display_width(r)) + " │")
    lines.append("└" + "─" * (width - 2) + "┘")
    return "\n".join(lines)


def display_width(s):
    w = 0
    for ch in s:
        cp = ord(ch)
        if is_modifier(cp) or unicodedata.combining(ch):
            continue
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") or is_emoji_base(cp) else 1
    return w


# --- the checks ------------------------------------------------------------------


def check(text, fmt="reel", keywords=(), handle="", allow_links=False, script=None, **settings):
    s = dict(DEFAULTS)
    s.update({k: v for k, v in settings.items() if v is not None})
    text = text.replace("\r\n", "\n").strip("\n").rstrip()
    results = []

    def add(name, status, detail):
        results.append({"check": name, "status": status, "detail": detail})

    # 0. unfilled placeholders
    slots = [m.group(0) for m in PLACEHOLDER_RE.finditer(text)]
    if slots:
        shown = ", ".join(dict.fromkeys(slots[:5]))
        add("placeholders", "FAIL", f"Unfilled template slot{'s' if len(slots) > 1 else ''}: {shown}. "
            "Put in the real words before posting.")
    else:
        add("placeholders", "PASS", "No {{...}} or {...} left in the text.")

    # 1. length
    n = len(text)
    n16 = utf16_len(text)
    if n > s["max_chars"]:
        add("length", "FAIL", f"{n} characters, over the {s['max_chars']} limit by {n - s['max_chars']}.")
    elif n16 > s["max_chars"]:
        add("length", "WARN",
            f"{n} characters as a reader counts them, but {n16} if emoji count double. "
            f"Over {s['max_chars']} that way; trim to be safe.")
    else:
        add("length", "PASS", f"{n} of {s['max_chars']} characters.")

    # 2. first line
    lines = [l for l in text.split("\n")]
    first = next((l.strip() for l in lines if l.strip()), "")
    feed_vis, feed_cut = preview(text, handle, s["feed_chars"], s["feed_lines"])
    reel_vis, reel_cut = preview(text, handle, s["reel_chars"], s["reel_lines"])
    main_vis = feed_vis if fmt in ("post", "carousel") else reel_vis
    stripped_first = first
    for _, e in emoji_clusters(first):
        stripped_first = stripped_first.replace(e, "")
    stripped_first = stripped_first.strip()
    kw_norm = [normalise(k) for k in keywords if k.strip()]
    if not first:
        add("first line", "FAIL", "The caption is empty.")
    elif not words(stripped_first):
        add("first line", "FAIL", "The first line has no words, only emoji or symbols.")
    elif HASHTAG_RE.match(first) or first.startswith("@"):
        add("first line", "FAIL", "The first line opens with a hashtag or a mention, which is what the feed shows.")
    else:
        problems = []
        if VAGUE_RE.search(stripped_first):
            problems.append("opens by announcing rather than saying something (\"" + stripped_first[:30] + "\")")
        has_number = bool(re.search(r"\d", first))
        caps = [w for w in words(stripped_first)[1:] if w[:1].isupper() and not w.isupper()]
        has_kw = any(k in normalise(first) for k in kw_norm)
        if not (has_number or caps or has_kw):
            problems.append("no number, name or search term in it; make sure it names one specific thing")
        # Photos, carousels and Reels all appear in the feed, so the line has
        # to fit there. The one-line Reels cut is too short to require it.
        if first not in feed_vis:
            problems.append("it does not fit before the feed cut, so its end is hidden")
        if problems:
            add("first line", "WARN", sentence_case("; ".join(problems)) + ".")
        else:
            add("first line", "PASS", f"\"{first[:60]}\"")

    # 3. call to action: count only the post's ask to the viewer, and show the
    # line that was counted so the person can tell when the match is wrong.
    # A standing footer (separator, "Follow @handle..." line, hashtags) is not
    # this post's ask; it is only counted when the body asks nothing.
    body, footer = split_footer(text)
    asks = find_asks(body)
    footer_asks = find_asks(footer) if footer else []
    footer_note = ""
    if footer:
        first_foot = next((l.strip() for l in footer.split("\n") if l.strip() and not is_separator(l)), "")
        footer_note = f" (left out your closing footer \"{first_foot[:60]}\": a standing footer is not this post's ask)"
    if not asks and footer_asks:
        asks = footer_asks
        footer_note = " (in your closing footer, the only ask in the caption)"
    if len(asks) == 1:
        add("call to action", "PASS", f"counted 1 ask: \"{asks[0][0][:100]}\"{footer_note}")
    elif not asks:
        add("call to action", "FAIL", "No ask found. Add exactly one thing for the viewer to do.")
    else:
        listed = "; ".join(f"\"{a[0][:80]}\"" for a in asks)
        add("call to action", "FAIL", f"{len(asks)} asks found, keep one. Counted: {listed}{footer_note}")

    # 3b. the caption's ask against the Reel script's final spoken ask, when a
    # script is given. Only the last ask said out loud is compared: an earlier
    # line or an on-screen cue is not what the video ends by asking for.
    if script is not None:
        parts = script_parts(script)
        spoken_asks = find_asks(parts["spoken"])
        screen_asks = find_asks(parts["onscreen"])
        final = spoken_asks[-1] if spoken_asks else None
        cap_kinds = {k for _, ks in asks for k in ks}
        cap_kw = {comment_keyword(a) for a, _ in asks} - {None}
        if final is None:
            add("matches script", "WARN", "No ask said in the script, so the caption's ask can't be compared. "
                "Make sure the video and the caption ask for the same thing.")
        else:
            scr_kinds = set(final[1])
            scr_kw = {comment_keyword(final[0])} - {None}
            if not asks:
                add("matches script", "WARN", f"The script ends by asking: \"{final[0][:80]}\", the caption asks nothing.")
            elif not cap_kinds & scr_kinds:
                add("matches script", "WARN",
                    f"The script ends by asking \"{final[0][:80]}\" but the caption asks \"{asks[-1][0][:80]}\". "
                    "Viewers get two different asks; use the same one in both.")
            elif cap_kw and scr_kw and not cap_kw & scr_kw:
                add("matches script", "WARN",
                    f"Different comment keywords: script {', '.join(sorted(scr_kw))}, "
                    f"caption {', '.join(sorted(cap_kw))}.")
            else:
                add("matches script", "PASS", f"Same ask as the script's final ask: \"{final[0][:80]}\"")
            if screen_asks:
                last_screen = screen_asks[-1]
                screen_kw = {comment_keyword(last_screen[0])} - {None}
                if not set(last_screen[1]) & scr_kinds or (screen_kw and scr_kw and not screen_kw & scr_kw):
                    add("script asks", "WARN",
                        f"The script says \"{final[0][:60]}\" but its on-screen text asks "
                        f"\"{last_screen[0][:60]}\". Pick one ask for the video too.")

    # 4. search terms: say for each one where it is, matching simple word
    # forms ("skill" and "skills", "plan" and "planning").
    if not kw_norm:
        add("search terms", "WARN", "No search terms given (--keywords). Say what people would type to find this.")
    else:
        plain = stems(HASHTAG_RE.sub(" ", text))
        visible = stems(HASHTAG_RE.sub(" ", main_vis))
        tags = {normalise(t) for t in HASHTAG_RE.findall(text)}
        tag_stems = {stem(t) for t in tags}
        cut_name = "the Reels cut" if fmt == "reel" else "the feed cut"
        where, bad = [], False
        for k in kw_norm:
            ks = stems(k)
            if contains_term(visible, ks):
                where.append(f"'{k}' before {cut_name}")
            elif contains_term(plain, ks):
                where.append(f"'{k}' after {cut_name}")
            elif k.replace(" ", "") in tags or "".join(ks) in tag_stems or stem(k.replace(" ", "")) in tag_stems:
                where.append(f"'{k}' only as a hashtag, not as words")
                bad = True
            else:
                where.append(f"'{k}' missing")
                bad = True
        add("search terms", "FAIL" if bad else "PASS", "; ".join(where) + ".")

    # 5. hashtags
    tags = HASHTAG_RE.findall(text)
    lower = [t.lower() for t in tags]
    dupes = sorted({t for t in lower if lower.count(t) > 1})
    if len(tags) > s["max_hashtags"]:
        add("hashtags", "FAIL", f"{len(tags)} hashtags, over the limit of {s['max_hashtags']}.")
    elif dupes:
        add("hashtags", "WARN", f"{len(tags)} of {s['max_hashtags']}, but repeated: " + ", ".join("#" + d for d in dupes))
    else:
        add("hashtags", "PASS", f"{len(tags)} of {s['max_hashtags']}.")

    # 6. links
    links = [m.group(0).rstrip(".,!?)") for m in LINK_RE.finditer(text)]
    links = [l for l in links if not l.startswith("@")]
    if links and not allow_links:
        add("links", "FAIL", "Link in the caption: " + ", ".join(links[:3]) +
            ". Most accounts can't click caption links; point to the bio or a comment keyword instead.")
    elif links:
        add("links", "WARN", "Link kept on purpose (--allow-links): " + ", ".join(links[:3]))
    else:
        add("links", "PASS", "No link in the caption.")

    # 7. emoji
    clusters = emoji_clusters(text)
    wc = len(words(text)) or 1
    per100 = len(clusters) * 100 / wc
    run = longest_emoji_run(text, clusters)
    emoji_notes = []
    if per100 > s["emoji_per_100_words"]:
        emoji_notes.append(f"{len(clusters)} emoji in {wc} words ({per100:.1f} per 100, limit {s['emoji_per_100_words']})")
    if run >= 3:
        emoji_notes.append(f"{run} emoji in a row")
    if clusters and clusters[0][0] == len(text) - len(text.lstrip()) and fmt in ("post", "carousel"):
        emoji_notes.append("the caption opens with an emoji, which spends preview space on no words")
    if emoji_notes:
        add("emoji", "WARN", sentence_case("; ".join(emoji_notes)) + ".")
    else:
        add("emoji", "PASS", f"{len(clusters)} emoji in {wc} words.")

    return {
        "format": fmt,
        "text": text,
        "settings": s,
        "feed_preview": {"visible": feed_vis, "cut": feed_cut},
        "reel_preview": {"visible": reel_vis, "cut": reel_cut},
        "results": results,
        "failed": sum(r["status"] == "FAIL" for r in results),
        "warned": sum(r["status"] == "WARN" for r in results),
    }


def longest_emoji_run(text, clusters):
    best = run = 0
    prev_end = None
    for start, e in clusters:
        if prev_end is not None and text[prev_end:start].strip() == "":
            run += 1
        else:
            run = 1
        best = max(best, run)
        prev_end = start + len(e)
    return best


def find_ig_voice():
    """Look for an installed ig-voice skill next to this one. Never required."""
    here = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    candidates = [os.path.join(os.path.dirname(here), "ig-voice")]
    for root in ("~/.claude/skills", "~/.codex/skills", "~/.agents/skills"):
        candidates.append(os.path.join(os.path.expanduser(root), "ig-voice"))
    for c in candidates:
        if os.path.isfile(os.path.join(c, "SKILL.md")):
            return c
    return None


def render(report, handle, width):
    s = report["settings"]
    out = []
    main = "post" if report["format"] in ("post", "carousel") else "reel"
    feed_title = "Feed, photo or carousel" + (" (this post)" if main == "post" else "")
    reel_title = "Reels" + (" (this post)" if main == "reel" else "")
    fp, rp = report["feed_preview"], report["reel_preview"]
    order = [(feed_title, fp, s["feed_chars"], s["feed_lines"]), (reel_title, rp, s["reel_chars"], s["reel_lines"])]
    if main == "reel":
        order.reverse()
    out.append("What shows before \"... more\" (estimate):")
    for title, p, c, l in order:
        out.append(box(title, p["visible"], p["cut"], handle, width))
        nth = {1: "first", 2: "second", 3: "third"}.get(l, f"{l}th")
        out.append(f"  cut at {c} characters or the {nth} line break, whichever comes first")
    out.append("")
    out.append("Checks:")
    for r in report["results"]:
        out.append(f"  {r['status']:<4}  {r['check']:<15} {r['detail']}")
    out.append("")
    verdict = "ready to post" if report["failed"] == 0 else f"not ready: {report['failed']} failed"
    out.append(f"Result: {verdict}, {report['warned']} warning(s).")
    voice = find_ig_voice()
    out.append("ig-voice: " + (f"installed at {voice}; run it on this caption." if voice else "not installed, skipped."))
    out.append("")
    out.append("── copy below this line " + "─" * 20)
    out.append(report["text"])
    out.append("── copy above this line " + "─" * 20)
    return "\n".join(out)


def parse_keywords(values):
    out = []
    for v in values or []:
        out.extend(p.strip() for p in re.split(r"[,;\n]", v) if p.strip())
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check an Instagram caption before posting. Never posts.")
    ap.add_argument("file", help="caption as plain text, or - for stdin")
    ap.add_argument("--format", choices=["reel", "post", "carousel"], default="reel",
                    help="reel: the video carries the hook. post/carousel: the caption carries it.")
    ap.add_argument("--keywords", action="append", default=[],
                    help="what people would search to find this; comma-separated or repeated")
    ap.add_argument("--handle", default="", help="account name shown before the caption in the feed")
    ap.add_argument("--allow-links", action="store_true", help="the account can post clickable caption links")
    ap.add_argument("--script", help="the Reel script, optional: warns when the caption's ask differs from the script's")
    for key, val in DEFAULTS.items():
        ap.add_argument("--" + key.replace("_", "-"), type=type(val), default=None,
                        help=f"default {val}")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    args = ap.parse_args(argv)

    try:
        if args.file == "-":
            text = sys.stdin.read()
        else:
            with open(args.file, encoding="utf-8") as f:
                text = f.read()
    except OSError as e:
        print(f"check_caption: {e}", file=sys.stderr)
        return 2

    script = None
    if args.script:
        try:
            with open(args.script, encoding="utf-8") as f:
                script = f.read()
        except OSError as e:
            print(f"check_caption: {e}", file=sys.stderr)
            return 2

    settings = {k: getattr(args, k) for k in DEFAULTS}
    report = check(text, fmt=args.format, keywords=parse_keywords(args.keywords), handle=args.handle,
                   allow_links=args.allow_links, script=script, **settings)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        width = report["settings"]["box_width"]
        print(render(report, args.handle, width))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
