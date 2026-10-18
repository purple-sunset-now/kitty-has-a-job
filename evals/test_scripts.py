#!/usr/bin/env python3
"""Deterministic tests for scripts/ (no model). Run from the repo root:
    python3 evals/test_scripts.py          (add --fast to skip LibreOffice page counts)
"""
import csv, filecmp, io, json, os, re, shutil, subprocess, sys, tempfile, zipfile

ROOT = os.getcwd()
S = os.path.join(ROOT, "scripts")
F = os.path.join(ROOT, "evals", "files")
FAST = "--fast" in sys.argv
W = tempfile.mkdtemp()
results = []


def run(script, *args, ok=True):
    r = subprocess.run([sys.executable, os.path.join(S, script), *args], capture_output=True, text=True)
    if ok and r.returncode != 0:
        raise AssertionError(f"{script} {' '.join(args)} failed: {r.stderr or r.stdout}")
    return r


def test(name):
    def deco(fn):
        try:
            fn()
            results.append((name, None))
        except AssertionError as e:
            results.append((name, str(e) or "assertion failed"))
        except Exception as e:
            results.append((name, f"{type(e).__name__}: {e}"))
        return fn
    return deco


def edits(ops):
    p = os.path.join(W, f"e{len(os.listdir(W))}.json")
    json.dump(ops, open(p, "w"))
    return p


def out(name):
    return os.path.join(W, name)


def doc_text(path):
    x = zipfile.ZipFile(path).read("word/document.xml").decode()
    return x


def paras(path):
    from docx import Document
    return Document(path).paragraphs


def ids(path):
    """paragraph text -> id from `cv.py read`."""
    m = {}
    for line in run("cv.py", "read", path).stdout.splitlines():
        g = re.match(r"\s*(\d+) \[[^\]]*\] (.*)", line)
        if g:
            m[g.group(2)] = int(g.group(1))
    return m


def pid(path, start):
    m = ids(path)
    hits = [i for t, i in m.items() if t.lstrip("•\t ").startswith(start)]
    assert len(hits) == 1, f"{start!r}: {hits}"
    return hits[0]


# ---------------- cv.py read ----------------
MAIN = os.path.join(F, "templates", "cv_main.docx")


@test("read: finds hidden content-control bullet that python-docx skips")
def _():
    r = run("cv.py", "read", MAIN).stdout
    assert "adopted by 12,000" in r and "content-control" in r
    assert not any("12,000" in p.text for p in paras(MAIN))


@test("read: flags table, text box, tracked changes, comments, glyph bullets")
def _():
    assert "ATS risk" in run("cv.py", "read", os.path.join(F, "cv_table.docx")).stdout
    r = run("cv.py", "read", os.path.join(F, "cv_tracked.docx")).stdout
    assert "text boxes 1" in r and "tracked changes 2" in r and "comments 1" in r and "--clean" in r
    assert "glyph:•" in run("cv.py", "read", os.path.join(F, "cv_glyph_bullets.docx")).stdout


@test("read: reports fonts")
def _():
    assert "fonts" in run("cv.py", "read", MAIN).stdout


# ---------------- cv.py apply ----------------
@test("apply: replace refuses 0 and 2+ matches and writes nothing")
def _():
    o = out("refuse.docx")
    r = run("cv.py", "apply", MAIN, edits([{"op": "replace", "old": "not in the cv", "new": "x"}]), o, ok=False)
    assert r.returncode == 2 and not os.path.exists(o)
    r = run("cv.py", "apply", MAIN, edits([{"op": "replace", "old": "users", "new": "x"}]), o, ok=False)
    assert r.returncode == 2 and "times" in r.stderr and not os.path.exists(o)


@test("apply: never overwrites the template or an existing file")
def _():
    e = edits([{"op": "replace", "old": "BSc Computer Science", "new": "BSc CS"}])
    assert run("cv.py", "apply", MAIN, e, MAIN, ok=False).returncode == 2
    o = out("once.docx")
    run("cv.py", "apply", MAIN, e, o)
    assert run("cv.py", "apply", MAIN, e, o, ok=False).returncode == 2


