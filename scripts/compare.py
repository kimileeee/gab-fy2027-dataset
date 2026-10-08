"""Phase 6: appropriations_compared.csv - every appropriation with GAB_FILED and GAB_3R side by side, one row per line.

Lines pair on appropriation_id (UACS agency + normalised hierarchy + label + occurrence), so an agency that moves department between
stages (NAPC, PCUP: DSWD -> Other Executive Offices) pairs with itself instead of showing as a removal plus an addition (D10).
Status, flags and relabel pairing follow ph-pork-graph build/gab_office_compare.py, restricted to leaves (rows that hold money)."""
import collections, re

FLAG_PCT, FLAG_ABS = 0.20, 50_000_000          # a changed line is flagged if it moved by >= 20% AND >= P50M (starting guess, tunable)
SHARED = ('appropriation_id', 'dept_id', 'agency_id', 'agency_printed', 'category', 'program', 'sub_program', 'pap', 'sub_pap',
          'funding_source', 'region_printed', 'region_code', 'operating_unit', 'sub_unit', 'label', 'geo_level', 'psgc_code',
          'province_psgc', 'district_id', 'prexc_fpap_id', 'nep_match', 'drilldown_group_id')
AMT = ('ps', 'mooe', 'finex', 'co', 'amount')
COLS = (SHARED[:3] + ('dept_printed_A', 'dept_printed_B', 'moved_department') + SHARED[3:] +
        tuple(f'{k}_A' for k in AMT) + tuple(f'{k}_B' for k in AMT) +
        ('delta', 'pct_change', 'status', 'flag', 'possible_relabel', 'relabel_counterpart_id', 'relabel_counterpart_label',
         'pdf_page_A', 'pdf_page_B'))

def norm(s): return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def compare(apps):
    A = {r['appropriation_id']: r for r in apps if r['stage'] == 'GAB_FILED'}
    B = {r['appropriation_id']: r for r in apps if r['stage'] == 'GAB_3R'}
    out = []
    for i in list(A) + [i for i in B if i not in A]:
        a, b = A.get(i), B.get(i); base = b or a
        row = {k: base[k] for k in SHARED}
        row.update(dept_printed_A=a['dept_printed'] if a else '', dept_printed_B=b['dept_printed'] if b else '',
                   moved_department=int(bool(a and b and a['dept_printed'] != b['dept_printed'])),
                   pdf_page_A=a['pdf_page'] if a else '', pdf_page_B=b['pdf_page'] if b else '',
                   path=base['path_printed'], possible_relabel='', relabel_counterpart_id='', relabel_counterpart_label='')
        for k in AMT:
            row[f'{k}_A'] = (a[k] or 0) if a else ''; row[f'{k}_B'] = (b[k] or 0) if b else ''
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
    """A removed (GAB_FILED only) and an added (GAB_3R only) line with the same amount in the same agency are probably one line printed
    under a different label or parent, not a real cut plus a real insertion. Pair 1:1, strongest evidence first: 'moved' (same label,
    different ancestors), 'same_parent' (same ancestors, different label = a rename), 'same_amount' (>= P1M and unique on both sides)."""
    for how, keyf in (('moved', lambda r, t: (r['agency_id'], norm(r['label']), t)),
                      ('same_parent', lambda r, t: (r['agency_id'], norm(r['path']), t)),
                      ('same_amount', lambda r, t: (r['agency_id'], t))):
        rem, add = collections.defaultdict(list), collections.defaultdict(list)
        for r in out:
            if r['possible_relabel']: continue
            if r['status'] == 'removed' and r['amount_A']: rem[keyf(r, r['amount_A'])].append(r)
            elif r['status'] == 'added' and r['amount_B']: add[keyf(r, r['amount_B'])].append(r)
        for k, rs in rem.items():
            if len(rs) == 1 and len(add.get(k, [])) == 1 and (how != 'same_amount' or k[-1] >= 1_000_000):
                x, y = rs[0], add[k][0]
                for p, q in ((x, y), (y, x)):
                    p.update(possible_relabel=how, relabel_counterpart_id=q['appropriation_id'], relabel_counterpart_label=q['label'])

def checks(rows, gab_compare_rows):
    """Lines for CHECKS.md: status/flag counts, transfers between departments, and per-department agreement with the old compare."""
    L = ['', '## Stage comparison (phase 6): appropriations_compared.csv', '']
    st = collections.Counter(r['status'] for r in rows)
    L += [f"- {len(rows):,} lines: " + ', '.join(f'{k} {v:,}' for k, v in st.most_common())]
    L += ['- flags: ' + ', '.join(f'{k} {v:,}' for k, v in collections.Counter(r['flag'] for r in rows if r['flag']).most_common())]
    rel = collections.Counter(r['possible_relabel'] for r in rows if r['possible_relabel'])
    L += ['- relabel pairs (rows, both sides counted): ' + (', '.join(f'{k} {v:,}' for k, v in rel.most_common()) or 'none')]
    unp = [r for r in rows if r['status'] in ('added', 'removed') and not r['possible_relabel']]
    L += [f"- unpaired: added {sum(1 for r in unp if r['status'] == 'added'):,} (₱{sum(r['delta'] for r in unp if r['status'] == 'added'):,}), "
          f"removed {sum(1 for r in unp if r['status'] == 'removed'):,} (₱{-sum(r['delta'] for r in unp if r['status'] == 'removed'):,})"]
    L += [f"- net change GAB_FILED → GAB_3R: ₱{sum(r['delta'] for r in rows):,}"]
    mv = collections.defaultdict(lambda: [0, 0, 0, '', ''])
    for r in rows:
        if r['moved_department']:
            m = mv[r['agency_printed']]; m[0] += 1; m[1] += r['amount_A']; m[2] += r['amount_B']; m[3] = r['dept_printed_A']; m[4] = r['dept_printed_B']
    L += ['', 'Agencies printed under a different department in GAB_3R (paired as the same lines, not removed + added):', '']
    L += [f'- {k}: {v[3]} → {v[4]}, {v[0]} lines, ₱{v[1]:,} → ₱{v[2]:,} (change ₱{v[2] - v[1]:,})' for k, v in mv.items()] or ['- none']
    if not gab_compare_rows: return L                 # the per-department compare files exist only in ph-pork-graph
    # agreement with ph-pork-graph's per-department pap_compare.csv (detail table, role=item rows) on line counts by status
    old = collections.defaultdict(collections.Counter)
    for r in gab_compare_rows:
        if r['role'] == 'item' and r['table'] == 'detail': old[r['dept']][r['status']] += 1
    new = collections.defaultdict(collections.Counter)
    for r in rows: new[r['dept_printed_B'] or r['dept_printed_A']][r['status']] += 1
    diff = [(d, dict(old[d]), dict(new[d])) for d in sorted(set(old) | set(new)) if old[d] != new[d]]
    L += ['', f'Per-department status counts vs the per-department pap_compare.csv files: {len(set(old) | set(new)) - len(diff)} departments identical, '
          f'{len(diff)} differ (old = role=item rows, which include a few non-leaves; new = leaves, paired across departments):', '']
    L += [f'- {d}: old {o} | new {n}' for d, o, n in diff]
    return L
