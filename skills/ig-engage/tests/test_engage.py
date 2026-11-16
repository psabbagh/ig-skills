"""Offline tests for scripts/engage.py, on made-up comments. Run: python3 -m unittest discover ig-engage/tests"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "engage.py")
sys.path.insert(0, os.path.dirname(SCRIPT))

import engage as eg  # noqa: E402


def slurp(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def run(*args, stdin=None, env=None):
    p = subprocess.run([sys.executable, "-B", SCRIPT, *args], input=stdin, capture_output=True, text=True,
                       env=None if env is None else {**os.environ, **env})
    return p.returncode, p.stdout + p.stderr


def cat(text, keywords=("GUIDE",)):
    c = eg.Comment("x", "", "someone", 0, 0, text, 0)
    eg.classify(c, list(keywords))
    return c


def by_user(res, user):
    return [c for c in res["comments"] if c.user == user]


class Classify(unittest.TestCase):
    def test_keyword_whole_word_and_plural(self):
        for t in ("GUIDE", "guide please!!", "Guides 🙏", "the guide pls", "G U I D E"):
            self.assertEqual(cat(t).category, "keyword", t)

    def test_keyword_typo_only_when_short(self):
        self.assertEqual(cat("guid").category, "keyword")
        self.assertNotEqual(cat("I think the guid of this video is about rendering speed tricks").category, "keyword")

    def test_keyword_not_inside_other_words(self):
        self.assertNotEqual(cat("misguided take honestly").category, "keyword")

    def test_keyword_phrase(self):
        self.assertEqual(cat("skill pack!", ["SKILL PACK"]).category, "keyword")

    def test_keyword_with_question_tagged(self):
        c = cat("guide! does it work on windows?")
        self.assertEqual(c.category, "keyword")
        self.assertIn("question", c.tags)

    def test_keyword_with_lead_tagged(self):
        self.assertIn("lead", cat("guide, and how much to set it up for my agency?").tags)

    def test_lead(self):
        for t in ("How much would you charge for this?", "Do you offer this as a service?",
                  "Can you build this for my business", "Would love to work with you on something"):
            self.assertEqual(cat(t).category, "lead", t)

    def test_question(self):
        for t in ("does this work on windows or only mac?", "how do you keep it in sync", "Which app is that"):
            self.assertEqual(cat(t).category, "question", t)

    def test_spam_beats_lead_and_keyword(self):
        for t in ("Love this! DM us to collab and grow your page 🚀", "guide at www.spamsite.com",
                  "check out my page for more", "Promote it on our page", "follow me back"):
            self.assertEqual(cat(t).category, "noise", t)

    def test_friend_tag_is_noise(self):
        c = cat("@bestfriend @other.one")
        self.assertEqual(c.category, "noise")
        self.assertIn("tagged", c.why)

    def test_praise(self):
        for t in ("so good", "🔥🔥🔥", "needed this", "game changer"):
            self.assertEqual(cat(t).category, "praise", t)

    def test_emoji_only_not_positive_is_noise(self):
        self.assertEqual(cat("👀").category, "noise")

    def test_substance(self):
        t = "I tried something like this last year but keeping notes in sync was the hard part"
        self.assertEqual(cat(t).category, "substance")
        self.assertEqual(cat("I switched to plain files instead").category, "substance")

    def test_one_other_word_flagged_maybe_keyword(self):
        c = cat("Skill", ["STARTUP"])
        self.assertEqual(c.category, "noise")
        self.assertIn("maybe-keyword", c.tags)
        cs = [eg.Comment(str(i), "", f"u{i}", 0, 0, "Skill", i) for i in range(2)]
        out = eg.render_sort(eg.sort_comments(None, cs, ["STARTUP"], "me"))
        self.assertIn("SKILL x2", out)

    def test_no_keyword_given(self):
        self.assertEqual(cat("GUIDE", []).category, "noise")


class Loading(unittest.TestCase):
    def test_simple_lines_with_reply(self):
        post, cs = eg.load([os.path.join(FIX, "pasted.txt")])
        self.assertIsNone(post)
        self.assertEqual(len(cs), 12)
        reply = next(c for c in cs if c.user == "demo.creator")
        tom = next(c for c in cs if c.user == "tom_k")
        self.assertEqual(reply.parent, tom.id)

    def test_copied_from_instagram(self):
        _, cs = eg.load([os.path.join(FIX, "copied.txt")])
        self.assertEqual([c.user for c in cs], ["jules.makes", "ben_tries", "mira.co"])
        self.assertEqual(cs[0].text, "This is exactly what I needed, saving it")
        self.assertEqual(cs[0].likes, 3)
        self.assertTrue(cs[1].liked_by_creator)
        self.assertEqual(cs[2].text, "Do you offer this as a service for small teams?")

    def test_browser_dump(self):
        post, cs = eg.load([os.path.join(FIX, "dump.json")])
        self.assertEqual(post["owner"], "demo.creator")
        self.assertEqual(post["comments"], 9)
        self.assertEqual(len(cs), 7)
        self.assertEqual(cs[2].parent, "2")

    def test_long_text_continues_on_more_lines(self):
        lines = ["#post\tC0de12\tme\t0\t1\t" + "a" * 400, "#more\t\t\t\t\tb" * 1,
                 "1\t\tx\t0\t0\t" + "c" * 400, "#more\t\t\t\t\td"]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(lines, f)
            post, cs = eg.load([p], 4, eg.djb2("\n".join(lines)))
        self.assertEqual(post["caption"], "a" * 400 + "b")
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0].text, "c" * 400 + "d")

    def test_checksum_matches_and_mismatch_exits(self):
        lines = json.loads(slurp(os.path.join(FIX, "dump.json")))
        h = eg.djb2("\n".join(lines))
        eg.load([os.path.join(FIX, "dump.json")], len(lines), h)  # no exit
        with self.assertRaises(SystemExit):
            eg.load([os.path.join(FIX, "dump.json")], len(lines), "deadbeef")

    def test_djb2_known_value(self):
        # same as the JS: h = imul(h, 33) + charCode, unsigned, from 5381
        self.assertEqual(eg.djb2(""), "00001505")
        self.assertEqual(eg.djb2("a"), f"{(5381 * 33 + 97) & 0xFFFFFFFF:08x}")
        # astral emoji hash as two UTF-16 units, like charCodeAt
        h = 5381
        for unit in (0xD83D, 0xDD25):
            h = (h * 33 + unit) & 0xFFFFFFFF
        self.assertEqual(eg.djb2("🔥"), f"{h:08x}")


class Sorting(unittest.TestCase):
    def setUp(self):
        post, cs = eg.load([os.path.join(FIX, "pasted.txt")])
        self.res = eg.sort_comments(post, cs, ["GUIDE"], "demo.creator")

    def test_counts(self):
        c = self.res["counts"]
        self.assertEqual(c["keyword"], 4)
        self.assertEqual(c["lead"], 1)
        self.assertEqual(c["question"], 1)
        self.assertEqual(self.res["yours"], 1)

    def test_replied_marked(self):
        self.assertTrue(by_user(self.res, "tom_k")[0].replied)
        self.assertEqual(self.res["answered"]["keyword"], 1)

    def test_order_lead_question_first_and_no_noise(self):
        order = self.res["order"]
        self.assertEqual(order[0].user, "lena.ops")
        self.assertEqual(order[1].user, "raj.dev")
        self.assertFalse(any(c.category == "noise" for c in order))
        self.assertFalse(any(c.replied for c in order))

    def test_keyword_person_once_in_order(self):
        self.assertEqual(sum(1 for c in self.res["order"] if c.user == "maya.builds"), 1)

    def test_dump_owner_is_me_and_thread_reply_answers(self):
        post, cs = eg.load([os.path.join(FIX, "dump.json")])
        res = eg.sort_comments(post, cs, ["PROMPT"])
        self.assertEqual(res["me"], "demo.creator")
        leo = by_user(res, "leo.m")[0]
        self.assertTrue(leo.replied)
        self.assertIn("question", leo.tags)
        self.assertEqual(res["order"][0].user, "zed.agency")

    def test_likes_break_ties(self):
        cs = [eg.Comment("1", "", "a", 1, 0, "how does this work", 0),
              eg.Comment("2", "", "b", 2, 30, "what app is this", 1)]
        res = eg.sort_comments(None, cs, [], "me")
        self.assertEqual([c.user for c in res["order"]], ["b", "a"])

    def test_render_has_counts_and_order(self):
        out = eg.render_sort(self.res)
        self.assertIn("used the keyword", out)
        self.assertIn("1 already answered", out)
        self.assertIn("@lena.ops", out)


class DMs(unittest.TestCase):
    def setUp(self):
        post, cs = eg.load([os.path.join(FIX, "pasted.txt")])
        self.res = eg.sort_comments(post, cs, ["GUIDE"], "demo.creator")

    def test_one_per_person_rotating_messages(self):
        rows = eg.dm_rows(self.res, ["A {link}", "B {link} {handle}"], "https://x.example/g")
        self.assertEqual([r["handle"] for r in rows], ["maya.builds", "tom_k", "pat.r"])
        self.assertEqual(rows[0]["dm"], "A https://x.example/g")
        self.assertEqual(rows[1]["dm"], "B https://x.example/g tom_k")
        self.assertTrue(rows[1]["replied"])
        self.assertIn(" / ", rows[0]["comment"])

    def test_reply_saying_sent_is_marked_and_new_only_drops_it(self):
        rows = eg.dm_rows(self.res, ["{link}"], "L")
        tom = next(r for r in rows if r["handle"] == "tom_k")
        self.assertTrue(tom["said_sent"])
        self.assertNotIn("tom_k", [r["handle"] for r in eg.dm_rows(self.res, ["{link}"], "L", new_only=True)])
        self.assertIn("your reply under the post says you sent it", eg.render_dms(rows, "L"))

    def test_skip_list(self):
        rows = eg.dm_rows(self.res, ["{link}"], "L", skip=["@maya.builds", "PAT.R"])
        self.assertEqual([r["handle"] for r in rows], ["tom_k"])

    def test_unknown_placeholder_exits(self):
        with self.assertRaises(SystemExit):
            eg.dm_rows(self.res, ["Hi {name}"], "L")

    def test_cli_csv(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "dms.csv")
            rc, text = run("dms", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE", "--me", "demo.creator",
                           "--link", "https://x.example/g", "-m", "Here it is: {link}", "--csv", out)
            self.assertEqual(rc, 0, text)
            self.assertIn("sent nothing", text)
            rows = slurp(out).splitlines()
            self.assertEqual(len(rows), 4)
            self.assertTrue(rows[0].startswith("n,handle,profile"))

    def test_cli_needs_link_for_placeholder(self):
        rc, text = run("dms", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE", "-m", "x {link}")
        self.assertNotEqual(rc, 0)
        self.assertIn("--link", text)


class CsvAndErrors(unittest.TestCase):
    ARGS = ("dms", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE", "--me", "demo.creator",
            "--link", "https://x.example/g", "-m", "Here: {link}")

    def test_csv_into_existing_folder(self):
        with tempfile.TemporaryDirectory() as d:
            rc, text = run(*self.ARGS, "--csv", d)
            self.assertEqual(rc, 0, text)
            self.assertNotIn("Traceback", text)
            path = os.path.join(d, "dms-guide.csv")
            self.assertIn("CSV: " + path, text)
            self.assertEqual(len(slurp(path).splitlines()), 4)

    def test_csv_into_new_folder_with_slash_uses_post_code(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "out") + "/"
            rc, text = run("dms", os.path.join(FIX, "dump.json"), "-k", "PROMPTS", "--link", "L", "-m", "{link}",
                           "--csv", target)
            self.assertEqual(rc, 0, text)
            code = eg.load([os.path.join(FIX, "dump.json")])[0]["code"]
            self.assertTrue(os.path.isfile(os.path.join(target, f"dms-{code}.csv")), text)

    def test_no_traceback_on_bad_paths(self):
        rc, text = run("sort", "/nonexistent/comments.txt", "-k", "GUIDE")
        self.assertNotEqual(rc, 0)
        self.assertNotIn("Traceback", text)
        self.assertIn("no such file", text)
        with tempfile.TemporaryDirectory() as d:
            rc, text = run("sort", d, "-k", "GUIDE")
            self.assertNotIn("Traceback", text)
            self.assertIn("is a folder", text)


class CountNote(unittest.TestCase):
    def test_gap_explained_with_comments_and_replies(self):
        post = {"code": "C", "owner": "me", "ts": 0, "comments": 18, "caption": ""}
        cs = [eg.Comment("1", "", "a", 0, 0, "x", 0), eg.Comment("2", "1", "me", 0, 0, "y", 1),
              eg.Comment("3", "", "b", 0, 0, "z", 2), eg.Comment("4", "3", "me", 0, 0, "w", 3)]
        text = "\n".join(eg.count_note(post, cs))
        self.assertIn("read 2 comments and 2 replies", text)
        self.assertIn("Instagram shows 18", text)
        self.assertIn("deleted", text)
        self.assertIn("hidden words", text)
        self.assertNotIn("read 4 of 18", text)

    def test_no_gap_no_explanation(self):
        post = {"code": "C", "owner": "me", "ts": 0, "comments": 1, "caption": ""}
        self.assertEqual(len(eg.count_note(post, [eg.Comment("1", "", "a", 0, 0, "x", 0)])), 1)


class Replies(unittest.TestCase):
    def setUp(self):
        post, cs = eg.load([os.path.join(FIX, "pasted.txt")])
        self.res = eg.sort_comments(post, cs, ["GUIDE"], "demo.creator")
        self.wanted = eg.worth_answering(self.res)

    def test_worth_answering_in_reply_order(self):
        self.assertEqual([c.user for c in self.wanted], ["lena.ops", "raj.dev", "sam.writes"])
        self.assertIn("kay", [c.user for c in eg.worth_answering(self.res, include_praise=True)])

    def test_keyword_with_question_is_drafted(self):
        cs = eg.parse_simple("ann: GUIDE! does it work offline?\nbo: GUIDE")
        res = eg.sort_comments(None, cs, ["GUIDE"], "me")
        self.assertEqual([c.user for c in eg.worth_answering(res)], ["ann"])

    def test_parse_drafts_by_handle_number_and_continuation(self):
        text = "@lena.ops: Sending you a DM now\n2. Both, Mac and Windows\nsecond line\n@nobody: hi"
        drafts, unmatched = eg.parse_drafts(text, self.wanted)
        self.assertEqual(drafts[self.wanted[0].id], "Sending you a DM now")
        self.assertEqual(drafts[self.wanted[1].id], "Both, Mac and Windows\nsecond line")
        self.assertEqual(len(unmatched), 1)

    def test_check_drafts_copy_ready_and_flags(self):
        drafts = {self.wanted[0].id: "Thanks! Sending you a DM so we can talk about your setup",
                  self.wanted[1].id: "Thanks!"}
        text, ok = eg.check_drafts(self.wanted, drafts, [], use_voice=False)
        self.assertFalse(ok)
        self.assertIn("no draft yet", text)              # sam.writes
        self.assertIn("answers it", text)                # raj.dev's too-short answer
        self.assertIn("Ready to paste (2 of 3)", text)
        self.assertIn("1. @lena.ops:", text)
        self.assertIn("nothing was posted", text)

    def test_cli_worksheet_then_drafts(self):
        rc, out = run("replies", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE", "--me", "demo.creator")
        self.assertEqual(rc, 0, out)
        self.assertIn("1. @lena.ops [possible lead", out)
        self.assertIn("--drafts", out)
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "r.txt")
            with open(f, "w", encoding="utf-8") as fh:
                fh.write("@lena.ops: Thanks for asking, sending you a DM so we can look at your setup\n"
                         "@raj.dev: Both. It runs the same on Windows and Mac\n"
                         "@sam.writes: Same problem here at first. One synced folder fixed it for me\n")
            rc, out = run("replies", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE", "--me", "demo.creator",
                          "--drafts", f, "--no-voice")
            self.assertEqual(rc, 0, out)
            self.assertIn("Ready to paste (3 of 3)", out)
            rc, out = run("replies", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE", "--me", "demo.creator",
                          "--drafts", f)
            self.assertIn("ig-voice", out)


class VoiceLookup(unittest.TestCase):
    def setUp(self):
        self.old = {k: os.environ.pop(k, None) for k in ("IG_VOICE_SKILL_DIR", "IG_VOICE_DIR")}
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = os.path.join(self.tmp.name, "ig-voice")
        os.makedirs(os.path.join(self.fake, "scripts"))
        open(os.path.join(self.fake, "scripts", "voice.py"), "w").close()

    def tearDown(self):
        for k, v in self.old.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_new_name_wins_and_is_named(self):
        os.environ["IG_VOICE_SKILL_DIR"] = self.fake
        script, where, _ = eg.find_voice_info()
        self.assertEqual(script, os.path.join(self.fake, "scripts", "voice.py"))
        self.assertIn("$IG_VOICE_SKILL_DIR", where)

    def test_old_name_still_read(self):
        os.environ["IG_VOICE_DIR"] = self.fake
        script, where, _ = eg.find_voice_info()
        self.assertEqual(script, os.path.join(self.fake, "scripts", "voice.py"))
        self.assertIn("$IG_VOICE_DIR", where)

    def test_profile_folder_in_var_is_reported_not_silent(self):
        os.environ["IG_VOICE_DIR"] = self.tmp.name  # a folder without scripts/voice.py, e.g. a profile folder
        _, _, notes = eg.find_voice_info()
        self.assertTrue(any("IG_VOICE_PROFILE" in n and "ignored" in n for n in notes), notes)

    def test_sibling_in_same_pack_comes_before_global_folders(self):
        sibling = os.path.join(os.path.dirname(os.path.dirname(HERE)), "ig-voice", "scripts", "voice.py")
        if not os.path.isfile(sibling):
            self.skipTest("no ig-voice next to this skill")
        script, where, _ = eg.find_voice_info()
        self.assertEqual(os.path.realpath(script), os.path.realpath(sibling))
        self.assertIn("same pack", where)

    def test_summary_names_the_copy(self):
        lines = eg.summarize_voice({"profile": False, "fixed": []}, where="~/x/ig-voice (from $IG_VOICE_SKILL_DIR)")
        self.assertIn("Copy used: ~/x/ig-voice", lines[0])


class Log(unittest.TestCase):
    E = [{"date": "2026-11-01", "account": "a", "post": "-",
          "text": "The part about batching renders overnight is what I needed"},
         {"date": "2026-11-02", "account": "b", "post": "-",
          "text": "This is so smart, saving it for my next shoot"}]

    def levels(self, text, entries=None, account=None):
        return [lvl for lvl, _ in eg.log_issues(text, self.E if entries is None else entries, account)]

    def test_exact_and_near_repeat_refused(self):
        self.assertIn("REFUSE", self.levels("The part about batching renders overnight is what I needed!"))
        self.assertIn("REFUSE", self.levels("The part about batching renders overnight is exactly what I needed"))

    def test_same_opening_refused(self):
        self.assertIn("REFUSE", self.levels("The part about lighting with one lamp surprised me"))

    def test_same_shape_refused(self):
        self.assertIn("REFUSE", self.levels("That is so clever, keeping it for my next edit"))

    def test_fresh_comment_passes(self):
        self.assertEqual(self.levels("Wait, you shoot everything on a phone from 2019? Respect"), [])

    def test_habits_warn(self):
        es = [{"date": "d", "account": f"x{i}", "post": "-", "text": t} for i, t in enumerate(
            ["Love the color grading here", "Love how short this is", "Love that you showed the fail",
             "Love the second tip about audio", "Okay the timing on this one"])]
        self.assertIn("WARN", self.levels("Love the way you cut the intro", es))

    def test_same_account_warns(self):
        es = [{"date": "d", "account": "a", "post": "-", "text": f"comment number {w} here"} for w in ("one", "two", "three")]
        msgs = [m for _, m in eg.log_issues("A totally different thought about pacing", es, "a")]
        self.assertTrue(any("@a 3 times" in m for m in msgs))

    def test_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sub", "log.md")
            eg.add_log(p, "@someone", "https://www.instagram.com/p/X/", "a | pipe\nand newline", "2026-11-03")
            es = eg.read_log(p)
            self.assertEqual(es, [{"date": "2026-11-03", "account": "someone",
                                   "post": "https://www.instagram.com/p/X/", "text": "a / pipe and newline"}])
            self.assertTrue(slurp(p).startswith("# ig-engage comment log"))

    def test_log_path_override(self):
        old = os.environ.get("IG_ENGAGE_LOG")
        os.environ["IG_ENGAGE_LOG"] = "/tmp/x/log.md"
        try:
            self.assertEqual(eg.log_path(), "/tmp/x/log.md")
            self.assertEqual(eg.log_path("/y/l.md"), "/y/l.md")
        finally:
            if old is None:
                del os.environ["IG_ENGAGE_LOG"]
            else:
                os.environ["IG_ENGAGE_LOG"] = old


class Check(unittest.TestCase):
    def names(self, res, level):
        return [n for lvl, n, _ in res if lvl == level]

    def test_generic_and_promo_and_link_fail(self):
        self.assertIn("generic", self.names(eg.check_text("Great post! 🔥", "comment"), "FAIL"))
        self.assertIn("self-promotion", self.names(eg.check_text("Nice one, check out my page for more", "comment"), "FAIL"))
        self.assertIn("link", self.names(eg.check_text("see https://x.example", "comment"), "FAIL"))

    def test_about_the_post(self):
        post = {"caption": "Three prompts I use every morning to plan the week", "owner": "x", "code": "c", "comments": 0, "ts": 0}
        on = eg.check_text("The morning prompt for planning is the one I'm stealing", "comment", post=post)
        off = eg.check_text("My cat would disagree with all of that honestly", "comment", post=post)
        self.assertIn("about the post", self.names(on, "PASS"))
        self.assertIn("about the post", self.names(off, "WARN"))

    def test_log_refusal_in_check(self):
        res = eg.check_text("The part about batching renders overnight is what I needed", "comment", Log.E)
        self.assertIn("log", self.names(res, "REFUSE"))

    def test_reply_to_question_too_short(self):
        res = eg.check_text("Thanks!", "reply", to="does this work on windows?")
        self.assertIn("answers it", self.names(res, "WARN"))

    def test_dm_link_and_documented_placeholders_pass(self):
        self.assertEqual(self.names(eg.check_text("Here it is: https://x.example", "dm"), "FAIL"), [])
        res = eg.check_text("Hey {handle}, here's the {keyword}: {link}", "dm")
        self.assertEqual(self.names(res, "FAIL"), [])
        self.assertIn("placeholder", self.names(res, "PASS"))

    def test_dm_unknown_placeholder_and_missing_link(self):
        self.assertIn("placeholder", self.names(eg.check_text("Hi {name}: {link}", "dm"), "FAIL"))
        self.assertIn("link", self.names(eg.check_text("Hey! Sending it over soon", "dm"), "WARN"))

    def test_cli_dm_template_passes_check_then_dms_fills_it(self):
        tpl = "Hey! Here's the guide you asked for: {link}"
        rc, out = run("check", "--kind", "dm", "--no-voice", tpl)
        self.assertEqual(rc, 0, out)
        rc, out = run("dms", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE", "--me", "demo.creator",
                      "--link", "https://x.example/g", "-m", tpl)
        self.assertEqual(rc, 0, out)
        self.assertIn("asked for: https://x.example/g", out)
        self.assertNotIn("{link}", out)

    def test_gap_fails_everywhere(self):
        for kind in ("reply", "dm", "comment"):
            self.assertIn("gap", self.names(eg.check_text("It costs [ ] a month {link}", kind), "FAIL"), kind)

    def test_cli_exit_codes_and_voice_line(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "log.md")
            rc, out = run("check", "--log", log, "Great post!")
            self.assertEqual(rc, 2)
            rc, out = run("check", "--log", log, "--no-voice", "Wait, you keep it all in one text file? Bold")
            self.assertEqual(rc, 0, out)
            self.assertIn("ok to post", out)

    def test_voice_missing_message(self):
        lines = eg.summarize_voice(None)
        self.assertIn("would be better with it", lines[0])

    def test_voice_runs_when_installed(self):
        script = eg.find_voice()
        if not script:
            self.skipTest("ig-voice not installed next to this skill")
        v = eg.run_voice("This is a game changer — love it", "comment")
        self.assertIn("rewrite", v)
        self.assertTrue(eg.summarize_voice(v)[0].startswith("ig-voice:"))


FAKE_VOICE = """import json, sys
sys.stdin.read()
print(json.dumps({"profile": True, "fixed": [], "rewrite": [],
                  "unlike_you": [{"sentence": "here is the guide", "reasons": ["you write here's"]}]}))
