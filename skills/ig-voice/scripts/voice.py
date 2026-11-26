#!/usr/bin/env python3
"""
voice.py - make a draft sound like the creator who will post it.

Three commands, standard library only, nothing leaves the machine:

  learn  Read 5 to 10 of the creator's own captions or scripts and save a voice
         profile: their words and phrases, sentence length and its spread, how
         they open and close, contractions, person, emoji, swearing and
         punctuation habits.
  check  Clean one draft and report on it. Mechanical marks (invisible
         characters, odd spaces, curly quotes, dashes and ellipsis characters
         the creator never types, markdown Instagram would show literally) are
         fixed in the output. Sentence shapes and stock phrases that read as
         machine-written are listed for a rewrite, never rewritten here. With a
         profile, the lines that sound least like the creator are ranked, with
         the reasons.
  show   Print where the profile lives and what it says.

Usage
  python3 voice.py learn caption1.txt caption2.txt ...   (or a folder, or - for stdin;
                                                          one file may hold several samples
                                                          separated by a line of ---; a ---
                                                          above a footer is not a break)
  python3 voice.py learn --add more.txt                  (add samples, rebuild)
  python3 voice.py check draft.txt                       (report, then the cleaned text)
  python3 voice.py check draft.txt -o clean.txt --report report.md
  python3 voice.py check draft.txt --json
  python3 voice.py check - --kind dm < message.txt
  python3 voice.py show

The profile is ~/.config/ig-voice/voice.md ($XDG_CONFIG_HOME is honoured), or
the path in $IG_VOICE_PROFILE, or --profile. The samples it was built from are
kept beside it in samples/ so --add can rebuild from all of them.

Every check is a local heuristic. It points at lines worth a second look; it is
not an AI detector and predicts nothing about how any detector scores the text.
"""
import argparse
import json
import os
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patterns as P  # noqa: E402
import tells as TL  # noqa: E402  (shared with humanize; identical copy)

DISCLAIMER = ("These checks are local heuristics. They point at lines worth a second look. They are not "
              "an AI detector and say nothing about how any detector would score the text.")
KINDS = ("caption", "script", "dm", "comment")
MIN_SAMPLES = 5

# ---------------------------------------------------------------- characters

INVISIBLE = {
    "\u200b": "zero-width space", "\u200c": "zero-width non-joiner", "\u2060": "word joiner",
    "\ufeff": "byte-order mark", "\u00ad": "soft hyphen", "\u180e": "Mongolian vowel separator",
    "\u200e": "direction mark", "\u200f": "direction mark", "\u202a": "direction control",
    "\u202b": "direction control", "\u202c": "direction control", "\u202d": "direction control",
    "\u202e": "direction control", "\u2066": "direction control", "\u2067": "direction control",
    "\u2068": "direction control", "\u2069": "direction control",
}
ZWJ = "\u200d"  # joins emoji (family, flags); kept between emoji, removed elsewhere
ODD_SPACES = "\u00a0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF]")
CURLY = {"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
         "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"'}
EM, EN, ELLIPSIS = "\u2014", "\u2013", "\u2026"


def is_emojiish(ch):
    return bool(ch) and (EMOJI_RE.match(ch) is not None or ch in "\ufe0f\u20e3" or "\U0001F3FB" <= ch <= "\U0001F3FF")


# ---------------------------------------------------------------- text units

URL_TAG_RE = re.compile(r"https?://\S+|www\.\S+|[#@][\w.]+")
WORD_RE = re.compile(r"[A-Za-z0-9\u00c0-\u024f]+(?:['\u2019][A-Za-z]+)*")
SPLIT_RE = re.compile(r"(?<=[.!?\u2026])[\"')\]\u201d\u2019]*\s+")
LIST_MARK_RE = re.compile(r"^\s*(?:[-*\u2022>]+|\d+[.)])\s+")


def words(text):
    return WORD_RE.findall(URL_TAG_RE.sub(" ", text))


# A {{placeholder}} is one slot to fill, usually one figure or one name, so it counts
# as one word in sentence lengths, however many words describe it.
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]*\}\}")


def nwords(text):
    return len(words(PLACEHOLDER_RE.sub(" slot ", text)))


# ---- Spoken word count, for how long a script takes to say. The same rule, in the
# same words, is in ig-reel's scripts/reel.py and ig-script's scripts/timeline.py, so
# all three give the same length for the same lines; a test runs them side by side.
#   - Tokens are split on whitespace; punctuation at either end is dropped; a token with
#     no letter or digit is not said.
#   - A {{placeholder}} is one token and counts as one word, however many words it holds:
#     what goes there is usually one figure or one name.
#   - A figure counts as it is said: 1, plus 1 for a currency sign ($ EUR GBP), plus 1 for
#     %, plus 1 per thousands separator, plus 1 for a k/m/bn suffix. "$18,000" is
#     "eighteen thousand dollars": 3. "30%" is 2. "60" is 1.
SPOKEN_TOKEN = re.compile(r"\{\{[^{}]*\}\}|\S+")
EDGE_PUNCT = "\"'\u201c\u201d\u2018\u2019()[]<>.,;:!?\u2026*_"
LEAD_NUMBER = re.compile(r"^\s*(?:L?\d+[.):]\s+)")
WORDS_PER_SECOND = 2.5  # the default speaking rate of reel.py and timeline.py


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
            n += bool(re.search("[$\u20ac\u00a3]", tok)) + ("%" in tok)
            n += len(re.findall(r"\d,\d{3}", tok))
            n += bool(re.search(r"\d(?:k|m|bn|b)$", tok, re.I))
        out.append((tok, n))
    return out


def spoken_count(text):
    return sum(n for _, n in spoken_words(text))


def script_word_count(text):
    """Spoken words in a whole script, line by line, with line numbers ("1. ", "L2:")
    left out, as timeline.py reads a numbered script."""
    return sum(spoken_count(LEAD_NUMBER.sub("", ln).strip()) for ln in text.split("\n"))


