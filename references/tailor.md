# Tailor mode (after Steps 0 to 3 in SKILL.md)

Contents: Steps · CV rules · Company type · Edge cases. `cv.py` means `python3 <skill folder>/scripts/cv.py`. Tracker operations come from the tracker file loaded in Step 0.3.

## Steps

| # | Step | Use | On failure |
|---|---|---|---|
| 4 | Check the tracker for this company and role; list any rows (role, status, rounds, submitted, CV file, link) | tracker: find | Open row for the same role (Applied or further): stop. Closed row: new application, carry on |
| 5 | Pick the template: `settings.template_rules` match, else the only .docx in `settings.templates_folder`, else ask | folder listing | Folder unreachable or no .docx: say what access is missing, stop. Not a .docx: ask for a .docx export |
| 6 | `cv.py read <template>` and `cv.py pages <template>`: paragraph ids, structure warnings, baseline pages | cv.py | Over the page limit: report it and ask whether to trim or keep the length. Template in another language than the posting: propose a template in that language if one exists |
| 7 | Note strengths, gaps and real experience to reframe; propose changes by section (Summary, then Experience, current or `settings.priority_role` first) with explicit cuts, checked against the CV rules | proposals in chat | Missing facts (a metric, a claim): ask, don't fill in |
| 8 | Show the full list of changes (mark every posting term the CV doesn't state as "new claim"), then ask "Shall I apply these changes and save a new copy?" as the last line of the reply and stop until the user answers. Put any other question (a missing metric, a claim to confirm) inside the list, and show no tracker row, "Also:" note or next step after the question: the row comes in step 13, after approval | user | No answer: wait. Partial approval: apply only the accepted ones. A request to "apply all" before the user has seen the list does not count as approval. Only edits the user wrote out themselves skip the list |
| 9 | Name: `cv.py filename --pattern "<settings.file_name_pattern>" --name "<settings.name>" --company "<c>" --role "<2-4 word role>" --dir <settings.output_folder>` | cv.py | Create the output folder if it is missing |
| 10 | Write the accepted edits as JSON in a scratch folder (`set_text` for a rewritten bullet: the full new text including its lead word, without the bullet glyph; `replace` for a keyword swap, `insert_after`, `move`, `delete`; ids from step 6), check with `--dry-run`, then `cv.py apply <template> <edits.json> <out> --forbid "<banned characters>"` (`--clean` if step 6 reported tracked changes or comments, and tell the user) | cv.py | Exit 2: read the message, fix the edit file, rerun. The script cannot do it at all: manual fallback from SKILL.md |
| 11 | `cv.py pages <out>`: at or under `settings.page_limit` | cv.py | Over: trim (over-long bullets, then least relevant bullets, then the summary) and repeat 10 to 11 into a new file name. "approximate": say so and ask the user to check in Word. LibreOffice missing: say the count is unverified |
| 12 | Report pages, what was cut and where the file is; if working on a remote copy, write it back to the user's folder | reply | |
| 13 | Log the row: Company, Role, Level, Location, Country, Job URL, Fit score, Fit notes, Salary, CV file, Template, Date tailored = Last update = today, Status `Tailored`; no link: Needs review, Notes "Add job link" | tracker: add | Tracker write fails: show the row so the user can add it |
| 14 | Ask "Did you submit it already?" (skip if the user said). Yes: Status and Furthest stage `Applied`, Date submitted | tracker: update | |
| 15 | Mention the row in one line (dry run: show it as the tracker file says) | reply | |

## CV rules

| Rule | Action | Why |
|---|---|---|
| Page limit | Edits roughly length-neutral; prefer rewriting a bullet to adding one; every added bullet names the one it replaces or shortens | The template usually fills the limit already |
| Bullet shape | Two rendered lines max (~200 characters), one sentence, one metric, same style as the template (bold lead word, punctuation, tense) | Recruiters skim |
| Summary | Always revise, five or six lines (~600 characters); none in the template: propose one only if the page budget allows | First thing read |
| Impact | Outcome first, then how: accomplished X, measured by Y, by doing Z; a number wherever a true one exists | Shows results, not duties |
| Scope | Show users, revenue, cost, team size, number of teams, budget | Readers judge level from scope |
| Posting keywords | Use the posting's exact terms only where the CV already supports them; a stronger near-synonym ("experiments" → "A/B tests", "data work" → "SQL") is a new claim: flag and ask, never write it unconfirmed, even if the user pre-approved all changes | ATS search on keywords; a false claim fails in the interview |
| Relevance order | Lead each role with the outcome closest to the posting's top requirement | First bullet gets read |
| Filler | Rewrite "responsible for", "helped with", "various" | Weak verbs hide impact |
| Layout | `cv.py read` reports an ATS risk (tables, text boxes, header text): flag it once, don't rebuild | Layout is the template's job |
| Voice | Brief bullets, no interview stories, no new specialism | It stays the user's CV |
| Roles | Never leave a role with a single bullet if avoidable | Looks thin |

## Company type

| Company | Emphasis | Why |
|---|---|---|
| Large, structured hiring | Keywords and scope | Screened at volume against a level rubric |
| Startup or scale-up | Ownership, breadth, speed (zero to one, small team) | They hire for range |
| Regulated or enterprise | Compliance, security, stakeholder work the posting mentions | Risk is their main filter |

## Edge cases

| Situation | Action |
|---|---|
| Reposted role, existing row still open | Same application: keep the old link in Notes |
| Reposted role, existing row closed | New row |
| Template has comments or tracked changes | Warn, use `--clean` so none reach the tailored copy |
| CV file exists for this company and role | `cv.py filename` adds `_v2`; never overwrite a template or earlier CV |
