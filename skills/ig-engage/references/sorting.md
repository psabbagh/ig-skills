# How the sorter decides

Read this when a comment landed in the wrong group, or someone asks how the order is made.

`engage.py sort` uses word rules, in this order. The first rule that matches decides the group.

1. **Yours**: written by `--me` (or the post owner, from the browser reader). Not counted.
2. **Spam or noise (spam)**: a link or a domain, "link in bio", "check my page", "DM us to collab", promotion, giveaways, crypto and forex, follow-for-follow. Spammers often say "collab", so this runs before the lead rule.
3. **Used the keyword**: the keyword as a whole word, its plural, or spelled out letter by letter ("G U I D E"). A one-letter typo ("guid") counts only when the comment is three words or fewer, so a longer comment that happens to contain a near-miss word doesn't. Phrases work ("skill pack"). If the same comment also asks something it is tagged `+question`; if it asks about price or working together, `+lead`.
4. **Friend tags**: a comment that is only @mentions is a share, so it goes to noise with "tagged a friend". No reply needed.
5. **Possible lead**: price, cost, rates, "how much" (but not a question about the creator's own result, such as "how much time does it save you?", which is a question), hire, freelance, consult, "your services", "work with you", collaborate, partner, "book a call", "can you build this", "for my business / agency / clients", coaching, mentoring.
6. **Question**: a question mark, or it starts with how, what, why, where, when, which, who, can, does, is, are, will, would, should, anyone, "is there", "have you".
7. **One other word**: with a keyword given, a one-word comment that isn't it (and isn't praise) goes to noise tagged `maybe-keyword`; the report lists these words with counts, since people often comment the keyword from another Reel.
8. **Emoji only**: positive emoji are praise; anything else is noise.
9. **Worth a real reply**: 8 words or more, or 5 or more with a sign of their own view or experience ("I tried", "in my experience", "but", "actually", "instead", a number).
10. **Praise**: short and positive ("so good", "needed this", "game changer", 🔥).
11. Anything left: 4 words or more is worth a reply; shorter is noise.

The rules are English. Comments in other languages mostly fall to praise, substance or noise by length; skim them.

## Already answered

A comment counts as answered when the creator replied in its thread, or wrote a comment starting with `@its-author` after it. With pasted text, an indented `you: @them ...` line under a comment is a thread reply. "Liked by creator" is not an answer.

The browser reader fetches replies under up to 120 threads; past that it says so in its note, and answers in the threads it skipped are not seen.

## The order

Not-yet-answered comments, ranked by a score: lead 100, question 80, worth a reply 60, keyword 40, praise 20; `+lead` adds 70 and `+question` adds 45; each like adds 0.5, up to 20. Ties go to the oldest comment, which has waited longest. A person who commented the keyword twice appears once.

Why leads first: a person asking what it costs is the most valuable comment on the post and the one most likely to go cold. Questions next because an unanswered question is visible to everyone who reads the comments. Keyword comments come after real conversation because their main answer is the DM, not a public reply.

## What it can't see

- Comments nobody can load: ones Instagram's filter hid, ones caught by your hidden words, ones from restricted accounts, and deleted ones. Instagram's comment count still includes them, and it counts replies too. The reader gets everything that loads on the post's page; when Instagram's number is higher, the header says how many comments and replies were read and that the rest are these. The gap can be large: in testing, a post showing 18 as its count had 4 that load (two comments and two replies), on its own page and to the reader alike.
- Whether you already sent someone the DM, beyond your own reply saying so ("Sent! Check your DMs" marks that person, and `dms --new-only` leaves them out). Keep the handles you've sent in a file and pass it to `dms --skip`.