def sentences(text):
    """(line number, sentence) for every sentence that has a word in it."""
    out = []
    for n, line in enumerate(text.split("\n"), 1):
        line = LIST_MARK_RE.sub("", line.strip())
        if not line:
            continue
        for piece in SPLIT_RE.split(line):
            piece = piece.strip()
            if words(piece):
                out.append((n, piece))
    return out


def low(text):
    return text.lower().replace("\u2019", "'")


def pct(values, q):
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * q
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def ends_with_question(s):
    s = s.rstrip()
    while s and (is_emojiish(s[-1]) or s[-1].isspace()):
        s = s[:-1]
    return s.endswith("?")


def opener_type(sentence):
    s = low(sentence).strip()
    w = words(s)
    first = w[0] if w else ""
    if ends_with_question(s):
        return "question"
    if first[:1].isdigit() or first in {"one", "two", "three", "four", "five", "six", "seven", "eight",
                                        "nine", "ten", "hundred", "thousand", "million", "billion"}:
        return "number"
    if first in {"i", "i'm", "i've", "i'd", "i'll", "my", "me"}:
        return "I"
    if first in {"you", "your", "you're", "you've", "you'll"}:
        return "you"
    return "statement"


def closer_type(sentence):
    s = low(sentence)
    if re.search(P.CALL_TO_ACTION, s):
        return "call to action"
    if ends_with_question(s):
        return "question"
    return "statement"


# ---------------------------------------------------------------- samples

def strip_frontmatter(text):
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if m and all(re.match(r"^[\w -]+:|^\s+-|^\s*$", ln) for ln in m.group(1).split("\n")):
        return text[m.end():]
    return text


def looks_like_footer(part):
    """True when a piece of text is a closing block, not a post: a few lines that are
    all hashtags, a mention or "Follow ..." line, or "link in bio"."""
    lines = [ln.strip() for ln in part.split("\n") if ln.strip()]
    return 0 < len(lines) <= FOOTER_TAIL and all(
        HASHTAG_LINE_RE.match(ln) or FOOTER_TEXT_RE.search(ln) or is_separator(ln) for ln in lines)


def split_samples(text):
    """The samples in one file. A line of only --- separates samples, unless what
    follows it is a closing footer ("Follow @...", hashtags): then the --- is the
    footer's separator, the same as a line of \u2014 or ___, and stays in the post."""
    text = strip_frontmatter(text.replace("\r\n", "\n"))
    parts = re.split(r"\n[ \t]*---[ \t]*\n", "\n" + text + "\n")
    out = []
    for p in parts:
        if out and looks_like_footer(p):
            out[-1] = out[-1].rstrip() + "\n\n---\n" + p.strip()
        elif words(p):
            out.append(p.strip())
    return out


def read_inputs(paths):
    samples = []
    for raw in paths:
        if raw == "-":
            samples += split_samples(sys.stdin.read())
            continue
        p = Path(raw).expanduser()
        files = sorted(f for f in p.iterdir() if f.suffix in (".txt", ".md")) if p.is_dir() else [p]
        for f in files:
            samples += split_samples(f.read_text(encoding="utf-8"))
    return samples


def tidy_sample(text):
    """Markdown and list marks out, so they do not count as the creator's punctuation."""
    text = re.sub(r"^\s*#{1,6}\s+.*$", "", text, flags=re.M)
    text = re.sub(r"\*\*|__|`", "", text)
    return text


# ---------------------------------------------------------------- footer

# Many creators end every caption with the same block: a separator line, a
# "Follow @..." line, a line of hashtags. That block is a posting habit, not
# their voice: counted as voice it teaches "uses em dashes" and fills "phrases
# they repeat" with the footer. learn finds it and records it apart; check
# accepts a draft that ends with it and leaves it out of the voice checks.
FOOTER_TAIL = 6          # how many non-blank lines at the end of a sample can be footer
HASHTAG_LINE_RE = re.compile(r"^(?:[#][\w.]+[\s,.]*)+$")
# A separator is a line of punctuation only: \u2014, \u2013, ---, ___, * * *, ~~~, a lone dot.
# All of them are the same footer line, so a creator who types \u2014 on one post and ---
# on another has one footer. Underscore counts, although regex calls it a word character.
SEPARATOR_RE = re.compile(r"^(?:[^\w\s#@]|_){1,12}$")
SEPARATOR_KEY = "sep"
FOOTER_TEXT_RE = re.compile(r"(?<![\w.])@[A-Za-z0-9._]+|^follow\b|\blink\s+in\s+(?:my\s+|the\s+)?bio\b", re.I)


def is_separator(line):
    t = line.replace(" ", "").strip()
    return bool(t) and bool(SEPARATOR_RE.match(t))


def normal_footer_keys(keys):
    """Footer keys from any profile version: older ones stored "sep:<the line>"."""
    return {SEPARATOR_KEY if k.startswith("sep:") else k for k in keys}


def footer_key(line):
    """A line as the footer matcher sees it: hashtag lines and separators by shape, the rest by text."""
    t = line.strip()
    if HASHTAG_LINE_RE.match(t):
        return "#hashtags"
    if is_separator(t):
        return SEPARATOR_KEY
    return re.sub(r"\s+", " ", low(t))


