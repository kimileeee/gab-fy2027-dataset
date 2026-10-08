"""Build release/ from the parsed GAB trees (pap_{A,B}.csv, one per agency per copy) and BetterGov's NEP 2027 (agency crosswalk).

Phase 2 of gab-dataset-plan.md: appropriations.csv (fact: one leaf x stage), declared_totals.csv (every printed total, with the sum
of the leaves under it), object_of_expenditure.csv, CHECKS.md. A leaf is a printed amount row with no child row - derived from
parent_id, never from the parser's `role` (see CONTEXT.md). Amounts are integer pesos (object tables are printed in thousands).
Usage: python pipeline/run.py && python scripts/build.py && python scripts/package.py (paths: --help)"""
import argparse, collections, csv, glob, hashlib, os, re
import duckdb
import compare, dims, drilldowns, geo, nep_match, provisions

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = {'A': 'GAB_FILED', 'B': 'GAB_3R'}
CLASSES = ('ps', 'mooe', 'fin', 'co')

def norm(s): return re.sub(r'[^a-z0-9]', '', s.lower())
def h(*parts): return hashlib.sha1('|'.join(map(str, parts)).encode()).hexdigest()[:12]
def num(v): return int(float(v)) if v not in ('', None) else None

# --- hierarchy: a leaf's chain (path + label) follows the PREXC tiers -----------------------------------------------------
SKIP = {norm(s) for s in ('TOTAL NEW APPROPRIATIONS', 'Regular Programs', 'Regular Program', 'Programs', 'Project(s)', 'Projects')}
CATEGORY = {norm(k): v for k, v in {
    'General Administration and Support': 'General Administration and Support',
    'Support to Operations': 'Support to Operations',
    'Operations': 'Operations',
    'Locally-Funded Project(s)': 'Locally-Funded Projects', 'Locally-Funded Projects': 'Locally-Funded Projects',
    'Foreign-Assisted Project(s)': 'Foreign-Assisted Projects', 'Foreign-Assisted Projects': 'Foreign-Assisted Projects',
}.items()}
FUNDING = {norm(k): v for k, v in {'Loan Proceeds': 'Loan Proceeds', 'GOP Counterpart': 'GOP Counterpart',
                                   'Grant': 'Grant', 'Grants': 'Grant'}.items()}
# whole-heading match only: 'Negros Island Region Center for Health Development' is an office, not a region
REGION = re.compile(r'^(Region\s+[IVX]+\s*-?\s*[AB]?(\s*-\s*.+)?|National Capital Region(\s*\(NCR\))?|Cordillera Administrative Region'
                    r'(\s*\(CAR\))?|Negros Island Region(\s*\(NIR\))?|Bangsamoro Autonomous Region.*|BARMM)$', re.I)
SUBPROG = re.compile(r'SUB-?\s?PROGRAM$', re.I)
SUBTOTAL = re.compile(r'^(Sub-?\s?total|Total),\s*', re.I)
COLS_H = ('category', 'program', 'sub_program', 'pap', 'sub_pap', 'funding_source', 'region_printed', 'operating_unit', 'sub_unit')
APP_COLS = ('appropriation_id', 'stage', 'fiscal_year', 'dept_id', 'agency_id', 'dept_printed', 'agency_printed', 'category', 'program',
            'sub_program', 'pap', 'sub_pap', 'funding_source', 'region_printed', 'region_code', 'operating_unit', 'sub_unit', 'geo_level', 'psgc_code', 'province_psgc', 'district_id',
            'geo_basis', 'drilldown_group_id', 'label',
            'ps', 'mooe', 'finex', 'co', 'amount', 'prexc_fpap_id', 'nep_description', 'nep_operunit', 'nep_operunit_name', 'nep_fund_type',
            'nep_match', 'pdf_page', 'path_printed', 'source_row_id')

