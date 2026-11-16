---
name: ig-engage
description: Handle the comments under your own Instagram posts and write comments on other people's, in your own voice. Sorts a post's comments into who used your call-to-action keyword, questions, possible leads, comments worth a real reply, praise and spam, marks the ones you already answered, then drafts a checked reply to every question, lead and comment worth answering, in reply order, as a copy-ready list keyed to each commenter; lists everyone who commented the keyword with a drafted DM each, as a copy-ready list or CSV; reads someone else's post before you comment on it and refuses a comment that repeats a line or shape you already used elsewhere. Use when someone wants to go through their comments, find who commented the keyword, send the DMs they promised in a Reel, reply to comments, or write a comment on another creator's post, even if they don't say "engage". Never posts, likes, follows or sends anything.
argument-hint: "<your post link + KEYWORD + link to send> | <someone's post link to comment on>"
---

# ig-engage

Two jobs, both ending in text the creator posts themselves:

- **Under your own post**: sort the comments, then **draft a reply to every comment worth answering** (questions, possible leads, comments with something in them), in reply order and in the creator's voice, each one checked, as a copy-ready list keyed to the commenter. Also the keyword DMs the Reel promised ("comment GUIDE and I'll send it over").
- **On someone else's post**: read what it actually says, write a comment about that, and make sure it doesn't repeat one you've posted before.

The scripts do the reading, sorting, listing, checking and logging. You do the writing.

**It never posts, comments, likes, follows or sends a DM.** Automating those breaks Instagram's terms and gets accounts restricted. Every output is copy-ready text. Don't offer to send anything, and don't click anything on Instagram but links.

**No invented facts under their name.** A reply or comment uses only what the creator told you, what is in their post, or what is in the post being commented on. If an answer needs a fact you don't have (a price, a date, whether something works on Windows), write the reply with a gap and ask them.

Below, `<skill>` is this skill's folder and `<tmp>` a temporary folder (the session scratchpad if there is one). All commands: `python3 -B <skill>/scripts/engage.py ...`.

## 1. Work out which job

From `$ARGUMENTS` and the conversation:

- **Their own post** (their Reel link, or pasted comments): get their **handle**, the **keyword** the Reel asked for (several are fine) and the **link** to DM. If they didn't say, ask for all of them in one question; the sort and the reply drafts run without the keyword and link, the DM list needs both.
- **Someone else's post** (a link to another account's post): step 5.

## 2. Get the comments

Either way works; don't make them choose if they already pasted.

- **Pasted**: write what they pasted to `<tmp>/comments.txt` as is. The script reads `handle: text` lines (indent a reply under its comment) and text copied straight from the comment section on instagram.com. Ask for their handle (`--me`) so their own replies count as answers.
- **From the post link, in their own browser** (read-only). **Claude Code:** Claude in Chrome; load `tabs_context_mcp`, `tabs_create_mcp`, `navigate`, `javascript_tool`, `tabs_close_mcp` in one ToolSearch call. **Codex:** a browser tool that runs JavaScript in their signed-in Chrome; if there is none, ask them to paste the comments.

  Open a new tab at the post link. If it lands on `/accounts/login`, ask them to sign in themselves in that browser, then go on. Never ask for a password and never type one. Read `<skill>/scripts/instagram-comments.js` and send its **entire text** as one JavaScript call, ending with

      __igcomments.start({code: "<code>", max: 300, replies: true})

  `<code>` is the part after `/reel/` or `/p/` in the link. Call `await __igcomments.wait(25000)` until `phase` is `done` or `error`, then `__igcomments.checksum()`, then `__igcomments.dump(0, 100)`, `dump(100, 100)`… until all lines are out. Save each result **verbatim** as `<tmp>/c-1.json`, `<tmp>/c-2.json`. It goes at a person's scrolling speed (1.5 to 3 s a page; 300 comments with replies take two to four minutes). A `note` about pushback means Instagram slowed it: use what was read and don't retry in a loop. Close the tab when done.

## 3. Sort them

    engage.py sort <tmp>/c-*.json --keyword GUIDE --lines <lines> --hash <hash>
    engage.py sort <tmp>/comments.txt --keyword GUIDE --me <their handle>

Exit with `MISMATCH` means the copy doesn't match the page: dump again. It reads every comment and reply that loads on the post's page, the same ones the creator sees there. Instagram's comment count is often higher, because it also counts comments its filter hid, ones caught by the creator's hidden words, ones from restricted accounts and deleted ones, which nobody can load; the header says so in those words when the numbers differ. Pass that on as it is; it is not a reading error. It prints counts per group (used the keyword, possible lead, question, worth a real reply, praise, spam or noise), how many in each they already answered, and the reply order: leads first, then questions, then comments with something in them, then keyword comments, then praise. Spam, follow bait and friend tags get no reply. A keyword comment that also asks something is tagged `+question` and moves up.

One-word comments that aren't the keyword are listed together (people often comment the word from another Reel); if they meant it, run again with that word as a second `--keyword`. Show the counts and the order as printed. The sort is word rules, not judgement (`references/sorting.md`): skim the list and move anything it got wrong before writing replies.

## 4. Draft the replies

This is the main job under their own post: a reply for every comment worth answering, not a list for them to work through.

    engage.py replies <same input> --keyword GUIDE --me <their handle>

prints the comments to answer, numbered in reply order: possible leads, questions, comments worth a real reply, and keyword comments that also asked something. Each comes with its group and how to answer that kind. Plain keyword comments are left out (the DM is the answer) and so is praise (`--with-praise` adds it if they want to thank people).

