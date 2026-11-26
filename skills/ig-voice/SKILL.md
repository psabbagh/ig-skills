---
name: ig-voice
description: Make a caption, Reel script, DM or comment sound like the creator who will post it, not like AI. Learns their voice from 5 to 10 of their own past posts (words and phrases they use, sentence length, how they open and close, contractions, emoji, punctuation), then cleans a draft (invisible characters, dashes and quotes they never type, markdown Instagram would show), lists the machine-sounding lines for a rewrite and the lines least like them, and rewrites those in their voice. Use when someone asks to humanize, de-AI, "make this sound like me", clean up an AI-written caption or script, check a draft before posting, or set up their voice profile, even if they do not say "voice".
argument-hint: "[draft text or file; or \"learn\" plus 5 to 10 past captions or scripts]"
---

# ig-voice

A generic humanizer makes text sound like nobody in particular. This one makes it sound like the person posting it, by learning how they actually write and checking each draft against that. It runs locally: standard-library Python, no network, nothing uploaded, no API keys.

`scripts/voice.py` does the measuring and the mechanical cleaning. You do the rewriting, because a regex that rewrites sentences produces the same flat text this skill exists to remove.

Every check is a local heuristic. Never tell anyone the result is "undetectable" or that it will pass a given detector. Say what it is: a draft that has been checked against their own writing and a list of known machine habits.

## 1. Work out what is being asked

- **A draft to fix** (pasted or a file): go to step 3. If there is no profile yet, still run it, and say once that it gets much better with one.
- **"Learn my voice"**, or samples arrive with no draft: step 2.
- **Both**: step 2, then step 3.
- **Called by another skill** (for example a caption skill finishing its work): run steps 3 and 4 on the file it gives you and return the final text and the report. Do not ask questions the caller cannot answer. A script that only needs the mechanical clean can call `voice.py check draft.txt -o clean.txt --report report.md` directly.

### Where the profile is saved

The first of these that is set decides where the profile file is, for `learn`, `check` and `show` alike:

1. `--profile <file>` on the command line.
2. `IG_VOICE_PROFILE`: the full path of the profile file itself, for example `/tmp/voice-test/voice.md`.
3. `XDG_CONFIG_HOME`: the config folder. The profile is then `$XDG_CONFIG_HOME/ig-voice/voice.md`.
4. Otherwise `~/.config/ig-voice/voice.md`.

The samples it was built from go in a `samples/` folder next to the profile file, wherever that is. `python3 <skill dir>/scripts/voice.py show` prints the path in use and the profile.

For a test run that must not touch the real profile, point `IG_VOICE_PROFILE` at a throwaway file (`--profile` works too). `learn` replaces the samples beside whichever profile is in use, so set it before running `learn`:

```bash
IG_VOICE_PROFILE=/tmp/voice-test/voice.md python3 <skill dir>/scripts/voice.py learn test-samples/
IG_VOICE_PROFILE=/tmp/voice-test/voice.md python3 <skill dir>/scripts/voice.py check draft.txt
```

## 2. Learn the voice

Get 5 to 10 pieces the creator wrote themselves and actually posted or recorded: captions, spoken Reel scripts, longer DMs. Recent ones beat old ones. Fewer than 5 gives a rough profile; say so.

Only what they posted goes in. Remove what was never part of the post: notes, headings, version labels, prompts written for an AI, other people's comments. Keep the post exactly as it went up, including a closing block they put under every post (a separator line, a "Follow @..." line, hashtags). `learn` finds a block repeated at the end of at least half the samples and records it as their footer and hashtag habit, apart from their voice: its dashes and phrases don't count as how they write, and a draft that ends with the same footer is not flagged for it. Text an AI drafted and they posted unedited teaches the profile the wrong voice; if they say a post was mostly generated, leave it out.

Write each sample to its own `.txt` file in a temporary folder (or one file with a line containing only `---` between samples), then run the command below. A footer separator is never a sample break: any line of only `---`, `—`, `–`, `___` or `* * *` followed by a "Follow @..." line or hashtags stays part of that post's footer, and all those separator forms count as the same footer line.

