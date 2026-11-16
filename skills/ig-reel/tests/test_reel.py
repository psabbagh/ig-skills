"""reel.py: reading ig-research output, checking a draft, the copy block, the command line.
Offline, made-up data only. Run: python3 -m unittest discover ig-reel/tests"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPT = SKILL / "scripts" / "reel.py"
sys.path.insert(0, str(SCRIPT.parent))
import reel  # noqa: E402

COLS = ["platform", "views", "likes", "comments", "shares", "account", "posted", "age_days",
        "url", "ig_only_views", "caption", "send_rank", "shares_per_1k_views", "low_reactions"]


def row(code, views, likes, shares, rank="", spk="", low="", account="maker"):
    return {"platform": "Instagram", "views": views, "likes": likes, "comments": 10, "shares": shares,
            "account": account, "posted": "2026-10-01", "age_days": 40,
            "url": f"https://www.instagram.com/reel/{code}/", "ig_only_views": views,
            "caption": "a made-up caption", "send_rank": rank, "shares_per_1k_views": spk,
            "low_reactions": low}


HOOKS_MD = """# Hooks: made-up idea (2026-11-01)

| # | Video | Creator | Views | Shares/1K | Spoken hook | Text hook | Would send to |
|---:|---|---|---:|---:|---|---|---|
| 1 | [Reel](https://www.instagram.com/reel/AAA111/) | @one | 50K | 20.0 | "My oven caught fire and the app told me first." | "OVEN ALERT" | A roommate: "set this up" |
| 2 | [Reel](https://www.instagram.com/reel/BBB222/) | @two | 90K | 12.0 | "Stop paying for a smart oven." | None: a kitchen | Nobody obvious |
"""

DRAFT = """## Hook
Spoken: My oven caught fire and my phone told me first.
On screen: Phone beat the smoke alarm

## Script
My oven caught fire and my phone told me first.
I'd left a tray in for {{how long}} and walked out.
Here's the setup, it takes two minutes.
Send this to whoever forgets the oven.

## On-screen text
0:00-0:03 Phone beat the smoke alarm
0:05-0:08 {{how long}} in the oven
"""


def write_research(folder, rows, hooks=HOOKS_MD, stem="research-smart-oven-2026-11-01"):
    folder = Path(folder)
    with open(folder / f"{stem}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    if hooks is not None:
        (folder / f"{stem}-hooks.md").write_text(hooks, encoding="utf-8")
    return folder / f"{stem}.csv"


class Evidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_hooks_table_is_read_by_header_words(self):
        p = self.dir / "h-hooks.md"
        p.write_text(HOOKS_MD, encoding="utf-8")
        h = reel.read_hooks(p)
        self.assertEqual(set(h), {"AAA111", "BBB222"})
        self.assertIn("oven caught fire", h["AAA111"]["spoken_hook"])
        self.assertEqual(h["AAA111"]["text_hook"], '"OVEN ALERT"')
        self.assertIn("roommate", h["AAA111"]["would_send_to"])

    def test_columns_found_in_any_order(self):
        p = self.dir / "x-hooks.md"
        p.write_text("| Would send to | Text hook | Reel | Spoken hook |\n|---|---|---|---|\n"
                     "| a friend | NONE | https://www.instagram.com/reel/ZZZ9/ | hello there |\n", encoding="utf-8")
        h = reel.read_hooks(p)["ZZZ9"]
        self.assertEqual((h["spoken_hook"], h["text_hook"], h["would_send_to"]),
                         ("hello there", "NONE", "a friend"))

    def test_winners_follow_research_order_and_skip_low_reactions(self):
        write_research(self.dir, [
            row("BBB222", 90000, 3000, 1080, rank=2, spk=12.0),
            row("CCC333", 2000000, 5000, 900, low="yes"),
            row("AAA111", 50000, 2000, 1000, rank=1, spk=20.0),
        ])
        c, h = reel.research_files(self.dir)
        ev = reel.evidence(c, h)
        self.assertEqual([w["code"] for w in ev["winners"]], ["AAA111", "BBB222"])
        self.assertEqual(ev["skipped_low_reactions"], 1)
        self.assertEqual(ev["without_hook"], 0)

    def test_hooked_reels_lead_since_they_passed_the_topic_check(self):
        write_research(self.dir, [
            row("OFF999", 80000, 3000, 2400, rank=1, spk=30.0),
            row("AAA111", 50000, 2000, 1000, rank=2, spk=20.0),
        ])
        ev = reel.evidence(*reel.research_files(self.dir))
        self.assertEqual(ev["winners"][0]["code"], "AAA111")
        self.assertEqual(ev["winners"][-1]["code"], "OFF999")
        self.assertEqual(ev["without_hook"], 1)

    def test_old_research_gets_the_rate_and_the_flag_worked_out(self):
        rows = [row("AAA111", 100000, 3000, 500), row("BBB222", 100000, 3000, 2000),
                row("LOW000", 500000, 1000, 50)]
        for r in rows:
            del r["send_rank"], r["shares_per_1k_views"], r["low_reactions"]
        cols = [c for c in COLS if c not in ("send_rank", "shares_per_1k_views", "low_reactions")]
        with open(self.dir / "research-old-2026-10-01.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        ev = reel.evidence(*reel.research_files(self.dir))
        self.assertEqual([w["code"] for w in ev["winners"]], ["BBB222", "AAA111"])
        self.assertEqual(ev["winners"][0]["shares_per_1k_views"], 20.0)
        self.assertEqual(ev["skipped_low_reactions"], 1)

    def test_folder_picks_newest_matching_idea(self):
        write_research(self.dir, [row("AAA111", 50000, 2000, 1000, rank=1)], stem="research-smart-oven-2026-10-01")
        write_research(self.dir, [row("BBB222", 50000, 2000, 1000, rank=1)], stem="research-smart-oven-2026-11-01")
        sub = self.dir / "other"
        sub.mkdir()
        write_research(sub, [row("CCC333", 50000, 2000, 1000, rank=1)], stem="research-garden-hose-2026-12-01")
        c, h = reel.research_files(self.dir, idea="smart oven")
        self.assertTrue(c.name.endswith("smart-oven-2026-11-01.csv"))
        self.assertTrue(h.name.endswith("-hooks.md"))
        c, _ = reel.research_files(self.dir, idea="garden hose tips")
        self.assertIn("garden-hose", c.name)

    def test_hooks_file_alone_or_csv_given_directly(self):
        csvp = write_research(self.dir, [row("AAA111", 50000, 2000, 1000, rank=1)])
        hooks = csvp.with_name(csvp.stem + "-hooks.md")
        self.assertEqual(reel.research_files(csvp), (csvp, hooks))
        self.assertEqual(reel.research_files(hooks), (csvp, hooks))
        csvp.unlink()
        ev = reel.evidence(*reel.research_files(hooks))
        self.assertEqual([w["code"] for w in ev["winners"]], ["AAA111", "BBB222"])

    def test_nothing_found_says_unproven(self):
        out = subprocess.run([sys.executable, "-B", str(SCRIPT), "evidence", str(self.dir)],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertIn("unproven", out.stdout)


class Draft(unittest.TestCase):
    def test_parse(self):
        d = reel.parse_draft(DRAFT)
        self.assertEqual(d["hook"]["spoken"], "My oven caught fire and my phone told me first.")
        self.assertEqual(d["hook"]["onscreen"], "Phone beat the smoke alarm")
        self.assertEqual(len(d["script"]), 4)
        self.assertEqual([(c["start"], c["end"]) for c in d["cues"]], [(0.0, 3.0), (5.0, 8.0)])

    def test_placeholders_block_ready(self):
        d = reel.parse_draft(DRAFT)
        r = reel.check(d)
        self.assertFalse(r["ready"])
        self.assertEqual({p["placeholder"] for p in r["placeholders"]}, {"{{how long}}"})
        self.assertEqual(len(r["placeholders"]), 2)
        self.assertEqual(r["problems"], [])

    def test_filled_draft_is_ready_and_timed(self):
        d = reel.parse_draft(DRAFT.replace("{{how long}}", "an hour"))
        r = reel.check(d)
        self.assertTrue(r["ready"], r)
        self.assertAlmostEqual(r["length_s"], r["words"] / 2.5, places=1)
        self.assertEqual(r["lines"][0]["start"], 0.0)
        self.assertTrue(r["heard_by_3s"].startswith("My oven caught fire"))
        self.assertLessEqual(len(r["heard_by_3s"].split()), 8)

    def test_wps_changes_length(self):
        d = reel.parse_draft(DRAFT)
        self.assertLess(reel.check(d, wps=3.0)["length_s"], reel.check(d, wps=2.0)["length_s"])

    def test_script_must_open_with_the_hook(self):
        d = reel.parse_draft(DRAFT.replace("Spoken: My oven caught fire", "Spoken: Your oven is lying"))
        self.assertIn("the script does not open with the chosen spoken hook", reel.check(d)["problems"])

    def test_hook_punctuation_and_quotes_dont_matter(self):
        d = reel.parse_draft(DRAFT.replace("Spoken: My oven caught fire and my phone told me first.",
                                           'Spoken: "My oven caught fire, and my phone told me first"'))
        self.assertNotIn("the script does not open with the chosen spoken hook", reel.check(d)["problems"])

    def test_cue_problems(self):
        bad = DRAFT.replace("0:05-0:08 {{how long}} in the oven",
                            "0:02-0:04 overlapping\n0:09-0:07 backwards\n0:59-1:02 after the end\n"
                            "no timing here")
        r = reel.check(reel.parse_draft(bad))
        joined = "\n".join(r["problems"])
        self.assertIn("overlaps", joined)
        self.assertIn("ends before it starts", joined)
        self.assertIn("starts after the script ends", joined)
        self.assertIn("without a timing", joined)

    def test_cue_too_long_to_read_warns(self):
        long = DRAFT.replace("0:05-0:08 {{how long}} in the oven",
                             "0:05-0:06 this cue has far too many words to read in one second")
        r = reel.check(reel.parse_draft(long))
        self.assertTrue(any("to read" in w for w in r["warnings"]))

    def test_open_ended_cue_and_minutes(self):
        d = reel.parse_draft(DRAFT.replace("0:05-0:08", "0:05-end"))
        self.assertIsNone(d["cues"][1]["end"])
        self.assertEqual(reel.parse_draft("## Script\nhi\n## On-screen text\n1:05-1:07 x")["cues"][0]["start"], 65.0)

    def test_target_warns_when_far_off(self):
        r = reel.check(reel.parse_draft(DRAFT), target=60)
        self.assertTrue(any("target" in w for w in r["warnings"]))

    def test_target_says_where_it_stands_inside_the_margin(self):
        r = reel.check(reel.parse_draft(DRAFT), target=round(reel.check(reel.parse_draft(DRAFT))["length_s"]) + 2)
        self.assertFalse(any("target" in w for w in r["warnings"]))
        self.assertIn("under, inside the", r["target_note"])
        self.assertIsNone(reel.check(reel.parse_draft(DRAFT))["target_note"])

    def test_card_before_its_spoken_line_is_a_problem(self):
        # L3 "Here's the setup, it takes two minutes." starts at 0:08.0.
        early = DRAFT.replace("0:05-0:08 {{how long}} in the oven", "0:05-0:07 Setup: two minutes")
        r = reel.check(reel.parse_draft(early))
        self.assertTrue(any("before its spoken line (L3 at 0:08.0)" in p for p in r["problems"]), r["problems"])
        for on_time in ("0:07-0:10 Setup: two minutes", "0:08-0:10 Setup: two minutes"):
            r = reel.check(reel.parse_draft(DRAFT.replace("0:05-0:08 {{how long}} in the oven", on_time)))
            self.assertFalse(any("before its spoken line" in p for p in r["problems"]), on_time)

    def test_step_numbers_and_unmatched_cards_are_not_tied_to_a_line(self):
        d = reel.parse_draft(DRAFT)
        timed = [{"start": i * 4.0, "text": t} for i, t in enumerate(d["script"])]
        self.assertEqual(reel.spoken_line_for("2. The setup", timed), 2)
        self.assertIsNone(reel.spoken_line_for("Totally unrelated words", timed))

    def test_quotes_inside_a_cue_are_kept(self):
        d = reel.parse_draft(DRAFT.replace("0:05-0:08 {{how long}} in the oven", '0:05-0:08 Mia: "never again"')
                             .replace("On screen: Phone beat the smoke alarm", 'On screen: "Phone beat the smoke alarm"'))
        self.assertEqual(d["cues"][1]["text"], 'Mia: "never again"')
        self.assertEqual(d["hook"]["onscreen"], "Phone beat the smoke alarm")

    def test_shared_word_rule(self):
        self.assertEqual(reel.spoken_count("It cost {{your real number}} and $18,000, 30% of it."), 11)  # 1+1+1+1+3+2+1+1
        self.assertEqual(reel.words("Wait — {{the thing}} works."), ["Wait", "{{the thing}}", "works"])
        self.assertEqual(reel.words_heard_by(["One two three four five six seven eight nine ten."], 3.0, 2.5),
                         "One two three four five six seven")

    def test_copy_block_has_every_part(self):
        d = reel.parse_draft(DRAFT)
        block = reel.copy_block(d, reel.check(d))
        for part in ("HOOK (said): My oven", "HOOK (on screen): Phone beat", "SCRIPT",
                     "Send this to whoever", "ON-SCREEN TEXT", "0:00.0-0:03.0  Phone beat", "LENGTH: about"):
            self.assertIn(part, block)


class CommandLine(unittest.TestCase):
    def run_cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], input=stdin,
                              capture_output=True, text=True)

    def test_check_exit_codes(self):
        self.assertEqual(self.run_cli("check", "-", stdin=DRAFT).returncode, 1)
        out = self.run_cli("check", "-", stdin=DRAFT.replace("{{how long}}", "an hour"))
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertIn("READY TO RECORD", out.stdout)
        self.assertEqual(self.run_cli("check", "-", stdin="no sections here").returncode, 2)
        self.assertEqual(self.run_cli("check", "/no/such/file.md").returncode, 2)

    def test_check_json(self):
        out = self.run_cli("check", "-", "--json", stdin=DRAFT)
        data = json.loads(out.stdout)
        self.assertIn("copy_block", data)
        self.assertFalse(data["ready"])

    def test_skills_lists_every_sibling(self):
        data = json.loads(self.run_cli("skills", "--json").stdout)
        self.assertEqual(set(data), {"ig-research", "ig-script", "ig-voice", "ig-caption"})


TIMELINE = SKILL.parent / "ig-script" / "scripts" / "timeline.py"
SAME_LINES = [
    "{{N}} hours a week. That's what one free skill gave back.",
    "It was {{the weekly job}}, every {{day of the week}} night.",
    "It cost me $18,000 and 30% of my weekends — really.",
    "Now it's done in {{how long it took}}.",
    "Send this to the friend who still does it by hand.",
]


@unittest.skipUnless(TIMELINE.is_file(), "ig-script is not installed next to this skill")
class SameCountAsIgScript(unittest.TestCase):
    """reel.py check and ig-script's timeline.py count the same lines the same way."""

    def test_both_timers_agree(self):
        draft = ("## Hook\nSpoken: " + SAME_LINES[0] + "\nOn screen: None\n\n## Script\n"
                 + "\n".join(SAME_LINES) + "\n")
        r = json.loads(subprocess.run([sys.executable, "-B", str(SCRIPT), "check", "-", "--json"],
                                      input=draft, capture_output=True, text=True).stdout)
        t = json.loads(subprocess.run([sys.executable, "-B", str(TIMELINE), "-", "--json"],
                                      input="\n".join(SAME_LINES), capture_output=True, text=True).stdout)
        self.assertEqual(r["words"], t["total_words"])
        self.assertAlmostEqual(r["length_s"], t["total_seconds"], places=1)
        self.assertEqual(r["heard_by_3s"], t["heard_by_3s"])
        self.assertEqual([x["start"] for x in r["lines"]], [round(x["start"], 1) for x in t["lines"]])


class SkillFiles(unittest.TestCase):
    """The shape the repo's README asks of every skill."""

    def test_frontmatter_and_openai_yaml(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: ig-reel\n"))
        self.assertIn("\nargument-hint: ", text.split("\n---", 2)[0] + "\n")
        y = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
        short = [l for l in y.splitlines() if "short_description" in l][0].split(":", 1)[1].strip().strip('"')
        self.assertTrue(25 <= len(short) <= 64, short)
        self.assertIn("$ig-reel", y)

    def test_no_hard_paths_into_sibling_folders_and_nothing_personal(self):
        for p in [SKILL / "SKILL.md", *SKILL.glob("references/*.md")]:
            text = p.read_text(encoding="utf-8")
            for sib in ("ig-research", "ig-script", "ig-voice", "ig-caption"):
                self.assertNotIn(f"{sib}/scripts", text, p)
            self.assertNotIn("/Users/", text, p)
            self.assertNotIn("Pierre", text, p)


if __name__ == "__main__":
    unittest.main()
