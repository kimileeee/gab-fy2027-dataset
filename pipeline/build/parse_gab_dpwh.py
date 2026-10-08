"""DPWH Vol I-C project rows from both copies inside CR00638.pdf (A = as filed, B = [3RD READING]).
Hierarchy is pattern-based (indents differ between copies); a leaf is any amount row indented deeper than the last DEO row.
The range ends with the LOCALLY-FUNDED PROJECTS list (Buildings - Multipurpose/Facilities + PPP Strategic Support Fund); its rows go
to ../data/gab_dpwh_tail_rows_{A,B}.csv, everything before it to ../data/gab_dpwh_rows_{A,B}.csv. Parsing stops at FOREIGN-ASSISTED
PROJECTS (parse_gab_dpwh_fap.py). Prints a DEO-subtotal reconciliation and the LF list vs its printed heading. Run from build/."""
import csv, re, sys, hashlib, collections, pymupdf
from gab_pdf import page_rows, fold

PDF = '../raw/hb10858/CR00638.pdf'
RANGES = {'A': (2399, 2923), 'B': (5966, 6795)}   # 1-based CR page numbers: Vol I-C DPWH project details (after the PAP summary) through the LF list
TAIL_ID_BASE = {'A': 2912, 'B': 6782}  # tail ids number leaves from this page on, as the first (frozen) tail extract did, so they stay stable
VERB = r'(?:Construction|Rehabilitation|Improvement|Repair|Maintenance|Upgrading|Retrofitting|Installation|Widening|Concreting|Procurement|Purchase|Completion|Reconstruction|Preventive|Replacement|Seal|Road|Bridge|Flood|Drainage|Slope|Seawall|Provision)'
DEO = re.compile(rf'^(?!{VERB})(?:[A-Za-z0-9 .,\-\'/()&]+?)(?:District Engineering Office|Regional Office|Central Office|Engineering Office|Office)$', re.I)
REGION = re.compile(r'^(?:\d+\.\s*)?(National Capital Region(?: \(NCR\))?|Cordillera Administrative Region(?: \(CAR\))?|Negros Island Region|Region [IVX]+(?:-[AB])?(?: - .*)?|[IVX]+-?[AB]? - .*|CALABARZON|MIMAROPA(?: Region)?|Bangsamoro.*|BARMM|CARAGA(?: Region)?|Caraga.*|Central Office|Nationwide)$', re.I)
PROG = re.compile(r'^[A-Za-z][A-Za-z,&\-/() ]{3,90}\bProgram$', re.I)
NUM = re.compile(r'^(?:[a-z]|\d{1,3})\.\s+')
HDR_X = {'A': 204, 'B': 192}     # x of the 'PROGRAMS / ACTIVITIES / PROJECTS' column header on a zero-offset page
LEAF_X = {'A': 176, 'B': 134}    # normalised x at/after which an amount row is a project (deepest level)
SKIP = ('PROGRAMS / ACTIVITIES / PROJECTS', 'AMOUNT (Php)', 'DETAILS OF DPWH')

def clean(t): return re.sub(r'\s+', ' ', NUM.sub('', t.strip()))

def parse(copy):
    lo, hi = RANGES[copy]
    d = pymupdf.open(PDF)
    ctx = dict(program='', region='', deo='', anchor_x=None, anchor_kind='')
    leaves, tail, deos, progs = [], [], [], []
    out = leaves
    for pn in range(lo, hi + 1):
        rows, _ = page_rows(d[pn - 1])
        hdr = next((r['x'] for r in rows if 'PROGRAMS / ACTIVITIES / PROJECTS' in r['text']), HDR_X[copy])
        off = hdr - HDR_X[copy]
        for r in fold(rows):
            t, x = clean(r['text']), r['x'] - off
            if any(k in r['text'] for k in SKIP) or '....' in t: continue
            if t == 'FOREIGN-ASSISTED PROJECTS': return leaves, tail, deos, progs
            if t == 'LOCALLY-FUNDED PROJECTS':
                out = tail; ctx.update(program='', region='', deo='', anchor_x=None, anchor_kind='')
                progs.append(dict(copy=copy, page=pn, program=t, amount=r['amt'])); continue
            if PROG.match(t):
                ctx.update(program=t, anchor_x=None, anchor_kind='', deo='')
                if r['amt'] is not None: progs.append(dict(copy=copy, page=pn, program=t, amount=r['amt']))
                continue
            if REGION.match(t):
                ctx.update(region=t, anchor_x=x, anchor_kind='region', deo=''); continue
            if r['amt'] is None: continue
            if DEO.match(t):
                ctx.update(deo=t, anchor_x=x, anchor_kind='deo')
                deos.append(dict(copy=copy, page=pn, program=ctx['program'], region=ctx['region'], deo=t, amount=r['amt'])); continue
            if x >= LEAF_X[copy]:
                out.append(dict(copy=copy, page=pn, program=ctx['program'], region=ctx['region'], deo=ctx['deo'], project=t, amount=r['amt']))
    raise ValueError(f'copy {copy}: FOREIGN-ASSISTED PROJECTS heading not found by p{hi}')

if __name__ == '__main__':
    for c in sys.argv[1:] or ['A', 'B']:
        L, T, D, PG = parse(c)
        base = sum(1 for x in L if x['page'] >= TAIL_ID_BASE[c])
        for pfx, rows, i0, fn in (('DPWH', L, 0, 'gab_dpwh_rows'), ('DPWHTAIL', T, base, 'gab_dpwh_tail_rows')):
            for i, x in enumerate(rows, i0): x['id'] = hashlib.sha1(f"{pfx}|{c}|{x['page']}|{i}".encode()).hexdigest()[:12]   # stable row id
            rows = [{'id': x['id'], **{k: v for k, v in x.items() if k != 'id'}} for x in rows]
            with open(f'../data/{fn}_{c}.csv', 'w', newline='', encoding='utf8') as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        lf = next(x['amount'] for x in PG if x['program'] == 'LOCALLY-FUNDED PROJECTS'); ts = sum(x['amount'] for x in T)
        print(f'copy {c}: LF list rows={len(T)} total=P{ts:,} | printed heading P{lf:,} | {"ties" if ts == lf else "DIFF"}')
        L = L + T
        by = collections.defaultdict(int); dsum = collections.defaultdict(int)
        for x in L: by[(x['program'], x['region'], x['deo'])] += x['amount']
        for x in D: dsum[(x['program'], x['region'], x['deo'])] += x['amount']
        ok = sum(1 for k, v in dsum.items() if by.get(k) == v)
        print(f'copy {c}: leaves={len(L)} total=P{sum(x["amount"] for x in L)/1e9:.2f}B | DEO groups={len(dsum)} reconciled={ok} ({100*ok/max(1,len(dsum)):.0f}%)')
        pg = collections.defaultdict(int)
        for x in L: pg[x['program']] += x['amount']
        hdr = collections.defaultdict(list)
        for x in PG: hdr[x['program']].append(x['amount'])
        for p, v in sorted(pg.items(), key=lambda kv: -kv[1])[:10]: print(f'    leaves P{v/1e9:8.2f}B | header rows {[round(h/1e9,2) for h in hdr.get(p, [])][:4]}  {p[:60]}')
