"""Column assignment (PS / MOOE / [Financial] / CO / Total) for amounts in the House GAB tables (CR00638.pdf).
Amounts are right-aligned on a fixed grid (step D pt, Total rightmost) and a blank column is simply absent, so the column of a lone amount
can only be read from its right edge x1. T (right edge of the Total column) varies by page; the column set depends on the table header
(4 columns: PS, MOOE, CO, Total; 5 with 'Financial Expenses' on 6 DOF/BIR-type tables), which carries over continuation pages.
Run from build/."""
import re, collections
from parse_gab_annex import NUM

D = 73.6            # column step (pt); measured 73.0-74.2 across pages
TOL = 9.0           # max distance of x1 from a grid line (pt)
COLS = {4: ('total', 'co', 'mooe', 'ps'), 5: ('total', 'co', 'fin', 'mooe', 'ps')}
HDR = re.compile(r'Pers\w+\s+Se\w+.*Capital\s+Outlays.*Total')

def rows_x1(page):
    """Like parse_gab_annex.rows_of, tokens are (x0, text, x1)."""
    w = sorted(page.get_text('words'), key=lambda w: (round(w[1] / 2), w[0]))
    rows = []
    for x0, y0, x1, y1, t, b, l, _ in w:
        if rows and abs(rows[-1][0] - y0) <= 2.5: rows[-1][1].append((x0, t, x1))
        else: rows.append([y0, [(x0, t, x1)]])
    return rows

def page_T(rows):
    """Right edge of the Total column: the rightmost amount cluster (>= 2 hits) at x1 >= 560; a lone hit only if nothing clusters."""
    c = collections.Counter(round(x1) for _, r in rows for x0, t, x1 in r if NUM.match(t) and x1 >= 560)
    if not c: return None
    multi = [k for k, v in c.items() if v >= 2]
    return max(multi) if multi else max(c, key=c.get)

def header_layout(row):
    """4 / 5 if this row is a column-header row, else None."""
    txt = ' '.join(t for x0, t, x1 in sorted(row) if not re.fullmatch(r'\d{1,2}', t))
    return (5 if 'Financial' in txt else 4) if HDR.search(txt) else None

def assign(amts, T, layout=4):
    """amts: [(value, x1)]. Returns (dict ps/mooe/fin/co/total -> value or None, ok). Column k = round((T - x1) / D): 0 Total, 1 CO, ... PS last.
    ok=False if an amount is off-grid or two land in one column (those amounts are left unassigned)."""
    cols = COLS[layout]; out = dict(ps=None, mooe=None, fin=None, co=None, total=None); ok = T is not None
    for v, x1 in amts:
        if T is None: break
        k = round((T - x1) / D)
        if not 0 <= k < len(cols) or abs(T - x1 - k * D) > TOL or out[cols[k]] is not None: ok = False; continue
        out[cols[k]] = v
    return out, ok

class ColState:
    """Walks pages/rows in order. Use: st.page(rows); for each row: st.row(r) first, then st.cols(amts) (None outside a table), then st.after(r)."""
    def __init__(self): self.layout, self.in_table, self.T, self.Tprev = 4, False, None, None
    def page(self, rows): self.T = page_T(rows) or self.Tprev; self.Tprev = self.T
    @staticmethod
    def text(r): return ' '.join(t for x0, t, x1 in sorted(r) if not re.fullmatch(r'\d{1,2}', t) and not NUM.match(t))
    def row(self, r):
        h = header_layout(r)
        if h: self.layout, self.in_table = h, True
        elif re.match(r'Special Provision', self.text(r)): self.in_table = False
    def cols(self, amts):
        """amts: [(value, x1)] -> (dict, ok) or (None, None) outside a table."""
        return assign(amts, self.T, self.layout) if self.in_table else (None, None)
    def after(self, r):
        if re.match(r'TOTAL NEW APPROPRIATIONS', self.text(r)): self.in_table = False
