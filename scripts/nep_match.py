"""Phase 3: attach BetterGov NEP 2027 codes (PREXC FPAP id, UACS region, operating unit, fund) to each appropriation.

GAB_FILED (the bill as filed) is the NEP as submitted, so its leaves are matched to NEP line groups on the exact amount signature
(total, PS, MOOE, FinEx, CO) within the same UACS agency. NEP groups are formed at two grains: (FPAP, region, operating unit) and, for
lines split by fund, (FPAP, region, operating unit, fund type) where fund type is regular / loan proceeds (all foreign-loan funds
together: NSCR is ADB + JICA) / GOP counterpart. Passes: (1) signature unique in the agency; (2) ambiguous signature, best region +
name score first, each NEP group used once; (3) residual: a bill line that aggregates every NEP operating unit of its division not
itemized in the bill (DepEd 'Division Office - Proper' = division total minus the schools printed separately).
GAB_2R and GAB_3R rows inherit the codes of the same appropriation_id in GAB_FILED."""
import collections, difflib, os, re
import duckdb

NEP_COLS = ('region_code', 'prexc_fpap_id', 'nep_description', 'nep_operunit', 'nep_operunit_name', 'nep_fund_type', 'nep_match')

def norm(s): return re.sub(r'[^a-z0-9]', '', (s or '').lower())

# printed region heading -> 2-digit code shared by PSGC and UACS (D8). Matched on the descriptive name, not the numeral: the bill
# misprints numerals at least once ('Region XI - Zamboanga Peninsula') and spells SOCCSKSARGEN two ways.
REGION_CODE = [(r'National Capital', '13'), (r'Cordillera', '14'), (r'Ilocos', '01'), (r'Cagayan Valley', '02'), (r'Central Luzon', '03'),
               (r'CALABARZON', '04'), (r'MIMAROPA', '17'), (r'Bicol', '05'), (r'Western Visayas', '06'), (r'Negros Island', '18'),
               (r'Central Visayas', '07'), (r'Eastern Visayas', '08'), (r'Zamboanga', '09'), (r'Northern Mindanao', '10'),
               (r'Davao', '11'), (r'SOCC?S?K?SARGEN', '12'), (r'Caraga', '16'), (r'Bangsamoro|BARMM', '19')]
NUMERAL = {'I': '01', 'II': '02', 'III': '03', 'IVA': '04', 'IV-A': '04', 'IVB': '17', 'IV-B': '17', 'V': '05', 'VI': '06', 'VII': '07',
           'VIII': '08', 'IX': '09', 'X': '10', 'XI': '11', 'XII': '12', 'XIII': '16'}

def region_code(printed):
    if not printed: return ''
    for pat, code in REGION_CODE:
        if re.search(pat, printed, re.I): return code
    m = re.match(r'Region\s+([IVX]+(?:\s*-?\s*[AB])?)\b', printed, re.I)
    return NUMERAL.get(re.sub(r'\s', '', m.group(1)).upper(), '') if m else ''

def fund_type(fundcd):
    f = str(fundcd)
    return 'gop_counterpart' if f == '10102151' else 'loan_proceeds' if f.startswith('10102') else 'regular'

def add(v, w):
    for i in range(5): v[i] += w[i]

def nep_groups(nep):
    """Returns (groups: {agency: {signature: [group]}}, units: {(agency, fpap, reg, div): [coarse group]}), amounts in pesos."""
    q = f"""select DEPARTMENT, AGENCY, PREXC_FPAP_ID, coalesce(UACS_REG_ID, ''), coalesce(OPERUNIT, ''), FUNDCD, UACS_EXP_CD,
                   any_value(DSC), any_value(coalesce(UACS_OPER_DSC, '')), any_value(coalesce(UACS_DIV_DSC, '')),
                   any_value(coalesce(UACS_OPERDIV_ID, '')), sum(try_cast(replace(AMT, ',', '') as bigint)) * 1000
            from read_csv_auto('{nep.replace(os.sep, '/')}') where cast(FUNDCD as varchar) like '101%' and AMT is not null
            group by DEPARTMENT, AGENCY, PREXC_FPAP_ID, UACS_REG_ID, OPERUNIT, FUNDCD, UACS_EXP_CD"""
    slot = {1: 1, 2: 2, 3: 3, 6: 4}                     # UACS expense class -> signature slot (PS, MOOE, FinEx, CO)
    by_type, coarse, meta, types = (collections.defaultdict(lambda: [0] * 5), collections.defaultdict(lambda: [0] * 5),
                                    {}, collections.defaultdict(set))
    for d, a, fpap, reg, ou, fund, exp, dsc, oud, divd, divid, amt in duckdb.sql(q).fetchall():
        v = [0] * 5; v[0] = amt or 0
        if exp is not None and int(exp) in slot: v[slot[int(exp)]] = amt or 0
        ck = (f'{str(d).zfill(2)}-{str(a).zfill(3)}', fpap, reg, ou)
        add(coarse[ck], v); add(by_type[ck + (fund_type(fund),)], v); types[ck].add(fund_type(fund))
        meta[ck] = dict(dsc=dsc, ou_name=oud or divd, div=divid)
    groups = collections.defaultdict(lambda: collections.defaultdict(list)); units = collections.defaultdict(list)
    def mk(k, v, ft): return dict(key=k, vec=tuple(v), agency=k[0], fpap=k[1], reg=k[2], ou=k[3], fund_type=ft, **meta[k[:4]])
    for ck, v in coarse.items():
        ft = next(iter(types[ck])) if len(types[ck]) == 1 else 'mixed'
        g = mk(ck + ('',), v, ft)
        if v[0]: groups[ck[0]][tuple(v)].append(g)
        units[(ck[0], ck[1], ck[2], g['div'])].append(g)
    for k, v in by_type.items():
        if len(types[k[:4]]) > 1 and v[0]: groups[k[0]][tuple(v)].append(mk(k, v, k[4]))
    return groups, units

