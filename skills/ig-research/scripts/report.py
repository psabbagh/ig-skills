#!/usr/bin/env python3
"""Merge the Instagram and TikTok results for one idea into a CSV and a Markdown table.

    report.py --idea "IDEA" --queries "phrasing 1" "phrasing 2" ... \
              [--ig PART [PART ...] --ig-rows N --ig-hash H] [--tiktok tiktok.tsv] \
              [--out FILE] [--top 25]

--ig: the __igsearch.dump(offset, 50) results from instagram.js, each saved verbatim
as its own file (a JSON array of TSV lines, header first in the offset-0 part), in
offset order. They were copied out of the browser by the model, so the script refuses
to continue (exit 2) unless the copy matches __igsearch.checksum() (--ig-rows,
--ig-hash) field for field, captions excepted.
--tiktok: the TSV tiktok.py wrote. It went straight to disk, so it needs no check.

Writes the CSV, every video from both platforms, then prints a summary and a Markdown
table of the top rows. Rows are ranked the way Instagram says it ranks Reels (sends per
reach weigh most, then likes per reach, then watch time): by shares per 1,000 views, then
likes per 1,000 views, among videos with 10K+ views. Reach isn't public for other people's videos, so
views stand in for it: Instagram-only views on Instagram, plays on TikTok. Videos under
10K views or without a share count follow by views, and videos with few reactions for
their views (likes + comments under 2% of views: possibly boosted, or a flop) come last.
--sort views gives the plain order by views. The summary has a timeline (videos and views per
month, and the newest video with 10K+ views), and every date carries its age, so a news
wave from months ago shows as one; videos under 7 days old are marked still climbing.
The CSV is research-<idea-slug>-<date>.csv in the working folder; --dir picks the folder
(created if needed), --out the exact file. Standard library only.

This file can be shared, identical, by other skills that carry this same file; each such
skill's tests fail if the copies differ, so a change goes to every copy.
"""
import argparse
import csv
import datetime
import json
import re
import statistics
import sys
from pathlib import Path

IG_COLS = ["rank", "code", "username", "posted", "duration_s", "views", "ig_views", "likes",
           "comments", "shares", "type", "queries", "caption"]
TT_COLS = ["rank", "id", "username", "followers", "posted", "duration_s", "views", "likes",
           "comments", "shares", "saves", "queries", "caption"]
OUT_COLS = ["platform", "views", "likes", "comments", "shares", "saves", "engagement_pct",
            "followers", "views_per_follower", "vs_recent_reels", "recent_reels_median",
            "recent_reels_n", "account", "posted", "age_days", "duration_s", "url", "found_by", "best_rank",
            "ig_only_views", "transcript_file", "caption",
            # Added 2026-11-14, at the end so earlier columns keep their place.
            "send_rank", "shares_per_1k_views", "likes_per_1k_views", "saves_per_1k_views",
            "rate_basis", "reactions_pct", "low_reactions"]
CLIMBING_DAYS = 7      # a video younger than this is still gaining views
TOOK_OFF = 10_000      # "newest video with 10K+ views" in the summary
MONTHS_SHOWN = 12      # older months fold into one "earlier" count
RANK_MIN_VIEWS = 10_000  # below this a share rate is too noisy to rank on
LOW_REACTIONS_PCT = 2.0  # (likes + comments) under 2% of views: about 1 Reel in 10 in testing


def rate_views(r):
    """The views a rate divides by, and what they are. Instagram: Instagram-only plays,
    since the shown count adds Facebook plays that the shares and likes don't come from."""
    if r["platform"] == "Instagram":
        if r.get("ig_only_views"):
            return r["ig_only_views"], "instagram-only views"
        return r["views"], "instagram views incl. facebook"
    return r["views"], "tiktok plays"


def per_1k(n, views):
    return round(1000 * n / views, 2) if n is not None and views else None


