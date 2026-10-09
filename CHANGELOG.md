# Changelog

## Unreleased — 2026-10-09

**Three stages.** The House's 3rd-reading text (HB 10858 "FOR 3RD READING", Volumes I-A, I-B, I-C, II, 8 Oct 2026) is added as a
stage, and the stage names now say what each document is:

| stage | document | was |
|---|---|---|
| `GAB_FILED` | CR 638 copy A, as filed | unchanged |
| `GAB_2R` | CR 638 copy B, 2nd reading (its print stamp says `[3RD READING]`) | **`GAB_3R` in v0.1.0** |
| `GAB_3R` | the four 3rd-reading volumes | new |

**Breaking:** rows labelled `GAB_3R` in v0.1.0 are `GAB_2R` now. `appropriations_compared` and `special_provisions_compared` are one
row per line × `comparison` (`GAB_FILED_to_GAB_2R`, `GAB_2R_to_GAB_3R`, `GAB_FILED_to_GAB_3R`); their `_A` / `_B` columns are now
`_from` / `_to`, with `stage_from` / `stage_to`. Every page reference gains `pdf_file` (CR00638.pdf or the volume), and `pdf_page` is
the page in that file.

- 2nd → 3rd reading, in full: DPWH moves ₱134M from Right-of-Way payments (Central Office) to five new Metro Manila 3rd District
  Engineering Office projects (flood control +₱68M, access roads +₱66M); DOTr's ₱500M Service Contracting Program becomes ₱250M MOOE +
  ₱250M capital outlay, with a new provision clause (battery-electric passenger vessels); DOH's MAIFIP line and provision become the
  Medical Assistance Program (MAP), same ₱48.2 bn; NEA gets a new provision, Expanded Sitio Electrification Activities. Totals unchanged.
- Special-purpose funds parsed (back matter): Contingent Fund, Miscellaneous Personnel Benefits Fund, NDRRM Fund, Pension and
  Gratuity Fund, Revised AFP Modernization Program are in `appropriations` (UACS 01-401…01-416 from NEP 2027). Filing → 2nd reading
  cut Pension by ₱10.0 bn and NDRRMF by ₱9.5 bn — the ₱17.9 bn the departments gained. Unprogrammed Appropriations (₱111.98 bn,
  unchanged; four purposes) is in `appropriations` too, with `unprogrammed = 1` (new column, also in `appropriations_compared`) and
  ids from the bill's numeral (`dept_id` XLIII, `agency_id` XLIII-001, `nep_match` not_in_nep) because the NEP has no code for it.
  Filter `unprogrammed = 0` to compare with the NEP.
- Department codes follow the NEP exactly: the NEP files the special-purpose funds under department `01` ("New General
  Appropriations"), the same code as Congress, so they keep `01-4xx` here too. Group by `agencies.gab_dept_code` to separate Congress
  (I) from the funds (XXXVIII–XLII); README rule 7.
- `docs/BUDGET_CHANGES.md` has As filed / 2nd reading / 3rd reading columns and generated notes on every 2nd → 3rd change.
- `docs/EXTERNAL_VALIDATION.md` compares the external extractions with `GAB_2R` (their DPWH rows match the 2nd-reading text).
- Inputs: the four volumes (Google Drive folder in `inputs/SOURCES.md`, SHA-256 checked, downloaded by `scripts/fetch_inputs.py`).

## 0.1.0 — 2026-10-09 (pre-release, for BetterGov review)

First build. Departments I–XXXV of HB 10858 (FY2027 GAB), both stages (`GAB_FILED`, `GAB_3R`).

- `appropriations.csv`: 37,797 lines (18,810 filed = ₱3,858,184,415,000; 18,987 3rd reading = ₱3,876,048,999,000).
- `appropriations_compared.csv`: 19,081 lines — 17,837 unchanged, 879 amount changed, 271 added, 94 removed; NAPC and PCUP are
  paired across their move from DSWD to Other Executive Offices.
- `declared_totals.csv`: 28,933 printed totals; 28,923 tie, 10 are page-checked misprints in the bill.
- UACS codes for every agency (316) and 99.9% of filed lines (BetterGov NEP 2027); PSGC 2Q-2026 places; drill-downs for DPWH,
  FMR, HFEP, NIA, SBDP.
- `special_provisions.csv` / `special_provisions_compared.csv`: 857 / 877 provisions with full text (incl. 121 / 124 from
  back-matter funds), compared across stages: 625 unchanged, 183 reworded, 45 renumbered, 24 added, 4 removed.
- Every input is now scripted from the PDF: the DPWH locally-funded list (now ties to its printed heading to the peso; its first
  page's Convergence port rows, ₱259M / ₱120M, moved to the DPWH projects) and the SBDP barangay list (1,948 per copy, columns
  re-split; junk page-header rows removed) replace earlier frozen extracts.
- Not yet: back matter XXXVI–XLIII tables.
