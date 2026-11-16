---
name: ig-reel
description: Write an Instagram Reel from an idea, starting from what already performed. Reads the top Reels on the idea (from ig-research, or runs it), matches how each winner opens to 26 hook formulas, picks three formulas weighted by what worked, writes a spoken and an on-screen line for each, scores the hooks to filter out weak ones before any script is written, then writes the script and its timed on-screen text, checks it for a cold listener and in the creator's voice, and ends with a copy-ready block. Use when someone has an idea, a story or a topic and wants a Reel script, hooks for a Reel, "a video about X", or to turn notes into something to record, even if they do not say "script". Never invents a number, a client or a result, and never posts.
argument-hint: "<the idea, and who it is for if you know> [research folder or CSV] [target length in seconds]"
---

# ig-reel: from an idea to a script you can shoot

It writes Reels off 26 hook formulas (`references/hooks.json`), but it doesn't pick one at random or by taste. It first reads the Reels that already performed on the same idea: what they opened with, out loud and on screen, and who a viewer would send them to. The formulas those winners used, weighted by how often viewers shared them, decide which three get written. Each hook is scored before the script is written, the script is built on the one true story the person brings, and every number in it is theirs.

It chains the pack's other skills and works without each of them:

| Step | Uses, if installed | Without it |
|---|---|---|
| 2. Evidence | `ig-research` | Hooks are written but marked unproven |
| 5. Cold-listener check | `ig-script` | A shorter self-check, said so |
| 4, 6. Voice | `ig-voice` | Plain spoken style, said so |
| 7. Next | `ig-caption` | Suggest writing the caption by hand |

Find out which are installed first:

```bash
python3 <skill>/scripts/reel.py skills
```

`<skill>` is this skill's directory (the folder holding this file); `<tmp>` is a scratch folder (the session scratchpad if there is one). Call a sibling skill by its name and let it follow its own instructions; never reach into its folder. Installed as the IG Skills plugin, the names carry the plugin's prefix (in Claude Code, `ig-skills:ig-research`).

## 1. The idea, and the one true thing

From `$ARGUMENTS` take the **idea**, **who it is for** if given, a research folder or CSV if given, and a target length if given. If the person keeps notes or an earlier draft for this idea, read them.

A Reel is carried by one specific true thing: what happened, to whom, and what it cost or returned. "AI can watch things for you" is a topic; "I was watching qualifying, there was a red flag, I asked it to tell me when the session restarted and it did" is a Reel. Check that the idea has:

- **The moment**: what actually happened, or what the viewer will see happen.
- **Who it happened to**: the person themself, a client, a friend. Named only as they want.
- **The cost or the return**: time, money, a mistake avoided, a result. A number if there is one.

If any is missing, ask **one** batched question for exactly what is missing, in plain words, then wait. Don't ask what the notes already say. If they can't answer a part, carry on and leave a placeholder.

**Get the one true number before writing any hook.** Most strong hooks carry a figure (hours saved, money, a count), and a hook written before the person gives theirs gets one made up. So if the cost or the return has no number yet, the batched question asks for it: "roughly how long did it take before, and now?" Then write what they gave you, in their words, to `<tmp>/facts.txt`: the moment, who, the numbers, names, times, quotes and results. Only what they said; nothing you inferred. Step 3 scores the hooks against this file.