def classify(chain):
    """Split a printed chain into tier columns. Everything after the first region heading is geography/operating units."""
    out = dict.fromkeys(COLS_H, ''); paps, units = [], []
    for s in chain:
        n = norm(s)
        if n in FUNDING: out['funding_source'] = FUNDING[n]; continue     # 'Loan Proceeds' can print below the region/office rows
        if out['region_printed']: units.append(s); continue
        if n in SKIP: continue
        if SUBTOTAL.match(s):                     # a closing sub-total the parser made a parent (MSU): structural, but names its category
            c = norm(SUBTOTAL.sub('', s))
            if c in CATEGORY and not out['category']: out['category'] = CATEGORY[c]
            continue
        if n in CATEGORY:                         # DEPDev prints 'Operations' twice (heading + amount line): never a PAP
            out['category'] = out['category'] or CATEGORY[n]
        elif REGION.match(s): out['region_printed'] = s
        elif s.isupper() and SUBPROG.search(s): out['sub_program'] = s
        elif s.isupper() and 'PROGRAM' in s and not out['program']: out['program'] = s
        else: paps.append(s)
    out['pap'] = paps[0] if paps else ''
    out['sub_pap'] = ' > '.join(paps[1:])
    out['operating_unit'] = units[0] if units else ''
    out['sub_unit'] = ' > '.join(units[1:])
    return out

def chain_of(r): return ([s.strip() for s in r['path'].split(' > ')] if r['path'] else []) + [r['label']]

# --- inputs -----------------------------------------------------------------------------------------------------------------
def load_trees(gab):
    """{(copy, dept_slug, agency_slug): rows} in printed (file) order."""
    trees = {}
    for f in sorted(glob.glob(os.path.join(gab, '*', '*', 'pap_[AB].csv'))):
        parts = os.path.normpath(f).split(os.sep)
        trees[(parts[-1][4], parts[-3], parts[-2])] = list(csv.DictReader(open(f, encoding='utf-8')))
    return trees

def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60] or 'no-agency'   # = gab_tree.slug (folder names)

def printed_names(gab, folders):
    """(dept_slug, agency_slug) -> the bill's own Table of Contents row (copy A first, then B): printed department and agency names,
    Roman-numeral department code, agency letter, and for SUCs the regional group (A-S). Folder slugs are lossy, so 3 folders need a
    fallback: a slug truncated at 60 characters (prefix match within the department) or a body name that differs from the TOC
    (Marinduque State University vs ...State College)."""
    toc = {}
    for c in 'AB':
        for r in csv.DictReader(open(os.path.join(gab, f'toc_{c}.csv'), encoding='utf-8')):
            if r['kind'] == 'agency': toc.setdefault((slug(r['dept']), slug(r['agency'])), r)
            elif r['kind'] == 'dept': toc.setdefault((slug(r['dept']), 'no-agency'), dict(r, agency=r['dept']))
    names = {}
    for d, g in folders:
        t = toc.get((d, g)) or next((v for (td, tg), v in toc.items() if td == d and (tg.startswith(g) or g.startswith(tg[:40]))), None)
        if t is None:
            base = next((v for (td, _), v in toc.items() if td == d), {})
            t = dict(dept=base.get('dept', d.replace('-', ' ').upper()), dept_code=base.get('dept_code', ''),
                     agency=g.replace('-', ' ').upper(), agency_code='', group_code='', group='')
        names[(d, g)] = t
    return names

def nep_agencies(nep):
    """NEP 2027 new appropriations (fund codes 101*) per UACS agency, in pesos -> {amount: (dept, agency, dept_dsc, agency_dsc)}."""
    q = f"""select DEPARTMENT, AGENCY, any_value(UACS_DPT_DSC), any_value(UACS_AGY_DSC), sum(try_cast(replace(AMT, ',', '') as bigint)) * 1000
            from read_csv_auto('{nep.replace(os.sep, '/')}') where cast(FUNDCD as varchar) like '101%' group by 1, 2"""
    by = collections.defaultdict(list)
    for d, a, dd, ad, amt in duckdb.sql(q).fetchall():
        if amt: by[amt].append((str(d).zfill(2), str(a).zfill(3), dd, ad))
    return by

