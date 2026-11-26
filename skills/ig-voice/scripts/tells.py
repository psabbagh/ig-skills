"""
tells.py - habits that make text read as machine-written, ranked by strength.

Shared by the humanize and ig-voice skills as an identical copy (a test in each fails when the two
drift). Plain data plus a few functions, standard library only, Python 3.9.

Built on Wikipedia's "Signs of AI writing" guide (WikiProject AI Cleanup), checked section by section
against revision 1387041075 on 2026-11-25; humanize/references/tells.md maps each section to an entry.
The entries and their wording are ours.

Every habit here is something a careful writer can also do on purpose, so each one carries a
strength:

- "strong": rare in careful human writing. One sighting is worth a rewrite.
- "weak":   common enough in human writing that one sighting means nothing. Only worth listing when
            other tells sit in the same paragraph, or when the text is full of it.

Matching is per sentence, case-insensitive, after curly apostrophes are made straight. Each entry is
(key, regex, strength, group, hint). The hint says what to do instead, in plain words.
"""
import re

STRONG = "strong"
WEAK = "weak"

GROUPS = {
    "staging": "signals importance instead of adding a fact",
    "rhythm": "a shape applied by rule, whether or not the meaning asks for it",
    "inflation": "an ordinary fact dressed up as pivotal, expert-backed or for sale",
    "leftover": "left over from a chat or a draft, never meant for the reader",
    "stock": "a stock line: fine once, a tell when several gather",
}

