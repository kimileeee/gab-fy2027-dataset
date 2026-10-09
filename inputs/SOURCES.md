# Sources

Large source files are not committed (GitHub's 100 MB limit, and they are other publishers' files). `python scripts/fetch_inputs.py`
downloads what it can and checks every file's SHA-256 — a different file would silently change the release.

| file | what | where | SHA-256 |
|---|---|---|---|
| `pipeline/raw/hb10858/CR00638.pdf` (104 MB, 7,408 pp) | House Committee Report No. 638 on HB 10858: pp 12–3535 = the bill as filed (`[1ST READING]` footer, = `GAB_FILED`), pp 3536–7408 = the bill on 2nd reading (= `GAB_2R`; its print-shop stamp reads `[3RD READING]`, dated 1 Oct 2026, but this is the 2nd-reading text — the 3rd-reading text is the four volumes below). Text layer present; pp 1–11 are image-only front matter. | House of Representatives: https://docs.congress.hrep.online/legisdocs/first_20/CR00638.pdf (downloaded automatically) | `3242a248d1436be5d15c2bd81628c1c9691e0b796fc4a58552d063f18177b6b0` |
| `pipeline/raw/hb10858_3r/HB10858_3R_VOL_I-A.pdf` (17.7 MB, 1,339 pp) | HB 10858 "FOR 3RD READING", Volume I-A (= `GAB_3R`; 8 Oct 2026, for House approval). The four volumes paginate exactly like CR 638 pp 3536–7408. | Google Drive folder "2027 House GAB - 3rd Reading": https://drive.google.com/drive/folders/1gs7q6NIw3E13JsWt190MLZmqzwvRxHB0 (downloaded automatically; saved under this name) | `79f56b8d577246342b59cc996afdd707523268f0bde10378e3c1b5ef844451fd` |
| `pipeline/raw/hb10858_3r/HB10858_3R_VOL_I-B.pdf` (14.9 MB, 982 pp) | HB 10858 "FOR 3RD READING", Volume I-B (= `GAB_3R`; 8 Oct 2026, for House approval). The four volumes paginate exactly like CR 638 pp 3536–7408. | Google Drive folder "2027 House GAB - 3rd Reading": https://drive.google.com/drive/folders/1gs7q6NIw3E13JsWt190MLZmqzwvRxHB0 (downloaded automatically; saved under this name) | `4cc0f17e472d1af380ea6d3972561f6bb241137826fd85ed7e7e70bcd92986b9` |
| `pipeline/raw/hb10858_3r/HB10858_3R_VOL_I-C.pdf` (9.2 MB, 942 pp) | HB 10858 "FOR 3RD READING", Volume I-C (= `GAB_3R`; 8 Oct 2026, for House approval). The four volumes paginate exactly like CR 638 pp 3536–7408. | Google Drive folder "2027 House GAB - 3rd Reading": https://drive.google.com/drive/folders/1gs7q6NIw3E13JsWt190MLZmqzwvRxHB0 (downloaded automatically; saved under this name) | `48cb7a11e391bd4da89d4f47cf39a2eba8fe9bfe636dba101c8284b224ac1b1b` |
| `pipeline/raw/hb10858_3r/HB10858_3R_VOL_II.pdf` (10.5 MB, 610 pp) | HB 10858 "FOR 3RD READING", Volume II (= `GAB_3R`; 8 Oct 2026, for House approval). The four volumes paginate exactly like CR 638 pp 3536–7408. | Google Drive folder "2027 House GAB - 3rd Reading": https://drive.google.com/drive/folders/1gs7q6NIw3E13JsWt190MLZmqzwvRxHB0 (downloaded automatically; saved under this name) | `376ddaf7291e2beaa839b606c77e07ed82c49ec7eca7276c68e86959c1e80750` |
| `inputs/NEP-FY2027.csv` (244 MB) | BetterGov NEP 2027: UACS line items (codes, amounts in ₱ thousands). CC0. | https://huggingface.co/datasets/bettergovph/nep-2027 (downloaded automatically) | `5236dba760e9cd5628ed9b48cd8930e18dc2afe5ae4cbd65c524b8c60a259874` |
| `inputs/PSGC-2Q-2026-Publication-Datafile.xlsx` (3 MB) | PSA Philippine Standard Geographic Code, 2nd Quarter 2026 (published 30 June 2026). | https://psa.gov.ph/classification/psgc (browser check; download by hand) | `31892bc2bdde3ea0682562d9412b5bab4d45a0be5e5a5b4f6c9d7714b94bca5d` |

## Curated tables (`pipeline/curated/`, committed)

| file | what | provenance |
|---|---|---|
| `regions.csv`, `localities.csv`, `districts.csv` | short region ids, provinces/cities, the 254 House legislative districts | ph-pork-graph `data/` (Wikipedia + OpenHalalan, Oct 2026); localities are matched to PSGC by name in the build |
| `deo_district_map.csv` | DPWH District Engineering Office → legislative district (`exact`) or province/city (`locality`) | ph-pork-graph `data/`, reviewed; `not-a-deo` / `unmatched` offices are not placed below region |
| `scripts/curated/known_bill_errors.csv` | page-checked misprints in the bill that the release explains instead of "fixing" | hand-curated |
