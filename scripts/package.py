"""Phase 8: package release/ for sharing. Run after scripts/build.py: python scripts/package.py

Writes, from the release CSVs and scripts/schema.py: release/parquet/<table>.parquet (typed), release/master.parquet + master.csv
(appropriations with every dimension joined in), release/gab_fy2027.duckdb (all tables + a `master` view), release/datapackage.json
(Frictionless Data Package) and release/DATA_DICTIONARY.md. Validates every CSV against the schema first and exits non-zero on any
problem: header = schema fields in order, typed columns parse, primary keys unique and non-null, foreign keys resolve."""
import csv, json, os, sys
import duckdb
from schema import TABLES

VERSION, RELEASED = '0.1.0', '2026-10-09'
HERE = os.path.dirname(os.path.abspath(__file__))
REL = os.path.join(HERE, '..', 'release')
SQL_TYPE = {'string': 'VARCHAR', 'integer': 'BIGINT', 'number': 'DOUBLE'}
SOURCES = [
    dict(title='House of Representatives, Committee Report No. 638 on House Bill No. 10858 (FY2027 General Appropriations Bill): copy A as filed (GAB_FILED), copy B 2nd reading (GAB_2R); CR00638.pdf, SHA-256 3242a248d1436be5d15c2bd81628c1c9691e0b796fc4a58552d063f18177b6b0'),
    dict(title='House of Representatives, HB 10858 FOR 3RD READING, Volumes I-A, I-B, I-C and II (8 Oct 2026; GAB_3R); SHA-256 in inputs/SOURCES.md', path='https://drive.google.com/drive/folders/1gs7q6NIw3E13JsWt190MLZmqzwvRxHB0'),
    dict(title='BetterGov.ph, NEP 2027 (bettergovph/nep-2027, CC0): agency, program and operating-unit codes', path='https://huggingface.co/datasets/bettergovph/nep-2027'),
    dict(title='Philippine Statistics Authority, PSGC 2nd Quarter 2026 publication datafile', path='https://psa.gov.ph/classification/psgc'),
]
MASTER = """
select a.*, d.acronym as dept_acronym, d.name_official as dept_name_official, g.acronym as agency_acronym,
       g.name_official as agency_name_official, g.suc_region_group, r.name as region_name,
       coalesce(l.name, case when a.geo_level = 'region' then r.name end) as place_name, p.name as province_name, di.name as district_name
from appropriations a
left join departments d on d.dept_id = a.dept_id
left join agencies g on g.agency_id = a.agency_id
left join regions r on r.region_code = a.region_code
left join localities l on l.psgc_code = a.psgc_code
left join localities p on p.psgc_code = a.province_psgc
left join districts di on di.district_id = a.district_id
order by a.stage, a.agency_id, a.pdf_file, a.pdf_page, a.appropriation_id"""

def csv_path(t): return os.path.join(REL, f'{t}.csv').replace(os.sep, '/')

def load(con, t, spec):
    sel = ', '.join(f"""try_cast(nullif("{f}", '') as {SQL_TYPE[ty]}) as "{f}" """ for f, ty, _ in spec['fields'])   # bad values become NULL here; validate() reports them
    con.sql(f"""create or replace table "{t}" as select {sel}
                from read_csv('{csv_path(t)}', header = true, all_varchar = true, quote = '"', escape = '"')""")

def validate(con):
    problems = []
    for t, spec in TABLES.items():
        with open(csv_path(t), encoding='utf-8-sig') as f: header = next(csv.reader(f))
        names = [f for f, _, _ in spec['fields']]
        if header != names: problems.append(f'{t}: header {header} != schema {names}'); continue
        raw = f"read_csv('{csv_path(t)}', header = true, all_varchar = true, quote = '\"', escape = '\"')"
        for f, ty, _ in spec['fields']:
            if ty != 'string':
                n = con.sql(f"""select count(*) from {raw} where nullif("{f}", '') is not null and try_cast("{f}" as {SQL_TYPE[ty]}) is null""").fetchone()[0]
                if n: problems.append(f'{t}.{f}: {n} values are not {ty}')
        if spec['primary_key']:
            k = ', '.join(f'"{c}"' for c in spec['primary_key'])
            n = con.sql(f'select count(*) - count(distinct ({k})) from "{t}"').fetchone()[0]
            nul = con.sql(f'select count(*) from "{t}" where ' + ' or '.join(f'"{c}" is null' for c in spec['primary_key'])).fetchone()[0]
            if n or nul: problems.append(f'{t}: primary key {spec["primary_key"]} has {n} duplicates, {nul} nulls')
        for f, ref, rf in spec['foreign_keys']:
            n = con.sql(f'select count(*) from "{t}" c where c."{f}" is not null and c."{f}" not in (select "{rf}" from "{ref}")').fetchone()[0]
            if n: problems.append(f'{t}.{f}: {n} values missing from {ref}.{rf}')
    return problems

