"""Back-matter special-purpose funds XXXVIII-XLIII (Contingent, Miscellaneous Personnel Benefits, NDRRM, Pension and Gratuity,
Revised AFP Modernization, Unprogrammed Appropriations). Shape differs from a department: no agencies or programs, only the fund's
lead line and 'New Appropriations, by Purpose' printed TWICE - first a single TOTAL NEW APPROPRIATIONS row by expense class, then,
after the Special Provisions, the itemized purposes - plus the usual by Object table (thousand pesos). gab_tree.py reads both as one
purpose table and double-counts. Here the first is filed as table=summary and the itemized one as table=detail, so downstream code
(gab_office_compare.py, the release build) treats them like a department's two program tables. A lead line printed without
'hereunder' ('Fund subsidies for contingencies . . . P 13,000,000,000') is the fund's first amount row before any table. A purpose's
list number is dropped ('1. Restoration of ...'): copy B numbers Unprogrammed's purposes and copy A doesn't, which would otherwise read
as four lines removed and re-added.
Reuses gab_tree.py (events, tree, ids, output layout) unchanged: ../data/gab/<fund-slug>/no-agency/pap_{A,B}.csv.
Check per fund and copy: lead = summary total = detail total = sum of detail items = object total x 1,000, every printed sum ties.
Usage: python parse_gab_backmatter.py [A B]. Run from build/."""
import re, sys
import gab_tree
from gab_tree import TNA

FUNDS = ['CONTINGENT FUND', 'MISCELLANEOUS PERSONNEL BENEFITS FUND', 'NATIONAL DISASTER RISK REDUCTION AND MANAGEMENT FUND (CALAMITY FUND)',
         'PENSION AND GRATUITY FUND', 'REVISED AFP MODERNIZATION PROGRAM', 'UNPROGRAMMED APPROPRIATIONS']

def adjust(E):
    """First by-Purpose table (up to its TOTAL NEW APPROPRIATIONS row) -> summary, the rest -> detail; flag the lead."""
    summary_done = table_seen = False
    for e in E:
        if e['table'] == 'purpose':
            table_seen = True
            e['table'] = 'detail' if summary_done else 'summary'
            if e['kind'] == 'A' and TNA.match(e['label']): summary_done = True
            e['label'] = re.sub(r'^\d{1,2}\.\s+', '', e['label'])
        elif e['table']: table_seen = True
        elif e['kind'] == 'A' and not table_seen: e['lead'] = True; table_seen = True
    return E

def check(fund, copy, rows):
    tot = {r['table']: r['total'] for r in rows if r['role'] == 'total'}
    lead = [r['total'] for r in rows if r['role'] == 'lead']
    items = sum(r['total'] for r in rows if r['table'] == 'detail' and r['role'] == 'item')
    bad = [r for r in rows if r['sum_ok'] == 0]
    ok = lead == [tot.get('summary')] == [tot.get('detail')] == [items] and tot.get('object', 0) * 1000 == items and not bad
    print(f"  {'ok ' if ok else '!! '}{fund[:45]:45} lead {lead} summary {tot.get('summary')} detail {tot.get('detail')} items {items}"
          f" object x1000 {tot.get('object', 0) * 1000} sum mismatches {len(bad)}")
    return ok

if __name__ == '__main__':
    good = True
    for c in sys.argv[1:] or ['A', 'B', 'C']:
        print(f'== copy {c}')
        for fund in FUNDS:
            out = gab_tree.run(fund, c, adjust(gab_tree.events(c, fund)))
            good &= check(fund, c, [r for R in out.values() for r in R])
    sys.exit(0 if good else 1)
