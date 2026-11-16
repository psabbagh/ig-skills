# How the planner works out each number

Everything here is computed by `scripts/plan.py` from the research CSVs and the posting log. Nothing is estimated or looked up.

## Ranking ideas

Instagram has said publicly how it ranks Reels for people who don't follow the creator: sends per reach weigh most, then likes per reach, then watch time. Reach isn't public for other people's Reels, so views stand in for it, the same as in `ig-research`.

- A research Reel is **ranked** when it has 10K+ views, a share count, and likes + comments of at least 2% of its views. Below 10K views a share rate is noise; under 2% reactions the views may have been bought or the Reel flopped.
- Views are Instagram-only plays when the CSV has them (`ig_only_views`): a Reel cross-posted to Facebook shows Facebook plays too, and the shares didn't come from those.
- Ranked Reels are ordered by shares per 1,000 views, then likes per 1,000 views.
- An idea's **score** is the median shares per 1,000 views of its top 5 ranked Reels. The median keeps one outlier from carrying an idea.
- **State**: `thin` with fewer than 3 ranked Reels; `wave passed?` when the newest ranked Reel is more than 90 days old (a news idea whose moment may be over); otherwise `live`. The draft takes live ideas first, then thin, then stale, each by score.
- When an idea was researched more than once, the newest file is used. Research more than 30 days old gets a note: its numbers have moved.
- The CSV may hold TikTok rows (from a merged research run). They are ranked by the same rule on TikTok plays, and their links say TikTok.

## On topic and drift: ig-research's decisions

- **Drift** is settled in the CSV: when ig-research reruns its report with `--drop N`, the Reels found only by the drifting phrasing are not in the CSV, so they are not here either.
- **On topic** is settled in the hooks file next to the CSV, `research-<idea>-<date>-hooks.md`. A Reel in its table was judged on topic. A Reel the file explicitly marks off topic (or drifted, unrelated, a different idea) is left out of the idea everywhere: its score, its angles and the accounts to engage with. The mark can name it by link, by `#N` (its place in the report table, which is the CSV's row order) or by `@creator`, in a clause that says off topic itself or under a sentence that opens with it ("Skipped as off topic: #3 @a; #5 @b"). "Skipped" alone is not such a mark: a Reel noted as not read ("#9 @x not read (top 8 only)") or skipped for ⚠ low reactions stays in, and its creator can still be listed to engage with (an unread Reel's angle says "on topic not checked"; a low-reactions Reel is unranked anyway). A Reel both in the table and on an off-topic line stays in.
- With no hooks file, nothing is dropped and every angle says "on topic not checked".

## Angles: filling the week from one research run

One research run holds many winners that open differently. Each becomes its own slot:

- An idea's angles come from its top 10 ranked on-topic Reels: those the hooks file judged on topic first, then the ones it didn't read (marked unchecked), each group in ranked order.
- One per creator. The angle is the Reel's text hook, else its spoken hook (from the hooks file), else the first sentence of its caption without the comment-keyword call to action. Why it worked goes into the slot's evidence: the Structure and Payoff lines of ig-research's "## Why they worked" breakdown in the hooks file, or a hooks-table column headed "why". Off-topic lines are only read above that section.
- Angles are told apart by their **promise**, not their wording. A hook's promise words are its content words with plurals as singulars, synonyms as one word (buyer, client, customer; startup, company, business; test, validate; spend, dollar, cost, free, $0; four and 4), hook filler left out ("did you know", "someone built", "entire", "exactly", "without", "inside"), and the idea's own words and the niche words left out. Two Reels make the same promise when their promise words share 2+ words making up half of the shorter: "test entire businesses without spending a dollar" and "test your business idea on 100 buyers before you spend a dollar" are one promise (test + free), not two. A later Reel making the promise of an angle already found is folded into it: no slot of its own, credited in that slot's evidence, and its wording kept for the coverage check below. A later Reel needs 2+ promise words to count as an angle of its own.
- Two ideas' angles that make the same promise fill one slot, not two.
- The week takes every idea's first angle (the idea itself, by idea order), then every idea's second angle, and so on, then the follow-up. The output counts the angles and says how many slots the research fills; a slot is left for new research only when every angle is used.

## Coverage

