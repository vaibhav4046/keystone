# Design-partner / usage outreach

The one cap that code cannot move is evidence: judges read the Impact criterion as illustrative
because there is no real team using it and no real incident it has prevented. The fix is not more
code, it is one honest conversation with someone who lives this problem. Below is a short outreach
message you can send to a platform or CODEOWNERS lead on a team that runs GitLab Ultimate with
Orbit, plus where to send it and what to ask for. Even one reply with a concrete war story moves
the Impact story from "I estimate" to "a team that does this told me."

No em-dashes, written to be forwarded as-is.

---

## The message (short version, for a DM or a comment)

Subject: a 2am-page problem on big monorepos, and a graph-native gate for it

Hi <name>, I built a small open-source tool for a specific failure on large GitLab monorepos and
I am looking for one person who has actually lived it to tell me where I am wrong.

The failure: two merge requests, different files, no merge conflict, both pass review, and they
break together because one changed a function the other depended on. The normal review surface
cannot see it. The Orbit call graph can. Keystone reads the Orbit graph, flags the collision,
computes a safe merge order, and then governs the change with a tamper-evident gate that refuses an
approval contradicting a prior rejection.

I am not selling anything and it is MIT-licensed. I would value fifteen minutes of your time on two
questions: how often does a silent cross-MR break actually bite your team, and what would the gate
have to do for you to put it in front of a reviewer. Live demo and code are here: <links>. Thank
you either way.

---

## The message (longer version, for an email)

Hi <name>,

I have been building an open-source prototype called Keystone for a problem I keep seeing described
on large GitLab monorepos, and I am trying to find one or two people who own merge-request review at
that scale to sanity-check it against reality.

The problem is the silent cross-MR break. Two engineers open two merge requests on different files.
There is no Git conflict, both pass review independently, and they break together once merged because
one of them changed a symbol the other one depended on. Afterward the post-incident review is hard,
because the approval had no recorded rationale and the log was editable.

Keystone uses the GitLab Orbit code knowledge graph to do two things the normal review surface
cannot. It finds those cross-MR collisions before they merge and computes a safe merge order, and it
binds every approval to the computed blast radius, the human rationale, and a prior-decision check
into a hash-chained record nobody can quietly edit. It is a GitLab-native extension, not a separate
product, and the onboarding is a merge-request hook or a CI gate because the graph is already
indexed for Orbit customers.

What I do not have is field evidence, and that is exactly what I am asking you for. I would value a
short call on three questions:

1. How often does a silent cross-MR break, or a merge that quietly broke transitive callers, actually
   cost your team real hours in a quarter. Even a rough number or one concrete story helps.
2. When you approve a risky change, what do you wish you could see at that moment that you cannot see
   today.
3. If a gate refused an approval that contradicted a past rejection of the same change, would that be
   a help or an annoyance, and where is the line.

I am not selling anything, there is nothing to buy, and the code is MIT-licensed and public. If it is
useful, great, and if it is wrong, your telling me why is just as valuable.

Live demo: <live link>
Code: <repo link>

Thank you for reading this far.

<your name>

---

## Where to send it

- The GitLab Transcend hackathon community channel or Discord: the most on-topic audience, people
  there already use Orbit. Ask for one reviewer who runs CODEOWNERS at scale.
- A targeted post in r/devops or r/gitlab framed as "does this cross-MR break happen to you," asking
  for stories rather than promoting the tool. The stories are the asset.
- Anyone in your own network who works on a platform or developer-experience team at a company with a
  large monorepo on GitLab Ultimate.
- If you get one substantive reply, quote it (with permission) in the Devpost Impact section. A single
  real "this happens to us about once a quarter and costs us a day" sentence is worth more than any
  estimate.

## What counts as a win here

You are not trying to land a customer before the deadline. You are trying to convert one line in the
submission from "I estimate the cost" to "a team that reviews merge requests at this scale told me how
often this bites them." That is the difference between an Impact score that reads as hypothetical and
one that reads as grounded, and it is the only lever on Impact that code cannot pull for you.
