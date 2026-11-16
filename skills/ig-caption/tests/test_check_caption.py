"""Offline tests for scripts/check_caption.py. Run: python3 -m unittest discover ig-caption/tests"""

import io
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "check_caption.py")
sys.path.insert(0, os.path.dirname(SCRIPT))

import check_caption as cc  # noqa: E402

GOOD = (
    "I cut my grocery bill by $212 a month with one spreadsheet.\n"
    "\n"
    "Meal planning on a budget works when the list is built from what you already own. "
    "The sheet sorts by aisle and flags what runs out first.\n"
    "\n"
    "Comment SHEET and I'll send you the template.\n"
    "\n"
    "#mealprep #budgeting"
)


def status(report, name):
    return next(r for r in report["results"] if r["check"] == name)["status"]


def detail(report, name):
    return next(r for r in report["results"] if r["check"] == name)["detail"]


class GoodCaption(unittest.TestCase):
    def test_passes_everything(self):
        r = cc.check(GOOD, fmt="post", keywords=["meal planning on a budget", "grocery bill"])
        self.assertEqual(r["failed"], 0, r["results"])
        for name in ("length", "first line", "call to action", "search terms", "hashtags", "links", "emoji"):
            self.assertEqual(status(r, name), "PASS", name)


class Length(unittest.TestCase):
    def test_over_limit_fails(self):
        r = cc.check("Price 1 thing. Comment YES. " + "a" * 2200)
        self.assertEqual(status(r, "length"), "FAIL")

    def test_limit_is_a_setting(self):
        r = cc.check("Price 1 thing. Comment YES. " + "a" * 100, max_chars=50)
        self.assertEqual(status(r, "length"), "FAIL")

    def test_emoji_counted_double_warns(self):
        text = "Price 1 thing. Comment YES. " + "a" * 2150 + "🔥" * 40
        r = cc.check(text, emoji_per_100_words=1000)
        self.assertEqual(status(r, "length"), "FAIL")
        text = "Price 1 thing. Comment YES. " + "a" * 2150 + " 🔥"
        r = cc.check(text, max_chars=len(text))
        self.assertEqual(status(r, "length"), "WARN")


class FirstLine(unittest.TestCase):
    def test_vague_opener_warns(self):
        r = cc.check("Here's what nobody tells you.\nComment YES.", keywords=[])
        self.assertEqual(status(r, "first line"), "WARN")

    def test_hashtag_first_fails(self):
        r = cc.check("#tips for you\nComment YES.")
        self.assertEqual(status(r, "first line"), "FAIL")

    def test_emoji_only_fails(self):
        r = cc.check("🔥🔥\nI saved 3 hours. Comment YES.")
        self.assertEqual(status(r, "first line"), "FAIL")

    def test_long_first_line_on_post_warns(self):
        first = "I tracked 41 coffee shops in Lisbon for a month and the cheapest flat white was not where anyone said it would be at all, which surprised me"
        r = cc.check(first + "\nComment LISBON.", fmt="post")
        self.assertEqual(status(r, "first line"), "WARN")
        self.assertIn("feed cut", next(x for x in r["results"] if x["check"] == "first line")["detail"])

    def test_reel_line_only_needs_to_fit_the_feed(self):
        line = "My phone kept locking between 3 sets, so I asked my AI to keep the screen on."
        r = cc.check(line + "\nComment GYM.", fmt="reel")
        self.assertTrue(r["reel_preview"]["cut"])
        self.assertEqual(status(r, "first line"), "PASS")

    def test_warning_keeps_capitals(self):
        r = cc.check("Here's what I found in 2024.\nComment YES.")
        detail = next(x for x in r["results"] if x["check"] == "first line")["detail"]
        self.assertIn("Here's", detail)

    def test_number_makes_it_concrete(self):
        r = cc.check("I sleep 9 hours now.\nComment SLEEP.")
        self.assertEqual(status(r, "first line"), "PASS")


class CallToAction(unittest.TestCase):
    def test_none_fails(self):
        r = cc.check("I sleep 9 hours now.")
        self.assertEqual(status(r, "call to action"), "FAIL")

    def test_two_fails(self):
        r = cc.check("I sleep 9 hours now.\nSave this for tonight.\nFollow for more.")
        self.assertEqual(status(r, "call to action"), "FAIL")

    def test_two_verbs_in_one_sentence_is_one_ask(self):
        r = cc.check("I sleep 9 hours now.\nComment SLEEP and I'll DM the plan, so drop a comment.")
        self.assertEqual(status(r, "call to action"), "PASS")


