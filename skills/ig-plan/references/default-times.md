# The default days and times, and where they come from

The planner names days and times from the creator's own posts once 8+ settled posts with views
exist (`references/method.md`, "When to post"). Before that, it uses the creator's followers'
most active times when they give them (`--active`), and only without those, this default.
Every slot that uses it says so.

## Source

Buffer, "Best Time to Post on Instagram in 2026: Data from 9.6 Million Posts", published
2026-09-23: https://buffer.com/library/best-time-to-post-on-instagram

- 9.6 million Instagram posts from January 2024 to December 2025, part of a 52M+ post study
  of 200,000+ accounts.
- Measured on median engagement rate: likes + comments + shares + saves over followers.
- All post types together; the article gives no separate analysis for Reels.
- Times are each account's local time.

## What the planner takes from it

| Day | Tier in the study | Time used (the day's top hour) |
|---|---|---|
| Wednesday | highest (best day) | 12:00 |
| Thursday | highest | 09:00 |
| Tuesday | high | 19:00 |
| Sunday | moderate | 21:00 |
| Monday | moderate | 19:00 |
| Friday | low | 22:00 |
| Saturday | low | 21:00 |

Days are picked in that order (Wed, Thu, Tue, then Sun and Mon, which the study ties, then Fri
and Sat), skipping any day the creator already posted on that week. Sunday is put before Monday
to spread a 4-post week; the study doesn't order the two.

## Why it is only a default

- It is an average over many accounts, niches and time zones, not the creator's audience.
- It measures engagement per follower, mostly from followers; a Reel's reach to
  non-followers depends more on how often it is sent than on the hour.
- Other studies name other hours (some put the best Reel hours early morning or late night).

## Getting the creator's own answer

1. **Their followers' active times.** In the Instagram app: professional dashboard > Total
   followers > Most active times, with an Hours and a Days view. Write what it shows into a
   text file and pass `--active FILE` (`--remember` keeps it). Accepted:
   - top days and hours as a list, busiest first: `Tue Thu Sun` and `6p 9p`, or `Wed 12pm 6pm`
   - counts per day (`Mon 1,234`), per hour (`6p 812`), or a row of hour labels with a row of
     counts under it, as copied from a table
2. **Their own posts.** Log each post with its time (`postlog.py add --at "YYYY-MM-DD HH:MM"`)
   and paste its insights a week later. From 8 settled posts with views, the planner names
   their best days and time band from their own views, and that takes precedence.
