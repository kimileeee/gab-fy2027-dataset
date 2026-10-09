"""Table of contents of the House GAB (CR00638.pdf), copy A and B -> ../data/gab/toc_{A,B}.csv. The bill prints one contents block per
volume: I-A (pdf 15 in copy A / 3538 in copy B) lists departments I-XXI, I-B (1358 / 4877) continues XXII-XLIII and the back matter,
II (2932 / 6803) repeats the department/agency list for the Details volume. I-C's contents is a single line and is skipped. This file is
the authority for <department>/<agency> names in gab_tree.py and friends.

kind: dept (Roman numeral code) | group (letter code whose children are 'letter.number' - the SUC regions, and the per-department
groupings under Budgetary Support to GOCCs / Allocations to LGUs) | agency | other (back matter: General Provisions, the annexes, the DOE
attached corporations). bill_page is the printed page, which restarts in each volume. Roman vs letter is ambiguous for I/V/X/L/C: a Roman
code is a department only when it is the next number in sequence, so DOST's agencies 'I.' and 'L.' stay agencies, and so the back-matter
funds after the real departments (XXXVIII CONTINGENT FUND, etc.) still count as depts - they continue the same Roman sequence. Text is
read with sort=True, which puts 'CODE  Title ......  page' on one line; a title that wraps leaves its first line(s) without the dot
leader, and the code sits on the first of them. Run from build/."""
import csv, re, os, pymupdf
from gab_pdf import open_bill, with_c, COPIES

STARTS = with_c({'A': (15, 1358, 2932), 'B': (3538, 4877, 6803)})
CODE = re.compile(r'^(?:([IVXLC]+)\.?|([A-Z]{1,2})\.(\d+)?)(?=\s|$)\s*')   # 'XXII.', 'A.', 'A.1' (no trailing dot on the sub-code,
ROW = re.compile(r'^(.*?)\s*\.{3,}\s*(\d+)\s*$')                            # and none on the bill's 'XXXVIII' / 'XXXIX')
ROMAN = dict(I=1, V=5, X=10, L=50, C=100)


def roman(s):
    n = 0
    for i, c in enumerate(s):
        v = ROMAN[c]
        n += -v if i + 1 < len(s) and ROMAN[s[i + 1]] > v else v
    return n


def block(d, start):
    """TOC pages from `start` until a page with no dot leaders; volume from the VOLUME line on those pages or just before them."""
    vol = ''
    pages = []
    while re.search(r'\.{10,}', d[start - 1].get_text()): pages.append(start); start += 1
    for p in pages + list(range(pages[0] - 1, pages[0] - 6, -1)):
        m = re.search(r'VOLUME\s+([IVX]+)(?:\s*-\s*([A-C]))?\s*$', d[p - 1].get_text(sort=True), re.M)
        if m: vol = m.group(1) + (m.group(2) or ''); break
    return vol, pages


def toc(copy):
    d = open_bill()
    out = []
    for start in STARTS[copy]:
        vol, pages = block(d, start)
        dept = dcode = ''; ndept = 0; buf = []; code = None          # buf/code span page breaks: a title can wrap across pages
        for pn in pages:
            for l in d[pn - 1].get_text(sort=True).split('\n'):
                if not l.strip():
                    if buf: dept = dcode = ''                        # a standalone heading ('General Provisions') ends the dept list
                    buf = []; code = None; continue
                if not buf and re.fullmatch(r'\d+', l.strip()): continue   # a stray page-number line, sorted ahead of its own row
                if '.indd' in l: continue                           # the print shop's page-bottom filename/timestamp stamp
                c = CODE.match(l.strip())
                if c and not buf:                                   # a code only opens an entry, never continues one
                    code = c.group(1) or c.group(2) + ('.' + c.group(3) if c.group(3) else '')
                    l = l.strip()[c.end():]
                m = ROW.match(l.strip())
                if not m: buf.append(l.strip()); continue           # first line(s) of a title that wraps
                title, page = ' '.join(buf + [m.group(1)]).strip(), int(m.group(2)); buf = []
                if code and re.fullmatch(r'[IVXLC]+', code) and roman(code) == (ndept + 1 if ndept else roman(code)):
                    ndept = roman(code); dept, dcode = title.upper(), code; kind = 'dept'
                elif code and dcode: kind = 'agency'
                else: kind = 'other'; code = None
                out.append(dict(copy=copy, vol=vol, toc_page=pn, kind=kind, dept_code=dcode if kind != 'other' else '',
                                dept=dept if kind != 'other' else '', group_code='', group='',
                                agency_code=code if kind == 'agency' else '', agency=title if kind == 'agency' else '',
                                title=title, bill_page=page))
                code = None
    # a letter code with 'letter.number' children is a grouping, not an agency
    kids = {(r['vol'], r['dept_code'], r['agency_code'].split('.')[0]) for r in out if '.' in r['agency_code']}
    for r in out:
        if r['kind'] == 'agency' and '.' not in r['agency_code'] and (r['vol'], r['dept_code'], r['agency_code']) in kids:
            r.update(kind='group', group_code=r['agency_code'], group=r['agency'], agency_code='', agency='')
    group = {}
    for r in out:
        if r['kind'] == 'group': group[(r['vol'], r['dept_code'], r['group_code'])] = r['title']
        elif r['kind'] == 'agency' and '.' in r['agency_code']:
            g = r['agency_code'].split('.')[0]
            r.update(group_code=g, group=group.get((r['vol'], r['dept_code'], g), ''))
    return out


if __name__ == '__main__':
    os.makedirs('../data/gab', exist_ok=True)
    for c in COPIES:
        R = toc(c)
        with open(f'../data/gab/toc_{c}.csv', 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=list(R[0])); w.writeheader(); w.writerows(R)
        print(c, len(R), 'rows |', {k: sum(r['kind'] == k for r in R) for k in ('dept', 'group', 'agency', 'other')},
              '| depts per vol', {v: sum(r['kind'] == 'dept' and r['vol'] == v for r in R) for v in sorted({r['vol'] for r in R})})
