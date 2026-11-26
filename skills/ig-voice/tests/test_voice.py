"""voice.py: the profile, the automatic fixes, the rewrite flags, the least-like-you ranking and the
command line. Offline, made-up text only. Run: python3 -m unittest discover ig-voice/tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPT = SKILL / "scripts" / "voice.py"
sys.path.insert(0, str(SCRIPT.parent))
import voice  # noqa: E402

# A made-up creator: short sentences, always contracts, talks as "I", no emoji, no em dashes,
# straight quotes, ends on "comment X", says "honestly" and "the boring part" a lot.
SAMPLES = [
    "I tried meal prep for a month. Honestly, the boring part was the shopping.\n"
    "So I made a list I reuse every week. It's on my fridge.\nComment LIST and I'll send it.",
    "Three things I'd tell my younger self about money. Don't buy the car. Keep a buffer.\n"
    "Honestly, the boring part is what works. Comment MONEY and I'll send my sheet.",
    "I don't plan my week on Sunday anymore. I do it Friday, before I'm tired.\n"
    "Honestly, the boring part is the habit. Comment PLAN and I'll send the template.",
    "My phone was eating my mornings. I moved the charger to the kitchen.\n"
    "It's a dumb fix but it's worked for six weeks. Comment PHONE if you want the setup.",
    "I can't cook, so I learned five dinners and stopped there. That's it.\n"
    "Honestly, the boring part is repeating them. Comment DINNERS and I'll send the list.",
    "You don't need a new app to read more. I read ten pages before bed.\n"
    "Honestly, the boring part is the only part. Comment READ and I'll send my list.",
]


def profile():
    return voice.build_profile(SAMPLES)


class Cleaning(unittest.TestCase):
    def test_invisible_characters_go_but_emoji_joiners_stay(self):
        family = "\U0001F468‍\U0001F469‍\U0001F467"
        text = f"Hello​ world﻿ and friends {family} ok‍then"
        out, changes = voice.clean(text)
        self.assertEqual(out, f"Hello world and friends {family} okthen")
        whats = " ".join(c["what"] for c in changes)
        self.assertIn("zero-width space", whats)
        self.assertIn("zero-width joiner", whats)
        self.assertIn("special spaces", whats)

    def test_curly_quotes_and_ellipsis_without_profile(self):
        out, _ = voice.clean("“Wait…” she said. It’s fine.")
        self.assertEqual(out, '"Wait..." she said. It\'s fine.')

    def test_curly_quotes_kept_for_a_creator_who_uses_them(self):
        prof = voice.build_profile(["I’m in. It’s “done”."] * 5)
        out, _ = voice.clean("It’s fine.", prof)
        self.assertEqual(out, "It’s fine.")

    def test_dashes(self):
        out, changes = voice.clean("It isn't a tool — it's a habit.\nPages 5–10 matter—\n— a list item")
        self.assertEqual(out, "It isn't a tool, it's a habit.\nPages 5-10 matter...\n- a list item")
        self.assertTrue(any("dashes" in c["what"] for c in changes))

    def test_dash_becomes_spaced_hyphen_for_someone_who_types_one(self):
        prof = voice.build_profile(["I tried it - it worked. Then I stopped."] * 5)
        out, _ = voice.clean("Simple fix — move the charger.", prof)
        self.assertEqual(out, "Simple fix - move the charger.")

    def test_em_dash_kept_for_a_creator_who_uses_it(self):
        prof = voice.build_profile(["I tried it—and it worked. Then I stopped."] * 5)
        out, _ = voice.clean("Simple fix—move the charger.", prof)
        self.assertIn("—", out)

    def test_markdown_markers_removed_hashtags_kept(self):
        out, _ = voice.clean("# Title\n**Bold** and *soft* and `code`.\n#fitness #food 5 * 3")
        self.assertEqual(out, "Title\nBold and soft and code.\n#fitness #food 5 * 3")
        kept, _ = voice.clean("**Bold**", keep_markdown=True)
        self.assertEqual(kept, "**Bold**")


class Profile(unittest.TestCase):
    def test_measures(self):
        p = profile()
        self.assertEqual(p["samples"], 6)
        self.assertEqual(p["contraction_share"], 1.0)
        self.assertGreater(p["per_100_words"]["I"], p["per_100_words"]["we"])
        self.assertEqual(p["emoji_per_sample"], 0)
        self.assertEqual(p["punctuation"]["em_dash"], 0)
        self.assertEqual(p["closers"].get("call to action"), 6)
        self.assertEqual(p["openers"].get("I"), 4)
        self.assertLess(p["sentence_words"]["median"], 10)
        self.assertIn("honestly", p["signature_words"])
        self.assertTrue(any("boring part" in ph for ph in p["signature_phrases"]))

    def test_split_and_frontmatter(self):
        text = "---\ntitle: x\ntags: [a]\n---\nFirst post here.\n---\nSecond post here.\n"
        self.assertEqual(voice.split_samples(text), ["First post here.", "Second post here."])

    def test_profile_round_trips_through_markdown(self):
        p = profile()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "voice.md"
            path.write_text(voice.profile_markdown(p))
            self.assertEqual(voice.load_profile(path), p)
            self.assertIn("## Summary", path.read_text())

    def test_profile_path_order(self):
        old = dict(os.environ)
        try:
            os.environ["IG_VOICE_PROFILE"] = "/x/env.md"
            self.assertEqual(str(voice.profile_path()), "/x/env.md")
            self.assertEqual(str(voice.profile_path("/x/arg.md")), "/x/arg.md")
            del os.environ["IG_VOICE_PROFILE"]
            os.environ["XDG_CONFIG_HOME"] = "/x/cfg"
            self.assertEqual(str(voice.profile_path()), "/x/cfg/ig-voice/voice.md")
        finally:
            os.environ.clear()
            os.environ.update(old)


class RewriteFlags(unittest.TestCase):
    def flagged(self, text, prof=None):
        res = voice.check(text, prof)
        return {r["line"]: " ".join(r["reasons"]) for r in res["rewrite"]}

    def test_shapes(self):
        text = ("It's not just a planner, it's a coach.\n"
                "The result? I sleep more.\n"
                "Here's the truth: nobody reads the manual.\n"
                "Fast. Cheap. Done.\n"
                "No apps. No timers. Just a notebook.\n"
                "This isn't a diet. It's a routine.\n"
                "Whether you're busy or not, this works.")
        f = self.flagged(text)
        self.assertIn("contrast frame", f[1])
        self.assertIn("set-up question", f[2])
        self.assertIn("colon reveal", f[3])
        self.assertIn("one- or two-word", f[4])
        self.assertIn("No X. No Y. Just Z.", f[5])
        self.assertIn("two-step contrast", f[6])
        self.assertIn("Whether you're", f[7])

    def test_stock_phrases(self):
        f = self.flagged("In today's fast-paced world, this is a game-changer.\nLet's dive in.\nLet that sink in.")
        self.assertIn("stock opener", f[1])
        self.assertIn("hype word", f[1])
        self.assertIn("stock opener", f[2])
        self.assertIn("stock closer", f[3])

    def test_a_phrase_the_creator_uses_is_not_flagged_for_them(self):
        prof = voice.build_profile([s + " Here's the thing, I'm lazy." for s in SAMPLES])
        self.assertTrue(self.flagged("Here's the thing, it works."))
        self.assertFalse(self.flagged("Here's the thing, it works.", prof))

    def test_lists_of_three_depend_on_the_creator(self):
        text = ("I eat eggs, rice and beans.\nI walk, read and sleep.\nI save, spend and give.\n"
                "That's the whole week, honestly.")
        self.assertTrue(self.flagged(text))
        listy = voice.build_profile(["I like tea, toast and jam. I run, swim and bike. I cook, clean and rest."] * 5)
        self.assertFalse(self.flagged(text, listy))

    def test_plain_human_text_is_not_flagged(self):
        text = "I moved my charger to the kitchen. Now I read before bed instead. Comment READ and I'll send my list."
        res = voice.check(text, profile())
        self.assertEqual(res["rewrite"], [])
        self.assertEqual(res["unlike_you"], [])


class LeastLikeYou(unittest.TestCase):
    def test_ranks_lines_far_from_the_profile(self):
        draft = ("I moved the charger. It worked.\n"
                 "We utilize a comprehensive approach to ensure that you do not lose momentum; "
                 "consistency is what ultimately determines long-term outcomes for individuals like you.\n"
                 "Comment PLAN and I'll send it.")
        res = voice.check(draft, profile(), kind="caption")
        top = res["unlike_you"][0]
        self.assertEqual(top["line"], 2)
        reasons = " ".join(top["reasons"])
        for bit in ('"utilize"', '"do not"', "semicolon", "words; your sentences run", '"we/our"'):
            self.assertIn(bit, reasons)
        self.assertNotIn(1, [r["line"] for r in res["unlike_you"]])

    def test_whole_draft_notes(self):
        draft = ("\U0001F680 Fast setup\n\U0001F4A1 Smart tips\n✅ No stress\n"
                 "Do you want to know more? Let me know below?\n#a #b #c #d #e")
        notes = " ".join(voice.check(draft, profile())["draft"])
        self.assertIn("emoji bullet", notes)
        self.assertIn("hashtags", notes)
        self.assertIn("Ends with a question", notes)

    def test_dm_skips_post_level_notes(self):
        notes = voice.check("Do you want the list? I can send it later?", profile(), kind="dm")["draft"]
        self.assertEqual(notes, [])

    def test_without_profile_still_reports(self):
        res = voice.check("We utilize tools to ensure you do not miss anything.")
        self.assertFalse(res["profile"])
        self.assertTrue(res["unlike_you"])
        report = voice.render(res, "none")
        self.assertIn("No voice profile", report)
        self.assertIn("Other lines to look at", report)


# The same made-up creator, now ending every caption with a standard footer: a separator line
# with an em dash, a follow line and a line of hashtags. Their own sentences never use a dash.
FOOTER = "\n\n—\nFollow @made.up.creator for more\n"
TAGS = ["#mealprep #budget", "#money #savings", "#planning", "#habits #phone", "#cooking", "#reading #books"]
FOOTED = [s + FOOTER + t for s, t in zip(SAMPLES, TAGS)]


class Footer(unittest.TestCase):
    """End-to-end test: a repeated footer was learned as voice, or stripped and then every hashtag flagged."""

    def test_footer_recorded_apart_from_voice(self):
        p = voice.build_profile(FOOTED)
        self.assertEqual(p["footer"]["samples_with_footer"], 6)
        self.assertEqual(p["footer"]["lines"], ["—", "Follow @made.up.creator for more", "(a line of hashtags)"])
        self.assertEqual(p["punctuation"]["em_dash"], 0)  # the separator is not their punctuation
        self.assertFalse(any("follow" in ph or "creator" in ph for ph in p["signature_phrases"]))
        self.assertNotIn("follow", p["signature_words"])
        self.assertEqual(p["closers"].get("call to action"), 6)  # still their own last sentence
        self.assertGreater(p["hashtags_per_sample"], 0)  # the hashtag habit is kept
        summary = voice.describe(p)
        self.assertIn("never an em dash", summary)
        self.assertIn("Footer: the same closing block in 6 of 6", summary)

    def test_draft_ending_with_the_footer_is_accepted(self):
        p = voice.build_profile(FOOTED)
        draft = "I stopped buying lunch out. It's saved me a lot.\nComment LUNCH and I'll send the list." \
                + FOOTER + "#lunch #budget"
        res = voice.check(draft, p)
        self.assertTrue(res["cleaned"].endswith(FOOTER + "#lunch #budget"))  # em dash kept in the footer
        self.assertEqual(res["fixed"], [])
        self.assertEqual(res["footer"], "—\nFollow @made.up.creator for more\n#lunch #budget")
        notes = " ".join(res["draft"])
        self.assertNotIn("hashtags", notes)
        self.assertNotIn("Ends with a statement", notes)
        self.assertIn("Ends with your usual footer", voice.render(res, "x"))

    def test_dash_in_the_body_is_still_fixed(self):
        p = voice.build_profile(FOOTED)
        res = voice.check("I cook twice a week — that's it.\nComment COOK." + FOOTER + "#food", p)
        self.assertIn("I cook twice a week, that's it.", res["cleaned"])
        self.assertIn("\n—\n", res["cleaned"])

    def test_no_footer_when_endings_differ(self):
        p = profile()
        self.assertEqual(p["footer"]["lines"], [])
        self.assertIn("Footer: none repeated", voice.describe(p))


class TopicPhrases(unittest.TestCase):
    """End-to-end test: a topic phrase from 2 posts on the same subject was called a repeated phrase."""

    def test_two_posts_on_one_subject_are_topic_not_voice(self):
        samples = [
            "I built a claude code skill that reads my calendar. It took an hour.",
            "My second claude code skill reads my calendar invites and drafts replies.",
            "I walk every morning before coffee. It clears my head.",
            "I quit sugar for a month and slept better.",
            "Garden update: the tomatoes finally came in after weeks of rain.",
        ]
        p = voice.build_profile(samples)
        self.assertFalse(any("claude code" in ph for ph in p["signature_phrases"]), p["signature_phrases"])

    def test_three_posts_make_a_habit(self):
        self.assertTrue(any("boring part" in ph for ph in profile()["signature_phrases"]))

    def test_two_posts_on_different_subjects_still_count(self):
        grams = [{"to be fair"}, {"to be fair"}, set()]
        content = [{"tomatoes", "garden", "rain"}, {"crypto", "taxes", "spreadsheet"}, set()]
        self.assertTrue(voice.repeated_habit("to be fair", 2, grams, content))
        content[1] = {"tomatoes", "garden", "rain"}
        self.assertFalse(voice.repeated_habit("to be fair", 2, grams, content))


class WholeDraftEveryKind(unittest.TestCase):
    """End-to-end test: a --kind script report had no Whole draft section."""

    def test_script_report_has_whole_draft(self):
        script = "I moved my charger to the kitchen. Now my mornings are mine. Comment PHONE for the setup."
        for kind in voice.KINDS:
            for prof in (profile(), None):
                report = voice.render(voice.check(script, prof, kind=kind), "x")
                self.assertIn("## Whole draft", report, (kind, bool(prof)))
        report = voice.render(voice.check(script, profile(), kind="script"), "x")
        self.assertIn("seconds spoken", report)


class CommandLine(unittest.TestCase):
    def run_cli(self, *args, env=None, stdin=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                              env=env, input=stdin)

    def test_learn_check_show(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            env = dict(os.environ, IG_VOICE_PROFILE=str(tmp / "cfg" / "voice.md"))
            (tmp / "a.txt").write_text("\n---\n".join(SAMPLES[:3]))
            (tmp / "b.txt").write_text("\n---\n".join(SAMPLES[3:5]))
            r = self.run_cli("learn", str(tmp / "a.txt"), str(tmp / "b.txt"), env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("from 5 samples", r.stdout)
            (tmp / "c.txt").write_text(SAMPLES[5])
            r = self.run_cli("learn", "--add", str(tmp / "c.txt"), env=env)
            self.assertIn("from 6 samples", r.stdout)
            self.assertEqual(len(list((tmp / "cfg" / "samples").glob("*.txt"))), 6)

            draft = tmp / "draft.txt"
            draft.write_text("It’s not just a list — it’s a system.​\nComment LIST and I will send it!")
            r = self.run_cli("check", str(draft), "-o", str(tmp / "clean.txt"), "--report", str(tmp / "r.md"),
                             env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((tmp / "clean.txt").read_text(),
                             "It's not just a list, it's a system.\nComment LIST and I will send it!")
            report = (tmp / "r.md").read_text()
            self.assertIn("Checked against your voice profile", report)
            self.assertIn("contrast frame", report)
            self.assertIn('"i will": you write', report)
            self.assertNotIn("detector", report)  # no closing disclaimer since 2026-11-26
            self.assertNotIn("## Cleaned text", report)

            r = self.run_cli("check", "-", "--json", env=env, stdin="Great question! Here's a caption.")
            data = json.loads(r.stdout)
            self.assertIn("assistant voice", " ".join(data["rewrite"][0]["reasons"]))

            r = self.run_cli("check", str(draft), "--strict", env=env)
            self.assertEqual(r.returncode, 2)
            self.assertIn("## Cleaned text", r.stdout)

            r = self.run_cli("show", env=env)
            self.assertIn("Built from 6 samples", r.stdout)

    def test_json_honours_strict_and_report(self):
        """End-to-end test: --strict exited 2, --strict --json exited 0 and wrote no report."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            env = dict(os.environ, IG_VOICE_PROFILE=str(tmp / "none.md"))
            draft = tmp / "draft.txt"
            draft.write_text("It's not just a list, it's a system. Great question!")
            plain = self.run_cli("check", str(draft), "--strict", env=env)
            js = self.run_cli("check", str(draft), "--strict", "--json", "--report", str(tmp / "r.md"), env=env)
            self.assertEqual(plain.returncode, 2)
            self.assertEqual(js.returncode, 2, js.stderr)
            self.assertTrue(json.loads(js.stdout)["rewrite"])
            self.assertIn("## Whole draft", (tmp / "r.md").read_text())
            ok = tmp / "ok.txt"
            ok.write_text("I moved my charger. It worked.")
            self.assertEqual(self.run_cli("check", str(ok), "--strict", "--json", env=env).returncode, 0)

    def test_no_profile_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, IG_VOICE_PROFILE=str(Path(tmp) / "none.md"))
            r = self.run_cli("check", "-", env=env, stdin="Just a normal line I wrote.")
            self.assertIn("No voice profile", r.stdout)
            self.assertIn("No profile at", self.run_cli("show", env=env).stdout)


