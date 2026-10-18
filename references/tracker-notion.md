# Tracker: Notion

`settings.tracker_data_source` is the database's data source (`collection://...`). Tool names below are those of the Notion connector (`Notion:<tool>`); if the host names them differently, use the equivalent tool.

| Operation | How | On failure |
|---|---|---|
| Find a company's rows | `Notion:notion-query-data-sources` with SQL on the data source, filtering `Company` (or `Notion:notion-search` inside it); compare names with `tracker.py normalize "<name>"` | Same role with an open status (Applied or further): stop and show the row |
| Add a row | `Notion:notion-create-pages` with the data source as parent and the columns from `common.md` | Notion error: retry once, then stop and show the row so nothing is lost |
| Update a row | `Notion:notion-fetch` the page, save its values and your changes as JSON, run `tracker.py merge current.json changes.json --today <date>`, then write the merged values with `Notion:notion-update-page` | `merge` exit 2: the change breaks a tracker rule; don't write it, tell the user |
| Stats rows | SQL: `SELECT "Company","Role","Level","Status","Furthest stage","Rounds reached","Reached final round","Country","Fit score","Date tailored" FROM "<data source>"`, save as a JSON list, run `stats.py rows.json` | Query fails: say so; never compute stats from a partial result |
| New target country | Add it to the `Country` options with `Notion:notion-update-data-source` | |
| Settings change | Edit only that line on the settings page (`Notion:notion-update-page`) | |

| Situation | Action | Why |
|---|---|---|
| Notion is not connected or times out | Say so and stop writing; offer local mode | A half-written tracker is worse than none |
| Several databases named like a tracker | Use only the one `tracker_data_source` points to | The user may have their own tracker |
| Shared workspace | Recommend a personal workspace in Setup | Compensation targets are private |
