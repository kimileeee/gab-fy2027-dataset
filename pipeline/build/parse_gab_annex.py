"""Sector annex project rows from CR00638.pdf (A = as filed pp12-3535, B = [3RD READING] pp3536-7408).
Annexes: FMR (DA Farm-to-Market Roads, B only), NIA (irrigation, A+B). Rows carry a stable id = sha1(annex|copy|page|ordinal)[:12].
Amounts in pesos. Prints printed-heading total vs parsed total per section. Run from build/."""
import csv, re, sys, hashlib, collections, pymupdf

PDF = '../raw/hb10858/CR00638.pdf'
NUM = re.compile(r'^\d{1,3}(?:,\d{3})+$')
ANNEX = {  # annex: copy -> (first page, last page), item-start regex, label x max, amount x min
    'FMR': dict(pages={'A': (2006, 2049), 'B': (5539, 5600)}, head=r'^(REGION|CORDILLERA|NATIONAL CAPITAL|NEGROS|BANGSAMORO|CARAGA|MIMAROPA|DESIGNATED|REPAIR)', start=r'^(Construction|Concreting|Rehabilitation|Repair|Improvement|Opening|Installation|Widening|Upgrading|Reconstruction|Maintenance|Road)\b', amt_x=490),
    'NIA': dict(pages={'A': (2216, 2259), 'B': (5769, 5816)}, start=r'^[^:]{3,70}:\s', amt_x=500, amt_starts=True, head=r'(?!)'),
}

def rows_of(page):
    w = sorted(page.get_text('words'), key=lambda w: (round(w[1] / 2), w[0]))
    rows = []
    for x0, y0, x1, y1, t, b, l, _ in w:
        if rows and abs(rows[-1][0] - y0) <= 2.5: rows[-1][1].append((x0, t))
        else: rows.append([y0, [(x0, t)]])
    return rows

def parse(annex, copy):
    cfg = ANNEX[annex]; lo, hi = cfg['pages'][copy]; d = pymupdf.open(PDF)
    start = re.compile(cfg['start']); out = []; heads = []; sect = ''; cur = None; pend = []
    def close():
        nonlocal cur
        if cur and cur['amount'] is not None: out.append(cur)
        cur = None
    for pn in range(lo, hi + 1):
        for y, r in rows_of(d[pn - 1]):
            if y < 20: continue
            if any(re.search(p, ' '.join(t for x, t in sorted(r))) for p in (r'GENERAL APPROPRIATIONS BILL', r'^DEPARTMENT OF AGRICULTURE', r'\bNAME\b.*\bPROJECTS\b', r'^NATIONAL IRRIGATION ADMINISTRATION\s*[-–]')): continue    # running page headers / column titles
            amts = [int(re.sub(',', '', t)) for x, t in r if x >= cfg['amt_x'] and NUM.match(t)]
            lab = ' '.join(t for x, t in sorted(r) if not (x >= cfg['amt_x'] and NUM.match(t))).strip()
            if re.match(r'^(START|END):', lab) or lab in ('PESOS', 'AMOUNT IN', 'AMOUNT') or 'NAME OF PROJECTS' in lab or 'NAME OR PROJECTS' in lab or lab.startswith('PROGRAMS / ACTIVITIES'):
                if amts and cur and cur['amount'] is None: cur['amount'] = amts[0]
                continue
            if lab.isupper() and amts and not start.match(lab) and re.match(cfg.get('head', r'.'), lab):       # section heading with printed total
                close(); sect = lab; heads.append(dict(copy=copy, page=pn, section=lab, printed=amts[0])); continue
            if re.search(r'(Sub-Program|Program|Projects)\s*$', lab) and amts and ':' not in lab:
                close(); sect = lab; heads.append(dict(copy=copy, page=pn, section=lab, printed=amts[0])); continue
            if start.match(lab) or (cfg.get('amt_starts') and amts and not (cur and cur['amount'] is None)):
                close(); cur = dict(annex=annex, copy=copy, page=pn, section=sect, project=lab, amount=amts[0] if amts else None); continue
            if cur is not None:
                if lab: cur['project'] += ' ' + lab
                if amts and cur['amount'] is None: cur['amount'] = amts[0]
    close()
    for i, r in enumerate(out): r['id'] = hashlib.sha1(f"{annex}|{copy}|{r['page']}|{i}".encode()).hexdigest()[:12]
    return out, heads

if __name__ == '__main__':
    for annex, cfg in ANNEX.items():
        for copy in cfg['pages']:
            rows, heads = parse(annex, copy)
            fn = f'../data/gab_annex_{annex.lower()}_{copy}.csv'
            with open(fn, 'w', newline='', encoding='utf8') as f:
                w = csv.DictWriter(f, fieldnames=['id', 'annex', 'copy', 'page', 'section', 'project', 'amount']); w.writeheader(); w.writerows(rows)
            tot = sum(r['amount'] for r in rows)
            print(f'{annex} {copy}: rows={len(rows)} parsed=P{tot/1e9:.3f}B | headings={len(heads)}')
            top = [h for h in heads][:3]
            for h in top: print('   heading', h['section'][:60], h['printed'])
            by = collections.defaultdict(int)
            for r in rows: by[r['section']] += r['amount']
            hs = {h['section']: h['printed'] for h in heads}
            bad = [(s, hs[s], by[s]) for s in hs if s in by and hs[s] != by[s]]
            print(f'   sections matching printed: {sum(1 for s in hs if by.get(s)==hs[s])}/{len(hs)}; mismatches (first 5):', [(s[:30], p, q) for s, p, q in bad[:5]])