PHRASES = [
    # ---- staging: closers that repeat instead of adding
    ("closer", r"^(and )?(that'?s|that is|this is) (the|what) (real |whole |actual )?"
               r"(win|point|difference|magic|key|secret|lesson|game|unlock)\s*[.!]?$", STRONG, "staging",
     "a closer that restates the point: cut it, or replace it with the consequence"),
    ("closer", r"^(that|this|the) (distinction|difference|detail|nuance|part) matters\b", STRONG, "staging",
     "a closer that only asks the reader to pause: cut it, or say why it matters"),
    ("closer", r"\blet that sink in\b|\bread that again\b|\bsit with that\b", STRONG, "staging",
     "a pause command: cut it"),
    ("closer", r"^the (message|lesson|takeaway|verdict) (was|is) (clear|simple)\b", STRONG, "staging",
     "names what the example already showed: cut it"),
    ("closer", r"^(it|this|that) (was|is) a (lesson|reminder|masterclass|study) (in|of|that)\b", STRONG, "staging",
     "names what the example already showed: cut it"),
    ("closer", r"\band that changes everything\b|\bthat'?s the whole (game|point|trick)\b", STRONG, "staging",
     "a closer that adds weight, not a fact: cut it"),
    ("closer", r"^(overall|ultimately|in the end),", WEAK, "staging",
     "a closing verdict: keep it only if it says something the paragraph didn't"),

    # ---- staging: sayings that sound deep
    ("saying", r"\bthe real (question|issue|problem|story|work|test|challenge|risk|answer) (is|was|isn'?t)\b",
     STRONG, "staging", "dresses a plain point as a hidden truth: state the point"),
    ("saying", r"\bat (its|the|their|our) (core|heart)\b", STRONG, "staging",
     "dresses a plain point as a hidden truth: state the point"),
    ("saying", r"\bwhat (really|truly|actually) matters\b|\bthe heart of the matter\b", STRONG, "staging",
     "dresses a plain point as a hidden truth: say what matters and why"),
    ("saying", r"\bthe deeper (issue|truth|question|problem|lesson)\b", STRONG, "staging",
     "dresses a plain point as a hidden truth: state the point"),
    ("saying", r"\bis the (language|currency|architecture|grammar|operating system|oxygen) of\b", STRONG,
     "staging", "an aphorism ('X is the language of Y'): say the specific claim"),
    ("saying", r"\bnot an? \w+,? but an? (mirror|lens|window|map|compass|multiplier)\b", STRONG, "staging",
     "an aphorism: say what it actually does"),
    ("saying", r"^(fundamentally|in reality|in truth),", WEAK, "staging",
     "a run-up to a 'truth': usually cut the word"),

    # ---- staging: run-ups before the point
    ("run-up", r"^let'?s (dive|jump|dig) (in|into|right in)\b|^let'?s (explore|unpack)\b"
               r"|^let'?s break (this|it) down\b", STRONG, "staging", "announces the point: make it instead"),
    ("run-up", r"\bhere'?s (what you need to know|the thing|the deal|the kicker|the truth|the catch)\b",
     STRONG, "staging", "announces the point: make it instead"),
    ("run-up", r"^without further ado\b|^buckle up\b|^picture this\b|^imagine a world\b", STRONG, "staging",
     "announces the point: make it instead"),
    ("run-up", r"^(real talk|let'?s be honest|the thing is|truth be told|hot take)\b", STRONG, "staging",
     "staged candor before a routine claim: drop it and say the claim"),
    ("run-up", r"^(honestly|look|seriously)\?", STRONG, "staging",
     "staged candor ('Honestly?'): drop it and say the claim"),
    ("run-up", r"^the (hard|tricky|interesting|surprising|new|best|worst|scary|wild|crazy|fun) part"
               r"( is|\?|:)", STRONG, "staging", "'the hard part is X' stages X: name X directly"),
    ("run-up", r"\bwhat (nobody|no one) (tells|told|warns|warned) you\b|\b(nobody|no one) talks about\b"
               r"|\bthe (secret|truth|thing) (nobody|no one)\b", STRONG, "staging",
     "promises a secret before an ordinary point: make the point"),
    ("run-up", r"\bthe part (that|worth|nobody|no one)\b", STRONG, "staging",
     "'the part' stands in for a thing the text never names: name it"),
    ("run-up", r"^i'?m (so |really )?(thrilled|excited|delighted|proud|happy) to (announce|share|introduce)\b",
     STRONG, "staging", "an announcement run-up: start with what is new"),
    ("run-up", r"^in today'?s (fast[- ]paced|digital|modern|ever[- ]changing) (world|age|landscape)\b"
               r"|^in a world where\b", STRONG, "staging", "a stock opener: start at the second half"),
    ("run-up", r"^(honestly|look),|^(quick note|heads up|fun fact)[:,!]", WEAK, "staging",
     "an opener before the point: often fine, cut it if the text has other tells"),

    # ---- staging: arguing with no one
    ("strawman", r"^(this|it) (isn'?t|is not) (really |mainly |just |only )?about\b", STRONG, "staging",
     "answers an objection nobody raised: state what it is about"),
    ("strawman", r"^none of this (means|is to say)\b", STRONG, "staging",
     "heads off a conclusion nobody drew: cut it, keep any real claim"),
    ("strawman", r"^i'?m not saying\b|^don'?t get me wrong\b|^this is not to say\b|^that'?s not to say\b",
     STRONG, "staging", "defends against a claim nobody made: cut it, keep any real claim"),
    ("strawman", r"\b(a|one|the) (tempting|obvious|naive|natural|easy) (approach|option|answer|fix|move) "
                 r"(would be|is to|might be)\b|\bone might be tempted\b|\bit would be easy to\b", STRONG,
     "staging", "rejects an option the reader never weighed: cut it"),
    ("strawman", r"\byou (might|may|could) (think|assume|be tempted)\b", STRONG, "staging",
     "argues with a belief the reader may not hold: say the point"),
    ("strawman", r"^to be clear,", WEAK, "staging",
     "fine when it corrects a real misreading; otherwise cut"),

    # ---- rhythm: stacked qualifiers and hyphen pairs
    ("hedge", r"\bcould potentially\b|\bmight (arguably|possibly|potentially)\b|\bmay potentially\b"
              r"|\bcould possibly\b", STRONG, "rhythm", "stacked qualifiers: keep one, or none"),
    ("hedge", r"\bit'?s (also )?possible that\b|\bin some cases,? (it )?may\b|^to be fair,|\barguably\b",
     WEAK, "rhythm", "a hedge: keep it only if the doubt is real"),
    ("hyphen", r"\b(is|are|was|were|be|been|seems?|looks?|feels?) (high|well|long|low|short|real|full)-"
               r"(quality|known|documented|term|time|level|length|established|designed)\b", WEAK, "rhythm",
     "a hyphen after the noun ('is high-quality'): drop it ('is high quality')"),

    # ---- inflation: words models use far more than people do
    ("ai-word", r"\bdelv(e|es|ed|ing)\b|\btapestry\b|\btestament\b|\bintricacies\b|\binterplay\b"
                r"|\bgarner(s|ed|ing)?\b|\bunderscor(ed|ing)\b|\bunderscores? (the|that|how|why|what|its|their|our|a|an)\b"
                r"|\bshowcas(e|es|ed|ing)\b"
                r"|\bmeticulous(ly)?\b|\bbolster(s|ed|ing)?\b", STRONG, "inflation",
     "a word models use far more than people: use the everyday word"),
    ("ai-word", r"\bpivotal\b|\bcrucial\b|\bvibrant\b|\benduring\b|\brobust\b|\benhanc(e|es|ed|ing)\b"
                r"|\bvaluable\b|\bseamless(ly)?\b|\b(realm|landscape) of\b|\bever[- ]evolving\b"
                r"|\bnavigat(e|ing) the (complex|world|landscape)\w*|\bembark(s|ed|ing)? on\b"
                r"|\balign(s|ed)? with\b|\bquietly\b|\bfoster(s|ed|ing)?\b|\bholistic\b"
                r"|\bin the realm\b|\bkey (takeaway|insight|factor|role)s?\b|\bvaluable insights?\b"
                r"|\bresonat(e|es|ed|ing) with\b|\bdeep dive\b|\bmultifaceted\b|\bdependable\b"
                r"|\bleverag(e|es|ed|ing)\b|\bprioriti[sz](e|es|ed|ing)\b|\buniversally\b"
                r"|\b(was|were|is|are) echoed by\b", WEAK, "inflation",
     "a word models overuse: fine once, a tell in a cluster"),

    # ---- inflation: significance
    ("significance", r"\b(stands|serves) as an? (testament|reminder|symbol|beacon)\b"
                     r"|\b(marks|marking|marked) (a|an) (pivotal|crucial|key|significant|major|turning|new) "
                     r"(moment|point|step|milestone|chapter|shift|era)\b", STRONG, "inflation",
     "says an ordinary fact marks a turning point: keep the fact, drop the significance"),
    ("significance", r"\b(has|have|had) (shaped|sparked|generated|prompted|fueled|fuelled|informed) (broader |"
                     r"ongoing |public |emerging )?(conversations?|discussions?|debates?|reflection)\b"
                     r"|\brepresent(s|ed)? an? (significant |major |broader )?shift\b"
                     r"|\bcontribut(es|ed|ing) to the (broader|wider|rich|ongoing)\b|\bthe wider history of\b",
     STRONG, "inflation", "places the subject in a 'broader' story it doesn't need: keep the fact"),
    ("significance", r"\bplays? an? (crucial|vital|key|pivotal|significant|important|central) role\b",
     STRONG, "inflation", "'plays a key role': say what it does"),
    ("significance", r"\bsets? the stage\b|\bsetting the stage\b|\bpav(e|es|ed|ing) the way\b"
                     r"|\breflects? an? (broader|wider|larger|growing) (trend|shift|movement)\b"
                     r"|\b(enduring|lasting|indelible) (legacy|mark|impact)\b"
                     r"|\b(evolving|ever-changing|shifting) landscape\b", STRONG, "inflation",
     "promises a legacy or a future: end on the last concrete fact"),
    ("significance", r"\bthe future (looks|is) bright\b|\bexciting times (lie )?ahead\b"
                     r"|\bthe future is (here|now)\b|\bdespite (these|its|their|the) challenges\b"
                     r"|\bfaces? (several|many|numerous|new|significant|a number of) challenges\b",
     STRONG, "inflation", "a stock closing paragraph: cut it, end on a fact or a real plan"),
    ("significance", r"\ba step in the right direction\b|\bgame[- ]?chang(er|ing)\b", WEAK, "inflation",
     "a stock verdict: say what changed"),

    # ---- inflation: shallow -ing tails
    ("ing-tail", r", (highlighting|underscoring|emphasi[sz]ing|symboli[sz]ing|showcasing|cementing|"
                 r"solidifying|reflecting|fostering|cultivating|encompassing|contributing to|signaling|enhancing|"
                 r"signalling)\b", STRONG, "inflation",
     "an -ing phrase bolted on to sound deeper: keep the fact, cut the phrase or make it its own claim"),
    ("ing-tail", r", (ensuring|demonstrating|illustrating|making it)\b", WEAK, "inflation",
     "an -ing tail: fine when it states a real result"),

    # ---- inflation: sales language
    ("sales", r"\bnestled\b|\bbreathtaking\b|\bin the heart of\b|\bmust[- ]visit\b|\bstunning\b"
              r"|\bboasts?\b|\bunparalleled\b|\bharness(ing)? the power\b"
              r"|\b(unlock|unleash|supercharge|turbocharge|skyrocket|revolutioni[sz])\w*\b"
              r"|\btake (it|your \w+( \w+)?) to the next level\b|\bcutting[- ]edge\b", WEAK, "inflation",
     "sales language (mostly older AI text, and plenty of human ads): say plainly what the thing is or does"),
    ("sales", r"\brenowned\b|\bdiverse (array|range)\b|\bcommitment to\b|\bgroundbreaking\b|\bprofound\b"
              r"|\bworld[- ]class\b|\b(elevate|empower)\w*\b|\btransformative\b", WEAK, "inflation",
     "brochure wording: fine once, a tell in a cluster"),

    # ---- inflation: borrowed authority (skipped when the sentence names or links its source)
    ("authority", r"\b(experts|researchers|scientists|studies|research|critics|observers|analysts|"
                  r"industry reports|many people|some say)\b[^.!?]{0,20}\b(say|says|agree|suggest|suggests|"
                  r"show|shows|argue|believe|have (shown|found|noted|cited)|point to)\b", STRONG, "inflation",
     "an unnamed authority props up the claim: name the source and what it found, or cut the claim"),

    ("authority", r"\bseveral (sources|publications|reviewers|scholars|outlets)\b|\bobservers have\b"
                  r"|\bsome critics (argue|say|note)\b|\bindustry reports\b", STRONG, "inflation",
     "a vague crowd of sources: name them, or say what the one source said"),
    ("notability", r"\b(independent|extensive|widespread|significant) (media )?coverage\b"
                   r"|\b(featured|profiled|cited|covered) in (several|multiple|numerous|various|major|many)\b"
                   r"|\btrade publications\b|\b(local|regional|national) (media )?outlets\b"
                   r"|\b(maintains?|has|keeps) an? (active|strong|growing|robust) (social media|online|digital) "
                   r"presence\b|\bsocial media presence\b", STRONG, "inflation",
     "argues the subject matters by pointing at its coverage or online presence: say what it did"),
    ("notability", r"\b(records|databases|listings|filings|sources|materials) (identify|list|describe) \w+ as\b"
                   r"|\bwas identified (by|in) [^.]{1,40} as\b|\bprofessional profile lists\b", WEAK, "inflation",
     "stresses how a source 'identifies' the subject: state the fact"),

    # ---- inflation: avoiding is / are / has
    ("copula", r"\b(serves|stands|functions|acts|operates) as (a|an|the)\b", WEAK, "inflation",
     "'serves as': usually 'is'"),

    # ---- leftovers from the chat
    ("chatbot", r"^(certainly|great question|absolutely)[!.,]|\byou'?re absolutely right\b"
                r"|\bi hope this helps\b|\bwould you like me to\b|^want me to\b|\bshall i (continue|expand)\b"
                r"|\blet me know if you('d| would) like (me to|any)\b|\bas an ai\b"
                r"|\bhere(?:'s| is) (a|an|the|your) (revised|updated|rewritten|polished|improved|draft|"
                r"summary|version|breakdown|overview)\b|\bi'?d be happy to\b|\bis there anything else\b"
                r"|\b(a )?more detailed breakdown\b|\bas an? (ai|large) language model\b"
                r"|\b(check|verify|confirm|double-check)\b[^.!?]{0,40}\bbefore (publishing|publication|"
                r"submitting|sending|posting)\b|\bwhile (preserving|retaining|keeping) (the|your|its) "
                r"(original )?(meaning|tone|voice|structure|content|facts)\b"
                r"|\bi'?ve (preserved|retained|kept) (the|your|all)\b", STRONG, "leftover",
     "a chatbot's wrapper left in the text: cut it, keep the content"),
    ("cutoff", r"\bas of my (last|latest) (update|training)\b|\b(up to|as of) my (knowledge )?cut-?off\b"
               r"|\bwhile (specific )?(details|information) (is|are) (limited|scarce)\b"
               r"|\bbased on (the )?available information\b"
               r"|\bnot (widely|publicly|extensively|readily) (documented|available|disclosed|known)\b"
               r"|\bmaintains? a low profile\b|\bin the (provided|available) (sources|search results|materials|"
               r"documents|information)\b|\bnot (fully|well) documented in (public|available) sources\b",
     STRONG, "leftover",
     "a knowledge-limit disclaimer, often followed by a guess: say what the source doesn't show, or cut"),
    ("corrective", r"\bshould be (treated|presented|understood|read|seen|viewed|regarded|taken) as [^.!?]{1,60}"
                   r"\brather than\b|\bdoes not,? (by itself|on its own|alone),? (establish|prove|confirm|show)\b"
                   r"|\bshould be distinguished from\b", STRONG, "leftover",
     "a corrective framing about how to read a source: state what the source shows"),
    ("corrective", r"\bshould not be confused with\b", WEAK, "leftover",
     "disambiguation nobody asked for: keep it only if readers really mix the two up"),
    ("self-ref", r"\b(this|the) (section|post|article|table|guide|document|email) (below )?"
                 r"(will )?(explores?|covers?|compares?|walks you through|dives into|is organi[sz]ed)\b"
                 r"|\bin this (post|article|guide|section),? (we|i)('ll| will)\b|\bwas added to replace\b",
     WEAK, "leftover", "writes about the document instead of its subject: say the thing itself"),

    # ---- stock lines (emails and posts): fine once, a tell when several gather
    ("stock", r"\bi hope this (email|message|note) finds you well\b|\bi wanted to (reach out|follow up|"
              r"touch base|circle back)\b|\bi'?m reaching out\b|\bplease (don'?t|do not) hesitate\b"
              r"|\bfeel free to (reach out|let me know|ask)\b|\bat the end of the day\b|\bwhen it comes to\b"
              r"|\bit'?s (important|worth|crucial) (to note|noting|mentioning|remembering)\b",
     WEAK, "stock", "a stock line: fine once, cut it if the text has other tells"),
    ("connector", r"^(moreover|furthermore|additionally|consequently|nevertheless|thus|hence)\b"
                  r"|^(in conclusion|to sum up|in summary|all in all),", WEAK, "stock",
     "an essay connector: usually 'also', 'so', or nothing"),
]