class SearchTerms(unittest.TestCase):
    def test_missing_fails(self):
        r = cc.check(GOOD, keywords=["sourdough starter"])
        self.assertEqual(status(r, "search terms"), "FAIL")

    def test_hashtag_only_fails(self):
        r = cc.check("I cut 3 costs.\nComment YES.\n#mealprep", keywords=["meal prep"])
        self.assertEqual(status(r, "search terms"), "FAIL")
        self.assertIn("only as a hashtag", detail(r, "search terms"))

    def test_case_and_spacing_ignored(self):
        r = cc.check("I cut 3 costs with Meal\n Planning.\nComment YES.", keywords=["meal planning"])
        self.assertEqual(status(r, "search terms"), "PASS")

    def test_no_keywords_warns(self):
        self.assertEqual(status(cc.check(GOOD), "search terms"), "WARN")

    def test_keywords_parsed_from_flags(self):
        self.assertEqual(cc.parse_keywords(["a, b", "c;d"]), ["a", "b", "c", "d"])


class Hashtags(unittest.TestCase):
    def test_six_fails_at_default_five(self):
        tags = " ".join(f"#t{i}" for i in range(6))
        r = cc.check("I cut 3 costs.\nComment YES.\n" + tags)
        self.assertEqual(status(r, "hashtags"), "FAIL")

    def test_limit_is_a_setting(self):
        tags = " ".join(f"#t{i}" for i in range(6))
        r = cc.check("I cut 3 costs.\nComment YES.\n" + tags, max_hashtags=30)
        self.assertEqual(status(r, "hashtags"), "PASS")

    def test_not_fooled_by_anchors_or_html_entities(self):
        r = cc.check("I ranked #1 in 2024 &#39; ok.\nComment YES.")
        self.assertEqual(len(cc.HASHTAG_RE.findall("x&#39;")), 0)
        self.assertEqual(status(r, "hashtags"), "PASS")

    def test_repeat_warns(self):
        r = cc.check("I cut 3 costs.\nComment YES.\n#Food #food")
        self.assertEqual(status(r, "hashtags"), "WARN")


class Links(unittest.TestCase):
    def test_url_fails(self):
        for t in ("see https://example.com/x", "go to www.example.org", "at mysite.com/sale"):
            r = cc.check("I cut 3 costs.\nComment YES.\n" + t)
            self.assertEqual(status(r, "links"), "FAIL", t)

    def test_allow_links(self):
        r = cc.check("I cut 3 costs.\nComment YES.\nhttps://example.com", allow_links=True)
        self.assertEqual(status(r, "links"), "WARN")

    def test_mentions_and_decimals_are_not_links(self):
        r = cc.check("I cut 3.5 costs with @some.body.\nComment YES.")
        self.assertEqual(status(r, "links"), "PASS")


class Emoji(unittest.TestCase):
    def test_dense_warns(self):
        r = cc.check("I cut 3 costs 🔥 today 💸 ok ✅ yes 🙌 go 🚀.\nComment YES.")
        self.assertEqual(status(r, "emoji"), "WARN")

    def test_run_warns(self):
        text = "I cut 3 costs " + "and more words here " * 30 + "🔥🔥🔥\nComment YES."
        r = cc.check(text)
        self.assertIn("in a row", next(x for x in r["results"] if x["check"] == "emoji")["detail"])

    def test_clusters_count_once(self):
        family = "👨‍👩‍👧"
        flag = "🇫🇷"
        thumbs = "👍🏽"
        self.assertEqual(len(cc.emoji_clusters(family + flag + thumbs)), 3)


class Preview(unittest.TestCase):
    def test_short_caption_not_cut(self):
        vis, cut = cc.preview("Short one.", "", 125, 2)
        self.assertEqual((vis, cut), ("Short one.", False))

    def test_line_break_ends_preview(self):
        vis, cut = cc.preview("one\ntwo\nthree", "", 125, 2)
        self.assertEqual((vis, cut), ("one\ntwo", True))

    def test_char_budget_cuts_on_word_and_counts_handle(self):
        vis, cut = cc.preview("alpha beta gamma delta", "me", 15, 2)
        self.assertTrue(cut)
        self.assertEqual(vis, "alpha beta")

    def test_box_shows_more(self):
        out = cc.box("Feed", "hello", True, "", 30)
        self.assertIn("hello... more", out)