def footer_min_samples(n):
    return max(2, -(-n // 2))  # at least 2, and at least half the samples


def find_footer(samples):
    """The footer lines repeated at the end of the samples, as footer keys, plus how to show them."""
    counts, shown = Counter(), {}
    for text in samples:
        tail = [ln for ln in text.split("\n") if ln.strip()][-FOOTER_TAIL:]
        for ln in tail:
            k = footer_key(ln)
            shown.setdefault(k, ln.strip())
        counts.update({footer_key(ln) for ln in tail})
    need = footer_min_samples(len(samples))
    keys = {k for k, c in counts.items() if c >= need and len(samples) >= 2}
    # a footer is the end of the post, so every footer line has to be part of a
    # trailing run in at least `need` samples, not just appear near the end
    runs = Counter()
    for text in samples:
        body, foot = split_footer(text, keys)
        runs.update({footer_key(ln) for ln in foot.split("\n") if ln.strip()})
    keys = {k for k in keys if runs[k] >= need}
    return keys, shown


def split_footer(text, keys):
    """(body, footer): the footer is the run of trailing lines whose keys are all footer keys."""
    if not keys:
        return text, ""
    lines = text.rstrip().split("\n")
    cut = len(lines)
    while cut > 0 and (not lines[cut - 1].strip() or footer_key(lines[cut - 1]) in keys):
        cut -= 1
    if cut == len(lines) or cut == 0:
        return text, ""
    return "\n".join(lines[:cut]).rstrip(), "\n".join(lines[cut:]).strip("\n")


# ---------------------------------------------------------------- profile

def build_profile(samples):
    footer_keys, footer_shown = find_footer(samples)
    split = [split_footer(s, footer_keys) for s in samples]
    bodies = [b for b, _ in split]
    with_footer = sum(1 for _, f in split if f)
    # hashtags are a habit whether they sit in the footer or the body, so they
    # are counted on the whole post; everything else is counted on the body
    hashtags = [len(re.findall(r"#\w+", s)) for s in samples]
    texts = [tidy_sample(b) for b in bodies]
    all_sents, lengths, openers, closers = [], [], Counter(), Counter()
    emoji, word_bag, doc_words, doc_phrases = Counter(), Counter(), Counter(), Counter()
    doc_grams, doc_content = [], []
    contracted = uncontracted = swears = 0
    person = Counter()
    wps, lines = [], []
    for t in texts:
        sents = [s for _, s in sentences(t)]
        if not sents:
            continue
        all_sents += sents
        lengths += [len(words(s)) for s in sents]
        openers[opener_type(sents[0])] += 1
        closers[closer_type(sents[-1])] += 1
        lt = low(t)
        ws = [w.lower().replace("\u2019", "'") for w in words(t)]
        wps.append(len(ws))
        lines.append(len([ln for ln in t.split("\n") if ln.strip()]))
        emoji.update(ch for ch in t if EMOJI_RE.match(ch))
        contracted += len(re.findall(P.CONTRACTION_RE, lt))
        uncontracted += sum(len(re.findall(r"\b" + k + r"\b", lt)) for k in P.UNCONTRACTED)
        swears += len(re.findall(P.SWEARS, lt))
        for w in ws:
            if w in ("i", "me", "my", "i'm", "i've", "i'll", "i'd", "mine"):
                person["I"] += 1
            elif w in ("you", "your", "you're", "you've", "you'll", "yours"):
                person["you"] += 1
            elif w in ("we", "our", "us", "we're", "we've", "ours"):
                person["we"] += 1
        content = [w for w in ws if w not in P.STOPWORDS and len(w) > 2 and not w.isdigit()]
        word_bag.update(content)
        doc_words.update(set(content))
        grams = set()
        for n in (2, 3):
            for i in range(len(ws) - n + 1):
                g = ws[i:i + n]
                if not all(x in P.STOPWORDS for x in g) and not any(x.isdigit() for x in g):
                    grams.add(" ".join(g))
        doc_phrases.update(grams)
        doc_grams.append(grams)
        doc_content.append(set(content))
    raw = "\n".join(bodies)
    raw_tidy = "\n".join(texts)
    n = len(texts)
    total_words = sum(wps) or 1
    used_stock = sorted({rx for rx, _ in P.STOCK_PHRASES for s in all_sents if re.search(rx, low(s))}
                        | {rx for _, rx, *_ in TL.PHRASES for s in all_sents if re.search(rx, TL.norm(s), re.I)})
    used_formal = sorted({w for w in P.FORMAL_WORDS if w in word_bag or re.search(r"\b" + w + r"\b", low(raw))})
    phrases = [g for g, c in doc_phrases.most_common() if repeated_habit(g, c, doc_grams, doc_content)]
    # keep the longest phrase when a shorter one only ever appears inside it
    phrases = [g for g in phrases if not any(g != h and g in h and doc_phrases[h] == doc_phrases[g]
                                             for h in phrases)]
    kept = []  # "and i'll send", "i'll send you", "send you the" are one habit: keep the first
    for g in phrases:
        if not any(len(set(g.split()) & set(k.split())) >= 2 for k in kept):
            kept.append(g)
    phrases = kept[:15]
    sig_words = [w for w, c in sorted(doc_words.items(), key=lambda kv: (-kv[1], -word_bag[kv[0]], kv[0]))
                 if c >= 2][:25]
    nsent = len(all_sents) or 1
    return {
        "version": 1,
        "samples": n,
        "words_total": sum(wps),
        "words_per_sample": round(statistics.median(wps), 1) if wps else 0,
        "lines_per_sample": round(statistics.median(lines), 1) if lines else 0,
        "sentence_words": {
            "median": round(statistics.median(lengths), 1) if lengths else 0,
            "mean": round(statistics.mean(lengths), 1) if lengths else 0,
            "spread": round(statistics.pstdev(lengths), 1) if len(lengths) > 1 else 0,
            "p10": round(pct(lengths, 0.1), 1), "p90": round(pct(lengths, 0.9), 1),
            "longest": max(lengths) if lengths else 0,
        },
        "contraction_share": round(contracted / (contracted + uncontracted), 2) if contracted + uncontracted else None,
        "per_100_words": {k: round(person[k] * 100 / total_words, 1) for k in ("I", "you", "we")},
        "swears_per_100_words": round(swears * 100 / total_words, 2),
        "emoji_per_sample": round(sum(emoji.values()) / n, 1) if n else 0,
        "emoji_top": [e for e, _ in emoji.most_common(8)],
        "hashtags_per_sample": round(statistics.median([h for h in hashtags if h]), 1) if any(hashtags) else 0,
        "samples_with_hashtags": sum(1 for h in hashtags if h),
        "triples_per_100_words": round(sum(1 for x in all_sents if TRIPLE_RE.search(low(x))) * 100 / total_words, 2),
        "punctuation": {
            "em_dash": raw.count(EM),
            "en_dash": raw.count(EN),
            "spaced_hyphen": len(re.findall(r"\w - \w", raw_tidy)),
            "curly_quotes": sum(raw.count(c) for c in CURLY),
            "straight_quotes": raw.count("'") + raw.count('"'),
            "ellipsis_char": raw.count(ELLIPSIS),
            "three_dots": raw.count("..."),
            "semicolons": raw_tidy.count(";"),
            "colons": len(re.findall(r"\w:\s", raw_tidy)),
            "parentheses": raw_tidy.count("("),
            "exclaim_per_sentence": round(sum(s.count("!") for s in all_sents) / nsent, 2),
            "question_per_sentence": round(sum(s.count("?") for s in all_sents) / nsent, 2),
        },
        "lowercase_start_share": round(sum(1 for s in all_sents if s[:1].islower()) / nsent, 2),
        "openers": dict(openers),
        "closers": dict(closers),
        "signature_words": sig_words,
        "signature_phrases": phrases,
        "used_stock_patterns": used_stock,
        "used_formal_words": used_formal,
        "footer": {
            "lines": [("(a line of hashtags)" if k == "#hashtags" else footer_shown[k])
                      for k in sorted(footer_keys, key=lambda k: first_position(k, samples))],
            "keys": sorted(footer_keys),
            "samples_with_footer": with_footer,
        },
    }


def first_position(key, samples):
    for text in samples:
        for i, ln in enumerate(text.split("\n")):
            if ln.strip() and footer_key(ln) == key:
                return i - len(text.split("\n"))
    return 0


PHRASE_MIN_SAMPLES = 3


def repeated_habit(gram, count, doc_grams, doc_content):
    """A phrase is a habit when it shows up in 3 or more samples, or in 2 on clearly different subjects.

    Two posts on the same subject share their topic words ("claude code skill"), and that is
    the topic, not the voice. Different subjects: the two samples share under a fifth of their
    other content words.
    """
    if count >= PHRASE_MIN_SAMPLES:
        return True
    if count < 2:
        return False
    docs = [c for g, c in zip(doc_grams, doc_content) if gram in g]
    if len(docs) != 2:
        return False
    own = set(gram.split())
    a, b = docs[0] - own, docs[1] - own
    union = a | b
    return bool(union) and len(a & b) / len(union) < 0.2


def describe(prof):
    sw = prof["sentence_words"]
    pu = prof["punctuation"]
    cs = prof["contraction_share"]
    per = prof["per_100_words"]
    main_person = max(per, key=per.get) if any(per.values()) else "none"
    lines = [
        f"- Built from {prof['samples']} samples, {prof['words_total']} words, about "
        f"{prof['words_per_sample']:g} words each.",
        f"- Sentences: usually {sw['p10']:g} to {sw['p90']:g} words (median {sw['median']:g}, spread "
        f"{sw['spread']:g}, longest {sw['longest']}).",
        "- Contractions: " + ("no evidence either way" if cs is None else
                              f"{round(cs * 100)}% of the time when there is a choice"),
        f"- Person: mostly \"{main_person}\" (per 100 words: I {per['I']:g}, you {per['you']:g}, we {per['we']:g}).",
        "- Emoji: " + (f"about {prof['emoji_per_sample']:g} per sample, most used "
                       + " ".join(prof["emoji_top"][:5]) if prof["emoji_per_sample"] else "none"),
        "- Swearing: " + ("none" if not prof["swears_per_100_words"] else
                          f"{prof['swears_per_100_words']:g} per 100 words"),
        "- Hashtags: " + (f"about {prof['hashtags_per_sample']:g} in the {prof['samples_with_hashtags']} samples that "
                          "have any" if prof["samples_with_hashtags"] else "none"),
        "- Footer: " + (f"the same closing block in {prof['footer']['samples_with_footer']} of {prof['samples']} "
                        "samples (" + " / ".join(prof["footer"]["lines"]) + "). Kept as a posting habit, "
                        "not counted as voice; a draft may end with it."
                        if prof.get("footer", {}).get("lines") else "none repeated"),
        "- Punctuation: "
        + ", ".join([
            "uses em dashes" if pu["em_dash"] else "never an em dash",
            "mostly curly quotes" if pu["curly_quotes"] > pu.get("straight_quotes", 0) else "straight quotes",
            ("\u2026 character" if pu["ellipsis_char"] > pu["three_dots"] else "types ...")
            if pu["ellipsis_char"] + pu["three_dots"] else "no ellipsis",
            f"{pu['semicolons']} semicolons", f"{pu['exclaim_per_sentence']:g} ! per sentence",
            f"{pu['question_per_sentence']:g} ? per sentence",
        ]),
        f"- Starts sentences in lowercase: {round(prof['lowercase_start_share'] * 100)}% of the time.",
        "- Opens with: " + ", ".join(f"{k} {v}" for k, v in sorted(prof["openers"].items(), key=lambda kv: -kv[1])),
        "- Closes with: " + ", ".join(f"{k} {v}" for k, v in sorted(prof["closers"].items(), key=lambda kv: -kv[1])),
        "- Phrases they repeat: " + (", ".join(f'"{p}"' for p in prof["signature_phrases"][:10]) or "none yet"),
        "- Words they come back to: " + (", ".join(prof["signature_words"][:15]) or "none yet"),
    ]
    return "\n".join(lines)


def profile_markdown(prof):
    return ("# Voice profile (ig-voice)\n\n"
            "Built by `voice.py learn` from the creator's own posts. Rebuild it rather than editing the data "
            "block by hand; the summary is for reading.\n\n## Summary\n\n" + describe(prof)
            + "\n\n## Data\n\n```json\n" + json.dumps(prof, indent=1, ensure_ascii=False) + "\n```\n")


def profile_path(arg=None):
    if arg:
        return Path(arg).expanduser()
    if os.environ.get("IG_VOICE_PROFILE"):
        return Path(os.environ["IG_VOICE_PROFILE"]).expanduser()
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "ig-voice" / "voice.md"


def load_profile(path):
    if not path.exists():
        return None
    m = re.search(r"```json\n(.*?)\n```", path.read_text(encoding="utf-8"), re.S)
    if not m:
        raise SystemExit(f"{path} has no data block; rebuild it with: voice.py learn <samples>")
    return json.loads(m.group(1))


# ---------------------------------------------------------------- cleaning

def clean(text, prof=None, keep_markdown=False):
    """Fix mechanical marks. Returns (text, list of changes)."""
    changes = []
    pu = (prof or {}).get("punctuation", {})

    def note(what, count, why):
        if count:
            changes.append({"what": what, "count": count, "why": why})

    # invisible characters (keep a joiner that sits between two emoji)
    removed = Counter()
    out = []
    for i, ch in enumerate(text):
        if ch in INVISIBLE:
            removed[INVISIBLE[ch]] += 1
            continue
        if ch == ZWJ:
            prev = text[i - 1] if i else ""
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if not (is_emojiish(prev) and is_emojiish(nxt)):
                removed["zero-width joiner"] += 1
                continue
        out.append(ch)
    text = "".join(out)
    for name, c in removed.items():
        note(f"removed {name}", c, "invisible, survives copy-paste, and you never type it")

    n = sum(text.count(c) for c in ODD_SPACES)
    text = re.sub("[" + ODD_SPACES + "]", " ", text)
    note("non-breaking or special spaces made normal", n, "invisible difference you would not type on a phone")

    if not keep_markdown:
        before = text
        text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)
        text = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])", r"\1", text)
        text = re.sub(r"`([^`\n]+)`", r"\1", text)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.M)
        note("markdown markers removed", int(before != text), "Instagram shows asterisks and # headings as typed")

    if pu.get("curly_quotes", 0) <= pu.get("straight_quotes", 0):
        n = sum(text.count(c) for c in CURLY)
        for c, r in CURLY.items():
            text = text.replace(c, r)
        note("curly quotes made straight", n,
             "you mostly type straight quotes" if prof else "no profile; straight is what most people type")

    if pu.get("ellipsis_char", 0) <= pu.get("three_dots", 0):
        n = text.count(ELLIPSIS)
        text = text.replace(ELLIPSIS, "...")
        note("\u2026 made ...", n, "you type three dots" if prof else "no profile; three dots is the common way")

    if not pu.get("em_dash") and not pu.get("en_dash"):
        joint = " - " if pu.get("spaced_hyphen") else ", "
        n = text.count(EM) + text.count(EN)
        text = re.sub(r"(\d)\s*" + EN + r"\s*(\d)", r"\1-\2", text)
        text = re.sub(r"\s*[" + EM + EN + r"]\s*$", "...", text, flags=re.M)
        text = re.sub(r"^\s*[" + EM + EN + r"]\s*", "- ", text, flags=re.M)
        text = re.sub(r"\s*[" + EM + EN + r"]\s*", joint, text)
        text = re.sub(r",\s*([.,!?;:])", r"\1", text)
        note(f"dashes replaced with \"{joint.strip() or ','}\"", n,
             ("you never use an em dash" if prof else "em dashes are a well-known sign of AI text")
             + "; reread those lines, a full stop may read better")

    before = text
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.M)
    note("extra spaces removed", int(before != text), "tidy")
    return text, changes


