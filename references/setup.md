# Setup

Runs on first use, or when the user asks to change settings. Tracker columns and values are in `common.md`.

## Rules

| Situation | Action | Why |
|---|---|---|
| Settings page or `kitty-settings.md` already exists | Reuse it and the tracker it points to; never create a second one | Setup may run twice |
| User changes one setting | Edit only that line; don't rerun the interview. New location in Notion: add the country to the tracker's Country options | Keeps everything else as it is |
| A database is named like a tracker but settings don't point to it | Don't write into it; reuse only a tracker the settings point to or the user names | It may be the user's own tracker |
| Notion connected | Recommend a personal workspace | Colleagues could see the compensation target |
| No Notion | Local mode: same interview, then `tracker.csv` (header row with the `common.md` columns) and `kitty-settings.md` in the templates folder, with full paths for folders and `tracker_data_source`; existing files are reused, never overwritten | All modes except Sync work without connectors |
| Order | Interview, then tracker, then settings page | Country options depend on the answers |

## Steps

| # | Step | Use | On failure |
|---|---|---|---|
| 1 | Notion: ask once which page should hold the job search (offer to create a private "Job Search" page) | `Notion:notion-search`, `Notion:notion-create-pages` | Notion not connected: local mode |
| 2 | Interview in small groups (two or three questions at a time), with defaults, skipping anything the user doesn't want to set (list below) | user | Templates folder unreachable or without a .docx: say what access is missing before going on |
| 3 | Create the tracker: Notion database "Application tracker" under the parent page with the `common.md` columns (Country options from the locations), and record its data source (`collection://...`); local: `tracker.csv` | `Notion:notion-create-database`, or a file write | Creation fails: stop and say what failed; don't create the settings page without a tracker |
| 4 | Create the settings page "Kitty Settings" (child of the parent) or `kitty-settings.md` with the template below | `Notion:notion-create-pages`, or a file write | |
| 5 | Sync on: update an existing sync task or create one at the chosen time with the prompt below; save the time in `sync_schedule` | scheduling tool | No scheduling tool: give the user the prompt to paste into their scheduler |
| 6 | Confirm in one message: tracker link, settings link, sync on or off, "share a job posting to start" | reply | |

## Interview

1. **Basics**: name for file names; templates folder; output folder (can be the same); file name pattern (default `{name}_cv_{company}_{role}.docx`).
2. **Targets**: target levels; strong, adjacent and avoided domains.
3. **Logistics**: target locations; remote OK; max on-site days per week; languages with level.
4. **Money**: compensation target (yearly total, currency); stored only in the private settings.
5. **CV**: page limit (default 2); priority role to lead with (default the current role); template rules (for example "Head of roles: template A").
6. **Guardrails**: claims never to make; writing rules (default "no em dashes; metric units").
7. **Sync**: daily Gmail sync, time and timezone (default weekdays 06:00 local); days without a reply before No response (default 45).

## Settings template

One `key: value` per line, lists comma-separated. Tell the user they can edit it directly at any time.

```
name: 
templates_folder: 
output_folder: 
file_name_pattern: {name}_cv_{company}_{role}.docx
tracker_data_source: collection://...
page_limit: 2
target_levels: 
strong_domains: 
adjacent_domains: 
avoid_domains: 
locations: 
remote_ok: yes
max_onsite_days: 
languages: 
compensation_target: 
priority_role: 
template_rules: 
guardrails: 
writing_rules: no em dashes; metric units
sync_enabled: no
sync_schedule: 
no_response_days: 45
last_sync: 
dashboard_url: 
```

## Scheduled sync prompt

> Use the kitty-has-a-job skill in Sync mode. Read the settings page (or kitty-settings.md), scan Gmail since the last sync, update the Application tracker, and finish with a three-line summary of what changed.
