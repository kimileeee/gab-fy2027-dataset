# Changelog

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