# ---------------------------------------------------------------- checks

TRIPLE_RE = re.compile(r"\b[\w']+(?: [\w']+)?, [\w']+(?: [\w']+)?,? (and|or) [\w']+")


def shape_flags(sents, prof=None):
    """Sentence shapes that read as machine-written. {index: [reasons]}"""
    flags = {}

    def add(i, why):
        flags.setdefault(i, []).append(why)

    texts = [low(s) for _, s in sents]
    for i, s in enumerate(texts):
        if re.search(r"\b(it'?s|this is|that'?s|they'?re|you'?re|it is)\s+not\s+(just|only|about|merely)\b"
                     r"[^.!?]{0,60}[,;:]\s*(it'?s|this is|that'?s|they'?re|you'?re|it is|but)\b", s):
            add(i, 'contrast frame ("not just X, it\'s Y"): say the Y plainly')
        elif re.search(r"\bnot\s+(because|about|just|only)\b[^.!?]{1,50},\s*but\b", s):
            add(i, 'contrast frame ("not X, but Y"): say the Y plainly')
        if i and len(words(texts[i - 1])) <= 9 and re.search(r"\b(isn'?t|is not|aren'?t|wasn'?t|not)\b",
                                                             texts[i - 1]) \
                and re.match(r"(it'?s|it is|this is|that'?s|they'?re|we'?re)\b", s):
            add(i, 'two-step contrast ("This isn\'t X. It\'s Y."): one plain sentence is usually enough')
        if re.match(r"^(and |but )?(the|my|your|our|his|her|their) [\w' ]{1,25}\?$", s) and i + 1 < len(texts):
            add(i, 'set-up question answered by the next line ("The result? ..."): just say it')
        if re.match(r"^(here'?s|this is|the (secret|truth|trick|answer|reason|lesson|catch)) ?[\w' ]{0,20}:\s", s):
            add(i, 'colon reveal ("Here\'s the truth: ..."): drop the set-up')
        if re.match(r"^whether you'?re\b", s):
            add(i, '"Whether you\'re X or Y" opener: name the one person this is for')
        if re.match(r"^from [\w' ]{1,30} to [\w' ]{1,30},", s):
            add(i, '"From X to Y," sweep: say the one thing that matters')
    # runs: three or more very short sentences in a row, "No X. No Y. Just Z."
    run = []
    for i, s in enumerate(texts + ["placeholder sentence that ends a run"]):
        if len(words(s)) <= 2:
            run.append(i)
            continue
        if len(run) >= 3:
            for j in run:
                add(j, "string of one- or two-word sentences: reads as ad copy, merge into one line")
        run = []
    for i in range(len(texts) - 2):
        if texts[i].startswith("no ") and texts[i + 1].startswith("no ") and texts[i + 2].startswith("just "):
            add(i + 2, '"No X. No Y. Just Z." pattern: say what it is')
    # strong shapes from the shared list (humanize's tells.py), where this file has no flag of its own
    for i, hs in TL.find_shapes([s for _, s in sents]).items():
        for h in hs:
            if h["strength"] == TL.STRONG and i not in flags:
                add(i, h["hint"])
    triples = [i for i, s in enumerate(texts) if TRIPLE_RE.search(s)]
    total = sum(len(words(s)) for s in texts) or 1
    usual = (prof or {}).get("triples_per_100_words")
    too_many = len(triples) >= 3 and (usual is None or len(triples) * 100 / total > usual * 2)
    if too_many:
        for i in triples:
            add(i, "list of three again: this many in one draft is a pattern"
                + (" (more than twice your usual)" if usual is not None else "") + "; cut one or break it up")
    return flags


