# What ig-script checks, and what it leaves to other skills

ig-script answers one question: can someone who hears this script once, cold, follow it? Everything it checks serves that question. Writing the script, choosing and scoring its hook, and making it sound like the creator are other jobs, done by other skills in the same pack before this check runs.

## The job is split on purpose

| Job | Who does it | Why there |
|---|---|---|
| Find what already performed on the idea | `ig-research` | Evidence comes before writing. |
| Pick hook formulas from the 26, write hooks, score them | `ig-reel` | Hooks are written and filtered before a script exists, while changing them is cheap. Its score is a filter for weak hooks (a warm-up, nothing concrete, too long), not a forecast of which good hook wins. |
| Check the finished script can be followed by ear | `ig-script` (this skill) | The author can't see their own gaps: they fill each one with what they already know. A listener who hasn't seen the notes can. |
| Make it sound like the creator | `ig-voice` | Style, not sense. |

So ig-script never rewrites a hook, never picks a formula and never gives a hook a score. When it looks at the opening, it asks the one question that is about understanding: from the words heard by 0:03 alone, can a stranger say what the video is about? A hook can score well in ig-reel and still fail this, if it leans on context the viewer doesn't have yet; the fix is then a word or two from the file, and the hook's move stays the writer's choice.

## What it checks, and why

| Check | Why it is about understanding |
|---|---|
| Each line timed at a speaking pace, timecodes stacked (`scripts/timeline.py`) | A viewer can't rewind, so "answered too late" and "where would you stop" are about seconds, not line numbers. |
| The words heard by 0:03 | Instagram measures who leaves in the first three seconds. A viewer who can't yet say what the video is about is the one who leaves. The listener answers from those words alone. |
| The words heard by 0:07 | One step on: by then, does the viewer know who it's for and why it matters to them? This is the missing-premise gap, timed. |
| The midpoint | A question the opening raises that is answered only after the midpoint is answered late. |
| Lines over 8 seconds (about 20 words) | A line that long usually carries two ideas and loses the first. Flagged lines are checked, not cut on sight. |
| Three or more lines with no number or name | Where a picture is needed, the viewer may have nothing to picture. The tool sees only numbers and names, so it over-flags lines with everyday nouns ("gym", "phone"); the judge decides. |
| One idea per video | Shows up as a retelling that names two separate points. Reported, not fixed: splitting is the creator's call. |
| Lines that sound written | A parenthesis, "the former", a slash or a long list is hard to follow on one hearing. |
| On-screen text against the spoken words | A viewer reads before hearing. A card that names a thing differently from the voice is name drift. Card size, safe zones and captions are production, not sense. |
| Never inventing a fact | A fix uses only facts already in the file or the conversation; anything else is asked for. |

## What it leaves alone

- **Hooks**: their formula, wording and score belong to `ig-reel`.
- **Length**: the writer's decision. The check reports length against a target only when one is given.
- **Endings and calls to action**: a writing choice. The check only asks that the ending match what the body set up.
- **Replay tricks** such as echoing the hook in the last line: they buy replays, not understanding.
- **Visual and edit decisions** (frame changes, motion in the first frame): the script check can't see them.
- **Style and AI tells**: `ig-voice`. A line that works stays, however it sounds; a written-sounding line is flagged only when it hurts understanding.

## How the timer counts

`timeline.py` and `ig-reel`'s `reel.py check` count words by one rule, so they give the same length and the same words by 0:03 for the same lines: a `{{placeholder}}` is one word, a figure counts as it is said ("$18,000" is three: eighteen thousand dollars), and a word is heard by 0:03 once it has been said in full. The rule is written out above `spoken_words` in both scripts.
