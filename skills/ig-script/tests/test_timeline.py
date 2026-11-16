"""timeline.py and the skill's files. Offline, made-up lines only.
Run: python3 -m unittest discover -s ig-script/tests"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPT = SKILL / "scripts" / "timeline.py"
sys.path.insert(0, str(SCRIPT.parent))
import timeline  # noqa: E402

LINES = """L1. My kettle texted me that the water was ready.
L2. I'd been standing there for {{how long}} like an idiot.
L3. It cost $18,000 to build the first one, and 30% of that was the app.
L4. Here's how you set one up.
L5. Plug it in.
L6. Open the app.
L7. Pick the sound.
L8. Send this to whoever stares at the kettle.
"""


def run(*args, stdin=None):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], input=stdin,
                          capture_output=True, text=True)


class Counting(unittest.TestCase):
    def test_word_rule(self):
        self.assertEqual(timeline.spoken_count("It cost {{your real number}} and $18,000, 30% of it."), 11)
        self.assertEqual(timeline.spoken_count("Wait — really?"), 2)
        self.assertEqual(timeline.spoken_count("10K views, $5 each"), 6)  # ten thousand views five dollars each
        self.assertEqual(timeline.words("{{the thing}} works."), ["{{the thing}}", "works"])

    def test_heard_by_counts_whole_words(self):
        a = timeline.analyse("One two three four five six seven eight nine ten.")
        self.assertEqual(a["heard_by_3s"], "One two three four five six seven")
        self.assertEqual(a["total_seconds"], 4.0)

    def test_lines_are_timed_in_order(self):
        a = timeline.analyse(LINES)
        self.assertEqual(len(a["lines"]), 8)
        self.assertEqual(a["lines"][0]["start"], 0.0)
        for prev, cur in zip(a["lines"], a["lines"][1:]):
            self.assertAlmostEqual(cur["start"], prev["end"], places=2)
        self.assertEqual(a["lines"][1]["text"].split()[0], "I'd")  # "L2." dropped
        self.assertAlmostEqual(a["total_seconds"], a["total_words"] / 2.5, places=1)

    def test_pointers(self):
        a = timeline.analyse(LINES, target=10)
        notes = "\n".join(a["notes"])
        self.assertIn("Midpoint", notes)
        self.assertIn("over the 10s target", notes)
        self.assertIn("L4-L8: no number or name in 5 lines", notes)
        long = timeline.analyse(" ".join(["word"] * 25))
        self.assertTrue(any("long for one hearing" in f for f in long["lines"][0]["flags"]))

    def test_wps(self):
        self.assertLess(timeline.analyse(LINES, wps=3.0)["total_seconds"],
                        timeline.analyse(LINES, wps=2.0)["total_seconds"])


class CommandLine(unittest.TestCase):
    def test_text_and_json(self):
        out = run("-", stdin=LINES)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Heard by 0:03:", out.stdout)
        data = json.loads(run("-", "--json", "--target", "30", stdin=LINES).stdout)
        self.assertEqual(data["target"], 30)
        self.assertEqual(len(data["lines"]), 8)

    def test_no_lines(self):
        self.assertEqual(run("-", stdin="\n\n").returncode, 2)


REEL = SKILL.parent / "ig-reel" / "scripts" / "reel.py"


@unittest.skipUnless(REEL.is_file(), "ig-reel is not installed next to this skill")
class SameCountAsIgReel(unittest.TestCase):
    def test_both_timers_agree(self):
        lines = [re.sub(r"^L\d+\.\s*", "", l) for l in LINES.splitlines() if l.strip()]
        draft = "## Hook\nSpoken: " + lines[0] + "\nOn screen: None\n\n## Script\n" + "\n".join(lines) + "\n"
        r = json.loads(subprocess.run([sys.executable, "-B", str(REEL), "check", "-", "--json"],
                                      input=draft, capture_output=True, text=True).stdout)
        t = json.loads(run("-", "--json", stdin=LINES).stdout)
        self.assertEqual(r["words"], t["total_words"])
        self.assertAlmostEqual(r["length_s"], t["total_seconds"], places=1)
        self.assertEqual(r["heard_by_3s"], t["heard_by_3s"])

    def test_rule_is_written_the_same_in_both(self):
        def rule(path):
            text = path.read_text(encoding="utf-8")
            return text[text.index("# ---- Spoken word count."):text.index("def spoken_count")].split("\n", 2)[2]
        self.assertEqual(rule(SCRIPT), rule(REEL))


class SkillFiles(unittest.TestCase):
    def test_frontmatter_and_openai_yaml(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: ig-script\n"))
        self.assertIn("\nargument-hint: ", text.split("\n---", 2)[0] + "\n")
        self.assertIn("$ig-script", (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8"))

    def test_referenced_files_exist(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for ref in re.findall(r"`((?:references|scripts)/[\w./-]+)`", text):
            self.assertTrue((SKILL / ref).is_file(), ref)

    def test_called_by_another_skill_and_pasted_scripts(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## Called by another skill", text)
        self.assertIn("**Pasted**", text)

    def test_own_work_and_agrees_with_ig_reel(self):
        for p in [SKILL / "SKILL.md", SCRIPT, *SKILL.glob("references/*.md")]:
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("github.com", text, p)
            self.assertNotIn("Schincariol", text, p)
        ref = (SKILL / "references" / "what-it-checks.md").read_text(encoding="utf-8")
        self.assertNotIn("Does not fit", ref)
        self.assertNotIn("does not fit", ref)
        self.assertIn("ig-reel", ref)
        self.assertNotIn("Pierre", ref)
        self.assertNotIn("/Users/", ref)


if __name__ == "__main__":
    unittest.main()