def add_rates(r):
    """Shares, likes and saves per 1,000 views, and the low-reactions flag."""
    v, r["rate_basis"] = rate_views(r)
    r["shares_per_1k_views"] = per_1k(r.get("shares"), v)
    r["likes_per_1k_views"] = per_1k(r.get("likes"), v)
    r["saves_per_1k_views"] = per_1k(r.get("saves"), v)
    lk = r.get("likes")
    r["reactions_pct"] = round(100 * (lk + (r.get("comments") or 0)) / v, 2) if v and lk is not None else None
    low = v is not None and v >= RANK_MIN_VIEWS and r["reactions_pct"] is not None \
        and r["reactions_pct"] < LOW_REACTIONS_PCT
    r["low_reactions"] = "yes" if low else None
    r["_rank_views"] = v


def send_order(rows):
    """Ranked by shares per 1K views, then likes per 1K, among videos with RANK_MIN_VIEWS+
    views; then the rest by views; then low-reaction videos by views. Sets send_rank."""
    def group(r):
        if r.get("low_reactions"):
            return 2
        if (r["_rank_views"] or 0) >= RANK_MIN_VIEWS and r.get("shares_per_1k_views") is not None:
            return 0
        return 1

    def key(r):
        g = group(r)
        if g == 0:
            return (0, -r["shares_per_1k_views"], -(r.get("likes_per_1k_views") or 0), -(r["views"] or 0))
        return (g, r["views"] is None, -(r["views"] or 0))

    rows.sort(key=key)
    n = 0
    for r in rows:
        if group(r) == 0:
            n += 1
            r["send_rank"] = n
    return n


def djb2(text):
    h = 5381
    for ch in text:
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    return f"{h:08x}"


def short(n):
    if n is None:
        return "–"
    for div, suffix in ((1_000_000, "M"), (1_000, "K")):
        if n >= div:
            return f"{n / div:.1f}".rstrip("0").rstrip(".") + suffix
    return str(int(n))


def age_days(posted, today):
    """Whole days from the post date to today; None without a date."""
    try:
        return max(0, (today - datetime.date.fromisoformat(posted)).days)
    except (TypeError, ValueError):
        return None


def age_label(days):
    """'3 d, still climbing' under a week, then '2 wk', '3 mo', '2 yr'."""
    if days is None:
        return ""
    if days < CLIMBING_DAYS:
        return ("today" if days == 0 else f"{days} d") + ", still climbing"
    if days < 30:
        return f"{days // 7} wk"
    if days < 730:
        return f"{max(1, int(days / 30.44))} mo"
    return f"{days // 365} yr"


def posted_label(r):
    """'2026-07-27 (3 mo)': the date and how old the video is today."""
    if not r.get("posted"):
        return "–"
    age = age_label(r.get("age_days"))
    return f"{r['posted']} ({age})" if age else r["posted"]


def timeline(rows, today):
    """The videos per month with their total views, from the oldest month to this one,
    and the newest video that reached TOOK_OFF views. Shows a news wave at a glance."""
    months, undated = {}, 0
    for r in rows:
        if r.get("age_days") is None:
            undated += 1
            continue
        d = datetime.date.fromisoformat(r["posted"])
        n, v = months.get((d.year, d.month), (0, 0))
        months[(d.year, d.month)] = (n + 1, v + (r["views"] or 0))
    lines = []
    if months:
        keys, (y, m) = [], min(months)
        while (y, m) <= max(max(months), (today.year, today.month)):
            keys.append((y, m))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        earlier, keys = keys[:-MONTHS_SHOWN], keys[-MONTHS_SHOWN:]
        years = len({k[0] for k in keys}) > 1 or keys[0][0] != today.year
        parts = []
        if earlier:
            n = sum(months.get(k, (0, 0))[0] for k in earlier)
            v = sum(months.get(k, (0, 0))[1] for k in earlier)
            parts.append(f"earlier {n}" + (f" ({short(v)})" if v else ""))
        for i, (y, m) in enumerate(keys):
            n, v = months.get((y, m), (0, 0))
            label = datetime.date(y, m, 1).strftime("%b")
            if years and (i == 0 or m == 1):
                label = f"{y}: {label}"
            parts.append(f"{label} {n}" + (f" ({short(v)})" if v else ""))
        lines.append("By month: " + " · ".join(parts) + (f" · {undated} undated" if undated else ""))
    hits = [r for r in rows if r.get("age_days") is not None and (r["views"] or 0) >= TOOK_OFF]
    if hits:
        r = max(hits, key=lambda r: (r["posted"], r["views"]))
        lines.append(f"Newest with {short(TOOK_OFF)}+ views: {posted_label(r)}, @{r['account']} on "
                     f"{r['platform']}, {short(r['views'])} views")
    elif months:
        lines.append(f"No dated video reached {short(TOOK_OFF)} views")
    return lines