**Never invent** a number, a client, a quote, a result or a date. If they can't give the number, write `{{N}}` or a placeholder in plain words (`{{how long it took}}`, `{{the client's industry}}`) wherever it goes, in the hooks and the script alike, and list it at the end. A draft with a placeholder is **NOT READY** to record, and says so, until they fill it in. A placeholder is honest; a made-up "saved 10 hours a week" or "100 owners asked" is a lie said on camera in their name.

## 2. Evidence: how the winners open

What performed on this idea is the evidence the hooks are written from. Look for it in this order:

1. **Research already exists**: a folder, CSV or hooks file the person named, or `research-<idea>-<date>.csv` with its `-hooks.md` in the working folder or their research folder. Read it with

   ```bash
   python3 <skill>/scripts/reel.py evidence <folder | csv | hooks file> [--idea "<idea>"] [--top 8]
   ```

   It prints the winners in the research's order (shares per 1,000 views, the signal Instagram weighs most), with each one's spoken hook, text hook and who a viewer would send it to, and leaves out Reels the research marked for low reactions. A `?` means that hook was never read. If the CSV is there but no hooks file, the hooks step of `ig-research` hasn't run: offer to run just that step.
2. **No research, `ig-research` installed**: offer to run it now on this idea, with a smaller count when they want it quick (15 to 25 Reels, hooks of the top 5 to 8). It runs in their own signed-in browser and takes a few minutes. Run it only on their yes, then read its output as above.
3. **No research and they don't want it, or `ig-research` isn't installed**: say in one line that the hooks below are **unproven**, written from the idea alone, and that research on the idea would ground them. Go on to step 3.

**Check the evidence fits.** Skip winners that are about a different idea however big they are, and say which. If every winner rode a news moment that has passed (the research's timeline line says so), say that their openings show what worked then, not now.

**Match each winner to the 26 formulas.** `references/hooks.json` holds 26 hook formulas, each with a name, the move it makes, a template, a made-up example, the on-screen version and when to use it (`python3 <skill>/scripts/hooks.py list` prints them). Then run

```bash
python3 <skill>/scripts/hooks.py pick <the same folder, CSV or hooks file> [--idea "<idea>"]
```

It matches each winner's spoken and on-screen hook to the formulas it resembles (a winner whose spoken hook is "no captions" is matched on its on-screen hook alone, and marked "on screen") and ranks the formulas by the shares per 1,000 views of the winners that used them, recent winners counting a little more. A formula matches only when the hook has its defining feature (free and a deadline; a number and hidden things; can't and a way now), so it would rather name nothing than the wrong formula. Read each winner's hook yourself and correct the match. A winner that fits no formula, listed with both its hooks, still counts: name its move in plain words, so someone who never saw the Reel could make the same move ("names the pain in the viewer's words, then says the fix exists"), and treat that move as a formula for this Reel.

Then say in two or three lines which formulas the winners used, which share most, which are recent, and how many winners have a real text hook. How to read the hooks table, and what counts as one move or two: `references/evidence.md`.

## 3. Three hooks from the 26, scored before the script

**Pick three formulas, each a different move.** Take them from the top of `hooks.py pick` where they fit the person's true thing. Skip a backed formula that would need a fact they don't have: "Free, with a date" needs a real offer, "The number first" needs their real number (or `{{N}}`). Fill the rest from the 26 by each formula's "use when". With no evidence, pick three clearly different moves from the 26 and label all three unproven.

**Write each hook** with:

- **Spoken**: the first line said, what the viewer hears in the first three seconds. It says what the video is about with the person's true thing in it, not a warm-up.
- **On screen**: the words placed on screen at 0:00, read before the first word is heard. Short enough to read in two seconds or so, and not a transcript of the spoken line: it can carry the number or the name while the voice carries the moment. "None" is allowed when the winners mostly had none.
- **Formula**: its id from the 26, and the winners behind it with their shares per 1,000 views, or "unproven".
- **Sendable to**: who a viewer would send this Reel to, and what they would say.

Copy the move, never a winner's words.

**Score them before writing any script.** Write the three to `<tmp>/hooks.txt`, one per block (`Spoken:`, `On screen:`, `Formula:` lines, a blank line between hooks; a `Sendable to:` line can stay in the block, it is never scored as speech), and run

```bash
python3 <skill>/scripts/hooks.py score <tmp>/hooks.txt --topic "<the idea in a few words>" --facts <tmp>/facts.txt
```

It scores each out of 100 and ranks them: specificity weighs most, then whether it starts on the content rather than a greeting or preamble, whether it can be said in about 3 seconds, whether there is something to picture, and whether the topic arrives in the first 3 seconds. Specificity means the person's own detail: their numbers, names, times, quotes or results. Saying the topic is not a detail, so the topic's words and the names the whole niche uses ("Claude", "Code", "ChatGPT", "Instagram") earn nothing. A number earns points only when it is in `facts.txt`; a number that isn't marks the hook **WEAK** ("number not in your facts"), and without `--facts` no number earns anything. A `{{N}}` earns the points the real number would, and the hook says **NOT READY** until it is filled. It also marks a hook **WEAK** for a warm-up, for nothing concrete, or for being far too long, and warns when the on-screen line can't be read in time.

**Be honest about what the score is.** It's a filter: it catches weak hooks for reasons text can show. It doesn't predict which good hook gets more shares; two hooks a few points apart are a tie, and a text-only score has not been shown to tell a good hook from a better one. So:

- Rewrite any **WEAK** hook, usually by moving the person's number or name into the first few words, and score again. A "number not in your facts" is never fixed by adding it to the facts: ask the person for the real one, or use `{{N}}`.
- Among hooks that pass, **the evidence decides**: the formula with the highest share rate among recent, on-topic winners that fits the true thing without stretching it. The script is written on that one. Only when there is no evidence, or the evidence is split, does the top score decide.

Show the three hooks with their scores, and say which you'd pick and why, in one or two lines from the evidence and the score together. Ask which they want, or go on with your pick if they asked you to just write it, and say so.

## 4. Write the script

Write on the chosen hook, in this shape, to `<tmp>/reel-draft.md`:

```markdown
## Hook
Spoken: <the chosen spoken line, word for word>
On screen: <the chosen on-screen line, or None>

