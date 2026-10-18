# Tracker: local CSV (and dry run)

`settings.tracker_data_source` is the CSV path (normally `tracker.csv` next to the settings file; a relative path is read from the working folder). Never edit the CSV by hand: Notes and URLs contain commas, and the file's line endings must stay as they are. `tracker.py` handles both.

| Operation | Command | On failure |
|---|---|---|
| Find a company's rows | `tracker.py find <csv> --company "<c>" --role "<r>" --url "<u>"` | Exit 3: this role has an open application; stop and show the rows |
| Add a row | Write the row as JSON in a scratch folder, then `tracker.py add <csv> <row.json> --today <date>` | Exit 2: a value is invalid (status, date, column); fix the JSON |
| Update a row | Changes as JSON (scratch folder), then `tracker.py update <csv> --row N <changes.json> --today <date>` | Exit 2: the change breaks a tracker rule; don't force it, tell the user |
| Is an email recorded? | `tracker.py recorded <csv> --row N --date <d> --subject "<s>"` | |
| No response check | `tracker.py stale <csv> --today <d> --days <settings.no_response_days> --apply` | |
| Stats rows | Pass the CSV straight to `stats.py` | |
| User's own edit | Add `--manual` to `update` | |

## Dry run

| Situation | Action |
|---|---|
| `tracker_data_source: dry run` and the user names a tracker CSV | Read that file; run every write with `--dry-run` |
| `dry run` and no tracker named | Skip tracker checks and say so in one line; don't search for a file |
| A row or change would be written | Show it in the reply as one `|`-separated line with every filled field (at least Company, Role, Status, Fit score, Country, Job URL) |
