"""Rebuild every parsed input of the release from the bill PDF: python pipeline/run.py

The parsers in pipeline/build/ are a pinned snapshot of ph-pork-graph's build/ (see pipeline/README.md). They run from build/ with
the PDF at raw/hb10858/CR00638.pdf and write ../data/ - the same layout they were written for. Curated tables (pipeline/curated/:
reference geography and the reviewed DEO -> district map) are copied into data/ last."""
import csv, hashlib, os, shutil, subprocess, sys
import duckdb, pymupdf

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD, DATA, PDF = (os.path.join(ROOT, p) for p in ('build', 'data', os.path.join('raw', 'hb10858', 'CR00638.pdf')))
PDF_SHA256 = '3242a248d1436be5d15c2bd81628c1c9691e0b796fc4a58552d063f18177b6b0'
LAST_REGULAR_DEPT = 'COMMISSION ON HUMAN RIGHTS'          # departments I-XXXV; back matter XXXVI-XLIII is not parsed yet
SUC = 'STATE UNIVERSITIES AND COLLEGES'                   # own builder: Department -> Region -> Institution

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def step(*args):
    print('>', ' '.join(args), flush=True)
    p = subprocess.run([sys.executable, *args], cwd=BUILD, capture_output=True, text=True, encoding='utf-8')
    if p.returncode: sys.exit(f'FAILED {args}:\n{p.stdout[-2000:]}\n{p.stderr[-4000:]}')

def page_text():
    """Per-page text of the bill (acronym lookup in scripts/dims.py)."""
    db = duckdb.connect(os.path.join(DATA, 'cr638_pages.duckdb'))
    db.sql("create or replace table pages (pdf varchar, page int, text varchar)")
    db.executemany("insert into pages values (?, ?, ?)", [('CR638', i, p.get_text()) for i, p in enumerate(pymupdf.open(PDF), 1)])
    db.close()

if __name__ == '__main__':
    if not os.path.exists(PDF): sys.exit(f'missing {PDF} - see inputs/SOURCES.md')
    if sha256(PDF) != PDF_SHA256: sys.exit(f'{PDF} is not the expected Committee Report 638 (SHA-256 mismatch)')
    os.makedirs(os.path.join(DATA, 'gab'), exist_ok=True)
    step('gab_toc.py'); step('parse_gab_pap.py'); step('parse_gab_projects.py')
    depts = []
    for r in csv.DictReader(open(os.path.join(DATA, 'gab', 'toc_A.csv'), encoding='utf-8')):
        if r['kind'] == 'dept' and r['dept'] not in depts: depts.append(r['dept'])
    for d in depts[:depts.index(LAST_REGULAR_DEPT) + 1]:
        step('parse_gab_suc.py', 'A', 'B') if d == SUC else step('gab_tree.py', d, 'A', 'B')
    step('parse_gab_dpwh.py'); step('parse_gab_annex.py'); step('parse_gab_hfep.py'); step('parse_gab_sbdp.py'); step('parse_gab_provisions.py')
    page_text()
    for f in os.listdir(os.path.join(ROOT, 'curated')): shutil.copy(os.path.join(ROOT, 'curated', f), DATA)
    print('pipeline done ->', DATA)
