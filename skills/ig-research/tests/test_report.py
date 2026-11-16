"""report.py's ranking: shares then likes per 1,000 views, the 10K floor, the low-reactions flag,
and a CSV whose earlier columns keep their place. Run from the skill's folder:
python3 -m unittest discover tests

report.py and this test file can be shared, identical, by other skills that carry this same
file; SharedCode fails when a sibling skill's copy differs."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import report  # noqa: E402

OLD_COLS = ["platform", "views", "likes", "comments", "shares", "saves", "engagement_pct",
            "followers", "views_per_follower", "vs_recent_reels", "recent_reels_median",
            "recent_reels_n", "account", "posted", "age_days", "duration_s", "url", "found_by", "best_rank",
            "ig_only_views", "transcript_file", "caption"]

# code, user, shown views, ig-only views, likes, comments, shares, queries
IG = [
    ("AAA", "a", 100_000, 100_000, 5000, 100, 3000, "1"),   # 30 shares/1K
    ("BBB", "b", 60_000, 50_000, 3000, 50, 2000, "1,2"),    # 40 shares/1K on IG-only views
    ("CCC", "c", 5_000, 5_000, 400, 10, 500, "2"),          # under the floor
    ("DDD", "d", 300_000, 300_000, 100, 20, 900, "1"),      # 0.04% reactions: low
    ("EEE", "e", 40_000, 40_000, "", 30, 400, "1"),         # likes hidden: 10 shares/1K, unchecked
    ("FFF", "f", 80_000, 80_000, 4000, 40, "", "2"),        # no share count
]


def ig_files(tmp):
    lines = ["\t".join(report.IG_COLS)]
    for i, (code, user, v, igv, lk, cm, sh, q) in enumerate(IG, 1):
        lines.append("\t".join(map(str, [i, code, user, "2026-10-01", 30, v, igv, lk, cm, sh, "clips", q,
                                          f"caption {code}"])))
    p = Path(tmp) / "ig-1.json"
    p.write_text(json.dumps(lines))
    body = [ln.split("\t") for ln in lines[1:]]
    return p, len(body), report.djb2("\n".join("\t".join(f[:-1]) for f in body))


def tt_file(tmp):
    p = Path(tmp) / "tiktok.tsv"
    rows = ["\t".join(report.TT_COLS),
            "\t".join(map(str, [1, "777", "t", 1000, "2026-10-02", 20, 20_000, 1000, 50, 100, 300, "1", "tt video"]))]
    p.write_text("\n".join(rows) + "\n")
    return p


def run(tmp, *extra, tiktok=True):
    p, n, h = ig_files(tmp)
    out = Path(tmp) / "out.csv"
    tt = ["--tiktok", str(tt_file(tmp))] if tiktok else []
    res = subprocess.run([sys.executable, "-B", str(SCRIPTS / "report.py"), "--idea", "test idea",
                          "--queries", "q one", "q two", "--ig", str(p), "--ig-rows", str(n), "--ig-hash", h,
                          *tt, "--out", str(out), "--top", "0", *extra],
                         capture_output=True, text=True)
    if res.returncode:
        raise AssertionError(res.stderr)
    with out.open() as fh:
        reader = csv.DictReader(fh)
        return reader.fieldnames, list(reader), res.stdout


def key(r):
    return r["url"].rstrip("/").rsplit("/", 1)[-1]


class Ranking(unittest.TestCase):
    def test_send_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            cols, rows, out = run(tmp)
        self.assertEqual([key(r) for r in rows], ["BBB", "AAA", "EEE", "777", "FFF", "CCC", "DDD"])
        self.assertEqual([r["send_rank"] for r in rows], ["1", "2", "3", "4", "", "", ""])
        by = {key(r): r for r in rows}
        self.assertEqual(by["BBB"]["shares_per_1k_views"], "40.0")
        self.assertEqual(by["BBB"]["rate_basis"], "instagram-only views")
        self.assertEqual(by["777"]["saves_per_1k_views"], "15.0")
        self.assertEqual(by["777"]["rate_basis"], "tiktok plays")
        self.assertEqual(by["DDD"]["low_reactions"], "yes")
        self.assertEqual(by["EEE"]["low_reactions"], "")
        self.assertEqual(by["EEE"]["reactions_pct"], "")
        self.assertIn("10K+ views): 1, marked", out)
        self.assertIn("1 video with 10K+ views has likes hidden", out)
        self.assertIn("⚠", out)

    def test_csv_keeps_old_columns_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            cols, rows, _ = run(tmp)
        self.assertEqual(cols[:len(OLD_COLS)], OLD_COLS)
        by = {key(r): r for r in rows}
        # engagement_pct keeps its old meaning: (likes + comments) / shown views
        self.assertEqual(by["BBB"]["engagement_pct"], "5.08")

    def test_sort_views_is_the_old_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, rows, out = run(tmp, "--sort", "views")
        self.assertEqual([key(r) for r in rows], ["DDD", "AAA", "FFF", "BBB", "EEE", "777", "CCC"])
        self.assertTrue(all(r["send_rank"] == "" for r in rows))
        self.assertEqual({key(r): r["low_reactions"] for r in rows}["DDD"], "yes")
        self.assertIn("Sorted by views", out)

    def test_drop_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, rows, _ = run(tmp, "--drop", "2")
        self.assertNotIn("CCC", [key(r) for r in rows])
        self.assertIn("BBB", [key(r) for r in rows])  # found by 1 and 2


class SavesColumn(unittest.TestCase):
    def test_instagram_only_table_has_no_saves_column(self):
        """Instagram shows no saves on other people's Reels: no column that is always blank."""
        with tempfile.TemporaryDirectory() as tmp:
            cols, _, out = run(tmp, tiktok=False)
        header = next(l for l in out.splitlines() if l.startswith("| # |"))
        self.assertNotIn("Saves/1K", header)
        self.assertIn("No Saves/1K column", out)
        row = next(l for l in out.splitlines() if l.startswith("| 1 |"))
        self.assertEqual(row.count("|"), header.count("|"))
        self.assertIn("saves_per_1k_views", cols)  # the CSV keeps its columns

    def test_saves_column_shown_with_tiktok(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, out = run(tmp)
        header = next(l for l in out.splitlines() if l.startswith("| # |"))
        self.assertIn("Saves/1K", header)
        self.assertIn("| 15 |", out)  # the TikTok row's saves per 1K


# The sentence report.py carries when it is shared. Siblings are found by it, not by name.
SHARED_MARK = "shared, identical, by other skills that carry this same file"


class SharedCode(unittest.TestCase):
    def test_shared_files_match_the_other_skills(self):
        """A change to report.py (or this test) goes to every skill that carries a copy.
        Skipped when the skill stands alone, as in a public copy of one skill."""
        skill = SCRIPTS.parent
        found = 0
        for other in sorted(skill.parent.iterdir()):
            theirs = other / "scripts" / "report.py"
            if other == skill or not theirs.is_file():
                continue
            if " ".join(SHARED_MARK.split()) not in " ".join(theirs.read_text().split()):
                continue  # a different report.py
            for rel in ("scripts/report.py", "tests/test_report.py"):
                if (other / rel).exists():
                    found += 1
                    self.assertEqual((skill / rel).read_text(), (other / rel).read_text(),
                                     f"{other.name}/{rel} differs from {skill.name}/{rel}; copy it across")
        if not found:
            self.skipTest("no sibling skill next to this one")

    def test_report_names_no_other_skill(self):
        """The copy that goes public must not name the private skills sharing it."""
        text = (SCRIPTS / "report.py").read_text()
        self.assertIn(" ".join(SHARED_MARK.split()), " ".join(text.split()))
        for d in SCRIPTS.parent.parent.iterdir():
            # hyphenated names only: a one-word skill such as "read" is also an ordinary word
            if d.is_dir() and d != SCRIPTS.parent and "-" in d.name and (d / "SKILL.md").exists():
                self.assertNotIn(d.name, text, f"report.py names the skill {d.name}")


if __name__ == "__main__":
    unittest.main()
