"""Phase 2b + 6: special_provisions.csv (one row per Special Provision x stage) and special_provisions_compared.csv (two stages side
by side per comparison in stages.PAIRS, with a word-level change count; _from / _to = earlier / later stage).

Input: pipeline/data/gab_provisions_{A,B,C}.csv (parse_gab_provisions.py). Provisions are attached to the agency whose heading is
printed above them; a provision printed before any agency heading is department-wide (scope = department). Back-matter funds
(Unprogrammed Appropriations, Pension and Gratuity Fund, ...) print provisions too although their tables are not parsed yet: they are
kept, with scope = back_matter and no UACS code. Provisions pair across stages on agency + normalised title (+ occurrence), so a
renumbered provision is still the same provision."""
import collections, csv, difflib, hashlib, os, re
from stages import STAGE, PAIRS, comparison, pdf_ref

def norm(s): return re.sub(r'[^a-z0-9]', '', (s or '').lower())
def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60] or 'no-agency'
def h(*p): return hashlib.sha1('|'.join(map(str, p)).encode()).hexdigest()[:12]

def build(ph_data, agency, names, trees):
    """agency: {(dept_slug, agency_slug): (dept, agency, dept_dsc, agency_dsc)} from the NEP crosswalk; names: TOC rows per folder;
    trees: parsed agency tables, for the page span of each agency (attributes provisions printed before an agency's heading)."""
    dept_of_folder = {d: v[0] for (d, g), v in agency.items()}
    span = {(c, d, g): (min(int(r['page']) for r in rows), max(int(r['page']) for r in rows)) for (c, d, g), rows in trees.items() if rows}
    rows, gaps = [], []
    for c in 'ABC':
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
                             scope=scope, attribution=how, provision_no=r['no'], title=r['title'], text=r['text'], pdf_file=pdf_ref(r['page_start'])[0],
                             pdf_page_start=pdf_ref(r['page_start'])[1], pdf_page_end=pdf_ref(r['page_end'])[1], lines=int(r['lines'])))
        for k, nos in seen_no.items():
            n = [int(x) for x in nos if x != '']
            if n != list(range(1, len(n) + 1)): gaps.append(f'{STAGE[c]} {k}: numbered {n} as printed')
    return rows, gaps

def compare(rows):
    return [r for sa, sb in PAIRS for r in compare_pair(rows, sa, sb)]

def compare_pair(rows, sa, sb):
    A = {r['provision_id']: r for r in rows if r['stage'] == sa}
    B = {r['provision_id']: r for r in rows if r['stage'] == sb}
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
        out.append(dict(comparison=comparison(sa, sb), stage_from=sa, stage_to=sb, provision_id=i, dept_id=base['dept_id'], agency_id=base['agency_id'], dept_printed=base['dept_printed'],
                        agency_printed=base['agency_printed'], scope=base['scope'], title=base['title'],
                        provision_no_from=a['provision_no'] if a else '', provision_no_to=b['provision_no'] if b else '', status=status,
                        words_added=added if a and b else len(wb), words_removed=removed if a and b else len(wa),
                        text_from=a['text'] if a else '', text_to=b['text'] if b else '',
                        pdf_file_from=a['pdf_file'] if a else '', pdf_page_from=a['pdf_page_start'] if a else '',
                        pdf_file_to=b['pdf_file'] if b else '', pdf_page_to=b['pdf_page_start'] if b else ''))
    return out

def checks(rows, cmp, gaps):
    L = ['', '## Special Provisions (phase 2b)', '']
    st = collections.Counter((r['stage'], r['scope']) for r in rows)
    L += ['- provisions: ' + ', '.join(f'{s} {sc} {n:,}' for (s, sc), n in sorted(st.items()))]
    L += ['- agencies with provisions: ' + ', '.join(f"{st} {len({r['agency_id'] for r in rows if r['stage'] == st and r['agency_id']})}" for st in STAGE.values())
          + f"; untitled: {sum(1 for r in rows if not r['title'])}"]
    for sa, sb in PAIRS:
        C = [r for r in cmp if r['comparison'] == comparison(sa, sb)]
        L += [f'- compared {sa} → {sb}: ' + ', '.join(f'{k} {v:,}' for k, v in collections.Counter(r['status'] for r in C).most_common())]
        top = sorted((r for r in C if r['status'] in ('text_changed', 'added', 'removed')), key=lambda r: -(r['words_added'] + r['words_removed']))[:10]
        L += ['  - largest changes (words added / removed): ' + '; '.join(f"{r['agency_printed'] or r['dept_printed']} — {r['title'][:50]} ({r['status']}, +{r['words_added']} / -{r['words_removed']})" for r in top)]
    L += ['- numbering gaps (checked against the page text: the missing number is not printed):'] + [f'  - {g}' for g in gaps]
    return L