def load_known(path):
    return list(csv.DictReader(open(path, encoding='utf-8')))

def apply_adopt(rows, stage, dept, ag, known):
    """known_bill_errors adopt_next: the next n rows after a misprinted heading become its children (the parser kept them as siblings)."""
    for k in known:
        if k['action'] != 'adopt_next' or (k['stage'], k['dept_slug'], k['agency_slug']) != (stage, dept, ag): continue
        i = next(i for i, r in enumerate(rows) if r['table'] == k['table'] and r['label'] == k['row_label'] and r['page'] == k['page'])
        for r in rows[i + 1:i + 1 + int(k['n'])]: r['parent_id'] = rows[i]['id']

# --- build ------------------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gab', default=os.path.join(HERE, '..', 'pipeline', 'data', 'gab'), help='parsed trees (pipeline/run.py)')
    ap.add_argument('--nep', default=os.path.join(HERE, '..', 'inputs', 'NEP-FY2027.csv'), help='BetterGov nep-2027 (inputs/SOURCES.md)')
    ap.add_argument('--psgc', default=os.path.join(HERE, '..', 'inputs', 'PSGC-2Q-2026-Publication-Datafile.xlsx'), help='PSA PSGC (inputs/SOURCES.md)')
    ap.add_argument('--ph-data', default=os.path.join(HERE, '..', 'pipeline', 'data'), help='parsed lists + curated tables (pipeline/run.py)')
    ap.add_argument('--pdf-text', default=os.path.join(HERE, '..', 'pipeline', 'data', 'cr638_pages.duckdb'), help='per-page bill text (acronyms)')
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'release'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    trees, nep = load_trees(a.gab), nep_agencies(a.nep)
    names = printed_names(a.gab, {(d, g) for (c, d, g) in trees})
    known = load_known(os.path.join(HERE, 'curated', 'known_bill_errors.csv'))
    known_mm = {(k['stage'], k['dept_slug'], k['agency_slug'], k['table']): k['note'] for k in known if k['action'] == 'known_mismatch'}

    # agency crosswalk: copy A (= NEP as filed) by exact amount; copy B inherits by folder, then by agency slug (agencies can move dept)
    agency, problems = {}, []
    for (c, d, g), rows in trees.items():
        if c != 'A': continue
        lead = [num(r['total']) for r in rows if r['role'] == 'lead']
        m = nep.get(lead[0], []) if lead else []
        if len(m) == 1: agency[(d, g)] = m[0]
        else: problems.append(f'copy A {d}/{g}: {len(m)} NEP agencies match lead {lead}')
    by_slug = collections.defaultdict(list)
    for (d, g), v in agency.items(): by_slug[g].append(v)
    for (c, d, g) in trees:
        if c == 'B' and (d, g) not in agency:
            if len(by_slug[g]) == 1: agency[(d, g)] = by_slug[g][0]
            else: problems.append(f'copy B {d}/{g}: no unique copy-A agency to inherit from')

    apps, decl, objs, checks = [], [], [], collections.defaultdict(list)
    for (c, d, g), rows in sorted(trees.items()):
        stage = STAGE[c]
        if (d, g) not in agency: continue
        u = agency[(d, g)]; agency_id = f'{u[0]}-{u[1]}'
        dept_p, ag_p = names[(d, g)]['dept'], names[(d, g)]['agency']
        base = dict(stage=stage, fiscal_year=2027, dept_id=u[0], agency_id=agency_id, dept_printed=dept_p, agency_printed=ag_p)
        apply_adopt(rows, stage, d, g, known)
        kids = collections.defaultdict(list)        # keyed by (table, id): parser ids are only unique within a table
        for r in rows: kids[(r['table'], r['parent_id'])].append(r)
        dup = collections.Counter((r['table'], r['id']) for r in rows)
        checks['id_collision'] += [f"{stage} {ag_p}: id {i} used {n}x in table '{t}'" for (t, i), n in dup.items() if n > 1]
        ch_of = lambda r: kids[(r['table'], r['id'])]
        is_leaf = lambda r: not ch_of(r) and r['total'] != '' and r['role'] in ('item', 'group')
        memo = {}
        def leaf_sum(r):
            k = (r['table'], r['id'])
            if k not in memo:
                memo[k] = num(r['total']) if is_leaf(r) else sum(leaf_sum(x) for x in ch_of(r))
            return memo[k]
        occ = collections.Counter()
        tot = {}
        for r in rows:
            t, unit = r['table'], (1000 if r['table'] == 'object' else 1)
            if not t: continue
            if r['role'] == 'total': tot[t] = (num(r['total']) * unit, leaf_sum(r) * unit)
            ch = chain_of(r)
            if t == 'detail' and is_leaf(r):
                key = norm('>'.join(s for s in ch if norm(s) not in SKIP)); occ[key] += 1
                amt = {k: num(r[k]) for k in CLASSES}
                if sum(v or 0 for v in amt.values()) not in (0, num(r['total'])):
                    checks['class_sum'].append(f"{stage} {ag_p} p{r['page']}: {r['label']} PS+MOOE+FIN+CO != {r['total']}")
                apps.append(dict(appropriation_id=h(agency_id, key, occ[key]), **base, **classify(ch), label=r['label'],
                                 ps=amt['ps'], mooe=amt['mooe'], finex=amt['fin'], co=amt['co'], amount=num(r['total']),
                                 pdf_page=r['page'], path_printed=' > '.join(ch[:-1]), source_row_id=r['id']))
            elif t == 'object' and is_leaf(r):
                p = ch[:-1]
                cls = next((s.replace('Total ', '') for s in p if re.search(r'Personnel Services|Maintenance and Other|Financial Expenses|Capital Outlay', s)), '')
                grp = p[p.index(next(s for s in p if cls and cls in s)) + 1].replace('Total ', '') if cls and p[-1].replace('Total ', '') != cls else ''
                objs.append(dict(**base, expense_class=cls, object_group=grp, object=r['label'], amount=num(r['total']) * unit,
                                 pdf_page=r['page'], path_printed=' > '.join(p)))
            elif r['total'] != '' and (ch_of(r) or r['role'] in ('total', 'subtotal')):
                ls = leaf_sum(r) if ch_of(r) else None
                if ls is None and r['parent_id']:          # a closing sub-total printed as a sibling: it sums its parent heading
                    par = next((x for x in rows if x['id'] == r['parent_id'] and x['table'] == t), None)
                    ls = leaf_sum(par) if par else None
                key = norm('>'.join(ch)); occ[('D', t, key)] += 1
                declared = num(r['total']) * unit; ls = None if ls is None else ls * unit
                note = known_mm.get((stage, d, g, t), '') if ls is not None and ls != declared else ''
                decl.append(dict(declared_id=h(agency_id, t, key, occ[('D', t, key)]), **base, table=t, role=r['role'], level=r['level'],
                                 label=r['label'], **(classify(ch) if t != 'object' else dict.fromkeys(COLS_H, '')),
                                 ps=None if num(r['ps']) is None else num(r['ps']) * unit, mooe=None if num(r['mooe']) is None else num(r['mooe']) * unit,
                                 finex=None if num(r['fin']) is None else num(r['fin']) * unit, co=None if num(r['co']) is None else num(r['co']) * unit,
                                 declared_amount=declared, leaf_sum=ls, difference=None if ls is None else ls - declared,
                                 ties='' if ls is None else int(ls == declared), known_bill_error=note, pdf_page=r['page'],
                                 path_printed=' > '.join(ch[:-1])))
        lead = [num(r['total']) for r in rows if r['role'] == 'lead']
        if lead: decl.append(dict(declared_id=h(agency_id, 'lead'), **base, table='lead', role='lead', level='', label='(agency appropriation, lead line)',
                                  **dict.fromkeys(COLS_H, ''), ps=None, mooe=None, finex=None, co=None, declared_amount=lead[0],
                                  leaf_sum=tot.get('detail', (0, None))[1], difference=tot.get('detail', (0, 0))[1] - lead[0],
                                  ties=int(tot.get('detail', (0, None))[1] == lead[0]), known_bill_error=known_mm.get((stage, d, g, 'detail'), '') if tot.get('detail', (0, None))[1] != lead[0] else '',
                                  pdf_page=next(r['page'] for r in rows if r['role'] == 'lead'), path_printed=''))
        for t in ('summary', 'object'):
            if t in tot and 'detail' in tot and tot[t][0] != tot['detail'][0]:
                checks['cross_table'].append(f'{stage} {ag_p}: {t} total {tot[t][0]:,} != detail total {tot["detail"][0]:,}')
        checks['agency_stage'].append((stage, ag_p, d, g, lead[0] if lead else None))

    nep_match.attach(apps, a.nep)
    psgc_rows = geo.attach(apps, a.psgc, a.ph_data)
    items, cov = drilldowns.build(apps, a.ph_data, a.psgc, psgc_rows)
    write(a.out, 'drilldown_items.csv', items)
    write(a.out, 'drilldown_coverage.csv', cov)
    cmp_rows = compare.compare(apps)
    write(a.out, 'appropriations_compared.csv', [{k: r[k] for k in compare.COLS} for r in cmp_rows])
    old = [r for f in glob.glob(os.path.join(a.gab, '*', 'pap_compare.csv')) for r in csv.DictReader(open(f, encoding='utf-8'))]
    checks['compare'] = compare.checks(cmp_rows, old)
    write(a.out, 'appropriations.csv', [{k: r[k] for k in APP_COLS} for r in apps])
    for name, rows in zip(('regions.csv', 'localities.csv', 'districts.csv', 'operating_units.csv'),
                          geo.dimension_rows(apps, psgc_rows, a.ph_data, os.path.join(a.ph_data, 'regions.csv'))):
        write(a.out, name, rows)
    D, A = dims.build([dict(agency_id=f'{agency[(d, g)][0]}-{agency[(d, g)][1]}', dept_id=agency[(d, g)][0], uacs_dept_name=agency[(d, g)][2],
                            uacs_agency_name=agency[(d, g)][3], toc=names[(d, g)], stage=STAGE[c]) for (c, d, g) in sorted(trees) if (d, g) in agency],
                      a.pdf_text)
    write(a.out, 'departments.csv', D); write(a.out, 'agencies.csv', A)
    checks['dims'] = ['', '## Departments and agencies (phase 7, D12)', '',
                      f"- departments: {len(D)}, with acronym {sum(1 for d in D if d['acronym'])}; agencies: {len(A)}, with acronym {sum(1 for x in A if x['acronym'])} "
                      f"({dict(collections.Counter(x['acronym_source'] or '(none)' for x in A))})",
                      '- agencies without an official acronym found, by department: ' +
                      ', '.join(f'{k} {v}' for k, v in collections.Counter(x['dept_id'] for x in A if not x['acronym']).most_common())]
    prov, gaps = provisions.build(a.ph_data, agency, names, trees)
    pcmp = provisions.compare(prov)
    write(a.out, 'special_provisions.csv', prov); write(a.out, 'special_provisions_compared.csv', pcmp)
    checks['dims'] += provisions.checks(prov, pcmp, gaps)
    write(a.out, 'declared_totals.csv', decl)
    write(a.out, 'object_of_expenditure.csv', objs)
    write_checks(a.out, apps, decl, objs, checks, problems, trees, agency, items, cov)

