---
name: ig-profile
description: Score an Instagram profile out of 100 and rewrite the parts that lose the most points, biggest loss first. Reads the person's own profile in their signed-in browser (read-only) or from pasted text and screenshots, rates the name field, handle, bio, next step, links, photo, account type, highlights, pinned posts, grid and recent posting against a rubric built from what Instagram itself says about search and profiles, then writes a new name field, bio lines, highlight titles and what to pin, plus the changes that can't be written for them. Use when someone asks to review, audit, score, fix or optimize their Instagram profile or bio, asks why visitors don't follow, or wants a better name field or highlights, even if they don't say "profile". Never edits Instagram.
argument-hint: "[@handle, profile link, or pasted profile text and screenshots; optionally the search words people would use]"
---

# Instagram profile

A stranger lands on a profile from a Reel, a search or a share, and decides in a few seconds whether to follow. This skill scores what they see out of 100, then rewrites what loses the most points first. The person applies the edits; this skill changes nothing on Instagram.

The rubric is ours, in `references/rubric.json`: 11 parts, 23 criteria, 100 points. Each criterion is marked `platform` (it rests on something Instagram itself says, like search matching the name field and bio, the 150-character bio, 5 links, 3 pins) or `judgement` (our view of what makes a stranger follow). `references/sources.md` has every source with its date. `scripts/score_profile.py` does the arithmetic and refuses to run if the points don't add to 100.

## 1. Get the profile

Use the first of these that works. Never log in for the person, never ask for a password, and never click Edit profile or anything that changes the account.

- **Their own signed-in browser** (if the host has browser tools, such as Claude in Chrome): open `https://www.instagram.com/<handle>/` and read it. If it shows a login page, ask them to sign in themselves, or fall back to screenshots. Read only.
- **Pasted text and screenshots:** ask for a screenshot of the top of the profile (name, bio, link, highlights) and one of the grid scrolled past the first rows.

Collect into a scratch `profile.json`, outside the person's project:

```json
{
  "name": "", "handle": "", "bio": "line one\nline two",
  "links": [{"url": "", "title": ""}],
  "category": "", "account_type": "creator|business|personal|unknown",
  "highlights": ["title", "title"],
  "pinned": ["what each pinned post is"],
  "grid": "what the top three rows show, covers readable or not",
  "last_post": "YYYY-MM-DD",
  "posting": "rough pace over the last three months"
}
```

On the web: pinned posts carry a pin icon on the grid; the date of the latest post is in the post's `<time datetime>`; a "Professional dashboard" link means a creator or business account. Leave a field out if you can't see it; don't guess.

Ask, if you can't tell from the profile: **who should follow this account, and what would they type into Instagram search to find it?** Two or three search phrases. Everything is scored against that answer.

## 2. Count, then rate

```bash
python3 <this skill's directory>/scripts/score_profile.py check profile.json --keywords "phrase one, phrase two"
python3 <this skill's directory>/scripts/score_profile.py rubric
```

`check` counts what can be counted (bio length against 150, a URL typed into the bio, "font" letters search may not match, handle shape, link and pin counts, emoji-only highlight titles, days since the last post, whether the search phrases appear) and says whether an `ig-voice` profile exists. It decides nothing.

Then rate every criterion from `rubric` as `met`, `partly`, `missed` or `unseen`, using the rubric's own `met` / `partly` / `missed` descriptions, with a one-line reason a person can check by looking at their profile. Use `unseen` only for what you truly couldn't see (it counts 0 and is listed so they can check). Write `ratings.json`:

```json
{"ratings": {"name.search_term": {"rating": "missed", "reason": "name field is just the person's name"}, "...": "..."}}
```

```bash
python3 <this skill's directory>/scripts/score_profile.py score ratings.json
```

It prints the total, each part's points with the reasons, and the **fix-first list**: criteria ordered by points lost. Don't change the numbers by hand; change a rating and re-run.

## 3. Rewrite, biggest loss first

Work down the fix-first list. For each item that text can fix, write it; for the rest, say exactly what to make or change. `references/rewriting.md` has the patterns and examples for every part; read it before writing.

- **Name field:** the name people know + the search phrase, e.g. `Ana Ruiz | Meal prep for one`. One or two options.
- **Bio:** two or three versions, each at most 150 characters: who it's for and what they get, one proof, one ask that matches the first link. The search words as plain words.
- **Links:** which link goes first and the title to give it.
- **Highlights:** titles in newcomer order (what to show in each), one or two words each.
- **Pinned posts:** which existing posts to pin and why, each doing a different job (intro, proof, offer). If no post does a job, describe the post to make.
- **Handle:** suggest a change only if it loses real points, and say the cost: followers may be notified, large accounts may be reviewed, old links and mentions break.
- **Things text can't fix:** photo, covers, posting pace, account type. One concrete instruction each.

**Voice.** If `check` found an `ig-voice` profile, read it and write the bio and name in that voice; if the `ig-voice` skill is installed, you may run its `check` on the bio drafts. If not, write plainly and say so in one line. Don't install anything.

**Check the rewrite.** Put the proposed name, handle, bio, links, highlights and pins in `rewrite.json` (same shape as `profile.json`) and run `check` on it with the same keywords. Fix every `FAIL` (a bio over 150 won't save) and re-run.

Optionally score the rewrite (re-rate only what the rewrite changes) to show the expected score after the text edits, labelled as an estimate.

## 4. Hand it over

Show, in this order:

1. **Score** out of 100 and the part table from `score`, as printed.
2. **Fix first:** for each of the top losses, the rewrite ready to paste (name field, bio, link title, highlight titles) or the instruction, with the points it should win back.
3. **What text can't fix,** one line each.
4. **Where to tap:** Edit profile for name, bio and links; open a post > ... > Pin to main grid; hold a highlight > Edit highlight.
5. One line saying which criteria are platform facts and which are judgement, pointing to `references/sources.md`.

Stop there. The person makes the edits.
