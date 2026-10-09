"""Rebuild the printed hierarchy of the House GAB agency tables (CR00638.pdf) for one department and write it per agency:
../data/gab/<dept>/<agency>/pap_{A,B}.csv. Usage: python gab_tree.py "DEPARTMENT OF HEALTH" [A B]. Run from build/.

Visual cues used (see the page images): indentation relative to the left-margin line-number column (`rx`); wrapped labels are single-spaced
while a heading sits a blank line above its first child; a heading with no amount is closed by its 'Sub-total, X' / 'Total, X' / 'Total X'
row; 'TOTAL NEW APPROPRIATIONS' closes the table. Where the bill prints a program and its activities at the same indent (Senate, DA), an
ALL-CAPS row only becomes a parent when the following same-indent rows sum to it exactly.

Tables (`table`): summary (by Programs/Projects), detail (by Programs/Activities/Projects), object (by Object of Expenditures; amounts in
THOUSAND pesos), purpose; '' = row outside a table (provision text, the agency lead line).
`role`: item (leaf) | group (has children) | subtotal ('Sub-total, X' / 'Total, X' = the amount of heading X) | total (TOTAL NEW
APPROPRIATIONS) | lead (the 'For general administration ... hereunder P x' line = agency total) | text. Never sum across roles: per table,
items sum to the total. parent_id points to the row whose amount contains this one; child_sum/sum_ok check the printed sum.
`id` = the row's id in ../data/gab_pap_{A,B}.csv (matched by page + printed amounts), so the two files join; 'T…' if no match.
Also writes projects_{A,B}.csv: the department's ../data/gab_projects_{A,B}.csv rows filed under the agency the tree puts them in (the flat
file's agency tag goes stale across page breaks), plus pap_id (the project's row in pap_*.csv: its regions, offices and Loan Proceeds / GOP
Counterpart lines are that row's descendants there) and sum_ok of that row."""
import csv, re, os, sys, hashlib, collections, unicodedata
from parse_gab_pap import lines, DEPT, AGENCY
csv.field_size_limit(10**9)

TOL = 1.5        # indent tolerance (pt); the bill's smallest indent step is 3 pt (DENR), anchor noise across pages < 1 pt
GAP = 14         # y gap (pt) between lines of one wrapped label; rows are double-spaced (~23 pt)
GENERIC = re.compile(r'^(REGULAR PROGRAMS?|PROJECTS?(\(S\))?)$', re.I)
TABLE = [('activities', 'detail'), ('object', 'object'), ('purpose', 'purpose'), ('program', 'summary')]
HEADER = re.compile(r'^New Appropriations,?\.?\s*by\b', re.I)     # ',.' printed in DOSU p820/p4339
NOISE = re.compile(r'^(GENERAL APPROPRIATIONS BILL|(?-i:FOR)\b|\(Amount|\(In Thousand|Total$)', re.I)
TITLE = re.compile(r'^[A-Z]{1,2}(?:\.\d+)?\.\s+([A-Z].{3,})$')    # centred agency title in any case ('A. Office of the Secretary', DepEd)
LEAD = re.compile(r'(\. ){3,}|hereunder', re.I)
TOTAL = re.compile(r'^(Sub-?total|Total)\b', re.I)
TNA = re.compile(r'^TOTAL NEW APP?R?OPRIATIONS', re.I)     # 'APPOPRIATIONS' printed in Sandiganbayan p1808/p5339

def norm(s):
    """Printed text, normalised for matching and output: NFKC, one kind of dash with spaces around free-standing ones, single spaces,
    dot leaders ('hereunder . . . . P') dropped. Case is kept (ALL-CAPS marks programs); matching is case-insensitive where position
    already says what a line is."""
    s = unicodedata.normalize('NFKC', s).replace('–', '-').replace('—', '-').replace('‐', '-')
    s = re.sub(r'(\s*\.){3,}\s*P?\s*$', '', s)
    return re.sub(r'\s+', ' ', s).strip()

def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60] or 'no-agency'   # '' = department printed without agencies
MIN_STEP = 3.0
REGLINE = re.compile(r'(National Capital Region|Region |Cordillera|Negros Island|Bangsamoro)')
SECTIONS = {'operations', 'supporttooperations', 'generaladministrationandsupport'}
def key(s):
    k = re.sub(r'[^a-z0-9]', '', re.sub(r'^([A-Z]\.\s+|(Sub-?total|Total)\s*,?\s*)', '', s, flags=re.I).lower())
    return k.replace('expenditures', 'expenses').replace('operatingservices', 'operatingexpenses').replace('operating', '')   # the bill words the same heading/total pair differently ('...Operating Expenditures' / 'Total ... Expenses'; 'Total Maintenance and Other Operating Services', SCSC p834)
