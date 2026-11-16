---
name: ig-plan
description: Plan the creator's week on Instagram from their own data, not generic advice. Reads their ig-research CSVs and their posting log, ranks the ideas by shares per view and turns each research run's distinct winning Reels into separate ideas so one run can fill a week, drops topics they covered recently, finds their best days and times from their own numbers or their followers' active times pasted from Instagram (else a sourced, labelled default), lists the creators worth engaging with this week, then drafts the week slot by slot with the idea, the format, the day, the time and the evidence, and hands each Reel idea to ig-reel. Also keeps the posting log: add what went up, paste its insights. Use when someone asks what to post this week, for a content plan or calendar, when to post, what to post next, who to engage with, or wants to log a post or paste their numbers, even if they do not say "plan". Never posts or schedules anything.
argument-hint: "[posts this week] [research folder or CSVs] [@your handle]"
---

# ig-plan: the week, from real numbers

The goal is a week the creator can act on, where every slot says why: which idea, in which format, on which day at what time, and the numbers behind it. Scripts do the counting; you make the final call and explain it. Nothing here posts or schedules: the creator posts.

It runs on two kinds of data:

- **Research**: the `research-<idea>-<date>.csv` files the `ig-research` skill writes, one per idea, with every Reel it found and its views, likes, comments and shares.
- **The posting log**: what the creator posted, when, in which format, on which topic, and its numbers once they paste them. One CSV, `~/.config/ig-plan/posted.csv` by default, under `$XDG_CONFIG_HOME/ig-plan/` when that is set (`IG_PLAN_LOG` or `--log` picks another).
- **Optional, the followers' most active times**: what Instagram's insights show (professional dashboard > Total followers > Most active times), written into a text file.

Settings saved with `--remember` (research folders, handle, active times) go to `config.json` in the same folder; `--config FILE` points at another settings file.

Below, `<skill>` is this skill's directory (the folder holding this file).

## Logging posts (any time, also on its own)

When the creator says they posted something, add it; when they paste a post's insights, import them. Each command prints what it wrote, so show that line.

    python3 -B <skill>/scripts/postlog.py add --at "YYYY-MM-DD HH:MM" --format reel --topic "what it was about" [--hook "its opening line"] [--idea <research slug>] [--url <link>]
    python3 -B <skill>/scripts/postlog.py insights [--id N | --url <link> | --topic <words>]   # pasted text on stdin
    python3 -B <skill>/scripts/postlog.py list

- Time is the creator's local time, 24-hour. Ask if they gave only a day; a date alone is accepted but can't count towards best times.
- `--hook` is the post's opening line, spoken or on screen. With it, the plan can tell when a research angle makes a promise the creator already posted, however it was worded.
- `--idea` is the research slug the post came from (`research-<slug>-<date>.csv`). It makes coverage exact; without it, coverage matches topic words.
- For `insights`, write the pasted text to a temporary file and pass it on stdin, unchanged. Without `--id`/`--url`/`--topic` it goes to the most recent post with no views yet. Check the `read ...` line against the paste: a number read wrong is planned on.
- Formats: `reel`, `carousel`, `photo`, `story`, `live`.

## 1. Gather

From `$ARGUMENTS` take the number of posts, the research location and the creator's handle, if given.