"""


def fake_voice(folder):
    os.makedirs(os.path.join(folder, "scripts"))
    with open(os.path.join(folder, "scripts", "voice.py"), "w") as f:
        f.write(FAKE_VOICE)
    return folder


class RoundTwo(unittest.TestCase):
    """Fixes from the second end-to-end test round."""

    def names(self, res, level):
        return [n for lvl, n, _ in res if lvl == level]

    # E1: check fails every placeholder dms would not fill
    def test_dm_placeholder_with_space_fails_like_dms(self):
        tpl = "hey, here's {missing fact} {link}"
        self.assertIn("placeholder", self.names(eg.check_text(tpl, "dm"), "FAIL"))
        rc, out = run("check", "--kind", "dm", "--no-voice", tpl)
        self.assertEqual(rc, 2, out)
        self.assertNotIn("ok to post", out)
        rc, out = run("dms", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE", "--link", "L", "-m", tpl)
        self.assertEqual(rc, 1, out)
        self.assertIn("{missing fact}", out)

    def test_dm_malformed_braces_fail_check_and_dms_without_traceback(self):
        for tpl in ("here {link} {}", "here {link} {", "here {link} }", "here {link} {0}", "here {link:d}"):
            self.assertIn("placeholder", self.names(eg.check_text(tpl, "dm"), "FAIL"), tpl)
            rc, out = run("dms", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE", "--link", "L", "-m", tpl)
            self.assertNotEqual(rc, 0, tpl)
            self.assertNotIn("Traceback", out, tpl)
            self.assertIn("error:", out, tpl)

    def test_dm_escaped_braces_pass(self):
        res = eg.check_text("use {{this}} then {link}", "dm")
        self.assertEqual(self.names(res, "FAIL"), [])

    # E2: voice flags make check not ok
    def test_voice_flags_make_check_not_ok(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"IG_VOICE_SKILL_DIR": fake_voice(os.path.join(d, "ig-voice"))}
            rc, out = run("check", "--kind", "dm", "hey, here is the guide you asked for {link}", env=env)
            self.assertEqual(rc, 2, out)
            self.assertIn("rewrite the lines ig-voice lists", out)
            rc, out = run("check", "--kind", "dm", "--json", "hey, here is the guide you asked for {link}", env=env)
            self.assertEqual(rc, 2, out)
            data = json.loads(out)
            self.assertFalse(data["ok"])
            self.assertTrue(data["voice_flagged"])

    # E3: a question about the creator's own result is a question, not a lead
    def test_question_about_result_is_not_a_lead(self):
        c = cat("INSTAGRAM. How much time does it save you?", ("INSTAGRAM",))
        self.assertEqual(c.category, "keyword")
        self.assertIn("question", c.tags)
        self.assertNotIn("lead", c.tags)
        c = cat("How much time does it save you?")
        self.assertEqual(c.category, "question")
        for text in ("how much?", "How much is it?", "how much would it be to set this up for me"):
            self.assertEqual(cat(text).category, "lead", text)

    # E4: the other-copy notice only with --verbose
    def test_other_voice_copy_only_with_verbose(self):
        sibling = os.path.join(os.path.dirname(os.path.dirname(HERE)), "ig-voice", "scripts", "voice.py")
        if not os.path.isfile(sibling):
            self.skipTest("no ig-voice next to this skill")
        with tempfile.TemporaryDirectory() as d:
            env = {"IG_VOICE_SKILL_DIR": fake_voice(os.path.join(d, "ig-voice"))}
            rc, out = run("check", "--kind", "dm", "hey {link}", env=env)
            self.assertNotIn("another ig-voice copy", out)
            self.assertIn("Copy used:", out)
            rc, out = run("check", "--kind", "dm", "--verbose", "hey {link}", env=env)
            self.assertIn("another ig-voice copy", out)

    # E5: multi-line DMs keep their indentation
    def test_multiline_dm_stays_indented(self):
        rc, out = run("dms", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE", "--me", "demo.creator",
                      "--link", "https://x.example/g", "-m", "Hey!\nHere it is: {link}\nEnjoy")
        self.assertEqual(rc, 0, out)
        self.assertIn("   Hey!\n   Here it is: https://x.example/g\n   Enjoy", out)

    # E6: output folders that don't exist yet are created, never a traceback
    def test_missing_output_folders_are_created(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a", "b", "dms.csv")
            rc, out = run("dms", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE", "--link", "L", "-m", "{link}",
                          "--csv", path)
            self.assertEqual(rc, 0, out)
            self.assertTrue(os.path.isfile(path), out)
            log = os.path.join(d, "x", "y", "log.md")
            rc, out = run("log", "add", "--account", "a", "--log", log, "a fresh comment about batching")
            self.assertEqual(rc, 0, out)
            self.assertTrue(os.path.isfile(log), out)
            rc, out = run("replies", os.path.join(FIX, "pasted.txt"), "-k", "GUIDE",
                          "--drafts", os.path.join(d, "none", "r.txt"))
            self.assertNotIn("Traceback", out)
            self.assertIn("no such file", out)


NODE_HARNESS = r"""
const fs = require('fs');
const comments = [];
for (let i = 0; i < 30; i++) comments.push({pk: 100 + i, user: {username: 'u' + i}, text: 'c' + i,
  child_comment_count: 1, preview_child_comments: [{pk: 900 + i, user: {username: 'r' + i}, text: 'reply'}]});