def _hook(text):
    """The transcript's opening line, up to 9 words: what the video says first."""
    body = [l for l in text.splitlines() if l.startswith("**[")]
    first = re.sub(r"^\*\*\[[^\]]*\]\*\*\s*", "", body[0]) if body else ""
    words = re.split(r"(?<=[.!?])\s", first, maxsplit=1)[0].split()
    if len(words) < 3:
        words = first.split()
    return " ".join(words[:9]).rstrip(".,!?;:")


def readable_name(r, hook):
    """<creator> - <platform> - <hook> (<id>).md. The id stays so the report can match it."""
    title = (hook or r.get("caption") or "").replace("’", "'")
    title = " ".join(re.sub(r"[^\w\s'.,!&+-]", "", title).split())  # drops emoji and :/#[]|? etc.
    if len(title) > 60:
        title = title[:60].rsplit(" ", 1)[0]
    key = r.get("code") or r.get("id")
    return f"{r['account']} - {r['platform']} - {title} ({key}).md" if title else f"{r['account']} - {r['platform']} ({key}).md"


def retitle(path, r):
    """Rewrite a transcript's heading lines from the row; leave the transcript itself alone."""
    lines = path.read_text(encoding="utf-8").splitlines()
    hook = _hook("\n".join(lines))
    d = r.get("duration_s")
    dur = f" ({int(d // 60):02d}:{int(d % 60):02d})" if d else ""
    kind = "Reel" if r["platform"] == "Instagram" else "TikTok"
    head = [f"# @{r['account']} on {r['platform']}: \"{hook}\"" if hook else f"# @{r['account']} on {r['platform']}",
            "", f"{kind}: {r['url']}{dur} · posted {r['posted']} · {short(r['views'])} views  "]
    start = next((i for i, l in enumerate(lines) if l.startswith(("Transcribed:", "Fetched:"))), None)
    path.write_text("\n".join(head + (lines[start:] if start is not None else lines[1:])) + "\n", encoding="utf-8")
    return hook


def attach_transcripts(rows, folder):
    """Find each row's transcript by id (fresh <id>.md, or an earlier '... (<id>).md'),
    give it a readable name and heading, and record its path."""
    for r in rows:
        key = r.get("code") or r.get("id")
        if not key:
            continue
        p = folder / f"{key}.md"
        if not p.is_file():
            hits = sorted(folder.glob(f"*({key}).md"))
            if not hits:
                continue
            p = hits[0]
        new = folder / readable_name(r, retitle(p, r))
        if new != p:
            p.rename(new)
            p = new
        r["transcript_file"] = str(p)


def ints(r, keys):
    for k in keys:
        r[k] = int(r[k]) if r.get(k) not in ("", None) else None
    r["duration_s"] = float(r["duration_s"]) if r.get("duration_s") else None


def load_ig(parts, want_rows, want_hash):
    lines = []
    for p in parts:
        text = Path(p).read_text(encoding="utf-8").strip()
        part = json.loads(text) if text.startswith("[") else text.splitlines()
        if not all(isinstance(x, str) for x in part):
            sys.exit(f"error: {p} must be a JSON array of strings")
        lines.extend(x for x in part if x.strip())
    if not lines or lines[0].split("\t") != IG_COLS:
        sys.exit("error: the first Instagram part must start with the header line: " + " ".join(IG_COLS))
    if any(ln.split("\t") == IG_COLS for ln in lines[1:]):
        sys.exit("error: Instagram header appears twice; only the offset-0 part carries it")
    raw = [ln.split("\t") for ln in lines[1:]]
    bad = [i + 2 for i, f in enumerate(raw) if len(f) != len(IG_COLS)]
    if bad:
        sys.exit(f"error: wrong number of tab-separated fields on Instagram line(s) {bad[:10]}")
    got = djb2("\n".join("\t".join(f[:-1]) for f in raw))
    if len(raw) != want_rows or got != want_hash.lower():
        print(f"MISMATCH: Instagram copy has {len(raw)} rows, hash {got}; browser has {want_rows} rows, "
              f"hash {want_hash}. Dump again and rewrite the part files verbatim; never fix numbers "
              "by hand.", file=sys.stderr)
        sys.exit(2)
    rows = []
    for f in raw:
        r = dict(zip(IG_COLS, f))
        ints(r, ("rank", "views", "ig_views", "likes", "comments", "shares"))
        r.update(platform="Instagram", followers=None, saves=None, account=r["username"],
                 url=f"https://www.instagram.com/{'reel' if r['type'] == 'clips' else 'p'}/{r['code']}/",
                 ig_only_views=r["ig_views"])
        rows.append(r)
    return rows