def caps(s): return sum(c.isupper() for c in s) > 0.8 * sum(c.isalpha() for c in s)

def events(copy, dept_name):
    """Walk the department's pages; yield ('row', dict) for amount rows and heading events. Headings / wraps decided by y gap."""
    pages = [int(r['page']) for r in csv.DictReader(open(f'../data/gab_pap_{copy}.csv', encoding='utf8')) if r['dept'] == dept_name]
    dept = agency = ''; table = None; pend = []; out = []; last_a = None
    def flush():   # pending lines -> heading events (blocks split by blank lines)
        nonlocal pend
        if table:
            for b in blocks(pend, table): out.append(dict(kind='H', agency=agency, table=table, pn=b[0]['pn'], rx=b[0]['rx'], label=' '.join(l['lab'] for l in b)))
        pend = []
    for L in lines(copy, min(pages), max(pages), small=True, keep_dash=True):
        L['lab'] = lab = norm(L['lab']); am = L['am']
        if not am:
            if lab.strip() == 'GENERAL SUMMARY': break           # every department ends with one compact roll-up page
            # (all agencies, one row each, no per-agency lead/summary/detail/object tables) after its real agency
            # sections; its own heading text differs enough from the real sections' ('UNIVERSITY OF THE PHILIPPINES
            # SYSTEM (THE NATIONAL UNIVERSITY)' vs the real section's 'UNIVERSITY OF THE PHILIPPINES SYSTEM') to
            # read as new, separate agencies instead of re-merging into the ones already built - stop here rather
            # than emit those as bogus near-empty entries (confirmed harmless on every department run so far only
            # because their shorter agency lists happened to re-merge by accident; SUC's didn't).
            title = (L['rx'] or 0) > 150                        # centred: department / agency titles
            m = DEPT.match(lab) or (title and DEPT.match(lab.upper()))
            # only the real 'dept_name' header counts - SUC's own region lettering (A-S) includes letters that are
            # themselves valid Roman numerals ('I. REGION V - BICOL', 'L. REGION VII - CENTRAL VISAYAS'), which
            # would otherwise misfire as a new department here too and, since this function's own `dept` tracking
            # (not just the already-correct page range from parse_gab_pap.py) decides what counts as dept_name's
            # rows, would cut the walk short even on a correct page list. A global next-in-sequence counter (as in
            # parse_gab_pap.py/gab_toc.py) doesn't work here since events() is called once per department and has
            # no notion of which number in the sequence dept_name itself is - but it doesn't need one: dept_name is
            # already known exactly, so just require the match to equal it.
            if m and m.group(2).strip() == dept_name:
                dept = dept_name; agency = ''; table = None; pend = []; continue
            m = AGENCY.match(lab) or (title and TITLE.match(lab))
            if m and not GENERIC.match(m.group(m.lastindex).strip()): agency = m.group(m.lastindex).strip().upper(); table = None; pend = []; continue
            if HEADER.match(lab):
                flush(); table = next(t for k, t in TABLE if k in lab.lower()); continue
            if re.match(r'Special Provision', lab, re.I): flush(); table = None; continue
            if NOISE.match(lab) or (L['x'] or 0) >= 250: pend = []; continue      # column-header text sits right of x 250
            pend.append(L); continue
        if dept != dept_name: pend = []; continue
        # a label that wraps AFTER its amount line ('Cebu-Mactan Bridge ... 8,570,911,000' / 'Construction Project, JICA Loan No. PH - P274', DPWH p1453):
        # text single-spaced right below an amount row, at its indent, and not itself wrapping into the next amount line, continues that row's label
        if last_a is not None and out and out[-1]['kind'] == 'A' and out[-1]['agency'] == agency and out[-1]['table'] == table and table != 'object' and pend and L['rx'] is not None and out[-1]['rx'] is not None and L['rx'] > out[-1]['rx'] + TOL:
            cont, prev = [], last_a
            for l in pend:
                if l['pn'] == prev['pn'] and 0 < l['y'] - prev['y'] <= GAP and l['rx'] is not None and out[-1]['rx'] is not None and abs(l['rx'] - out[-1]['rx']) <= TOL and not wrap(l, L, table): cont.append(l); prev = l
                else: break
            if cont:   # the block must be followed by a gap: if the chain runs on (within single spacing) into the next line / the amount line, it is that row's label
                nxt = pend[len(cont)] if len(cont) < len(pend) else L
                if nxt['pn'] == cont[-1]['pn'] and 0 < nxt['y'] - cont[-1]['y'] <= GAP: cont = []
            if cont: out[-1]['label'] += ' ' + ' '.join(l['lab'] for l in cont); pend = pend[len(cont):]
        bl = blocks(pend, table); glue = []
        if bl and wrap(bl[-1][-1], L, table): glue = bl.pop()
        pend = [l for b in bl for l in b]; flush()
        first = glue[0] if glue else L
        label = ' '.join([l['lab'] for l in glue] + [lab]).strip()
        if not label: continue
        cv = L['colv'] if L['colv'] and L['ok'] else {}
        last_a = L
        out.append(dict(kind='A', agency=agency, table=table, pn=L['pn'], rx=first['rx'], label=label, amounts='|'.join(map(str, am)), total=am[-1],
                        **{k: cv.get(k) for k in ('ps', 'mooe', 'fin', 'co')}))
        if TNA.match(label): table = None
    # a label that ends on a dangling word ('INDUSTRIAL TECHNOLOGY RESEARCH AND') with its amount on that first line wraps onto the next line
    # at the same indent (DOST ITDI p1475: '... DEVELOPMENT PROGRAM'); that line reads as a heading, so glue it back on or the row never groups.
    for e in out:   # a section name printed with a zero amount ('Operations  -', HSAC p1118) is the section heading, not a line
        if e['kind'] == 'A' and e['total'] == 0 and key(e['label']) in SECTIONS: e['kind'] = 'H'
    merged = []
    for e in out:
        p = merged[-1] if merged else None
        if (e['kind'] == 'H' and p and p['kind'] == 'A' and p['pn'] == e['pn'] and p['agency'] == e['agency'] and p['table'] == e['table']
                and p['rx'] is not None and e['rx'] is not None and abs(p['rx'] - e['rx']) <= TOL
                and (re.search(r'\b(AND|OF|FOR|THE|TO|IN|ON|OR|&)$', p['label'], re.I)
                     or (caps(p['label']) and caps(e['label']) and e['label'].endswith('PROGRAM') and not p['label'].endswith('PROGRAM')))):
            p['label'] += ' ' + e['label']; continue
        merged.append(e)
    # an amount row repeated verbatim right below itself (identical text, amount and indent) is the bill printing the line twice (DPWH p1380, every
    # 'Preventive Maintenance - Primary Roads'-type activity), which double-counts its program; keep one. Same label at a different indent
    # (the 'Region V - Bicol' region row vs its office row) is not a repeat.
    dedup = []
    for e in merged:
        p = dedup[-1] if dedup else None
        if (e['kind'] == 'A' and p and p['kind'] == 'A' and p['agency'] == e['agency'] and p['table'] == e['table'] and p['total'] == e['total']
                and p['rx'] is not None and e['rx'] is not None and abs(p['rx'] - e['rx']) <= TOL and p['label'] == e['label'] and not TOTAL.match(e['label'])):
            continue
        dedup.append(e)
    merged = dedup
    # object tables: a heading's closing amount row is sometimes printed WITHOUT the word 'Total' ('Other Compensation for Specific Groups  402',
    # NLP p1752) - it then reads as a sibling item and double-counts. A row repeating an open heading's label at that heading's indent is its total.
    open_h = []
    for e in merged:
        if e['table'] != 'object': open_h = []; continue
        if e['kind'] == 'H': e['_n'] = 0; open_h.append(e); continue
        for h in open_h: h['_n'] = h.get('_n', 0) + (e['kind'] == 'A')
        if e['kind'] == 'A' and TOTAL.match(e['label']):    # a real 'Total X' row closes heading X, so a later row labelled X is a separate line (EPD CPD p247)
            closed = next((h for h in reversed(open_h) if h['agency'] == e['agency'] and key(h['label']) == key(e['label'])), None)
            if closed: open_h = open_h[:open_h.index(closed)]
            continue
        hit = next((h for h in reversed(open_h) if h['agency'] == e['agency'] and key(h['label']) == key(e['label']) and e['rx'] is not None and h['rx'] is not None and e['rx'] <= h['rx'] + TOL and h.get('_n', 0) >= 1), None) if e['kind'] == 'A' and not TOTAL.match(e['label']) else None
        if hit: e['label'] = 'Total ' + e['label']; open_h = open_h[:open_h.index(hit)]
    return merged