A post covers an idea when its `idea` column is the idea's research slug, or when its topic and the idea's name share 2+ content words making up 60%+ of the shorter one and 40%+ of both together ("budget meal prep" and "my budget meal prep routine"). Plurals count as their singular, filler words ("how", "turn", "your") don't count, and with 5+ ideas, a word in 30%+ of the idea names is the creator's niche ("claude" for someone whose every idea is about Claude) and doesn't count either: otherwise every idea would match every other. Covered in the last 28 days (`--recent-days`) leaves the idea out; covered earlier keeps it with a note that it needs a new angle. Two research ideas whose names match by the same rule share one slot.

Each angle is also checked against the log by its promise: the topic and the hook of every post (`postlog.py add --hook` records a post's opening line) against every wording folded into the angle, by the same-promise rule above. So "test your startup idea on 100 AI buyers" in the log covers the research angle "Claude can test your business idea on 100 fake customers", and the angles folded in with it.

- When the matching post is the creator's own winner that the week follows up, those angles go into the follow-up slot as its research instead of slots of their own, and the slot says it is a deliberate follow-up: the week makes that promise once.
- Any other match in the last 28 days leaves the angle out; the output lists it as a promise already posted recently, with the post.
- An older match keeps the angle, with a note that the promise was made before and needs a new angle.

## The creator's own numbers

- **Shares per 1,000** for their own posts divide by reach when they pasted it (that is Instagram's "sends per reach"), else by views. Each post says which.
- Posts under 7 days old are **still climbing**: they count as covered, but stay out of every average.
- **By format**: median shares per 1,000 per format, compared only between formats with 2+ settled posts.
- **Winners**: settled posts at 1.5x the creator's median, once 3+ posts have shares. The best one becomes a follow-up slot: the third post of the week by date, so new ideas lead (with fewer than 3 posts, it fills the last slot only when research runs out).

## When to post

Timing changes how many people see a post, not how often they share it, so it is judged on views. Each settled post's views are compared with the creator's median views; a weekday or time band's **index** is the median of its posts' views over that median (1.0 = typical).

- Named only with 8+ settled posts with views, and only for buckets with 2+ posts. Best days are those with an index of 1.0 or more; the time is the median posting time within the best band (with an even number of posts, halfway between the middle two, rounded to the minute; in the 21-06 band, times after midnight count as the night before).
- Bands: 06-10, 10-13, 13-17, 17-21, 21-06, the creator's local time as logged.
- With less data, the followers' most active times decide when the creator gives them (`--active FILE`, as read off Instagram's professional dashboard > Total followers > Most active times): the busiest days, each at its busiest hour (or the overall busiest hour). Accepted forms are in `references/default-times.md`.
- Without either, the draft uses a labelled default from Buffer's study of 9.6M Instagram posts: days in the order Wed, Thu, Tue, Sun, Mon, Fri, Sat, each at that day's top hour. Source, caveats and the table: `references/default-times.md`. Every slot using it says so.
- The week is the seven days from today, or from the next day with no post logged, or from `--start`. Days the creator already posted on that week are used last.
- With few posts, a good day may just have had a good idea. The more posts, the more the index means.

## Accounts to engage with

The creators behind the top 10 ranked on-topic Reels of each idea that isn't a passed wave (a Reel the hooks file marked off topic doesn't count). Creators who appear across several ideas come first (they lead the space the creator is posting into), then by how many top Reels they have, then by their best share rate. The creator's own handle (`--me`) is left out.

## The posting log

`~/.config/ig-plan/posted.csv`, or `$XDG_CONFIG_HOME/ig-plan/posted.csv` when that is set (or `IG_PLAN_LOG`, or `--log`). Settings saved with `--remember` go to `config.json` beside it (or `--config FILE`). Columns:

| Column | What |
|---|---|
| `id` | 1, 2, 3… assigned on add |
| `posted_at` | `YYYY-MM-DD HH:MM`, local time (a date alone is accepted) |
| `format` | reel, carousel, photo, story, live |
| `topic` | a few words on what it was about |
| `idea` | the research slug it came from, if any |
| `url` | the post's link |
| `views`, `reach`, `likes`, `comments`, `shares`, `saves` | from the post's insights |
| `avg_watch_s` | average watch time in seconds |
| `logged` | the day it was added |

Other skills may append rows in the same format. Columns the planner doesn't know are kept untouched.
