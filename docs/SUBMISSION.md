# Campaory: DEV submission kit

Verify every rule against the live challenge page before submitting. This kit is built from the rules as understood on 16 Oct 2026: Hacktoberfest Open-Source AI Challenge, Week 2 "Side Hustle". New project started within 12 to 18 Oct. Deadline 18 Oct 11:59 PM PDT (19 Oct about 12:29 PM IST). Writing quality is judged first.

## 1. Checklist

- [ ] Public GitHub repo with README, licence, setup, model details, limitations, sample data
- [ ] Live URL (Render) and, if claimed, the .tech domain
- [ ] DEV post published with the required template and tags (copy exactly from the challenge page)
- [ ] Demo video or screenshots in the post, under 3 minutes
- [ ] Real user story with real numbers (section 4)
- [ ] Open-source AI named clearly: which Gemma model, how it was served
- [ ] Category claims backed by evidence (section 3)
- [ ] All links checked from a phone

## 2. Article outline (write in your own voice)

Working title options: "I built a campaign tool that refuses to invent your event details" / "Facts first, then posts: planning a Hacktoberfest event with Gemma".

1. The problem: your real event (PyData Indore Hacktoberfest), the actual mess of reposting, a specific moment where a detail was wrong or late. Two or three paragraphs, concrete.
2. What I built: one paragraph and one screenshot. Try-it link first.
3. The idea that matters: facts are confirmed by the human, the model only writes copy, code checks every date, time and link. Show one guard catch (a real flagged post).
4. How Gemma is used: tasks, why an open model, how it is served, what failed (JSON format, latency, quota). Honest numbers from TEST_PLAN section 6.
5. Change impact demo: change a time, see which posts to update, published post untouched. GIF.
6. Guest-first: why no login wall; what happened with testers; how many chose to save.
7. What organizers said: three quotes with permission, one thing I changed because of it.
8. Architecture in one picture (from ARCHITECTURE section 1).
9. What I would do next and limitations.
10. Links.

Writing rules for yourself: first person, specific numbers, one failure story, no marketing adjectives, no "revolutionary", no AI-sounding triplets. Read it aloud once.

## 3. Category evidence

| Category | Claim only if | Evidence to show |
|---|---|---|
| Overall | Real users tried it | Trial notes, quotes, numbers |
| Gemma | Gemma generates the extraction and posts in production | Model id, prompts, `/api/config` output, eval table |
| Render | Deployed on Render | URL, `render.yaml`, screenshot of the service |
| .tech domain | Domain claimed and serving | The domain URL, TLS screenshot |
| Sentry Agent Tracing | Traces captured for model calls | Screenshot of a trace with latency/tokens; link in README |
| Entire | Sessions really recorded | Session link or export |
| My First User bonus | A real first user | Their feedback, with permission |

Do not claim a category without its evidence. Judges look.

## 4. Numbers to collect while testing

Per trial: tester role, time from landing to first approved post, facts corrected, posts accepted unchanged / with edits / rejected, guard flags (true / false), did they sign in to save (yes/no, why), price they would pay (if offered), one quote.

Overall: model calls, failures, median latency (from logs), tokens.

## 5. README outline (repo)

Title and one-liner · Try it (link) · Why · Screens (3 images) · How it works (diagram) · Open-source AI (model, serving, prompts location) · Run locally · Configuration · Tests · Limitations (English-first, guard false positives, in-memory rate limit, free-tier cold start, no publishing) · Roadmap · Licence.

## 6. Demo video script (under 3 minutes)

0:00 problem in one sentence · 0:15 Try a sample event, no login · 0:35 facts screen, fix one wrong fact, gate unlocks · 1:00 plan · 1:15 posts for four platforms, guard flag fixed · 1:45 change a time, affected posts, diff, published post untouched · 2:20 Save, sign in, same campaign appears · 2:40 close with the link.
