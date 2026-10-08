"""Dedicated per-institution hierarchy builder for STATE UNIVERSITIES AND COLLEGES (dept IX) - structurally different
from every other department: Department -> Region (19 regions, lettered A-S) -> Institution (A.1, A.2, B.1, B.2...),
not the flat Department -> Agency every other department has. gab_tree.py's generic agency-detection, built for the
flat shape, needed three separate SUC-specific patches to limp through this one department (a quote mark in an
institution's own name breaking the AGENCY regex's charset; SUC's own region lettering ('I.', 'L.') colliding with
Roman numerals and firing the DEPT-transition logic; its trailing GENERAL SUMMARY roll-up page re-triggering agency
detection under near-but-not-quite-matching names) and still left an unresolved residual (136 folders for ~116
institutions - something was still off). This file replaces that detection with an explicit region/institution state
machine instead (CODE below, 'B.' vs 'B.1' is the only split that matters, and the title is captured as '.+' - any
character at all - so nothing like a quote mark can ever break it), and reuses gab_tree.py's proven per-institution
tree-building (blocks/wrap/tree/link_ids) completely unchanged, since that part was never broken.

Also parses the trailing GENERAL SUMMARY roll-up page into its own file and cross-checks it against each
institution's own lead total - the one thing gab_tree.py's generic path could only treat as noise to suppress, this
one can use properly, the same way parse_gab_dpwh.py validates against DPWH's printed program headers.

Output: same shape as gab_tree.py, so gab_office_compare.py needs no changes -
../data/gab/state-universities-and-colleges/<institution-slug>/pap_{A,B}.csv (+ projects_{A,B}.csv where printed),
plus .../general_summary_{A,B}.csv (the roll-up rows: region, code, institution, total) and a printed cross-check
report. Usage: python parse_gab_suc.py [A B]. Run from build/."""
import csv, os, re, sys, collections
from parse_gab_pap import lines
from gab_tree import blocks, wrap, tree, link_ids, outside, slug, norm, TABLE, HEADER, NOISE, LEAD, TOTAL, TNA, GENERIC, COLS

DEPT = 'STATE UNIVERSITIES AND COLLEGES'
CODE = re.compile(r'^([A-Z]{1,2})\.(?:(\d+)\.?)?\s+(.+)$')   # 'B.' = region heading (group 2 absent); 'B.1.' = institution
CODE_TYPO = re.compile(r'^([A-Z]{1,2})\.(I)\.?\s+(.+)$')     # the bill misprints 'J.1.' as 'J.I.' once (capital I for
                                                               # digit 1) in the GENERAL SUMMARY roll-up table only -
                                                               # the institution's own section heading is unaffected
nk = lambda t: re.sub(r'[^a-z0-9]', '', t.lower())[:25]


def events(copy):
    """Walk dept IX's pages; yield ('A'-kind amount rows, same shape as gab_tree.events()) plus the GENERAL SUMMARY
    roll-up rows, kept separate (`summary`)."""
    pages = [int(r['page']) for r in csv.DictReader(open(f'../data/gab_pap_{copy}.csv', encoding='utf8')) if r['dept'] == DEPT]
    region = inst = ''; table = None; pend = []; out = []; summary = []; in_summary = False; swrap = None
    def flush():
        nonlocal pend
        if table:
            for b in blocks(pend, table): out.append(dict(kind='H', agency=inst, table=table, pn=b[0]['pn'], rx=b[0]['rx'], label=' '.join(l['lab'] for l in b)))
        pend = []
    for L in lines(copy, min(pages), max(pages), small=True, keep_dash=True):
        L['lab'] = lab = norm(L['lab']); am = L['am']
        if lab.strip() == 'GENERAL SUMMARY': flush(); in_summary = True; continue
        if in_summary:
            m = CODE.match(lab) or CODE_TYPO.match(lab)
            if m and m.group(2) and am: summary.append(dict(region=region, code=f'{m.group(1)}.{m.group(2)}', inst=m.group(3).strip(), total=am[-1]))
            elif m and m.group(2) and not am: swrap = (f'{m.group(1)}.{m.group(2)}', m.group(3).strip())   # title wraps
            # to a second line in this table too (e.g. 'I.7. Dr. Emilio B. Espinosa, Sr. Memorial State College of' /
            # 'Agriculture and Technology'); its amounts land on that continuation line, matched below
            elif m and not m.group(2): region = m.group(3).strip(); swrap = None
            elif swrap and am: summary.append(dict(region=region, code=swrap[0], inst=f'{swrap[1]} {lab}'.strip(), total=am[-1])); swrap = None
            continue
        if not am:
            m = CODE.match(lab)
            # 'A. REGULAR PROGRAMS' / 'B. PROJECT(S)' etc. are an institution's own in-table program category, not a
            # region/institution code - same collision gab_tree.py's AGENCY detection already guards against with
            # this exact regex; without it here, hitting one mid-institution wipes `inst` back to '' right after a
            # real institution heading correctly set it.
            if m and not GENERIC.match(m.group(3).strip()):
                if not m.group(2): region = m.group(3).strip(); inst = ''; table = None; pend = []; continue
                inst = m.group(3).strip().upper(); table = None; pend = []; continue
            if HEADER.match(lab): flush(); table = next(t for k, t in TABLE if k in lab.lower()); continue
            if re.match(r'Special Provision', lab, re.I): flush(); table = None; continue
            if NOISE.match(lab) or (L['x'] or 0) >= 250: pend = []; continue      # column-header text sits right of x 250
            pend.append(L); continue
        bl = blocks(pend, table); glue = []
        if bl and wrap(bl[-1][-1], L, table): glue = bl.pop()
        pend = [l for b in bl for l in b]; flush()
        first = glue[0] if glue else L
        label = ' '.join([l['lab'] for l in glue] + [lab]).strip()
        if not label: continue
        cv = L['colv'] if L['colv'] and L['ok'] else {}
        out.append(dict(kind='A', agency=inst, table=table, pn=L['pn'], rx=first['rx'], label=label, amounts='|'.join(map(str, am)), total=am[-1],
                        **{k: cv.get(k) for k in ('ps', 'mooe', 'fin', 'co')}))
        if TNA.match(label): table = None
    return out, summary


