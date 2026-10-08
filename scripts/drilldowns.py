"""Phase 5: drill-down tables (ADR 0001) - finer lists the bill prints elsewhere for some appropriations, never summed with them.

Sources (ph-pork-graph parser outputs): DPWH Vol I-C project rows (5 programs) and its locally-funded tail list; the DA farm-to-market
road (FMR), DOH Health Facilities Enhancement (HFEP), NIA irrigation and DILG Support to Barangay Development (SBDP) annexes.
Each item belongs to a drill-down group = (source, region[, program]); the group's parent is the set of appropriations it itemizes,
which get the same drilldown_group_id. drilldown_coverage.csv compares the two sums per stage. NIA's parent (Budgetary Support to
Government Corporations) and SBDP's (likely Allocations to LGUs) are back matter, not parsed yet; SBDP prints no amounts.
Items are placed on the map from what they print: DEO -> district (DPWH), province/municipality/barangay columns (SBDP, HFEP), the
trailing ', Municipality, Province' of the project title (FMR)."""
import collections, csv, hashlib, os, re
import openpyxl
import geo
from nep_match import region_code as _rc

STAGE = {'A': 'GAB_FILED', 'B': 'GAB_3R'}
ITEM_COLS = ('item_id', 'stage', 'source', 'drilldown_group_id', 'section', 'region_printed', 'region_code', 'office', 'province_printed',
             'municipality_printed', 'barangay_printed', 'item', 'amount', 'geo_level', 'psgc_code', 'province_psgc', 'district_id',
             'geo_basis', 'pdf_page', 'source_row_id')

def norm(s): return re.sub(r'[^a-z0-9]', '', (s or '').lower())
def h(*p): return hashlib.sha1('|'.join(map(str, p)).encode()).hexdigest()[:12]

SHORT = {'NCR': '13', 'CAR': '14', 'NIR': '18', 'BARMM': '19', 'CARAGA': '16', 'MIMAROPA': '17', 'CENTRAL OFFICE': '13'}
def region_code(s):
    s = (s or '').strip()
    return SHORT.get(s.upper()) or _rc(s)

# parent appropriations of each source: (agency_id, test on an appropriation row, group key of that row)
PARENTS = {
# Group grain follows where BOTH sides print region: Vol I-B carries much DPWH money as Central Office lumps that Vol I-C spreads over
# regions, and HFEP is one national line, so those compare per program / nationally; FMR prints region on both sides.
    'dpwh_vol_ic': ('18-001', lambda r: r['category'] == 'Operations' and r['program'] != '', lambda r: (norm(r['program']),)),
    'dpwh_tail':   ('18-001', lambda r: r['category'] == 'Locally-Funded Projects', lambda r: ()),   # Buildings + PPP Strategic Support Fund
    'fmr':         ('05-001', lambda r: r['pap'].startswith('Repair/Rehabilitation and Construction of Farm-to-Market Roads'), lambda r: (r['region_code'],)),
    'hfep':        ('13-001', lambda r: r['pap'] == 'Health Facilities Enhancement Program', lambda r: ()),
}

class Admin:
    """PSGC lookups scoped to a parent: municipality/city within a province, barangay within a municipality."""
    def __init__(self, xlsx, psgc_rows):
        self.places = geo.Places(psgc_rows)
        self.prov = collections.defaultdict(list); self.in_prov = collections.defaultdict(list); self.bgy = collections.defaultdict(list)
        for r in psgc_rows:
            if r['geo_level'] == 'province': self.prov[(r['region_code'], norm(r['name']))].append(r)
            if r['geo_level'] in ('city', 'municipality'):
                for k in geo.variants(r): self.in_prov[(r['province_psgc'], k)].append(r)
        ws = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)['PSGC']
        for r in ws.iter_rows(values_only=True, min_row=2):
            if r[0] and r[3] == 'Bgy':
                c = str(r[0]).zfill(10); self.bgy[(c[:7] + '000', norm(str(r[1]).strip()))].append(c)
    def province(self, name, reg):
        c = self.prov.get((reg, norm(name)), []) or [p for p in [self.places.find(name, reg)] if p and p['geo_level'] in ('province', 'city')]
        return c[0] if len(c) == 1 else None
    def mun(self, name, prov):
        name = re.sub(r'^(Municipality|City) of\s+', '', name.strip(), flags=re.I)
        c = self.in_prov.get((prov['psgc_code'], norm(name)), []) or self.in_prov.get((prov['psgc_code'], norm(name + ' City')), [])
        if prov['geo_level'] == 'city' and not c: return None
        return c[0] if len(c) == 1 else None
    def barangay(self, name, mun):
        c = self.bgy.get((mun['psgc_code'][:7] + '000', norm(name)), [])
        return c[0] if len(c) == 1 else None

def place_admin(admin, reg, province, municipality='', barangay=''):
    p = admin.province(province, reg) if province else None
    if not p: return ('region', reg + '00000000', '', '', 'annex region') if reg else ('national', '', '', '', 'no region')
    m = admin.mun(municipality, p) if municipality else None
    if not m: return (p['geo_level'], p['psgc_code'], p['province_psgc'] or p['psgc_code'], '', 'annex province')
    b = admin.barangay(barangay, m) if barangay else None
    if b: return ('barangay', b, m['province_psgc'], '', 'annex barangay')
    return (m['geo_level'], m['psgc_code'], m['province_psgc'], '', 'annex municipality')

def read(ph_data, name):
    p = os.path.join(ph_data, name)
    return list(csv.DictReader(open(p, encoding='utf-8'))) if os.path.exists(p) else []

