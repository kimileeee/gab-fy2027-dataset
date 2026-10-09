"""Phase 6: appropriations_compared.csv - every appropriation line in two stages side by side, one row per line x comparison
(stages.PAIRS: GAB_FILED -> GAB_2R, GAB_2R -> GAB_3R, and GAB_FILED -> GAB_3R). Suffix _from / _to = the earlier / later stage.

Lines pair on appropriation_id (UACS agency + normalised hierarchy + label + occurrence), so an agency that moves department between
stages (NAPC, PCUP: DSWD -> Other Executive Offices) pairs with itself instead of showing as a removal plus an addition (D10).
Status, flags and relabel pairing follow ph-pork-graph build/gab_office_compare.py, restricted to leaves (rows that hold money)."""
import collections, re
from stages import PAIRS, comparison

FLAG_PCT, FLAG_ABS = 0.20, 50_000_000          # a changed line is flagged if it moved by >= 20% AND >= P50M (starting guess, tunable)
SHARED = ('appropriation_id', 'dept_id', 'agency_id', 'agency_printed', 'category', 'program', 'sub_program', 'pap', 'sub_pap',
          'funding_source', 'region_printed', 'region_code', 'operating_unit', 'sub_unit', 'label', 'geo_level', 'psgc_code',
          'province_psgc', 'district_id', 'prexc_fpap_id', 'nep_match', 'drilldown_group_id', 'unprogrammed')
AMT = ('ps', 'mooe', 'finex', 'co', 'amount')
COLS = (('comparison', 'stage_from', 'stage_to') + SHARED[:3] + ('dept_printed_from', 'dept_printed_to', 'moved_department') + SHARED[3:] +
        tuple(f'{k}_from' for k in AMT) + tuple(f'{k}_to' for k in AMT) +
        ('delta', 'pct_change', 'status', 'flag', 'possible_relabel', 'relabel_counterpart_id', 'relabel_counterpart_label',
         'pdf_file_from', 'pdf_page_from', 'pdf_file_to', 'pdf_page_to'))

def norm(s): return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def compare(apps):
    return [r for sa, sb in PAIRS for r in compare_pair(apps, sa, sb)]

def compare_pair(apps, sa, sb):
    A = {r['appropriation_id']: r for r in apps if r['stage'] == sa}
    B = {r['appropriation_id']: r for r in apps if r['stage'] == sb}
    out = []
    for i in list(A) + [i for i in B if i not in A]:
        a, b = A.get(i), B.get(i); base = b or a
        row = {k: base[k] for k in SHARED}
        row.update(comparison=comparison(sa, sb), stage_from=sa, stage_to=sb,
                   dept_printed_from=a['dept_printed'] if a else '', dept_printed_to=b['dept_printed'] if b else '',
                   moved_department=int(bool(a and b and a['dept_printed'] != b['dept_printed'])),
                   pdf_file_from=a['pdf_file'] if a else '', pdf_page_from=a['pdf_page'] if a else '',
                   pdf_file_to=b['pdf_file'] if b else '', pdf_page_to=b['pdf_page'] if b else '',
                   path=base['path_printed'], possible_relabel='', relabel_counterpart_id='', relabel_counterpart_label='')
        for k in AMT:
            row[f'{k}_from'] = (a[k] or 0) if a else ''; row[f'{k}_to'] = (b[k] or 0) if b else ''
        ta, tb = (a['amount'] if a else 0), (b['amount'] if b else 0)
        d = tb - ta; row['delta'] = d
        if a and b:
            pct = d / ta if ta else (1 if d else 0)
            row.update(status='unchanged' if d == 0 else 'amount_changed', pct_change=round(pct, 4),
                       flag='new_amount' if ta == 0 and tb > 0 else ('big_increase' if d > 0 else 'big_decrease')
                       if abs(pct) >= FLAG_PCT and abs(d) >= FLAG_ABS else '')
        elif a: row.update(status='removed', pct_change=-1, flag='removed_line')
        else: row.update(status='added', pct_change=1, flag='new_line')
        out.append(row)
    mark_relabels(out)
    for r in out: r.pop('path')
    return out

