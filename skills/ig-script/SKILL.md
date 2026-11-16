---
name: ig-script
description: Check whether an Instagram Reel script, or any short video script, makes sense to someone hearing it cold, not just to its author. A fresh listener who has not seen the notes hears only the script, writes the question each line raises, and retells the video; the check then finds the jumps (missing premise, unanswered question, one thing called by several names, jargon, "that" pointing at nothing, advice without its reason) and proposes the smallest connecting lines using facts already in the file. Use it whenever someone asks to check, review, tighten or sanity-check a Reel script (pasted, or in a file), says a script "jumps", "doesn't flow" or "makes sense to me but", or wants a Reel script or draft checked before recording, even if they do not say "coherence". Also runs without questions when another skill (such as ig-reel) hands it a script to check.
argument-hint: "[path to the script file, or paste the script]"
---

# ig-script: Reel script coherence check

A script can read perfectly to its author and still lose a listener. The author fills each gap with context they already have, so rereading it, or even saying it aloud, does not reveal the gap. This is the curse of knowledge. Scripts written from long notes are especially exposed: compression keeps the conclusions and drops the connecting sentences first, because to the author they look like filler.

The fix is a listener who does not have the notes. This skill gets one by giving a fresh subagent the script and nothing else, then uses the notes (which you can see) to repair what that listener could not follow.

## Called by another skill

Another skill can hand this one a script to check: `ig-reel` does, after writing a Reel, and it says so when it calls. It gives the spoken lines, the on-screen text with its timings and who the video is for. Then:

- **Take what it gave as the file.** Don't look for a script file, and don't ask for the audience, the takeaway, whether it is recorded or what stays out: the caller can't answer, and the person is waiting on the caller. Use the audience it gave; if it gave none, use "someone who follows creators on this topic" and say so. Use the takeaway it gave; if none, take what the opening promises the viewer as the takeaway. Treat the video as not yet recorded, with no "what stays out" list.
- **Run steps 2 to 5 as written**: the timer, the cold listener, the judging, the smallest fixes. A fix uses only facts in what was handed over. A gap that needs a fact nobody gave goes back as a question for the person, with a `{{placeholder}}` in the revised line, never a made-up fact.
- **Return, don't save.** Skip steps 6 and 7 and edit no file. Return to the caller only: the verdict line, the timeline line, the kept gaps each with its type and fix, and the revised spoken lines and on-screen text in the shape they came in, changed lines marked ✱. The caller shows the person what it needs.

## 1. Find the script

The script comes one of three ways:

- **Handed over by another skill**: see "Called by another skill" above.
- **Pasted** into the conversation: use it as it is. Anything else the person pasted or said around it (notes, the idea, who it is for) counts as the notes.
- **A file path** (`$ARGUMENTS`, or a path in the message): read the file. Any text format works: a Markdown or plain-text note, a doc exported as text. If only a partial name is given, look for it in the working folder and ask before guessing.

If none of these was given, ask for the script: paste it, or give the file. Don't go looking for scripts on your own.

If what you were given holds more than one version, take the current spoken script: a section marked approved or final, or else the newest or highest version (`Script v3` over `Script v2`). Ignore sections marked previous, earlier or parked. If two candidates are plausible, ask. Everything else is the notes.

Below, "the file" means the script and its notes, whichever way they came.

Also collect, and keep away from the listener:
- the audience (an `Audience:` line, or what the person told you; without one, ask who the video is for)
- the intended takeaway (`One viewer takeaway`, `The one claim`, `Viewer promise` or similar; without one, ask what one thing a viewer should leave with)
- any target length
- the "What stays out" list, if there is one
- feedback already recorded about the script, such as notes on a practice recording
- whether the video is already recorded: it changes what a fix can be, in step 5. If it isn't clear, ask

## 2. Time the lines

Write the spoken lines to a scratch file, numbered, one sentence per line, with markdown removed. Spoken labels such as "One, give it memory." stay as lines. Then time them:

```bash
python3 <this skill's directory>/scripts/timeline.py lines.txt [--target <seconds>]
```

