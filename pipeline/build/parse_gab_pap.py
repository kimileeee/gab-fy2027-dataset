"""Program/activity (PAP) rows for every agency in CR00638.pdf, copy A (as filed) and B (House [3RD READING]).
Rows: dept, agency, label (wrapped labels merged), PS/MOOE/CO/total as printed; total = rightmost amount, pesos. Vol I-A+I-B agency pages only.
Output ../data/gab_pap_{A,B}.csv (id,copy,page,dept,agency,label,amounts,total,ps,mooe,fin,co,cols). ps/mooe/fin(ancial)/co are the printed
columns read by right-edge position (gab_cols.py; `amounts` lists only the non-blank ones, so a lone column amount is ambiguous there); cols = ok / text (row outside a PS-MOOE-CO table: provision lists, PS itemization) / off (off-grid). id = sha1(PAP|copy|page|ordinal)[:12].
`lines()` is the shared line reader (also used by gab_tree.py, which rebuilds the printed hierarchy). Run from build/."""
import csv, re, sys, hashlib, statistics, pymupdf
from parse_gab_annex import NUM, PDF
from gab_cols import rows_x1, ColState, D, TOL as COL_TOL
from gab_toc import roman
PAGES = {'A': (12, 1959), 'B': (3536, 5492)}
DEPT = re.compile(r'^([IVXL]+)\.\s+([A-Z][A-Z\'"\-,&/() ]{3,})$')
AGENCY = re.compile(r'^([A-Z]{1,2}(?:\.\d+)?)\.\s+([A-Z][A-Z\'"\-,&/()\. ]{3,})$')
# the charset above covers every dept/agency/group title in the bill (checked via toc_{A,B}.csv) except the quote mark in
# SUC's 'B.1. EULOGIO "AMANG" RODRIGUEZ INSTITUTE OF SCIENCE AND TECHNOLOGY' - added here so that heading is recognised as
# an agency transition directly, rather than falling through to gab_tree.py's rx>150 'is this a centred title' fallback,
# which itself under-triggers for a long title (centering a wide string starts it further left, so a long heading's rx can
# sit well under 150 even though it genuinely is centred) - true for this exact title, so relying on that fallback instead
# of fixing the charset would have left this one broken regardless.
SKIP = re.compile(r'^(Maintenance and|Other Operating|Personnel Services|Expenses|Capital Outlays|Total$|Current Operating Expenditures|New Appropriations, by|Special Provision|A\. REGULAR PROGRAMS|REGULAR PROGRAMS|GENERAL APPROPRIATIONS BILL|FOR\b|For general administration|\(Amount)', re.I)

def on_grid(x1, T): k = round((T - x1) / D); return 0 <= k <= 4 and abs(T - x1 - k * D) <= COL_TOL

