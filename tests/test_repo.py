"""The repo as a whole: eight skills, each in the shape the plugin hosts load, nothing private
in them, and the manifests pointing at them. Run from the repo root:
python3 -m unittest discover -s tests"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ["ig-research", "ig-reel", "ig-script", "ig-voice", "ig-caption", "ig-profile",
          "ig-engage", "ig-plan"]
PRIVATE = re.compile(r"pierre|psabbagh|/Users/|content-hub|ownhealth|roof\.ai|obsidian|"
                     r"repos/hq|op://|1password|claude-501", re.I)


class Skills(unittest.TestCase):
    def test_exactly_the_eight_skills(self):
        self.assertEqual(sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir()),
                         sorted(SKILLS))

    def test_each_skill_has_frontmatter_and_openai_yaml(self):
        for name in SKILLS:
            d = ROOT / "skills" / name
            text = (d / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith(f"---\nname: {name}\n"), name)
            self.assertIn("\ndescription: ", text.split("\n---", 2)[0], name)
            y = (d / "agents" / "openai.yaml").read_text(encoding="utf-8")
            self.assertIn(f"${name}", y, name)

    def test_nothing_private_in_any_skill(self):
        for p in (ROOT / "skills").rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                text = p.read_text(encoding="utf-8")
                for line in text.splitlines():
                    if PRIVATE.search(line):
                        # tests that assert a name is absent are the one allowed kind of hit
                        self.assertRegex(line, r"assertNotIn", f"{p.relative_to(ROOT)}: {line.strip()}")

    def test_ig_script_takes_a_pasted_script_or_a_file(self):
        text = (ROOT / "skills" / "ig-script" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("**Pasted**", text)
        self.assertIn("**A file path**", text)
        for gone in ("Coherence check:", "From Idea to Camera", "Ready to Record", "Instagram Reels/"):
            self.assertNotIn(gone, text)

    def test_ig_script_timeline_runs(self):
        lines = "I lost my first client in a week.\nHere's why.\nI never sent the follow-up.\n"
        out = subprocess.run([sys.executable, "-B", str(ROOT / "skills/ig-script/scripts/timeline.py"), "-"],
                             input=lines, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("0:03", out.stdout)


class Manifests(unittest.TestCase):
    def load(self, rel):
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))

    def test_claude_and_codex_agree(self):
        claude = self.load(".claude-plugin/plugin.json")
        codex = self.load(".codex-plugin/plugin.json")
        self.assertEqual(claude["name"], "ig-skills")
        for k in ("name", "version", "description", "license", "repository"):
            self.assertEqual(claude[k], codex[k], k)
        self.assertEqual(codex["skills"], "./skills/")

    def test_marketplaces_point_at_this_plugin(self):
        cm = self.load(".claude-plugin/marketplace.json")
        self.assertEqual(cm["name"], "ig-skills")
        self.assertEqual([(p["name"], p["source"]) for p in cm["plugins"]], [("ig-skills", "./")])
        am = self.load(".agents/plugins/marketplace.json")
        self.assertEqual([(p["name"], p["source"]["path"]) for p in am["plugins"]], [("ig-skills", "./")])

    def test_readme_install_commands_match_the_manifests(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for cmd in ("claude plugin marketplace add psabbagh/ig-skills",
                    "claude plugin install ig-skills@ig-skills",
                    "codex plugin marketplace add psabbagh/ig-skills",
                    "codex plugin add ig-skills@ig-skills"):
            self.assertIn(cmd, readme)
        self.assertTrue(readme.startswith("# IG Skills"))
        self.assertIn("To set it up, open Claude Code and paste this message", readme)
        self.assertIn("Install the IG Skills plugin from https://github.com/psabbagh/ig-skills", readme.split("## 1.")[0])


if __name__ == "__main__":
    unittest.main()