def wrap(a, b, table=None):
    """True if line b continues line a (single-spaced on one page, or a's line ends a page and b starts the next). Object tables are
    single-spaced throughout, so there a continuation must also keep the indent (a heading's children sit deeper)."""
    if table == 'object' and (a['rx'] is None or b['rx'] is None or abs(a['rx'] - b['rx']) > TOL): return False
    if a['pn'] == b['pn']: return 0 < b['y'] - a['y'] <= GAP
    # across a page break the continuation must also keep the indent: a heading ending page n sits shallower than its first child on n+1
    return b['pn'] == a['pn'] + 1 and a['y'] > 690 and b['y'] < 70 and a['rx'] is not None and b['rx'] is not None and abs(a['rx'] - b['rx']) <= TOL

def blocks(ls, table=None):
    out = []
    for l in ls:
        if out and wrap(out[-1][-1], l, table): out[-1].append(l)
        else: out.append([l])
    return out

def tree(E):
    """E: events of one table (same agency, table). Sets parent (index or None), role, child_sum on the 'A' events."""
    n = len(E); parent = [None] * n
    A = [i for i, e in enumerate(E) if e['kind'] == 'A']
    is_tot = lambda e: e['kind'] == 'A' and TOTAL.match(e['label'])
    # pass 1 (bottom-up): an amount row is a group if the rows after it are deeper, or (ALL-CAPS rows only) at the same indent and summing
    # to it exactly. Child level: try each indent level found below the row, shallowest first, and keep the first whose rows sum exactly
    # to the printed amount (DOH prints NCR rows ~4 pt left of the other regions); rows deeper than the level are grandchildren, rows
    # between the parent and the level are children too. No exact level -> the row stays a leaf and the rows below go to the enclosing
    # heading, whose Sub-total row is checked instead (ACPC p168 prints a sibling 2.4 pt deeper than its neighbour).
    for i in reversed(A):
        e = E[i]
        if is_tot(e) or i + 1 >= n or E[i + 1]['kind'] != 'A' or is_tot(E[i + 1]) or e['rx'] is None or E[i + 1]['rx'] is None: continue
        # a SUB-PROGRAM header can print deeper than its own activities (COMELEC p1847: header at 22.5, activities at 19.4): it then adopts the
        # shallower rows below it up to the next all-caps header, on an exact sum like any other group
        subp = bool(re.search('SUB-PROGRAM', e['label'])); shallow = subp
        if E[i + 1]['rx'] < e['rx'] - TOL and not subp: continue
        same = not shallow and abs(E[i + 1]['rx'] - e['rx']) <= TOL
        if not shallow and e['table'] == 'object' and TOL < E[i + 1]['rx'] - e['rx'] < MIN_STEP: continue   # in OBJECT tables 1.5-3 pt deeper is indent drift, not nesting (detail tables do nest 2-3 pt: activity -> its region row) (CCC p1703: 'Productivity Enhancement Incentive' 1.6 pt right of its sibling Cash Gift, same 305)
        # same-indent, mixed-case row is a sibling, unless the next row is a region line repeating its amount (CSC p1818: an activity printed
        # level with its own 'National Capital Region (NCR)' breakdown) - then that region row is its child, not a double-counted sibling.
        # an activity whose region rows ALL print level with it (TUP p518: 'General Management and Supervision' 173,849,000, then NCR / CALABARZON /
        # Western Visayas at its indent) takes the region rows right below it as children - region rows only, on an exact sum
        regsame = same and not caps(e['label']) and bool(REGLINE.match(E[i + 1]['label'])) and not REGLINE.match(e['label'])
        if same and not caps(e['label']) and not regsame and not (E[i + 1]['total'] == e['total'] and ((REGLINE.match(E[i + 1]['label']) and not REGLINE.match(e['label'])) or (REGLINE.match(e['label']) and not REGLINE.match(E[i + 1]['label'])))): continue   # (2nd form: a region row followed by its own office row at the same indent, GHQ AFP p1349)
        best = None
        # strict run first; if no exact sum, a looser one that also takes same-indent mixed-case rows (a lump line like 'Quick Response Fund'
        # printed level with its own caps program, DENR MGB p980) and stops only at the next caps header at that indent
        # last resort: children within 1,000 of the printed amount (the bill's own arithmetic is occasionally off by one printed unit, e.g. PIA
        # p1687: 20,318,000 vs a 20,319,000 office line) - adopt them anyway so only that row is flagged (sum_ok=0), not every ancestor
        for loose, near in ((False, False), (True, False), (False, True)):
            regional = loose and not caps(e['label']) and bool(REGLINE.match(E[i + 1]['label']))   # activity whose region rows print level with it (DENR p937)
            if loose and (same or shallow or not (caps(e['label']) or regional)): continue
            run = []
            for k in range(i + 1, n):          # candidate descendants: until a heading, a total row, or a row back at the parent's indent
                f = E[k]
                if f['kind'] != 'A' or is_tot(f) or f['rx'] is None or (not same and not shallow and f['rx'] <= e['rx'] + TOL and not re.search('SUB-PROGRAM', f['label']) and not (loose and not caps(f['label']))) or (shallow and caps(f['label']) and f['rx'] <= e['rx'] + TOL) or (same and f['rx'] < e['rx'] - (MIN_STEP if regsame else TOL)): break   # (level region rows drift up to 2.1 pt left, TUP p519 Region VI)
                if loose and f['rx'] < e['rx'] - TOL: break
                if (regional or regsame) and parent[k] is None and not REGLINE.match(f['label']): break
                if parent[k] is None: run.append(k)
            for c in sorted({E[k]['rx'] for k in run if E[k]['rx'] >= E[i + 1]['rx'] - TOL} | ({E[k]['rx'] for k in run} if loose else set())):
                kids, s = [], 0
                for k in run:
                    if E[k]['rx'] > c + TOL: continue
                    kids.append(k); s += E[k]['total']
                    if s >= e['total'] - (1000 if near else 0): break
                if s == e['total'] or (near and e['total'] >= 1_000_000 and abs(s - e['total']) <= 1000): best = kids; break
            if best is not None: break
        if best is None: continue
        for k in best: parent[k] = i
    # a funding-source line ('Loan Proceeds') printed at the project's own indent AFTER its region rows repeats the project's amount as a second
    # breakdown (DOTr p1637); hang it under the leaf row of equal amount (the Central Office row), the shape DICT/CSC print natively
    hasKids = set(p for p in parent if p is not None)
    for k in A:
        if parent[k] is None and re.match(r'Loan Proceeds', E[k]['label']):
            j = next((j for j in reversed(A) if j < k and E[j]['total'] == E[k]['total'] and j not in hasKids and E[j]['rx'] is not None and E[k]['rx'] is not None and E[j]['rx'] >= E[k]['rx'] - TOL), None)
            if j is not None: parent[k] = j
    # funding split: 'Loan Proceeds' + 'GOP Counterpart' lines printed right after a project row, summing to its amount (PCC p1778) - children of it
    FUND = re.compile(r'(Loan Proceeds|GOP Counterpart|Grants?|Local Counterpart)')
    for j in A:
        if parent[j] is not None or j in hasKids or FUND.match(E[j]['label']) or is_tot(E[j]): continue
        run, t = [], 0
        for k in range(j + 1, n):
            f = E[k]
            if f['kind'] != 'A' or parent[k] is not None or not FUND.match(f['label']): break
            run.append(k); t += f['total']
            if t >= E[j]['total']: break
        if run and t == E[j]['total'] and len(run) > 1:
            for k in run: parent[k] = j
            hasKids.add(j)
    # pass 2: headings (no amount) collect the unclaimed rows until their closing total row, which becomes their parent.
    stack = []
    def close(fr, node):
        for k in fr['kids'] + ([fr['self']] if 'self' in fr else []):
            if node is not None: parent[k] = node
            elif stack: stack[-1]['kids'].append(k)
    for i, e in enumerate(E):
        if e['kind'] == 'H':
            while stack and (stack[-1]['rx'] > e['rx'] + TOL or (abs(stack[-1]['rx'] - e['rx']) <= TOL and stack[-1]['deep'])): close(stack.pop(), None)
            stack.append(dict(rx=e['rx'], key=key(e['label']), label=e['label'], kids=[], deep=False)); continue
        if is_tot(e):
            if TNA.match(e['label']):
                while stack: close(stack.pop(), None)
                for t in [k for k in A if k < i and parent[k] is None and is_tot(E[k])]:   # 'Total, X' adopts the unparented Sub-total rows just above it that sum to it (CSC p1825: Total, Project(s))
                    s, run = 0, []
                    for k in reversed([k for k in A if k < t and parent[k] is None]):
                        if not is_tot(E[k]): break
                        run.append(k); s += E[k]['total']
                        if s >= E[t]['total']: break
                    if s == E[t]['total'] and run:
                        for k in run: parent[k] = t
                for k in A:
                    if k < i and parent[k] is None: parent[k] = i
                continue
            j = next((j for j in range(len(stack) - 1, -1, -1) if stack[j]['key'] == key(e['label'])), len(stack) - 1)
            if j >= 0:
                while len(stack) > j + 1: close(stack.pop(), None)
                close(stack.pop(), i)
        if parent[i] is None and e['kind'] == 'A' and key(e['label']) in SECTIONS and i in parent and any(is_tot(E[j]) and key(E[j]['label']) == key(e['label']) for j in range(i + 1, n)):
            # a section name printed WITH its amount ('Operations  1,134,986' - DEPDev p230) is a group row, not a heading: its own
            # 'Sub-total, Operations' must still close it, or that sub-total falls through to the enclosing heading and swallows the section
            stack.append(dict(rx=e['rx'], key=key(e['label']), label=e['label'], kids=[], deep=False, **{'self': i})); continue
        if parent[i] is None and stack:
            stack[-1]['kids'].append(i)
            if e['rx'] is not None and e['rx'] > stack[-1]['rx'] + TOL: stack[-1]['deep'] = True
    kids = collections.defaultdict(list)
    for k in A:
        if parent[k] is not None: kids[parent[k]].append(k)
    for i in A:
        e = E[i]; e['parent'] = parent[i]
        e['role'] = 'total' if TNA.match(e['label']) else 'subtotal' if is_tot(e) else 'group' if kids[i] else 'item'
        e['child_sum'] = sum(E[k]['total'] for k in kids[i]) if kids[i] else ''
        e['sum_ok'] = '' if not kids[i] else int(e['child_sum'] == e['total'])
    for i in A:     # depth + path of ancestor labels (heading names for subtotal rows)
        p, path = parent[i], []
        while p is not None: path.append(re.sub(r'^(Sub-?total|Total)\s*,\s*', '', E[p]['label'])); p = parent[p]
        E[i]['level'] = len(path); E[i]['path'] = ' > '.join(reversed(path))