## Script
<one spoken sentence per line, starting with the spoken hook>

## On-screen text
0:00-0:03 <the on-screen hook>
0:12-0:16 <a number, a step name, a word to keep>
```

- **Deliver what the hook promised**, early, and with the person's true thing: the moment, then what it cost or returned, then what the viewer can take from it. One idea per Reel; a second idea is a second Reel.
- **Write to be said**: short sentences, contractions, everyday words, one thing per line. If a line needs rehearsing, it's still written.
- **End on one ask** that fits: send it to someone, save it, comment a word, follow. Not three.
- **On-screen text is its own list**, timed against the spoken lines. It's read, not heard, so keep each cue short and give it time on screen. It backs up the voice (a number, a name, a step); it doesn't caption it word for word.
- **Length**: what the story needs. If the person gave a target, aim for it.
- **Voice**: if `ig-voice` is installed and has a saved profile (its own instructions say where it lives and how to print it), read it and write in that voice from the start. Its repeated phrases are for when they fit, never forced in.
- Keep every `{{placeholder}}` from step 1 as is.

More on shape, endings and on-screen text: `references/writing.md`.

Then time it and list what's open:

```bash
python3 <skill>/scripts/reel.py check <tmp>/reel-draft.md [--target <seconds>]
```

It prints the estimated length (and, with `--target`, how far it is from the target), when each line starts, the words heard by 0:03, every placeholder, on-screen cues that overlap, run out of order, start after the script ends, show up more than 1.5 s before the spoken line they back up, or are too long to read in their time, and the copy block. Words are counted the same way as `ig-script`'s timer (a placeholder is one word, "$18,000" is three), so both give the same length. Fix every `PROBLEM`; treat a `WARN` as a question. With a placeholder left it ends **NOT READY**; that is the honest state of a script waiting on the person's number, not something to work around.

## 5. Cold-listener check

**If `ig-script` is installed**, run it on the script in its "called by another skill" mode: it times the lines with its own timer, has a listener who hasn't seen any notes say what the video is about from the first three seconds and retell it, and proposes the smallest connecting lines. Give it the spoken lines, the on-screen text with timings and who the Reel is for, and say that ig-reel is calling, so it doesn't stop to ask for a takeaway or a "what stays out" list; leave out the idea's title and your notes, since they'd fill the gaps a viewer can't. Apply the fixes that keep the hook and the true thing, and re-run `reel.py check`.

**If it isn't**, say so in one line and do a short version yourself: read only the spoken lines and ask whether, from the words heard by 0:03 alone, a stranger could say what the video is about; whether any "this", "that" or "it" points at nothing; whether one thing is called by two names; and whether every piece of advice has its reason. Fix those.

## 6. Voice pass

**If `ig-voice` is installed**, run it on the spoken lines as a script, as its own instructions say (it is built to be called by another skill), and apply its rewrites without changing a fact, a number or a placeholder. Then re-run `reel.py check` so the final text is the checked text. **If it isn't**, say so in one line.

## 7. Hand it over

Show, in this order:

1. **The evidence** in two or three lines: which formulas the winners used and their share rates, or that the hooks are unproven.
2. **The three hooks** as written in step 3, each with its formula and score, and your pick and why.
3. **What the checks changed**, one line each.
4. **The copy block** exactly as `reel.py check` printed it on the final draft: hook said, hook on screen, script, on-screen text with timings, length.
5. **To fill in**: every placeholder, and that the script isn't ready to record until they are filled.

Then suggest the next step in one line: `ig-caption` to write and check the caption for this Reel, if it's installed. Stop there. This skill never posts, schedules or opens Instagram.
