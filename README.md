# GAB FY2027 dataset — the Philippine House budget bill as flat tables

Every appropriation printed in **House Bill No. 10858**, the FY2027 General Appropriations Bill, at three stages — as **filed**,
on **2nd reading**, and as submitted for **3rd reading** — rebuilt from the bill PDFs into flat, joinable tables:

- **One row per appropriation line** with its department, agency, program, activity, region, office and PS / MOOE / FinEx / CO amounts.
- **Official codes** (UACS department, agency, program and region) that join directly to [BetterGov's](https://bettergov.ph) `nep-2027` and `gaa` datasets.
- **Map-ready places**: PSA PSGC codes, legislative districts, and an honest `geo_level` for money that has no place.
- **Every printed total**, kept separately so each claim in the bill can be checked against its lines.
- **Itemized project lists** (DPWH projects, farm-to-market roads, health facilities, irrigation, barangays) linked to the lines they break down.

> **Status: pre-release (v0.1.0 + unreleased changes), for review by BetterGov before announcement.** Coverage is departments
> I–XXXV of the bill (₱3.86 trillion as filed), five special-purpose funds (Contingent, Miscellaneous Personnel Benefits, NDRRM,
> Pension and Gratuity, AFP Modernization; ₱345 bn as filed) and Unprogrammed Appropriations (₱112 bn, `unprogrammed = 1`).
> Budgetary support to GOCCs (XXXVI) and allocations to LGUs (XXXVII) are not parsed yet. See
> [What is not in here yet](#what-is-not-in-here-yet).

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
select dept_printed_to as department, sum(delta) as change_php
from appropriations_compared where comparison = 'GAB_FILED_to_GAB_3R'
group by 1 order by abs(sum(delta)) desc;
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
| `appropriations_compared.csv` | appropriation line × comparison (filed→2R, 2R→3R, filed→3R) | what the House changed at each step (status, delta, flags, relabel pairing) |
| `declared_totals.csv` | printed total × stage | checking the bill's own arithmetic (`ties`) |
| `object_of_expenditure.csv` | object line × stage | the same money by Basic Salary, Travel, … |
| `special_provisions.csv` | Special Provision × stage | the legal conditions attached to each agency's money (full text) |
| `special_provisions_compared.csv` | Special Provision × comparison | provisions added, removed or reworded at each step (word-level counts) |
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
2. **Pick one stage.** Every amount table carries `GAB_FILED`, `GAB_2R` and `GAB_3R`; filter on `stage`. The compared tables
   carry three comparisons; filter on `comparison`.
3. **"Central Office" is not Metro Manila.** 42% of the money is an agency's national headquarters line, printed under NCR.
   It has `geo_level = central_office` and no place code — keep it off maps (or show it separately). National lump sums with
   no region (`geo_level = national`) are another 15%.
4. **A changed line is not automatically an insertion.** `added` / `removed` lines with a `possible_relabel` are probably one line
   renamed or re-nested; check before calling either a cut or a new item. `big_increase` / `big_decrease` thresholds (≥20% and
   ≥₱50M) are a starting guess, not an editorial standard.
5. **Unprogrammed is not programmed money.** Rows with `unprogrammed = 1` (Unprogrammed Appropriations, ₱112 bn) are standby
   authority, released only if revenues exceed targets or for specific foreign loans. The NEP's ₱4,494 bn "new appropriations"
   excludes them: filter `unprogrammed = 0` when comparing with the NEP or reporting programmed spending. Its ids (`XLIII`,
   `XLIII-001`) are the bill's numeral, not UACS codes — the NEP has none for it.
6. **"Division Office - Proper" (DepEd) is many schools.** It is the division total minus the schools the bill lists by name —
   often 100+ schools in one row.
7. **Department `01` is Congress *and* most special-purpose funds**, exactly as in the NEP: the funds keep their NEP codes
   (`01-401` NDRRM Fund, `01-402` Contingent, `01-406` MPBF, `01-407` Pension and Gratuity, `01-416` AFP Modernization).
   Grouping by `dept_id` therefore adds the funds to Congress; group by `agencies.gab_dept_code` (I = Congress, XXXVIII–XLII =
   the funds) to keep them apart.
8. **This is the House bill, not the law.** The Senate version, the bicameral report and the enacted GAA 2027 come later.
   A House change is `GAB_3R` vs `GAB_FILED` (`GAB_2R` shows which step made it); a GAA-vs-NEP difference mixes House, Senate
   and bicam changes.

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

Generated on every build in [release/CHECKS.md](release/CHECKS.md). Current build (three stages):

- Every agency's lines sum to its printed appropriation in 962 of 963 agency × stage pairs; all 43,569 printed totals tie except
  11 that are **misprints in the bill itself**, each page-checked and listed in `scripts/curated/known_bill_errors.csv`.
- Rebuilt from its parts (departments + special-purpose funds + unprogrammed), each stage totals ₱4,606,066,495,000, the figure
  the bill's own Summary of New Appropriations prints (`docs/BUDGET_CHANGES.md`).
- `GAB_FILED` = NEP 2027 for all 316 agencies (₱3,858,184,415,000); 99.9% of lines matched to an NEP line; region agrees on all
  16,628 matched lines that print one; 30 hand-checked tie-broken matches all correct.
- Drill-downs: DPWH projects cover 99.6–99.7% of their programs (4 of 5 programs to the peso), its locally-funded list and
  farm-to-market roads 100% (every region), in every stage.
- Special Provisions: 857 (filed) / 877 (2nd reading) / 878 (3rd reading), every agency's numbering continuous except 6 gaps that
  are printed that way (the missing number does not occur on the page). Filed → 3rd: 622 unchanged, 182 reworded, 48 renumbered,
  26 added, 5 removed; 2nd → 3rd: 1 reworded, 2 added, 1 removed, 3 renumbered.
- External cross-check (`docs/EXTERNAL_VALIDATION.md`): two independent extractions of the filed and 2nd-reading bills agree on all
  35 department totals and all 5 parsed special-purpose funds.
- Two builds from the same inputs are byte-identical.

## What is not in here yet

- **Back matter XXXVI–XXXVII**: Budgetary Support to Government Corporations (₱182.0B filed) and Allocations to LGUs (₱109.1B
  filed), including the parents of the NIA irrigation and SBDP barangay lists.
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
