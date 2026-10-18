#!/usr/bin/env python3
"""Tracker helpers for the kitty-has-a-job skill. The rules live here, so
they are the same on every run.

Local CSV tracker:
  python3 tracker.py find    TRACKER.csv --company C [--role R] [--url U]
  python3 tracker.py add     TRACKER.csv ROW.json --today D [--dry-run]
  python3 tracker.py update  TRACKER.csv --row N CHANGES.json --today D [--dry-run] [--manual]
  python3 tracker.py stale   TRACKER.csv --today D [--days 45] [--apply] [--dry-run]
  python3 tracker.py recorded TRACKER.csv --row N --date D --subject S
Any tracker (Notion too):
  python3 tracker.py merge   CURRENT.json CHANGES.json --today D [--manual]   prints the merged row
  python3 tracker.py window  --today D [--last-sync D]                        sync scan window
  python3 tracker.py normalize "Company GmbH"                                 name used for matching

Rows are dicts keyed by the tracker's column names. CHANGES may include
"Notes" (appended as a new line, never overwriting). History columns never go
down, and Status never moves backwards, unless --manual (the user's own edit).
Exit codes: 0 ok, 1 usage error, 2 refused (a rule or a value check failed; nothing
written; the message says which), 3 stop (find: this role already has an open
application). On 2, correct the change; never work around the rule.
"""
import csv, datetime as dt, io, json, os, re, sys

COLUMNS = ["Company", "Role", "Level", "Status", "Furthest stage", "Rounds reached", "Reached final round",
           "Country", "Location", "Job URL", "Fit score", "Fit notes", "Salary", "CV file", "Template",
           "Date tailored", "Date submitted", "Last update", "Next step", "Last email", "Needs review", "Notes"]
STATUS = ["Tailored", "Applied", "Screening", "Interviewing", "Offer", "Rejected", "Withdrawn", "No response", "On hold"]
ACTIVE = ["Tailored", "Applied", "Screening", "Interviewing", "Offer"]          # forward order
FINAL = ["Rejected", "Withdrawn"]                                              # closed for good
PAUSED = ["No response", "On hold"]                                            # can reopen to an active status
OPEN = ["Applied", "Screening", "Interviewing", "On hold"]
STAGES = ["Applied", "Screening", "Interviewing", "Assignment", "Final round", "Offer"]
LEVELS = ["Junior", "Mid", "Senior", "Staff/Principal", "Lead/Manager", "Head/Director", "VP/Exec"]
DATE_COLS = ["Date tailored", "Date submitted", "Last update"]
LEGAL = r"\b(gmbh|ag|se|inc|ltd|llc|bv|nv|plc|sa|sas|srl|oy|ab|kg|co kg|corp|corporation|limited|holding|group)\b"


class Refused(Exception):
    pass


def normalize(name):
    s = (name or "").lower()
    s = re.sub(r"\(via [^)]*\)", "", s)
    s = s.replace("&", " and ").replace(".", "")
    s = re.sub(LEGAL, "", s)
    s = re.sub(r"[^a-z0-9äöüß]+", " ", s)
    return " ".join(s.split())


def truthy(v):
    return str(v).strip().lower() in ("true", "yes", "1", "__yes__", "x", "checked")


def num(v):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return 0


def date(v):
    v = (v or "").strip()
    return dt.date.fromisoformat(v) if v else None


def read_csv(path, allow_missing=False):
    if allow_missing and not os.path.exists(path):
        return COLUMNS, [], "\n", b""   # dry run against a tracker that does not exist yet
    if not os.path.exists(path):
        raise Refused(f"tracker file not found: {path}")
    raw = open(path, "rb").read()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    header = next(csv.reader(io.StringIO(text))) if text.strip() else COLUMNS
    return header, rows, nl, raw


def write_csv(path, header, rows, nl):
    buf = io.StringIO()
    wr = csv.DictWriter(buf, fieldnames=header, lineterminator=nl, extrasaction="raise")
    wr.writeheader()
    for r in rows:
        wr.writerow({k: r.get(k, "") for k in header})
    open(path, "w", encoding="utf-8", newline="").write(buf.getvalue())