def phrase_flags(sents, prof):
    used = set((prof or {}).get("used_stock_patterns", []))
    flags = {}
    for i, (_, s) in enumerate(sents):
        for rx, why in P.STOCK_PHRASES:
            if rx in used:
                continue
            m = re.search(rx, low(s))
            if m:
                flags.setdefault(i, []).append(f'"{m.group(0).strip()}" ({why})')
        # the strong tells from the shared list that patterns.py does not already catch
        seen = " ".join(flags.get(i, [])).lower()
        for h in TL.find_phrases(s, skip=used):
            if h["strength"] == TL.STRONG and h["group"] != "stock" and h["match"].lower() not in seen:
                flags.setdefault(i, []).append(f'"{h["match"]}" ({h["hint"]})')
                seen += " " + h["match"].lower()
    return flags


def voice_flags(sents, prof, kind):
    """Per-sentence reasons a line does not sound like the creator. {index: [(weight, reason)]}"""
    out = {}

    def add(i, w, why):
        out.setdefault(i, []).append((w, why))

    used_formal = set((prof or {}).get("used_formal_words", []))
    cs = (prof or {}).get("contraction_share")
    sw = (prof or {}).get("sentence_words")
    pu = (prof or {}).get("punctuation", {})
    per = (prof or {}).get("per_100_words", {})
    for i, (_, s) in enumerate(sents):
        ls = low(s)
        n = nwords(s)
        for w in sorted(set(re.findall(r"[a-z]+", ls))):
            if w in P.FORMAL_WORDS and w not in used_formal:
                add(i, 2, f'"{w}" is report language (try "{P.FORMAL_WORDS[w]}")'
                    + (", and it is not in your samples" if prof else ""))
        for long_form, short in P.UNCONTRACTED.items():
            if re.search(r"\b" + long_form + r"\b", ls):
                if prof is None or cs is None:
                    add(i, 1, f'"{long_form}" where most people say "{short}"')
                elif cs >= 0.6:
                    add(i, 2, f'"{long_form}": you write "{short}" ({round(cs * 100)}% of the time you contract)')
        if prof and sw and kind in ("caption", "script"):
            hi = max(sw["p90"] * 1.3, sw["p90"] + 4)
            lo_ = sw["p10"]
            if n > hi:
                add(i, 2 if n < hi * 1.5 else 3, f"{n} words; your sentences run {sw['p10']:g} to {sw['p90']:g}")
            elif lo_ >= 6 and n < lo_ / 2 and n > 0:
                add(i, 1, f"{n} words; you rarely go under {lo_:g}")
        elif not prof and n > 30:
            add(i, 1, f"{n} words in one sentence; long for a post")
        if prof:
            if ";" in s and not pu.get("semicolons"):
                add(i, 2, "semicolon, which you never use")
            if "!" in s and not pu.get("exclaim_per_sentence"):
                add(i, 1, "exclamation mark, which you never use")
            if re.search(r"\w:\s", s) and not pu.get("colons"):
                add(i, 1, "colon, which you never use")
            if EMOJI_RE.search(s) and not prof.get("emoji_per_sample"):
                add(i, 1, "emoji, and you never use them")
            if re.search(P.SWEARS, ls) and not prof.get("swears_per_100_words"):
                add(i, 1, "swearing, which you never do")
            if s[:1].isupper() and prof.get("lowercase_start_share", 0) >= 0.8:
                add(i, 1, "capital at the start; you write in lowercase")
            if re.search(r"\b(we|our|us)\b", ls) and per.get("we", 0) < 0.3 and per.get("I", 0) >= 1:
                add(i, 1, '"we/our"; you talk as "I"')
            if pu.get("em_dash") == 0 and EM in s:
                add(i, 1, "em dash")
    return out