class CommandLine(unittest.TestCase):
    def run_cli(self, text, *args):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(text)
        try:
            return subprocess.run([sys.executable, SCRIPT, f.name, *args], capture_output=True, text=True)
        finally:
            os.unlink(f.name)

    def test_exit_codes_and_copy_block(self):
        ok = self.run_cli(GOOD, "--format", "post", "--keywords", "meal planning on a budget")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("copy below this line", ok.stdout)
        self.assertIn("ready to post", ok.stdout)
        bad = self.run_cli("#x\n", "--max-hashtags", "0")
        self.assertEqual(bad.returncode, 1)

    def test_json(self):
        import json
        res = self.run_cli(GOOD, "--json", "--max-hashtags", "30")
        data = json.loads(res.stdout)
        self.assertEqual(data["settings"]["max_hashtags"], 30)

    def test_missing_file(self):
        res = subprocess.run([sys.executable, SCRIPT, "/nonexistent/caption.txt"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)


class Placeholders(unittest.TestCase):
    """End-to-end test: a caption with {{N}} left in it was called ready to post."""

    def test_double_brace_slots_fail(self):
        text = GOOD.replace("$212", "{{N}}").replace("the template", "{{the weekly job}}")
        r = cc.check(text, fmt="post")
        self.assertEqual(status(r, "placeholders"), "FAIL")
        self.assertIn("{{N}}", detail(r, "placeholders"))
        self.assertIn("{{the weekly job}}", detail(r, "placeholders"))
        self.assertGreater(r["failed"], 0)

    def test_single_brace_slot_fails(self):
        r = cc.check("I saved 3 hours with {tool name}.\nComment YES.")
        self.assertEqual(status(r, "placeholders"), "FAIL")

    def test_cli_not_ready(self):
        res = CommandLine.run_cli(None, "I cut {{N}} costs.\nComment YES.")
        self.assertEqual(res.returncode, 1)
        self.assertIn("not ready", res.stdout)
        self.assertNotIn("ready to post", res.stdout)

    def test_clean_caption_passes(self):
        self.assertEqual(status(cc.check(GOOD), "placeholders"), "PASS")


class AskIsTheViewersAsk(unittest.TestCase):
    """End-to-end test: a how-to step was counted as a second ask."""

    HOWTO = (
        "I turned a 40-minute YouTube video into a Claude Code skill.\n"
        "\n"
        "Paste the link, then tell Claude \"save this as a skill\".\n"
        "Join the two steps and download the transcript first if the video is long.\n"
        "\n"
        "Comment SKILL and I'll send you the setup."
    )

    def test_instruction_and_quote_are_not_asks(self):
        r = cc.check(self.HOWTO, keywords=["claude code skill"])
        self.assertEqual(status(r, "call to action"), "PASS", detail(r, "call to action"))
        self.assertIn("Comment SKILL", detail(r, "call to action"))

    def test_counted_lines_are_printed(self):
        r = cc.check("I sleep 9 hours now.\nSave this for tonight.\nFollow for more.")
        d = detail(r, "call to action")
        self.assertEqual(status(r, "call to action"), "FAIL")
        self.assertIn('"Save this for tonight."', d)
        self.assertIn('"Follow for more."', d)

    def test_real_asks_still_count(self):
        for line in ("Save this post for your next trip.", "DM me PLAN for the sheet.", "Link in bio.",
                     "Send this to a friend who meal preps.", "Join my newsletter, link in bio.",
                     "Let me know which one you'd try."):
            r = cc.check("I cut 3 costs in 2024.\n" + line)
            self.assertEqual(status(r, "call to action"), "PASS", line)

    def test_not_asks(self):
        for line in ("I read every comment.", "Tell Claude to save it as a skill.",
                     "Step 2: download the file.", "Then join the two tables."):
            self.assertEqual(cc.ask_kinds(line), [], line)


class SearchTermPlacement(unittest.TestCase):
    """End-to-end test: a term only in paragraph 2 was reported "before the cut"."""

    TEXT = ("The skill is called watch, and it runs in your terminal.\n"
            "\n"
            "It turns any YouTube video into claude code skills you keep.\n"
            "\n"
            "Comment WATCH for the setup.")

    def test_after_the_cut_and_plural(self):
        r = cc.check(self.TEXT, fmt="reel", keywords=["Claude Code skill", "watch", "podcast"])
        d = detail(r, "search terms")
        self.assertIn("'claude code skill' after the Reels cut", d)
        self.assertIn("'watch' before the Reels cut", d)
        self.assertIn("'podcast' missing", d)
        self.assertEqual(status(r, "search terms"), "FAIL")

    def test_word_forms(self):
        r = cc.check("I spent 3 weeks meal planning.\nComment YES.", keywords=["meal plan"])
        self.assertEqual(status(r, "search terms"), "PASS")
        self.assertIn("before the Reels cut", detail(r, "search terms"))

    def test_feed_cut_named_for_posts(self):
        r = cc.check(self.TEXT, fmt="post", keywords=["claude code skill"])
        self.assertIn("after the feed cut", detail(r, "search terms"))


class MatchesScript(unittest.TestCase):
    """End-to-end test: the script said "send this to a friend", the caption "comment SKILL"."""

    CAPTION = "I made 1 skill from a video.\nComment SKILL and I'll send you the guide."

    def test_different_ask_warns_not_fails(self):
        r = cc.check(self.CAPTION, script="Here's how.\nSend this to a friend who needs it.")
        self.assertEqual(status(r, "matches script"), "WARN")
        self.assertIn("Send this to a friend", detail(r, "matches script"))
        self.assertEqual(r["failed"], 0)

    def test_same_ask_passes(self):
        r = cc.check(self.CAPTION, script="Here's how.\nComment SKILL and I'll send it.")
        self.assertEqual(status(r, "matches script"), "PASS")

    def test_different_keyword_warns(self):
        r = cc.check(self.CAPTION, script="Comment GUIDE and I'll send it.")
        self.assertEqual(status(r, "matches script"), "WARN")
        self.assertIn("GUIDE", detail(r, "matches script"))

    def test_no_script_no_row(self):
        self.assertFalse(any(x["check"] == "matches script" for x in cc.check(self.CAPTION)["results"]))

    def test_cli_flag(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Send this to a friend.")
        try:
            res = CommandLine.run_cli(None, self.CAPTION, "--script", f.name)
        finally:
            os.unlink(f.name)
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("WARN  matches script", res.stdout)


# A caption in a creator's real style: the post's own ask, then the standing
# footer they put under every post (separator, "Follow @handle..." line, hashtags).
REAL_STYLE = (
    "A spreadsheet I built gives me back 3 hours every Friday on client invoices.\n"
    "\n"
    "It reads the week's hours and drafts every invoice for me to check.\n"
    "\n"
    "Follow me and comment SHEET, and I'll send you the step-by-step guide.\n"
    "\n"
    "{sep}\n"
    "\n"
    "Follow @made.up.creator to learn more about running a small business.\n"
    "\n"
    "#smallbusiness #invoices #spreadsheets"
)
SEPARATORS = ["—", "–", "---", "----", "___", "* * *", ".", "~~~"]


class StandingFooter(unittest.TestCase):
    """End-to-end test: a creator's standing footer was counted as a second call to action,
    so every caption in their real style failed."""

    def test_real_style_caption_passes(self):
        r = cc.check(REAL_STYLE.format(sep="—"), keywords=["client invoices", "small business"])
        self.assertEqual(r["failed"], 0, r["results"])
        self.assertEqual(status(r, "call to action"), "PASS")
        d = detail(r, "call to action")
        self.assertIn("counted 1 ask: \"Follow me and comment SHEET", d)
        self.assertIn("left out your closing footer \"Follow @made.up.creator", d)
        self.assertNotIn(".\".", d)  # no doubled full stop after the quote

    def test_every_separator_form_is_the_same(self):
        for sep in SEPARATORS:
            r = cc.check(REAL_STYLE.format(sep=sep))
            self.assertEqual(status(r, "call to action"), "PASS", (sep, detail(r, "call to action")))

    def test_footer_hashtags_still_count_toward_the_limit(self):
        r = cc.check(REAL_STYLE.format(sep="---").replace("#spreadsheets", "#spreadsheets #a #b #c"))
        self.assertEqual(status(r, "hashtags"), "FAIL")

    def test_no_separator_means_no_footer(self):
        text = REAL_STYLE.format(sep="").replace("\n\n\n\n", "\n\n")
        r = cc.check(text)
        self.assertEqual(status(r, "call to action"), "FAIL")
        self.assertIn("2 asks found", detail(r, "call to action"))

    def test_two_asks_in_the_body_still_fail(self):
        text = REAL_STYLE.format(sep="—").replace(
            "guide.\n", "guide.\n\nSave this post for your next invoice day.\n")
        r = cc.check(text)
        self.assertEqual(status(r, "call to action"), "FAIL")
        self.assertIn("2 asks found", detail(r, "call to action"))
        self.assertNotIn("@made.up.creator to learn", detail(r, "call to action").split("left out")[0])

    def test_footer_is_the_only_ask(self):
        text = REAL_STYLE.format(sep="—").replace(
            "Follow me and comment SHEET, and I'll send you the step-by-step guide.\n\n", "")
        r = cc.check(text)
        self.assertEqual(status(r, "call to action"), "PASS")
        self.assertIn("in your closing footer", detail(r, "call to action"))

    def test_split_footer(self):
        body, foot = cc.split_footer(REAL_STYLE.format(sep="___"))
        self.assertTrue(body.endswith("step-by-step guide."))
        self.assertTrue(foot.startswith("___\n"))
        # a separator in the middle, followed by ordinary sentences, is not a footer
        self.assertEqual(cc.split_footer("One.\n\n---\n\nTwo more lines here.\n#tag")[1], "")

    def test_cli_exit_zero(self):
        res = CommandLine.run_cli(None, REAL_STYLE.format(sep="---"), "--keywords", "client invoices")
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("Result: ready to post", res.stdout)


class ScriptFinalAsk(unittest.TestCase):
    """End-to-end test: --script pooled spoken and on-screen asks from every section, so a
    "save" caption got "Same ask as the script: ... Comment INSTAGRAM"."""

    DRAFT = (
        "## Hook\n"
        "Spoken: My invoice skill saves 3 hours every Friday.\n"
        "On screen: Claude Code for invoices\n"
        "\n"
        "## Script\n"
        "My invoice skill saves 3 hours every Friday.\n"
        "Save this Reel for your next invoice day.\n"
        "\n"
        "## On-screen text\n"
        "0:00-0:03 Claude Code for invoices\n"
        "0:03-0:06 Comment INSTAGRAM for the guide.\n"
    )
    SAVE = "Friday invoice work is where I'd start.\n\nSave this Reel for your next invoice day."
    COMMENT = "Friday invoice work is where I'd start.\n\nComment INSTAGRAM for the guide."

    def test_save_caption_matches_the_spoken_ask(self):
        r = cc.check(self.SAVE, script=self.DRAFT)
        self.assertEqual(status(r, "matches script"), "PASS")
        self.assertIn("Save this Reel", detail(r, "matches script"))
        self.assertNotIn("INSTAGRAM", detail(r, "matches script"))

    def test_comment_caption_warns(self):
        r = cc.check(self.COMMENT, script=self.DRAFT)
        self.assertEqual(status(r, "matches script"), "WARN")
        self.assertIn("ends by asking \"Save this Reel", detail(r, "matches script"))

    def test_conflicting_on_screen_ask_is_named(self):
        r = cc.check(self.SAVE, script=self.DRAFT)
        self.assertEqual(status(r, "script asks"), "WARN")
        self.assertIn("Comment INSTAGRAM", detail(r, "script asks"))
        same = self.DRAFT.replace("Comment INSTAGRAM for the guide.", "Save this for invoice day.")
        self.assertFalse(any(x["check"] == "script asks" for x in cc.check(self.SAVE, script=same)["results"]))

    def test_only_the_final_spoken_ask_counts(self):
        script = "Comment GUIDE if you want my sheet.\nBut first, the steps.\nSave this for later."
        r = cc.check(self.SAVE, script=script)
        self.assertEqual(status(r, "matches script"), "PASS")
        r = cc.check(self.COMMENT, script=script)
        self.assertEqual(status(r, "matches script"), "WARN")
        self.assertIn("Save this for later", detail(r, "matches script"))

    def test_script_parts(self):
        parts = cc.script_parts(self.DRAFT)
        self.assertNotIn("INSTAGRAM", parts["spoken"])
        self.assertIn("Comment INSTAGRAM for the guide.", parts["onscreen"].split("\n"))


if __name__ == "__main__":
    unittest.main()
