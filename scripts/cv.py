#!/usr/bin/env python3
"""Deterministic .docx helpers for the kitty-has-a-job skill.

The model decides WHAT to change; this script only knows HOW Word files work.
Nothing here is specific to one CV layout.

  python3 cv.py read  CV.docx                 paragraph map with ids, flags, missing fonts
  python3 cv.py pages CV.docx                 render with LibreOffice and count pages
  python3 cv.py apply CV.docx EDITS.json OUT.docx [--clean] [--forbid "—"] [--dry-run]
  python3 cv.py filename --pattern P --name N --company C --role R [--dir D]

EDITS.json is a list of operations. Paragraph ids ("p") come from `read` on the
same input file; all targets are resolved before anything changes.
  {"op": "replace",  "p": 14, "old": "exact text", "new": "text"}   # p optional: then old must be unique in the CV
  {"op": "set_text", "p": 14, "text": "Owned partner tools ..."}    # full new text incl. lead word; glyph/numbering kept, first word bold if it was
  {"op": "insert_after", "after": 14, "like": 12, "text": "..."}    # new paragraph cloned from paragraph 12's format
  {"op": "move", "p": 9, "after": 12}  (or "before": 12)
  {"op": "delete", "p": 9}
--clean drops tracked changes (accepting insertions) and comments.
--dry-run checks every edit and prints the resulting text, writing nothing.

Exit codes: 0 done, 1 usage error, 2 refused (nothing written; the message says
why: ambiguous match, unknown id, file exists, forbidden character...).
On 2, fix the edit file and rerun; if the script cannot do the edit at all,
use references/cv-editing.md.
"""
import copy, json, os, re, shutil, subprocess, sys, tempfile, zipfile
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
def w(tag): return "{%s}%s" % (W, tag)

GLYPH = re.compile(r"^([•▪●◦·‣■□\-–*]\s*)")
SUBSTITUTES = {"Calibri": "Carlito", "Cambria": "Caladea", "Arial": "Liberation Sans",
               "Times New Roman": "Liberation Serif", "Courier New": "Liberation Mono",
               "Helvetica": "Liberation Sans"}


class Refused(Exception):
    pass


# ---------- reading ----------