def build(apps, ph_data, psgc_xlsx, psgc_rows):
    admin = Admin(psgc_xlsx, psgc_rows); places = admin.places; deo = geo.load_deo(ph_data, places)
    items = []
    def add(src, c, row, group, **kw):
        it = dict.fromkeys(ITEM_COLS, ''); it.update(kw)
        it.update(item_id=h(src, row['id']), stage=STAGE[c], source=src, drilldown_group_id=h(src, *group),
                  pdf_page=row['page'], source_row_id=row['id'])
        items.append(it)
    for c in 'AB':
        for r in read(ph_data, f'gab_dpwh_rows_{c}.csv') + [dict(x, _tail=1) for x in read(ph_data, f'gab_dpwh_tail_rows_{c}.csv')]:
            src = 'dpwh_tail' if r.get('_tail') else 'dpwh_vol_ic'
            rc = region_code(r['region'])
            pseudo = dict(region_printed=r['region'] or '', region_code=rc, operating_unit=r['deo'] or ('Central Office' if r['region'] == 'Central Office' else ''))
            lvl, code, dist, basis = geo.place(pseudo, places, deo) if r['region'] else ('national', '', '', 'no region printed')
            prov = places.rows[code]['province_psgc'] if code in places.rows and lvl != 'region' else ''
            add(src, c, r, () if src == 'dpwh_tail' else (norm(r['program']),), section=r['program'], region_printed=r['region'],
                region_code=rc, office=r['deo'], item=r['project'], amount=int(r['amount']), geo_level=lvl, psgc_code=code,
                province_psgc=prov if lvl != 'province' else code, district_id=dist, geo_basis=basis)
        for r in read(ph_data, f'gab_annex_fmr_{c}.csv'):
            rc = region_code(r['section']); parts = [s.strip() for s in r['project'].split(',')]
            g = place_admin(admin, rc, parts[-1], parts[-2] if len(parts) > 2 else '')
            add('fmr', c, r, (rc,), section=r['section'], region_printed=r['section'], region_code=rc, province_printed=parts[-1],
                municipality_printed=parts[-2] if len(parts) > 2 else '', item=r['project'], amount=int(r['amount']),
                **dict(zip(('geo_level', 'psgc_code', 'province_psgc', 'district_id', 'geo_basis'), g)))
        for r in read(ph_data, f'gab_annex_hfep_{c}.csv'):
            rc = region_code(r['region']); m = re.search(r'(?:Municipality|City) of\s+([^,(]+?)(?:\s+(?:Brgy|Barangay|Rural|District|Provincial)\b|,|\(|$)', r['project'])
            mun = m.group(1).strip() if m else ''
            g = place_admin(admin, rc, r['province'], mun)
            add('hfep', c, r, (), section=r['section'], region_printed=r['region'], region_code=rc, province_printed=r['province'],
                municipality_printed=mun, item=r['project'], amount=int(r['amount']),
                **dict(zip(('geo_level', 'psgc_code', 'province_psgc', 'district_id', 'geo_basis'), g)))
        for r in read(ph_data, f'gab_annex_nia_{c}.csv'):
            add('nia', c, r, (norm(r['section']),), section=r['section'], item=r['project'], amount=int(r['amount']),
                geo_level='', geo_basis='not placed (no region printed per item)')
        for r in read(ph_data, f'gab_annex_sbdp_{c}.csv'):
            rc = region_code(r['region'])
            g = place_admin(admin, rc, r['province'], r['municipality'], r['barangay'])
            add('sbdp', c, r, ('', rc), section='Support to Barangay Development Program', region_printed=r['region'], region_code=rc,
                province_printed=r['province'], municipality_printed=r['municipality'], barangay_printed=r['barangay'],
                item=f"Barangay {r['barangay']}, {r['municipality']}, {r['province']}", amount='',
                **dict(zip(('geo_level', 'psgc_code', 'province_psgc', 'district_id', 'geo_basis'), g)))

    # parents: tag appropriations, then compare sums per (stage, group)
    for r in apps: r['drilldown_group_id'] = ''
    par = collections.defaultdict(lambda: [0, 0]); desc = {}
    for src, (agency, test, key) in PARENTS.items():
        for r in apps:
            if r['agency_id'] == agency and test(r):
                g = h(src, *key(r)); r['drilldown_group_id'] = g
                par[(r['stage'], src, g)][0] += r['amount']; par[(r['stage'], src, g)][1] += 1
                desc.setdefault(g, f"{r['program'] or r['pap']}" + (f" | {r['region_printed']}" if src == 'fmr' else ''))
    dd = collections.defaultdict(lambda: [0, 0])
    for it in items:
        k = (it['stage'], it['source'], it['drilldown_group_id'])
        dd[k][0] += it['amount'] or 0; dd[k][1] += 1
        desc.setdefault(it['drilldown_group_id'], it['section'] + (f" | {it['region_printed']}" if it['source'] in ('fmr', 'sbdp') else ''))
    cov = []
    for k in sorted(set(par) | set(dd)):
        s, src, g = k; p, d = par.get(k, [0, 0]), dd.get(k, [0, 0])
        status = ('no_amounts' if src == 'sbdp' else 'parent_not_parsed' if src not in PARENTS else
                  'no_items' if not d[1] else 'no_parent_line' if not p[1] else
                  'complete' if p[0] == d[0] else 'partial' if d[0] < p[0] else 'exceeds_parent')
        cov.append(dict(drilldown_group_id=g, stage=s, source=src, description=desc.get(g, ''), parent_rows=p[1], parent_amount=p[0] if p[1] else '',
                        items=d[1], drilldown_amount=d[0] if src != 'sbdp' else '', coverage=round(d[0] / p[0], 4) if p[0] and src != 'sbdp' else '',
                        status=status))
    return items, cov