def score(r, g):
    """Higher = more likely the same line. Region agreement dominates; names break the rest."""
    rc = r['region_code'] or '13'                  # national/Central Office lines carry NEP region 13
    s = 2.0 if g['reg'] == rc else 0.0
    s += difflib.SequenceMatcher(None, norm(r['pap'] or r['label']), norm(g['dsc'])).ratio()
    unit = r['sub_unit'] or r['operating_unit']
    if unit or g['ou_name']: s += difflib.SequenceMatcher(None, norm(unit), norm(g['ou_name'])).ratio()
    return s

def attach(apps, nep):
    groups, units = nep_groups(nep)
    for r in apps:
        r.update(dict.fromkeys(NEP_COLS, '')); r['region_code'] = region_code(r['region_printed'])
    filed = [r for r in apps if r['stage'] == 'GAB_FILED']
    used, took = set(), {}
    def take(r, g, how):
        used.add(g['key'][:4]); took[id(r)] = g
        r.update(prexc_fpap_id=g['fpap'], nep_description=g['dsc'], nep_operunit=g['ou'], nep_operunit_name=g['ou_name'],
                 nep_fund_type=g['fund_type'], nep_match=how, _nep_reg=g['reg'])
    sig = lambda r: (int(r['amount']), *(int(r[k] or 0) for k in ('ps', 'mooe', 'finex', 'co')))
    pending = []
    for r in filed:                                   # pass 1: signature unique within the agency
        c = groups[r['agency_id']].get(sig(r), [])
        if len(c) == 1: take(r, c[0], 'unique')
        elif c: pending.append(r)
    # pass 2: ambiguous signatures, best-scoring free candidate first (greedy one-to-one; a split-fund group blocks its coarse twin)
    cand = [(score(r, g), i, r, g) for i, r in enumerate(pending) for g in groups[r['agency_id']][sig(r)]]
    for s, i, r, g in sorted(cand, key=lambda x: (-x[0], x[1])):
        if not r['nep_match'] and (g['key'][:4] not in used or g['key'][4]): take(r, g, 'disambiguated')
    # pass 3: residual lines - NEP units of the siblings' division that no bill line claimed, summed
    sib = collections.defaultdict(list)
    for r in filed: sib[(r['agency_id'], r['pap'], r['region_printed'], r['operating_unit'])].append(r)
    for r in filed:
        if r['nep_match']: continue
        gs = [took[id(s)] for s in sib[(r['agency_id'], r['pap'], r['region_printed'], r['operating_unit'])] if id(s) in took]
        divs = {(g['agency'], g['fpap'], g['reg'], g['div']) for g in gs}
        if len(divs) != 1: continue
        rest = [g for g in units[divs.pop()] if g['key'][:4] not in used]
        v = [0] * 5
        for g in rest: add(v, g['vec'])
        if rest and tuple(v) == sig(r):
            for g in rest: used.add(g['key'][:4])
            r.update(prexc_fpap_id=gs[0]['fpap'], nep_description=gs[0]['dsc'], nep_operunit='',
                     nep_operunit_name=f'{len(rest)} operating units not itemized in the bill', nep_fund_type='regular',
                     nep_match='residual', _nep_reg=gs[0]['reg'])
    for r in filed:
        if not r['nep_match']: r['nep_match'] = 'none'
    # GAB_2R / GAB_3R inherit through the shared appropriation_id
    by_id = {r['appropriation_id']: r for r in filed}
    for r in apps:
        if r['stage'] == 'GAB_FILED': continue
        a = by_id.get(r['appropriation_id'])
        if a is None: r['nep_match'] = 'no_filed_counterpart'; continue
        for k in NEP_COLS[1:] + ('_nep_reg',): r[k] = a.get(k, '')
    return apps                                       # '_nep_reg' is for CHECKS only; build.py drops it before writing