It prints when each line starts and how long it takes at 2.5 words a second (pass `--wps` from a recorded take if the file has one), the exact words heard by 0:03 and by 0:07, the midpoint, lines over 8 seconds, and runs of three or more lines with no number or name. These are pointers for step 4, not findings: the times are estimates, and the concreteness test is blind to everyday nouns like "gym" or "phone". Keep the output for the listener prompt and the report.

## 3. Cold listener

Ask a listener that has no access to the file:

- **Claude Code**: one `Agent` subagent (general-purpose) on a lighter model such as `sonnet`, in the foreground, since the next step needs its answer.
- **Codex**: pipe the prompt on stdin to `codex exec -s read-only --skip-git-repo-check --ephemeral -C <new empty temp dir> -`, so the process has no notes it could read.

Paste the numbered lines from step 2 into its prompt. Include the on-screen text only if the file defines it, since a viewer reads it before hearing anything. Leave out the file name, title, path, notes and everything else: the title alone often supplies the missing premise.

Prompt (fill in the audience and the lines):

> You are a viewer scrolling Instagram who matches this description: <audience>. A short video starts playing. You hear these lines once, in order, and can't rewind. You know only what the lines tell you plus what a person like you knows from everyday life. Do not use any tools.
>
> First, answer from only these words, the first three seconds: "<heard by 0:03>". What do you think this video is about, and would you keep watching? Then from only the first seven seconds: "<heard by 0:07>". Who do you think it is for, and why would it matter to them? Guessing is fine; say that you guessed.
>
> <on screen at the start, if any: "On screen you read: <text>">
>
> The whole video:
>
> <numbered lines>
>
> 1. For each line, write the question it leaves in your head (or "none"), and the number of the later line that answers it, or "never". Keep each question short and in your own voice.
> 2. List any word or phrase this viewer would not use in everyday conversation, or would understand differently than the speaker seems to mean. List any place where two different words seemed to name the same thing, or one word seemed to change meaning, including between what you read on screen and what you heard.
> 3. List anywhere "that", "this", "it" or "here's how" pointed at something you could not identify.
> 4. Where, if anywhere, would you have stopped watching, and why?
> 5. Which lines, if any, were hard to take in at talking speed on one hearing: too long, too many parts at once, or sounding written rather than said?
> 6. Tell a friend in two or three sentences what the video said. Then say what, if anything, you would do or think differently after watching.
>
> Be honest about confusion. If you had to guess at a connection, say that you guessed. Don't be polite: the speaker wants to find the gaps before recording.

Why these instructions: a model listener knows more than a real viewer (it knows what an agent or a CRM is) and fills gaps generously. Asking it to mark guesses and use only everyday knowledge brings it closer to the real audience. It is still a weaker test than a person; see step 6. The first question exists because Instagram measures who leaves in the first three seconds, and a viewer who can't yet say what the video is about is the one who leaves.

## 4. Judge the gaps

The listener over-reports, because every line raises some question. Keep a gap only if it matters:

- **Never answered and needed**: the viewer needs the answer to follow the next step or to get the takeaway. This is the main failure.
- **Answered too late**: the answer comes, but after a line that depended on it.
- **Missing premise**: the reason something matters lives only in the notes (for example, why the AI needs the data at all).
- **Name drift**: one thing called by several names, or a new term with no plain definition.
- **Jargon** for this audience.
- **Pointing at nothing**: "that", "this" or "here's how" with no clear referent.
- **Abstract where a picture is needed**: a claim the viewer cannot imagine happening.
- **Advice without its reason**: an instruction whose reason is only in the notes.
- **Hook or ending mismatch**: the opening promises something the body does not deliver, or the closing claims more than the body set up.
- **Nothing to go on at 0:03**: from the words heard by 0:03 the listener could not say what the video is about, or guessed wrong. By 0:07 it could not say who it is for. This is a missing premise in seconds; name the time the topic actually arrives.
- **Promise answered after the midpoint**: the question the opening raises is answered only after the midpoint the timeline marks. A story the script openly returns to ("Back to the gym") is a bookend, not a gap, if the listener picked it back up; the gap is a question the viewer is left holding, such as "do I need to code?".
- **Too much for one hearing**: a line over 8 seconds that carries two ideas, or a line the listener called hard to take in or written rather than said (a parenthesis, "the former", a slash, a long list). A long line that holds one idea is fine.
- **Abstract run**: a stretch the timeline flagged in which the viewer, not the tool, can picture or check nothing. A flagged run with a gym, a phone or a meeting in it is not a gap.

