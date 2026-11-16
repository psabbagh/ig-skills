---
name: ig-caption
description: Write an Instagram caption and check it before it goes up. Decides first whether the caption has to carry the hook (a photo or carousel) or back up a Reel that already hooked the viewer, writes it, then checks it with a script that draws what the feed shows before "... more" and tests the length limit, the first line, a single call to action, the search terms as plain words, the hashtag limit, links and emoji. Ends with a copy-ready block. Use when someone asks for a caption, wants to fix or check one, says "what do I write under this", pastes a Reel script or post and wants the text for it, or asks how many hashtags to use, even if they don't say "caption". Never posts anything.
argument-hint: "[script, post idea or draft caption; optionally: reel|post|carousel and the search terms]"
---

# Instagram caption

A caption is read in two places: a couple of lines in the feed, cut off by "... more", and in full by the few who tap. Most people only ever see the first part, so the first line does the work and everything after it is for those who already care. Instagram search reads the words of the caption, so the words someone would type to find this post belong in it as ordinary sentences, not only as hashtags.

This skill writes the caption, then a script checks the parts that can be counted. The script never decides whether the caption is good. That judgement stays with you and the person.

## 1. Decide what the caption is for

Read what you were given: a Reel script, a description of a photo or carousel, a draft caption, or a link. Then settle three things before writing a word. Ask only for what you can't work out:

- **Format and job.**
  - **Photo or carousel (`post`, `carousel`): the caption carries the hook.** The image stops the scroll, and the first line has to say why it's worth reading on. Write that line as if nothing else will be read.
  - **Reel (`reel`): the video already did the hooking.** The viewer is watching. On the Reels screen the caption shows about one line over the video. Its job is to add what the video doesn't say: the takeaway in words, the detail or number someone would want to keep, and the one ask. Don't repeat the Reel's opening line word for word.
- **Search terms.** Two or three phrases a person would actually type to find this, such as "meal prep for one" rather than "nutrition". Take them from the person if they gave them; otherwise propose them from the subject and confirm.
- **The one ask.** One thing for the viewer to do: comment a word, save, send to someone, follow, or tap the link in the bio. Pick the one that fits the post. A Reel that teaches something is usually saved. One that someone would recognise a friend in is usually sent. If the Reel script already says an ask out loud, use that same ask in the caption.

If the person has a voice guide, past captions or a list of rules, read them first and follow them over anything here.

## 2. Write it

Write the caption in plain text, the way it will be pasted:

1. **First line:** one specific thing (a number, a name, a place, a result, a mistake) that fits before the cut. No warm-up such as "Here's the thing", and no hashtag or emoji at the start.
2. **Body:** short paragraphs separated by blank lines. Each search term appears once, naturally, in a sentence. Say the thing the post is about plainly. Leave out anything the post doesn't need.
3. **The ask:** one sentence, near the end.
4. **Hashtags,** if any: at the end, specific to the topic, within the limit. They are optional.
5. **No link** in the text unless the person says their account can post clickable caption links. Point to the bio or a comment keyword instead.

`references/writing.md` has the reasoning and worked patterns for each format. Read it when the post is unusual or the person pushes back on a choice.

Save the caption to a scratch file such as `caption.txt`, outside the person's project unless they ask for it there.

## 3. Check it

```bash
python3 <this skill's directory>/scripts/check_caption.py caption.txt \
  --format reel|post|carousel --keywords "first phrase, second phrase" [--handle accountname] \
  [--script reel-script.txt]
```

Pass `--script` when there is a Reel script, so the caption's ask can be compared with the one said in the video.

It prints:

- **Two boxes:** what the feed (photo or carousel) and the Reels screen show before "... more". The one for this post comes first. The cut point is an estimate. Instagram doesn't publish it, and it moves with screen size.
- **One line per check:** `PASS`, `WARN` or `FAIL`.

| Check | Fails when |
|---|---|
| placeholders | any unfilled template slot such as `{{N}}`, `{{the weekly job}}` or `{name}` is left in the text |
| length | over the character limit (default 2,200). It warns if the caption is only over when emoji are counted double |
| first line | empty, only emoji, or opens with a hashtag or @. It warns if the line opens by announcing ("Here's what…"), has no number, name or search term, or doesn't fit before the feed's cut |
| call to action | no ask, or more than one. Only the post's own ask to the viewer counts ("Comment X", "save this post", "follow for more", "DM me", "link in bio"), not a step of a how-to or words inside quotes. A standing footer at the end (a separator line such as `—`, `---` or `___`, then a "Follow @handle..." line and hashtags) is the creator's posting habit, not this post's ask: its follow line is left out of the count, and the hashtags still count toward the limit. It prints each line it counted |
| matches script | never fails. With `--script`, it compares the caption's ask with the last ask said in the script (the `## Script` section of an ig-reel draft, or the whole file) and warns when they differ (the video says "send this to a friend", the caption says "comment SKILL") or use a different comment keyword. A `script asks` warning is added when the draft's on-screen text asks for something other than what is said |
| search terms | a phrase is missing, or appears only as a hashtag. For each phrase it says whether it is before the cut, after it, or missing, and it matches simple word forms ("skill" and "skills", "plan" and "planning") |
| hashtags | over the limit (default 5). It warns on repeated tags |
| links | a URL or domain in the text, unless `--allow-links` |
| emoji | it only warns: more than 4 per 100 words, 3 in a row, or a post that opens with one |

Fix every `FAIL` and re-run. Treat a `WARN` as a question: fix it or say why it stays. The script matches patterns. If it calls something an ask that isn't one, or misses one, trust your reading and say so.

Every limit is a flag (`--max-chars`, `--max-hashtags`, `--feed-chars`, `--feed-lines`, `--reel-chars`, `--reel-lines`, `--emoji-per-100-words`). `references/facts.md` says where each default comes from and how sure it is. If the person knows their account works differently, or Instagram has changed a rule, pass the flag rather than arguing with the default. `--json` gives the same report for other tools.

## 4. Voice pass, if you have it

If an `ig-voice` skill is installed (the checker's last lines say whether it found one next to this skill or in the usual skills folders, and it may be installed elsewhere), run ig-voice on the caption file as its own instructions say, and apply what it finds that the person agrees with. If it isn't installed, skip this step and say so in one line. Don't install or fetch anything.

After any change, run step 3 again so the final text is the checked text.

## 5. Hand it over

Show the person, in this order:

1. The box for this post's format, from the last run.
2. The check lines, with a sentence on any `WARN` you kept.
3. The caption from the copy block, exactly as the script printed it, ready to paste.

Stop there. This skill never posts, schedules or opens Instagram. Posting is the person's step.