def load(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    return etree.fromstring(xml)


def ancestors(el):
    a = el.getparent()
    while a is not None:
        yield a
        a = a.getparent()


def own_p(el):
    for a in ancestors(el):
        if a.tag == w("p"):
            return a
    return None


def in_fallback(el):
    return any(a.tag == "{%s}Fallback" % MC for a in ancestors(el))


def paragraphs(root):
    body = root.find(w("body"))
    return [p for p in body.iter(w("p")) if not in_fallback(p)]


def segments(p):
    """Text-bearing pieces that belong to this paragraph (not nested text boxes), in order."""
    segs, pos = [], 0
    for el in p.iter(w("t"), w("tab"), w("br")):
        if own_p(el) is not p:
            continue
        if el.getparent().tag != w("r"):
            continue  # tab stops in pPr etc.
        if el.tag == w("t"):
            txt = el.text or ""
        elif el.tag == w("tab"):
            txt = "\t"
        else:
            txt = "\n"
        segs.append({"el": el, "run": el.getparent(), "kind": el.tag.split("}")[1],
                     "text": txt, "start": pos, "end": pos + len(txt)})
        pos += len(txt)
    return segs


def ptext(p):
    return "".join(s["text"] for s in segments(p))


def run_bold(run):
    rpr = run.find(w("rPr"))
    if rpr is None:
        return False
    b = rpr.find(w("b"))
    return b is not None and b.get(w("val"), "true") not in ("0", "false", "off")


def bold_map(p):
    out = []
    for s in segments(p):
        out += [run_bold(s["run"])] * len(s["text"])
    return out


def lead_info(p):
    """(body_start, lead_end or None): glyph prefix length and end of a bold lead word."""
    txt = ptext(p)
    m = GLYPH.match(txt)
    start = len(m.group(1)) if m else 0
    bm = bold_map(p)
    if start < len(txt) and bm[start] and not all(bm[start:]):
        end = start
        while end < len(txt) and bm[end]:
            end += 1
        return start, end
    return start, None


def tags_for(p):
    t = []
    ppr = p.find(w("pPr"))
    style = ""
    if ppr is not None:
        ps = ppr.find(w("pStyle"))
        style = ps.get(w("val")) if ps is not None else ""
        if ppr.find(w("numPr")) is not None:
            t.append("list")
    if style:
        t.append(style)
    txt = ptext(p)
    m = GLYPH.match(txt)
    if m:
        t.append("glyph:" + m.group(1).strip())
    if lead_info(p)[1] is not None:
        t.append("bold-lead")
    anc = [a.tag for a in ancestors(p)]
    if w("sdtContent") in anc:
        t.append("content-control")
    if w("tc") in anc:
        t.append("table")
    if w("txbxContent") in anc:
        t.append("textbox")
    if p.find(".//" + w("ins")) is not None or p.find(".//" + w("del")) is not None:
        t.append("tracked-change")
    return t


def fonts(path):
    """Fonts the text actually uses: explicit run/style fonts plus the theme's Latin fonts."""
    names = set()
    with zipfile.ZipFile(path) as z:
        if "word/styles.xml" in z.namelist():
            st = etree.fromstring(z.read("word/styles.xml"))
            names |= {rf.get(w("ascii")) for rf in st.iter(w("rFonts"))}
        for n in z.namelist():
            if n.startswith("word/theme/") and n.endswith(".xml"):
                th = etree.fromstring(z.read(n))
                for tag in ("majorFont", "minorFont"):
                    for f in th.iter("{%s}%s" % (A, tag)):
                        lat = f.find("{%s}latin" % A)
                        if lat is not None and lat.get("typeface"):
                            names.add(lat.get("typeface"))
        root = etree.fromstring(z.read("word/document.xml"))
    used = set()
    for rf in root.iter(w("rFonts")):
        v = rf.get(w("ascii"))
        if v:
            used.add(v)
    names = {n for n in names if n} | used
    try:
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=30).stdout
        have = {x.strip() for line in out.splitlines() for x in line.split(",")}
    except Exception:
        return names, None
    missing = sorted(n for n in names if n not in have)
    return names, [(n, SUBSTITUTES.get(n) if SUBSTITUTES.get(n) in have else None) for n in missing]


def cmd_read(path):
    root = load(path)
    ps = paragraphs(root)
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        headers = []
        for n in sorted(names):
            if re.match(r"word/(header|footer)\d*\.xml$", n):
                hx = etree.fromstring(z.read(n))
                for hp in hx.iter(w("p")):
                    t = "".join(x.text or "" for x in hp.iter(w("t")))
                    if t.strip():
                        headers.append((n.split("/")[1], t))
    body = root.find(w("body"))
    flags = {
        "tables": len(body.findall(".//" + w("tbl"))),
        "text boxes": len(body.findall(".//" + w("txbxContent"))),
        "content controls": len(body.findall(".//" + w("sdt"))),
        "tracked changes": len(body.findall(".//" + w("ins"))) + len(body.findall(".//" + w("del"))),
        "comments": len(body.findall(".//" + w("commentReference"))),
    }
    print(f"file: {os.path.basename(path)}  paragraphs: {len(ps)}")
    print("structure: " + ", ".join(f"{k} {v}" for k, v in flags.items()))
    _, missing = fonts(path)
    if missing is None:
        print("fonts: could not check (fc-list missing); page count is approximate")
    elif missing:
        print("fonts missing: " + ", ".join(f"{n} (substitute {s}, metric-compatible)" if s else f"{n} (no substitute: page count approximate)" for n, s in missing))
    else:
        print("fonts: all installed")
    ats = []
    if flags["tables"]:
        ats.append("content in tables")
    if flags["text boxes"]:
        ats.append("content in text boxes")
    if headers:
        ats.append("text in header/footer")
    if ats:
        print("ATS risk (flag once, do not rebuild): " + ", ".join(ats))
    if flags["tracked changes"] or flags["comments"]:
        print("WARNING: template has tracked changes or comments; use apply --clean")
    print("---")
    for i, p in enumerate(ps):
        t = ptext(p)
        if t.strip():
            tg = tags_for(p)
            print(f"{i:>3} [{','.join(tg)}] {t}")
    for part, t in headers:
        print(f"  ({part}, not editable with apply) {t}")


# ---------- editing ----------

