# Platform facts behind the checker's defaults

Checked on the web on **2026-11-16**. Each fact has a status:

- **Confirmed:** Instagram or Meta says it in their own words.
- **Reported:** Instagram announced it, but we read the words only through press coverage, or sources disagree.
- **Estimate:** nothing official exists, so the number is a default you can change.

Every number is a flag on `scripts/check_caption.py`. When Instagram changes a rule, pass the new value, then update this file and `DEFAULTS` in the script.

## Caption length: 2,200 characters (confirmed)

Meta's Instagram Platform reference describes the `caption` parameter of the media endpoint as "Maximum 2200 characters, 30 hashtags, and 20 @ tags."
Source: [developers.facebook.com, IG User Media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media). The page has no date. Its newest dated changelog entry is 9 Jul 2025. Read 2026-11-16.

That page documents publishing through the API. Guides that cover the app give the same 2,200 for posts, carousels and Reels, and we found no source giving a different number for the app.

Not settled: whether an emoji counts as one character or two. Meta doesn't say. The checker fails on the count a reader would make (code points). It only warns when the caption would go over if emoji counted double (UTF-16 units), so you can trim before Instagram refuses it.

Flag: `--max-chars` (default 2200).

## Hashtags: 5 per post (reported, from Instagram's own announcement)

On **18 December 2025**, Instagram's @creators account posted on Threads: "Instagram will gradually update the number of hashtags that you can include in a caption for a reel or post to five." The press linked that post and quoted it. The previous maximum was 30.

- Social Media Today, Andrew Hutchinson, published 18 Dec 2025. It quotes the @creators post, links it ([threads.com/@creators/post/DSalXGPCWM4](https://www.threads.com/@creators/post/DSalXGPCWM4)) and says a 2025 test had held many users to three. [Article](https://www.socialmediatoday.com/news/instagram-implements-new-limits-on-hashtag-use/808309/)
- Business Today, 19 Dec 2025: the limit dropped "from 30 to just 5", announced via @creators. [Article](https://www.businesstoday.in/technology/news/story/no-more-hashtag-stuffing-instagram-limits-hashtag-usage-to-just-5-per-reel-and-post-507444-2025-12-19)
- Blog du Modérateur, 19 Dec 2025: five per post or Reel. [Article](https://www.blogdumoderateur.com/instagram-limite-hashtags-5-par-publication/)
- Later, updated 21 Apr 2026: a hard 5-hashtag limit on posts and Reels since December 2025. [Article](https://later.com/blog/instagram-hashtags/)

So the claim that circulates (five per post, from 18 December 2025) is **confirmed as an announcement by Instagram's own creators account**. Two caveats:

1. The announcement says "gradually", so some accounts may have kept a higher limit for a while.
2. Meta's API reference above still said 30 on 2026-11-16, and Instagram's Help Center page on hashtags did not load for us. A few blogs still say 30 for that reason.

Not verified: whether hashtags in your own first comment count toward the five (Later says they do).

The checker defaults to the newer, stricter rule. Flag: `--max-hashtags` (default 5).

Context: the same coverage reports Adam Mosseri's long-standing position that hashtags help a post get found in search but do not increase its reach. That is why the skill treats hashtags as optional.

## Where the feed cuts to "... more" (estimate)

Instagram does not publish this number. Third-party guides agree on **about 125 characters in the feed**, and some describe it as about two lines. They also say the cut moves with screen width, font size, line breaks and app version. Examples, read 2026-11-16: [Sendible](https://www.sendible.com/insights/instagram-character-limit), [Bitly](https://bitly.com/blog/instagram-character-limit/), [Hootsuite caption preview tool](https://www.hootsuite.com/social-media-tools/social-media-caption-preview).

**Phone vs. other places:** the Reels screen shows less, because the caption sits over the video. Only one guide we found gives a figure for it, about 55 to 60 characters ([GrowthScribe](https://growthscribe.com/instagram-caption-character-limit/)), so treat it as weak. Desktop web shows the caption beside the post and cuts later. The checker models the phone feed and the phone Reels screen, because that is where most people see a caption.

How the checker cuts: at whichever comes first, N characters (counting the account name shown in front, if you pass `--handle`) or the end of the Nth line. A line break in the caption ends a line.

Flags: `--feed-chars` (125), `--feed-lines` (2), `--reel-chars` (60), `--reel-lines` (1). If you can see your own phone, post a test as a draft and adjust these flags to match it.

## Search reads the caption (confirmed, older source)

Adam Mosseri, "Breaking Down How Instagram Search Works", about.instagram.com, **25 Aug 2021**: search tries to "match what you type with relevant usernames, bios, captions, hashtags and places". The same post advises: "put keywords and hashtags in the caption, not the comments." [Post](https://about.instagram.com/blog/announcements/break-down-how-instagram-search-works/)

This is why the checker wants each search term as plain words in the caption. The source is from 2021, and Instagram has said little officially since. Later reports that search now also looks at the image and video come only from second-hand accounts we could not trace to Instagram.

## Links in captions (reported)

Ordinary accounts can't click caption links: a URL shows as plain text. In **March 2026** Instagram began **testing** clickable caption links for Meta Verified subscribers, with a monthly cap, reported by [PPC Land](https://ppc.land/instagram-tests-clickable-links-in-post-captions-for-meta-verified-users/) and [Dataconomy, 13 Mar 2026](https://dataconomy.com/2026/03/13/instagram-tests-clickable-caption-links-for-meta-verified-users/). We found no announcement of a general rollout.

The checker fails on a link by default. `--allow-links` turns that into a warning for accounts that have the feature.

## Our own rules, not Instagram's

These are writing choices the skill makes. They are not platform limits:

- exactly one call to action
- a concrete first line
- an emoji density of at most 4 per 100 words, and no run of 3 or more

Change them freely.
