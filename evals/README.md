# Evals

Nothing here runs automatically; run each set when the table says.

| File | What it checks | How to run | When |
|---|---|---|---|
| `test_scripts.sh` | The scripts in `scripts/`: CV read/edit/page count/file names on five CV layouts, tracker rules, sync helpers, stats numbers, CLI behaviour. No model, about a minute. | `bash evals/test_scripts.sh` from the repo root (`--fast` skips LibreOffice) | After every script change |
| `test_cv_pipeline.sh` | The manual fallback commands in `references/cv-editing.md`. No model. | `bash evals/test_cv_pipeline.sh` | After changing the fallback |
| `evals.json` | 8 core tasks: score, skip, tailor proposal (ask before editing), dictated edits with tracker write, stats, sync, German CV, open duplicate. Checkable assertions. | Ask Claude: "run the evals for kitty-has-a-job with skill-creator", comparing against the previous version | Before every release |
| `triggers.json` | 16 queries marked should / should not trigger (near-misses: cover letters, interview prep, negotiation, proofreading) | skill-creator's trigger test (`run_eval` / `run_loop` with `triggers.json`) | When the description changes or triggering misbehaves |
| `regression.json` | 14 cases from earlier fixes (CRLF endings, sync window, Final above Round 3+, file names, template layouts...) | Same as `evals.json` | Before bigger releases, or when touching their area |

Run each task case in its own fresh folder holding a copy of `evals/files` and an empty `evals/output`, outside the skill folder: cases write files and one drops a settings file into the working folder, so shared folders leak between runs.

All inputs live in `files/` and use a made-up person (Alex Example). Test CVs cover five layouts: Word numbered bullets with a hidden content control (`templates/cv_main.docx`), typed `•` bullets, a table layout, a German CV with sentences split across runs, and a template with tracked changes, a comment and a text box. Regenerate them with `python3 evals/files/make_fixtures.py`.

## When something fails in real use

1. Write down the input that broke it (posting, settings line, email) and what went wrong.
2. Add a fixture to `files/` that reproduces it with fake data. Never commit a real CV, real emails or real salaries.
3. Add a case to `regression.json` (or `evals.json` if it is a core path): next free `id`, a short `name`, the `prompt`, and one `expectations` line per thing that must be true.
4. Run it and confirm it fails on the current skill.
5. Fix the skill (or the script, with a test in `test_scripts.py`), rerun all evals, and only release when every case passes.
6. Note the fix in `CHANGELOG.md`, with the eval id.

## Writing good expectations

- One checkable fact per line ("The fit score is 1 or 2"), not a vibe ("the answer is good").
- Prefer facts a script can check (file exists, page count, no em dash) over judgment calls.
- Cover what must not happen too ("No CV file is created").