A question raised on purpose and answered soon is a hook, not a gap. Leave it. This check never scores a hook or writes a new one: writing and scoring hooks is `ig-reel`'s job, done before the script exists, and choosing the hook is the writer's call (see `references/what-it-checks.md`). A hook gap is only ever "the viewer can't tell yet what this is", fixed with words already in the file.

Then compare the listener's retelling with the intended takeaway. If the retelling misses or distorts the takeaway, that is the headline finding, even when every line looked fine on its own. If the retelling names two separate points, the script may hold two videos; say so and leave the choice to the creator.

Run the connective test yourself on each kept gap: between the two lines, "so", "but", "because" or "for example" should fit. If only "and also" fits, the link is missing.

## 5. Propose the smallest fix

For each kept gap, write the smallest connecting line or edit that closes it.

- Use only facts already in the file: the notes, established facts, the creator's own words. If a gap needs a fact the file does not have, ask the creator rather than inventing one.
- Respect the file's "What stays out" list. A fix must not bring an excluded topic back.
- Write in the creator's spoken voice: first person, short sentences, contractions, everyday words. No em dashes. Say every new line out loud in your head: if it needs rehearsing, rewrite it.
- Prefer replacing or reordering to adding. Closing a jump usually costs a line or two; that is fine, but state the cost. Re-run `timeline.py` on the revised lines for the new length and to check the fix didn't push the topic past 0:03 or the payoff past the midpoint.
- Leave lines that work alone. This is a coherence check, not a restyle.
- If the video is already recorded, sort each fix by what it costs: fixable in the edit (cut a line, add on-screen text) or needing a pickup or re-take of one line. Say that the footage may not match the saved script word for word.
- Look at the earlier drafts in the same file. A gap is often a sentence an earlier draft had and a later tightening cut; when it is, restore that wording and say so.

## 6. Report

Keep it tight, in this shape:

**<Reel title>** · <which version> · audience: <audience>

**Verdict**: one line. Does the listener's retelling match the intended takeaway?

**Timeline**: one or two lines from step 2: length, what the viewer has heard by 0:03 and what the listener made of it, when the topic actually lands, the midpoint, and any line too long for one hearing.

**Original script, problems marked**: the script as it stands, as a blockquote, every line numbered (L1, L2…). Put ❌ at the start of each line that holds a kept gap and bold the exact words causing it; lines that work stay plain. This shows each problem in place before the reader gets to why, instead of making them hunt for it in the question chain.

**Question chain**: each script line by its number, then the viewer's question and ✅ (answered, by which line) or ❌ (the gap, in a few words). Use the same numbers as the marked-up original. Quote the listener where its question is sharp.

**What the listener took away**: its retelling, quoted, against the intended takeaway.

**Gaps**: the kept gaps, most damaging first, at most five, each with its type and its fix.

**Revised script**: the full script with the fixes applied, as a blockquote, one line per sentence or short group. Mark each changed or new line with ✱ at the start and bold the words that changed inside it, so the edits show without comparing versions; unchanged lines stay plain. Write the word count and estimated time before and after above the quote. Check one script at a time.

**Test on a person**: the one or two exact spots to watch when the creator reads the revised script to someone who has not seen the notes and asks them to tell it back in their own words. That retell is the real check; this one only narrows where to look.

## 7. Saving

Never change the script itself unless asked: the decision is the creator's, and their script is what they read on camera.

- **A pasted script**: the report in the conversation is the result. Offer to save it as a file if they want to keep it.
- **A file**: offer to save the report next to it as `<file name>-check-<date>.md`, leading with the revised script, and write it only on a yes. Edit the script file only when asked, keeping the previous version below it under `## Previous script, <date>` so nothing is lost.

A revised script that still has a placeholder, such as a real example the creator has to supply, says so at the top and can't be used until they fill it in.

## Why it checks what it checks

What this skill checks, what it leaves to `ig-reel` and `ig-voice`, and why: `references/what-it-checks.md`.