# Checked on the raw text (outside code blocks), since the sentence checks never see links or brackets.
RAW = [
    ("placeholder", r"(?<![\w\]`])\[(?!(?:sic|citation needed|\.\.\.|x|\s)\])[A-Za-z][\w '/&.-]{1,40}\](?![(\[:])"
                    r"|\b[A-Z][A-Z0-9_]{2,}_HERE\b|\bINSERT_[A-Z0-9_]+\b|\b20\d\d-XX-XX\b"
                    r"|\((?:if available|if applicable)\)", STRONG, "leftover",
     "a placeholder left unfilled: fill it in or cut it before this goes out"),
    ("chatbot-link", r"utm_source=(?:chatgpt\.com|openai|copilot\.com)|referrer=grok\.com", STRONG, "leftover",
     "a link carrying a chatbot's tracking tag: remove the ?utm_source=... part (and check the source says what "
     "the text claims)"),
    ("citation-artifact", r"contentReference\[oaicite:\d+\]|\boaicite\b|\bturn\d+(?:search|view|news|file)\d+\b"
                          r"|\u3010\d+\u2020[^\u3011]*\u3011", STRONG, "leftover",
     "a chatbot's internal citation marker leaked into the text: remove it and cite the real source"),
]
_RAW_COMPILED = [(k, re.compile(rx, re.I), st, g, h) for k, rx, st, g, h in RAW]


