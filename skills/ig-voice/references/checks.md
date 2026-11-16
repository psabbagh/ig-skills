# What voice.py checks

Read this when a flag needs explaining, when a creator disputes one, or when you are changing the lists. All lists are in `scripts/patterns.py` and are meant to be edited.

None of this is a detector. Each check is a local rule of thumb about how people write on a phone versus how generated text tends to come out. A hit means "look at this line", not "this was written by AI", and a clean report proves nothing either way.

## The profile (`learn`)

Measured over the samples, after markdown headings and `**` markers are removed, and after the footer (below) is set aside. Only `hashtags_per_sample` counts the whole post, footer included, because hashtags are a habit wherever they sit.

| Field | What it is |
|---|---|
| `sentence_words` | Words per sentence: median, mean, spread (standard deviation), 10th and 90th percentile, longest. Sentences split on `.` `!` `?` `…` and on line breaks. Hashtags, @handles and links are not words. |
| `contraction_share` | Contracted forms ("don't", "I'm") out of all places a contraction was possible ("don't" plus "do not"). `null` when the samples give no evidence. |
| `per_100_words` | First person singular (I, me, my), second person (you, your), first person plural (we, our, us). |
| `emoji_per_sample`, `emoji_top` | Emoji count per sample and the most used ones. |
| `swears_per_100_words` | From a short list of common swear words. |
| `hashtags_per_sample`, `samples_with_hashtags` | Median hashtag count over the samples that have any (scripts usually have none, captions do), footer included. |
| `footer` | The closing block repeated across samples: `lines` as shown, `keys` as matched, `samples_with_footer`. A line is footer when it is among the last 6 non-blank lines and part of the trailing run of footer lines in at least half the samples (and at least 2). A line of only hashtags matches any other line of only hashtags; a separator (a line of only symbols, such as `—`, `–`, `---`, `___`, `* * *` or `•••`) matches any other separator, so the form does not matter; any other line matches the same text ignoring case. |
| `punctuation` | Counts of em dashes, en dashes, spaced hyphens, curly and straight quotes, the `…` character and typed `...`, semicolons, colons, parentheses; `!` and `?` per sentence. |
| `lowercase_start_share` | Share of sentences that start in lowercase. |
| `openers`, `closers` | How each sample starts (question, number, "I", "you", statement) and ends (call to action, question, statement). |
| `triples_per_100_words` | How often they write "X, Y and Z" lists. |
| `signature_phrases` | Two- and three-word phrases in at least 3 different samples, or in exactly 2 samples whose other content words overlap by less than a fifth (different subjects). Two posts on one subject share its name, which is the topic, not a habit. Most widespread first; overlapping phrases are collapsed to one. |
| `signature_words` | Content words that appear in at least two different samples, most widespread first. |
| `used_stock_patterns`, `used_formal_words` | Entries from the stock-phrase and formal-word lists that the creator used themselves. These are never flagged for them. |

## Fixed automatically (`check`)

| Fix | Rule |
|---|---|
| Invisible characters | Zero-width space, word joiner, byte-order mark, soft hyphen, direction marks and controls: removed. They survive copy-paste and nobody types them. A zero-width joiner between two emoji is kept, because it builds emoji such as families and flags. |
| Odd spaces | Non-breaking, thin, narrow and other special spaces become a normal space. |
| Markdown | `**bold**`, `__bold__`, `*italic*`, `` `code` `` and `# ` headings lose their markers, because Instagram shows them as typed. `--keep-markdown` turns this off. |
| Curly quotes | Made straight unless the creator's samples use more curly quotes than straight ones. Without a profile they are made straight. |
| `…` | Becomes `...` unless the creator uses the single character more than typed dots. |
| Em and en dashes | Kept if the creator uses them. Otherwise: a dash between numbers becomes a hyphen ("5-10"), a dash at the end of a line becomes `...`, a dash at the start of a line becomes `- `, and any other dash becomes `, ` (or ` - ` if the creator types spaced hyphens). Read those lines again: a full stop is often better than the comma. |
| Spaces | Runs of spaces inside a line collapse to one; trailing spaces go. |

## Rewrite these

Sentence shapes, matched per sentence (and across neighbouring sentences for the two-step ones):

- **Contrast frame**: "It's not just X, it's Y", "not because X, but Y".
- **Two-step contrast**: a short sentence with "isn't" or "not" followed by one starting "It's", "This is", "That's", "They're".
- **Set-up question**: a short "The result?", "My secret?" answered by the next sentence.
- **Colon reveal**: "Here's the truth: ...", "The secret: ...".
- **"Whether you're X or Y"** and **"From X to Y,"** openers.
- **Staccato run**: three or more one- or two-word sentences in a row.
- **"No X. No Y. Just Z."**
- **Lists of three**: three or more "X, Y and Z" lists in one draft, and (with a profile) more than twice the creator's usual rate.

Stock phrases come from `STOCK_PHRASES`, grouped as stock opener, stock reveal, stock closer, stock call to action, hype word or verb, brochure word, word people rarely say, essay connector, throat-clearing, filler phrase and assistant voice. Any entry the creator used in their samples is skipped.

## Least like you

Each sentence collects weighted reasons, and sentences scoring 2 or more are ranked (top 5 by default, `--top` to change):

| Reason | Weight |
|---|---|
| Report-language word from `FORMAL_WORDS` the creator never used | 2 |
| Long form ("do not") when the creator contracts at least 60% of the time | 2 |
| Longer than the creator's 90th percentile by 30% (or 4 words, whichever is more) | 2, or 3 if far over |
| Under half their 10th percentile, when that is 6 words or more | 1 |
| Semicolon they never use | 2 |
| `!`, colon, emoji, swearing they never use | 1 each |
| Capital first letter from someone who writes in lowercase | 1 |
| "we/our" from someone who talks as "I" | 1 |

Without a profile, only formal words, long forms and sentences over 30 words are listed, each at the lower weight, under "Other lines to look at".

Length rules apply to captions and scripts, not to DMs and comments.

## Whole draft

Every report has this section, for every `--kind`. It starts with a summary line: words, sentences and their range, then the emoji and hashtag count (captions, DMs, comments) or the speaking time (scripts). The speaking time uses the spoken word count shared with ig-reel's `reel.py` and ig-script's `timeline.py`, at their default 2.5 words a second: a `{{placeholder}}` is one word however long its description, "$18,000" is three, line numbers such as `1.` or `L2:` are not said. A placeholder also counts as one word in sentence lengths. When the draft ends with the creator's footer, the footer is split off before any check, left exactly as typed (only invisible characters are removed), and the summary says how much of it is there: the usual footer, part of it (naming what is missing), or only a line of hashtags (`footer_status` in `--json`: `usual`, `partial`, `hashtags`). The notes below follow, or "nothing else stands out".

- **Rhythm**: with 5 or more sentences, a spread under half the creator's and under 4 words (or under 2.5 words without a profile) means every sentence is about the same length.
- **Opening and ending**: flagged when the draft opens or ends in a way none of 5 or more samples do.
- **Emoji**: none when they usually use one or more; or more than 2.5 times their usual.
- **Emoji bullets**: three or more lines starting with an emoji.
- **Hashtags**: more than twice their usual plus three, or any when their samples have none.
- **Length** (captions): more than 2.2 times their usual post.
- **Swearing**: a note, not a flag, when they swear and the draft does not.

DMs and comments get only the rhythm and emoji-bullet notes: they skip the opening, ending, emoji count, hashtag, swearing and length notes.
