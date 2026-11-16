"""Offline tests for scripts/score_profile.py. Run: python3 -m unittest discover ig-profile/tests"""

import copy
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPT = os.path.join(SKILL, "scripts", "score_profile.py")
sys.path.insert(0, os.path.dirname(SCRIPT))

import score_profile as sp  # noqa: E402

RUBRIC = sp.load_rubric()
IDS = [c["id"] for _, c in sp.criteria(RUBRIC)]
POINTS = {c["id"]: c["points"] for _, c in sp.criteria(RUBRIC)}


def all_rated(value):
    return {"ratings": {i: value for i in IDS}}


def run(*args, stdin=None):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, input=stdin)


class Rubric(unittest.TestCase):
    def test_total_is_100(self):
        self.assertEqual(sum(POINTS.values()), 100)

    def test_every_platform_criterion_has_a_known_source(self):
        known = sp.source_ids()
        for _, c in sp.criteria(RUBRIC):
            if c["basis"] == "platform":
                self.assertTrue(c["sources"], c["id"])
            for s in c["sources"]:
                self.assertIn(s, known, c["id"])

    def test_both_bases_used(self):
        bases = {c["basis"] for _, c in sp.criteria(RUBRIC)}
        self.assertEqual(bases, {"platform", "judgement"})

    def broken(self, mutate):
        r = copy.deepcopy(RUBRIC)
        mutate(r)
        with self.assertRaises(sp.RubricError) as cm:
            sp.validate_rubric(r, sp.source_ids())
        return str(cm.exception)

    def test_wrong_total_is_refused(self):
        msg = self.broken(lambda r: r["parts"][0]["criteria"][0].__setitem__("points", 9))
        self.assertIn("add to 101", msg)

    def test_unknown_source_is_refused(self):
        msg = self.broken(lambda r: r["parts"][0]["criteria"][0].__setitem__("sources", ["nowhere"]))
        self.assertIn("nowhere", msg)

    def test_platform_without_source_is_refused(self):
        msg = self.broken(lambda r: r["parts"][0]["criteria"][0].__setitem__("sources", []))
        self.assertIn("needs at least one source", msg)

    def test_duplicate_id_is_refused(self):
        def dup(r):
            r["parts"][0]["criteria"][1]["id"] = r["parts"][0]["criteria"][0]["id"]
        self.assertIn("duplicate", self.broken(dup))

    def test_bad_basis_is_refused(self):
        msg = self.broken(lambda r: r["parts"][0]["criteria"][0].__setitem__("basis", "vibes"))
        self.assertIn("basis", msg)

    def test_cli_refuses_broken_rubric(self):
        r = copy.deepcopy(RUBRIC)
        r["parts"][0]["criteria"][0]["points"] = 1
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(r, f)
        try:
            p = run("--rubric", f.name, "rubric")
            self.assertEqual(p.returncode, 2)
            self.assertIn("not 100", p.stderr)
        finally:
            os.unlink(f.name)

    def test_rubric_command_prints_every_criterion(self):
        p = run("rubric")
        self.assertEqual(p.returncode, 0)
        for i in IDS:
            self.assertIn(i, p.stdout)