def draft_notes(text, sents, prof, kind):
    notes = []
    lengths = [nwords(s) for _, s in sents]
    if len(lengths) >= 5:
        spread = statistics.pstdev(lengths)
        ref = (prof or {}).get("sentence_words", {}).get("spread")
        if (ref and spread < ref * 0.5 and spread < 4) or (not ref and spread < 2.5):
            notes.append(f"Sentences are all about the same length (spread {spread:.1f} words"
                         + (f"; yours is {ref:g}" if ref else "") + "). Mix in a short one and a longer one.")
    emoji_starts = [ln for ln in text.split("\n") if EMOJI_RE.match(ln.strip()[:1])]
    if len(emoji_starts) >= 3:
        notes.append(f"{len(emoji_starts)} lines start with an emoji bullet, a layout common in generated posts.")
    if not prof or kind in ("dm", "comment") or not sents:
        return notes
    n = prof["samples"]
    op, cl = opener_type(sents[0][1]), closer_type(sents[-1][1])
    if n >= MIN_SAMPLES and prof["openers"].get(op, 0) == 0:
        usual = max(prof["openers"], key=prof["openers"].get)
        notes.append(f'Opens with "{op}"; you never open that way in {n} samples (most often: {usual}).')
    if n >= MIN_SAMPLES and prof["closers"].get(cl, 0) == 0:
        usual = max(prof["closers"], key=prof["closers"].get)
        notes.append(f'Ends with a {cl}; you never end that way in {n} samples (most often: {usual}).')
    emo = len(EMOJI_RE.findall(text))
    if prof["emoji_per_sample"] >= 1 and emo == 0:
        notes.append(f"No emoji; you use about {prof['emoji_per_sample']:g} per post "
                     f"({' '.join(prof['emoji_top'][:4])}).")
    elif emo > max(3, prof["emoji_per_sample"] * 2.5):
        notes.append(f"{emo} emoji; " + (f"you use about {prof['emoji_per_sample']:g} per post."
                                         if prof["emoji_per_sample"] else "you don't use emoji."))
    tags = len(re.findall(r"#\w+", text))
    if tags > prof["hashtags_per_sample"] * 2 + 3 or (tags and not prof.get("samples_with_hashtags", 1)):
        notes.append(f"{tags} hashtags; " + (f"you use about {prof['hashtags_per_sample']:g}."
                                             if prof["hashtags_per_sample"] else "your samples have none."))
    total = nwords(text)
    if kind == "caption" and prof["words_per_sample"] and total > prof["words_per_sample"] * 2.2:
        notes.append(f"{total} words; your posts run about {prof['words_per_sample']:g}.")
    if prof["swears_per_100_words"] >= 0.3 and not re.search(P.SWEARS, low(text)):
        notes.append("You swear now and then and this has none. Fine if that is the tone you want here.")
    return notes