def outside(e):
    """A row outside every table: the agency lead line, or Special Provision text, whose numbers (provision numbers, years, allocation
    lists like DA p109's GOCC shares) are not lines of the appropriation tree - text rows carry no amounts."""
    e.update(parent=None, role='lead' if LEAD.search(e['label']) or e.get('lead') else 'text', child_sum='', sum_ok='', level=0, path='')   # 'lead' flag: set by parse_gab_backmatter.py
    if e['role'] == 'text': e.update(total='', ps=None, mooe=None, fin=None, co=None)

def link_ids(copy, rows):
    """Attach gab_pap ids: same page, same printed amounts, in order."""
    by = collections.defaultdict(list)
    for r in csv.DictReader(open(f'../data/gab_pap_{copy}.csv', encoding='utf8')): by[int(r['page'])].append(r)
    ptr = collections.Counter(); seen = collections.Counter()
    for e in rows:
        cand = by[e['pn']]; j = ptr[e['pn']]
        hit = next((k for k in range(j, min(j + 4, len(cand))) if cand[k]['amounts'] == e['amounts']), None)
        if hit is None:   # a repeat of the same text + amounts on one page (Film Academy p1618: summary and detail TOTAL NEW APPROPRIATIONS) gets an ordinal, so ids stay unique
            k = f"TREE|{copy}|{e['pn']}|{e['label']}|{e['amounts']}"; n = seen[k]; seen[k] += 1
            e['id'] = 'T' + hashlib.sha1((k + (f'|{n}' if n else '')).encode()).hexdigest()[:11]
        else: e['id'] = cand[hit]['id']; ptr[e['pn']] = hit + 1

