# Sync mode

Reads Gmail and moves tracker rows forward. Gmail tools are named as in the Gmail connector (`Gmail:<tool>`); use the equivalent if the host differs. In tests, an emails JSON the user names replaces Gmail.

| # | Step | Use | On failure |
|---|---|---|---|
| 1 | Window: `tracker.py window --today <date> [--last-sync <settings.last_sync>]` | `scripts/tracker.py` | |
| 2 | Find application mail in the window | `Gmail:search_threads`, `Gmail:get_thread` | Gmail not connected or down: say so and stop. Older unrecorded application mail visible: mention it in one line, don't process it |
| 3 | Classify each email by meaning (table below); take the company from the body, since recruiting systems send from no-reply domains | judgment | Unsure what it says: Needs review with a Notes line |
| 4 | Match to rows: find by company (names normalised), then role; skip emails already recorded (`recorded`) | tracker: find, recorded | Several rows and the email names no role: change no status, tick Needs review on each, add a Notes line. No row: add one from the email with Needs review |
| 5 | Combine one row's emails into one change file (scratch folder), then update | tracker: update (CSV) or merge + write (Notion) | Exit 2: the change breaks a rule; skip it and report it |
| 6 | No response: `stale` with `--days <settings.no_response_days>` (default 45) | tracker: no response check | |
| 7 | Write today into `settings.last_sync` (not in dry run) | settings | Write fails: say so; the next run overlaps, which is safe (recorded emails are skipped) |
| 8 | Report in three lines: rows updated, new rows, rows needing review | reply | |

## Email → change

| Email says | Status | History columns | Why |
|---|---|---|---|
| Application received | `Applied` (if `Tailored`) | Furthest stage at least `Applied`; Date submitted if empty | Confirms submission |
| Recruiter or screening call | `Screening` | Rounds reached at least 1 | First step after the CV screen |
| Interview with team or hiring manager | `Interviewing` | Rounds reached +1 per new round; reminders, reschedules and confirmations of a round already in Notes don't count | Counts rounds, not emails |
| Take-home or case study | `Interviewing` | Furthest stage `Assignment`; counts as a round | |
| Final round | `Interviewing` | Reached final round ticked; Furthest stage `Final round` | |
| Offer | `Offer` | Furthest stage `Offer` | |
| Rejection | `Rejected` | unchanged | History keeps how far it got |
| Automated test sent to every applicant | no change | no round | Not a human step |
| Job alert, newsletter, marketing | ignore | | Not about an application |

Always set Last email to `YYYY-MM-DD: <subject>`, add a Notes line (`YYYY-MM-DD round N: <what>` for rounds), and fill an empty Job URL or Country when the email makes it clear.
