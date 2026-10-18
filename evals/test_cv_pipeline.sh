#!/usr/bin/env bash
# Deterministic check of the commands in references/cv-editing.md. No model needed.
# Run from the repo root: bash evals/test_cv_pipeline.sh
set -euo pipefail
ROOT=$(pwd); W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
cp evals/files/templates/cv_main.docx "$W/base.docx"; cd "$W"
fail(){ echo "FAIL: $1"; exit 1; }

# Read: python-docx misses the content control, raw w:t read finds it
python3 -c "from docx import Document; import sys; sys.exit(any('sellers' in p.text for p in Document('base.docx').paragraphs))" || fail "python-docx unexpectedly sees hidden bullet (fixture changed?)"
unzip -p base.docx word/document.xml | grep -oE '<w:t( [^>]*)?>[^<]*' | sed -E 's/<w:t( [^>]*)?>//' | grep sellers >/dev/null || fail "raw w:t read does not find hidden bullet"

# Edit and repack exactly as documented
rm -rf unpacked && mkdir unpacked && unzip -o -q base.docx -d unpacked
python3 - <<'PY'
p='unpacked/word/document.xml'; s=open(p,encoding='utf-8').read()
a='ML search ranking that lifted conversion by 9% for 3M monthly users.'
assert s.count(a)==1, 'search string not unique'
open(p,'w',encoding='utf-8').write(s.replace(a,'ML ranking for search and discovery, lifting conversion 9% for 3M users.'))
PY
echo stale > output.docx
rm -f output.docx && (cd unpacked && zip -q -r -X ../output.docx .)

unzip -l output.docx | grep customXml >/dev/null || fail "customXml lost on repack"
python3 -c "from docx import Document; Document('output.docx')" || fail "output is not a valid docx"
soffice --headless --convert-to pdf --outdir check output.docx >/dev/null 2>&1 || fail "LibreOffice conversion failed"
python3 - <<'PY'
import pypdf, sys
r = pypdf.PdfReader('check/output.pdf'); t = ''.join(p.extract_text() for p in r.pages)
assert len(r.pages) == 1, f'expected 1 page, got {len(r.pages)}'
assert 'search and discovery' in t, 'edit missing'
assert t.count('adopted by 12,000') == 1, 'hidden bullet lost or duplicated'
PY
cmp -s "$ROOT/evals/files/templates/cv_main.docx" base.docx || fail "template copy changed"
echo "PASS: cv pipeline"
