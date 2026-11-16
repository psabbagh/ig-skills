"""Offline tests for scripts/postlog.py and scripts/plan.py, on made-up data only.

Run: python3 -m unittest discover ig-plan/tests
"""
import contextlib
import csv
import datetime
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import plan  # noqa: E402
import postlog  # noqa: E402

TODAY = "2026-03-18"  # a Wednesday
RESEARCH_COLS = ["platform", "views", "likes", "comments", "shares", "saves", "engagement_pct",
                 "followers", "views_per_follower", "vs_recent_reels", "recent_reels_median",
                 "recent_reels_n", "account", "posted", "age_days", "duration_s", "url", "found_by",
                 "best_rank", "ig_only_views", "transcript_file", "caption"]


def reel(account, views, likes, comments, shares, posted="2026-03-01", ig_only="", code=None):
    return {"platform": "Instagram", "views": views, "likes": likes, "comments": comments,
            "shares": shares, "account": account, "posted": posted, "ig_only_views": ig_only,
            "url": f"https://www.instagram.com/reel/{code or account + str(views)}/", "caption": "made up"}


def write_research(folder, slug, date, rows):
    p = Path(folder) / f"research-{slug}-{date}.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RESEARCH_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


def run_main(mod, argv, stdin=None):
    out = io.StringIO()
    old = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out):
            rc = mod.main(argv)
    finally:
        sys.stdin = old
    return rc, out.getvalue()


