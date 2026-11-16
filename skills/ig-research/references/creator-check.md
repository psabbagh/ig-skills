# Versus the creator's recent Reels

Raw views favour big accounts. This shows which candidates beat their own creator's usual: a Reel's Instagram-only views divided by the median Instagram-only views of that creator's 15 most recent Reels. Run it only for the candidates the person is considering (at most 10), after showing them as SKILL.md step 5 says.

For each creator among those candidates, open `https://www.instagram.com/<handle>/reels/` in the signed-in tab. Opening the grid page reloads the tab, so the helper is gone: read `<skill>/scripts/creator-median.js` and send its **entire text** as one JavaScript call (once per creator, since each creator is a new page), with this line added at the end:

    __cmedian.start({videos: ["<code>", ...], reels: 15})

`<code>` is the Reel code at the end of its URL. Pass all of that creator's candidates in one start. Then call `await __cmedian.wait(25000)` until `phase` is `done` (or `error`: then stop and say so; it stops by itself if Instagram pushes back). It returns the creator's `median`, `n` and a score for each Reel.

Cost: one lookup per candidate plus one grid page load. A creator who cross-posts to Facebook (the script detects this when a Reel's Instagram-only views differ from the shown views by more than 5%) also costs one lookup per Reel in the median, about 15. Instagram-only views are used on both sides: the grid's shown counts include Facebook plays, which inflated cross-posters' medians about 1.5× in testing.

Then run the report again with the same arguments plus `--vs-recent <code>=<median>/<n>` for each checked Reel. It adds a "vs recent" column to the table and `vs_recent_reels`, `recent_reels_median` and `recent_reels_n` to the CSV.

Label it **"vs this creator's recent Reels"**, never "outlier score": outlier scores sold by research tools usually divide by the creator's Reels from the 90 days before each video, which needs months of history that Instagram's web app no longer lists cheaply. Compared on 12 videos, the two ranked alike (rank correlation 0.88), but this one ran about 1.25× higher. Use it to compare candidates with each other.

Pinned Reels, the candidates themselves and Reels under 3 days old are left out of the median.
