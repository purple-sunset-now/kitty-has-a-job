# Stats mode

| # | Step | Use | On failure |
|---|---|---|---|
| 1 | Get all tracker rows (CSV: the file itself; Notion: the stats query, saved as JSON) | tracker: stats rows | Tracker unreadable: say so, stop. Never report from partial rows |
| 2 | `stats.py <csv or rows.json> --today <date> [--dashboard <settings.dashboard_url>]` | `scripts/stats.py` | `SANITY: FAILED`: look at the rows it names before reporting; never adjust a number by hand |
| 3 | Empty Country rows are counted as "Remote / unclear": infer the country from company and location where you can, say how many | rows | Unclear: leave them as counted |
| 4 | Reply in the format below | reply | Sent = 0: use the script's one-line answer, skip the table |

## Reply format

| Part | Content | Why |
|---|---|---|
| 1 | One bold sentence: sent count, round 1 rate, the most important live process (facts from the script's first line) | Bottom line first |
| 2 | The script's table, overlap line, step conversion and Live line, verbatim | Same numbers every time |
| 3 | At most two short lines of observation; small numbers are signals, not proof | Avoids over-reading |
| 4 | Level and Fit lines if the script printed them; "Live funnel: <url>" if a dashboard is set | Calibrates scoring |
| 5 | Stale Tailored rows in one line, asking whether they were sent | They distort Sent |

The script owns the definitions: Sent = all rows except Tailored; Round 1/2/3+ = Rounds reached ≥ 1/2/3; Final = Reached final round; Offer = Furthest stage Offer; Open = Applied, Screening, Interviewing, On hold. Final above Round 3+ is normal (a final can happen at round 2).
