"""In-body project lines ("Locally-Funded Project(s)" / "Foreign-Assisted Project(s)" blocks) for every agency except DPWH,
from CR00638.pdf copy A (as filed) and B ([3RD READING]). Complements parse_gab_pap.py, which flattens these blocks and mis-tags the agency.
Block layout in the detailed table: project line (+amount) -> region rows -> implementing-office rows; foreign-assisted projects add
'Loan Proceeds' / 'GOP Counterpart' sub-lines (each with its own region rows). Blocks end at 'Total, Project(s)'.
Outputs ../data/gab_projects_{A,B}.csv (id,copy,page,dept,agency,kind,project,amount,ps,mooe,fin,co,loan,gop,regions,rollup,parent_id) and
gab_project_regions_{A,B}.csv (project_id,source,region,office,amount,ps,mooe,fin,co); ps/mooe/fin/co read by column position (gab_cols.py); prints parsed-vs-printed totals per (dept, kind). Run from build/."""
import csv, re, sys, hashlib, collections, pymupdf
from parse_gab_annex import NUM, PDF
from gab_cols import rows_x1, ColState
from parse_gab_pap import PAGES, DEPT, AGENCY
from gab_toc import roman

GENERIC = re.compile(r'^(REGULAR PROGRAMS?|PROJECTS?(\(S\))?)$', re.I)
MARK = re.compile(r'^(Locally[- ]Funded|Foreign[- ]Assisted) Projects?(?:\(s\))?(?![,\w])\s*(.*)$')
END = re.compile(r'^(Total, Project|TOTAL NEW APPROPRIATIONS|Total, Regular|Sub-total, Operations)', re.I)
SUB = re.compile(r'^Sub-total, ', re.I)
SOURCE = re.compile(r'^(Loan Proceeds|GOP Counterpart|Grants?)$', re.I)
REGION = re.compile(r'^(Region\s+[IVX]+|National Capital Region|Cordillera Admin|Negros Island|Bangsamoro|Autonomous Region|BARMM|Nationwide|Various|Not Applicable)', re.I)
SKIPLAB = re.compile(r'^(Maintenance and|Other Operating|Personnel Services|Expenses|Capital Outlays|Total$|New Appropriations, by|Special Provision|GENERAL APPROPRIATIONS BILL)', re.I)
OFFICE = re.compile(r'(Center|Office|Unit|Hospital|Medical)', re.I)     # 'Negros Island Region Center for Health Development' is an office, not a region
LEADER = re.compile(r'(\. ){3,}|as indicated hereunder', re.I)       # "For ... as indicated hereunder . . . P 71,701,770,000" intro line

def colcols(cv): return {k: cv.get(k) for k in ('ps', 'mooe', 'fin', 'co')}