@test("apply: set_text keeps bold lead and numbering; hidden bullet kept once; customXml kept; template unchanged")
def _():
    before = open(MAIN, "rb").read()
    o = out("main.docx")
    run("cv.py", "apply", MAIN, edits([
        {"op": "set_text", "p": pid(MAIN, "Responsible"), "text": "Owned partner tools and onboarding flows for the B2B marketplace."},
        {"op": "replace", "old": "ML search ranking", "new": "ML-powered search ranking"},
        {"op": "move", "p": pid(MAIN, "Cut"), "after": pid(MAIN, "Led")},
        {"op": "insert_after", "after": pid(MAIN, "Grew"), "like": pid(MAIN, "Grew"), "text": "Ran 30 partner interviews that shaped the roadmap."},
    ]), o, "--forbid", "—")
    assert open(MAIN, "rb").read() == before
    ps = {p.text: p for p in paras(o)}
    p = ps["Owned partner tools and onboarding flows for the B2B marketplace."]
    assert p.runs[0].text == "Owned " and p.runs[0].bold and not any(r.bold for r in p.runs[1:])
    assert p.style.name == "List Bullet"
    n = ps["Ran 30 partner interviews that shaped the roadmap."]
    assert n.runs[0].bold and n.style.name == "List Bullet"
    x = doc_text(o)
    assert x.count("adopted by 12,000") == 1
    assert "customXml/item1.xml" in zipfile.ZipFile(o).namelist()
    order = [t for t in ids(o)]
    assert order.index(next(t for t in order if t.startswith("Cut"))) > order.index(next(t for t in order if t.startswith("Led")))


@test("apply: two inserts after the same paragraph keep their order")
def _():
    o = out("order.docx")
    g = pid(MAIN, "Grew")
    run("cv.py", "apply", MAIN, edits([
        {"op": "insert_after", "after": g, "like": g, "text": "First new bullet."},
        {"op": "insert_after", "after": g, "like": g, "text": "Second new bullet."}]), o)
    t = [p.text for p in paras(o)]
    assert t.index("First new bullet.") < t.index("Second new bullet.") and t.index("First new bullet.") == t.index(next(x for x in t if x.startswith("Grew"))) + 1


@test("apply: forbid refuses an em dash in new text")
def _():
    r = run("cv.py", "apply", MAIN, edits([{"op": "replace", "old": "BSc Computer Science", "new": "BSc — CS"}]),
            out("dash.docx"), "--forbid", "—", ok=False)
    assert r.returncode == 2


@test("apply: typed '•' bullets keep the glyph, tab and bold lead (also on a cloned bullet)")
def _():
    src = os.path.join(F, "cv_glyph_bullets.docx")
    o = out("glyph.docx")
    run("cv.py", "apply", src, edits([
        {"op": "set_text", "p": pid(src, "Responsible"), "text": "• Owned partner tools and onboarding flows."},
        {"op": "insert_after", "after": pid(src, "Grew"), "like": pid(src, "Grew"), "text": "Ran 30 partner interviews."}]), o)
    for p in paras(o):
        if p.text.startswith("•"):
            assert p.text.startswith("•\t") and p.text.count("•") == 1, p.text
            assert p.runs[1].bold and not p.runs[2].bold, [r.text for r in p.runs]


@test("apply: edits inside table cells keep the table")
def _():
    src = os.path.join(F, "cv_table.docx")
    o = out("table.docx")
    run("cv.py", "apply", src, edits([{"op": "set_text", "p": pid(src, "Responsible"), "text": "Owned partner tools."}]), o)
    from docx import Document
    d = Document(o)
    assert len(d.tables) == 1 and "Owned partner tools." in d.tables[0].cell(1, 1).text


@test("apply: text split across runs (proofing marks) is replaced; German bold lead kept")
def _():
    src = os.path.join(F, "cv_german.docx")
    o = out("de.docx")
    run("cv.py", "apply", src, edits([
        {"op": "replace", "old": "B2B-SaaS und Marktplätzen", "new": "Marktplätzen und B2B-SaaS"},
        {"op": "set_text", "p": pid(src, "Verantwortlich"), "text": "Verantwortet: Partner-Tools und Onboarding für den B2B-Marktplatz."}]), o)
    t = {p.text: p for p in paras(o)}
    assert any("Erfahrung in Marktplätzen und B2B-SaaS." in k for k in t)
    p = t["Verantwortet: Partner-Tools und Onboarding für den B2B-Marktplatz."]
    assert p.runs[0].text == "Verantwortet: " and p.runs[0].bold


@test("apply --clean: removes tracked changes, comments and comment parts")
def _():
    src = os.path.join(F, "cv_tracked.docx")
    o = out("clean.docx")
    run("cv.py", "apply", src, edits([{"op": "replace", "old": "0000000", "new": "1234567"}]), o, "--clean")
    x = doc_text(o)
    assert not re.search(r"<w:(ins|del|delText|commentReference|commentRangeStart)\b", x)
    names = zipfile.ZipFile(o).namelist()
    assert not any("comments" in n for n in names)
    assert b"private reviewer note" not in open(o, "rb").read()
    assert "Based in Berlin." in x and "Loves spreadsheets" not in x and "1234567" in x


@test("apply: delete and move refuse bad ids")
def _():
    assert run("cv.py", "apply", MAIN, edits([{"op": "delete", "p": 999}]), out("bad.docx"), ok=False).returncode == 2