def check_values(row):
    for c in DATE_COLS:
        if row.get(c):
            try:
                dt.date.fromisoformat(row[c])
            except ValueError:
                raise Refused(f"{c} must be YYYY-MM-DD, got {row[c]!r}")
    if row.get("Status") and row["Status"] not in STATUS:
        raise Refused(f"Status {row['Status']!r} is not one of {STATUS}")
    if row.get("Furthest stage") and row["Furthest stage"] not in STAGES:
        raise Refused(f"Furthest stage {row['Furthest stage']!r} is not one of {STAGES}")
    if row.get("Level") and row["Level"] not in LEVELS:
        raise Refused(f"Level {row['Level']!r} is not one of {LEVELS}")


def merge(cur, ch, today, manual=False):
    """Apply CHANGES to CURRENT under the tracker rules. Returns (new_row, list of change lines)."""
    new = dict(cur)
    log = []
    ch = dict(ch)
    note = ch.pop("Notes", None)
    unknown = [k for k in ch if k not in COLUMNS]
    if unknown:
        raise Refused(f"unknown columns {unknown}")
    for k, v in ch.items():
        v = "" if v is None else (("true" if v else "false") if isinstance(v, bool) else str(v))
        old = cur.get(k, "") or ""
        if k == "Status" and not manual and v and old and v != old:
            if old in FINAL:
                raise Refused(f"Status is {old} (closed); only the user can change it (--manual)")
            if v in ACTIVE and old in ACTIVE and ACTIVE.index(v) < ACTIVE.index(old):
                raise Refused(f"Status cannot move backwards ({old} -> {v})")
        if not manual:
            if k == "Furthest stage" and old in STAGES and v in STAGES and STAGES.index(v) < STAGES.index(old):
                log.append(f"kept Furthest stage {old} (not lowered to {v})"); continue
            if k == "Rounds reached" and num(v) < num(old):
                log.append(f"kept Rounds reached {old} (not lowered to {v})"); continue
            if k == "Reached final round" and truthy(old) and not truthy(v):
                log.append("kept Reached final round true"); continue
            if k == "Date submitted" and old:
                log.append(f"kept Date submitted {old}"); continue
        if v != old:
            new[k] = v
            log.append(f"{k}: {old or '(empty)'} -> {v or '(empty)'}")
    if note:
        new["Notes"] = "; ".join(x for x in [cur.get("Notes", ""), note] if x)
        log.append(f"Notes += {note}")
    if log and not manual and "Last update" not in ch:
        new["Last update"] = today
    check_values(new)
    return new, log


def fmt(i, r):
    return (f"row {i}: {r.get('Company')} | {r.get('Role')} | {r.get('Status')} | furthest {r.get('Furthest stage') or '-'}"
            f" | rounds {r.get('Rounds reached') or 0} | submitted {r.get('Date submitted') or '-'} | CV {r.get('CV file') or '-'}"
            f" | {r.get('Job URL') or 'no link'}")