- **How many posts** is the creator's call. If they didn't say, ask once, plainly ("How many posts can you make this week?"), with what their log shows they did in the last weeks if it has posts. Don't pick a number for them.
- **Research**: the folder or CSVs they named; else ask where their research is. ig-research writes into the folder it was given with `--dir`, or the working folder. `--remember` saves the folders and the handle for next time.
- **Handle**: so their own account isn't listed among accounts to engage with.
- **When they want to start**: the week runs seven days from today (or the next day they haven't already posted on). If they want another start, pass `--start`.
- **Their followers' active times**, if they have them: ask them to open Instagram's professional dashboard > Total followers > Most active times and tell you the busiest days and hours (or paste the numbers). Write that into a temporary text file as given ("Tue Thu Sun", "6p 9p", "Mon 1,234") and pass `--active FILE`; `--remember` keeps it.

## 2. Run the planner

    python3 -B <skill>/scripts/plan.py --research <folders or CSVs> [--me <handle>] --posts <N> [--start YYYY-MM-DD] [--active FILE] [--remember] [--config FILE]

It prints the evidence as Markdown (`--json` gives the same as data): the ideas ranked with how many distinct angles each holds and how many slots the research can fill, the creator's own numbers, when to post, accounts to engage with, and a draft week from today (or `--start`). How the angles are found: each idea's top on-topic winners, one per creator and per promise; the Reels ig-research's hooks file judged on topic come first, Reels promising the same thing in other words are one angle, and a Reel it explicitly marked off topic (not one it only skipped or didn't read) is left out of the score, the angles and the accounts to engage with. Each slot says where its idea came from (`From`: the research file and the Reel's place in it, or the creator's own post). It asks for more research only when every distinct winner is used. How each number is worked out is in `references/method.md`; read it when a number needs explaining.

**Exit 3 means there is nothing to plan from**: no research and no logged posts. Show what it printed (run ig-research on a few ideas, log posts and paste insights) and stop. Never invent a plan without data.

If only one kind of data exists it still runs and says what is missing. With research but no log, it can't know what was already covered or the creator's best times: say so and ask whether anything from the list went up recently.

## 3. Decide the week

The draft is the script's mechanical pass. Your job is the judgement it can't make. Keep each change to the draft, and say why in the slot's evidence.

- **Same idea twice.** The script merges ideas whose names share most words. If two ideas are the same thing in different words and it missed them, keep one slot.
- **Ideas marked thin or "wave passed?"** Thin: fewer than 3 Reels to judge by, so the score is weak. Wave passed: the newest ranked Reel is over 90 days old; a news idea needs a new angle, not a remake. Say so in the slot.
- **Covered before** (not recently): it needs a new angle; name one from the research's top Reels.
- **Two angles of one idea.** A second slot from the same research is a different winning Reel making a different promise: the script folds Reels that promise the same thing in other words into one slot, and drops an angle whose promise the creator posted in the last 28 days (by the log's topics and hooks). Still read the hooks: if two slots really make the same promise, swap one for the next angle in the list. A slot marked "on topic not checked" is a Reel ig-research's hooks step didn't read (or there is no hooks file): open it before relying on it.
- **A follow-up to their own winner** (a post at 1.5× their median shares per reach) is a strong slot: say what the follow-up adds. Research angles making the winner's promise are folded into that slot as its evidence, so the week makes that promise once and says it is a deliberate follow-up.
- **Format.** Research is about Reels, so research ideas are Reels. If the creator's own numbers show another format sharing more (only when each format has 2+ settled posts), say so and offer it for one slot.
- **When.** Use the day and time sources the script gives: their own numbers (8+ settled posts), else their followers' active times (`--active`), else the default from Buffer's study of 9.6M posts (`references/default-times.md`). When it is the default, say plainly that it is a published average, not their data, and ask for their "Most active times" from Instagram's insights to replace it.

Then show:

1. **The week**: a table, one row per slot: date, day, time, format, idea and its angle, where it came from, evidence (the score and the best Reel's link, or their own post's numbers). Under it, one line each on where the days and the time came from.
2. **Accounts to engage with this week**: the script's table, with one line on why (their Reels lead the ideas this week). Comment on their recent posts with something specific; the plan doesn't send or post anything. If the `ig-engage` skill is installed, offer it to draft those comments.
3. **What would sharpen next week's plan**: only what is actually missing (insights for posts with no numbers, research older than 30 days, too few posts to read best times, their followers' active times while the default is in use, more research only if the week ran out of winners).

## 4. Hand the Reels to ig-reel

For each Reel slot, if the `ig-reel` skill is installed (in Claude Code it is listed among the available skills; in Codex, `$ig-reel`), offer to write it: the idea, the angle and its reference Reel (`angle` and `reel` in the `--json` output), who it is for, and the research CSV the slot came from (`file`). Ask before starting, since each one is a full script. If ig-reel isn't installed, give the idea and its best reference Reels so the creator can write it themselves.

After the week goes up, the creator logs each post and later pastes its insights; next week's plan reads them.