@test("apply --dry-run: validates, prints, writes nothing")
def _():
    o = out("dry.docx")
    r = run("cv.py", "apply", MAIN, edits([{"op": "replace", "old": "BSc Computer Science", "new": "BSc CS"}]), o, "--dry-run").stdout
    assert "DRY RUN" in r and "BSc CS" in r and not os.path.exists(o)


@test("all scripts: --help exits 0, no arguments exits 1")
def _():
    for s in ("cv.py", "tracker.py", "stats.py"):
        assert run(s, "--help").returncode == 0
        assert run(s, ok=False).returncode == 1
    assert run("tracker.py", "update", "--help").returncode == 0 and run("cv.py", "apply", "--help").returncode == 0


# ---------------- cv.py filename / pages ----------------
@test("filename: lowercase, & to and, no forbidden characters, _v2 when taken")
def _():
    a = ["filename", "--name", "Alex_Example", "--company", "Bart & Co. / Retail Labs", "--role", "Senior PM: Pricing?", "--dir", W]
    p = run("cv.py", *a).stdout.strip()
    assert os.path.basename(p) == "alex_example_cv_bart_and_co_retail_labs_senior_pm_pricing.docx", p
    open(p, "w").close()
    assert run("cv.py", *a).stdout.strip().endswith("_pricing_v2.docx")


@test("pages: 1-page and 3-page fixtures")
def _():
    if FAST:
        return
    assert "pages: 1" in run("cv.py", "pages", MAIN).stdout
    assert "pages: 3" in run("cv.py", "pages", os.path.join(F, "cv_too_long.docx")).stdout


# ---------------- tracker.py ----------------
def tcopy(name="tracker.csv", crlf=False):
    p = out(f"t{len(os.listdir(W))}.csv")
    data = open(os.path.join(F, name), "rb").read()
    if crlf:
        data = data.replace(b"\n", b"\r\n")
    open(p, "wb").write(data)
    return p


@test("tracker add: appends, keeps LF and CRLF files as they are, quotes commas")
def _():
    row = out("row.json")
    json.dump({"Company": "Tradeloop", "Role": "Senior PM Search", "Status": "Tailored", "Notes": "a, b; c",
               "Date tailored": "2026-10-15"}, open(row, "w"))
    for crlf in (False, True):
        p = tcopy(crlf=crlf)
        orig = open(p, "rb").read()
        run("tracker.py", "add", p, row, "--today", "2026-10-15")
        new = open(p, "rb").read()
        assert new.startswith(orig)
        assert (b"\r\n" in new) == crlf
        rows = list(csv.DictReader(io.StringIO(new.decode())))
        assert len(rows) == 6 and rows[-1]["Notes"] == "a, b; c" and rows[-1]["Rounds reached"] == "0"


@test("tracker add: rejects unknown columns, bad dates and bad statuses; dry run writes nothing")
def _():
    p = tcopy(); orig = open(p, "rb").read(); row = out("bad.json")
    for bad in ({"Company": "X", "Colour": "red"}, {"Company": "X", "Date tailored": "15.10.2026"}, {"Company": "X", "Status": "Ghosted"}):
        json.dump(bad, open(row, "w"))
        assert run("tracker.py", "add", p, row, ok=False).returncode == 2
    json.dump({"Company": "X", "Status": "Tailored"}, open(row, "w"))
    run("tracker.py", "add", p, row, "--dry-run")
    assert open(p, "rb").read() == orig


@test("tracker update: never lowers history, never moves status back, appends notes")
def _():
    p = tcopy(); ch = out("ch.json")
    json.dump({"Furthest stage": "Screening", "Rounds reached": 1, "Notes": "2026-10-15: note"}, open(ch, "w"))
    r = run("tracker.py", "update", p, "--row", "3", ch, "--today", "2026-10-15").stdout
    row = list(csv.DictReader(open(p)))[3]
    assert row["Furthest stage"] == "Interviewing" and row["Rounds reached"] == "2" and "kept" in r
    assert row["Notes"].endswith("; 2026-10-15: note") and row["Notes"].startswith("2026-09-10")
    json.dump({"Status": "Applied"}, open(ch, "w"))
    assert run("tracker.py", "update", p, "--row", "3", ch, ok=False).returncode == 2
    json.dump({"Status": "Rejected"}, open(ch, "w"))
    run("tracker.py", "update", p, "--row", "3", ch, "--today", "2026-10-15")
    json.dump({"Status": "Interviewing"}, open(ch, "w"))
    assert run("tracker.py", "update", p, "--row", "3", ch, ok=False).returncode == 2
    run("tracker.py", "update", p, "--row", "3", ch, "--manual")


