"""Phase 4: place every appropriation on the map, no finer than the bill supports (D6).

geo_level: national (no region printed) | central_office (an agency's HQ unit - printed under NCR, never mapped to NCR) | region |
province | city | municipality | district. A place finer than region is attributed only when the bill names it: a DPWH District
Engineering Office (via the reviewed DEO -> district map), a prefixed office (Division of X, PENRO X, CENRO X, PARO - X), or a place
name in its own segment of the office name (Mindanao State University - Naawan). geo_basis records which rule fired.
Places are PSGC 2Q-2026 codes; PSGC's 2-digit region prefix is the UACS region code (D8).
Known ceiling: schools (sub_unit) are placed at their division, not their municipality; offices named after a person or with the
place inside the name ('Southern Isabela Medical Center') stay at region."""
import collections, csv, os, re
import openpyxl

LEVEL = {'Reg': 'region', 'Prov': 'province', 'City': 'city', 'Mun': 'municipality', 'SubMun': 'sub_municipality'}
RANK = {'province': 0, 'city': 1, 'municipality': 2, 'sub_municipality': 3}
CENTRAL = re.compile(r'^(Central Office|Home Office)\b', re.I)
REGIONAL = re.compile(r'Regional|Center for Health Development|^Region\s|\bRO\b|Field Unit|Revenue Region|Area Office', re.I)
PREFIX = re.compile(r'^(?:Schools\s+)?(?:Division of|PENRO|CENRO|PARO\s*-|Provincial Office\s*-|Provincial\s+\w+\s+Office\s*-)\s*(.+)$', re.I)
DEO = re.compile(r'District Engineering Office', re.I)
PERSON = re.compile(r'Memorial|\bDr\.|\bSr\.|\bJr\.|President\s|Gov\.|Sen\.', re.I)
GEO_COLS = ('geo_level', 'psgc_code', 'province_psgc', 'district_id', 'geo_basis')

def norm(s): return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def load_psgc(xlsx):
    ws = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)['PSGC']
    rows = []
    for r in ws.iter_rows(values_only=True, min_row=2):
        if not r[0] or r[3] not in LEVEL: continue
        rows.append(dict(psgc_code=str(r[0]).zfill(10), name=str(r[1]).strip(), geo_level=LEVEL[r[3]], city_class=r[5] or '',
                         income_class=(r[6] or '').strip() if isinstance(r[6], str) else (r[6] or ''), population_2024=r[8] or ''))
    codes = {r['psgc_code'] for r in rows}
    for r in rows:
        c = r['psgc_code']; r['region_code'] = c[:2]
        p = c[:5] + '00000'
        r['province_psgc'] = p if r['geo_level'] != 'region' and p in codes else ''
    return rows

def variants(r):
    """Name keys a printed office might use: 'City of Tangub' -> tangub, tangubcity; 'Isabela (Capital)' -> isabela."""
    base = re.sub(r'\s*\(.*?\)', '', r['name'])
    v = {norm(base)}
    if r['geo_level'] == 'city':
        core = re.sub(r'^City of\s+', '', base, flags=re.I)
        v |= {norm(core), norm(core + ' City')}
    if r['geo_level'] == 'province': v.add(norm(base + ' Province'))
    return v

class Places:
    def __init__(self, psgc_rows):
        self.by_region = collections.defaultdict(lambda: collections.defaultdict(list))
        self.nation = collections.defaultdict(list)
        self.rows = {r['psgc_code']: r for r in psgc_rows}
        for r in psgc_rows:
            if r['geo_level'] == 'region': continue
            for k in variants(r):
                self.by_region[r['region_code']][k].append(r); self.nation[k].append(r)

    def find(self, text, region):
        """Best PSGC unit for a printed place name, within the region first; None if absent or ambiguous."""
        k = norm(text)
        cands = self.by_region[region].get(k) or ([] if region else self.nation.get(k, []))
        if not cands: return None
        if re.search(r'\bcity\b', text, re.I): cands = [c for c in cands if c['geo_level'] == 'city'] or cands
        if re.search(r'\bprovince\b', text, re.I): cands = [c for c in cands if c['geo_level'] == 'province'] or cands
        best = min(RANK[c['geo_level']] for c in cands)
        top = [c for c in cands if RANK[c['geo_level']] == best]
        return top[0] if len(top) == 1 else None

def load_deo(ph_data, places):
    """office name -> (district_id, PSGC row of its province/city) from ph-pork-graph's reviewed map."""
    loc = {r['id']: r for r in csv.DictReader(open(os.path.join(ph_data, 'localities.csv'), encoding='utf-8'))}
    def loc_psgc(lid):
        l = loc.get(lid)
        if not l: return None
        return places.find(l['name'] + (' City' if l['type'] == 'city' else ''), '') or places.find(l['name'], '')
    deo = {}
    for r in csv.DictReader(open(os.path.join(ph_data, 'deo_district_map.csv'), encoding='utf-8')):
        if r['confidence'] in ('exact', 'locality'):
            deo[norm(r['office'])] = (r['district_id'] if r['confidence'] == 'exact' else '', loc_psgc(r['locality_id']))
    return deo

