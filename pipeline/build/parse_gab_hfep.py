"""DOH Health Facilities Enhancement Program (HFEP) annex rows, A (pp2198-2215) vs B (pp5749-5768) of CR00638.pdf.
Leaf = facility row (not numbered heading / region / province row); amount = rightmost numeric (Total column), pesos.
Output ../data/gab_annex_hfep_{A,B}.csv (same cols as parse_gab_annex.py; section = numbered heading). Prints printed-vs-parsed per heading. Run from build/."""
import csv, re, hashlib, collections, pymupdf
from parse_gab_annex import rows_of, NUM
from gab_pdf import open_bill, with_c, COPIES
grand = {}
PAGES = with_c({'A': (2198, 2215), 'B': (5749, 5768)})
HEAD = re.compile(r'^(\d+\.?[a-z]?\.?\d*|[IVX]+\.|[A-Z]\.)\s+\S')
REGION = re.compile(r'^(CAR|NCR|NIR|BARMM|CARAGA|MIMAROPA|CALABARZON|National Capital Region|Region [IVX]+(-[AB])?(\s*\(.*\))?|Negros Island Region|Cordillera.*|Bangsamoro.*)$', re.I)
FAC = re.compile(r'(Station|Hospital|Medical|Center|Centre|Clinic|Facility|Facilities|Unit|Building|Birthing|Laboratory|Ambulance|Vehicle|Equipment|BHS|RHU|Infirmary|Pharmacy|Morgue|School|Institute|Complex|Ward|Dialysis|Sanitarium)', re.I)
PROV = re.compile(r'^[A-Za-z][A-Za-z.\-\' ]{2,32}$')

def parse(copy):
    lo, hi = PAGES[copy]; d = open_bill(); out = []; heads = {}; sect = ''; pend = []; reg = prov = ''
    for pn in range(lo, hi + 1):
        rows = rows_of(d[pn - 1]); anc = None
        for y, r in rows:
            r = sorted(r)
            if any(t == 'Name' for x, t in r) and any(t == 'Projects' for x, t in r): anc = next(x for x, t in r if t == 'Name'); break
        if anc is None: continue
        for y, r in rows[1:]:
            r = sorted(r); nums = [(x, int(t.replace(',', ''))) for x, t in r if NUM.match(t)]
            labw = [(x, t) for x, t in r if not NUM.match(t) and t != '-']
            if not labw or y < 100 and pn in (lo, lo + 1) and not nums: continue
            lab = ' '.join(t for x, t in labw).strip(); x0 = labw[0][0]
            if lab.startswith(('FY 2027', 'DEPARTMENT OF', 'HEALTH FACILITIES', '(Amount', 'Name of Projects', 'Medical', 'Equipment', 'GENERAL APPROPRIATIONS')) or re.fullmatch(r'\d+', lab): continue
            if x0 < anc - 55:                                    # heading / region level
                if HEAD.match(lab) and nums: heads[lab] = nums[-1][1]; sect = lab; reg = prov = ''
                elif lab and not HEAD.match(lab): reg = lab; prov = ''
                pend = []; continue
            if x0 < anc - 39: prov = lab; pend = []; continue    # province level
            if nums and re.match(r'(?i)^(grand )?total', lab):
                grand[copy] = nums[-1][1]; pend = []; continue
            if nums:
                full = ' '.join(pend + [lab]).strip(); pend = []
                out.append(dict(annex='HFEP', copy=copy, page=pn, section=sect, region=reg, province=prov, project=full, amount=nums[-1][1]))
            else:
                pend.append(lab)
    for i, r in enumerate(out): r['id'] = hashlib.sha1(f"HFEP|{copy}|{r['page']}|{i}".encode()).hexdigest()[:12]
    return out, heads

if __name__ == '__main__':
    for c in COPIES:
        rows, heads = parse(c)
        with open(f'../data/gab_annex_hfep_{c}.csv', 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=['id', 'annex', 'copy', 'page', 'section', 'region', 'province', 'project', 'amount']); w.writeheader(); w.writerows(rows)
        by = collections.defaultdict(int)
        for r in rows: by[r['section']] += r['amount']
        print(c, 'rows', len(rows), 'parsed P%.3fB' % (sum(by.values()) / 1e9), '| printed GRAND TOTAL P%.3fB' % (grand.get(c, 0) / 1e9), '| headings', len(heads))
        for h, p in []: print(f'   {h[:46]:46} printed {p/1e6:9.1f}M parsed {by.get(h,0)/1e6:9.1f}M {"OK" if by.get(h,0)==p else ""}')