def remove_if_empty_run(run):
    keep = [c for c in run if c.tag not in (w("rPr"),)]
    if not keep and run.getparent() is not None:
        run.getparent().remove(run)


def set_t(el, text):
    el.text = text
    el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def replace_span(p, start, end, new):
    segs = segments(p)
    if start == end:
        for s in segs:
            if s["kind"] == "t" and s["start"] <= start <= s["end"]:
                o = start - s["start"]
                set_t(s["el"], s["text"][:o] + new + s["text"][o:])
                return
        # no text segment at that point: add a run copying the last run's formatting
        last = segs[-1]["run"] if segs else None
        r = etree.SubElement(p, w("r"))
        if last is not None and last.find(w("rPr")) is not None:
            r.append(copy.deepcopy(last.find(w("rPr"))))
        set_t(etree.SubElement(r, w("t")), new)
        return
    hit = [s for s in segs if s["end"] > start and s["start"] < end]
    first_t = next((s for s in hit if s["kind"] == "t"), None)
    if first_t is None:
        raise Refused("span has no text run to write into")
    for s in hit:
        pre = s["text"][:max(0, start - s["start"])]
        post = s["text"][end - s["start"]:] if end < s["end"] else ""
        if s is first_t:
            set_t(s["el"], pre + new + post)
        elif s["kind"] == "t":
            txt = pre + post
            if txt:
                set_t(s["el"], txt)
            else:
                run = s["run"]
                run.remove(s["el"])
                remove_if_empty_run(run)
        else:
            run = s["run"]
            run.remove(s["el"])
            remove_if_empty_run(run)


def split_lead(new, lead_text):
    trailing = lead_text[-1:].isspace()
    parts = new.split(" ", 1)
    w0, rest = parts[0], (parts[1] if len(parts) > 1 else "")
    if not rest:
        return w0, ""
    return (w0 + " ", rest) if trailing else (w0, " " + rest)


def do_replace(p, start, end, new):
    """Replace [start,end) keeping a bold lead word bold and the rest plain."""
    body, lead_end = lead_info(p)
    txt = ptext(p)
    if lead_end is not None and start <= body < lead_end < end:
        lead, rest = split_lead(new, txt[body:lead_end])
        replace_span(p, lead_end, end, rest)
        replace_span(p, start, lead_end, lead)
    else:
        replace_span(p, start, end, new)


def op_set_text(p, text):
    txt = ptext(p)
    body, _ = lead_info(p)
    if GLYPH.match(text) and body:
        text = text[len(GLYPH.match(text).group(1)):]  # glyph is kept from the original
    do_replace(p, body, len(txt), text)


def op_replace(p, old, new):
    txt = ptext(p)
    n = txt.count(old)
    if n != 1:
        raise Refused(f"'{old[:60]}' found {n} times in paragraph (needs exactly 1)")
    i = txt.index(old)
    do_replace(p, i, i + len(old), new)


def unit(p):
    par = p.getparent()
    if par.tag == w("sdtContent") and len(par.findall(w("p"))) == 1 and len(par) == 1:
        return par.getparent()
    return p


def mirrors(p):
    """Duplicate copy of a text-box paragraph in mc:Fallback (Word stores text boxes twice)."""
    alt = next((a for a in ancestors(p) if a.tag == "{%s}AlternateContent" % MC), None)
    if alt is None:
        return []
    fb = alt.find("{%s}Fallback" % MC)
    if fb is None:
        return []
    t = ptext(p)
    return [q for q in fb.iter(w("p")) if ptext(q) == t]


def scrub_clone(p):
    for tag in ("bookmarkStart", "bookmarkEnd", "commentRangeStart", "commentRangeEnd"):
        for el in list(p.iter(w(tag))):
            el.getparent().remove(el)
    for el in p.iter():
        for att in list(el.attrib):
            if att.startswith("{%s}" % W14):
                del el.attrib[att]


def clean_tracking(root):
    n = 0
    for tag in ("del", "moveFrom"):
        for el in list(root.iter(w(tag))):
            el.getparent().remove(el); n += 1
    for tag in ("ins", "moveTo"):
        for el in list(root.iter(w(tag))):
            par = el.getparent(); i = par.index(el)
            for c in list(el):
                par.insert(i, c); i += 1
            par.remove(el); n += 1
    for tag in ("rPrChange", "pPrChange", "sectPrChange", "tblPrChange", "trPrChange", "tcPrChange", "numberingChange",
                "moveFromRangeStart", "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd",
                "commentRangeStart", "commentRangeEnd"):
        for el in list(root.iter(w(tag))):
            el.getparent().remove(el); n += 1
    for el in list(root.iter(w("commentReference"))):
        run = el.getparent(); run.remove(el); remove_if_empty_run(run); n += 1
    return n