SEPARATOR_FORMS = ["---", "—", "–", "___", "* * *", "----"]


class SeparatorForms(unittest.TestCase):
    """End-to-end test: a "---" footer separator split each sample file in two, so 5 captions
    became 10 samples, no footer was found and the footer's words were learned as voice."""

    def learn_files(self, sep, tmp):
        for k, (s, t) in enumerate(zip(SAMPLES, TAGS)):
            (tmp / f"{k}.txt").write_text(s + "\n\n" + sep + "\nFollow @made.up.creator to unlock it\n" + t)
        return voice.build_profile(voice.read_inputs([str(tmp)]))

    def test_every_separator_learns_the_same(self):
        for sep in SEPARATOR_FORMS:
            with tempfile.TemporaryDirectory() as tmp:
                p = self.learn_files(sep, Path(tmp))
            self.assertEqual(p["samples"], 6, sep)
            self.assertEqual(p["footer"]["samples_with_footer"], 6, sep)
            self.assertEqual(p["footer"]["keys"], ["#hashtags", "follow @made.up.creator to unlock it", "sep"], sep)
            self.assertFalse(any("unlock" in ph or "follow" in ph for ph in p["signature_phrases"]), sep)
            self.assertNotIn("unlock", p["signature_words"], sep)
            self.assertIn("Footer: the same closing block in 6 of 6", voice.describe(p), sep)

    def test_separators_mixed_across_posts_are_one_footer(self):
        mixed = [s + "\n\n" + SEPARATOR_FORMS[k % len(SEPARATOR_FORMS)] + "\nFollow @made.up.creator\n" + t
                 for k, (s, t) in enumerate(zip(SAMPLES, TAGS))]
        p = voice.build_profile(mixed)
        self.assertIn("sep", p["footer"]["keys"])
        self.assertEqual(p["footer"]["samples_with_footer"], 6)

    def test_one_file_with_several_footed_samples(self):
        text = "\n---\n".join(s + "\n---\nFollow @made.up.creator\n" + t for s, t in zip(SAMPLES, TAGS))
        parts = voice.split_samples(text)
        self.assertEqual(len(parts), 6)
        self.assertTrue(parts[0].endswith("---\nFollow @made.up.creator\n#mealprep #budget"))
        self.assertEqual(len(voice.split_samples("\n---\n".join(SAMPLES))), 6)  # plain separators still split

    def test_draft_footer_with_another_separator_is_recognised(self):
        p = voice.build_profile(FOOTED)  # learned with an em dash
        draft = "I stopped buying lunch out. It's saved me a lot.\nComment LUNCH and I'll send the list." \
                "\n\n---\nFollow @made.up.creator for more\n#lunch"
        res = voice.check(draft, p)
        self.assertEqual(res["footer"], "---\nFollow @made.up.creator for more\n#lunch")
        self.assertEqual(res["footer_status"], "usual")

    def test_profile_from_an_older_version_still_matches(self):
        p = voice.build_profile(FOOTED)
        p["footer"]["keys"] = [("sep:—" if k == "sep" else k) for k in p["footer"]["keys"]]
        res = voice.check("I cook twice a week. Comment COOK." + FOOTER + "#food", p)
        self.assertEqual(res["footer_status"], "usual")


