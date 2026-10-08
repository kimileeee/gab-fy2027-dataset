"""Phase 7: departments.csv and agencies.csv - UACS codes (BetterGov join keys), the bill's own codes and printed names, official
names, and official acronyms with their source (D12).

Acronym sources, in order: (1) the UACS name in BetterGov's NEP 2027, which DBM prints with the acronym in parentheses
("Department of Health (DOH)"); (2) the bill's own text, which defines most agencies' acronyms in their standard provisions
("The National Nutrition Council (NNC) shall submit...") and writes Office of the Secretary units as "DENR-OSEC"; otherwise blank,
never invented. Every acronym records where it came from (and the PDF page for bill text)."""
import collections, re
import duckdb

def norm(s): return re.sub(r'[^a-z0-9]', '', (s or '').lower())
ACR = re.compile(r'\(([A-Z][A-Za-z0-9&\-]{1,15})\)')
def looks_like_acronym(a): return sum(ch.isupper() for ch in a) >= 2

def split_acronym(uacs_name):
    """'Department of Health (DOH)' -> ('Department of Health', 'DOH'); names without a trailing acronym come back unchanged."""
    m = re.match(r'^(.*?)\s*\(([A-Za-z][A-Za-z0-9&\-]{1,15})\)\s*$', uacs_name or '')
    return (m.group(1), m.group(2)) if m and looks_like_acronym(m.group(2)) and m.group(2) != 'Proper' else ((uacs_name or '').strip(), '')

def bill_acronyms(pdf_text_db):
    """[(normalised text before '(ACR)', ACR, page)] for every parenthesised acronym in the bill, plus the set of 'XXX-OSEC' tokens."""
    occ, osec = [], {}
    for page, text in duckdb.connect(pdf_text_db, read_only=True).sql("select page, text from pages where pdf = 'CR638' order by page").fetchall():
        t = re.sub(r'\s+', ' ', text or '')
        for m in ACR.finditer(t):
            if looks_like_acronym(m.group(1)): occ.append((norm(t[max(0, m.start() - 200):m.start()]), m.group(1), page))
        for m in re.finditer(r'\b([A-Z][A-Za-z]{1,8})-OSEC\b', t): osec.setdefault(m.group(1), page)
    return occ, osec

def from_text(occ, *names):
    """Most frequent acronym printed right after one of `names`, and the first page it appears on."""
    keys = [norm(re.sub(r'\(.*?\)', '', n)) for n in names if n and len(norm(n)) > 6]
    c, first = collections.Counter(), {}
    for pre, a, page in occ:
        if any(pre.endswith(k) for k in keys): c[a] += 1; first.setdefault(a, page)
    if not c: return '', ''
    a = c.most_common(1)[0][0]
    return a, first[a]

def build(agency_rows, pdf_text_db):
    """agency_rows: one dict per agency folder × stage: agency_id, dept_id, uacs_dept_name, uacs_agency_name, toc (TOC row), stage."""
    occ, osec = bill_acronyms(pdf_text_db)
    depts, ags = {}, {}
    for r in agency_rows:
        t = r['toc']
        d = depts.setdefault(r['dept_id'], dict(dept_id=r['dept_id'], gab_dept_code=t.get('dept_code', ''), name_printed=t['dept'],
                                                uacs_name=r['uacs_dept_name'], agencies=set()))
        d['agencies'].add(r['agency_id'])
        a = ags.setdefault(r['agency_id'], dict(agency_id=r['agency_id'], dept_id=r['dept_id'], gab_dept_code=t.get('dept_code', ''),
                                                gab_agency_code=t.get('agency_code', ''), suc_region_group_code=t.get('group_code', '') if r['dept_id'] == '08' else '',
                                                suc_region_group=t.get('group', '') if r['dept_id'] == '08' else '', name_printed=t['agency'],
                                                uacs_name=r['uacs_agency_name'], stages=set(), dept_printed=set()))
        a['stages'].add(r['stage']); a['dept_printed'].add(f"{r['stage']}: {t['dept']}")
    for d in depts.values():
        d['name_official'], acr = split_acronym(d['uacs_name']); src, page = 'UACS name (BetterGov NEP 2027)', ''
        if not acr:
            acr, page = from_text(occ, d['name_official'], d['name_printed']); src = 'bill text (HB 10858, CR 638)' if acr else ''
        d.update(acronym=acr, acronym_source=src, acronym_source_page=page, agencies=len(d['agencies']))
    for a in ags.values():
        a['name_official'], acr = split_acronym(a['uacs_name']); src, page = 'UACS name (BetterGov NEP 2027)', ''
        if not acr:
            acr, page = from_text(occ, a['name_official'], a['name_printed']); src = 'bill text (HB 10858, CR 638)' if acr else ''
        dacr = depts[a['dept_id']]['acronym']
        if not acr and re.match(r'office of the secretary', a['name_official'] or a['name_printed'], re.I) and dacr in osec:
            acr, src, page = f'{dacr}-OSEC', 'bill text (HB 10858, CR 638)', osec[dacr]
        a.update(acronym=acr, acronym_source=src, acronym_source_page=page, stages=';'.join(sorted(a['stages'])),
                 dept_printed=' | '.join(sorted(a['dept_printed'])))
    D = [{k: d[k] for k in ('dept_id', 'gab_dept_code', 'name_printed', 'name_official', 'acronym', 'acronym_source', 'acronym_source_page', 'agencies')}
         for d in sorted(depts.values(), key=lambda d: d['dept_id'])]
    A = [{k: a[k] for k in ('agency_id', 'dept_id', 'gab_dept_code', 'gab_agency_code', 'suc_region_group_code', 'suc_region_group', 'name_printed',
                            'name_official', 'acronym', 'acronym_source', 'acronym_source_page', 'stages', 'dept_printed')}
         for a in sorted(ags.values(), key=lambda a: a['agency_id'])]
    return D, A