COMMENT_PARTS = re.compile(r"word/comments(Extended|Ids|Extensible)?\.xml$")


def cmd_apply(src, edits_path, out, clean=False, forbid="", dry=False):
    if os.path.abspath(src) == os.path.abspath(out):
        raise Refused("output path is the input file; never overwrite a template")
    if os.path.exists(out) and not dry:
        raise Refused(f"{out} already exists; pick a new name (use `filename`, it adds _v2)")
    edits = json.load(open(edits_path, encoding="utf-8"))
    root = load(src)
    ps = paragraphs(root)

    def P(i):
        if not isinstance(i, int) or i < 0 or i >= len(ps):
            raise Refused(f"paragraph id {i} does not exist (run `read` on this same file)")
        return ps[i]

    # resolve all targets first, against the original file
    plan = []
    for k, e in enumerate(edits):
        op = e.get("op")
        if op == "replace":
            if "p" in e:
                p = P(e["p"])
            else:
                hits = [q for q in ps if e["old"] in ptext(q)]
                total = sum(ptext(q).count(e["old"]) for q in hits)
                if total != 1:
                    raise Refused(f"edit {k}: '{e['old'][:60]}' found {total} times in the CV (needs exactly 1; give \"p\")")
                p = hits[0]
            if ptext(p).count(e["old"]) != 1:
                raise Refused(f"edit {k}: '{e['old'][:60]}' found {ptext(p).count(e['old'])} times in paragraph {ps.index(p)}")
            plan.append((op, p, e))
        elif op == "set_text":
            plan.append((op, P(e["p"]), e))
        elif op == "insert_after":
            plan.append((op, P(e["after"]), dict(e, _like=P(e.get("like", e["after"])))))
        elif op == "move":
            tgt = P(e["after"] if "after" in e else e["before"])
            plan.append((op, P(e["p"]), dict(e, _tgt=tgt)))
        elif op == "delete":
            plan.append((op, P(e["p"]), e))
        else:
            raise Refused(f"edit {k}: unknown op {op!r}")
        if any(x in (e.get("new", "") + e.get("text", "")) for x in forbid):
            raise Refused(f"edit {k}: new text contains a forbidden character ({forbid})")

    changed = []
    last_insert = {}
    for op, p, e in plan:
        if op == "replace":
            for q in [p] + mirrors(p):
                op_replace(q, e["old"], e["new"])
            changed.append(p)
        elif op == "set_text":
            for q in [p] + mirrors(p):
                op_set_text(q, e["text"])
            changed.append(p)
        elif op == "insert_after":
            clone = copy.deepcopy(e["_like"])
            scrub_clone(clone)
            op_set_text(clone, e["text"])
            # several inserts after the same paragraph keep their order
            u = last_insert.get(id(p), unit(p))
            u.addnext(clone)
            last_insert[id(p)] = clone
            changed.append(clone)
        elif op == "move":
            u, t = unit(p), unit(e["_tgt"])
            if u is t:
                raise Refused("cannot move a paragraph relative to itself")
            u.getparent().remove(u)
            (t.addnext if "after" in e else t.addprevious)(u)
            changed.append(p)
        elif op == "delete":
            u = unit(p)
            par = u.getparent()
            if par.tag == w("tc") and len(par.findall(w("p"))) == 1:
                replace_span(p, 0, len(ptext(p)), "")
            else:
                par.remove(u)

    removed = clean_tracking(root) if clean else 0
    xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    if dry:
        print(f"DRY RUN: {len(plan)} edit(s) valid, nothing written")
        for p in changed:
            print(f"  would change: {ptext(p)}")
        return

    tmp = out + ".tmp"
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(tmp, "w") as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == "word/document.xml":
                data = xml
            elif clean and COMMENT_PARTS.match(item.filename):
                continue
            elif clean and item.filename == "word/_rels/document.xml.rels":
                r = etree.fromstring(data)
                for rel in list(r):
                    if re.search(r"/comments(Extended|Ids|Extensible)?$", rel.get("Type", "")):
                        r.remove(rel)
                data = etree.tostring(r, xml_declaration=True, encoding="UTF-8", standalone=True)
            elif clean and item.filename == "[Content_Types].xml":
                r = etree.fromstring(data)
                for ov in list(r):
                    if COMMENT_PARTS.match((ov.get("PartName") or "").lstrip("/")):
                        r.remove(ov)
                data = etree.tostring(r, xml_declaration=True, encoding="UTF-8", standalone=True)
            zo.writestr(item, data)
    try:
        from docx import Document
        Document(tmp)
    except Exception as ex:
        os.remove(tmp)
        raise Refused(f"result does not open as a .docx ({ex}); nothing written")
    os.replace(tmp, out)
    print(f"written: {out}")
    if clean:
        print(f"cleaned: {removed} tracked-change/comment marks removed, comment parts dropped")
    for p in changed:
        print(f"  changed: {ptext(p)}")
    left = "".join(ptext(q) for q in paragraphs(etree.fromstring(xml)))
    for ch in forbid:
        if ch in left:
            print(f"  note: '{ch}' still appears elsewhere in the CV (unchanged text)")