def place(r, places, deo):
    """(geo_level, psgc_code, district_id, geo_basis) for one appropriation."""
    reg, unit = r['region_code'], r['operating_unit']
    if not r['region_printed']: return 'national', '', '', 'no region printed'
    if CENTRAL.match(unit): return 'central_office', '', '', 'Central Office (national HQ)'
    region_only = ('region', reg + '00000000' if reg else '', '')
    if not unit: return (*region_only, 'region heading')
    if DEO.search(unit):
        hit = deo.get(norm(unit))
        if hit and hit[1]: return (('district' if hit[0] else hit[1]['geo_level']), hit[1]['psgc_code'], hit[0], 'DEO map')
        name = re.sub(r'\s*(?:\d+(?:st|nd|rd|th)|First|Second|Third|Fourth|Fifth|Sixth|Seventh|Lone)?\s*(?:District\s+)*District Engineering Office.*$', '', unit, flags=re.I)
        p = places.find(name, reg)                    # misspelt / unmapped DEO: its province or city is still named
        if p: return p['geo_level'], p['psgc_code'], '', 'DEO name (district not mapped)'
        return (*region_only, 'DEO not in map')
    m = PREFIX.match(unit)
    if m:
        p = places.find(re.sub(r'\s+(?:[IVX]+|\d)$', '', m.group(1)), reg)   # 'Division of Pangasinan II' = a Pangasinan division
        if p: return p['geo_level'], p['psgc_code'], '', 'office prefix (Division/PENRO/CENRO/PARO)'
    if REGIONAL.search(unit): return (*region_only, 'regional office')
    if not PERSON.search(unit):
        found = {p['psgc_code']: p for s in re.split(r'\s*[-–,()]\s*|\s+-\s*', unit) if s and (p := places.find(s, reg))}
        found.update({p['psgc_code']: p for p in [places.find(unit, reg)] if p})
        if len(found) == 1:
            p = next(iter(found.values())); return p['geo_level'], p['psgc_code'], '', 'place name in office name'
        if len(found) > 1: return (*region_only, 'office spans several places')
    return (*region_only, 'office not placeable below region')

def attach(apps, psgc_xlsx, ph_data):
    psgc_rows = load_psgc(psgc_xlsx); places = Places(psgc_rows); deo = load_deo(ph_data, places)
    for r in apps:
        lvl, code, dist, basis = place(r, places, deo)
        prov = places.rows[code]['province_psgc'] if code in places.rows and lvl not in ('region',) else ''
        r.update(geo_level=lvl, psgc_code=code, province_psgc=prov if lvl != 'province' else code, district_id=dist, geo_basis=basis)
    return psgc_rows

def dimension_rows(apps, psgc_rows, ph_data, regions_csv):
    """regions, localities, districts, operating_units release tables."""
    short = {}
    for r in csv.DictReader(open(regions_csv, encoding='utf-8')): short[r['name']] = r['id']
    from nep_match import region_code
    regions = [dict(region_code=r['region_code'], psgc_code=r['psgc_code'], name=r['name'],
                    short_name=next((v for k, v in short.items() if region_code(k) == r['region_code']), ''),
                    population_2024=r['population_2024']) for r in psgc_rows if r['geo_level'] == 'region']
    localities = [{k: r[k] for k in ('psgc_code', 'name', 'geo_level', 'city_class', 'income_class', 'region_code', 'province_psgc', 'population_2024')}
                  for r in psgc_rows if r['geo_level'] != 'region']
    places = Places(psgc_rows); deo = load_deo(ph_data, places)
    loc = {r['id']: r for r in csv.DictReader(open(os.path.join(ph_data, 'localities.csv'), encoding='utf-8'))}
    districts = []
    for d in csv.DictReader(open(os.path.join(ph_data, 'districts.csv'), encoding='utf-8')):
        l = loc.get(d['locality_id'], {})
        p = (places.find(l.get('name', '') + (' City' if l.get('type') == 'city' else ''), '') or places.find(l.get('name', ''), '')) if l else None
        districts.append(dict(district_id=d['id'], name=d['name'], district_no=d['district_no'], psgc_code=p['psgc_code'] if p else '',
                              region_code=p['region_code'] if p else ''))
    units = collections.OrderedDict()
    for r in apps:
        k = (r['agency_id'], r['region_code'], r['operating_unit'])
        u = units.setdefault(k, dict(agency_id=k[0], agency_printed=r['agency_printed'], region_code=k[1], region_printed=r['region_printed'],
                                     operating_unit=k[2], **{c: r[c] for c in GEO_COLS}, rows=0))
        u['rows'] += 1
    return regions, localities, districts, list(units.values())
