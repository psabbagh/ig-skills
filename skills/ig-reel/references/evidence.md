# Reading the evidence

Read this when the research is thin, mixed, or the patterns are hard to tell apart.

## What the research gives you

`ig-research` leaves two files per run, side by side:

- `research-<idea>-<date>.csv`: every Reel found, with views, likes, comments, shares, the date and age, the phrasing that found it, and the caption. Rows are ranked by shares per 1,000 views among Reels with 10K+ views; `low_reactions` marks Reels whose likes and comments are under 2% of their views (bought views or a flop).
- `research-<idea>-<date>-hooks.md`: the top on-topic Reels after its drift check, each with its **spoken hook** (the first sentence said), its **text hook** (words placed on screen at the start, or "None" and what the opening shows), and **would send to** (who a viewer would send it to and what they'd say; a judgement, not a measurement). It also says which Reels it left out as off topic.

`reel.py evidence` puts the two together. When a hooks file exists, its Reels lead, because they passed the research's own on-topic check. Older research without the rate or the flag gets both worked out the same way.

## Which winners count

- **On topic.** A Reel about a neighbouring idea teaches a neighbouring hook. Leave it out and say so, however many views it has.
- **Share rate over views.** A 2M-view Reel on a big account can be shared less per view than a 60K one from a small account. The small one's opening carried it; the big one's audience did.
- **Recent over old.** An opening that worked a year ago may be worn out. If the strongest pattern is old and a recent winner opens differently, say both and lean recent.
- **Not low reactions.** Their numbers say little about the opening.
- **A handful is enough.** Five to eight on-topic winners with hooks read. Fewer than three: say the evidence is thin.

## Matching winners to the 26 formulas

`hooks.py pick` suggests which of the 26 formulas each winner's hook resembles, from rough word patterns (`cues` in `hooks.json`). It gets the obvious ones right ("Did Claude just kill X?" is the swap; "$250 free until October 7" is free with a date) and misses or over-matches the rest, so read every winner's hook yourself:

- **Confirm or correct each match.** A hook can use two moves (a launch plus a personal use); count it for both.
- **A winner that fits none** is not discarded. Name its move as below and treat it as a formula for this Reel.
- **15 of the 26 came from research** (moves seen in top Reels collected with ig-research in November 2026) and **11 from general craft**. A craft formula with no winner behind it on this idea is unproven here, like any formula the research didn't back.

## Naming a move

A move is what the opening does, described so someone who never saw the Reel could make the same move about a different topic. Derive it from the words and the screen.

Describe:

- **What the viewer hears first**: a pain, a result, a number, a claim against something familiar, a question, a moment in a story, an offer.
- **What it leaves open**: why the viewer keeps watching (how, whether it's true, what happened next).
- **What's on screen**: a headline that repeats the claim, one that adds a number, a face, the thing itself.

Good: "Opens on a result with a number and a time ('in 5 minutes'), and the screen repeats the result in capitals."
Too vague: "Curiosity hook." It names a feeling, not a move, and fits every Reel.
Too narrow: "Mentions GitHub." That's a topic word, not the move.

**One move or two?** Two openings share a move if you could swap their topics and they'd still read as the same move. "Did Claude just kill X?" and "Claude just replaced X" are one move (the swap: the new thing against the familiar one) in two wordings. "Free $250 before the 7th" is a different one (an offer with a deadline).

## Turning formulas into hooks

- Each of the three hooks uses a different formula. If the winners back only one, the other two come from the 26 by their "use when" and are labelled unproven, not passed off as evidence.
- The person's true thing goes into the pattern; the pattern doesn't replace it. A winner's "free $250" pattern doesn't fit an idea with no offer, so don't fake one.
- Copy the move, never the words. A hook that reuses a winner's sentence is their hook.
- **Picking one:** after the score has filtered out weak hooks, the formula with the highest shares per view among recent, on-topic winners, that fits the true thing without stretching it. Say the numbers ("the two pain-first openings average 22 shares per 1K; the versus openings 14"). If the evidence is thin or split, say it's a judgement and offer the choice.

## When there's no evidence

Pick three clearly different formulas from the 26 that fit the true thing (for example in-the-middle, what-it-did-for-me, my-mistake) and label all three **unproven**. The score still filters out weak ones; it can't stand in for evidence. Offer `ig-research` once; don't push.