Write one reply for **every** comment listed, in the creator's voice (their `ig-voice` profile if they have one, otherwise their own captions and replies you can see), using `references/replies.md`. Save them to `<tmp>/replies.txt`, one per line:

    @lena.ops: Thanks! Sending you a DM so we can look at your setup
    @raj.dev: Both. I built it on a Mac and it runs the same on Windows

A fact you don't have goes in as `[ ]`; the check fails it until the creator gives you the fact, so ask. Then check them all at once:

    engage.py replies <same input> --keyword GUIDE --me <their handle> --drafts <tmp>/replies.txt

Every draft goes through the reply check (too short to answer a question, a sales line nobody asked for, a link, a gap) and through `ig-voice` when it is installed (step 6). It exits 2 while any reply is missing, failed or flagged by `ig-voice`; rewrite those lines in the file and run it again (two rounds is enough). It ends with **Ready to paste**: each commenter's handle and comment, then the reply. Show that list. They paste each reply under the comment themselves.

## 4b. Keyword DMs

Get the link first: if they didn't give it in step 1, ask now. Write two or three short versions of the DM in their voice. Put `{link}` where the link goes (and `{handle}` or `{keyword}` if they want them); those three placeholders are what `dms` fills in for each person, and `engage.py check --kind dm` accepts them and fails any other `{...}`. Check each version (step 6). Rotating versions keeps a stack of identical DMs from reading as a bot. Then:

    engage.py dms <same input> --keyword GUIDE --me <their handle> --link "<their link>" \
      -m "<version 1>" -m "<version 2>" [--skip already-sent.txt] [--csv <folder>]

`--csv` takes a file name or a folder; given a folder it writes `dms-<post code>.csv` inside it (`dms-<keyword>.csv` for pasted comments) and prints the path. It lists each person once, oldest comment first, with their profile link, their comment, a note when they also asked something (answer it in the DM) or were already answered under the post, and the DM with the link filled in. Show the list. They open each profile and send it themselves; a DM to someone who doesn't follow them lands in that person's message requests. When the creator's own reply under a comment says they sent it ("Sent! Check your DMs"), the list marks that person; `--new-only` leaves them out. `--skip` takes a file of handles already sent, one per line, for a second pass later.

A single reply can also be checked on its own: `engage.py check --kind reply --to "<their comment>" "<your reply>"`.

## 5. A comment on someone else's post

1. **Read the post first.** In the browser as in step 2, send the whole `instagram-comments.js` ending with `__igcomments.start({code: "<code>", max: 20, replies: false})`, wait, dump, save as `<tmp>/post-<code>.json`, then

       engage.py read <tmp>/post-<code>.json

   It prints the owner, the caption and the top comments. If the browser can't be reached, ask them to paste the caption. Never comment on a post you haven't read.
2. **Write two options**, each about one specific thing the post says: a detail, a number, a step, a claim, with a reaction, a question, or something from the creator's own experience that they told you. Not praise that fits any post, not a pitch, no link, no "check my page". The top comments show what is already said; don't repeat them. `references/comments.md` has what makes a comment worth reading.
3. **Check each one**:

       engage.py check --kind comment --account <the post owner's handle> --post <tmp>/post-<code>.json "<comment>"

   It fails generic lines, links, self-promotion and hashtags, warns when the comment shares no word with the post, and **refuses** a comment that repeats a line, an opening, or a sentence shape from the creator's comment log, naming the earlier comment. Rewrite until it passes; never present a refused comment.
4. Show both options with the post link. When they say which one they posted, log it:

       engage.py log add --account <the post owner's handle> --post <post link> "<the comment as posted>"

   The log is `~/.config/ig-engage/log.md` (or `$IG_ENGAGE_LOG`, or `--log`), one line per comment; `engage.py log show` prints the last 20. Log only what they say they posted.

## 6. Voice, on every comment, reply and DM

`engage.py check` and `engage.py replies --drafts` run `ig-voice`'s checker by themselves when `ig-voice` is installed. They use the first copy found: the folder in `$IG_VOICE_SKILL_DIR` if set (the `ig-voice` skill folder itself, not the profile; `$IG_VOICE_DIR` is the old name and still works), then the `ig-voice` folder next to this skill in the same pack, then `~/.claude/skills`, `~/.codex/skills`, `~/.agents/skills`. The output names the copy used; add `--verbose` to also list other copies it found, for someone with two copies who wants to tell which one ran. A draft ig-voice still flags counts as not ready: `check` exits 2 and its `--json` says `"ok": false`. Rewrite the lines it lists for a rewrite, use its cleaned text when it fixed characters, and check again; two rounds is enough. With an `ig-voice` profile it also flags lines least like them; without one, say once that the results get better after `ig-voice learn`.

Three different settings, not to be mixed up: `$IG_VOICE_SKILL_DIR` says where the `ig-voice` skill is; `$IG_VOICE_PROFILE` (read by `ig-voice`) says which voice profile file it uses, default `~/.config/ig-voice/voice.md`; `$IG_ENGAGE_LOG` says where this skill's comment log is (step 5). If a skill-folder variable points somewhere without `scripts/voice.py`, the output says it was ignored.

If `ig-voice` isn't installed, the check says so; write from the creator's own captions and comments you can see, and say once that this would be better with `ig-voice`.

## 7. Show the result

- Their own post: counts (with the count note if Instagram's number is higher), the ready-to-paste replies keyed to each commenter, the DM list (and CSV path).
- Someone else's post: the post link, what it says in one line, two checked comments.
- One line: nothing was posted or sent; they post it themselves.

Keep their followers' handles and comments in the session or in files they choose. Don't paste them anywhere else.
