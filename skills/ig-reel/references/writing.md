# Writing the script

Read this when the story is hard to shape, the person pushes back on a choice, or the on-screen text gets crowded.

## The order that usually works

1. **The hook**, with the true thing in it: the viewer knows what this is about by the end of the first line.
2. **The moment**: what happened, told as it happened, with one detail someone could picture (the screen, the place, the time of day).
3. **The cost or the return**: what it saved, cost, earned or avoided. Their number, or a placeholder.
4. **What the viewer can take from it**: how they'd do it, or what to look for. If it's a how-to, the steps they'd actually follow, each with its reason.
5. **One ask**.

It isn't a template. A story told well in another order stays in that order. What matters is that the hook's promise is kept early, before the viewer is left wondering too long, and that the ending doesn't claim more than the middle showed.

## Questions to get the true thing

Ask only what's missing, all at once:

- What actually happened, the one time it worked (or didn't)?
- Who was it: you, a client (what kind), a friend?
- What did it save, cost or get you? Roughly how much, or how long?
- What would someone watching need to do it themselves?

If they don't know a number, the line can say so honestly ("I didn't time it, but it was the whole afternoon") or keep `{{a placeholder}}`. Never round up into a number they didn't give.

## Spoken lines

- One idea per line. A line with "and" joining two ideas is usually two lines.
- Say each line in your head at talking speed. A line over about 8 seconds (20 words) usually loses its first half.
- Call one thing by one name the whole way through.
- "This", "that" and "it" need something just before them to point at.
- No warm-up ("Hey guys", "So today", "In this video"). The first word is already the video.
- Everyday words for the audience given. A term they wouldn't use gets a plain line explaining it, or goes.

## On-screen text

Viewers often watch without sound, and read before they hear. The on-screen list is a second script.

- **The first cue is the on-screen hook**, at 0:00. It can say the same thing as the spoken hook in fewer words, or carry what the voice doesn't (the number, the name of the thing).
- **Keep each cue short**, and give it time: about a third of a second per word read, more if it appears while a lot is being said. `reel.py check` warns when a cue has more words than its time allows.
- **Use it for what should stick**: a number, a step's name, the one word to comment. Not every line.
- **Not before its line**: a card that backs up a spoken line appears with that line, not before it, or it gives the line away. `reel.py check` flags a card that starts more than 1.5 s before the line it shares its words with.
- **One name per thing**: the screen and the voice call it the same.
- **Timings are estimates** from the spoken word count. The editor moves them to the real take.

## Endings

- One ask, matched to the Reel: a story someone would recognise a friend in is sent; a how-to is saved; a comment keyword is for when there's a real thing to send back.
- The last line can close the loop the hook opened. It shouldn't introduce a new claim.

## Length

What the story needs, cut until each line earns its place. If the person gave a target, aim within a few seconds of it. `reel.py check --target` prints how far over or under the estimate is, and warns only when it is more than 5 seconds or 15% off (whichever is larger); inside that margin it says so and stays quiet. Don't pad to a length or squeeze out the reason a step matters.

## Placeholders

`{{like this}}`, in plain words for what goes there: `{{how long it took}}`, `{{the client's industry}}`, `{{your number}}`. `reel.py check` lists every one and won't call the draft ready until they're gone.