class Score(unittest.TestCase):
    def test_all_met_is_100(self):
        r = sp.score(RUBRIC, all_rated("met"))
        self.assertEqual(r["total"], 100)
        self.assertEqual(r["fix_first"], [])

    def test_all_missed_is_0(self):
        r = sp.score(RUBRIC, all_rated("missed"))
        self.assertEqual(r["total"], 0)
        self.assertEqual(len(r["fix_first"]), len(IDS))

    def test_all_partly_is_50(self):
        self.assertEqual(sp.score(RUBRIC, all_rated("partly"))["total"], 50)

    def test_numbers_accepted(self):
        self.assertEqual(sp.score(RUBRIC, all_rated(0.5))["total"], 50)

    def test_parts_add_to_total(self):
        ratings = all_rated("met")
        ratings["ratings"]["bio.who_for"] = {"rating": "missed", "reason": "a quote"}
        r = sp.score(RUBRIC, ratings)
        self.assertEqual(sum(p["earned"] for p in r["parts"]), r["total"])
        self.assertEqual(sum(p["max"] for p in r["parts"]), 100)
        self.assertEqual(r["total"], 100 - POINTS["bio.who_for"])

    def test_fix_first_orders_by_points_lost(self):
        ratings = all_rated("met")
        ratings["ratings"]["name.search_term"] = "missed"     # -8
        ratings["ratings"]["pinned.jobs"] = "partly"          # -3
        ratings["ratings"]["posting.recent_regular"] = "missed"  # -5
        r = sp.score(RUBRIC, ratings)
        self.assertEqual([x["id"] for x in r["fix_first"]],
                         ["name.search_term", "posting.recent_regular", "pinned.jobs"])

    def test_unseen_counts_zero_and_is_scaled_separately(self):
        ratings = all_rated("met")
        ratings["ratings"]["posting.recent_regular"] = "unseen"
        r = sp.score(RUBRIC, ratings)
        self.assertEqual(r["total"], 95)
        self.assertEqual(r["seen_max"], 95)
        self.assertEqual(r["scaled"], 100)
        self.assertEqual([x["id"] for x in r["unseen"]], ["posting.recent_regular"])
        self.assertNotIn("posting.recent_regular", [x["id"] for x in r["fix_first"]])

    def test_missing_rating_is_an_error(self):
        ratings = all_rated("met")
        del ratings["ratings"]["grid.covers_fit"]
        with self.assertRaises(ValueError) as cm:
            sp.score(RUBRIC, ratings)
        self.assertIn("grid.covers_fit", str(cm.exception))

    def test_unknown_id_is_an_error(self):
        ratings = all_rated("met")
        ratings["ratings"]["bio.vibe"] = "met"
        with self.assertRaises(ValueError):
            sp.score(RUBRIC, ratings)

    def test_bad_value_is_an_error(self):
        for bad in ("great", 0.7, True):
            ratings = all_rated("met")
            ratings["ratings"]["bio.proof"] = bad
            with self.assertRaises(ValueError):
                sp.score(RUBRIC, ratings)

    def test_bare_mapping_without_ratings_key(self):
        self.assertEqual(sp.score(RUBRIC, {i: "met" for i in IDS})["total"], 100)

    def test_render_shows_reason_and_order(self):
        ratings = all_rated("met")
        ratings["ratings"]["highlights.exist"] = {"rating": "missed", "reason": "no highlights"}
        out = sp.render_score(sp.score(RUBRIC, ratings))
        self.assertIn("Score: 97 / 100", out)
        self.assertIn("no highlights", out)
        self.assertIn("Fix first", out)

    def test_cli_score_and_json(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(all_rated("partly"), f)
        try:
            p = run("score", f.name)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("50 / 100", p.stdout)
            j = json.loads(run("score", f.name, "--json").stdout)
            self.assertEqual(j["total"], 50)
        finally:
            os.unlink(f.name)

    def test_cli_bad_ratings_exit_2(self):
        p = run("score", "-", stdin=json.dumps({"ratings": {"bio.proof": "met"}}))
        self.assertEqual(p.returncode, 2)
        self.assertIn("not rated", p.stderr)


def statuses(res, field):
    return [s for s, f, _ in res if f == field]


class Check(unittest.TestCase):
    TODAY = dt.date(2026, 11, 16)

    def check(self, profile, keywords=()):
        return sp.check_profile(profile, keywords, self.TODAY)

    def test_good_profile_has_no_fail_or_warn(self):
        res = self.check({
            "name": "Ana Ruiz | Meal prep for one",
            "handle": "anaruiz",
            "bio": "Cheap dinners for people who cook for one.\nSaved 400 readers $200 a month.\nFree 7-day plan below",
            "links": [{"url": "https://example.com/plan", "title": "Free 7-day plan"}],
            "highlights": ["Start here", "Recipes", "Results"],
            "pinned": ["intro", "best result", "plan"],
            "last_post": "2026-11-12",
        }, ["meal prep", "cook for one"])
        bad = [(s, f, m) for s, f, m in res if s in ("FAIL", "WARN")]
        self.assertEqual(bad, [])

    def test_bio_over_150_fails(self):
        res = self.check({"bio": "x" * 151})
        self.assertIn("FAIL", statuses(res, "bio"))

    def test_bio_at_150_passes(self):
        self.assertIn("PASS", statuses(self.check({"bio": "x" * 150}), "bio"))

    def test_emoji_double_count_warns(self):
        res = self.check({"bio": "x" * 149 + "\U0001F600"})
        self.assertIn("WARN", statuses(res, "bio"))
        self.assertNotIn("FAIL", statuses(res, "bio"))

    def test_url_in_bio_warns(self):
        res = self.check({"bio": "Recipes at example.com"})
        self.assertTrue(any("not clickable" in m for s, f, m in res))

    def test_fancy_letters_warn(self):
        res = self.check({"name": "\U0001D400\U0001D427\U0001D41A Ruiz", "bio": "hi"})
        self.assertIn("WARN", statuses(res, "name"))

    def test_name_repeating_handle_warns(self):
        res = self.check({"name": "ana_ruiz", "handle": "ana_ruiz"})
        self.assertTrue(any("repeats the handle" in m for _, _, m in res))

    def test_emoji_only_name_warns(self):
        res = self.check({"name": "✨\U0001F33F✨"})
        self.assertTrue(any("only emoji" in m for _, _, m in res))

    def test_long_name_warns_never_fails(self):
        st = statuses(self.check({"name": "A" * 40}), "name")
        self.assertIn("WARN", st)
        self.assertNotIn("FAIL", st)

    def test_handle_shape(self):
        self.assertIn("WARN", statuses(self.check({"handle": "ana_ruiz.92"}), "handle"))
        self.assertIn("FAIL", statuses(self.check({"handle": "ana ruiz!"}), "handle"))
        self.assertIn("PASS", statuses(self.check({"handle": "@anaruiz"}), "handle"))

    def test_link_counts(self):
        self.assertIn("FAIL", statuses(self.check({"links": ["a"] * 6}), "links"))
        self.assertIn("WARN", statuses(self.check({"links": []}), "links"))
        self.assertIn("PASS", statuses(self.check({"links": ["https://example.com"]}), "links"))

    def test_pin_counts(self):
        self.assertIn("FAIL", statuses(self.check({"pinned": [1, 2, 3, 4]}), "pinned"))
        self.assertIn("WARN", statuses(self.check({"pinned": []}), "pinned"))

    def test_emoji_highlight_titles_warn(self):
        res = self.check({"highlights": ["\U0001F4F8", "Recipes"]})
        self.assertIn("WARN", statuses(res, "highlights"))

    def test_keyword_only_as_hashtag_warns(self):
        res = self.check({"bio": "Dinners #mealprep"}, ["meal prep"])
        self.assertTrue(any("only a hashtag" in m for _, _, m in res))

    def test_keyword_in_name_counts(self):
        res = self.check({"name": "Ana | Meal Prep", "bio": "Dinners"}, ["meal prep"])
        self.assertTrue(any(s == "PASS" and "name" in m for s, f, m in res if f == "search words"))

    def test_posting_age(self):
        self.assertIn("PASS", statuses(self.check({"last_post": "2026-11-10"}), "posting"))
        self.assertIn("INFO", statuses(self.check({"last_post": "2026-10-25"}), "posting"))
        self.assertIn("WARN", statuses(self.check({"last_post": "2026-09-01T10:00:00Z"}), "posting"))

    def test_voice_profile_detected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("# Voice profile")
        old = os.environ.get("IG_VOICE_PROFILE")
        os.environ["IG_VOICE_PROFILE"] = f.name
        try:
            res = self.check({})
            self.assertTrue(any(f_ == "voice" and "found" in m for _, f_, m in res))
        finally:
            os.unlink(f.name)
            if old is None:
                del os.environ["IG_VOICE_PROFILE"]
            else:
                os.environ["IG_VOICE_PROFILE"] = old

    def test_cli_check_exit_codes(self):
        p = run("check", "-", stdin=json.dumps({"bio": "x" * 200}))
        self.assertEqual(p.returncode, 1)
        p = run("check", "-", "--keywords", "x", stdin=json.dumps({"bio": "x"}))
        self.assertEqual(p.returncode, 0, p.stderr)
        p = run("check", "-", stdin="not json")
        self.assertEqual(p.returncode, 2)


class PublicReady(unittest.TestCase):
    def test_no_personal_details_in_skill(self):
        # spelled backwards so this file does not trip its own check
        banned = tuple(w[::-1] for w in ("erreip", "hgabbas", "/sresu/", "ia.foor"))
        for root, _, files in os.walk(SKILL):
            if "__pycache__" in root:
                continue
            for name in files:
                with open(os.path.join(root, name), encoding="utf-8") as f:
                    text = f.read().lower()
                for b in banned:
                    self.assertNotIn(b, text, f"{b!r} in {name}")


if __name__ == "__main__":
    unittest.main()
