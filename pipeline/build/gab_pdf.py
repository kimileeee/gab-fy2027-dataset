"""Row extraction from the House GAB PDFs (HB10858.pdf / CR00638.pdf) using word coordinates.
pdftotext -layout scrambles label/amount alignment on these files; the PDF's own y-coordinates are clean.
Page rows -> [(x_label, y, label_text, amount_or_None)], continuation lines folded into their parent row.
Run from build/. PDFs live in ../raw/hb10858/ (gitignored)."""
import re, pymupdf

AMT = re.compile(r"^\(?-?\d{1,3}(?:,\d{3})+\)?$")
AMT_X = 470       # amounts sit right of this x (pt) on 648pt-wide pages
ROW_TOL = 3.0     # label/amount y offset tolerance (pt)

def parse_amt(s):
    neg = s.startswith('(') or s.startswith('-')
    v = int(re.sub(r'[^\d]', '', s))
    return -v if neg else v

def page_rows(page):
    """Return rows in reading order: dict(x, y, text, amt, heading) for one page."""
    lines = {}
    for x0, y0, x1, y1, t, b, l, _ in page.get_text("words"):
        lines.setdefault((b, l), []).append((x0, y0, t))
    labels, amts = [], []
    for ws in lines.values():
        ws.sort()
        x, y = ws[0][0], ws[0][1]
        if y < 55 or y > 760:           # running header / footer
            continue
        txt = " ".join(t for _, _, t in ws)
        if x >= AMT_X and AMT.match(txt.replace(' ', '')):
            amts.append([y, parse_amt(txt.replace(' ', '')), False])
        else:
            labels.append([x, y, txt])
    labels.sort(key=lambda r: (r[1], r[0]))
    amts.sort()
    rows = []
    for x, y, txt in labels:
        a = next((m for m in amts if not m[2] and abs(m[0] - y) <= ROW_TOL), None)
        if a:
            a[2] = True
            rows.append(dict(x=x, y=y, text=txt, amt=a[1]))
        else:
            rows.append(dict(x=x, y=y, text=txt, amt=None))
    # amount with no label on this page (label continues from previous page)
    orphan = [m[1] for m in amts if not m[2]]
    return rows, orphan

def fold(rows):
    """Fold unpaired lines at the same indent as the previous amount row into it (wrapped labels); others stay headings."""
    out = []
    for r in rows:
        if r['amt'] is None and out and abs(r['x'] - out[-1]['x']) <= 3 and out[-1]['amt'] is not None and 0 < r['y'] - out[-1]['yend'] < 16:
            out[-1]['text'] += ' ' + r['text']; out[-1]['yend'] = r['y']
        else:
            r['yend'] = r['y']; r['heading'] = r['amt'] is None; out.append(r)
    return out

if __name__ == '__main__':
    import sys
    d = pymupdf.open('../raw/hb10858/CR00638.pdf')
    for pn in map(int, sys.argv[1:]):
        rows, orphan = page_rows(d[pn - 1])
        print(f'=== p{pn} orphan amounts: {orphan}')
        for r in fold(rows)[:40]:
            print(f"x={r['x']:5.0f} {'H' if r['heading'] else ' '} {r['amt'] if r['amt'] is not None else '':>15} {r['text'][:90]}")
