# GAB FY2027 dataset — the Philippine House budget bill as flat tables

Every appropriation printed in **House Bill No. 10858**, the FY2027 General Appropriations Bill, as **filed** and as passed on
**3rd reading**, rebuilt from the bill PDF into flat, joinable tables:

- **One row per appropriation line** with its department, agency, program, activity, region, office and PS / MOOE / FinEx / CO amounts.
- **Official codes** (UACS department, agency, program and region) that join directly to [BetterGov's](https://bettergov.ph) `nep-2027` and `gaa` datasets.
- **Map-ready places**: PSA PSGC codes, legislative districts, and an honest `geo_level` for money that has no place.
- **Every printed total**, kept separately so each claim in the bill can be checked against its lines.
- **Itemized project lists** (DPWH projects, farm-to-market roads, health facilities, irrigation, barangays) linked to the lines they break down.

> **Status: pre-release (v0.1.0), for review by BetterGov before announcement.** Coverage is departments I–XXXV of the bill
> (₱3.86 trillion as filed); the back-matter funds XXXVI–XLIII (budgetary support to GOCCs, allocations to LGUs, special purpose
> funds, unprogrammed appropriations) are not parsed yet. See [What is not in here yet](#what-is-not-in-here-yet).

## Quick start

| you use | open |
|---|---|
| Excel / Google Sheets | `release/master.csv` (one sheet with everything), or the table CSVs |
| pandas / Polars / R | `release/parquet/*.parquet` or `release/master.parquet` |
| SQL | `release/gab_fy2027.duckdb` (all tables + a `master` view) |
| validators / data portals | `release/datapackage.json` ([Frictionless Data Package](https://datapackage.org)) |

Column-by-column documentation: **[release/DATA_DICTIONARY.md](release/DATA_DICTIONARY.md)**. Terms: [CONTEXT.md](CONTEXT.md).

```sql
-- DuckDB: what changed between filing and 3rd reading, by department
select dept_printed_B as department, sum(delta) as change_php
from appropriations_compared group by 1 order by abs(sum(delta)) desc;
```

```python
import pandas as pd
m = pd.read_parquet("release/master.parquet")
m[m.stage == "GAB_3R"].groupby("dept_acronym").amount.sum().sort_values()
```

## The tables

| file | one row per | use it for |
|---|---|---|
| `appropriations.csv` | appropriation line × stage | **the fact table**: sums, filters, pivots |
| `appropriations_compared.csv` | appropriation line, both stages side by side | what the House changed (status, delta, flags, relabel pairing) |
| `declared_totals.csv` | printed total × stage | checking the bill's own arithmetic (`ties`) |
| `object_of_expenditure.csv` | object line × stage | the same money by Basic Salary, Travel, … |
| `special_provisions.csv` | Special Provision × stage | the legal conditions attached to each agency's money (full text) |
| `special_provisions_compared.csv` | Special Provision, both stages | provisions added, removed or reworded at 3rd reading (word-level counts) |
| `drilldown_items.csv` | itemized project × stage | DPWH projects, FMR, HFEP, NIA, SBDP |
| `drilldown_coverage.csv` | drill-down group × stage | how much of its parent line a list covers |
| `departments.csv`, `agencies.csv` | department / agency | UACS codes, printed and official names, acronyms (with source) |
| `regions.csv`, `localities.csv`, `districts.csv` | place | PSGC codes, population 2024, legislative districts |
| `operating_units.csv` | agency × region × office | how each office was placed on the map |
| `master.csv` / `.parquet` | appropriation line × stage | `appropriations` with all names joined in |

## Read this before you add numbers up

1. **Sum `appropriations`, nothing else.** Its rows (leaves) add up to every printed total. `declared_totals` are the bill's own
   totals *over* those rows; `object_of_expenditure` and `drilldown_items` are *other cuts* of the same money. Adding any two
   double-counts.
2. **Pick one stage.** Every amount table carries both `GAB_FILED` and `GAB_3R`; filter on `stage`.
3. **"Central Office" is not Metro Manila.** 42% of the money is an agency's national headquarters line, printed under NCR.
   It has `geo_level = central_office` and no place code — keep it off maps (or show it separately). National lump sums with
   no region (`geo_level = national`) are another 15%.
4. **A changed line is not automatically an insertion.** `added` / `removed` lines with a `possible_relabel` are probably one line
   renamed or re-nested; check before calling either a cut or a new item. `big_increase` / `big_decrease` thresholds (≥20% and
   ≥₱50M) are a starting guess, not an editorial standard.
5. **"Division Office - Proper" (DepEd) is many schools.** It is the division total minus the schools the bill lists by name —
   often 100+ schools in one row.
6. **This is the House bill, not the law.** The Senate version, the bicameral report and the enacted GAA 2027 come later.
   A House change is `GAB_3R` vs `GAB_FILED`; a GAA-vs-NEP difference mixes House, Senate and bicam changes.

## Joining with BetterGov

| this dataset | BetterGov `nep-2027` / `gaa` |
|---|---|
| `dept_id` (`"13"`) | `department` / `DEPARTMENT` |
| `agency_id` (`"13-001"`) | `department` + `agency` |
| `prexc_fpap_id` | `prexc_fpap_id` / `PREXC_FPAP_ID` |
| `region_code` | `uacs_reg_id` / `UACS_REG_ID` |
| `nep_operunit` | `operunit` / `OPERUNIT` |
| `amount` (pesos) | `amt` / `AMT` × 1,000 (BetterGov amounts are in thousands) |
| PS / MOOE / FinEx / CO columns | `uacs_exp_cd` 1 / 2 / 3 / 6 |

BetterGov's rows are finer (one per object code such as Basic Salary): sum them up to (agency, FPAP, region, operating unit)
before comparing. `GAB_FILED` equals the NEP: all 316 agency totals match exactly, and 18,795 of 18,810 lines carry NEP codes.

## How it was checked

Generated on every build in [release/CHECKS.md](release/CHECKS.md). At v0.1.0:

- Every agency's lines sum to its printed appropriation in 631 of 632 agency × stage pairs; all 28,933 printed totals tie except
  10 that are **misprints in the bill itself**, each page-checked and listed in `scripts/curated/known_bill_errors.csv`.
- `GAB_FILED` = NEP 2027 for all 316 agencies (₱3,858,184,415,000); 99.9% of lines matched to an NEP line; region agrees on all
  16,628 matched lines that print one; 30 hand-checked tie-broken matches all correct.
- Drill-downs: DPWH projects cover 99.6% of their programs (4 of 5 programs to the peso), farm-to-market roads 100% in every region.
- Special Provisions: 857 (filed) / 877 (3rd reading), every agency's numbering continuous except 6 gaps that are printed that way
  (the missing number does not occur on the page); 625 unchanged, 183 reworded, 45 renumbered, 24 added, 4 removed.
- Two builds from the same inputs are byte-identical.

## What is not in here yet

- **Back matter XXXVI–XLIII** (≈₱636B of the NEP's ₱4,494B new appropriations), including the parents of the NIA irrigation and
  SBDP barangay lists.
- **Places below region** for ~₱150B of named offices (military units, national hospitals, New Bilibid) and for individual schools
  (placed at their division).
- Senate version, bicameral conference report, GAA 2027.

## Rebuilding it yourself

```bash
pip install -r requirements.txt
python scripts/fetch_inputs.py    # downloads the bill PDF and BetterGov NEP 2027, points you to the PSGC file; checks SHA-256
python pipeline/run.py            # PDF -> parsed tables (pipeline/data/), ~3 min
python scripts/build.py           # -> release/*.csv + CHECKS.md
python scripts/package.py         # -> Parquet, master, DuckDB, datapackage.json, DATA_DICTIONARY.md (validates first)
```

Sources and hashes: [inputs/SOURCES.md](inputs/SOURCES.md). The parsers in `pipeline/build/` are a pinned snapshot; see
[pipeline/README.md](pipeline/README.md). Design decisions: [docs/adr/](docs/adr/).

## Licence and citation

Data: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain dedication, like BetterGov's datasets). Code: MIT.
See [LICENSE](LICENSE). The bill is a public document of the House of Representatives; PSGC is published by the Philippine
Statistics Authority; NEP codes come from BetterGov's CC0 `nep-2027` dataset.

Suggested citation: *GAB FY2027 dataset (v0.1.0): House Bill No. 10858 as flat tables, derived from House Committee Report No. 638.*
