"""Special Provisions for every agency in the bill, copies A/B/C (see gab_pdf.py).

Each agency prints its Special Provision(s) between its summary table ('New Appropriations, by Programs/Projects') and its detail
table ('New Appropriations, by Programs/Activities/Projects'). In the PDF's text stream that text comes out of order (after the
detail table), so lines are rebuilt from word coordinates: words -> rows by y, margin line numbers dropped, running header skipped.
A provision starts at a line '<n>. <Title>. <text>'; following lines continue it, an indented line starts a new paragraph.
dept / agency = the nearest Roman-numeral department / lettered agency heading above the block (agency '' = printed before any
agency heading, i.e. department-wide). Headings are only read outside a provisions block, so a lettered list inside a provision
can't switch the agency. Output ../data/gab_provisions_{A,B}.csv (id,copy,dept,agency,no,title,text,page_start,page_end,lines).
Run from build/."""
import csv, hashlib, re, sys
import pymupdf
from gab_pdf import open_bill
from parse_gab_pap import PAGES, DEPT, AGENCY

START = re.compile(r'^Special Provisions?(?:\s*\(s\))?$', re.I)
END = re.compile(r'^New Appropriations,?\s*\.?\s*by\b', re.I)
NUMBERED = re.compile(r'^(\d{1,2})\.+\s*(?=[A-Z(\'"])(.*)$')         # '1. Reporting and Posting ...'; the bill once prints '1..'
TITLE = re.compile(r'^(.{3,200}?)\.(?:\s+|$)(.*)$', re.S)              # title = text up to the first '. ' (it may wrap onto the next line)
GENERIC = re.compile(r'^(REGULAR PROGRAMS?|PROJECTS?|PROJECT\(S\)|(LOCALLY-FUNDED|FOREIGN-ASSISTED) PROJECTS?(\(S\))?)$')

def toc_depts(copy):
    """Department names in the bill's own Table of Contents. A heading such as 'L. MARAWI COMPENSATION BOARD' also matches the
    Roman-numeral pattern (L, V, X and I are agency letters too), so a department heading only counts if it is a real one."""
    # numeral AND name must match: Budgetary Support to GOCCs letters its groups 'I. DEPARTMENT OF TRADE AND INDUSTRY' (DTI is XXVI)
    return {(r['dept_code'], r['dept']) for r in csv.DictReader(open(f'../data/gab/toc_{copy}.csv', encoding='utf8')) if r['kind'] == 'dept'}

def page_lines(page):
    """[(y, rx, text)] for one page in reading order, margin line numbers removed. rx = x of the first word relative to the right
    edge of the left-margin line numbers, so indents compare across odd and even pages (their margins differ)."""
    rows = []
    for x0, y0, x1, y1, t, *_ in sorted(page.get_text('words'), key=lambda w: (round(w[1] / 2.5), w[0])):
        if rows and abs(rows[-1][0] - y0) <= 2.5: rows[-1][1].append((x0, t, x1))
        else: rows.append([y0, [(x0, t, x1)]])
    edges = sorted(min(r)[2] for y, r in rows if y >= 45 and re.fullmatch(r'\d{1,2}', min(r)[1]) and min(r)[0] < 100)
    anchor = edges[len(edges) // 2] if edges else 0
    out = []
    for y, toks in rows:
        if y < 45: continue                                               # running header: 'DEPARTMENT OF HEALTH 1069'
        toks = sorted(toks)
        if toks and re.fullmatch(r'\d{1,2}', toks[0][1]) and toks[0][0] < 100: toks = toks[1:]
        if toks and re.fullmatch(r'\d{1,2}', toks[-1][1]) and toks[-1][0] > 540: toks = toks[:-1]
        if toks: out.append((y, round(toks[0][0] - anchor, 1), ' '.join(t for x, t, x1 in toks)))
    return out

def parse(copy):
    lo, hi = PAGES[copy]; d = open_bill(); depts = toc_depts(copy)
    dept = agency = ''; inside = False; cur = None; out = []; left = None
    def close():
        nonlocal cur
        if cur:
            t = re.sub(r'[ \t]+', ' ', cur['text']).strip()
            m = TITLE.match(t) if cur['no'] != '' else None
            cur['title'], cur['text'] = (m.group(1).strip(), m.group(2).strip()) if m else ('', t)
            out.append(cur)
        cur = None
    for pn in range(lo, hi + 1):
        for y, x, t in page_lines(d[pn - 1]):
            if not inside:
                m = DEPT.match(t)
                name = next((n for code, n in depts if code == m.group(1) and m.group(2).strip().startswith(n)), None) if m else None
                if name: dept, agency = name, ''; continue          # body may extend the TOC name: '... FUND (CALAMITY FUND)'
                m = AGENCY.match(t)
                if m and not GENERIC.match(m.group(2).strip()): agency = m.group(2).strip(); continue
                if START.match(t): inside, left = True, None
                continue
            if END.match(t): close(); inside = False; continue
            m = NUMBERED.match(t)
            prev = cur['no'] if cur and cur['no'] != '' else 0
            if m and prev < int(m.group(1)) <= prev + 3 and (left is None or x <= left + 8):   # a later number, at the block's left edge
                close(); left = x                                                          # (a skipped number is kept and checked)
                cur = dict(copy=copy, dept=dept, agency=agency, no=int(m.group(1)), title='', text=m.group(2), page_start=pn, page_end=pn, lines=1)
                continue
            if cur is None:                                               # text before the first numbered provision
                cur = dict(copy=copy, dept=dept, agency=agency, no='', title='', text='', page_start=pn, page_end=pn, lines=0); left = x
            cur['text'] += ('\n' if left is not None and x > left + 8 else ' ') + t
            cur['page_end'] = pn; cur['lines'] += 1
    close()
    seen = {}
    for r in out:                                                         # stable id: copy + agency + number + title (+ repeat count)
        k = (r['copy'], r['dept'], r['agency'], r['no'], r['title']); seen[k] = seen.get(k, 0) + 1
        r['id'] = hashlib.sha1('|'.join(map(str, k + (seen[k],))).encode()).hexdigest()[:12]
    return out

if __name__ == '__main__':
    for c in sys.argv[1:] or ['A', 'B', 'C']:
        rows = parse(c)
        with open(f'../data/gab_provisions_{c}.csv', 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=['id', 'copy', 'dept', 'agency', 'no', 'title', 'text', 'page_start', 'page_end', 'lines'])
            w.writeheader(); w.writerows(rows)
        print(c, len(rows), 'provisions |', len({(r['dept'], r['agency']) for r in rows}), 'agencies |',
              sum(1 for r in rows if r['no'] == ''), 'unnumbered blocks |', sum(r['lines'] for r in rows), 'lines')
