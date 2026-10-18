# Common rules (all modes, both trackers)

## Tracker columns

| Column | Values | Notes |
|---|---|---|
| Company | text | Title in Notion; agency posts: `Unknown (via <agency>)` |
| Role | text | Posting title |
| Level | `Junior`, `Mid`, `Senior`, `Staff/Principal`, `Lead/Manager`, `Head/Director`, `VP/Exec` | |
| Status | `Tailored`, `Applied`, `Screening`, `Interviewing`, `Offer`, `Rejected`, `Withdrawn`, `No response`, `On hold` | Current state |
| Furthest stage | `Applied` < `Screening` < `Interviewing` < `Assignment` < `Final round` < `Offer` | History |
| Rounds reached | number | 1 = first step after the CV screen; history |
| Reached final round | checkbox (`true`/`false` in CSV) | History; a final can happen at round 2 |
| Country | one per target country, plus `Remote`, `Other` | Map cities to countries |
| Location | text | City |
| Job URL | url | The posting itself |
| Fit score | 1-5 | |
| Fit notes | text | One line |
| Salary | text | Published band or marked estimate |
| CV file | text | File name only |
| Template | text | Template file name |
| Date tailored, Date submitted, Last update | date | YYYY-MM-DD |
| Next step | text | |
| Last email | text | `YYYY-MM-DD: <subject>` |
| Needs review | checkbox | Sync unsure, or data missing |
| Notes | text | Append only, `YYYY-MM-DD: ...`, lines joined with `; ` |

## Tracker rules

`tracker.py` enforces these (`update` for CSV, `merge` before every Notion write).

| Situation | Action | Why |
|---|---|---|
| Any change | Never delete a row | The history is the dataset for stats |
| Status change | Only forward (Tailored → Applied → Screening → Interviewing → Offer), or to Rejected, Withdrawn, No response, On hold | A later email never undoes progress |
| Row is Rejected or Withdrawn | Don't change its status; a new application is a new row | Closed means closed |
| Row is No response or On hold | May reopen to an active status | Late replies happen |
| History columns | Never lowered (Furthest stage, Rounds reached, Reached final round) | Stats count the furthest point reached |
| Notes | Append, never overwrite | Keeps the audit trail |
| Date submitted already set | Keep it | First submission counts |
| User edited a row by hand | Never revert, even if it lowers history (`--manual`) | The user's edit is authoritative |
| Same company, other legal form (GmbH, SE, Inc, B.V.) | Treat as the same company (`tracker.py normalize`) | Avoids duplicate rows |

## Formats

| Item | Format | Why |
|---|---|---|
| Dates | YYYY-MM-DD | Sorts and parses everywhere |
| CV file name | `settings.file_name_pattern`, default `{name}_cv_{company}_{role}.docx`, via `cv.py filename` | Lowercase, `&` → `and`, no forbidden characters, `_v2` if taken |
| Dry run | `tracker_data_source: dry run` → never write; show each row or change in the reply instead | Used by evals and previews |
| Writing | `settings.writing_rules` on everything written into the CV or tracker | User preference |
