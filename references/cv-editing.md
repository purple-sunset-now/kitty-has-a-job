# CV editing by hand (fallback)

Use this only when `scripts/cv.py` cannot run here (no Python or python-docx) or cannot do a specific edit (it says why when it refuses). Tell the user you are editing manually, and still verify the page count before saving.

Work on a copy in a fresh scratch directory of its own (for example `W=$(mktemp -d)`), never on the template itself and never in a shared fixed path like `/tmp/cv`, where another run can overwrite your files. If a docx skill is available in the environment, it is a good fuller reference for Word XML.

## Read

```bash
python3 -c "
from docx import Document
doc = Document('template.docx')
for i, p in enumerate(doc.paragraphs):
    if p.text.strip():
        print(f'{i}: {p.text}')
"
```

Many CV templates put text inside Word content controls (`w:sdt` elements), which python-docx skips. Always also read the raw text nodes, otherwise you add duplicates of bullets you could not see:

```bash
unzip -p template.docx word/document.xml | grep -oE '<w:t( [^>]*)?>[^<]*' | sed -E 's/<w:t( [^>]*)?>//'
```

## Baseline page count

Page counts are only reliable if the template's fonts are installed; otherwise LibreOffice substitutes fonts and line breaks move. Check first:

```bash
unzip -p template.docx word/fontTable.xml | grep -o 'w:name="[^"]*"' | sort -u
fc-list : family | sort -u
```

If a template font is missing, say the page count is approximate and ask the user to confirm it in Word.

```bash
soffice --headless --convert-to pdf --outdir check template.docx
python3 -c "import pypdf; print(len(pypdf.PdfReader('check/template.pdf').pages))"
```

## Edit

Run every command from the working directory (the one holding `base.docx`); the commands use explicit paths so they work even when each shell call starts fresh.

1. Unpack: `rm -rf unpacked && mkdir unpacked && unzip -o -q base.docx -d unpacked`
2. Edit `word/document.xml` by exact string replacement on text nodes. Assert each search string matches exactly once before replacing. Word often splits one sentence across several runs (spell-check marks, revision IDs), so a search can fail even though the text is there. If it does, rewrite that paragraph's runs instead: keep the first run's properties for the lead word, put the new text in place, and drop the leftover runs.
3. New bullet: copy the XML of an existing bullet (same `<w:numPr>` numId, spacing, `<w:ind>`, run properties and run pattern) and change the text.
4. Delete a bullet: remove its whole `<w:p>...</w:p>`.
5. Repack everything: `rm -f output.docx && (cd unpacked && zip -q -r -X ../output.docx .)`. Remove any old output first, because zip updates an existing archive instead of replacing it. Do not list folders by hand: templates with content controls often have a `customXml` folder, and leaving it out corrupts the file.

## Verify

Needs LibreOffice (`soffice`) and `pypdf`. If they are missing and cannot be installed, say plainly that the page count is unverified and ask the user to check it in Word before sending.

```bash
soffice --headless --convert-to pdf --outdir check output.docx
python3 -c "import pypdf; r=pypdf.PdfReader('check/output.pdf'); print(len(r.pages)); print(r.pages[-1].extract_text()[:500])"
```

- Over the page limit means not finished. Trim and re-check in a loop: over-long bullets first, then least relevant bullets, then the summary.
- LibreOffice and Word wrap slightly differently. If the last page is full to the last line, trim one more line.
- Check with python-docx that the new text is present and new bullets kept the bold first word and numbering.

## Save

Copy the result to `settings.output_folder` with the configured file name (never overwrite the template or an earlier CV). If the environment works on a remote copy of the user's files, write it back to their folder and tell them the folder and file name.
