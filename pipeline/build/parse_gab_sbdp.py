"""DILG Local Government Support Fund - Support to the Barangay Development Program (SBDP) barangay list from the bill
(copies A/B/C, see gab_pdf.py). Five printed columns: No., Region, Province, City/Municipality, Barangay; no amounts.
Columns are cut at fixed offsets from the region cell's x (the whole table shifts ~14pt between left and right pages); a line
with no leading number continues the cells of the row above (wrapped names). Output ../data/gab_annex_sbdp_{A,B,C}.csv, id =
sha1(SBDP|copy|page|ordinal)[:12]. Prints rows vs the printed numbering. Run from build/."""
import csv, re, sys, hashlib, pymupdf
from parse_gab_annex import rows_of
from gab_pdf import open_bill, with_c

PAGES = with_c({'A': (2260, 2299), 'B': (5817, 5856)})
CUTS = (70, 180, 310)   # province / city-municipality / barangay columns start this far right of the region cell
COLS = ('region', 'province', 'municipality', 'barangay')
SKIP = re.compile(r'GENERAL APPROPRIATIONS|LOCAL GOVERNMENT SUPPORT|BARANGAY DEVELOPMENT|CITY/MUNICIPALITY|FISCAL YEAR')

def cells(words, rx):
    out = dict.fromkeys(COLS, '')
    for x, t in words:
        col = COLS[sum(x >= rx + c - 4 for c in CUTS)]
        out[col] = (out[col] + ' ' + t).strip()
    return out

def parse(copy):
    lo, hi = PAGES[copy]; d = open_bill(); out = []; i = 0
    for pn in range(lo, hi + 1):
        rx = None
        for y, ws in rows_of(d[pn - 1]):
            ws = sorted(ws); text = ' '.join(t for _, t in ws)
            if SKIP.search(text):
                if ws[0][1].isdigit() and ws[0][0] < 100: i += 1   # left-page running header "884 GENERAL ..." - the first (frozen) extract counted it as a row; keeps ids stable
                continue
            if ws[0][1].isdigit() and len(ws) >= 4:                # numbered row: No. then the region cell
                rx = ws[1][0]
                out.append(dict(id=hashlib.sha1(f'SBDP|{copy}|{pn}|{i}'.encode()).hexdigest()[:12], annex='SBDP', copy=copy, page=pn,
                                row_no=int(ws[0][1]), **cells(ws[1:], rx)))
                i += 1
            elif rx is not None and not (len(ws) == 1 and ws[0][1].isdigit()):   # wrapped cell text (a lone number is the page footer)
                for k, v in cells(ws, rx).items():
                    if v: out[-1][k] += ' ' + v
    return out

if __name__ == '__main__':
    for c in sys.argv[1:] or ['A', 'B', 'C']:
        rows = parse(c)
        with open(f'../data/gab_annex_sbdp_{c}.csv', 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        n = [r['row_no'] for r in rows]
        print(f'SBDP {c}: rows={len(rows)} numbered 1..{max(n)} | out of sequence: {[(a, b) for a, b in zip(n, n[1:]) if b != a + 1]}'
              f" | empty cells: {sum(1 for r in rows for k in COLS if not r[k])}")