```bash
python3 <skill dir>/scripts/voice.py learn <folder or files>
python3 <skill dir>/scripts/voice.py learn --add <more files>   # add to what is saved
```

It prints a summary: sentence length range, contraction rate, person (I / you / we), emoji, swearing, hashtags, the footer if there is one, punctuation habits, how they open and close, the phrases and words they repeat. A phrase counts as one they repeat only when it is in 3 or more samples, or in 2 samples on clearly different subjects, so the name of a topic two posts share is not mistaken for a habit. Show that summary and ask if anything looks wrong; they know their own voice better than a handful of samples does. The samples are kept beside the profile (`samples/`) on their machine only.

## 3. Check a draft

Write the draft to a file and run:

```bash
python3 <skill dir>/scripts/voice.py check draft.txt --kind caption|script|dm|comment
```

Add `-o clean.txt` to write the cleaned text to a file, `--report report.md` for the report, `--json` for both as data, `--no-profile` to ignore the saved profile, `--strict` to exit with status 2 when any line is listed. These combine: `--json --report r.md --strict` prints the JSON, writes the report and still exits 2 when something is listed.

The report has these parts (what each check looks for and its thresholds: `references/checks.md`):

- **Fixed automatically**: invisible characters, odd spaces, curly quotes, ellipsis characters and dashes the creator does not type, markdown markers. These are already changed in the cleaned text. A dash replaced with a comma is grammatical but not always good; reread those lines.
- **Rewrite these**: sentence shapes and stock phrases that read as machine-written. A phrase the creator used in their own samples is never listed for them.
- **Least like you** (with a profile) or **Other lines to look at** (without): lines ranked by how far they sit from the profile, with the reasons: length outside their range, long forms they would contract, report-language words they never use, punctuation they never use, emoji or swearing where they have none, "we" from someone who says "I".
- **Whole draft**, in every report whatever the `--kind`: a summary line (words, sentences, their range; for a caption, DM or comment the emoji and hashtag count; for a script, roughly how many seconds it takes to say, counted the same way as ig-reel and ig-script: 2.5 words a second, a `{{placeholder}}` as one word), whether it ends with their usual footer (or only part of it, or only hashtags), then notes on what stands out: for every kind, sentences that are all the same length and emoji used as bullets; for captions and scripts, also the opening and closing compared with how they usually open and close, and emoji, hashtags and swearing against their posts; for captions, the overall length. A script gets this section too because how a spoken piece opens and closes matters as much as a caption's; hashtags rarely apply to it, so its summary gives the speaking time instead.
- **Your words**: their repeated phrases and words, for you to draw on in the rewrite.

## 4. Rewrite the flagged lines

Start from the cleaned text. Rewrite only the lines the report lists, plus any line a fix broke. Leave the rest alone: lines that pass are already in their voice.

For each flagged line:

- Keep every fact, number, name and call-to-action keyword exactly. Do not add a claim, an example or a feature that is not in the draft; if a line only works with a fact you do not have, flag it and ask.
- Say the point plainly instead of in the flagged shape: "It's not just X, it's Y" becomes the Y; "The result? Z." becomes Z.
- Fit their range: sentence length, contractions, person, punctuation, emoji, how they end. Use their own phrases where they fit naturally, never forced in.
- Read it as them. For a script, say it out loud in your head: if it needs rehearsing, it is still written, not said.

Then run `check` again on the rewrite. If it still flags something, fix that once more. Two rounds is enough; after that, show what is left and why, rather than polishing it into something stiff. Some flags are judgement calls: a list of three can be exactly right. Keep what they would really say over what passes the check. More on rewriting, including DMs and comments: `references/rewriting.md`.

## 5. Show the result

- **Before and after**, side by side or one after the other, with the changed lines marked.
- **What was fixed automatically**, in one line per kind.
- **What was rewritten and why**, one line each, in plain words.
- **Anything left**, with your reason for leaving it.

When another skill called this one, return the final text and the report file path and nothing else.
