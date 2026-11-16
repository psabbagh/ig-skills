---
name: ig-research
description: Research a Reel idea on Instagram before making it. Finds the top Reels on that idea through your own signed-in browser, with views, likes, comments and shares, ranks them by how often viewers shared them for their views, flags Reels whose views look bought, writes a CSV, reads the spoken and on-screen hooks of the winners, and breaks down why each top Reel worked (hook, opening frames, length, structure, payoff, the ask, and who a viewer would send it to), saying which parts were seen and which are inferred. Use when someone has an idea for a Reel and wants to see what already exists on Instagram and what performed, gives an Instagram search query or Reel link, or asks what is doing well on a topic, even if they do not say "research".
argument-hint: "<Reel idea, or an Instagram search query or link> [Reels to collect, default 50]"
---

# Instagram research: the top Reels on an idea

The goal is the list someone needs before making a Reel: what already exists on this idea, and which of those Reels performed. It searches several phrasings of the idea on Instagram and ranks everything by how often viewers shared each Reel against its views, then reads how the winners open.

It is free and needs no API key. Instagram's keyword search exists only for signed-in users and has no public API, so `scripts/instagram.js` runs inside the person's own signed-in browser tab: it lets the search page send its request once, replays it for each phrasing (what the page's own infinite scroll does), then looks up each Reel's stats. Nothing leaves the browser except the requests Instagram's own page makes.

Below, `<skill>` is this skill's directory (the folder holding this file) and `<tmp>` is a temporary folder (the session scratchpad if there is one).

## Why shares come first

Instagram has said publicly how it ranks Reels for people who don't follow the creator. The strongest signal is sends per reach: of the people a Reel reached, how many sent it to someone in a DM. Next comes likes per reach, then watch time (how much of the Reel people watch). A send is a viewer putting their own name behind the Reel to a specific person, which is why it weighs most.

Two consequences shape everything here:

- **Rank by shares per view, not by views.** A Reel with 2M views on a big account can be shared less, per view, than a 60K Reel from a small one. The small one is the better reference: its idea carried it, not the audience. Reach isn't public for anyone else's Reel, so views stand in for it.
- **The send test.** Before calling a Reel a model to follow, ask who a viewer would send it to and what they would say when they did ("my cofounder: we should set this up"). If nobody obvious comes to mind, the Reel may be worth saving but not sending, and it will travel less. Ask the same of your own idea.

## 1. Turn the idea into phrasings

From `$ARGUMENTS` take the **idea** and the **count** (Reels to collect, default 50, at most 100).

Write 3 to 5 search phrasings: what someone would actually type into Instagram search, 2 to 4 words each. Put the person's own wording first. If they gave a query or link, it is phrasing 1; add 2 or 3 variants unless they said to search only that.

**Keep the idea's action in every phrasing**: the verb or the claim, not just its nouns. Search matches words, so a phrasing that keeps the nouns and drops the verb finds a neighbouring idea instead. For "Claude can watch YouTube videos", "claude code video skill" returned mostly "make animated videos with Claude", and "claude youtube skill" partly returned "let Claude run your YouTube channel". Watch the subject too: "claude learn from youtube" was read as people learning Claude from YouTube. Vary what changes the results while keeping the action: a synonym ("watch" / "understand"), the outcome ("learn from YouTube"), the format ("tutorial", "hack"). Avoid near-duplicates that return the same Reels.

Search only sees the words in captions, so cover the ways creators actually caption this idea. Among the phrasings, always include:

- **Another verb** for the same action: "analyze", "breakdown", "summarize", whatever fits. In testing, "claude analyze any video" found an 889K Reel at position 1 that no "watch" phrasing surfaced.
- **The pain in plain words**, the way a hook says it: "claude can't watch youtube".
- **The comment-keyword style** creators put in captions: "comment youtube skill". It surfaces "Comment YOUTUBE" Reels the other phrasings miss, but it also drifts toward neighbouring ideas, so the drift check in step 3 matters more.

Keep the total at 5 at most: each phrasing costs search pages, and Instagram pushes back on heavy use. Some Reels stay out of reach whatever the wording: a caption that never names the idea won't come up.

## 2. Search in the browser

**Claude Code:** use Claude in Chrome. Load in one ToolSearch call: `tabs_context_mcp`, `tabs_create_mcp`, `navigate`, `javascript_tool`, `computer`, `tabs_close_mcp`. **Codex:** use a browser tool that can run JavaScript in a signed-in Chrome tab. If there is none, say Instagram can't be searched here and stop.

Open a new tab at

    https://www.instagram.com/explore/search/keyword/?q=<URL-encoded phrasing 1>

If it lands on `/accounts/login`, ask the person to sign in to Instagram in that browser, then go on.

First check whether the helper is already in the tab: `window.__igsearch && window.__igsearch.version` returns 2 when it is (an earlier search in the same tab, with no navigation since). If it does, send only the `start` line below. Otherwise read `<skill>/scripts/instagram.js` and send its **entire text** as one JavaScript call, with this line added at the end:

    __igsearch.start({queries: ["<phrasing 1>", "<phrasing 2>", ...], limit: <count>})

It runs in the background in the tab. Call `await __igsearch.wait(25000)` until `phase` is `done` or `error`. 50 Reels take about 30 to 60 seconds.

- `mode: "dom"`: no search request could be captured, so only the first phrasing's visible posts were used. Say so.
- A rate-limit `note`: Instagram pushed back. Use what was collected and don't retry in a loop.

Then call `__igsearch.checksum()`, then `__igsearch.dump(0, 50)`, `dump(50, 50)`… until all rows are out. Send each `dump` call **bare**, exactly as written, so its array comes back as it is. Never wrap it in `JSON.stringify(...)` or a template string: that turns it into one long string, and the browser tool cuts any single string off at about 1,000 characters (an array of 50 lines comes back whole). Save each result **verbatim** as its own file, `<tmp>/ig-1.json`, `<tmp>/ig-2.json`. They are JSON arrays of tab-separated lines. Copy them exactly: no reformatting, unescaping or tidying. Keep the tab open for step 4.

## 3. Rank and report

    python3 -B <skill>/scripts/report.py \
      --idea "<idea>" --queries "<phrasing 1>" "<phrasing 2>" ... \
      --ig <tmp>/ig-*.json --ig-rows <rows> --ig-hash <hash> --dir "<folder>"

`<folder>` is where the person keeps research; leave `--dir` out to write into the working folder. Exit 2 means the copy doesn't match what the page collected: dump again and rewrite the files; never correct a number by hand. It writes `research-<idea>-<date>.csv` and prints a summary and a Markdown table of the top 25 (`--top N`, `0` for all).

**The order.** Rows are ranked by shares per 1,000 views, then likes per 1,000 views, among Reels with 10K+ views and a share count. The views are Instagram-only plays: the count shown on a Reel cross-posted to Facebook adds Facebook plays that the shares didn't come from. Reels under 10K views or without a share count follow by views, since a few shares on a few hundred views is noise. `--sort views` gives the plain order by views. Views stay in the table, so a 2M Reel that shares less still shows its reach.

**Low reactions.** A Reel with 10K+ views whose likes and comments come to under 2% of its views is marked ⚠ and listed last: its views may have been bought (a boosted post or a sponsor's ad), or it flopped. In testing this marked about 1 Reel in 10. A Reel with likes hidden can't be checked and is left unmarked; the summary counts them. Instagram gives no boost flag, so this is a guess from the numbers, not proof.

**Check for drift** before showing it. Skim the captions of Reels found by only one phrasing (`found_by` in the CSV). If most of one phrasing's own Reels are about a different idea, run the report again with `--drop N`: that leaves out the Reels found only by phrasing N and keeps the ones it shares with other phrasings. Say which phrasing you dropped and why.

**Read the timeline before calling the idea validated.** Top views only show the idea worked once. The summary's `By month` line shows when: how many of the kept Reels were posted each month with their total views, and the next line gives the newest Reel past 10K views. Instagram's search can't filter by date, so this is where recency shows. Say in one line which the idea is:

- **A news wave that has passed.** A news idea (a launch, an update, a new feature) whose Reels and views bunch in one month, months back, with nothing recent past 10K. Those Reels rode the news, and what they show may have changed since. Such an idea needs a different angle (what changed since, what months of use taught, a use the launch Reels missed), not a remake.
- **Still live.** An evergreen idea (a how-to, a pain, a habit), or a news idea with winners in the last month or two. Its references show what works now.

A Reel under 7 days old says "still climbing": its views aren't final.

Show the summary and the table as printed, with that one line, and link the CSV. If they asked something specific (the outliers, what the top ones have in common), answer it from the CSV. What each column means is in `references/numbers.md`; read it when a number needs explaining.

## 4. Hooks of the top Reels, and why they worked

What the winners open with, and how they are built, is what a new Reel is written against, so a run isn't finished without this step. Don't wait to be asked.

Take the top on-topic Reels in the report's order, after the drift check, at most 10 (8 is a good default). Skip Reels marked ⚠ and say which you skipped. Judge "on topic" from the captions: a list of tools, or a different tool, isn't this idea however big, so leave it out and say so. If a caption can't place a Reel, include it.

**Load the helper once.** Stay in the same tab; this step never navigates it. Check `window.__ighooks && window.__ighooks.version`: if it returns 2 the helper is already there. Otherwise read `<skill>/scripts/instagram-hooks.js` and send its **entire text** as one JavaScript call, ending with

    __ighooks.start({codes: ["<code>", ...]})

(if it was already loaded, send only that line). Then call `await __ighooks.wait(25000)` until `done`, then `__ighooks.dump(0, 10)`, sent bare like step 2's dumps. `<code>` is the Reel code at the end of its URL. Each line is the code, the creator, the length in seconds, the first 12 seconds of Instagram's own captions (the opening) and the last 10 seconds (the ending: payoff and ask). Both are empty when the Reel has no caption track.

**Spoken hook.** The first sentence of the opening. These captions mishear names ("Clod" for Claude), so fix them, and they can clip the first word or two ("You're using Claude Code" for "If you're using Claude Code"), so check the start against the first frame. If there's no on-screen caption to check it against, mark it "[first word or two cut off]".

**Frames.** `await __ighooks.frame("<code>", <second>)` shows that Reel paused at that second over the page, full height and without Instagram's buttons; take a screenshot at `scale` 0.5. Three frames per Reel, in this order:

1. **0.5 s**: what the first frames show, and any text hook.
2. **2.5 s**: whether a text hook appears or changes, and what the opening has turned into.
3. **The last 2 seconds** (its length minus 2): the end card, if any: the ask, the payoff on screen.

A Reel with no caption track usually has captions burned into the picture. Then add frames at 1.2 s and 4 s, zoomed on the caption band (`zoom` at `scale` 0.5), to read the spoken hook; put any word you didn't see in [brackets], and add a frame only where a word is still missing. If it has neither, write "no captions"; a transcript (`references/transcripts.md`) would get it, but that's a download, so it waits for the person's yes. When `frame` says the Reel has no plain video file, fall back to `scripts/instagram-seek.js` on the Reel's own page (its header says how). `__ighooks.close()` takes the frame away when you are done.

A **text hook** is words placed on screen to be read, such as a banner or headline; word-by-word captions aren't one. If there is none, write "None" and what the opening shows in a few words. Most Reels have none, so "None" is a finding, not a failed read. A text hook that first appears after about 3 seconds would be missed.

**Would send to.** For each Reel, one line: who a viewer would send it to, and what they'd say when they did. This is the send test from the top of this file. It is your judgement from the hook and the caption, so say so above the table, and write "nobody obvious" when no one comes to mind.

**Save the hooks.** Write them to `research-<idea>-<date>-hooks.md` next to the CSV, same date: a table of Reel link, creator, views, shares per 1K views, spoken hook, text hook and would send to, one row per Reel, and a line saying how the spoken hooks were read (captions, frames). Keep this table's columns as they are: ig-reel reads it.

**Why they worked.** For the top 5 of those Reels (all of them if fewer), a short breakdown, from what was read above and nothing more. What each part is and how to tell its kind is in `references/breakdown.md`; read it before the first one. For the structure, payoff and ask read the whole caption track, `__ighooks.transcript("<code>")`, and the post caption, `__ighooks.caption("<code>")`. Write `<tmp>/notes.json` as that file shows, then

    python3 -B <skill>/scripts/breakdown.py --csv <the research CSV> --notes <tmp>/notes.json

It refuses notes that pass a judgement off as seen (the hook type, structure and "would send to" are always inferred), a "seen" part without the second of its frame, or a missing part (write `"basis": "unread"` rather than guess), and it writes one block per Reel under "## Why they worked" in the hooks file, after the table, with the length from the CSV.

**Show** the hooks table after the report, with one line on the pattern: how many share the same spoken hook, how many have a real text hook. Then the breakdown blocks as printed, with one line on what the winners share (the structure, the ask). Then close the frame and the tab. If Instagram pushes back, stop and report what you have.

**Cost**, measured on the live site: one lookup per Reel (paced about 2 s apart), 3 screenshots per Reel with a caption track and 5 without (more only where a word is still missing), plus a few short calls for the dump, transcripts and captions. Send each Reel's frames and screenshots as one batch of browser calls when the tool allows it. In a test run, 3 Reels took 75 seconds and 11 screenshots that way; 8 Reels take about 3 to 5 minutes and 24 to 40 screenshots, longer when each call goes on its own. The helper is sent once for the whole step.

## 5. On request: beat their usual, and transcripts

Both are only for the Reels the person is actually considering, never every result. Ask which (the `#` from the table, at most 10) unless they already named them. **Before any pick, show the candidates first:** a short numbered table with a clickable link to each Reel, the creator, the date with its age as the table prints it ("2026-07-27 (3 mo)"), the views, and its spoken and text hook from step 4. They need to watch them to choose. A question dialog hides the chat behind it, so ask after the table, referring to the numbers.

- **Versus the creator's recent Reels**: raw views favour big accounts, so this divides a Reel's views by the median of its creator's 15 most recent Reels. Steps in `references/creator-check.md`.
- **Transcripts** of the picked Reels, made on this computer: steps and setup in `references/transcripts.md`.