class FooterWording(unittest.TestCase):
    """End-to-end test: "Ends with your usual footer" was said for a draft ending in hashtags only."""

    DRAFT = "I stopped buying lunch out. It's saved me a lot.\nComment LUNCH and I'll send the list."

    def test_hashtags_alone_are_not_the_usual_footer(self):
        res = voice.check(self.DRAFT + "\n\n#lunch #budget", voice.build_profile(FOOTED))
        self.assertEqual(res["footer_status"], "hashtags")
        self.assertNotIn("Ends with your usual footer", res["draft_summary"])
        self.assertIn("Ends with a line of hashtags", res["draft_summary"])
        self.assertIn("usual footer is not there", res["draft_summary"])

    def test_part_of_the_footer_names_what_is_missing(self):
        res = voice.check(self.DRAFT + "\n\n—\n#lunch", voice.build_profile(FOOTED))
        self.assertEqual(res["footer_status"], "partial")
        self.assertIn('without "follow @made.up.creator for more"', res["draft_summary"])

    def test_whole_footer_is_the_usual_footer(self):
        res = voice.check(self.DRAFT + FOOTER + "#lunch", voice.build_profile(FOOTED))
        self.assertEqual(res["footer_status"], "usual")
        self.assertIn("Ends with your usual footer", res["draft_summary"])