def find_raw(text):
    """[(offset, hit)] for the raw-text tells."""
    return [(m.start(), hit(key, m.group(0), st, g, h))
            for key, rx, st, g, h in _RAW_COMPILED for m in rx.finditer(text)]


_COMPILED = [(k, re.compile(rx, re.I), st, g, h) for k, rx, st, g, h in PHRASES]

# A sentence that names or links its source is not borrowed authority.
_SOURCED = re.compile(r"https?://|\]\(|\(\d{4}\)|\baccording to [A-Z]|\b(19|20)\d{2}\b")


def norm(s):
    return s.replace("’", "'").replace("‘", "'").strip()


def hit(key, matched, strength, group, hint):
    return {"key": key, "match": matched, "strength": strength, "group": group, "hint": hint}


def find_phrases(sentence, skip=()):
    """Phrase tells in one sentence. `skip` holds regex strings to ignore (the writer's own habits)."""
    s = norm(sentence)
    out = []
    for (key, rx, st, g, h), (_, raw, _, _, _) in zip(_COMPILED, PHRASES):
        if raw in skip:
            continue
        m = rx.search(s)
        if not m:
            continue
        if key == "authority" and _SOURCED.search(sentence):
            continue
        out.append(hit(key, m.group(0).strip(" ,"), st, g, h))
    return out