global.window = global;
global.document = {cookie: ''};
global.setTimeout = (f) => setImmediate(f);
global.fetch = async (path) => {
  let body;
  if (path.includes('/info/')) body = {items: [{user: {username: 'owner'}, caption: {text: 'cap'}, comment_count: 60}]};
  else if (path.includes('child_comments')) body = {child_comments: [], has_more_tail_child_comments: false};
  else {
    const page = path.includes('min_id=p2') ? comments.slice(15) : comments.slice(0, 15);
    body = {comments: page, next_min_id: path.includes('min_id=p2') ? null : 'p2'};
  }
  return {ok: true, status: 200, text: async () => JSON.stringify(body)};
};
eval(fs.readFileSync(process.argv[2], 'utf8'));
const opts = JSON.parse(process.argv[3]);
__igcomments.start(Object.assign({code: 'DfXcY28peC5'}, opts));
(async () => {
  while (__igcomments.state.phase === 'running') await new Promise((r) => setImmediate(r));
  const rows = __igcomments.state.rows;
  console.log(JSON.stringify({phase: __igcomments.state.phase, note: __igcomments.state.note,
    top: rows.filter((r) => !r.parent).length, replies: rows.filter((r) => r.parent).length}));
})();
"""


class BrowserReader(unittest.TestCase):
    # E7: replies: false gives max comments and no replies
    def reader(self, opts):
        import shutil
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        js = os.path.join(os.path.dirname(SCRIPT), "instagram-comments.js")
        with tempfile.TemporaryDirectory() as d:
            harness = os.path.join(d, "harness.js")
            with open(harness, "w") as f:
                f.write(NODE_HARNESS)
            p = subprocess.run([node, harness, js, json.dumps(opts)], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_replies_false_respected(self):
        r = self.reader({"max": 20, "replies": False})
        self.assertEqual(r["phase"], "done", r)
        self.assertEqual((r["top"], r["replies"]), (20, 0))

    def test_replies_true_keeps_previews_without_using_up_max(self):
        r = self.reader({"max": 20, "replies": True})
        self.assertEqual(r["phase"], "done", r)
        self.assertEqual((r["top"], r["replies"]), (20, 20))


class Read(unittest.TestCase):
    def test_read_post(self):
        rc, out = run("read", os.path.join(FIX, "dump.json"), "--top", "2")
        self.assertEqual(rc, 0, out)
        self.assertIn("Three prompts I use every morning", out)
        self.assertIn("@kim (7♥)", out)


class NeverActs(unittest.TestCase):
    def test_no_network_or_posting_code(self):
        src = slurp(SCRIPT)
        for bad in ("urllib", "http.client", "requests", "socket"):
            self.assertNotIn("import " + bad, src)
        js = slurp(os.path.join(os.path.dirname(SCRIPT), "instagram-comments.js"))
        self.assertNotIn("method: 'POST'", js)
        self.assertNotIn('method: "POST"', js)
        for word in ("/like/", "/follow/", "/add/", "create_comment", "direct_v2"):
            self.assertNotIn(word, js)


if __name__ == "__main__":
    unittest.main()


class RoundThree(unittest.TestCase):
    """Fixes from the final end-to-end check: a draft ig-voice could not clear is never reported ready."""

    def test_flag_without_a_profile_is_not_ok(self):
        v = {"profile": False, "fixed": [], "rewrite": [],
             "unlike_you": [{"sentence": "here is the guide", "reasons": ["most people say here's"]}]}
        self.assertTrue(eg.voice_flagged(v))

    def test_voice_that_could_not_run_is_not_ok(self):
        self.assertTrue(eg.voice_flagged({"error": "Expecting value: line 1 column 1 (char 0)"}))

    def test_clean_voice_result_is_ok(self):
        self.assertFalse(eg.voice_flagged({"profile": True, "fixed": [], "rewrite": [], "unlike_you": []}))
        self.assertFalse(eg.voice_flagged(None))  # ig-voice not installed: general checks only, no block


class RoundThreeGeneric(unittest.TestCase):
    def test_stock_praise_in_several_clauses_is_generic(self):
        for c in ("Great post, love this!", "Love this, so helpful!", "This is amazing, thanks for sharing"):
            self.assertTrue(eg.all_generic(c), c)

    def test_a_comment_about_the_post_is_not_generic(self):
        self.assertFalse(eg.all_generic("Love this, the 3-step invoice flow is exactly what I needed"))