def _sibling(skill, script):
    """Import a script from a sibling skill in the same pack, or None when it is not installed."""
    import importlib.util
    path = SKILL.parent / skill / "scripts" / script
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(skill.replace("-", "_") + "_" + path.stem, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SpokenLength(unittest.TestCase):
    """End-to-end test: --kind script said "about 35 seconds" where ig-reel and ig-script said
    28.8, mostly because a {{placeholder}} counted as every word inside it."""

    LINES = [
        "I don't charge $18,000 for a one-off job.",
        "It takes {{how long it takes}} hours, not 2.5 days.",
        "1. Open the {{name of the app you use}} and type 30% off.",
        "L4: Tag @made.up.creator, it's 2k people now — honestly.",
    ]

    def test_same_count_as_reel_and_timeline(self):
        for skill, script in (("ig-reel", "reel.py"), ("ig-script", "timeline.py")):
            mod = _sibling(skill, script)
            if mod is None:
                self.skipTest(f"{skill} not next to ig-voice")
            for line in self.LINES:
                plain = voice.LEAD_NUMBER.sub("", line).strip()
                self.assertEqual(voice.spoken_words(plain), mod.spoken_words(plain), (skill, line))

    def test_placeholder_is_one_word(self):
        text = "\n".join(self.LINES[:2])
        self.assertEqual(voice.script_word_count(text), 17)  # what reel.py and timeline.py say
        res = voice.check(text, None, kind="script")
        self.assertIn("17 words", res["draft_summary"])
        self.assertIn("about 7 seconds spoken at 2.5 words a second", res["draft_summary"])

    def test_long_placeholder_does_not_make_a_long_sentence(self):
        line = "So I open {{the exact name of the invoicing app and the menu where the export lives}} first."
        res = voice.check(line + "\nComment LIST and I'll send it.", profile(), kind="script")
        self.assertFalse(any("words; your sentences run" in r for u in res["unlike_you"] for r in u["reasons"]))


class Packaging(unittest.TestCase):
    def test_skill_md_names_the_location_variables(self):
        text = (SKILL / "SKILL.md").read_text()
        for bit in ("IG_VOICE_PROFILE", "XDG_CONFIG_HOME", "--profile", "test run"):
            self.assertIn(bit, text)

    def test_frontmatter_and_metadata(self):
        text = (SKILL / "SKILL.md").read_text()
        self.assertTrue(text.startswith("---\nname: ig-voice\n"))
        self.assertIn("argument-hint:", text.split("\n---\n")[0])
        meta = (SKILL / "agents" / "openai.yaml").read_text()
        short = meta.split('short_description: "')[1].split('"')[0]
        self.assertTrue(25 <= len(short) <= 64, short)
        self.assertIn("$ig-voice", meta)

    def test_no_overclaims_and_standard_library_only(self):
        for f in SKILL.rglob("*"):
            if f.is_file() and f.suffix in (".md", ".py", ".yaml") and f.name != "test_voice.py":
                # SKILL.md names the claim only to forbid it
                body = f.read_text().lower().replace('never tell anyone the result is "undetectable"', "")
                self.assertNotIn("undetectable", body, f)
                self.assertNotIn("bypass", body, f)
        imports = (SCRIPT.read_text() + (SCRIPT.parent / "patterns.py").read_text())
        for mod in ("requests", "urllib", "socket", "http"):
            self.assertNotIn(f"import {mod}", imports)


class SharedTells(unittest.TestCase):
    """tells.py is shared with the humanize skill as an identical copy."""

    def test_matches_humanize_copy(self):
        other = SKILL.parent / "humanize" / "scripts" / "tells.py"
        if not other.exists():
            self.skipTest("humanize is not beside this skill")
        self.assertEqual((SKILL / "scripts" / "tells.py").read_text(), other.read_text(),
                         "tells.py differs from humanize's copy: change both")

    def test_strong_shared_tells_are_listed(self):
        for line in ("Studies show most creators quit.", "I'm not saying you need more followers.",
                     "The launch was huge, highlighting how much people wanted it.",
                     "As of my last update, it was free."):
            with self.subTest(line=line):
                res = voice.check(line, None, "caption")
                self.assertTrue(res["rewrite"], line)

    def test_a_shared_tell_the_creator_uses_is_not_listed(self):
        samples = [s + " The real question is time." for s in SAMPLES]
        prof = voice.build_profile(samples)
        res = voice.check("The real question is money.", prof, "caption")
        self.assertFalse(any("hidden truth" in r for item in res["rewrite"] for r in item["reasons"]))
        self.assertTrue(voice.check("The real question is money.", None, "caption")["rewrite"])


if __name__ == "__main__":
    unittest.main()