def mark_relabels(out):
    """A removed (earlier stage only) and an added (later stage only) line with the same amount in the same agency are probably one line printed
    under a different label or parent, not a real cut plus a real insertion. Pair 1:1, strongest evidence first: 'moved' (same label,
    different ancestors), 'same_parent' (same ancestors, different label = a rename), 'same_amount' (>= P1M and unique on both sides)."""
    for how, keyf in (('moved', lambda r, t: (r['agency_id'], norm(r['label']), t)),
                      ('same_parent', lambda r, t: (r['agency_id'], norm(r['path']), t)),
                      ('same_amount', lambda r, t: (r['agency_id'], t))):
        rem, add = collections.defaultdict(list), collections.defaultdict(list)
        for r in out:
            if r['possible_relabel']: continue
            if r['status'] == 'removed' and r['amount_from']: rem[keyf(r, r['amount_from'])].append(r)
            elif r['status'] == 'added' and r['amount_to']: add[keyf(r, r['amount_to'])].append(r)
        for k, rs in rem.items():
            if len(rs) == 1 and len(add.get(k, [])) == 1 and (how != 'same_amount' or k[-1] >= 1_000_000):
                x, y = rs[0], add[k][0]
                for p, q in ((x, y), (y, x)):
                    p.update(possible_relabel=how, relabel_counterpart_id=q['appropriation_id'], relabel_counterpart_label=q['label'])

def checks(rows, gab_compare_rows):
    """Lines for CHECKS.md: per comparison, status/flag counts and transfers between departments; agreement with the old per-department
    compare (ph-pork-graph pap_compare.csv = copy A vs B = GAB_FILED -> GAB_2R)."""
    L = ['', '## Stage comparison (phase 6): appropriations_compared.csv']
    for sa, sb in PAIRS:
        R = [r for r in rows if r['comparison'] == comparison(sa, sb)]
        L += ['', f'### {sa} → {sb}', '']
        st = collections.Counter(r['status'] for r in R)
        L += [f"- {len(R):,} lines: " + ', '.join(f'{k} {v:,}' for k, v in st.most_common())]
        L += ['- flags: ' + (', '.join(f'{k} {v:,}' for k, v in collections.Counter(r['flag'] for r in R if r['flag']).most_common()) or 'none')]
        rel = collections.Counter(r['possible_relabel'] for r in R if r['possible_relabel'])
        L += ['- relabel pairs (rows, both sides counted): ' + (', '.join(f'{k} {v:,}' for k, v in rel.most_common()) or 'none')]
        unp = [r for r in R if r['status'] in ('added', 'removed') and not r['possible_relabel']]
        L += [f"- unpaired: added {sum(1 for r in unp if r['status'] == 'added'):,} (₱{sum(r['delta'] for r in unp if r['status'] == 'added'):,}), "
              f"removed {sum(1 for r in unp if r['status'] == 'removed'):,} (₱{-sum(r['delta'] for r in unp if r['status'] == 'removed'):,})"]
        L += [f"- net change: ₱{sum(r['delta'] for r in R):,}"]
        mv = collections.defaultdict(lambda: [0, 0, 0, '', ''])
        for r in R:
            if r['moved_department']:
                m = mv[r['agency_printed']]; m[0] += 1; m[1] += r['amount_from']; m[2] += r['amount_to']; m[3] = r['dept_printed_from']; m[4] = r['dept_printed_to']
        L += ['- agencies printed under a different department (paired as the same lines): ' +
              ('; '.join(f'{k}: {v[3]} → {v[4]}, {v[0]} lines, ₱{v[1]:,} → ₱{v[2]:,}' for k, v in mv.items()) or 'none')]
    if not gab_compare_rows: return L                 # the per-department compare files exist only in ph-pork-graph
    old = collections.defaultdict(collections.Counter)
    for r in gab_compare_rows:
        if r['role'] == 'item' and r['table'] == 'detail': old[r['dept']][r['status']] += 1
    new = collections.defaultdict(collections.Counter)
    for r in rows:
        if r['comparison'] == comparison('GAB_FILED', 'GAB_2R'): new[r['dept_printed_to'] or r['dept_printed_from']][r['status']] += 1
    diff = [(d, dict(old[d]), dict(new[d])) for d in sorted(set(old) | set(new)) if old[d] != new[d]]
    L += ['', f'GAB_FILED → GAB_2R status counts vs the per-department pap_compare.csv files (copy A vs B): {len(set(old) | set(new)) - len(diff)} departments identical, '
          f'{len(diff)} differ (old = role=item rows, which include a few non-leaves; new = leaves, paired across departments):', '']
    L += [f'- {d}: old {o} | new {n}' for d, o, n in diff]
    return L