@test("tracker: unknown row and missing file are refused cleanly; dry-run add works without a file")
def _():
    t = os.path.join(F, "tracker.csv")
    r = run("tracker.py", "recorded", t, "--row", "9", "--date", "2026-10-14", "--subject", "x", ok=False)
    assert r.returncode == 2 and "Traceback" not in r.stderr
    row = out("r2.json"); json.dump({"Company": "X", "Status": "Tailored"}, open(row, "w"))
    assert run("tracker.py", "add", out("missing.csv"), row, ok=False).returncode == 2
    r = run("tracker.py", "add", out("missing.csv"), row, "--dry-run")
    assert "DRY RUN" in r.stdout and not os.path.exists(out("missing.csv"))


@test("tracker update: Notion-style merge gives the same result as the CSV update")
def _():
    cur = list(csv.DictReader(open(os.path.join(F, "tracker.csv"))))[3]
    a, b = out("cur.json"), out("chg.json")
    json.dump(cur, open(a, "w")); json.dump({"Furthest stage": "Assignment", "Rounds reached": 3}, open(b, "w"))
    merged = json.loads(run("tracker.py", "merge", a, b, "--today", "2026-10-15").stdout.splitlines()[-1])
    assert merged["Furthest stage"] == "Assignment" and merged["Rounds reached"] == "3" and merged["Last update"] == "2026-10-15"


@test("tracker find: normalises company names and stops on an open same-role row")
def _():
    t = os.path.join(F, "tracker.csv")
    r = run("tracker.py", "find", t, "--company", "Fintrail GmbH", "--url", "https://fintrail.example/careers/lead-pm-payments", ok=False)
    assert r.returncode == 3, r.returncode
    r = r.stdout
    assert r.count("row ") == 2 and "SAME ROLE" in r and "STOP" in r
    r = run("tracker.py", "find", os.path.join(F, "tracker_rejected.csv"), "--company", "Tradeloop B.V.",
            "--url", "https://jobs.tradeloop.example/senior-pm-search").stdout
    assert "SAME ROLE" in r and "STOP" not in r


@test("tracker stale, window, recorded")
def _():
    p = tcopy()
    r = run("tracker.py", "stale", p, "--today", "2026-10-15", "--days", "45", "--apply").stdout
    rows = list(csv.DictReader(open(p)))
    assert rows[0]["Status"] == "No response" and rows[2]["Status"] == "Applied" and "row 0" in r
    assert "2026-10-08 to 2026-10-15" in run("tracker.py", "window", "--today", "2026-10-15").stdout
    assert "2026-09-15" in run("tracker.py", "window", "--today", "2026-10-15", "--last-sync", "2026-06-01").stdout
    assert "skip" in run("tracker.py", "recorded", os.path.join(F, "tracker_synced.csv"), "--row", "4",
                         "--date", "2026-10-14", "--subject", "Ihre Bewerbung bei Oldco").stdout


# ---------------- stats.py ----------------
@test("stats: tracker.csv numbers and stale Tailored row")
def _():
    r = run("stats.py", os.path.join(F, "tracker.csv"), "--today", "2026-10-15").stdout
    assert "| **All** | 4 | 0% | 50% | 25% | 0% | 0% | 0% | 100% |" in r
    assert "STALE TAILORED" in r and "Oldco" in r and "all checks pass" in r
    assert "| Germany | 3 |" in r and "| Netherlands | 1 |" in r


@test("stats: Final above Round 3+ is not an error; no 3 -> Final step")
def _():
    r = run("stats.py", os.path.join(F, "tracker_final.csv"), "--today", "2026-10-15").stdout
    assert "| **All** | 10 | 50% | 60% | 40% | 10% | 30% | 0% | 40% |" in r
    assert "| Germany | 7 |" in r and "| Netherlands | 3 |" in r
    assert "3 -> Final" not in r and "all checks pass" in r and "Level:" in r


@test("stats: JSON rows from Notion and the nothing-sent case")
def _():
    rows = list(csv.DictReader(open(os.path.join(F, "tracker_final.csv"))))
    for r in rows:
        r["Reached final round"] = "__YES__" if r["Reached final round"] == "true" else "__NO__"
    j = out("rows.json"); json.dump(rows, open(j, "w"))
    assert "| **All** | 10 | 50% | 60% | 40% | 10% | 30% | 0% | 40% |" in run("stats.py", j, "--today", "2026-10-15").stdout
    j2 = out("none.json"); json.dump([{"Company": "A", "Status": "Tailored", "Date tailored": "2026-10-14"}], open(j2, "w"))
    assert run("stats.py", j2, "--today", "2026-10-15").stdout.startswith("No applications sent yet; 1 tailored")


shutil.rmtree(W, ignore_errors=True)
fails = [(n, e) for n, e in results if e]
for n, e in results:
    print(("PASS " if not e else "FAIL ") + n + ("" if not e else f"\n     {e}"))
print(f"\n{len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)