def parse(copy):
    lo, hi = PAGES[copy]; d = pymupdf.open(PDF)
    dept = agency = ''; kind = None; pend = []; px = None; ndept = 0
    cs = ColState(); projs = []; regs = []; printed = collections.defaultdict(int); cur = reg = None; src = ''
    for pn in range(lo, hi + 1):
        rows = rows_x1(d[pn - 1]); cs.page(rows)
        for y, r in rows:
            cs.row(r)
            if y < 45: cs.after(r); continue
            r = sorted(r); toks = [(x, t, x1) for x, t, x1 in r if t != 'P']
            if len(toks) > 1 and re.fullmatch(r'\d{1,2}', toks[0][1]) and toks[0][0] < 100: toks = toks[1:]
            if len(toks) > 1 and re.fullmatch(r'\d{1,2}', toks[-1][1]) and toks[-1][0] > 540: toks = toks[:-1]
            am = [int(t.replace(',', '')) for x, t, x1 in toks if NUM.match(t)]
            cv, ok = cs.cols([(int(t.replace(',', '')), x1) for x, t, x1 in toks if NUM.match(t) and x1 > 200]) if am else (None, None)
            cv = {k: v for k, v in cv.items() if k != 'total'} if cv and ok else {}
            cs.after(r)
            lt = [(x, t) for x, t, x1 in toks if not NUM.match(t) and t != '-']
            lab = ' '.join(t for x, t in lt).strip()
            lab = re.sub(r'^\d{1,2}\s+(?=[^\d\s])', '', lab); lab = re.sub(r'\s+\d{1,2}$', '', lab)
            x0 = lt[0][0] if lt else None
            if not am and (not lab or re.fullmatch(r'\d{1,3}', lab)): continue
            m = DEPT.match(lab)
            # only the next department in sequence: lettered groups inside a department ('L. OTHER EXECUTIVE OFFICES' under XXXVI Budgetary Support
            # to Government Corporations, SUC's 'I. REGION V - BICOL') are valid Roman numerals too - same guard as parse_gab_pap.parse()
            if m and not am and roman(m.group(1)) == ndept + 1: ndept = roman(m.group(1)); dept, agency, kind, pend, cur, reg = m.group(2).strip(), '', None, [], None, None; continue
            m = AGENCY.match(lab)
            if m and not am:
                if not GENERIC.match(m.group(2).strip()): agency = m.group(2).strip()
                kind = None; pend = []; continue
            if GENERIC.match(lab) and not am: pend = []; continue
            if END.match(lab): kind = None; pend = []; cur = reg = None; continue
            if SUB.match(lab) or (SKIPLAB.match(lab) and not am): pend = []; continue
            mk = MARK.match(lab)
            if mk:
                kind = 'LF' if mk.group(1).lower().startswith('locally') else 'FA'; pend = []; cur = reg = None; src = ''
                lab = mk.group(2).strip()
                if am and not lab: printed[(dept, agency, kind)] = max(printed[(dept, agency, kind)], am[-1]); continue
                if not lab: continue
            if kind is None or dept.startswith('DEPARTMENT OF PUBLIC WORKS'): pend = []; continue
            lab = re.sub(r'^[.\s]+', '', lab)
            if not am and not lab: continue
            if not am:
                if not pend: px = x0
                pend.append(lab); continue
            full = ' '.join(pend + [lab]).strip(); xl = px if pend and px is not None else x0; pend = []; px = None
            a = am[-1]
            if not full or re.fullmatch(r'[\d\W]*', full):
                printed[(dept, agency, kind)] = max(printed[(dept, agency, kind)], a); continue
            if LEADER.search(full):
                printed[(dept, agency, kind)] = max(printed[(dept, agency, kind)], a); continue
            if cur is not None and SOURCE.match(full):
                src = 'loan' if full.lower().startswith('loan') else 'gop' if full.lower().startswith('gop') else 'grant'
                cur[src if src in ('loan', 'gop') else 'loan'] += a; reg = None; continue
            if cur is not None and REGION.match(full) and len(full) < 60 and not OFFICE.search(full):
                reg = dict(name=full, amount=a, x=xl, page=pn, rem=a)
                regs.append(dict(project_id=cur['id'], source=src, region=full, office='', amount=a, **colcols(cv))); continue
            if reg is not None and reg['rem'] > 0 and a <= reg['rem'] and not (reg['page'] == pn and xl is not None and reg['x'] is not None and xl < reg['x'] - 3):
                regs.append(dict(project_id=cur['id'], source=src, region=reg['name'], office=full, amount=a, **colcols(cv))); reg['rem'] -= a; continue
            cur = dict(id=hashlib.sha1(f'PROJ|{copy}|{pn}|{len(projs)}'.encode()).hexdigest()[:12], copy=copy, page=pn, dept=dept, agency=agency, kind=kind, project=full, amount=a, loan=0, gop=0, regions=0, rollup=0, parent_id='', **colcols(cv))
            projs.append(cur); reg = None; src = ''
    n = collections.Counter(g['project_id'] for g in regs if g['office'] == '' and not g['source'])
    nl = collections.Counter(g['project_id'] for g in regs if g['office'] == '' and g['source'])
    for p in projs: p['regions'] = n[p['id']] or nl[p['id']]
    for i, p in enumerate(projs):          # group heading whose total equals the sum of the next sibling lines (e.g. NIA 'New National Irrigation Sub-Program')
        if p['regions'] or p['rollup'] or p['parent_id'] or not re.search(r'Sub-?Program\s*$', p['project'], re.I): continue
        t = 0
        for j in range(i + 1, min(i + 60, len(projs))):
            q = projs[j]
            if (q['dept'], q['agency'], q['kind']) != (p['dept'], p['agency'], p['kind']) or q['regions']: break
            t += q['amount']
            if t == p['amount'] and j > i:
                p['rollup'] = 1
                for q in projs[i + 1:j + 1]: q['parent_id'] = p['id']
                break
            if t > p['amount']: break
    return projs, regs, printed

if __name__ == '__main__':
    for c in sys.argv[1:] or ['A', 'B']:
        projs, regs, printed = parse(c)
        with open(f'../data/gab_projects_{c}.csv', 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=['id', 'copy', 'page', 'dept', 'agency', 'kind', 'project', 'amount', 'ps', 'mooe', 'fin', 'co', 'loan', 'gop', 'regions', 'rollup', 'parent_id']); w.writeheader(); w.writerows(projs)
        with open(f'../data/gab_project_regions_{c}.csv', 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=['project_id', 'source', 'region', 'office', 'amount', 'ps', 'mooe', 'fin', 'co']); w.writeheader(); w.writerows(regs)
        by = collections.defaultdict(lambda: [0, 0])
        for p in projs:
            if not p['rollup']: by[(p['dept'], p['kind'])][0] += p['amount']
        for k, v in printed.items(): by[(k[0], k[2])][1] += v
        print(f'{c}: {len(projs)} projects P{sum(p["amount"] for p in projs if not p["rollup"])/1e9:.2f}B (rollups excluded: {sum(p["rollup"] for p in projs)}), {len(regs)} region/office rows, {len({p["dept"] for p in projs})} depts')
        ok = sum(1 for v in by.values() if v[1] and v[0] == v[1])
        print(f'   dept/kind blocks exact to printed: {ok}/{sum(1 for v in by.values() if v[1])}')
        for k, v in sorted(by.items(), key=lambda kv: -abs(kv[1][0] - kv[1][1])):
            if v[0] != v[1]: print(f'   {k[0][:40]:40} {k[1]}  parsed {v[0]/1e9:9.3f}B  printed {v[1]/1e9:9.3f}B')