COLS = ['id', 'copy', 'page', 'table', 'level', 'role', 'label', 'path', 'total', 'ps', 'mooe', 'fin', 'co', 'parent_id', 'child_sum', 'sum_ok', 'rx']

def run(dept, copy, E=None):
    """E: events already adjusted by a caller (parse_gab_backmatter.py); default = events(copy, dept)."""
    E = events(copy, dept) if E is None else E; rows = [e for e in E if e['kind'] == 'A']
    link_ids(copy, rows)
    segs = collections.defaultdict(list); order = []
    for e in E:     # a table = consecutive events with the same (agency, table); rows outside tables are lead/text
        k = (e['agency'], e['table'])
        if not order or order[-1] != k: order.append(k); segs[(k, len(order))] = []
        segs[(k, len(order))].append(e)
    for (k, _), S in segs.items():
        if k[1]: tree(S)
        else:
            for e in S:
                if e['kind'] == 'A': outside(e)
        for e in S:
            if e['kind'] == 'A' and e['parent'] is not None: e['parent_id'] = S[e['parent']]['id']
    out = collections.defaultdict(list)
    for e in rows: out[e['agency']].append(dict(e, copy=copy, page=e['pn'], table=e['table'] or '', parent_id=e.get('parent_id', '')))
    projs = collections.defaultdict(list); nk = lambda t: re.sub(r'[^a-z0-9]', '', t.lower())[:25]
    for p in csv.DictReader(open(f'../data/gab_projects_{copy}.csv', encoding='utf8')):
        if p['dept'] != dept: continue
        e = next((e for e in rows if e['table'] == 'detail' and e['pn'] == int(p['page']) and e['total'] == int(p['amount']) and nk(e['label']) == nk(p['project'])), None)
        projs[e['agency'] if e else p['agency']].append(dict(p, agency=e['agency'] if e else p['agency'], pap_id=e['id'] if e else '', sum_ok=e['sum_ok'] if e else ''))
    for ag, R in out.items():
        d = f'../data/gab/{slug(dept)}/{slug(ag)}'; os.makedirs(d, exist_ok=True)
        with open(f'{d}/pap_{copy}.csv', 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=COLS, extrasaction='ignore'); w.writeheader(); w.writerows(R)
    for ag, P in projs.items():
        d = f'../data/gab/{slug(dept)}/{slug(ag)}'; os.makedirs(d, exist_ok=True)
        with open(f'{d}/projects_{copy}.csv', 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=list(P[0])); w.writeheader(); w.writerows(P)
        print(f'  projects {ag[:40]}: {len(P)} rows, linked to pap {sum(1 for p in P if p["pap_id"])}, with breakdown {sum(1 for p in P if p["sum_ok"] != "")} (sum ok {sum(1 for p in P if p["sum_ok"] == 1)})')
    return out