def load_tt(path):
    with open(path, encoding="utf-8") as fh:
        lines = [ln.rstrip("\n") for ln in fh if ln.strip()]
    if not lines or lines[0].split("\t") != TT_COLS:
        sys.exit(f"error: {path} does not start with the tiktok.py header")
    rows = []
    for ln in lines[1:]:
        r = dict(zip(TT_COLS, ln.split("\t")))
        ints(r, ("rank", "followers", "views", "likes", "comments", "shares", "saves"))
        r.update(platform="TikTok", account=r["username"], ig_only_views=None,
                 url=f"https://www.tiktok.com/@{r['username']}/video/{r['id']}")
        rows.append(r)
    return rows


def summary(name, rows):
    views = [r["views"] for r in rows if r["views"] is not None]
    s = f"{name}: {len(rows)} videos"
    if views:
        s += f" · median {short(int(statistics.median(views)))} views · top {short(max(views))}"
    hidden = sum(1 for r in rows if r["platform"] == "Instagram" and r["likes"] is None)
    if hidden:
        s += f" · {hidden} with likes hidden by the creator"
    if len(views) < len(rows):
        s += f" · {len(rows) - len(views)} without a view count"
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--idea", required=True)
    ap.add_argument("--queries", nargs="+", required=True, help="the phrasings, in the order searched")
    ap.add_argument("--ig", nargs="+", type=Path, default=[])
    ap.add_argument("--ig-rows", type=int)
    ap.add_argument("--ig-hash")
    ap.add_argument("--tiktok", type=Path)
    ap.add_argument("--vs-recent", nargs="+", default=[], metavar="CODE=MEDIAN/N",
                    help="from creator-median.js: Instagram video code = the creator's recent-Reels median "
                         "(Instagram-only views) / how many Reels it covers")
    ap.add_argument("--transcripts", type=Path, metavar="DIR",
                    help="folder of <code>.md / <video id>.md transcripts from transcribe.py and tiktok_transcript.py")
    ap.add_argument("--drop", type=int, nargs="+", default=[], metavar="N",
                    help="leave out videos found only by these phrasings (1-based), e.g. one that drifted off the idea")
    ap.add_argument("--dir", type=Path, help="folder for the CSV and candidates (default: the working folder)")
    ap.add_argument("--out", type=Path, help="exact CSV path; overrides --dir")
    ap.add_argument("--top", type=int, default=25, help="rows to print (0 = all)")
    ap.add_argument("--sort", choices=("send", "views"), default="send",
                    help="send (default): by shares then likes per 1,000 views, see above; views: by views alone")
    a = ap.parse_args()
    if a.ig and (a.ig_rows is None or not a.ig_hash):
        sys.exit("error: --ig needs --ig-rows and --ig-hash from __igsearch.checksum()")
    if not a.ig and not a.tiktok:
        sys.exit("error: give --ig, --tiktok, or both")

    ig = load_ig(a.ig, a.ig_rows, a.ig_hash) if a.ig else []
    tt = load_tt(a.tiktok) if a.tiktok else []
    dropped = {"Instagram": 0, "TikTok": 0}
    if a.drop:
        drop = set(a.drop)

        def keep(r):
            qs = {int(q) for q in str(r["queries"]).split(",") if q.strip().isdigit()}
            if qs and qs <= drop:
                dropped[r["platform"]] += 1
                return False
            return True

        ig, tt = [r for r in ig if keep(r)], [r for r in tt if keep(r)]
    rows = ig + tt
    # "versus this creator's recent Reels": the video's Instagram-only views over the median
    # Instagram-only views of the creator's recent Reels.
    recent = {}
    for spec in a.vs_recent:
        m = re.fullmatch(r"([A-Za-z0-9_-]+)=(\d+(?:\.\d+)?)/(\d+)", spec.strip())
        if not m:
            sys.exit(f"error: --vs-recent expects CODE=MEDIAN/N, got {spec!r}")
        recent[m.group(1)] = (float(m.group(2)), int(m.group(3)))
    unmatched = set(recent) - {r.get("code") for r in ig}
    for r in rows:
        spec = recent.get(r.get("code")) if r["platform"] == "Instagram" else None
        if spec and spec[0] > 0 and r.get("ig_only_views") is not None:
            r["vs_recent_reels"] = round(r["ig_only_views"] / spec[0], 2)
            r["recent_reels_median"], r["recent_reels_n"] = int(round(spec[0])), spec[1]
    if a.transcripts:
        attach_transcripts(rows, a.transcripts)
    today = datetime.date.today()
    for r in rows:
        r["age_days"] = age_days(r.get("posted"), today)
        v, lk, cm = r["views"], r["likes"], r["comments"]
        # (likes + comments) / views; unknown when likes are hidden
        r["engagement_pct"] = round(100 * (lk + (cm or 0)) / v, 2) if v and lk is not None else None
        r["views_per_follower"] = round(v / r["followers"], 2) if v and r.get("followers") else None
        qs = [int(q) for q in str(r["queries"]).split(",") if q.strip().isdigit()]
        r["found_by"] = " | ".join(a.queries[q - 1] for q in qs if 0 < q <= len(a.queries))
        r["best_rank"] = r["rank"]
        add_rates(r)
    rows.sort(key=lambda r: (r["views"] is None, -(r["views"] or 0)))
    ranked = send_order(rows) if a.sort == "send" else 0

    if a.out is None:
        slug = re.sub(r"[^a-z0-9]+", "-", a.idea.lower()).strip("-")[:60] or "idea"
        folder = a.dir or Path.cwd()
        folder.mkdir(parents=True, exist_ok=True)
        a.out = folder / f"research-{slug}-{datetime.date.today().isoformat()}.csv"
    with a.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r[k]) for k in OUT_COLS})

    print(f'Idea: "{a.idea}"')
    print("Phrasings: " + " · ".join(f'{i} "{q}"' for i, q in enumerate(a.queries, 1)))
    if a.ig:
        print(summary("Instagram", ig))
    if a.tiktok:
        print(summary("TikTok", tt))
    if a.drop:
        names = ", ".join(f'{n} "{a.queries[n - 1]}"' for n in a.drop if 0 < n <= len(a.queries))
        print(f"Left out {dropped['Instagram'] + dropped['TikTok']} videos found only by {names} "
              f"({dropped['Instagram']} Instagram, {dropped['TikTok']} TikTok)")
    for line in timeline(rows, today):
        print(line)
    if a.sort == "send":
        bases = sorted({r["rate_basis"] for r in rows})
        print(f"Ranked by shares per 1,000 views, then likes per 1,000, among the {ranked} videos with "
              f"{short(RANK_MIN_VIEWS)}+ views and a share count; the rest follow by views. Views here are "
              + ", ".join(bases) + ". Instagram gives no saves for other people's Reels. "
              "Why sends: Instagram ranks Reels by sends per reach first, then likes per reach.")
    else:
        print("Sorted by views (--sort views).")
    low = [r for r in rows if r.get("low_reactions")]
    if low:
        print(f"Low reactions (likes + comments under {LOW_REACTIONS_PCT:g}% of views, at {short(RANK_MIN_VIEWS)}+ views): "
              f"{len(low)}, marked ⚠. Possibly boosted, or a flop." + (" Listed last." if a.sort == "send" else ""))
    unchecked = sum(1 for r in rows if r.get("reactions_pct") is None and (r["_rank_views"] or 0) >= RANK_MIN_VIEWS)
    if unchecked:
        print(f"{unchecked} video{'s' if unchecked != 1 else ''} with {short(RANK_MIN_VIEWS)}+ views {'have' if unchecked != 1 else 'has'} likes hidden, so reactions can't be checked.")
    checked = [r for r in rows if r.get("vs_recent_reels") is not None]
    if checked:
        print(f"vs recent Reels ({len(checked)} checked): the video's Instagram-only views divided by the median "
              "Instagram-only views of the creator's recent Reels. A guide to \"did it beat their usual\".")
    if unmatched:
        print("warning: --vs-recent codes not among the Instagram rows: " + ", ".join(sorted(unmatched)))
    # Instagram gives no saves for other people's Reels, so a Saves/1K column would be
    # blank on every Instagram row: shown only when a platform that has saves is in the table.
    saves = any(r["platform"] != "Instagram" for r in rows)
    if not saves:
        print("No Saves/1K column: Instagram doesn't show saves on other people's Reels.")
    print(f"CSV: {a.out}")
    print()

    shown = rows if a.top == 0 else rows[: a.top]
    vs = bool(checked)
    print("| # | | Views | Shares/1K | Likes/1K |" + (" Saves/1K |" if saves else "") + " Eng. |"
          + (" vs recent |" if vs else "") + " Account | Posted | Video |")
    print("|---:|---|---:|---:|---:|" + ("---:|" if saves else "") + "---:|" + ("---:|" if vs else "")
          + "---|---|---|")
    rate = lambda x: "–" if x is None else f"{x:g}"
    for i, r in enumerate(shown, 1):
        cap = (r["caption"] or "").replace("|", "/").replace("[", "(").replace("]", ")")
        cap = cap[:45].rstrip() + "…" if len(cap) > 45 else cap
        # (likes + comments) over the same views the rates use, so it matches the flag
        eng = f"{r['reactions_pct']}%" if r.get("reactions_pct") is not None else "–"
        if r.get("low_reactions"):
            eng += " ⚠"
        tag = "IG" if r["platform"] == "Instagram" else "TT"
        vsr = (f" {r['vs_recent_reels']:g}x |" if r.get("vs_recent_reels") is not None else " – |") if vs else ""
        sav = f" {rate(r.get('saves_per_1k_views'))} |" if saves else ""
        print(f"| {i} | {tag} | {short(r['views'])} | {rate(r.get('shares_per_1k_views'))} | "
              f"{rate(r.get('likes_per_1k_views'))} |{sav} {eng} |{vsr} "
              f"@{r['account']} | {posted_label(r)} | "
              f"[{cap or 'video'}]({r['url']}) |")
    if len(shown) < len(rows):
        print(f"\n{len(rows) - len(shown)} more in the CSV.")

    # Picked candidates: each transcript under its video's stats, also saved next to the CSV.
    picked = [r for r in rows if r.get("transcript_file")]
    if picked:
        out = [f'# Candidates for "{a.idea}"', ""]
        for r in picked:
            stats = [f"{short(r['views'])} views", f"{short(r['likes'])} likes", f"{short(r['comments'])} comments",
                     f"{short(r['shares'])} shares"]
            if r.get("saves") is not None:
                stats.append(f"{short(r['saves'])} saves")
            if r.get("engagement_pct") is not None:
                stats.append(f"{r['engagement_pct']}% engagement")
            if r.get("shares_per_1k_views") is not None:
                stats.append(f"{r['shares_per_1k_views']:g} shares per 1K views")
            if r.get("low_reactions"):
                stats.append("low reactions for its views")
            if r.get("vs_recent_reels") is not None:
                stats.append(f"{r['vs_recent_reels']:g}x vs this creator's recent Reels")
            body = Path(r["transcript_file"]).read_text(encoding="utf-8").splitlines()
            body = body[1:] if body and body[0].startswith("# ") else body  # drop the file's own title
            out += [f"## {r['platform']}: @{r['account']}, {posted_label(r)}", "",
                    " · ".join(stats) + "  ", r["url"], "",
                    f"> {r['caption']}" if r.get("caption") else "", ""] + body + [""]
        cand = a.out.with_name(a.out.stem + "-candidates.md")
        cand.write_text("\n".join(out), encoding="utf-8")
        print(f"\nCandidates with transcripts ({len(picked)}): {cand}\n")
        print("\n".join(out))


if __name__ == "__main__":
    main()
