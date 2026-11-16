# Writing replies and keyword DMs

Read this before writing replies under the creator's own post. `engage.py replies` lists which comments get one; write a reply for each, save them as `@handle: reply` lines, and check them with `--drafts`.

## Every reply

- Answer what that person said, in one or two lines. If the reply would fit under any comment, it isn't a reply.
- Use only facts the creator gave you or that are in the post. Missing a fact? Write the reply with `[ ]` where it goes and ask.
- No sales line in a reply to someone who didn't ask. No links in public replies: they aren't clickable in comments and read as spam.
- Vary the openings. Twenty replies that all start "Thanks!" read as automated.
- Match how the creator talks to people, which is usually looser than their captions.

## By group

- **Possible lead**: thank them in a few words and move it to DMs ("Sending you a DM"). Only name a price, a package or availability if the creator gave it to you for this.
- **Question**: the answer itself, short. If the honest answer is "it depends", say on what. If the creator plans a follow-up Reel on it, they may say so, but don't promise one for them.
- **Worth a real reply**: respond to their point: agree with a reason, add one detail, or ask one thing back. Disagreement gets a calm answer, not a defence.
- **Keyword**: the DM is the answer. A public reply is optional and short ("Sent, check your requests"); write one only if the creator replies to keyword comments.
- **Praise**: a short, specific thanks, or nothing. The creator can like it themselves.
- **Spam or noise**: no reply. They can delete or hide it.

## Keyword DMs

- Two or three versions, rotated by `dms -m ... -m ...`. Each one: a hello, the link or resource, and at most one line more (what it is, or one tip for using it). That's it.
- Leave the colon out before the link ("Here's the guide: {link}" reads as a set-up line, and `ig-voice` flags it); "Here's the guide you asked for {link}" or the link on its own line reads as a person.
- Put `{link}` where the link goes; `dms --link` fills it in for each person. `{handle}` fills in their handle and `{keyword}` the word they commented; most DMs read better without them. `check --kind dm` accepts exactly these three and fails any other `{...}`.
- If they also asked something in their comment, the list says so: add the answer to that one DM.
- The creator sends each DM from the app. A DM to someone who doesn't follow them lands in that person's message requests, where it may sit unseen; that's normal, not a failure.
- Sending dozens of identical DMs in a few minutes can trip Instagram's limits. Spread a big list over the day.