# ---------- pages ----------

def cmd_pages(path):
    import pypdf
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise Refused("LibreOffice (soffice) not installed: page count unverified, ask the user to check in Word")
    tmp = tempfile.mkdtemp()
    try:
        prof = "file://" + os.path.join(tmp, "profile")
        # own LibreOffice profile per call: parallel runs otherwise block each other;
        # 180 s covers a cold LibreOffice start on a slow machine
        subprocess.run([soffice, f"-env:UserInstallation={prof}", "--headless", "--convert-to", "pdf",
                        "--outdir", tmp, path], capture_output=True, timeout=180)
        pdf = os.path.join(tmp, os.path.splitext(os.path.basename(path))[0] + ".pdf")
        if not os.path.exists(pdf):
            raise Refused("LibreOffice conversion failed")
        r = pypdf.PdfReader(pdf)
        last = [l for l in (r.pages[-1].extract_text() or "").splitlines() if l.strip()]
        print(f"pages: {len(r.pages)}")
        print(f"last page lines: {len(last)}")
        _, missing = fonts(path)
        if missing and any(s is None for _, s in missing):
            print("approximate: a template font has no metric-compatible substitute; ask the user to confirm in Word")
        elif missing:
            print("reliable: missing fonts replaced by metric-compatible substitutes")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------- filename ----------

def slug(s):
    s = s.replace("&", " and ")
    s = re.sub(r'[/\\:*?"<>|.,()\[\]]', " ", s)
    s = re.sub(r"\s+", "_", s.strip()).lower()
    return re.sub(r"_+", "_", s).strip("_")


def cmd_filename(pattern, name, company, role, d):
    base = pattern.format(name=slug(name), company=slug(company), role=slug(role))
    stem, ext = os.path.splitext(base)
    path = os.path.join(d, base) if d else base
    v = 2
    while d and os.path.exists(path):
        path = os.path.join(d, f"{stem}_v{v}{ext}")
        v += 1
    print(path)


def main(a):
    if not a or any(x in ("-h", "--help") for x in a) or a[0] == "help":
        print(__doc__)
        return 0 if a else 1
    try:
        if a[:1] == ["read"] and len(a) == 2:
            cmd_read(a[1])
        elif a[:1] == ["pages"] and len(a) == 2:
            cmd_pages(a[1])
        elif a[:1] == ["apply"] and len(a) >= 4:
            clean = "--clean" in a
            forbid = a[a.index("--forbid") + 1] if "--forbid" in a else ""
            cmd_apply(a[1], a[2], a[3], clean, forbid, "--dry-run" in a)
        elif a[:1] == ["filename"]:
            o = {a[i]: a[i + 1] for i in range(1, len(a) - 1, 2)}
            cmd_filename(o.get("--pattern", "{name}_cv_{company}_{role}.docx"), o["--name"], o["--company"], o["--role"], o.get("--dir"))
        else:
            print(__doc__)
            return 1
    except Refused as ex:
        print(f"REFUSED: {ex}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
