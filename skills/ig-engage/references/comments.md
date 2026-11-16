# Comments on other people's posts

Read this before writing a comment on someone else's post.

## What earns a reply and gets read

A comment shows under someone else's post, to their audience. The ones that get read and answered are about that post, not about the commenter:

- **One specific thing** from the post: a step, a number, a claim, a line from the caption. Name it.
- **Then one move**: a short reaction with a reason, a real question the post didn't answer, a short "I did this and X happened" from the creator's own experience, or a respectful "this didn't work for me because…".
- One to three lines. Long comments get cut behind "more".

## What not to write

- Praise that fits any post ("Great content!", "So true 🔥"). The checker fails these.
- A pitch, a link, "check my page", "DM me". The checker fails these; it is also what gets an account's comments hidden.
- Hashtags.
- A claim about the creator's own results, clients or numbers they didn't give you.
- What the top comments already say.

## Why the log

A creator who comments a lot drifts into a template: the same opening, the same "This is so X, Y" shape, the same closing question. Other creators and their followers notice, and it reads as automated. `engage.py check` compares each new comment with every comment in the log and refuses:

- the same line, or nearly (80% the same words in order, or 60% of the content words shared);
- the same first three words;
- the same sentence shape (function words kept, other words blanked: "this is so _ , _ it for _ ."), when 85% alike and at least five tokens long.

It warns when the last three words match, when half the recent comments start with the same word, when most end on a question, and when the same account got three or more of the last 30 comments.

Log only comments the creator says they posted, as posted. The file is plain Markdown and theirs to edit.
