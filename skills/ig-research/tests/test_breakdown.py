"""breakdown.py: the "why they worked" blocks say how each part is known, refuse a judgement
passed off as seen, and go into the hooks file without touching the hooks table.
Run from the skill's folder: python3 -m unittest discover tests"""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
COLS = ["platform", "views", "account", "duration_s", "url", "shares_per_1k_views", "low_reactions"]
TABLE = """# Hooks

| Reel | Creator | Spoken hook | Text hook | Would send to |
|---|---|---|---|---|
| https://www.instagram.com/reel/AAA111/ | a | "Stop doing X" | None | a friend |
"""


def good(code="AAA111"):
    return {"code": code,
            "hook": {"text": "Stop doing X", "basis": "heard", "at": 0},
            "hook_type": {"text": "a warning", "basis": "inferred", "from": "heard"},
            "first_frames": {"text": "Creator at a desk, title 'Stop doing X'", "basis": "seen", "at": 0.5},
            "structure": {"kind": "list", "text": "three mistakes, one per beat", "basis": "inferred", "from": "heard"},
            "payoff": {"text": "the fix for the third mistake", "basis": "heard", "at": 28},
            "ask": {"text": "Comment FIX for the guide", "basis": "seen", "at": 33},
            "send_to": {"text": "a coworker making the same mistake", "basis": "inferred"}}


def setup(tmp, entries, hooks_text=TABLE):
    t = Path(tmp)
    with (t / "r.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerow({"platform": "Instagram", "views": 120000, "account": "a", "duration_s": 35.4,
                    "url": "https://www.instagram.com/reel/AAA111/", "shares_per_1k_views": 12.5,
                    "low_reactions": ""})
    (t / "notes.json").write_text(json.dumps({"reels": entries}))
    (t / "r-hooks.md").write_text(hooks_text)
    return t


def run(t):
    return subprocess.run([sys.executable, "-B", str(SCRIPTS / "breakdown.py"), "--csv", str(t / "r.csv"),
                           "--notes", str(t / "notes.json")], capture_output=True, text=True)


class Breakdown(unittest.TestCase):
    def test_block_labels_every_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = setup(tmp, [good()])
            res = run(t)
            self.assertEqual(res.returncode, 0, res.stderr)
            out = (t / "r-hooks.md").read_text()
        self.assertIn("### 1. @a: 120K views, 12.5 shares per 1K", out)
        self.assertIn('- **Hook** (heard at 0:00, Instagram\'s captions): "Stop doing X". '
                      "Type: a warning (inferred from what was heard).", out)
        self.assertIn("- **First frames** (seen at 0:00.5):", out)
        self.assertIn("- **Length** (Instagram's data): 35 s", out)
        self.assertIn("- **Structure** (inferred from what was heard): list, three mistakes", out)
        self.assertIn("- **Ask at the end** (seen at 0:33): Comment FIX", out)
        self.assertIn("- **Would send to** (inferred): a coworker", out)
        self.assertIn("Nobody watched these Reels end to end", out)

    def test_hook_ending_a_sentence_gets_one_full_stop(self):
        e = good()
        e["hook"]["text"] = "I made this without spending a single dollar."
        q = good()
        q["hook"]["text"] = "Are you still doing X?"
        for entry, want in ((e, '"I made this without spending a single dollar." Type:'),
                            (q, '"Are you still doing X?" Type:')):
            with tempfile.TemporaryDirectory() as tmp:
                t = setup(tmp, [entry])
                res = run(t)
                self.assertEqual(res.returncode, 0, res.stderr)
                out = (t / "r-hooks.md").read_text()
            self.assertIn(want, out)
            self.assertNotIn('.".', out)
            self.assertNotIn('?".', out)

    def test_docstring_example_matches_the_reference(self):
        import re
        doc = (SCRIPTS / "breakdown.py").read_text(encoding="utf-8").split('"""')[1]
        ref = (SCRIPTS.parent / "references" / "breakdown.md").read_text(encoding="utf-8")
        from_doc = json.loads(re.search(r'\{"reels": \[.*?\n\s*\]\}', doc, re.S).group(0))
        from_ref = json.loads(re.search(r"```json\n(.*?)```", ref, re.S).group(1))
        self.assertEqual(from_doc, from_ref)
        self.assertEqual(from_doc["reels"][0]["hook_type"].get("from"), "heard")

    def test_table_kept_and_rerun_replaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = setup(tmp, [good()])
            run(t)
            first = (t / "r-hooks.md").read_text()
            run(t)
            second = (t / "r-hooks.md").read_text()
        self.assertTrue(first.startswith(TABLE.rstrip()))
        self.assertEqual(first, second)
        self.assertEqual(second.count("## Why they worked"), 1)
        # no new table rows: ig-reel reads every "|" line of this file as the hooks table
        self.assertEqual([l for l in second.splitlines() if l.startswith("|")],
                         [l for l in TABLE.splitlines() if l.startswith("|")])

    def test_judgement_cannot_be_seen(self):
        e = good()
        e["send_to"]["basis"] = "seen"
        e["send_to"]["at"] = 3
        with tempfile.TemporaryDirectory() as tmp:
            t = setup(tmp, [e])
            res = run(t)
            unchanged = (t / "r-hooks.md").read_text() == TABLE
        self.assertEqual(res.returncode, 2)
        self.assertIn("send_to is a judgement", res.stderr)
        self.assertTrue(unchanged)

    def test_seen_needs_the_frame_second(self):
        e = good()
        del e["first_frames"]["at"]
        with tempfile.TemporaryDirectory() as tmp:
            res = run(setup(tmp, [e]))
        self.assertEqual(res.returncode, 2)
        self.assertIn("first_frames is seen, so give \"at\"", res.stderr)

    def test_unread_is_allowed_and_said(self):
        e = good()
        e["ask"] = {"basis": "unread"}
        e["payoff"] = {"basis": "unread"}
        with tempfile.TemporaryDirectory() as tmp:
            t = setup(tmp, [e])
            res = run(t)
            out = (t / "r-hooks.md").read_text()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("- **Ask at the end** (not read): not read", out)

    def test_missing_part_and_unknown_code(self):
        e = good("ZZZ999")
        del e["payoff"]
        e["structure"]["kind"] = "vibes"
        with tempfile.TemporaryDirectory() as tmp:
            res = run(setup(tmp, [e]))
        self.assertEqual(res.returncode, 2)
        self.assertIn("ZZZ999: not an Instagram row", res.stderr)
        self.assertIn("payoff is missing", res.stderr)
        self.assertIn("structure kind must be one of", res.stderr)


if __name__ == "__main__":
    unittest.main()