class TestParsing(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(postlog.parse_number("12,345"), 12345)
        self.assertEqual(postlog.parse_number("12.345"), 12345)
        self.assertEqual(postlog.parse_number("1.2", "K"), 1200)
        self.assertEqual(postlog.parse_number("3,4", "M"), 3400000)
        self.assertEqual(postlog.parse_number("7"), 7)

    def test_durations(self):
        self.assertEqual(postlog.parse_duration("7 sec"), 7.0)
        self.assertEqual(postlog.parse_duration("1m 5s"), 65.0)
        self.assertEqual(postlog.parse_duration("0:07"), 7.0)
        self.assertEqual(postlog.parse_duration("12.5 s"), 12.5)
        self.assertIsNone(postlog.parse_duration("soon"))

    def test_insights_same_line_and_next_line(self):
        text = """Reel insights
Overview
Views
12,345
Accounts reached 9.8K
Interactions 700
Likes 512
Comments: 31
Shares 88
Saves 40
Average watch time 7 sec
Watch time 23h 4m
"""
        got = postlog.parse_insights(text)
        self.assertEqual(got, {"views": 12345, "reach": 9800, "likes": 512, "comments": 31,
                               "shares": 88, "saves": 40, "avg_watch_s": 7.0})

    def test_reach_not_confused_with_longer_words(self):
        self.assertEqual(postlog.parse_insights("Reached people 40\nReach 1,000"), {"reach": 1000})

    def test_when(self):
        self.assertEqual(postlog.parse_when("2026-03-02T18:30"), "2026-03-02 18:30")
        self.assertEqual(postlog.parse_when("2026-03-02"), "2026-03-02")
        with self.assertRaises(ValueError):
            postlog.parse_when("monday")


class TestPostLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "sub" / "posted.csv"

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, *args):
        return run_main(postlog, ["--log", str(self.log), "add", *args])

    def test_add_list_and_ids(self):
        self.add("--at", "2026-03-02 18:30", "--format", "reel", "--topic", "Budget meal prep")
        self.add("--at", "2026-03-04 12:00", "--format", "carousel", "--topic", "Pantry list", "--views", "900")
        rows, cols = postlog.load(self.log)
        self.assertEqual([r["id"] for r in rows], ["1", "2"])
        self.assertEqual(rows[1]["views"], "900")
        self.assertEqual(cols[:len(postlog.LOG_COLS)], postlog.LOG_COLS)
        rc, out = run_main(postlog, ["--log", str(self.log), "list"])
        self.assertIn("Pantry list", out)
        self.assertIn("(no numbers yet)", out)

    def test_duplicate_url_refused(self):
        self.add("--at", "2026-03-02", "--format", "reel", "--topic", "a", "--url", "https://x/1")
        with self.assertRaises(SystemExit):
            self.add("--at", "2026-03-03", "--format", "reel", "--topic", "b", "--url", "https://x/1")

    def test_insights_go_to_latest_without_views_by_default(self):
        self.add("--at", "2026-03-02 18:30", "--format", "reel", "--topic", "first", "--views", "100")
        self.add("--at", "2026-03-05 18:30", "--format", "reel", "--topic", "second")
        rc, out = run_main(postlog, ["--log", str(self.log), "insights"], stdin="Views 2,000\nShares 30\n")
        self.assertEqual(rc, 0)
        rows, _ = postlog.load(self.log)
        self.assertEqual((rows[0]["views"], rows[1]["views"], rows[1]["shares"]), ("100", "2000", "30"))
        self.assertIn("not in the paste", out)

    def test_insights_by_topic_must_be_unique(self):
        self.add("--at", "2026-03-02", "--format", "reel", "--topic", "meal prep one")
        self.add("--at", "2026-03-03", "--format", "reel", "--topic", "meal prep two")
        with self.assertRaises(SystemExit):
            run_main(postlog, ["--log", str(self.log), "insights", "--topic", "meal prep"], stdin="Views 5")

    def test_insights_keep_numbers_the_paste_omits(self):
        self.add("--at", "2026-03-02", "--format", "reel", "--topic", "x", "--saves", "12")
        run_main(postlog, ["--log", str(self.log), "insights", "--id", "1"], stdin="Views 400")
        rows, _ = postlog.load(self.log)
        self.assertEqual((rows[0]["views"], rows[0]["saves"]), ("400", "12"))

    def test_unknown_columns_survive(self):
        self.log.parent.mkdir(parents=True)
        self.log.write_text("id,posted_at,format,topic,mood\n1,2026-03-01,reel,old,happy\n")
        self.add("--at", "2026-03-02", "--format", "reel", "--topic", "new")
        rows, cols = postlog.load(self.log)
        self.assertIn("mood", cols)
        self.assertEqual(rows[0]["mood"], "happy")

    def test_env_var_picks_log(self):
        old = os.environ.get("IG_PLAN_LOG")
        os.environ["IG_PLAN_LOG"] = str(self.log)
        try:
            self.assertEqual(postlog.default_log(), self.log)
        finally:
            if old is None:
                del os.environ["IG_PLAN_LOG"]
            else:
                os.environ["IG_PLAN_LOG"] = old


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.research = self.dir / "research"
        self.research.mkdir()
        self.log = self.dir / "posted.csv"
        self.cfg = self.dir / "config.json"

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, *extra, json_out=True):
        argv = ["--research", str(self.research), "--log", str(self.log), "--config", str(self.cfg),
                "--today", TODAY, *extra]
        if json_out:
            argv.append("--json")
        rc, out = run_main(plan, argv)
        return rc, (json.loads(out) if json_out and rc == 0 else out)

    def strong_idea(self, slug="budget meal prep", date="2026-03-15", base=40, accounts=None):
        accounts = accounts or ["cookA", "cookB", "cookC", "cookD", "cookE", "cookF"]
        rows = [reel(a, 100_000, 5_000, 200, base * 100 + k * 100) for k, a in enumerate(accounts)]
        return write_research(self.research, slug.replace(" ", "-"), date, rows)

    def add_post(self, at, topic, fmt="reel", **nums):
        args = ["--log", str(self.log), "add", "--at", at, "--format", fmt, "--topic", topic]
        for k, v in nums.items():
            args += [f"--{k}", str(v)]
        run_main(postlog, args)

    def test_needs_data(self):
        rc, out = self.plan(json_out=False)
        self.assertEqual(rc, 3)
        self.assertIn("run the ig-research skill", out)
        self.assertIn("postlog.py insights", out)

    def test_ranking_rule_matches_ig_research(self):
        rows = [
            reel("big", 2_000_000, 80_000, 1_000, 20_000),         # 10 shares/1K
            reel("small", 60_000, 3_000, 100, 1_800),              # 30 shares/1K: ranks first
            reel("tiny", 900, 100, 5, 90),                         # under 10K views: not ranked
            reel("bought", 500_000, 2_000, 100, 40_000),           # reactions 0.42%: not ranked
            reel("fb", 101_147, 4_000, 50, 1_287, ig_only=42_903),  # 30.0/1K on Instagram-only views
            reel("noshare", 50_000, 2_000, 10, ""),                # no share count: not ranked
        ]
        write_research(self.research, "x-idea", "2026-03-10", rows)
        rc, res = self.plan()
        idea = res["ideas"][0]
        self.assertEqual(idea["ranked"], 3)
        self.assertEqual(idea["low_reactions"], 1)
        self.assertEqual([r["account"] for r in idea["top"]], ["fb", "small", "big"])
        self.assertEqual(idea["top"][0]["shares_per_1k"], 30.0)
        self.assertEqual(idea["score"], 30.0)  # median of 30.0, 30, 10
        self.assertEqual(idea["state"], "live")

    def test_newest_research_file_wins_and_states(self):
        write_research(self.research, "same-idea", "2026-01-01", [reel("old", 50_000, 2_000, 10, 100)])
        self.strong_idea("same idea", "2026-03-10")
        write_research(self.research, "thin-idea", "2026-03-10", [reel("one", 50_000, 2_000, 10, 2_000)])
        old = [reel(a, 50_000, 2_000, 10, 1_000, posted="2025-10-01") for a in "pqr"]
        write_research(self.research, "old-wave", "2026-03-10", old)
        rc, res = self.plan()
        by = {i["idea"]: i for i in res["ideas"]}
        self.assertTrue(by["same-idea"]["file"].endswith("2026-03-10.csv"))
        self.assertEqual(by["thin-idea"]["state"], "thin")
        self.assertEqual(by["old-wave"]["state"], "wave passed?")
        # live ideas come before thin and stale ones however high those score
        self.assertEqual(res["candidates"][0]["idea"], "same-idea")

    def test_recent_coverage_excludes_and_older_coverage_flags(self):
        self.strong_idea("budget meal prep")
        self.strong_idea("cold brew at home", base=30)
        self.strong_idea("sourdough starter basics", base=20)
        self.add_post("2026-03-10 18:00", "my budget meal prep routine")                 # 8 days ago: recent
        self.add_post("2026-01-05 18:00", "sourdough starter for basics", views=1000)    # long ago
        rc, res = self.plan()
        titles = [c["title"] for c in res["candidates"]]
        self.assertNotIn("budget meal prep", titles)
        self.assertEqual(titles[0], "cold brew at home")
        sd = next(c for c in res["candidates"] if c["title"] == "sourdough starter basics")
        self.assertIn("needs a new angle", sd["evidence"])

    def test_idea_slug_in_log_counts_as_coverage(self):
        self.strong_idea("cold brew at home")
        run_main(postlog, ["--log", str(self.log), "add", "--at", "2026-03-12", "--format", "reel",
                           "--topic", "totally different words", "--idea", "cold-brew-at-home"])
        rc, res = self.plan()
        self.assertTrue(res["ideas"][0]["covered_recently"])

    def test_twin_ideas_share_one_slot(self):
        self.strong_idea("cold brew coffee at home", base=40)
        self.strong_idea("make cold brew coffee", base=30)
        self.strong_idea("sourdough starter basics", base=20)
        rc, res = self.plan("--posts", "3")
        titles = [c["title"] for c in res["candidates"]]
        self.assertEqual(titles, ["cold brew coffee at home", "sourdough starter basics"])
        self.assertIn("also researched as", res["candidates"][0]["evidence"])
        self.assertIsNone(res["week"][2]["idea"])
        self.assertIn("run ig-research", res["week"][2]["evidence"])

    def test_same_topic(self):
        self.assertTrue(plan.same_topic("Budget meal prep", "my budget meal prep routine"))
        self.assertFalse(plan.same_topic("meal prep", "desk setup tour"))
        self.assertFalse(plan.same_topic("coffee", "coffee"))  # one word is not enough to call it covered
        self.assertFalse(plan.same_topic("find holes in your business",
                                         "sales expert find clients for your business with"))
        self.assertTrue(plan.same_topic("claude can now watch youtube videos",
                                        "a claude skill that watches youtube videos"))

    def test_too_little_data_uses_labelled_default(self):
        self.strong_idea()
        for d in range(2, 6):
            self.add_post(f"2026-02-0{d} 09:00", f"post {d}", views=1000, shares=10)
        rc, res = self.plan("--posts", "3")
        self.assertFalse(res["timing"]["enough"])
        # The published default (Buffer): Wed, Thu, Tue, each at that day's top hour; by date
        # from today (Wed 18): Wed 18, Thu 19, Tue 24.
        self.assertEqual([s["day"] for s in res["week"]], ["Wed", "Thu", "Tue"])
        self.assertEqual([s["time"] for s in res["week"]], ["12:00", "09:00", "19:00"])
        self.assertTrue(res["week"][0]["day_source"].startswith("default, not your data"))
        self.assertIn("references/default-times.md", res["week"][0]["time_source"])
        self.assertEqual(res["week"][0]["date"], "2026-03-18")
        rc, text = self.plan("--posts", "3", json_out=False)
        self.assertIn("Your own posts can't say yet", text)
        self.assertIn("Using a default, not your data", text)
        self.assertIn("Most active times", text)
        self.assertIn("--active FILE", text)
        ref = (SCRIPTS.parent / "references" / "default-times.md").read_text()
        self.assertIn("buffer.com", ref)

    def test_best_days_and_time_from_own_numbers(self):
        self.strong_idea()
        # Tuesdays and Thursdays at about 19:00 do 3x the views of Mondays at 08:00.
        days = {"2026-02-03": 3000, "2026-02-05": 3200, "2026-02-10": 2900, "2026-02-12": 3100,
                "2026-02-02": 1000, "2026-02-09": 900, "2026-02-16": 1100, "2026-02-23": 1000}
        for d, v in days.items():
            t = "08:00" if v < 2000 else ("19:00" if d < "2026-02-10" else "19:30")
            self.add_post(f"{d} {t}", f"topic {d}", views=v, shares=v // 100)
        self.add_post("2026-03-16 19:00", "fresh one", views=50, shares=1)  # 2 days old: still climbing
        rc, res = self.plan("--posts", "2")
        tim = res["timing"]
        self.assertTrue(tim["enough"])
        self.assertEqual(tim["posts"], 8)
        self.assertEqual(sorted(tim["best_days"]), [1, 3])
        self.assertEqual(tim["best_band"], "17-21")
        self.assertEqual(tim["best_time"], "19:15")  # median of 19:00 x2 and 19:30 x2
        self.assertEqual([s["day"] for s in res["week"]], ["Thu", "Tue"])  # by date from Wed 18
        self.assertTrue(res["week"][0]["day_source"].startswith("your numbers"))
        self.assertEqual(len(res["own"]["climbing"]), 1)

    def test_fill_avoids_weak_days_and_best_idea_gets_best_day(self):
        self.strong_idea("aa idea one", base=40)
        self.strong_idea("bb idea two", base=30)
        self.strong_idea("cc idea three", base=20)
        # Thursdays strong, Tuesdays weak; the default spacing for 3 posts is Mon, Wed, Fri.
        for d, v in {"2026-02-05": 3000, "2026-02-12": 3200, "2026-02-19": 2900, "2026-02-26": 3100,
                     "2026-02-03": 900, "2026-02-10": 1000, "2026-02-17": 1100, "2026-02-24": 950}.items():
            self.add_post(f"{d} 18:00", f"topic {d}", views=v, shares=10)
        rc, res = self.plan("--posts", "3")
        days = [s["day"] for s in res["week"]]
        self.assertNotIn("Tue", days)
        self.assertIn("Thu", days)
        self.assertIn("avoiding Tue", res["week"][0]["day_source"])
        thu = next(s for s in res["week"] if s["day"] == "Thu")
        self.assertEqual(thu["idea"], "aa idea one")
        self.assertEqual([s["slot"] for s in res["week"]], [1, 2, 3])

    def test_niche_words_do_not_chain_matches(self):
        # Every idea mentions the niche word "claude"; with it, generic overlaps used to make the
        # YouTube post "cover" the marketing idea, which then knocked out the SEO idea as a twin.
        for k, slug in enumerate(["turn claude code into an seo expert", "turn claude code into a marketing manager with skills",
                                  "claude can now watch youtube videos", "claude as a sales expert",
                                  "five secret codes for claude", "claude remote control phone"]):
            self.strong_idea(slug, base=40 - k)
        self.add_post("2026-03-10 18:00", "turn youtube videos into claude skills")
        rc, res = self.plan()
        by = {i["idea"]: i for i in res["ideas"]}
        self.assertTrue(by["claude-can-now-watch-youtube-videos"]["covered_recently"])
        self.assertFalse(by["turn-claude-code-into-a-marketing-manager-with-skills"]["covered_recently"])
        titles = [c["title"] for c in res["candidates"]]
        self.assertIn("turn claude code into an seo expert", titles)
        self.assertIn("turn claude code into a marketing manager with skills", titles)

    def test_stem_and_common_words(self):
        self.assertEqual(plan.stem("videos"), "video")
        self.assertEqual(plan.stem("watches"), "watch")
        self.assertEqual(plan.stem("class"), "class")
        titles = ["claude a b", "claude seo", "claude video", "sourdough bread", "cold brew"]
        self.assertEqual(plan.common_words(titles), {"claude"})
        self.assertEqual(plan.common_words(titles[:4]), set())  # too few ideas to say

    def test_own_winner_becomes_follow_up_and_formats_compare(self):
        self.strong_idea("aa idea one", base=40)
        self.strong_idea("bb idea two", base=30)
        self.strong_idea("cc idea three", base=20)
        self.add_post("2026-02-02 18:00", "carousel one", fmt="carousel", reach=1000, views=1500, shares=5)
        self.add_post("2026-02-04 18:00", "carousel two", fmt="carousel", reach=1000, views=1500, shares=6)
        self.add_post("2026-02-06 18:00", "pantry hack", reach=1000, views=1200, shares=40)
        self.add_post("2026-02-09 18:00", "reel two", reach=1000, views=1300, shares=10)
        rc, res = self.plan("--posts", "4")
        own = res["own"]
        self.assertEqual(own["median_shares_per_1k"], 8.0)  # rates over reach: 5, 6, 40, 10
        self.assertEqual(own["by_format"][0]["format"], "reel")
        self.assertEqual([w["topic"] for w in own["winners"]], ["pantry hack"])
        kinds = [s["idea"] for s in res["week"]]
        self.assertEqual(kinds[2], "follow-up: pantry hack")
        self.assertIn("5.0x your median", res["week"][2]["evidence"])

    def test_creators_recur_across_ideas_and_skip_me(self):
        self.strong_idea("aa idea", accounts=["shared", "me_myself", "a1", "a2", "a3"])
        self.strong_idea("bb idea", accounts=["shared", "b1", "b2", "b3", "b4"])
        rc, res = self.plan("--me", "@Me_Myself")
        names = [c["account"] for c in res["creators"]]
        self.assertEqual(names[0], "shared")
        self.assertEqual(res["creators"][0]["ideas"], ["aa-idea", "bb-idea"])
        self.assertNotIn("me_myself", names)
        self.assertEqual(res["creators"][0]["profile"], "https://www.instagram.com/shared/")

    def test_log_only_still_plans_with_note(self):
        self.add_post("2026-02-02 18:00", "something", views=1000, shares=10)
        rc, text = self.plan(json_out=False)
        self.assertEqual(rc, 0)
        self.assertIn("No research CSV found", text)

    def test_remember_saves_and_reuses_folders(self):
        self.strong_idea()
        run_main(plan, ["--research", str(self.research), "--me", "@someone", "--remember",
                        "--log", str(self.log), "--config", str(self.cfg), "--today", TODAY])
        cfg = json.loads(self.cfg.read_text())
        self.assertEqual(cfg["me"], "someone")
        rc, out = run_main(plan, ["--log", str(self.log), "--config", str(self.cfg), "--today", TODAY, "--json"])
        self.assertEqual(len(json.loads(out)["ideas"]), 1)

    def test_posts_range_checked(self):
        self.strong_idea()
        with self.assertRaises(SystemExit):
            self.plan("--posts", "9")

    def test_cli_runs_as_a_script(self):
        self.strong_idea()
        p = subprocess.run([sys.executable, "-B", str(SCRIPTS / "plan.py"), "--research", str(self.research),
                            "--log", str(self.log), "--config", str(self.cfg), "--today", TODAY, "--posts", "1"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("## Draft week from 2026-03-18", p.stdout)


HOOKS = """# Hooks: budget meal prep (2026-03-15)

Spoken hooks read from Instagram's captions.
Skipped as off topic: #2 @offtopicguy (a list of kitchen gadgets, not meal prep).

| # | Reel | Creator | Views | Shares/1K | Spoken hook | Text hook | Would send to | Why it worked |
|---:|---|---|---:|---:|---|---|---|---|
| 1 | https://www.instagram.com/reel/AAA1/ | @alpha | 200K | 50 | "I spend 20 dollars a week on lunches." | "20 dollar week of lunches" | a broke friend | a price in the first line |
| 3 | [BBB2](https://www.instagram.com/reel/BBB2/) | @bravo | 150K | 40 | "Freezer burritos you make once a month." | None (a freezer full of foil) | a busy parent | one batch, a month of food |
| 4 | https://www.instagram.com/reel/CCC3/ | @charlie | 120K | 38 | "I spend 20 dollars a week on my lunches too." | "20 dollar lunches week" | a broke friend | same as #1 |
| 5 | https://www.instagram.com/reel/DDD4/ | @delta | 110K | 35 | "Three sauces that save every boring rice bowl." | "3 sauces for rice bowls" | a roommate | a list with a number |

Not read: #6.
"""


class TestWeekFilling(unittest.TestCase):
    """Items from the end-to-end test: fill a week from one research run, respect on-topic
    decisions, sourced default times and pasted active times, start today, XDG config."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.research = self.dir / "research"
        self.research.mkdir()
        self.log = self.dir / "posted.csv"
        self.cfg = self.dir / "config.json"

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, *extra, json_out=True, today=TODAY):
        argv = ["--research", str(self.research), "--log", str(self.log), "--config", str(self.cfg),
                "--today", today, *extra]
        if json_out:
            argv.append("--json")
        rc, out = run_main(plan, argv)
        return rc, (json.loads(out) if json_out and rc == 0 else out)

    def add_post(self, at, topic, **nums):
        args = ["--log", str(self.log), "add", "--at", at, "--format", "reel", "--topic", topic]
        for k, v in nums.items():
            args += [f"--{k}", str(v)]
        run_main(postlog, args)

    def one_run(self, hooks=True):
        """One research run: report order (the CSV's row order) is by shares per 1K."""
        rows = [
            reel("alpha", 200_000, 9_000, 300, 10_000, code="AAA1"),
            reel("offtopicguy", 900_000, 40_000, 900, 40_000, code="OFF9"),   # 44/1K, off topic
            reel("bravo", 150_000, 7_000, 200, 6_000, code="BBB2"),
            reel("charlie", 120_000, 6_000, 100, 4_560, code="CCC3"),
            reel("delta", 110_000, 5_000, 100, 3_850, code="DDD4"),
            reel("echo", 100_000, 5_000, 100, 3_000, code="EEE5"),
        ]
        rows[1]["caption"] = "10 kitchen gadgets under 20 dollars"
        rows[5]["caption"] = "Meal prep for runners: what I eat before a long run. Comment RUN and I'll send it"
        f = write_research(self.research, "budget-meal-prep", "2026-03-15", rows)
        if hooks:
            f.with_name(f.stem + "-hooks.md").write_text(HOOKS, encoding="utf-8")
        return f

    # 1. one research run fills the week, one angle each, saying where each came from
    def test_one_research_run_fills_a_week_with_distinct_angles(self):
        self.one_run()
        rc, res = self.plan("--posts", "4")
        week = res["week"]
        self.assertTrue(all(s["idea"] for s in week), [s["evidence"] for s in week])
        angles = [s["angle"] for s in week]
        self.assertEqual(len(set(angles)), 4)
        # @charlie repeats @alpha's hook, so it is the same angle and gets no slot of its own
        self.assertFalse(any("CCC3" in (s["reel"] or "") for s in week))
        self.assertIn("the same promise also won for @charlie", " ".join(s["evidence"] for s in week))
        self.assertIn("20 dollar week of lunches", angles)
        self.assertIn("Freezer burritos you make once a month.", angles)  # text hook "None": spoken
        for s in week:
            self.assertIn("research-budget-meal-prep-2026-03-15.csv, Reel #", s["source"])
        # judged Reels first; @echo, which the hooks file didn't read, comes last and says so
        srcs = sorted(week, key=lambda s: "echo" in s["evidence"])
        self.assertEqual(sum("on topic per its hooks file" in s["source"] for s in week), 3)
        self.assertIn("didn't read this Reel", srcs[-1]["source"])
        self.assertEqual([c["angle_no"] for c in res["candidates"]][-1], 4)
        self.assertIn("echo", res["candidates"][-1]["evidence"])
        self.assertIn("why it worked: a price in the first line", " ".join(s["evidence"] for s in week))

    def test_angles_without_hooks_file_come_from_captions_and_say_unchecked(self):
        self.one_run(hooks=False)
        rc, res = self.plan("--posts", "3")
        self.assertTrue(all(s["idea"] for s in res["week"]))
        self.assertIn("on topic not checked", res["week"][0]["source"])
        cands = [c["angle"] for c in res["candidates"]]
        self.assertIn("Meal prep for runners: what I eat before a long run", cands)
        self.assertFalse(any("Comment RUN" in a for a in cands))
        cut = plan.angle_of({"caption": "Comment SEO and I'll send it. I built a tool that tests ads on real hu"})
        self.assertEqual(cut[0], "I built a tool that tests ads on real hu…")

    def test_only_asks_for_research_when_winners_run_out(self):
        self.one_run()
        rc, res = self.plan("--posts", "6")
        filled = [s for s in res["week"] if s["idea"]]
        empty = [s for s in res["week"] if not s["idea"]]
        self.assertEqual(len(filled), res["capacity"]["slots"])
        self.assertTrue(empty)
        self.assertIn("run ig-research on a new idea", empty[0]["evidence"])

    def test_week_interleaves_ideas_before_second_angles(self):
        self.one_run()
        rows = [reel(a, 100_000, 5_000, 100, 2_000 + k * 100, code=f"S{k}") for k, a in enumerate("vwxyz")]
        for k, r in enumerate(rows):
            r["caption"] = ["Sourdough starter in five days flat", "Why your loaf is flat and dense",
                            "Scoring patterns for beginners at home", "Discard crackers nobody throws away",
                            "Cold proof overnight timing chart"][k]
        write_research(self.research, "sourdough-starter", "2026-03-15", rows)
        rc, res = self.plan()
        firsts = [c["idea"] for c in res["candidates"][:2]]
        self.assertEqual(sorted(firsts), ["budget-meal-prep", "sourdough-starter"])
        self.assertEqual([c["angle_no"] for c in res["candidates"][:2]], [1, 1])

    # 7. the output says how many slots the research can fill
    def test_output_says_how_many_slots_research_fills(self):
        self.one_run()
        rc, text = self.plan("--posts", "6", json_out=False)
        self.assertRegex(text, r"Your 1 research file holds \d distinct winning angles across 1 idea: enough for \d slots\.")
        self.assertIn("You asked for 6: the last", text)
        rc, text = self.plan(json_out=False)
        self.assertIn("enough for", text)
        self.assertIn("| Angles |", text)

    # 5. ig-research's on-topic decisions are respected
    def test_off_topic_reel_is_dropped_everywhere(self):
        self.one_run()
        rc, res = self.plan("--posts", "4")
        idea = res["ideas"][0]
        self.assertNotIn("offtopicguy", [c["account"] for c in res["creators"]])
        self.assertNotIn("offtopicguy", [r["account"] for r in idea["top"]])
        self.assertEqual(idea["top"][0]["account"], "alpha")
        self.assertTrue(idea["off_topic"][0].startswith("@offtopicguy"))
        rc, text = self.plan(json_out=False)
        self.assertIn("Left out of \"budget meal prep\" as off topic", text)

    def test_read_hooks_by_link_number_and_handle(self):
        rows = [{"code": c, "account": a} for c, a in [("A", "one"), ("B", "two"), ("C", "three"), ("D", "two")]]
        f = self.dir / "h.md"
        f.write_text("Skipped as off topic: #3 and https://www.instagram.com/reel/A/\n"
                     "Off-topic: @two\n| # | Reel |\n|---|---|\n| 4 | https://www.instagram.com/reel/D/ |\n")
        on, off = plan.read_hooks(f, rows)
        self.assertEqual(set(on), {"D"})
        self.assertEqual(off, {"A", "B", "C"})  # D is in the table, so it stays on topic

    def test_breakdown_section_feeds_why_and_is_not_read_as_off_topic(self):
        rows = [{"code": "A", "account": "one"}, {"code": "B", "account": "two"}]
        f = self.dir / "h.md"
        f.write_text("| # | Reel | Spoken hook |\n|---|---|---|\n| 1 | https://www.instagram.com/reel/A/ | hi there |\n"
                     "| 2 | https://www.instagram.com/reel/B/ | hello |\n\n## Why they worked\n\n"
                     "### 1. @one: 200K views\n\nhttps://www.instagram.com/reel/A/\n\n"
                     "- **Structure** (inferred): list, three tips skipped fast like @two does\n"
                     "- **Payoff** (heard at 0:28): the fix for the third mistake\n"
                     "- **Ask at the end** (heard): comment GUIDE\n")
        on, off = plan.read_hooks(f, rows)
        self.assertEqual(off, set())
        self.assertEqual(on["A"]["why"], "structure: list, three tips skipped fast like @two does; "
                                         "payoff: the fix for the third mistake")
        self.assertNotIn("why", on["B"])

    # 2. a sourced default, and the followers' active times when given
    def test_active_times_parse_lists_counts_and_label_rows(self):
        a = plan.active_summary(plan.parse_active("Tue Thu Sun\n6p 9p\n"))
        self.assertEqual(a["best_days"], [1, 3, 6])
        self.assertEqual(a["peak_hour"], 18)
        a = plan.active_summary(plan.parse_active("Mon 1,200\nTue 900\nWed 2.1K\n12a 3a 6a 9a 12p 3p 6p 9p\n"
                                                  "10 5 40 300 500 700 1,100 900\n"))
        self.assertEqual(a["best_days"][:2], [2, 0])
        self.assertEqual(a["peak_hour"], 18)
        a = plan.active_summary(plan.parse_active("Wednesday 12pm 6pm\nSaturday 9:00\n"))
        self.assertEqual(a["peak_by_day"], {2: 12, 5: 9})
        self.assertIsNone(plan.active_summary(plan.parse_active("nothing here")))

    def test_active_times_set_days_and_time_and_are_remembered(self):
        self.one_run()
        act = self.dir / "active.txt"
        act.write_text("Mon Fri Sat\n8pm\n")
        rc, res = self.plan("--posts", "3", "--active", str(act), "--remember")
        self.assertEqual(sorted(s["day"] for s in res["week"]), ["Fri", "Mon", "Sat"])
        self.assertEqual({s["time"] for s in res["week"]}, {"20:00"})
        self.assertIn("followers", res["week"][0]["day_source"])
        rc, res = self.plan("--posts", "3")  # from the saved settings
        self.assertEqual({s["time"] for s in res["week"]}, {"20:00"})
        bad = self.dir / "bad.txt"
        bad.write_text("no idea")
        with self.assertRaises(SystemExit):
            self.plan("--active", str(bad))

    # 3. the week starts today, or the next free day, or --start
    def test_week_starts_today_even_on_a_monday(self):
        self.one_run()
        rc, res = self.plan("--posts", "2", today="2026-03-16")  # a Monday
        self.assertEqual(res["week_start"], "2026-03-16")
        self.assertTrue(all("2026-03-16" <= s["date"] <= "2026-03-22" for s in res["week"]))

    def test_week_starts_after_a_day_already_posted_and_honours_start(self):
        self.one_run()
        self.add_post("2026-03-18 09:00", "something else entirely")
        rc, res = self.plan("--posts", "2")
        self.assertEqual(res["week_start"], "2026-03-19")
        rc, res = self.plan("--posts", "2", "--start", "2026-04-01")
        self.assertEqual(res["week_start"], "2026-04-01")
        self.assertTrue(all("2026-04-01" <= s["date"] <= "2026-04-07" for s in res["week"]))
        with self.assertRaises(SystemExit):
            self.plan("--start", "next week")

    # 4. XDG_CONFIG_HOME is honoured and --config is documented
    def test_xdg_config_home_for_config_and_log(self):
        old = {k: os.environ.get(k) for k in ("XDG_CONFIG_HOME", "IG_PLAN_LOG")}
        os.environ["XDG_CONFIG_HOME"] = str(self.dir / "xdg")
        os.environ.pop("IG_PLAN_LOG", None)
        try:
            self.assertEqual(plan.config_path(), self.dir / "xdg" / "ig-plan" / "config.json")
            self.assertEqual(postlog.default_log(), self.dir / "xdg" / "ig-plan" / "posted.csv")
            self.one_run()
            run_main(plan, ["--research", str(self.research), "--me", "x", "--remember", "--today", TODAY])
            self.assertTrue((self.dir / "xdg" / "ig-plan" / "config.json").exists())
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        p = subprocess.run([sys.executable, "-B", str(SCRIPTS / "plan.py"), "--help"], capture_output=True, text=True)
        self.assertIn("--config", p.stdout)
        self.assertIn("XDG_CONFIG_HOME", p.stdout)
        self.assertIn("--config", (SCRIPTS.parent / "SKILL.md").read_text())

    # 6. the follow-up lands third by date; an even median is the true median
    def test_follow_up_is_third_by_date_even_when_its_day_is_preferred_late(self):
        for k, slug in enumerate(["aa idea one", "bb idea two", "cc idea three"]):
            write_research(self.research, slug.replace(" ", "-"), "2026-03-15",
                           [reel(a, 100_000, 5_000, 200, 4_000 - k * 500) for a in "pqrst"])
        self.add_post("2026-02-02 18:00", "pantry hack", reach=1000, views=1200, shares=40)
        self.add_post("2026-02-04 18:00", "reel two", reach=1000, views=1300, shares=10)
        self.add_post("2026-02-06 18:00", "reel three", reach=1000, views=1300, shares=8)
        # Today Monday: the default order Wed, Thu, Tue, Sun puts Tue third by preference but
        # second by date; the follow-up must still be the third post of the week.
        rc, res = self.plan("--posts", "4", today="2026-03-16")
        self.assertEqual([s["day"] for s in res["week"]], ["Tue", "Wed", "Thu", "Sun"])
        self.assertEqual(res["week"][2]["idea"], "follow-up: pantry hack")
        self.assertEqual(res["week"][0]["idea"], "bb idea two")
        self.assertEqual(res["week"][1]["idea"], "aa idea one")

    def test_even_median_posting_time(self):
        posts = []
        for k, (d, t) in enumerate([("2026-02-02", "18:00"), ("2026-02-03", "18:00"), ("2026-02-04", "18:30"),
                                    ("2026-02-05", "18:30"), ("2026-02-09", "08:00"), ("2026-02-10", "08:00"),
                                    ("2026-02-11", "08:00"), ("2026-02-12", "08:00")]):
            v = 3000 if t.startswith("18") else 1000
            posts.append({"settled": True, "views": v, "time": t, "weekday": datetime.date.fromisoformat(d).weekday()})
        tim = plan.timing(posts)
        self.assertEqual(tim["best_band"], "17-21")
        self.assertEqual(tim["best_time"], "18:15")
        night = [dict(p, time=("23:00" if p["views"] == 3000 and k % 2 else "01:00") if p["views"] == 3000 else p["time"])
                 for k, p in enumerate(posts)]
        self.assertEqual(plan.timing(night)["best_time"], "00:00")


class TestPromises(unittest.TestCase):
    """End-to-end round 2: angles are deduped by the promise they make, not their wording, and
    checked against the posting log's topics and hooks; only an explicit off-topic mark drops
    a creator. Made-up data: a home-bakery idea, invented creators."""

    BAKERY = [  # report order: by shares per 1K
        ("ann", "AN01", 300_000, 15_000, "You can price your entire bakery menu without spending a single dollar.", "None"),
        ("ben", "BE02", 200_000, 9_000, "no captions", "Did you know you can price your bakery menu on 50 neighbours before you spend a dollar"),
        ("dan", "DA03", 180_000, 7_000, "Sell out your Saturday market stall by ten.", "Sell out the market stall"),
        ("cat", "CA04", 150_000, 5_500, "Your bakery menu, priced by 50 neighbours for $0.", "50 neighbours price your menu"),
        ("eve", "EV05", 140_000, 4_900, "Three cake boxes that ship without breaking.", "3 cake boxes that ship"),
        ("fay", "FA06", 120_000, 4_000, "How I got my first wholesale clients for the bakery.", "First wholesale clients"),
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.research = self.dir / "research"
        self.research.mkdir()
        self.log = self.dir / "posted.csv"
        self.cfg = self.dir / "config.json"
        rows, table = [], []
        for k, (acc, code, views, shares, spoken, text) in enumerate(self.BAKERY, 1):
            rows.append(reel(acc, views, views // 20, 100, shares, code=code))
            table.append(f"| {k} | https://www.instagram.com/reel/{code}/ | @{acc} | {spoken} | {text} |")
        f = write_research(self.research, "home-bakery-side-hustle", "2026-03-15", rows)
        f.with_name(f.stem + "-hooks.md").write_text(
            "# Hooks\n\n| # | Reel | Creator | Spoken hook | Text hook |\n|---|---|---|---|---|\n"
            + "\n".join(table) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def add_post(self, at, topic, shares, hook=""):
        args = ["--log", str(self.log), "add", "--at", at, "--format", "reel", "--topic", topic,
                "--views", "2000", "--shares", str(shares)]
        if hook:
            args += ["--hook", hook]
        run_main(postlog, args)

    def plan(self, *extra):
        rc, out = run_main(plan, ["--research", str(self.research), "--log", str(self.log), "--config",
                                  str(self.cfg), "--today", TODAY, "--json", *extra])
        self.assertEqual(rc, 0)
        return json.loads(out)

    def test_wording_differs_promise_is_the_same(self):
        ign = {"app"}
        self.assertTrue(plan.same_promise(["Test your app idea on 100 buyers"],
                                          ["Your app idea, tested on 100 fake customers"], ign))
        self.assertTrue(plan.same_promise(["Price your whole menu without spending a single dollar"],
                                          ["Did you know you can price your menu before you spend a dollar"], ign))
        self.assertTrue(plan.same_promise(["Run the shop for $0"], ["run your shop for free"], ign))
        self.assertFalse(plan.same_promise(["An agent that finds you customers"],
                                           ["Test your app idea on 100 fake customers"], ign))
        self.assertFalse(plan.same_promise(["Run a whole agency for $0"],
                                           ["Price your whole menu without spending a dollar"], ign))

    def test_no_two_slots_share_a_promise(self):
        rc_res = self.plan("--posts", "4")
        week = [s for s in rc_res["week"] if s["idea"]]
        reels = [s["reel"] for s in week]
        # @ann, @ben and @cat make one promise (price the menu, free): one slot, credited to all
        self.assertEqual(sum(any(c in (r or "") for c in ("AN01", "BE02", "CA04")) for r in reels), 1)
        ev = " ".join(s["evidence"] for s in week)
        self.assertIn("the same promise also won for @ben", ev)
        self.assertIn("@cat", ev)
        self.assertEqual(len({s["angle"] for s in week}), len(week))

    def test_promise_of_followed_up_winner_folds_into_the_follow_up(self):
        # the creator's winner made the price-the-menu promise, worded their own way
        self.add_post("2026-03-08 18:00", "pricing my bakery menu with 50 neighbours", 60)
        self.add_post("2026-03-02 18:00", "my sourdough starter routine", 10)
        self.add_post("2026-03-04 18:00", "kitchen tour", 8)
        self.add_post("2026-03-06 18:00", "flour I buy in bulk", 12)
        res = self.plan("--posts", "4")
        week = res["week"]
        follow = [s for s in week if s["source"].startswith("your posting log")]
        self.assertEqual(len(follow), 1)
        self.assertIn("deliberate follow-up", follow[0]["evidence"])
        for code in ("AN01", "BE02", "CA04"):
            self.assertIn(code, follow[0]["evidence"])
        research = [s for s in week if s["source"].startswith("research-")]
        self.assertFalse(any(c in (s["reel"] or "") for s in research for c in ("AN01", "BE02", "CA04")))
        self.assertEqual(len(research), 3)

    def test_promise_posted_recently_is_left_out_matched_by_hook(self):
        # not a winner (all posts share alike), so no follow-up; the topic says nothing, the hook does
        self.add_post("2026-03-10 18:00", "Tuesday reel", 10,
                      hook="I let 50 neighbours price my bakery menu before I spent a dollar")
        self.add_post("2026-03-02 18:00", "my sourdough starter routine", 10)
        self.add_post("2026-03-04 18:00", "kitchen tour", 10)
        res = self.plan("--posts", "3")
        self.assertFalse(any(s["source"].startswith("your posting log") for s in res["week"]))
        self.assertFalse(any(c in (s["reel"] or "") for s in res["week"] for c in ("AN01", "BE02", "CA04")))
        left = res["ideas"][0]["already_posted"]
        self.assertEqual(len(left), 1)
        self.assertIn("#1 on 2026-03-10", left[0]["posts"][0])
        rc, text = run_main(plan, ["--research", str(self.research), "--log", str(self.log), "--config",
                                   str(self.cfg), "--today", TODAY, "--posts", "3"])
        self.assertIn("as a promise you already posted recently", text)

    def test_promise_posted_long_ago_stays_with_a_note(self):
        self.add_post("2026-01-05 18:00", "pricing my bakery menu with 50 neighbours", 10)
        self.add_post("2026-01-07 18:00", "kitchen tour", 10)
        self.add_post("2026-01-09 18:00", "flour I buy in bulk", 10)
        res = self.plan("--posts", "3")
        first = [s for s in res["week"] if "AN01" in (s["reel"] or "")]
        self.assertEqual(len(first), 1)
        self.assertIn("you made this promise before (#1 on 2026-01-05", first[0]["evidence"])

    # P2: only an explicit off-topic or drift mark drops a creator
    def test_not_read_and_low_reactions_are_not_off_topic(self):
        rows = [{"code": c, "account": a} for c, a in
                [("A", "one"), ("B", "two"), ("C", "three"), ("D", "four"), ("E", "five"), ("F", "six")]]
        f = self.dir / "h.md"
        f.write_text("Skipped: #2 @two (marked ⚠ low reactions); #6 @six not read (top 8 only).\n"
                     "Not read: #5.\n| # | Reel |\n|---|---|\n| 1 | https://www.instagram.com/reel/A/ |\n")
        on, off = plan.read_hooks(f, rows)
        self.assertEqual(off, set())
        f.write_text("Skipped as off topic: #3 @three; #6 @six not read (top 8 only).\n"
                     "Off topic: #2 @two (a gadget list); @four.\n"
                     "@five drifted to another idea.\n")
        on, off = plan.read_hooks(f, rows)
        self.assertEqual(off, {"C", "B", "D", "E"})

    def test_unread_creator_still_listed_to_engage_with(self):
        f = next(self.research.glob("*-hooks.md"))
        # @fay is not in the hooks table: the hooks step stopped before her Reel
        kept = [ln for ln in f.read_text().splitlines() if "FA06" not in ln]
        f.write_text("\n".join(kept).replace(
            "# Hooks\n", "# Hooks\n\nSkipped: #7 @nobody (marked ⚠ low reactions); #6 @fay not read (top 8 only).\n") + "\n")
        res = self.plan()
        self.assertIn("fay", [c["account"] for c in res["creators"]])
        self.assertEqual(res["ideas"][0]["off_topic"], [])


class RoundThreeLog(unittest.TestCase):
    """From the final end-to-end check: a winner whose hook only names the tool and whose caption
    names the promise must still be matched with a post in the log that made that promise."""

    def test_hook_plus_caption_matches_the_log(self):
        r = {"hook": {"text": "This 17 YEAR OLD", "spoken": "This 17 year old fixed ManyChat's biggest problem"},
             "caption": "A 17 year old got tired of paying for comment-to-DM automation, so he built his own"}
        show, said = plan.angle_of(r)
        texts = [said, plan.caption_said(r), f"{said} {plan.caption_said(r)}"]
        log = ["free open source alternative to ManyChat comment DMs",
               "This free tool replaces ManyChat for comment to DM automation"]
        self.assertTrue(plan.same_promise(texts, log, plan.COMMON))

    def test_unrelated_log_post_does_not_match(self):
        r = {"hook": {"text": "AI RUNS MY INSTAGRAM", "spoken": "AI runs my Instagram, 100 to 9,000 followers"},
             "caption": "How I grew from 100 to 9,000 followers letting AI post for me"}
        show, said = plan.angle_of(r)
        texts = [said, plan.caption_said(r), f"{said} {plan.caption_said(r)}"]
        log = ["free open source alternative to ManyChat comment DMs",
               "This free tool replaces ManyChat for comment to DM automation"]
        self.assertFalse(plan.same_promise(texts, log, plan.COMMON))

if __name__ == "__main__":
    unittest.main()