def write(out, name, rows):
    with open(os.path.join(out, name), 'w', newline='', encoding='utf-8-sig') as f:   # BOM: Excel shows 'Piñas', not mojibake
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f'{name}: {len(rows):,} rows')

def write_checks(out, apps, decl, objs, checks, problems, trees, agency, items, cov):
    L = ['# CHECKS — generated by scripts/build.py; do not edit', '']
    by_stage = collections.defaultdict(lambda: [0, 0])
    for r in apps: by_stage[r['stage']][0] += 1; by_stage[r['stage']][1] += r['amount']
    L += ['## Appropriations (leaves)', '', '| stage | rows | total (₱) |', '|---|---:|---:|']
    L += [f'| {s} | {n:,} | {v:,} |' for s, (n, v) in sorted(by_stage.items())]
    L += ['', f'Agency crosswalk: {len({(d, g) for (c, d, g) in trees})} agency folders, {len(agency)} matched to a UACS agency via NEP 2027.']
    L += [f'- PROBLEM: {p}' for p in problems] or ['- every agency matched']
    tie = [r for r in decl if r['ties'] == 0]
    unexpected = [r for r in tie if not r['known_bill_error']]
    L += ['', '## Tie-out: declared totals vs the leaves beneath them', '',
          f'{sum(1 for r in decl if r["ties"] == 1):,} tie, {len(tie)} do not ({len(tie) - len(unexpected)} explained by `known_bill_errors.csv`, '
          f'**{len(unexpected)} unexpected**), {sum(1 for r in decl if r["ties"] == "")} have nothing to compare.', '']
    lead_bad = [r for r in decl if r['table'] == 'lead' and r['ties'] == 0]
    L += [f'Agency leaf sum = lead line: {sum(1 for r in decl if r["table"] == "lead") - len(lead_bad)} / {sum(1 for r in decl if r["table"] == "lead")} agency × stage.', '']
    if unexpected:
        L += ['### Unexpected mismatches (fix the parser or add a page-checked entry to `known_bill_errors.csv`)', '',
              '| stage | agency | table | label | declared | leaf sum | diff | page |', '|---|---|---|---|---:|---:|---:|---:|']
        L += [f"| {r['stage']} | {r['agency_printed']} | {r['table']} | {r['label'][:60]} | {r['declared_amount']:,} | {r['leaf_sum']:,} | {r['difference']:,} | {r['pdf_page']} |"
              for r in sorted(unexpected, key=lambda r: -abs(r['difference']))[:80]]
        if len(unexpected) > 80: L.append(f'| … {len(unexpected) - 80} more | | | | | | | |')
    L += ['', '### Explained by known bill errors', ''] + sorted({f"- {r['stage']} {r['agency_printed']} ({r['table']}): {r['known_bill_error']}" for r in tie if r['known_bill_error']})
    L += ['', '## Cross-table totals (summary and object tables vs detail)', ''] + ([f'- {x}' for x in checks['cross_table']] or ['- all agree'])
    L += ['', '## PS + MOOE + FinEx + CO = amount', ''] + ([f'- {x}' for x in checks['class_sum']] or ['- holds on every leaf'])
    empty = collections.Counter(r['stage'] for r in apps if not r['pap'] and not r['program'])
    L += ['', '## Hierarchy columns', '',
          f"- leaves with neither program nor PAP: {dict(empty) or 0}",
          f"- leaves with a region: {sum(1 for r in apps if r['region_printed']):,} / {len(apps):,}",
          f"- leaves with an operating unit: {sum(1 for r in apps if r['operating_unit']):,}",
          f"- category values: {dict(collections.Counter(r['category'] or '(none)' for r in apps))}"]
    m = collections.Counter((r['stage'], r['nep_match']) for r in apps)
    L += ['', '## NEP 2027 match (phase 3)', '', '| stage | match | rows | ₱ |', '|---|---|---:|---:|']
    L += [f"| {s} | {k} | {n:,} | {sum(r['amount'] for r in apps if r['stage'] == s and r['nep_match'] == k):,} |" for (s, k), n in sorted(m.items())]
    chk = [r for r in apps if r['stage'] == 'GAB_FILED' and r['nep_match'] in ('unique', 'disambiguated') and r['region_code']]
    bad = [r for r in chk if r['_nep_reg'] != r['region_code']]
    L += ['', f'Region agreement (matched GAB_FILED rows with a printed region): {len(chk) - len(bad):,} / {len(chk):,}']
    L += [f"- {r['agency_printed']} | {r['region_printed']} (={r['region_code']}) vs NEP {r['_nep_reg']} | {r['label'][:50]} | {r['nep_match']}"
          for r in bad[:15]]
    nomatch = collections.Counter(r['agency_printed'] for r in apps if r['stage'] == 'GAB_FILED' and r['nep_match'] == 'none')
    L += ['', 'Unmatched GAB_FILED rows by agency (top 15): ' + ', '.join(f'{k} {v}' for k, v in nomatch.most_common(15))]
    L += ['', '## Map attribution (phase 4, D6)', '', '| stage | geo_level | rows | ₱ | share |', '|---|---|---:|---:|---:|']
    for s in ('GAB_FILED', 'GAB_3R'):
        S = [r for r in apps if r['stage'] == s]; T = sum(r['amount'] for r in S)
        for lvl, n in collections.Counter(r['geo_level'] for r in S).most_common():
            v = sum(r['amount'] for r in S if r['geo_level'] == lvl); L.append(f'| {s} | {lvl} | {n:,} | {v:,} | {100 * v / T:.1f}% |')
    L += ['', 'geo_basis (GAB_3R): ' + ', '.join(f'{k} {v:,}' for k, v in collections.Counter(r['geo_basis'] for r in apps if r['stage'] == 'GAB_3R').most_common())]
    bad = [r for r in apps if r['geo_level'] in ('central_office', 'national') and r['psgc_code']]
    L += [f'- central_office / national rows carrying a place code: {len(bad)} (must be 0)']
    top = collections.Counter()
    for r in apps:
        if r['stage'] == 'GAB_3R' and r['geo_basis'] == 'office not placeable below region': top[r['operating_unit']] += r['amount']
    L += ['- largest offices left at region level (candidates for a curated office -> place table): ' +
          '; '.join(f'{k} ₱{v / 1e9:.1f}B' for k, v in top.most_common(12))]
    L += ['', '## Drill-downs (phase 5, ADR 0001)', '', '| stage | source | groups | items | parent ₱ | drill-down ₱ | coverage | group status |',
          '|---|---|---:|---:|---:|---:|---:|---|']
    agg = collections.defaultdict(list)
    for c in cov: agg[(c['stage'], c['source'])].append(c)
    for (s, src), G in sorted(agg.items()):
        P = sum(c['parent_amount'] or 0 for c in G); D = sum(c['drilldown_amount'] or 0 for c in G)
        st = dict(collections.Counter(c['status'] for c in G))
        L.append(f"| {s} | {src} | {len(G)} | {sum(c['items'] for c in G):,} | {P:,} | {D:,} | {D / P:.4f} | {st} |" if P else
                 f"| {s} | {src} | {len(G)} | {sum(c['items'] for c in G):,} | – | {D:,} | – | {st} |")
    L += ['', 'Item placement (GAB_3R): ' + ', '.join(f'{k or "(none)"} {v:,}' for k, v in collections.Counter(i['geo_level'] for i in items if i['stage'] == 'GAB_3R').most_common())]
    L += checks['compare'] + checks['dims']
    L += ['', '## Parser id collisions (handled: rows are keyed by table + id)', ''] + ([f'- {x}' for x in checks['id_collision']] or ['- none'])
    ids = collections.Counter((r['stage'], r['appropriation_id']) for r in apps)
    L += ['', '## Keys', '', f"- duplicate (stage, appropriation_id): {sum(1 for v in ids.values() if v > 1)}",
          f"- ids present in both stages: {len({i for s, i in ids if s == 'GAB_FILED'} & {i for s, i in ids if s == 'GAB_3R'}):,}"]
    L += ['', f'## Object of expenditure', '', f'- {len(objs):,} rows; without an expense class: {sum(1 for r in objs if not r["expense_class"])}']
    open(os.path.join(out, 'CHECKS.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('CHECKS.md:', f'{len(unexpected)} unexpected tie-out mismatches,', f'{len(problems)} crosswalk problems')

if __name__ == '__main__':
    main()