def _words(s):
    return re.findall(r"[A-Za-z0-9']+", s)


_NEG_SHORT = re.compile(r"\b(isn'?t|is not|aren'?t|are not|wasn'?t|was not|it'?s not|this is not|"
                        r"(does|do|did)(n'?t| not) mean|not about|not just|not only)\b", re.I)
_AFFIRM_START = re.compile(r"^(it'?s|it is|it was|this is|that'?s|they'?re|it means|this means|rather,|"
                           r"instead,|they are|we'?re)\b", re.I)


def find_shapes(sentences, informal=False):
    """Tells that are a sentence shape or span several sentences.

    `sentences` is a list of plain strings in reading order (one paragraph or a whole text).
    Returns {index: [hits]}. With informal=True (chat messages, comments), shapes that are ordinary
    in casual talk (short fragments, set-up questions) are skipped.
    """
    flags = {}

    def add(i, key, matched, st, group, hint):
        flags.setdefault(i, []).append(hit(key, matched, st, group, hint))

    t = [norm(s) for s in sentences]
    lo = [s.lower() for s in t]
    for i, s in enumerate(lo):
        if re.search(r"\b(it'?s|this is|that'?s|they'?re|you'?re|it is|we'?re)\s+not\s+(just|only|merely|"
                     r"about|simply)\b[^.!?]{0,60}[,;:—-]\s*(it'?s|this is|that'?s|they'?re|it is|but|"
                     r"we'?re)\b", s) \
                or re.search(r"\bnot (just|only|merely|simply) [^.!?]{1,50},? but (?!also\b)", s):
            add(i, "contrast", t[i], STRONG, "staging",
                "'not just X, it's Y': the X is a claim nobody made. Say the Y plainly")
        elif re.match(r"^(and |but |so )?(it|this|that|they|he|she|we|you)('s|'re| is| are| was| were)"
                      r"( not|n't)\b[^.!?]{1,50}[,;:—]\s*(it|this|that|they|he|she|we|you)"
                      r"('s|'re| is| are| was| were)\b", s):
            add(i, "contrast", t[i], STRONG, "staging",
                "'it isn't X, it's Y': say the Y plainly, unless X is a belief the reader really holds")
        elif re.search(r"\bnot (just|only|merely) [^.!?]{1,60},? but also\b", s):
            add(i, "contrast", t[i], WEAK, "staging",
                "'not only X but also Y': fine when both halves carry information")
        if i and len(_words(lo[i - 1])) <= 12 and _NEG_SHORT.search(lo[i - 1]) and _AFFIRM_START.match(s):
            add(i, "contrast", t[i - 1] + " " + t[i], STRONG, "staging",
                "the not-X-but-Y contrast split over two sentences: one plain sentence")
        m = re.search(r", (no|zero|without) (guessing|guesswork|fluff|catch|strings( attached)?|surprises|setup|"
                      r"hassle|drama|exceptions|excuses|code|bs)[.!]?$", s)
        if m:
            add(i, "contrast", m.group(0), STRONG, "staging",
                "a clipped negative tail (', no guessing'): say what the reader gets instead")
        m = re.search(r"\w, not (an? |the )?\w+( \w+)?[.!]$", s)
        if m and len(_words(s)) <= 14:
            add(i, "contrast", m.group(0)[1:], WEAK, "staging",
                "'X, not Y' closing contrast: drop the Y unless the reader believed it")
        if not informal and s.endswith("?") and len(_words(s)) <= 4 and i + 1 < len(lo) \
                and re.match(r"^(and |but |so )?(the|my|your|our|result|honestly)\b", s):
            add(i, "setup-question", t[i], STRONG, "staging",
                "a set-up question answered by the next sentence ('The result? ...'): just say it")
        if re.match(r"^(here'?s|this is) (the|what|why|how) [\w' ]{0,25}:\s", s) \
                or re.match(r"^the (secret|truth|trick|answer|reason|lesson|catch|kicker|takeaway|"
                            r"bottom line|twist)( is)?:", s):
            add(i, "colon-reveal", t[i], STRONG, "staging", "a colon reveal: drop the set-up, keep what follows")
    if not informal:
        run = []
        for i, s in enumerate(lo + ["a sentence long enough to end any run"]):
            if len(_words(s)) <= 2 and not re.match(r"^\W*$", s):
                run.append(i)
                continue
            if len(run) >= 3:
                add(run[0], "fragments", " ".join(t[j] for j in run), STRONG, "rhythm",
                    f"a row of {len(run)} one- or two-word fragments: merge them into one sentence with a claim")
            run = []
        for i in range(1, len(lo)):
            if re.match(r"^no \w+( \w+)?[.!]$", lo[i]) and re.match(r"^no \w+( \w+)?[.!]$", lo[i - 1]):
                add(i, "fragments", t[i - 1] + " " + t[i], STRONG, "rhythm",
                    "'No X. No Y.': one sentence that says what it is")
    for i, s in enumerate(lo):
        if re.search(r"\bno [\w'-]+( [\w'-]+){0,2}, no [\w'-]+( [\w'-]+){0,2},? (and |or )?no\b", s):
            add(i, "fragments", t[i], STRONG, "rhythm",
                "'no X, no Y, no Z': say what it is instead of three things it isn't")
    # a mirrored pair of short sentences ("The fix takes an hour. The routing takes two weeks.")
    for i in range(1, len(lo)):
        a, b = _words(lo[i - 1]), _words(lo[i])
        if 3 <= len(a) <= 7 and 3 <= len(b) <= 7 and a[0] == b[0] and a[0] in ("the", "a", "an", "one") \
                and len(a) > 2 and len(b) > 2 and a[2] == b[2] and a[1] != b[1]:
            add(i, "mirrored-pair", t[i - 1] + " " + t[i], WEAK, "rhythm",
                "a mirrored pair of short sentences for effect: fine once, a tell when it recurs")
    # the same first word three sentences running (four is strong)
    first = [(_words(s)[0].lower() if _words(s) else "") for s in t]
    i = 0
    while i < len(first):
        j = i
        while j + 1 < len(first) and first[j + 1] == first[i] and first[i]:
            j += 1
        n = j - i + 1
        if n >= 3 and first[i] not in ("i",):
            st = STRONG if n >= 4 else WEAK
            add(j, "same-opening", " / ".join(t[i:j + 1])[:160], st, "rhythm",
                f"{n} sentences in a row start with '{first[i]}': merge some or start with the action")
        i = j + 1
    return flags


# "A, B, and C" with short items, or "cheap, clean and practical" (one-word items). The "and" or "or" is
# required, so commas around an aside ("The date, by contrast, is") are not a list.
TRIPLE_RE = re.compile(r"\b([\w'-]+(?: [\w'-]+){0,2}), ([\w'-]+(?: [\w'-]+){0,2}), (?:and|or) ([\w'-]+)"
                       r"|\b([\w'-]+), ([\w'-]+),? (?:and|or) ([\w'-]+)\b", re.I)


def find_triples(text):
    """The 'X, Y and Z' lists in a text that read as a habit. A list of names, formats or products
    (most items capitalized or holding a digit: "JPEG, HEIC and PNG", "Linux, macOS and Windows") is a
    real enumeration and is skipped."""
    out = []
    for m in TRIPLE_RE.finditer(norm(text)):
        items = [g for g in m.groups() if g]
        named = sum(1 for it in items if any(c.isupper() or c.isdigit() for c in it.split()[-1]))
        if named >= 2:
            continue
        out.append(m.group(0))
    return out


def count_triples(text):
    """How many 'X, Y and Z' lists the text holds."""
    return len(find_triples(text))