def report(copy, out):
    print(f'== copy {copy}')
    for ag, R in out.items():
        g = [r for r in R if r['sum_ok'] != '']
        bad = [r for r in g if not r['sum_ok']]
        tot = [r for r in R if r['role'] == 'total']
        items = collections.defaultdict(int)
        for r in R:
            if r['role'] == 'item' and r['table']: items[r['table']] += r['total']
        lead = [r['total'] for r in R if r['role'] == 'lead']
        miss = {'summary', 'detail', 'object'} - {r['table'] for r in tot}
        if miss: print(f'  !! {ag}: no TOTAL NEW APPROPRIATIONS found for table(s) {sorted(miss)} (header not recognised?)')
        print(f'  {ag[:50]:50} rows {len(R):5}  parents {len(g):4}  sum_ok {len(g) - len(bad):4}  unlinked ids {sum(r["id"].startswith("T") for r in R)}  lead {lead}')
        print(f'     TOTAL NEW APPROPRIATIONS by table: {[(r["table"], r["total"], r["sum_ok"]) for r in tot]}  items by table: {dict(items)}')
        for r in bad[:8]: print(f'     MISMATCH p{r["page"]} {r["role"]:8} {r["label"][:55]:55} printed {r["total"]:>15,} children {r["child_sum"]:>15,}')

if __name__ == '__main__':
    dept = sys.argv[1] if len(sys.argv) > 1 else 'DEPARTMENT OF HEALTH'
    for c in sys.argv[2:] or ['A', 'B', 'C']: report(c, run(dept, c))