def lines(copy, lo=None, hi=None, small=False, keep_dash=False):
    """Yield one dict per printed line: pn, y, x (first label token), rx (x relative to the left-margin line-number column, so indents
    compare across odd/even pages), lab, am (amounts), colv/ok (column split, gab_cols).
    small=True also reads comma-less amounts < 1,000 in the amount columns (object-of-expenditure tables are in thousands, e.g. 'Bank
    Transaction Fee 24'). parse() leaves it off: those rows were never in gab_pap and adding them would shift every later id.
    keep_dash=True keeps '-' inside labels ('Region I - Ilocos'); only '-' in the amount columns (blank-cell marks) is dropped."""
    lo = lo or PAGES[copy][0]; hi = hi or PAGES[copy][1]; d = pymupdf.open(PDF); cs = ColState(); anchor = 0
    for pn in range(lo, hi + 1):
        rows = rows_x1(d[pn - 1]); cs.page(rows)
        ln = [x1 for y, r in rows for x0, t, x1 in sorted(r)[:1] if re.fullmatch(r'\d{1,2}', t) and x0 < 100]
        if ln: anchor = statistics.median(ln)          # line numbers are right-aligned: their right edge is the page's x anchor
        for y, r in rows:
            cs.row(r)
            if y < 45: cs.after(r); continue                      # running page header
            r = sorted(r)
            toks = [(x, t, x1) for x, t, x1 in r if t != 'P']
            if len(toks) > 1 and re.fullmatch(r'\d{1,2}', toks[0][1]) and toks[0][0] < 100: toks = toks[1:]      # left-margin line number
            if len(toks) > 1 and re.fullmatch(r'\d{1,2}', toks[0][1]) and toks[0][0] < anchor + 5: toks = toks[1:]   # a 2nd number printed beside it ('45 1', Bicol p652), left of any indent (shallowest rx ~7)
            if len(toks) > 1 and re.fullmatch(r'\d{1,2}', toks[-1][1]) and toks[-1][0] > 540: toks = toks[:-1]   # right-margin line number
            if small and cs.T: toks = [(x, f'0,{int(t):03d}' if re.fullmatch(r'\d{1,3}', t) and x > 340 and on_grid(x1, cs.T) else f'{int(t):,}' if re.fullmatch(r'\d{4,6}', t) and x > 340 and on_grid(x1, cs.T) and len(toks) <= 9 and not re.match(r'\d+\.', toks[0][1]) else t, x1) for x, t, x1 in toks]   # '24' -> '0,024' so NUM reads it; '1295' (comma missing in the print, MCB p1733 Clothing Allowance) -> '1,295'
            am = [int(t.replace(',', '')) for x, t, x1 in toks if NUM.match(t)]
            colv, ok = cs.cols([(int(t.replace(',', '')), x1) for x, t, x1 in toks if NUM.match(t) and x1 > 200]) if am else (None, None)
            cs.after(r)
            lt = [(x, t) for x, t, x1 in toks if not NUM.match(t) and (t != '-' or (keep_dash and x < 340))]
            lab = ' '.join(t for x, t in lt).strip()
            lab = re.sub(r'^\d{1,2}\s+(?=[^\d\s])', '', lab); lab = re.sub(r'\s+\d{1,2}$', '', lab)    # stray margin line numbers
            if not am and (not lab or re.fullmatch(r'\d{1,3}', lab)): continue
            x = lt[0][0] if lt else None
            yield dict(pn=pn, y=y, x=x, rx=None if x is None else round(x - anchor, 1), lab=lab, am=am, colv=colv, ok=ok)

def parse(copy):
    out = []; dept = agency = ''; pend = []; ndept = 0
    for L in lines(copy):
        pn, lab, am, colv, ok = L['pn'], L['lab'], L['am'], L['colv'], L['ok']
        m = DEPT.match(lab)
        # a Roman-numeral code is a new department only when it's the next one in sequence - SUC's own internal
        # region lettering (A-S) includes single letters that are themselves valid Roman numerals ('I. REGION V -
        # BICOL', 'L. REGION VII - CENTRAL VISAYAS'), and without this guard they get misread as a new top-level
        # department, truncating 'STATE UNIVERSITIES AND COLLEGES' partway through (same fix as gab_toc.py's toc()).
        if m and not am and roman(m.group(1)) == ndept + 1:
            ndept = roman(m.group(1)); dept, agency, pend = m.group(2).strip(), '', []; continue
        m = AGENCY.match(lab)
        if m and not am: agency, pend = m.group(2).strip(), []; continue
        if SKIP.match(lab) and not am: pend = []; continue
        if am:
            full = ' '.join(pend + [lab]).strip(); pend = []
            if full and not SKIP.match(full): out.append(dict(copy=copy, page=pn, dept=dept, agency=agency, label=full, amounts='|'.join(map(str, am)), total=am[-1], cols='text' if colv is None else 'ok' if ok else 'off', **{k: (colv or {}).get(k) if (colv and ok) else None for k in ('ps', 'mooe', 'fin', 'co')}))
        elif lab: pend.append(lab)
    for i, r in enumerate(out): r['id'] = hashlib.sha1(f"PAP|{copy}|{r['page']}|{i}".encode()).hexdigest()[:12]
    return out

if __name__ == '__main__':
    for c in sys.argv[1:] or ['A', 'B']:
        rows = parse(c)
        with open(f'../data/gab_pap_{c}.csv', 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=['id', 'copy', 'page', 'dept', 'agency', 'label', 'amounts', 'total', 'ps', 'mooe', 'fin', 'co', 'cols']); w.writeheader(); w.writerows(rows)
        tn = sum(r['total'] for r in rows if r['label'].upper().startswith('TOTAL NEW APPROPRIATIONS'))
        print(c, 'rows', len(rows), 'depts', len({r['dept'] for r in rows}), 'agencies', len({(r['dept'], r['agency']) for r in rows}), '| sum of TOTAL NEW APPROPRIATIONS rows P%.1fB' % (tn / 1e9))
