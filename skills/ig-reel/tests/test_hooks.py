"""hooks.py and references/hooks.json: the 26 formulas, matching winners to them, and the
weak-hook filter. Offline, made-up data only. Run: python3 -m unittest discover ig-reel/tests"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPT = SKILL / "scripts" / "hooks.py"
sys.path.insert(0, str(SCRIPT.parent))
import hooks  # noqa: E402

FIELDS = ("id", "name", "move", "template", "example", "on_screen", "use_when", "source", "cues")


class Formulas(unittest.TestCase):
    def setUp(self):
        self.fs = hooks.load_formulas()

    def test_exactly_26(self):
        self.assertEqual(len(self.fs), 26)

    def test_skill_says_26(self):
        self.assertIn("26 hook formulas", (SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_every_formula_is_complete(self):
        for f in self.fs:
            for k in FIELDS:
                self.assertTrue(f.get(k), f"{f.get('id')}: missing {k}")
            self.assertIn(f["source"], ("research", "craft"))
            self.assertRegex(f["id"], r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_ids_names_and_examples_are_unique(self):
        for k in ("id", "name", "example", "on_screen"):
            vals = [f[k] for f in self.fs]
            self.assertEqual(len(vals), len(set(vals)), k)

    def test_cues_compile(self):
        for f in self.fs:
            for c in f["cues"]:
                re.compile(c)

    def test_both_sources_present(self):
        srcs = [f["source"] for f in self.fs]
        self.assertEqual(srcs.count("research") + srcs.count("craft"), 26)
        self.assertGreaterEqual(srcs.count("research"), 10)

    def test_on_screen_versions_are_short(self):
        for f in self.fs:
            self.assertLessEqual(len(hooks.words(f["on_screen"])), int(hooks.READ_SECONDS * hooks.READ_WPS), f["id"])

    def test_known_openings_match_their_formula(self):
        cases = {
            "Did the new app just kill the old one?": "the-swap",
            "You can now get a booking bot running in 5 minutes.": "done-in-minutes",
            "The bakery is giving out free bread, but only until Friday.": "free-with-a-date",
            "My AI read 400 emails for me while I slept.": "what-it-did-for-me",
            "Stop typing your address into checkout pages.": "stop-doing",
            "Your phone can't read receipts until you turn this on.": "cant-until-this",
            "Things your car can do, part 3: park itself.": "part-n",
        }
        for text, fid in cases.items():
            self.assertIn(fid, hooks.match_formulas(text, self.fs), text)

    def test_pick_weights_by_share_rate(self):
        ev = {"winners": [
            {"account": "a", "spoken_hook": "Did X just kill Y?", "text_hook": "", "shares_per_1k_views": 10.0, "age_days": 200},
            {"account": "b", "spoken_hook": "Free stuff until Friday", "text_hook": "", "shares_per_1k_views": 20.0, "age_days": 10},
            {"account": "c", "spoken_hook": "zzz qqq", "text_hook": "", "shares_per_1k_views": 5.0, "age_days": 10},
        ]}
        res = hooks.pick(ev, self.fs)
        self.assertEqual(res["backed"][0]["id"], "free-with-a-date")
        self.assertEqual(res["backed"][0]["weight"], 30.0)  # recent x1.5
        self.assertEqual([u["winner"].split()[0] for u in res["unmatched"]], ["@c"])


class Score(unittest.TestCase):
    def test_warm_up_is_weak(self):
        r = hooks.score_hook("Hey guys, today I want to talk about saving money.", "Saving money")
        self.assertIn("warm-up", r["weak"])

    def test_nothing_concrete_is_weak(self):
        r = hooks.score_hook("This changes everything about how you think.", "Big change")
        self.assertIn("nothing concrete", r["weak"])
        self.assertLess(r["score"], 50)

    def test_specificity_weighs_most(self):
        vague = hooks.score_hook("I found a better way to plan my week.", "x")
        exact = hooks.score_hook("I planned 14 meals for $38 on Sunday.", "x")
        self.assertGreater(exact["score"], vague["score"])
        spec = {c["check"]: c["of"] for c in exact["checks"]}
        self.assertEqual(max(spec, key=spec.get), "specific")

    def test_detail_after_three_seconds_counts_less(self):
        facts = hooks.load_facts("$400 vanished from my account.")
        early = hooks.score_hook("$400 vanished from my account and nobody told me why it happened.", "x", facts=facts)
        late = hooks.score_hook("Nobody told me why it happened, but money vanished from my account, $400.", "x",
                                facts=facts)
        e = next(c for c in early["checks"] if c["check"] == "specific")["points"]
        l = next(c for c in late["checks"] if c["check"] == "specific")["points"]
        self.assertGreater(e, l)

    def test_long_hook_loses_points_and_very_long_is_weak(self):
        short = hooks.score_hook("My oven caught fire at 6 PM.", "x")
        long = hooks.score_hook(" ".join(["word"] * 25) + " 5 dollars", "x")
        self.assertGreater(next(c for c in short["checks"] if c["check"].startswith("said"))["points"],
                           next(c for c in long["checks"] if c["check"].startswith("said"))["points"])
        self.assertIn("too long", long["weak"])

    def test_topic_check_only_with_topic_and_ignores_stopwords(self):
        r = hooks.score_hook("My oven caught fire at 6 PM.", "x")
        self.assertNotIn("topic early", [c["check"] for c in r["checks"]])
        miss = hooks.score_hook("And the thing for you is here.", "x", topic="and the for you smart oven")
        self.assertEqual(next(c for c in miss["checks"] if c["check"] == "topic early")["points"], 0)
        hit = hooks.score_hook("My oven caught fire at 6 PM.", "x", topic="smart oven alerts")
        self.assertEqual(next(c for c in hit["checks"] if c["check"] == "topic early")["points"], 10)

    def test_topic_early_uses_the_same_0_03_window_as_reel_check(self):
        # 7.5 words fit in 0:03 at 2.5 words a second; "invoice" is the 8th, so it is not heard.
        line = "3 hours every Friday. That's what one invoice skill saves."
        r = hooks.score_hook(line, "x", topic="invoice skill")
        topic = next(c for c in r["checks"] if c["check"] == "topic early")
        self.assertEqual(topic["points"], 0)
        heard = hooks.reel.words_heard_by([line], hooks.reel.HOOK_WINDOW, 2.5)
        self.assertEqual(heard, "3 hours every Friday That's what one")
        self.assertIn(heard, topic["note"])
        # A figure takes the time it takes to say: "$18,000" is three words.
        self.assertEqual(hooks.heard_by_window("$18,000 back in my bank account today"), 5)

    def test_detail_heard_after_0_03_is_not_early(self):
        facts = hooks.load_facts("Monday")
        r = hooks.score_hook("one two three four five six seven Monday", "x", facts=facts)
        self.assertEqual(next(c for c in r["checks"] if c["check"] == "specific")["points"], 20)

    def test_on_screen_warnings(self):
        r = hooks.score_hook("My oven caught fire at 6 PM.", "My oven caught fire at 6 PM.")
        self.assertTrue(any("word for word" in w for w in r["warnings"]))
        r = hooks.score_hook("My oven caught fire at 6 PM.", "one two three four five six seven eight nine ten")
        self.assertTrue(any("read in" in w for w in r["warnings"]))
        r = hooks.score_hook("My oven caught fire at 6 PM.", "")
        self.assertTrue(any("no on-screen" in w for w in r["warnings"]))
        facts = hooks.load_facts("My oven caught fire at 6 PM on a Tuesday.")
        self.assertEqual(hooks.score_hook("My oven caught fire at 6 PM.", "None", facts=facts)["warnings"], [])

    def test_score_is_out_of_100(self):
        for t in ("x", "My 3 kids ate 40 tacos on Friday at the Dodgers game.", "Hello there guys"):
            s = hooks.score_hook(t, "x", topic="tacos")["score"]
            self.assertTrue(0 <= s <= 100)

    def test_parse_candidates(self):
        text = "Formula: the-swap\nSpoken: A beat B for me.\nOn screen: A beat B\n\n1. Just this line\n"
        c = hooks.parse_candidates(text)
        self.assertEqual(len(c), 2)
        self.assertEqual(c[0], {"spoken": "A beat B for me.", "on_screen": "A beat B", "formula": "the-swap"})
        self.assertEqual(c[1]["spoken"], "Just this line")

    def test_sendable_to_and_other_notes_are_never_spoken(self):
        text = ("Spoken: My invoice skill saves 3 hours every Friday.\nOn screen: 3 hours back\nFormula: x\n"
                "Sendable to: An owner doing client invoices on Fridays, saying this might help.\n"
                "Why: backed by two winners\nNotes: keep it short\n- Sendable with: a friend\n")
        c = hooks.parse_candidates(text)
        self.assertEqual(c, [{"spoken": "My invoice skill saves 3 hours every Friday.",
                              "on_screen": "3 hours back", "formula": "x"}])
        plain = hooks.parse_candidates("Spoken: My invoice skill saves 3 hours every Friday.\nOn screen: x")
        self.assertEqual(hooks.score_hook(c[0]["spoken"], "x")["score"],
                         hooks.score_hook(plain[0]["spoken"], "x")["score"])
        # A colon inside a spoken line is still speech.
        self.assertEqual(hooks.parse_candidates("Here's the trick: send it Friday.")[0]["spoken"],
                         "Here's the trick: send it Friday.")


class CommandLine(unittest.TestCase):
    def run_cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], input=stdin,
                              capture_output=True, text=True)

    def test_list(self):
        out = self.run_cli("list", "--json")
        self.assertEqual(len(json.loads(out.stdout)), 26)

    def test_score_ranks_weak_last(self):
        text = ("Spoken: Hey guys, quick one today.\nOn screen: Quick one\n\n"
                "Spoken: My oven caught fire at 6 PM and my phone knew first.\nOn screen: Phone knew first\n")
        out = self.run_cli("score", "-", "--json", stdin=text)
        data = json.loads(out.stdout)
        self.assertEqual(data[0]["spoken"].split()[0], "My")
        self.assertTrue(data[-1]["weak"])
        human = self.run_cli("score", "-", stdin=text).stdout
        self.assertIn("does not predict", human)

    def test_score_bad_input(self):
        self.assertEqual(self.run_cli("score", "-", stdin="\n\n").returncode, 2)
        self.assertEqual(self.run_cli("score", "/no/such/file").returncode, 2)

    def test_pick_without_research_says_unproven(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.run_cli("pick", d)
            self.assertEqual(out.returncode, 0)
            self.assertIn("unproven", out.stdout)


class CleaningAndMatching(unittest.TestCase):
    """A winner's on-screen hook counts when its spoken hook is missing, and a formula
    matches only on its defining feature."""

    def setUp(self):
        self.fs = hooks.load_formulas()

    def ids(self, text):
        return hooks.match_formulas(text, self.fs)

    def test_clean_hook_drops_notes_and_missing_markers(self):
        c = hooks.clean_hook
        for missing in ("no captions", "None", "?", "", None, "None (word-by-word captions over a receipt)", "n/a"):
            self.assertEqual(c(missing), "", missing)
        self.assertEqual(c('"Did you know your kettle can text you [when] it boils" (typed headline)'),
                         "Did you know your kettle can text you when it boils")
        self.assertEqual(c('"40 burnt trays" banner (plus a progress bar)'), "40 burnt trays")
        self.assertEqual(c('"[I] built a thing that waters my plants..." (no track; frames)'),
                         "I built a thing that waters my plants")

    def test_text_hook_counts_when_spoken_hook_is_no_captions(self):
        ev = {"winners": [
            {"account": "quiet", "spoken_hook": "no captions", "text_hook": '"Did you know your oven has a hidden timer" (typed)',
             "shares_per_1k_views": 12.0, "age_days": 10},
            {"account": "loud", "spoken_hook": "no captions", "text_hook": "None (just a kitchen)",
             "shares_per_1k_views": 9.0, "age_days": 10},
        ]}
        res = hooks.pick(ev, self.fs)
        backed = {v["id"]: v for v in res["backed"]}
        self.assertIn("overlooked-tool", backed)
        self.assertTrue(backed["overlooked-tool"]["winners"][0].endswith("on screen"))
        self.assertEqual([u["winner"].split()[0] for u in res["unmatched"]], ["@loud"])
        self.assertEqual(res["unmatched"][0]["spoken_hook"], "(none)")

    def test_unmatched_shows_the_text_hook_too(self):
        ev = {"winners": [{"account": "a", "spoken_hook": "Look closer.", "text_hook": "THE KETTLE",
                           "shares_per_1k_views": 5.0, "age_days": 200}]}
        u = hooks.pick(ev, self.fs)["unmatched"][0]
        self.assertEqual((u["spoken_hook"], u["text_hook"]), ("Look closer.", "THE KETTLE"))

    def test_free_needs_a_deadline(self):
        self.assertIn("free-with-a-date", self.ids("The library is giving out free passes until Friday."))
        self.assertIn("free-with-a-date", self.ids("Ends Sunday: free coffee for every nurse."))
        for no_date in ("You can test it for free and see if it works.",
                        "This cost me $40 a month.",
                        "Claude can now test your idea on 100 customers for free."):
            self.assertNotIn("free-with-a-date", self.ids(no_date), no_date)

    def test_cues_need_their_defining_feature(self):
        negatives = {
            "cant-until-this": "I can't stand cold coffee.",
            "the-question-they-ask": "I asked my oven a question, and it answered?",
            "same-test-two": "I gave it my invoices.",
            "my-mistake": "You're holding it wrong.",
            "i-tested-it": "I used my phone for the shopping list.",
            "from-to": "I went from my desk to the kitchen.",
            "the-line-someone-said": "My dog asked for nothing.",
            "what-it-did-for-me": "My AI is great.",
        }
        for fid, text in negatives.items():
            self.assertNotIn(fid, self.ids(text), text)
        positives = {
            "cant-until-this": "Your kettle can now text you when it boils.",
            "the-question-they-ask": "How do you stop a toddler from flushing keys?",
            "same-test-two": "I gave both apps the same task.",
            "my-mistake": "For two years I was storing bread wrong, and it was my biggest mistake.",
            "i-tested-it": "I tested a paper planner for 30 days.",
            "from-to": "My grocery bill went from $180 to $95.",
            "from-to ": "4 hours to 15 minutes",
            "the-line-someone-said": "My client told me I was too cheap.",
            "hidden-shortcuts": "5 ways you didn't know your microwave can save you time.",
            "overlooked-tool": "Did you know your fridge has a holiday mode?",
        }
        for fid, text in positives.items():
            self.assertIn(fid.strip(), self.ids(text), text)

    def test_a_hook_that_fits_nothing_matches_nothing(self):
        self.assertEqual(self.ids("Someone built an agent whose only job is to find you customers."), [])


class FactsAndTopic(unittest.TestCase):
    """Specificity comes from the creator's own facts, never from the topic or an invented number."""

    TOPIC = "Claude Code skills for small business owners"

    def spec(self, r):
        return next(c for c in r["checks"] if c["check"] == "specific")["points"]

    def test_topic_and_niche_names_are_not_details(self):
        r = hooks.score_hook("Claude Code now does my invoices for my business.", "x", topic=self.TOPIC)
        self.assertEqual(self.spec(r), 0)
        self.assertIn("topic's own words", r["checks"][0]["note"])
        # Without --topic, the names the whole niche says still don't count.
        self.assertEqual(self.spec(hooks.score_hook("So ChatGPT and Claude Code now do it.", "x")), 0)
        # A real name of the creator's does.
        self.assertGreater(self.spec(hooks.score_hook("My client Dana got her Friday back.", "x")), 0)

    def test_invented_number_never_scores(self):
        facts = hooks.load_facts("I run a bakery. Invoices took 3 hours every Sunday. Now a skill does them in 12 minutes.")
        invented = hooks.score_hook("100 small business owners asked Claude the same question.", "100 owners asked",
                                    topic=self.TOPIC, facts=facts)
        true = hooks.score_hook("My bakery's invoices took 3 hours every Sunday. Now it's 12 minutes.",
                                "3 hours to 12 minutes", topic=self.TOPIC, facts=facts)
        self.assertTrue(any("not in your facts: 100" in w for w in invented["weak"]))
        self.assertTrue(any("on-screen number" in w for w in invented["weak"]))
        self.assertEqual(self.spec(invented), 0)
        self.assertEqual(self.spec(true), 40)
        self.assertFalse(true["weak"])
        self.assertGreater(true["score"], invented["score"])

    def test_without_facts_a_number_earns_nothing_and_says_so(self):
        r = hooks.score_hook("100 small business owners asked the same question.", "x", topic=self.TOPIC)
        self.assertEqual(self.spec(r), 0)
        self.assertTrue(any("--facts" in w for w in r["warnings"]))
        self.assertLess(r["score"], 60)

    def test_facts_match_figures_written_differently(self):
        facts = hooks.load_facts("It saved me $10,219 and three hours.")
        r = hooks.score_hook("$10219 and 3 hours, back.", "x", facts=facts)
        self.assertFalse(r["weak"], r)
        self.assertEqual(self.spec(r), 40)

    def test_placeholder_counts_but_is_not_ready(self):
        r = hooks.score_hook("{{N}} hours a week came back from one skill.", "{{N}} hours back", topic=self.TOPIC)
        self.assertGreater(self.spec(r), 0)
        self.assertEqual(r["to_fill"], ["{{N}}"])
        self.assertFalse(r["weak"])

    def test_sentence_starts_are_not_names(self):
        found = hooks.specifics("It took an hour. Now it's quick. That's the point.")
        self.assertEqual([x for x in found if x["kind"] == "name"], [])

    def test_cli_facts(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "facts.txt"
            f.write_text("My oven caught fire at 6 PM.", encoding="utf-8")
            text = "Spoken: 100 people burnt dinner at 6 PM.\nOn screen: 100 burnt dinners\n"
            out = subprocess.run([sys.executable, "-B", str(SCRIPT), "score", "-", "--facts", str(f)],
                                 input=text, capture_output=True, text=True)
            self.assertIn("WEAK (number not in your facts: 100", out.stdout)
            out = subprocess.run([sys.executable, "-B", str(SCRIPT), "score", "-", "--facts", "/no/such"],
                                 input=text, capture_output=True, text=True)
            self.assertEqual(out.returncode, 2)
            out = subprocess.run([sys.executable, "-B", str(SCRIPT), "score", "-"],
                                 input="Spoken: {{N}} burnt dinners at 6 PM.\nOn screen: {{N}} dinners\n",
                                 capture_output=True, text=True)
            self.assertIn("NOT READY until the creator fills: {{N}}", out.stdout)
            self.assertIn("no number earns points", out.stdout)


if __name__ == "__main__":
    unittest.main()