def footer_status(footer, keys):
    """How much of the profile's footer a draft ends with: "usual" (every line of it,
    hashtags aside), "partial", "hashtags" (only a line of hashtags), or "" (none)."""
    if not footer:
        return ""
    have = {footer_key(ln) for ln in footer.split("\n") if ln.strip()}
    core = {k for k in keys if k != "#hashtags"}
    if core and core <= have:
        return "usual"
    if have & core:
        return "partial"
    return "hashtags" if have == {"#hashtags"} else "partial"


FOOTER_SENTENCE = {
    "usual": "Ends with your usual footer, which is left as it is and not checked as voice.",
    "partial": "Ends with part of your usual footer, without {missing}; it is left as it is and not checked "
               "as voice. Add the rest if you meant to post it.",
    "hashtags": "Ends with a line of hashtags, left as it is and not checked as voice; your usual footer "
                "is not there.",
}


def draft_summary(text, sents, kind, footer, status="usual", missing="", raw=None):
    """One line that is always in the Whole draft section, whatever the kind."""
    lengths = [nwords(s) for _, s in sents]
    if kind == "script":
        # the same spoken count as reel.py and timeline.py, so the lengths agree
        # on the text as written: cleaning can split "word\u2014word" into two tokens
        total = script_word_count(text if raw is None else raw)
    else:
        total = nwords(text)
    bits = [f"{total} words in {len(sents)} sentence{'s' if len(sents) != 1 else ''}"]
    if lengths:
        bits.append(f"sentences {min(lengths)} to {max(lengths)} words")
    if kind == "script":
        # spoken, so length is time, at the same rate as ig-reel and ig-script
        bits.append(f"about {round(total / WORDS_PER_SECOND)} seconds spoken at "
                    f"{WORDS_PER_SECOND:g} words a second")
    else:
        hashtags = len(re.findall(r'#\w+', text))  # outside the f-string: a backslash there needs Python 3.12
        bits.append(f"{len(EMOJI_RE.findall(text))} emoji, {hashtags} hashtags")
    line = ", ".join(bits) + "."
    if footer and status:
        line += " " + FOOTER_SENTENCE[status].format(missing=missing or "some of it")
    return line


def check(text, prof=None, kind="caption", keep_markdown=False, top=5):
    text = text.replace("\r\n", "\n")
    keys = normal_footer_keys(((prof or {}).get("footer") or {}).get("keys", []))
    body, footer = split_footer(text, keys)
    status = footer_status(footer, keys)
    have = {footer_key(ln) for ln in footer.split("\n") if ln.strip()}
    missing = ", ".join("the separator line" if k == SEPARATOR_KEY else f'"{k}"'
                        for k in sorted(keys - have - {"#hashtags"}))
    cleaned, changes = clean(body, prof, keep_markdown)
    sents = sentences(cleaned)
    if footer:
        end = text.rstrip()
        gap = end[len(body):len(end) - len(footer)]
        footer = "".join(ch for ch in footer if ch not in INVISIBLE)
        cleaned = cleaned.rstrip() + gap + footer + ("\n" if text.endswith("\n") else "")
    shapes = shape_flags(sents, prof)
    phrases = phrase_flags(sents, prof)
    voice = voice_flags(sents, prof, kind)
    lines = cleaned.split("\n")
    rewrite = []  # one entry per line, so "No X. No Y. Just Z." reads as one item
    for i in sorted(set(shapes) | set(phrases)):
        reasons = shapes.get(i, []) + phrases.get(i, [])
        if rewrite and rewrite[-1]["line"] == sents[i][0]:
            rewrite[-1]["sentence"] += " " + sents[i][1]
            rewrite[-1]["reasons"] += [r for r in reasons if r not in rewrite[-1]["reasons"]]
        else:
            rewrite.append({"line": sents[i][0], "sentence": sents[i][1], "reasons": reasons,
                            "line_text": lines[sents[i][0] - 1].strip()})
    ranked = []
    for i, reasons in voice.items():
        score = sum(w for w, _ in reasons)
        if score >= 2 or not prof:
            ranked.append({"line": sents[i][0], "sentence": sents[i][1], "score": score,
                           "reasons": [r for _, r in sorted(reasons, key=lambda x: -x[0])]})
    ranked.sort(key=lambda r: (-r["score"], r["line"]))
    return {
        "profile": bool(prof),
        "kind": kind,
        "cleaned": cleaned,
        "fixed": changes,
        "rewrite": rewrite,
        "unlike_you": ranked[:top],
        "draft": draft_notes(cleaned, sents, prof, kind),
        "draft_summary": draft_summary(cleaned, sents, kind, footer, status, missing, raw=text),
        "footer": footer,
        "footer_status": status,
        "your_words": {"phrases": (prof or {}).get("signature_phrases", [])[:10],
                       "words": (prof or {}).get("signature_words", [])[:15]},
        "sentences": len(sents),
        "note": DISCLAIMER,
    }