def datapackage(con):
    res = []
    for t, spec in TABLES.items():
        schema = dict(fields=[dict(name=f, type=ty, description=d) for f, ty, d in spec['fields']], missingValues=[''])
        if spec['primary_key']: schema['primaryKey'] = spec['primary_key']
        if spec['foreign_keys']: schema['foreignKeys'] = [dict(fields=f, reference=dict(resource=r, fields=rf)) for f, r, rf in spec['foreign_keys']]
        res.append(dict(name=t, title=spec['title'], description=spec['description'], path=f'{t}.csv', profile='tabular-data-resource',
                        format='csv', mediatype='text/csv', encoding='utf-8-sig', schema=schema))
    pkg = dict(profile='tabular-data-package', name='gab-fy2027', version=VERSION, created=RELEASED,
               title='Philippine FY2027 General Appropriations Bill (House, HB 10858) as flat tables',
               description='Every appropriation the House bill prints, as filed and on 3rd reading, as flat joinable tables with UACS codes '
                           '(compatible with BetterGov\'s NEP/GAA datasets), PSGC places, printed totals for verification, and itemized drill-downs.',
               licenses=[dict(name='CC0-1.0', title='Creative Commons Zero v1.0 Universal', path='https://creativecommons.org/publicdomain/zero/1.0/')],
               sources=SOURCES, resources=res)
    with open(os.path.join(REL, 'datapackage.json'), 'w', encoding='utf-8', newline='\n') as f: json.dump(pkg, f, indent=2, ensure_ascii=False); f.write('\n')

def dictionary(con):
    L = ['# Data dictionary', '', f'Version {VERSION} ({RELEASED}). Generated by scripts/package.py from scripts/schema.py; do not edit.', '',
         'Amounts are integer pesos. Blank = not printed / not applicable. Files are UTF-8 with a byte-order mark (opens correctly in Excel).', '']
    for t, spec in TABLES.items():
        n = con.sql(f'select count(*) from "{t}"').fetchone()[0]
        L += [f'## `{t}.csv` — {spec["title"]}', '', spec['description'], '', f'Rows: {n:,}.' +
              (f' Primary key: `{", ".join(spec["primary_key"])}`.' if spec['primary_key'] else '') +
              ''.join(f' `{f}` → `{r}.{rf}`.' for f, r, rf in spec['foreign_keys']), '', '| column | type | description |', '|---|---|---|']
        L += [f'| `{f}` | {ty} | {d.replace("|", "/")} |' for f, ty, d in spec['fields']] + ['']
    L += ['## `master.parquet` / `master.csv`', '', 'appropriations.csv with the dimensions joined in: dept_acronym, dept_name_official, agency_acronym, '
          'agency_name_official, suc_region_group, region_name, place_name, province_name, district_name. One row per appropriation x stage.', '']
    open(os.path.join(REL, 'DATA_DICTIONARY.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(L))

def main():
    con = duckdb.connect(); con.sql('set threads = 1')            # single-threaded: deterministic row order in every output
    for t, spec in TABLES.items(): load(con, t, spec)
    problems = validate(con)
    for p in problems: print('PROBLEM:', p)
    if problems: sys.exit(f'{len(problems)} validation problems - nothing packaged')
    os.makedirs(os.path.join(REL, 'parquet'), exist_ok=True)
    for t in TABLES: con.sql(f"""copy "{t}" to '{os.path.join(REL, 'parquet', t + '.parquet').replace(os.sep, '/')}' (format parquet, compression zstd)""")
    con.sql(f'create or replace table master as {MASTER}')
    con.sql(f"""copy master to '{os.path.join(REL, 'master.parquet').replace(os.sep, '/')}' (format parquet, compression zstd)""")
    rel = con.sql('select * from master')
    with open(os.path.join(REL, 'master.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(rel.columns); w.writerows(['' if v is None else v for v in row] for row in rel.fetchall())
    mb = os.path.getsize(os.path.join(REL, 'master.csv')) / 1e6
    if mb > 95: os.remove(os.path.join(REL, 'master.csv')); print(f'master.csv {mb:.0f} MB > GitHub limit: Parquet only')
    db = os.path.join(REL, 'gab_fy2027.duckdb')
    if os.path.exists(db): os.remove(db)
    out = duckdb.connect(db)
    for t in TABLES: out.sql(f"""create table "{t}" as select * from read_parquet('{os.path.join(REL, 'parquet', t + '.parquet').replace(os.sep, '/')}')""")
    out.sql(f'create view master as {MASTER}'); out.close()
    datapackage(con); dictionary(con)
    print(f'packaged {len(TABLES)} tables + master ({mb:.0f} MB csv) -> {REL}')

if __name__ == '__main__':
    main()
