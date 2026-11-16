"""
patterns.py - the word and phrase lists ig-voice checks against.

Plain data, written for this skill. Edit freely: every entry is a regular
expression (matched case-insensitively against one sentence) and a short reason
shown to the writer. A phrase the creator used in their own samples is never
flagged for them, so a list entry only fires on words that are not theirs.
"""

# Phrases that turn up far more in machine-written posts than in what people
# type on a phone. Grouped by why they read that way.
STOCK_PHRASES = [
    # openers that announce instead of saying
    (r"\bin today'?s (fast[- ]paced|digital|modern|ever[- ]changing) (world|age|landscape)\b", "stock opener"),
    (r"\bin a world where\b", "stock opener"),
    (r"\bimagine a world\b", "stock opener"),
    (r"\bpicture this\b", "stock opener"),
    (r"\bever wondered\b", "stock opener"),
    (r"\bhave you ever wondered\b", "stock opener"),
    (r"\blet'?s (dive|jump) (in|into|right in)\b", "stock opener"),
    (r"\b(let me|let'?s) break (it|this) down\b", "stock opener"),
    (r"\bbuckle up\b", "stock opener"),
    (r"\bhere'?s the (thing|truth|deal|kicker)\b", "stock reveal"),
    (r"\bthe (best|crazy|wild|scary) part\?", "stock reveal"),
    (r"\bspoiler( alert)?:", "stock reveal"),
    (r"\blet that sink in\b", "stock closer"),
    (r"\bread that again\b", "stock closer"),
    (r"\bthe future is (here|now)\b", "stock closer"),
    (r"\bready to (take|level up|transform|unlock)\b", "stock call to action"),
    (r"\btake (it|your \w+( \w+)?) to the next level\b", "stock call to action"),
    (r"\bno fluff\b", "stock promise"),
    (r"\bnot the other way around\b", "stock reversal"),
    (r"\bgame[- ]?changer\b", "hype word"),
    (r"\bgame[- ]changing\b", "hype word"),
    (r"\b(unlock|unleash|supercharge|turbocharge|skyrocket)\w*\b", "hype verb"),
    (r"\brevolutioni[sz]\w*\b", "hype verb"),
    (r"\bharness(ing)? the power\b", "hype phrase"),
    (r"\b(elevate|empower)\w*\b", "hype verb"),
    (r"\bseamless(ly)?\b", "brochure word"),
    (r"\bcutting[- ]edge\b", "brochure word"),
    (r"\bdelv(e|es|ed|ing)\b", "word people rarely say"),
    (r"\btapestry\b", "word people rarely say"),
    (r"\b(realm|landscape) of\b", "word people rarely say"),
    (r"\ba testament to\b", "word people rarely say"),
    (r"\bnavigat(e|ing) the (complex|world|landscape)\w*\b", "word people rarely say"),
    (r"\bembark(ed|ing)? on\b", "word people rarely say"),
    (r"\bever[- ]evolving\b", "word people rarely say"),
    # essay connectors nobody uses in a caption
    (r"^(moreover|furthermore|additionally|consequently|nevertheless|thus|hence)\b", "essay connector"),
    (r"^(in conclusion|to sum up|in summary|all in all|overall),", "essay connector"),
    (r"\bit'?s (important|worth|crucial) (to note|noting|mentioning|remembering)\b", "throat-clearing"),
    (r"\bat the end of the day\b", "filler phrase"),
    (r"\bwhen it comes to\b", "filler phrase"),
    (r"\bplays? a (crucial|vital|key|pivotal) role\b", "filler phrase"),
    # assistant voice leaking into a post
    (r"^(certainly|absolutely|great question)[!.,]", "assistant voice"),
    (r"\bi hope this helps\b", "assistant voice"),
    (r"\bas an ai\b", "assistant voice"),
    (r"\bhere'?s (a|an) (caption|script|version|draft)\b", "assistant voice"),
]

