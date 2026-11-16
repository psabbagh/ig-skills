# Why they worked: the breakdown of a top Reel

One block per Reel, built only from what step 4 read: Instagram's caption track (what was said, with timings), the post's written caption, the length, and the three to five frames that were paused and screenshotted. Nobody watched the Reel end to end, so nothing between those frames was seen. Say so through the basis of each part rather than filling the gaps.

## The basis of each part

| basis | means | give |
|---|---|---|
| `seen` | on screen in one of the frames you screenshotted | `at`: that frame's second |
| `heard` | in the caption track | `at`: the cue's second, when it helps |
| `caption` | in the post's written caption | |
| `inferred` | your judgement from the above | `from`: `seen`, `heard` or `caption` |
| `unread` | not read (no caption track, no end frame) | nothing; the block says "not read" |

A frame at 0.5 s does not show what happens at 1.5 s. If the end card wasn't checked, the ask is `unread` or comes from the caption track (`heard`) or the post caption, never `seen`.

## The parts

- **hook**: the spoken hook, the first sentence of the opening, corrected for misheard names. `heard`; or `seen` when it was read off burned-in captions in a frame; `unread` when the Reel has neither.
- **hook_type**: what move the hook makes, in plain words. Always `inferred`. Pick the closest: a bold claim, a big number, a question, a warning ("stop doing X"), the result first, a pain or problem, a contrarian take, a secret or "nobody tells you", a story opening, a demo straight away, a challenge, a comparison. Two words of your own are fine when none fits.
- **first_frames**: what the first frames show, in one line: who or what is on screen, any text hook, the setting. `seen`, `at` 0.5.
- **structure**: how the middle is built, from the whole caption track. Always `inferred`, usually `from: heard`. `kind` is one of: `list` (numbered or "first, second"), `story` (something happened, then, then), `demo` (showing it being done on screen), `before/after` (a state, then the changed state), `tutorial` (steps to follow), `reaction` (responding to another clip or post), `talking head` (one argument, no steps), `other`. `text` says it in a few words: "five skills, one per beat", "the problem, then the setup in three steps".
- **payoff**: what the viewer gets that the hook promised: the answer, the result, the reveal. Usually `heard` with its second; `inferred` when it is spread through the Reel.
- **ask**: what the Reel asks the viewer to do at the end: comment a keyword, follow, save, send it, the link in bio. `seen` when it is on the end frame, `heard` when it is said, `caption` when only the post caption asks. "None" is a finding: a Reel with no ask is written `"text": "none", "basis": "heard"` after reading the ending.
- **send_to**: who a viewer would send it to and what they'd say. Always `inferred`. The same line as the hooks table's "would send to".

Keep every part under 220 characters. Quote the Reel's own words only for the hook and the ask.

## notes.json

```json
{"reels": [
  {"code": "DaN0yYtPzjY",
   "hook": {"text": "Claude Code skills has over [number] of uses", "basis": "heard", "at": 0},
   "hook_type": {"text": "a big number", "basis": "inferred", "from": "heard"},
   "first_frames": {"text": "Title card 'Claude Code Skills' over the creator talking to camera", "basis": "seen", "at": 0.5},
   "structure": {"kind": "list", "text": "five skills, one per beat", "basis": "inferred", "from": "heard"},
   "payoff": {"text": "the fifth skill, saved for last", "basis": "heard", "at": 35},
   "ask": {"text": "Comment SKILLS and I'll send the list", "basis": "heard", "at": 41},
   "send_to": {"text": "a teammate setting up Claude Code: 'install these'", "basis": "inferred"}}
]}
```

The order of the entries is the order of the blocks: keep the report's order.
