# pipeline/ — from the bill PDF to parsed tables

`python pipeline/run.py` rebuilds `pipeline/data/` from `raw/hb10858/CR00638.pdf` and the four `raw/hb10858_3r/` volumes (SHA-256
checked first). Every output exists per parser copy: `_A` = CR 638 first half (`GAB_FILED`), `_B` = CR 638 second half (`GAB_2R`), `_C` =
the 3rd-reading volumes (`GAB_3R`). `build/gab_pdf.py` appends the volumes after CR 638's 7,408 pages in memory, so copy C's page
numbers there are copy B's + 3,873 (the volumes paginate exactly like copy B); the release converts them to file + page. The scripts in `build/`
are a **pinned snapshot** of the parsers in ph-pork-graph's `build/` (taken 2026-10-09, after the phase-1 fixes), unchanged: they
run from `build/` and write `../data/`, the layout they were written for. Verified: run from the PDF, they reproduce
ph-pork-graph's parsed output byte for byte (632 agency trees, table of contents, DPWH and its locally-funded list, FMR, NIA, HFEP,
SBDP, Special Provisions, PAP and project files; since 2026-10-09 also copy C, and the special-purpose funds XXXVIII–XLIII via
`parse_gab_backmatter.py`).

| step | script | output (`data/`) |
|---|---|---|
| table of contents (names, codes, SUC groups) | `gab_toc.py` | `gab/toc_{A,B}.csv` |
| every program-table line | `parse_gab_pap.py` (+ `gab_cols.py`, `parse_gab_annex.py` helpers) | `gab_pap_{A,B}.csv` |
| in-body project blocks | `parse_gab_projects.py` | `gab_projects_{A,B}.csv`, `gab_project_regions_{A,B}.csv` |
| printed hierarchy per agency, departments I–XXXV | `gab_tree.py <DEPT> A B` | `gab/<dept>/<agency>/pap_{A,B}.csv`, `projects_{A,B}.csv` |
| State Universities and Colleges (Department → Region → Institution) | `parse_gab_suc.py A B` | same, plus `general_summary_{A,B}.csv` |
| DPWH Vol I-C projects and the locally-funded list | `parse_gab_dpwh.py` (+ `gab_pdf.py`) | `gab_dpwh_rows_{A,B}.csv`, `gab_dpwh_tail_rows_{A,B}.csv` |
| FMR and NIA annexes | `parse_gab_annex.py` | `gab_annex_{fmr,nia}_{A,B}.csv` |
| HFEP annex | `parse_gab_hfep.py` | `gab_annex_hfep_{A,B}.csv` |
| SBDP barangay list | `parse_gab_sbdp.py` | `gab_annex_sbdp_{A,B}.csv` |
| Special Provisions (word-coordinate reader; added 2026-10-09) | `parse_gab_provisions.py` | `gab_provisions_{A,B}.csv` |
| page text (acronyms) | `run.py` | `cr638_pages.duckdb` |

`curated/` is copied into `data/` last (see `inputs/SOURCES.md`). Parser development continues in ph-pork-graph; to update the
snapshot, copy the scripts over, re-run, and diff `data/` against the previous run — every difference must be explained in
CHANGELOG.md. Back matter (XXXVI–XLIII) has no parser yet.