# Words that put a caption into report register. Flagged only when the creator
# never used them in their samples. The hint is the everyday word.
FORMAL_WORDS = {
    "utilize": "use", "utilise": "use", "utilizing": "using", "leverage": "use",
    "leveraging": "using", "facilitate": "help", "commence": "start",
    "endeavor": "try", "endeavour": "try", "numerous": "lots of", "various": "different",
    "comprehensive": "full", "robust": "solid", "crucial": "key", "pivotal": "key",
    "essential": "needed", "optimal": "best", "optimize": "improve", "optimise": "improve",
    "enhance": "improve", "enhanced": "better", "ensure": "make sure", "subsequently": "then",
    "approximately": "about", "individuals": "people", "purchase": "buy",
    "assist": "help", "regarding": "about", "obtain": "get", "demonstrate": "show",
    "additionally": "also", "furthermore": "also", "moreover": "also",
    "meticulous": "careful", "meticulously": "carefully", "myriad": "lots of",
    "paramount": "most important", "streamline": "simplify", "streamlined": "simpler",
    "transformative": "big", "innovative": "new", "groundbreaking": "new",
    "unparalleled": "unmatched", "foster": "build", "bolster": "boost",
    "holistic": "whole", "synergy": "teamwork", "intricate": "complicated",
    "nuanced": "subtle", "plethora": "lots", "realm": "world", "vibrant": "lively",
}

# Long forms a person who talks in contractions would shorten.
UNCONTRACTED = {
    "do not": "don't", "does not": "doesn't", "did not": "didn't", "is not": "isn't",
    "are not": "aren't", "was not": "wasn't", "were not": "weren't", "have not": "haven't",
    "has not": "hasn't", "had not": "hadn't", "will not": "won't", "would not": "wouldn't",
    "could not": "couldn't", "should not": "shouldn't", "cannot": "can't", "can not": "can't",
    "i am": "I'm", "you are": "you're", "we are": "we're", "they are": "they're",
    "it is": "it's", "that is": "that's", "there is": "there's", "here is": "here's",
    "what is": "what's", "i have": "I've", "you have": "you've", "we have": "we've",
    "they have": "they've", "i will": "I'll", "you will": "you'll", "we will": "we'll",
    "it will": "it'll", "let us": "let's", "i would": "I'd", "you would": "you'd",
}

CONTRACTION_RE = (r"\b(\w+n't|i'm|i've|i'll|i'd|you're|you've|you'll|you'd|we're|we've|we'll|"
                  r"we'd|they're|they've|they'll|they'd|it's|it'll|that's|there's|here's|"
                  r"what's|who's|let's|he's|she's|y'all|gonna|wanna|gotta)\b")

SWEARS = r"\b(fuck\w*|shit\w*|bullshit|damn\w*|crap|wtf|af|bitch\w*|ass(hole)?|hell yeah|pissed)\b"

# Common words left out when picking the creator's signature words.
STOPWORDS = set("""
a about above after again against all also am an and any are aren't as at be because been
before being below between both but by can can't could couldn't did didn't do does doesn't
doing don't down during each few for from further get gets got had hadn't has hasn't have
haven't having he he's her here here's hers herself him himself his how i i'd i'll i'm i've if
in into is isn't it it's its itself just let's like me more most much my myself no nor not now
of off on once one only or other our ours ourselves out over own really same she should
shouldn't so some such than that that's the their theirs them themselves then there there's
these they they'd they'll they're they've thing things this those through to too under until up
us very was wasn't we we'd we'll we're we've were weren't what what's when where which while
who who's whom why will with won't would wouldn't you you'd you'll you're you've your yours
yourself yourselves go going make made know want need see say said even still way back well
yeah ok okay gonna wanna gotta new day time
""".split())

CALL_TO_ACTION = r"\b(comment|follow|save|share|link in (my )?bio|dm me|send (this|it)|tag (a|someone)|subscribe|drop a)\b"