def run(copy):
    E, summary = events(copy); rows = [e for e in E if e['kind'] == 'A']
    link_ids(copy, rows)
    segs = collections.defaultdict(list); order = []
    for e in E:     # a table = consecutive events with the same (institution, table); rows outside tables are lead/text
        k = (e['agency'], e['table'])
        if not order or order[-1] != k: order.append(k); segs[(k, len(order))] = []
        segs[(k, len(order))].append(e)
    for (k, _), S in segs.items():
        if k[1]: tree(S)
        else:
            for e in S:
                if e['kind'] == 'A': outside(e)
        for e in S:
            if e['kind'] == 'A' and e['parent'] is not None: e['parent_id'] = S[e['parent']]['id']
    out = collections.defaultdict(list)
    for e in rows: out[e['agency']].append(dict(e, copy=copy, page=e['pn'], table=e['table'] or '', parent_id=e.get('parent_id', '')))
    projs = collections.defaultdict(list)
    for p in csv.DictReader(open(f'../data/gab_projects_{copy}.csv', encoding='utf8')):
        if p['dept'] != DEPT: continue
        e = next((e for e in rows if e['table'] == 'detail' and e['pn'] == int(p['page']) and e['total'] == int(p['amount']) and nk(e['label']) == nk(p['project'])), None)
        projs[e['agency'] if e else p['agency']].append(dict(p, agency=e['agency'] if e else p['agency'], pap_id=e['id'] if e else '', sum_ok=e['sum_ok'] if e else ''))
    for ag, R in out.items():
        d = f'../data/gab/{slug(DEPT)}/{slug(ag)}'; os.makedirs(d, exist_ok=True)
        with open(f'{d}/pap_{copy}.csv', 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=COLS, extrasaction='ignore'); w.writeheader(); w.writerows(R)
    for ag, P in projs.items():
        d = f'../data/gab/{slug(DEPT)}/{slug(ag)}'; os.makedirs(d, exist_ok=True)
        with open(f'{d}/projects_{copy}.csv', 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=list(P[0])); w.writeheader(); w.writerows(P)
    d = f'../data/gab/{slug(DEPT)}'; os.makedirs(d, exist_ok=True)
    with open(f'{d}/general_summary_{copy}.csv', 'w', newline='', encoding='utf8') as f:
        w = csv.DictWriter(f, fieldnames=['region', 'code', 'inst', 'total']); w.writeheader(); w.writerows(summary)
    return out, summary


def report(copy, out, summary):
    print(f'== copy {copy}: {len(out)} institutions, {len(summary)} general-summary rows')
    by_name = {nk(a): a for a in out}
    miss_tree = []; miss_summary = []; mismatch = []
    for s in summary:
        a = by_name.get(nk(s['inst']))
        if a is None: miss_tree.append(s); continue
        lead = next((r['total'] for r in out[a] if r['role'] == 'lead'), None)
        if lead is None: lead = next((r['total'] for r in out[a] if r['role'] == 'total'), None)
        if lead != s['total']: mismatch.append((s, a, lead))
    summary_names = {nk(s['inst']) for s in summary}
    for a in out:
        if nk(a) not in summary_names: miss_summary.append(a)
    bad = [r for ag in out for r in out[ag] if r['sum_ok'] not in ('', 1, '1')]
    print(f'  cross-check vs GENERAL SUMMARY: {len(summary) - len(miss_tree) - len(mismatch)}/{len(summary)} match exactly')
    print(f'  arithmetic mismatches (child sum != printed total) across all institutions: {len(bad)}')
    if miss_tree: print(f'  !! in GENERAL SUMMARY but no matching institution built: {[s["inst"] for s in miss_tree][:10]}')
    if miss_summary: print(f'  !! institution built but not in GENERAL SUMMARY: {miss_summary[:10]}')
    for s, a, lead in mismatch[:10]: print(f'  !! {s["inst"][:45]:45} summary {s["total"]:>15,}  tree lead {lead if lead is not None else "(none)":>15}')


if __name__ == '__main__':
    for c in sys.argv[1:] or ['A', 'B']:
        out, summary = run(c)
        report(c, out, summary)