def row_at(rows, i):
    if not 0 <= i < len(rows):
        raise Refused(f"row {i} does not exist (rows are numbered 0 to {len(rows) - 1}; use `find` to get the number)")
    return rows[i]


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def main(a):
    if not a or any(x in ("-h", "--help") for x in a) or a[0] == "help":
        print(__doc__)
        return 0 if a else 1
    try:
        cmd = a[0] if a else ""
        today = opt(a, "--today", dt.date.today().isoformat())
        dry = "--dry-run" in a
        manual = "--manual" in a
        if cmd == "normalize":
            print(normalize(a[1]))
        elif cmd == "window":
            t = dt.date.fromisoformat(today)
            ls = opt(a, "--last-sync")
            # first sync looks back a week; never more than 30 days, which keeps
            # one run small and is longer than any normal gap between syncs
            start = dt.date.fromisoformat(ls) if ls else t - dt.timedelta(days=7)
            start = max(start, t - dt.timedelta(days=30))
            print(f"scan emails dated {start.isoformat()} to {t.isoformat()} (inclusive)")
        elif cmd == "merge":
            new, log = merge(json.load(open(a[1])), json.load(open(a[2])), today, manual)
            print("\n".join(log) or "no change")
            print(json.dumps(new, ensure_ascii=False))
        elif cmd == "find":
            _, rows, _, _ = read_csv(a[1])
            c = normalize(opt(a, "--company"))
            role, url = (opt(a, "--role") or "").lower(), opt(a, "--url")
            def same_co(x):
                x = normalize(x)
                return bool(c) and (x == c or x.startswith(c + " ") or c.startswith(x + " "))
            hits = [(i, r) for i, r in enumerate(rows) if same_co(r.get("Company"))]
            if not hits:
                print("no rows for this company")
            for i, r in hits:
                same = (url and r.get("Job URL") == url) or (role and r.get("Role", "").lower() == role)
                state = "OPEN" if r.get("Status") in OPEN + ["Tailored", "Offer"] else "closed"
                print(fmt(i, r) + f" | {state}" + (" | SAME ROLE" if same else ""))
            if any(((url and r.get("Job URL") == url) or (role and r.get("Role", "").lower() == role)) and
                   r.get("Status") in ["Applied", "Screening", "Interviewing", "Offer", "On hold"] for _, r in hits):
                print("STOP: this role already has an open application (Applied or further)")
                return 3
        elif cmd == "add":
            header, rows, nl, raw = read_csv(a[1], allow_missing=dry)
            row = json.load(open(a[2]))
            unknown = [k for k in row if k not in header]
            if unknown:
                raise Refused(f"columns not in tracker: {unknown}")
            row = {k: ("" if row.get(k) is None else str(row.get(k)).lower() if isinstance(row.get(k), bool) else str(row.get(k, ""))) for k in header}
            row.setdefault("Rounds reached", "0")
            for k, d in (("Rounds reached", "0"), ("Reached final round", "false"), ("Needs review", "false"),
                         ("Last update", today)):
                if not row.get(k):
                    row[k] = d
            check_values(row)
            if dry:
                print("DRY RUN, not written. Row:", json.dumps(row, ensure_ascii=False)); return 0
            buf = io.StringIO()
            csv.DictWriter(buf, fieldnames=header, lineterminator=nl).writerow(row)
            with open(a[1], "ab") as f:
                if raw and not raw.endswith(b"\n"):
                    f.write(nl.encode())
                f.write(buf.getvalue().encode("utf-8"))
            print(f"added row {len(rows)}: {row['Company']} | {row['Role']} | {row['Status']}")
        elif cmd == "update":
            header, rows, nl, _ = read_csv(a[1])
            i = int(opt(a, "--row"))
            ch_path = [x for x in a[2:] if x.endswith(".json")][0]
            new, log = merge(row_at(rows, i), json.load(open(ch_path)), today, manual)
            print(f"row {i} ({rows[i].get('Company')} | {rows[i].get('Role')}):")
            print("  " + ("\n  ".join(log) or "no change"))
            if dry:
                print("DRY RUN, not written"); return 0
            if log:
                rows[i] = new
                write_csv(a[1], header, rows, nl)
        elif cmd == "stale":
            header, rows, nl, _ = read_csv(a[1])
            days = int(opt(a, "--days", "45"))  # default for settings.no_response_days: most replies come within 6 weeks
            t = dt.date.fromisoformat(today)
            hit = []
            for i, r in enumerate(rows):
                sub = date(r.get("Date submitted"))
                if r.get("Status") != "Applied" or not sub or (t - sub).days <= days:
                    continue
                m = re.match(r"(\d{4}-\d{2}-\d{2})", r.get("Last email", "") or "")
                if m and dt.date.fromisoformat(m.group(1)) > sub:
                    continue
                hit.append(i)
                print(f"row {i}: {r['Company']} | {r['Role']} | submitted {sub} ({(t - sub).days} days, no later email) -> No response")
            if not hit:
                print(f"no Applied rows older than {days} days without a later email")
            elif dry or "--apply" not in a:
                print("DRY RUN, not written" if dry else "(add --apply to set them to No response)")
            if "--apply" in a and hit and not dry:
                for i in hit:
                    rows[i], _ = merge(rows[i], {"Status": "No response",
                                                 "Notes": f"{today}: no reply {days}+ days after applying"}, today)
                write_csv(a[1], header, rows, nl)
                print(f"set {len(hit)} row(s) to No response")
        elif cmd == "recorded":
            _, rows, _, _ = read_csv(a[1])
            r = row_at(rows, int(opt(a, "--row")))
            d, s = opt(a, "--date"), opt(a, "--subject")
            hit = (r.get("Last email", "") or "").strip() == f"{d}: {s}" or \
                any(x.strip().startswith(d) for x in (r.get("Notes", "") or "").split(";"))
            print("already recorded: skip" if hit else "not recorded")
        else:
            print(__doc__); return 1
    except Refused as ex:
        print(f"REFUSED: {ex}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
