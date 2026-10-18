#!/usr/bin/env python3
"""Funnel stats for the kitty-has-a-job skill.

  python3 stats.py TRACKER.csv --today YYYY-MM-DD [--dashboard URL]
  python3 stats.py ROWS.json   --today YYYY-MM-DD      (rows exported from Notion: a list of objects)

Prints the fixed report (table, overlap line, step conversion, live list), the
sanity checks, stale Tailored rows and, once there is enough data, the level and
fit lines. The model adds only the one-sentence headline and at most two lines
of observation.

Exit codes: 0 ok (check the SANITY line), 1 usage error.
"""
import csv, datetime as dt, json, sys
from collections import OrderedDict

OPEN = ["Applied", "Screening", "Interviewing", "On hold"]


def truthy(v):
    return v is True or str(v).strip().lower() in ("true", "yes", "1", "__yes__", "x", "checked")


def num(v):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return None


def pct(n, d):
    return "n/a" if not d else f"{int(n * 100 / d + 0.5)}%"


def load(path):
    if path.endswith(".json"):
        rows = json.load(open(path, encoding="utf-8"))
        return [{k: ("" if v is None else v) for k, v in r.items()} for r in rows]
    return list(csv.DictReader(open(path, encoding="utf-8-sig", newline="")))


def counts(rows):
    c = {"sent": len(rows)}
    st = lambda s: sum(1 for r in rows if r.get("Status") == s)
    c["rej"], c["wd"], c["nr"], c["offer_status"] = st("Rejected"), st("Withdrawn"), st("No response"), st("Offer")
    c["open"] = sum(1 for r in rows if r.get("Status") in OPEN)
    rr = lambda n: sum(1 for r in rows if (num(r.get("Rounds reached")) or 0) >= n)
    c["r1"], c["r2"], c["r3"] = rr(1), rr(2), rr(3)
    c["fin"] = sum(1 for r in rows if truthy(r.get("Reached final round")))
    c["offer"] = sum(1 for r in rows if r.get("Furthest stage") == "Offer")
    return c


def line(label, c):
    s = c["sent"]
    return (f"| {label} | {s} | {pct(c['rej'], s)} | {pct(c['r1'], s)} | {pct(c['r2'], s)} | {pct(c['r3'], s)}"
            f" | {pct(c['fin'], s)} | {pct(c['offer'], s)} | {pct(c['open'], s)} |")


def main(a):
    if not a or any(x in ("-h", "--help") for x in a) or a[0] == "help":
        print(__doc__); return 0 if a else 1
    today = dt.date.fromisoformat(a[a.index("--today") + 1]) if "--today" in a else dt.date.today()
    dash = a[a.index("--dashboard") + 1] if "--dashboard" in a else ""
    rows = load(a[0])
    sent = [r for r in rows if r.get("Status") != "Tailored"]
    tailored = [r for r in rows if r.get("Status") == "Tailored"]
    stale = []
    for r in tailored:
        try:
            d = dt.date.fromisoformat(str(r.get("Date tailored", "")).strip()[:10])
            if (today - d).days > 14:  # two weeks: long enough to have sent it, short enough to still matter
                stale.append(f"{r.get('Company')} {r.get('Role')} (tailored {d}, {(today - d).days} days ago)")
        except ValueError:
            pass
    if not sent:
        print(f"No applications sent yet; {len(tailored)} tailored and waiting.")
        if stale:
            print("STALE TAILORED (ask whether sent): " + "; ".join(stale))
        return 0

    c = counts(sent)
    by_country = OrderedDict()
    unclear = 0
    for r in sorted(sent, key=lambda r: str(r.get("Country") or "~")):
        k = str(r.get("Country") or "").strip()
        if not k:
            unclear += 1
            k = "Remote / unclear"
        by_country.setdefault(k, []).append(r)
    by_country = OrderedDict(sorted(by_country.items(), key=lambda kv: -len(kv[1])))

    print("FACTS FOR THE HEADLINE: " + f"sent {c['sent']}, round 1 {pct(c['r1'], c['sent'])}, "
          f"live {c['open']}, offers {c['offer']}")
    print()
    print("| | Sent | Rejected | Round 1 | Round 2 | Round 3+ | Final | Offer | Open |")
    print("|---|---|---|---|---|---|---|---|---|")
    print(line("**All**", c))
    for k, rs in by_country.items():
        print(line(k, counts(rs)))
    print()
    print(f"Columns overlap and don't sum to 100%. No response: {pct(c['nr'], c['sent'])}.")
    print()
    print(f"Step conversion: Round 1 -> 2: {pct(c['r2'], c['r1'])}, 2 -> 3: {pct(c['r3'], c['r2'])}, "
          f"Final -> Offer: {pct(c['offer'], c['fin'])}.")
    print()
    live = []
    for r in sent:
        if r.get("Status") in OPEN:
            rn = num(r.get("Rounds reached")) or 0
            stage = r.get("Status") + (", final round" if truthy(r.get("Reached final round")) else f", round {rn}" if rn else "")
            live.append(f"{r.get('Company')} {r.get('Role', '')} ({stage})".replace("  ", " "))
    print("Live: " + (", ".join(live) if live else "none") + ".")
    if unclear:
        print(f"(Country empty on {unclear} row(s), counted as Remote / unclear; infer from company and location if you can and say how many.)")

    if c["sent"] >= 10:
        lv = OrderedDict()
        for r in sent:
            lv.setdefault(r.get("Level") or "unknown", []).append(r)
        print("\nLevel: " + ", ".join(f"{k} {pct(counts(v)['r1'], len(v))} to round 1 ({len(v)} sent)" for k, v in lv.items()))
    scored = [r for r in sent if num(r.get("Fit score")) is not None]
    if len(scored) >= 5:
        hi = [r for r in scored if num(r.get("Fit score")) >= 4]
        lo = [r for r in scored if num(r.get("Fit score")) <= 3]
        print(f"\nFit: round 1 rate fit 4-5 {pct(counts(hi)['r1'] if hi else 0, len(hi))} ({len(hi)} sent), "
              f"fit 1-3 {pct(counts(lo)['r1'] if lo else 0, len(lo))} ({len(lo)} sent)")
        if len(scored) >= 15 and hi and lo and counts(hi)["r1"] / len(hi) <= counts(lo)["r1"] / len(lo):
            print("Fit scores are not predicting round 1: propose adjusting target levels or domains.")
    if dash:
        print(f"\nLive funnel: {dash}")

    # sanity checks (exact counts, so rounding cannot hide an error)
    s = c["sent"]
    checks = [
        ("outcomes add up", c["rej"] + c["wd"] + c["nr"] + c["open"] + c["offer_status"] == s),
        ("Round 1 >= Round 2 >= Round 3+", c["r1"] >= c["r2"] >= c["r3"]),
        ("Round 1 >= Final >= Offer", c["r1"] >= c["fin"] >= c["offer"]),
        ("countries add up", sum(len(v) for v in by_country.values()) == s),
    ]
    bad = [n for n, ok in checks if not ok]
    print("\nSANITY: " + ("all checks pass" if not bad else "FAILED: " + ", ".join(bad) +
                          " (check the tracker rows before reporting)"))
    print("(Final is a checkbox, not a round number: Final above Round 3+ is normal.)")
    if stale:
        print("STALE TAILORED (ask whether sent): " + "; ".join(stale))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
