# IG Skills

**To set it up, open Claude Code and paste this message:**

```text
Install the IG Skills plugin from https://github.com/psabbagh/ig-skills
```

Claude Code is the **Code** tab in the Claude desktop app, or the `claude` command in your
terminal. The regular Claude chat can't install plugins. Using Codex, or want to type the
commands yourself? See [Set it up](#1-set-it-up).

Eight free skills for Instagram that research, write, check and plan your Reels, in your
voice. Works in **Claude Code** and **Codex**. No API keys, nothing to sign up for.

## 1. Set it up

"Claude" here means **Claude Code**: the **Code** tab in the Claude desktop app, or the
`claude` command in your terminal. The regular Claude chat (claude.ai, or the Chat tab) can't
install plugins, so pasting the link there won't set anything up.

**The easy way.** Open Claude Code and paste this message:

```text
Install the IG Skills plugin from https://github.com/psabbagh/ig-skills
```

Claude runs the two install commands below for you. When it's done, start a new session so
the skills load.

**Or type the two commands yourself.** In your computer's terminal, one at a time:

```bash
claude plugin marketplace add psabbagh/ig-skills
```

```bash
claude plugin install ig-skills@ig-skills
```

Inside Claude Code you can type the same two lines starting with `/plugin` instead of
`claude plugin`.

**Codex.** In your terminal:

```bash
codex plugin marketplace add psabbagh/ig-skills
```

```bash
codex plugin add ig-skills@ig-skills
```

Then start a new Claude Code or Codex session so it picks up the skills.

**Before you research.** ig-research, ig-engage and ig-profile read Instagram through your own
browser. In Claude Code, install the **Claude in Chrome** extension and sign in to Instagram in
that Chrome first. Codex needs a browser tool instead: see [What it needs](#what-it-needs).

## 2. Your first Reel

Three steps, in the order the skills build on each other. Type each sentence in Claude Code
(or Codex), with your own words in place of the examples.

1. **Learn your voice** (ig-voice). Paste 5 to 10 captions or Reel scripts you wrote and
   posted yourself; fewer than 5 gives a rough profile. It saves your voice profile, and
   ig-reel, ig-caption, ig-engage and ig-profile write in it from then on.

   > *Learn my voice from these captions:* (paste 5 to 10)

2. **Research one idea** (ig-research). It searches Instagram in your signed-in browser for a
   few minutes and saves a spreadsheet and a table of the winners' hooks.

   > *Find the top Reels on "meal prep for busy parents" and show me how the winners open.*

3. **Write the Reel** (ig-reel). It reads the research from step 2. Have your one true story
   ready: what happened, to whom, and what it cost or returned, with your real number. It asks
   for anything missing before it writes a hook, and leaves a blank to fill rather than make a
   number up. If you skip step 2, it offers to run the research, or writes hooks marked
   unproven.

   > *Write me a Reel about how I got my first client from one comment, for freelance designers.*

Then check the script with ig-script, write the caption with ig-caption, and plan your week
with ig-plan.

## 3. The eight skills

You don't have to type a command: ask in plain words and the right skill starts. If you prefer
a command, type `/` in Claude Code and pick one (they show as `ig-skills:ig-reel` and so on),
or `$` in Codex.

| Skill | Try this |
|---|---|
| [**ig-research**](#ig-research): finds the top Reels on your idea, and why they worked | *Find the top Reels on "meal prep for busy parents" and show me how the winners open.* |
| [**ig-reel**](#ig-reel): writes your Reel from what already worked | *Write me a Reel about how I got my first client from one comment, for freelance designers.* |
| [**ig-script**](#ig-script): checks a script makes sense to a cold listener | *Check this Reel script before I record it:* (paste your script) |
| [**ig-voice**](#ig-voice): makes your text sound like you, not AI | *Learn my voice from these captions:* (paste 5 to 10) |
| [**ig-caption**](#ig-caption): writes your caption and checks it | *Write the caption for this Reel script.* |
| [**ig-profile**](#ig-profile): scores your profile out of 100 and rewrites it | *Score my Instagram profile @yourhandle and rewrite the weakest parts.* |
| [**ig-engage**](#ig-engage): replies to your comments, writes comments on others' posts | *Go through the comments on my latest Reel and list everyone who commented GUIDE with a DM to send.* |
| [**ig-plan**](#ig-plan): plans your week: what, when, and who to engage with | *Plan my Instagram week. I can post 4 times.* |

They work together: research an idea, write the Reel from it, check the script, write the
caption, then plan the week from your research and your own posts. Each one also works alone.

### ig-research

The virality skill. It finds the Reels doing best on your idea or niche, ranked by how often
viewers shared them for their views, and flags ones whose views look bought.

Then it breaks down why the top 5 worked:

- the hook and the kind of move it makes
- the opening frames
- the length
- how the middle is built
- the payoff
- the ask at the end
- who a viewer would send it to

Each part says whether it was seen on screen, heard, read in the caption, or is a judgement.

It saves it all as a swipe file you can shoot from: a spreadsheet, plus a table of every
winner's spoken and on-screen hook with the breakdowns.

### ig-reel

Writes your Reel off 26 hook formulas.

- It starts from what already worked on your idea (from ig-research).
- It writes three hooks, **scores the hooks first** and drops weak ones before writing any
  script.
- Then it writes the script and its on-screen text in your voice (with an ig-voice profile).
- It asks for your real number before writing hooks and never makes one up, or a client or a
  result. If you don't have it, it leaves a blank for you to fill.

### ig-script

Checks that a script makes sense to someone hearing it cold. A fresh listener who hasn't seen
your notes hears it once and says what it's about; you get the gaps and the smallest lines
that fix them. Paste the script or give it the file.

### ig-voice

Makes a caption, script, comment or DM sound like you, not like AI. It learns your voice from
5 to 10 of your own past posts, then flags the lines that sound machine-written or least like
you and rewrites them.

### ig-caption

Writes your caption and checks it:

- what shows before "... more"
- the first line
- one call to action, and that it matches the one in your Reel
- the words people search for
- the hashtag limit
- any blank left unfilled

Ends with text ready to paste.

### ig-profile

Optimizes your profile. It scores it out of 100 (name field, bio, link, highlights, pinned
posts, grid) and rewrites the parts that lose the most points, biggest first.

### ig-engage

Writes your comments on other people's posts, and handles your replies.

- It sorts the comments under your post: who commented your keyword, questions, possible
  leads, comments worth a real reply, praise, spam.
- It drafts and checks a reply to every question, lead and comment worth answering, in reply
  order, ready to paste under each commenter.
- It lists everyone who commented your keyword with a DM to send each.
- Before you comment on someone else's post it reads it, and it won't let you repeat a comment
  you've used before.

### ig-plan

Plans your whole week: what to post, when to post, and who to engage with.

- It ranks your ideas from your research, and turns the different winning Reels in one
  research run into separate ideas, so one run can fill a week.
- It skips topics you covered recently.
- It picks days and times from your own numbers (once you've logged 8 posts with their
  numbers), else from your followers' most active times that you paste from Instagram, else
  from a published study, and says which.
- It lists the creators worth engaging with and hands each Reel idea to ig-reel.
- It also keeps a log of what you posted and its numbers.

## What it needs

- **Claude Code** (a paid Claude plan) or **Codex** (a ChatGPT plan that includes it). The
  skills themselves are free.
- **Python 3.9 or newer.** The scripts use only what comes with Python; nothing else to
  install. The Python that comes with macOS works. If you have none, get it from
  [python.org](https://www.python.org/downloads/) or with `brew install python`.
- **No API keys and no accounts** beyond the Instagram you already use.
- **To read Instagram**: your own browser, signed in to Instagram. Three skills use it:
  ig-research always (it has no other way to search), ig-engage to read the comments on a
  post or someone else's post, and ig-profile to read your profile. It only reads, the way you
  would scrolling, at a person's pace. It never asks for your password: if Instagram wants you
  to sign in, you do it yourself.
  - **Claude Code**: install the Claude in Chrome extension and sign in to Instagram in that
    Chrome.
  - **Codex**: Codex needs a browser tool connected that can open a page and run JavaScript in
    your signed-in Chrome. Without one, ig-research can't search Instagram and says so; ig-engage
    works from comments you paste and ig-profile from text and screenshots you paste.
- **Optional, for transcripts of Reels you pick** (ig-research): a Mac with Apple silicon,
  ffmpeg and a free speech model that runs on your computer. The skill gives the setup steps
  and asks before downloading any Reel's audio. Everything else works without it.

## What it never does

It never posts, comments, likes, follows, sends a DM or edits your profile. Everything it makes
is copy-ready text that you post yourself. Automating those actions breaks Instagram's terms
and gets accounts restricted, so none of the skills do it, and none schedule posts.

## Where your files live

| What | Where |
|---|---|
| Your voice profile and the samples it learned from (ig-voice) | `~/.config/ig-voice/` |
| Your posting log and saved settings (ig-plan) | `~/.config/ig-plan/` |
| The comments you've posted on others' posts, so none repeat (ig-engage) | `~/.config/ig-engage/log.md` |
| Research: the spreadsheet, the hooks table, transcripts (ig-research) | The folder you name, or the folder you're working in |

`~` is your home folder. Delete a folder to start fresh.

The skills' scripts run on your computer and upload nothing themselves. The text you work on
(your script, captions, comments, what's read from Instagram) goes to Claude or Codex like
anything else you put in a chat.

**To keep a test run out of your real files**, set these before you start:

| Setting | What it moves |
|---|---|
| `XDG_CONFIG_HOME` | The folder all three skills above save in (instead of `~/.config`) |
| `IG_VOICE_PROFILE` | The ig-voice profile file itself, e.g. `/tmp/voice-test/voice.md`; its samples go next to it |
| `IG_PLAN_LOG` | The ig-plan posting log file (its saved settings move with `XDG_CONFIG_HOME`, or `--config`) |
| `IG_ENGAGE_LOG` | The ig-engage comment log file |
| `IG_VOICE_SKILL_DIR` | Not a file location: which copy of the ig-voice skill ig-engage runs (`IG_VOICE_DIR` is the old name and still works) |

## Uninstall

```bash
claude plugin uninstall ig-skills@ig-skills
```

```bash
codex plugin remove ig-skills@ig-skills
```

Your voice profile, posting log and research stay where they are.

## For developers

Each skill is in [`skills/`](skills/), with its scripts and its own tests; `tests/` checks the
repo as a whole. The tests use only the standard library. From the repo root (it exits non-zero
if any suite fails):

```bash
fail=0; for d in tests skills/*/tests; do python3 -m unittest discover -s "$d" || fail=1; done; test $fail = 0
```

## License

MIT. See [LICENSE](LICENSE).
