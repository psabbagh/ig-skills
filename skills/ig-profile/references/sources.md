# Sources behind the rubric

Checked on the web on **2026-11-16**. Every `platform` criterion in `rubric.json` names one or more ids below. A `judgement` criterion is our own view of what makes a stranger follow; where it leans on a number from outside Instagram, the id is listed too.

Status:

- **Confirmed:** Instagram or Meta says it in its own words, on a page we read.
- **Reported:** Instagram announced it, but we read it through press coverage, or only third-party guides give it.

When Instagram changes something, update the entry here, then the criterion in `rubric.json`, then the limits at the top of `scripts/score_profile.py`.

## ig-search-2021: search matches names, usernames and bios (confirmed)

Adam Mosseri, "Breaking Down How Instagram Search Works", about.instagram.com, **25 Aug 2021**. Search is matched by the text typed, against "usernames, bios, captions, hashtags and places". Its advice for showing up: use a handle and profile name related to what you post, include the name people know you by, and put keywords (and your location, for a local business) in the bio.
[Post](https://about.instagram.com/blog/announcements/break-down-how-instagram-search-works/). Read 2026-11-16.

Used by: `name.search_term`, `name.known_by`, `handle.findable`, `bio.keywords`. The post is from 2021 and Instagram has published nothing newer on profile search that we found; the advice still reads as current on the page.

## ig-help-bio: bio up to 150 characters, public (confirmed)

Instagram Help Center, "Add a bio to your Instagram profile": "You can write a bio of up to 150 characters on your Instagram profile", and anyone can see it.
[Article](https://help.instagram.com/728994388226960/). No date on the page. Read 2026-11-16.

Used by: `bio.keywords`, `bio.scannable`, and the 150 limit in the script.

## ig-help-website: up to 5 links (confirmed)

Instagram Help Center, "Add a website to your Instagram profile" (iPhone and Android versions): "You can add up to 5 websites to your Instagram profile", added under Edit profile > Links, and they can be reordered. The page says the feature isn't available on computers.
[Article](https://help.instagram.com/362497417173378/). Read 2026-11-16.

## five-links-2023: only the first link shows in full (reported)

Instagram launched multiple bio links on **18 Apr 2023**, announced by Mark Zuckerberg. Coverage says only the first link appears on the profile and the rest sit behind a tap ("and 2 others").
[TechCrunch, 18 Apr 2023](https://techcrunch.com/2023/04/18/instagram-takes-on-linktree-and-others-with-support-for-up-to-5-links-in-bio/), [9to5Mac, 18 Apr 2023](https://9to5mac.com/2023/04/18/instagram-multiple-links-in-bio/), [PetaPixel, 18 Apr 2023](https://petapixel.com/2023/04/18/instagram-now-lets-users-have-five-links-in-their-bio/).

The Help Center does not describe how the links display, so "first link shows" is reported, not confirmed.

Used by: `link.present`, `link.first_is_best`.

## ig-help-pin and pin-2022: up to 3 pinned posts (confirmed)

Instagram Help Center, "Pin a post to the top of your profile on Instagram": "You can pin up to 3 posts you share on Instagram to the top of your profile." The menu item is now called "Pin to main grid".
[Article](https://help.instagram.com/318456537074409/). Read 2026-11-16.

The feature launched for posts and Reels on **7 Jun 2022**: [iPhone in Canada, 8 Jun 2022](https://www.iphoneincanada.ca/2022/06/08/instagram-now-enables-users-to-pin-three-posts-or-reels-to-their-profile/), [PetaPixel, 7 Jun 2022](https://petapixel.com/2022/06/07/you-can-now-pin-photos-to-your-instagram-profile-grid/).

Used by: `pinned.used`.

## ig-help-highlights: highlights stay on the profile (confirmed)

Instagram Help Center, "Add a story to your Story Highlights": "You can add stories to appear on your profile as highlights, even after they disappear."
[Article](https://help.instagram.com/813938898787367/). Read 2026-11-16.

Instagram publishes no limit on highlight title length; titles that are too long are cut under the circle, so the rubric asks for one or two words without giving a number.

Used by: `highlights.exist`.

## ig-help-profile-info: changing name and username (confirmed)

Instagram Help Center, "How to change your Instagram profile information": name, username and photo are changed in Accounts Center or Edit profile. "If your account reaches a lot of people, your username change may need to be reviewed", and "Your followers may be notified of your username change."
[Article](https://help.instagram.com/583107688369069/). Read 2026-11-16.

Why it matters: a handle change has a cost, so the skill suggests one only when the handle loses real points, and says so. We could not confirm a limit on how often the name can be changed for ordinary accounts (the Help Center's assistant mentioned twice in 14 days only for Meta Verified), so the skill tells the person to expect a limit and choose the name once.

## ig-help-professional: creator and business accounts (confirmed)

Instagram Help Center, "About professional accounts on Instagram": professional accounts are Business or Creator, Creator being "best for public figures, content producers, artists and influencers", with tools to grow, monetize and understand growth.
[Article](https://help.instagram.com/138925576505882/). Read 2026-11-16.

Whether showing the category on the profile helps is our judgement, hence `account.professional_category` is marked judgement.

## grid-2025: the profile grid is tall, not square (reported)

In **January 2025** Instagram replaced square profile thumbnails with taller rectangles, announced by Adam Mosseri in his Stories; he said most uploads are vertical and cropping them to squares was "pretty brutal". Coverage gives 4:5 (Buffer) or 3:4 (others); the exact ratio is reported inconsistently.
[Social Media Today](https://www.socialmediatoday.com/news/instagram-chief-flags-coming-changes-profile-grid-displays/724532/), [Buffer](https://buffer.com/resources/instagram-grid/), [Engadget, test in 2024](https://www.engadget.com/social-media/instagrams-experimental-profile-grid-has-rectangular-images-instead-of-squares-160007086.html).

Related, reported: since **June 2026** the app lets people reorder their grid ("Reorder grid"), pinned posts staying on top. [ABC7, 9 Jun 2026](https://abc7.com/post/meta-debuts-new-instagram-feature-allows-users-rearrange-posts-profile-grid/19262454/), [Social Media Today](https://www.socialmediatoday.com/news/instagram-releases-profile-grid-rearranging/). The skill mentions it as an option for fixing the top rows; check the app has it before relying on it.

Used by: `grid.covers_fit`.

## name-length-guides: about 30 characters for name and username (reported, third-party only)

Instagram's Help Center gives no number for the name field or the username that we could find. Third-party guides agree on 30 for each, for example [Bitly](https://bitly.com/blog/instagram-character-limit/) and [Sendible](https://www.sendible.com/insights/instagram-character-limit), read 2026-11-16. The script only warns past 30; the app itself is the final word.

Used by: `name.readable`.

## posting-frequency: no required frequency (reported)

Instagram publishes no posting frequency. Adam Mosseri has said in videos that posting more tends to bring more reach but warned about burnout, and that successful accounts range from one post a month to several a day; the often-quoted "two feed posts a week, two stories a day" comes from a 2021 Q&A we read only second-hand. [RouteNote](https://routenote.com/blog/how-often-you-should-post-on-instagram/), read 2026-11-16.

So `posting.recent_regular` is judgement: it rewards a recent, steady pace, not a number.

## What is judgement

Everything marked `judgement` in `rubric.json`: who the bio is for, proof, the one ask, the photo, highlight names and order, what the pins do, whether the grid shows one topic, and posting pace. These are our own view of what makes a stranger who lands on the profile follow. Change their points freely; the script only insists the total stays 100.