def render(res, profile_label, include_text=True):
    out = ["# ig-voice report", ""]
    if res["profile"]:
        out.append(f"Checked against your voice profile ({profile_label}).")
    else:
        out.append("No voice profile, so this is checked against a general list only. It works much better "
                   "with one: run `voice.py learn` on 5 to 10 of your own past captions or scripts.")
    out += ["", f"## Fixed automatically ({sum(c['count'] for c in res['fixed'])})", ""]
    out += [f"- {c['what']}: {c['count']} ({c['why']})" for c in res["fixed"]] or ["- nothing to fix"]
    out += ["", f"## Rewrite these ({len(res['rewrite'])})", "",
            "Sentence shapes and stock phrases that read as machine-written. Rewrite them in your own words; "
            "they are not changed automatically.", ""]
    for k, r in enumerate(res["rewrite"], 1):
        out.append(f"{k}. line {r['line']}: \"{r['line_text']}\"")
        out += [f"   - {why}" for why in r["reasons"]]
    if not res["rewrite"]:
        out.append("- none found")
    title = "Least like you" if res["profile"] else "Other lines to look at"
    out += ["", f"## {title} ({len(res['unlike_you'])})", ""]
    for k, r in enumerate(res["unlike_you"], 1):
        out.append(f"{k}. line {r['line']}: \"{r['sentence']}\"")
        out += [f"   - {why}" for why in r["reasons"]]
    if not res["unlike_you"]:
        out.append("- none stand out")
    # every report has this section, for scripts, DMs and comments too: the
    # summary line is always there, the notes only when something stands out
    out += ["", "## Whole draft", "", f"- {res.get('draft_summary', '')}"]
    out += [f"- {n}" for n in res["draft"]] or ["- nothing else stands out"
                                                 + (" against how you usually open and close" if res["profile"]
                                                    and res["kind"] in ("caption", "script") else "")]
    yw = res["your_words"]
    if yw["phrases"] or yw["words"]:
        out += ["", "## Your words, for the rewrite", ""]
        if yw["phrases"]:
            out.append("- phrases you repeat: " + ", ".join(f'"{p}"' for p in yw["phrases"]))
        if yw["words"]:
            out.append("- words you come back to: " + ", ".join(yw["words"]))
    out += ["", res["note"]]
    if include_text:
        out += ["", "## Cleaned text", "", "```text", res["cleaned"].rstrip("\n"), "```"]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- commands

def cmd_learn(a):
    path = profile_path(a.profile)
    sdir = path.parent / "samples"
    new = read_inputs(a.inputs)
    old = []
    if a.add and sdir.is_dir():
        old = [f.read_text(encoding="utf-8") for f in sorted(sdir.glob("*.txt"))]
    samples = old + [s for s in new if s not in old]
    if not samples:
        raise SystemExit("no text found in the inputs")
    prof = build_profile(samples)
    path.parent.mkdir(parents=True, exist_ok=True)
    sdir.mkdir(exist_ok=True)
    for f in sdir.glob("*.txt"):
        f.unlink()
    for k, s in enumerate(samples, 1):
        (sdir / f"{k:03d}.txt").write_text(s + "\n", encoding="utf-8")
    path.write_text(profile_markdown(prof), encoding="utf-8")
    print(f"Saved {path} from {len(samples)} samples.\n")
    print(describe(prof))
    if len(samples) < MIN_SAMPLES:
        print(f"\nOnly {len(samples)} samples: the profile will be rough. 5 to 10 is the useful range.")
    elif len(samples) > 20:
        print("\nMore than 20 samples is fine, but older posts may not sound like you now.")


def cmd_check(a):
    text = sys.stdin.read() if a.draft == "-" else Path(a.draft).expanduser().read_text(encoding="utf-8")
    path = profile_path(a.profile)
    prof = None if a.no_profile else load_profile(path)
    res = check(text, prof, a.kind, a.keep_markdown, a.top)
    label = str(path).replace(str(Path.home()), "~")
    if a.out:
        Path(a.out).expanduser().write_text(res["cleaned"], encoding="utf-8")
    # write every requested output first, then decide the exit status, so
    # --json never skips --report or --strict
    report = render(res, label, include_text=not a.out)
    if a.report:
        Path(a.report).expanduser().write_text(report, encoding="utf-8")
    if a.json:
        print(json.dumps(res, indent=1, ensure_ascii=False))
    elif not a.report:
        sys.stdout.write(report)
    if a.strict and (res["rewrite"] or res["unlike_you"]):
        sys.exit(2)


def cmd_show(a):
    path = profile_path(a.profile)
    prof = load_profile(path)
    if not prof:
        print(f"No profile at {path}. Build one: voice.py learn <5 to 10 of your captions or scripts>")
        return
    print(f"{path}\n")
    print(describe(prof))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make a draft sound like you, not like AI. Local heuristics only.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("learn", help="build the voice profile from your own captions or scripts")
    lp.add_argument("inputs", nargs="+", help="files, folders, or - for stdin; --- on its own line separates samples")
    lp.add_argument("--add", action="store_true", help="add to the saved samples instead of replacing them")
    lp.add_argument("--profile", help="profile path (default $IG_VOICE_PROFILE or ~/.config/ig-voice/voice.md)")
    lp.set_defaults(fn=cmd_learn)
    cp = sub.add_parser("check", help="clean a draft and report what does not sound like you")
    cp.add_argument("draft", help="draft file, or - for stdin")
    cp.add_argument("--kind", choices=KINDS, default="caption")
    cp.add_argument("-o", "--out", help="write the cleaned text here (the report then leaves it out)")
    cp.add_argument("--report", help="write the report here instead of stdout")
    cp.add_argument("--json", action="store_true", help="everything as JSON on stdout")
    cp.add_argument("--profile", help="profile path")
    cp.add_argument("--no-profile", action="store_true", help="ignore any saved profile")
    cp.add_argument("--keep-markdown", action="store_true", help="leave **bold**, `code` and # headings alone")
    cp.add_argument("--top", type=int, default=5, help="how many least-like-you lines to list (default 5)")
    cp.add_argument("--strict", action="store_true", help="exit 2 when any line is listed for a rewrite")
    cp.set_defaults(fn=cmd_check)
    sp = sub.add_parser("show", help="print the saved profile")
    sp.add_argument("--profile", help="profile path")
    sp.set_defaults(fn=cmd_show)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
