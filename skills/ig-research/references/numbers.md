# What the numbers mean

- **Views.** The number shown on the Reel, which for Reels cross-posted to Facebook includes Facebook plays. The `ig_only_views` column is Instagram plays alone, and the two can differ by more than 2× (one checked Reel: 101,147 shown = 42,903 Instagram + 58,244 Facebook).
- **Likes** are blank when the creator hid them: the API sends a placeholder then, so the skill drops it. Engagement is blank for those rows too.
- **Saves** aren't given for other people's Reels, so `saves_per_1k_views` stays blank for Instagram rows, and the printed table leaves out its Saves/1K column when every row is from Instagram (it says so above the table).
- **Shares per 1K, likes per 1K** (`shares_per_1k_views`, `likes_per_1k_views`) divide by the views in `rate_basis`, Instagram-only views where known. `send_rank` is the place in the share ranking, blank for Reels outside it.
- **Engagement.** In the table, "Eng." is (likes + comments) over the same views as the rates (`reactions_pct` in the CSV). The CSV's `engagement_pct` is over the shown views.
- **Low reactions** (`low_reactions` = yes): 10K+ views and reactions under 2%. See SKILL.md step 3.
- **vs recent Reels** (`references/creator-check.md`) is the Reel's Instagram-only views divided by the median Instagram-only views of the creator's 15 most recent Reels.
- **Posted** is the post date with its age on the day the report ran: "3 d", "2 wk", "3 mo", "2 yr". Under 7 days it adds "still climbing", because the views are still growing. The CSV's `age_days` is the same age in days. **By month** counts the kept Reels per month with their total views, from the oldest month to the current one; months more than a year back fold into "earlier".
- **Found by** lists the phrasings that returned the Reel. A Reel found by several phrasings sits at the centre of the idea.
- **Search order** (`best_rank`) is Instagram's order, personalized to the signed-in account: a snapshot of today.
- The CSV also has TikTok columns (`followers`, `views_per_follower`, `saves`): the same report merges a TikTok search when one is given with `--tiktok`. They stay blank here.
