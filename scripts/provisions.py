"""Phase 2b + 6: special_provisions.csv (one row per Special Provision x stage) and special_provisions_compared.csv (both stages side
by side, with a word-level change count).

Input: pipeline/data/gab_provisions_{A,B}.csv (parse_gab_provisions.py). Provisions are attached to the agency whose heading is
printed above them; a provision printed before any agency heading is department-wide (scope = department). Back-matter funds
(Unprogrammed Appropriations, Pension and Gratuity Fund, ...) print provisions too although their tables are not parsed yet: they are
kept, with scope = back_matter and no UACS code. Provisions pair across stages on agency + normalised title (+ occurrence), so a
renumbered provision is still the same provision."""
import collections, csv, difflib, hashlib, os, re

STAGE = {'A': 'GAB_FILED', 'B': 'GAB_3R'}
def norm(s): return re.sub(r'[^a-z0-9]', '', (s or '').lower())
def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60] or 'no-agency'
def h(*p): return hashlib.sha1('|'.join(map(str, p)).encode()).hexdigest()[:12]

def build(ph_data, agency, names, trees):
    """agency: {(dept_slug, agency_slug): (dept, agency, dept_dsc, agency_dsc)} from the NEP crosswalk; names: TOC rows per folder;
    trees: parsed agency tables, for the page span of each agency (attributes provisions printed before an agency's heading)."""
    dept_of_folder = {d: v[0] for (d, g), v in agency.items()}
    span = {(c, d, g): (min(int(r['page']) for r in rows), max(int(r['page']) for r in rows)) for (c, d, g), rows in trees.items() if rows}
    rows, gaps = [], []
    for c in 'AB':
        p = os.path.join(ph_data, f'gab_provisions_{c}.csv')
        if not os.path.exists(p): continue
        occ = collections.Counter(); seen_no = collections.defaultdict(list)
        for r in csv.DictReader(open(p, encoding='utf-8')):
            d, g = slug(r['dept']), slug(r['agency']) if r['agency'] else 'no-agency'
            u = agency.get((d, g))
            if u is None and g != 'no-agency':                       # body heading vs folder slug: same rule gab_tree uses, try a prefix
                u = next((v for (fd, fg), v in agency.items() if fd == d and (fg.startswith(g[:40]) or g.startswith(fg[:40]))), None)
            how = 'heading' if u and r['agency'] else 'single-agency department' if u else ''
            if u is None and d in dept_of_folder:                  # printed before the agency heading: the one agency whose pages hold it
                hit = [g2 for (c2, d2, g2), (lo, hi) in span.items() if c2 == c and d2 == d and lo <= int(r['page_start']) <= hi]
                if len(hit) == 1: g = hit[0]; u = agency.get((d, g)); how = 'page range'
            scope = 'agency' if u else 'department' if d in dept_of_folder else 'back_matter'
            agency_id = f'{u[0]}-{u[1]}' if u else ''
            dept_id = u[0] if u else dept_of_folder.get(d, '')
            key = (agency_id or f'{scope}:{d}', norm(r['title'] or r['text'][:80]))
            occ[key] += 1
            seen_no[key[0]].append(r['no'])
            rows.append(dict(provision_id=h(*key, occ[key]), stage=STAGE[c], fiscal_year=2027, dept_id=dept_id, agency_id=agency_id,
                             dept_printed=r['dept'], agency_printed=(names.get((d, g), {}).get('agency') if u else '') or r['agency'],
                             scope=scope, attribution=how, provision_no=r['no'], title=r['title'], text=r['text'], pdf_page_start=int(r['page_start']),
                             pdf_page_end=int(r['page_end']), lines=int(r['lines'])))
        for k, nos in seen_no.items():
            n = [int(x) for x in nos if x != '']
            if n != list(range(1, len(n) + 1)): gaps.append(f'{STAGE[c]} {k}: numbered {n} as printed')
    return rows, gaps

def compare(rows):
    A = {r['provision_id']: r for r in rows if r['stage'] == 'GAB_FILED'}
    B = {r['provision_id']: r for r in rows if r['stage'] == 'GAB_3R'}
    out = []
    for i in list(A) + [i for i in B if i not in A]:
        a, b = A.get(i), B.get(i); base = b or a
        wa, wb = (a['text'].split() if a else []), (b['text'].split() if b else [])
        added = removed = 0
        if a and b and wa != wb:
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes():
                if op in ('replace', 'delete'): removed += i2 - i1
                if op in ('replace', 'insert'): added += j2 - j1
        status = ('added' if not a else 'removed' if not b else 'unchanged' if wa == wb else 'text_changed')
        if status == 'unchanged' and a['provision_no'] != b['provision_no']: status = 'renumbered'
        out.append(dict(provision_id=i, dept_id=base['dept_id'], agency_id=base['agency_id'], dept_printed=base['dept_printed'],
                        agency_printed=base['agency_printed'], scope=base['scope'], title=base['title'],
                        provision_no_A=a['provision_no'] if a else '', provision_no_B=b['provision_no'] if b else '', status=status,
                        words_added=added if a and b else len(wb), words_removed=removed if a and b else len(wa),
                        text_A=a['text'] if a else '', text_B=b['text'] if b else '',
                        pdf_page_A=a['pdf_page_start'] if a else '', pdf_page_B=b['pdf_page_start'] if b else ''))
    return out

def checks(rows, cmp, gaps):
    L = ['', '## Special Provisions (phase 2b)', '']
    st = collections.Counter((r['stage'], r['scope']) for r in rows)
    L += ['- provisions: ' + ', '.join(f'{s} {sc} {n:,}' for (s, sc), n in sorted(st.items()))]
    L += [f"- agencies with provisions: GAB_FILED {len({r['agency_id'] for r in rows if r['stage'] == 'GAB_FILED' and r['agency_id']})}, "
          f"GAB_3R {len({r['agency_id'] for r in rows if r['stage'] == 'GAB_3R' and r['agency_id']})}; untitled: {sum(1 for r in rows if not r['title'])}"]
    L += ['- compared: ' + ', '.join(f'{k} {v:,}' for k, v in collections.Counter(r['status'] for r in cmp).most_common())]
    top = sorted((r for r in cmp if r['status'] == 'text_changed'), key=lambda r: -(r['words_added'] + r['words_removed']))[:10]
    L += ['- largest rewrites (words added / removed): ' + '; '.join(f"{r['agency_printed'] or r['dept_printed']} — {r['title'][:50]} (+{r['words_added']} / -{r['words_removed']})" for r in top)]
    L += ['- numbering gaps (checked against the page text: the missing number is not printed):'] + [f'  - {g}' for g in gaps]
    return L
