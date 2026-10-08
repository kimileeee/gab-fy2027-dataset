# Sources

Large source files are not committed (GitHub's 100 MB limit, and they are other publishers' files). `python scripts/fetch_inputs.py`
downloads what it can and checks every file's SHA-256 — a different file would silently change the release.

| file | what | where | SHA-256 |
|---|---|---|---|
| `pipeline/raw/hb10858/CR00638.pdf` (104 MB, 7,408 pp) | House Committee Report No. 638 on HB 10858: pp 12–3535 = the bill as filed (`[1ST READING]` footer, = `GAB_FILED`), pp 3536–7408 = the bill on 3rd reading (`[3RD READING]`, = `GAB_3R`). Text layer present; pp 1–11 are image-only front matter. | House of Representatives: https://docs.congress.hrep.online/legisdocs/first_20/CR00638.pdf (downloaded automatically) | `3242a248d1436be5d15c2bd81628c1c9691e0b796fc4a58552d063f18177b6b0` |
| `inputs/NEP-FY2027.csv` (244 MB) | BetterGov NEP 2027: UACS line items (codes, amounts in ₱ thousands). CC0. | https://huggingface.co/datasets/bettergovph/nep-2027 (downloaded automatically) | `5236dba760e9cd5628ed9b48cd8930e18dc2afe5ae4cbd65c524b8c60a259874` |
| `inputs/PSGC-2Q-2026-Publication-Datafile.xlsx` (3 MB) | PSA Philippine Standard Geographic Code, 2nd Quarter 2026 (published 30 June 2026). | https://psa.gov.ph/classification/psgc (browser check; download by hand) | `31892bc2bdde3ea0682562d9412b5bab4d45a0be5e5a5b4f6c9d7714b94bca5d` |

## Curated tables (`pipeline/curated/`, committed)

| file | what | provenance |
|---|---|---|
| `regions.csv`, `localities.csv`, `districts.csv` | short region ids, provinces/cities, the 254 House legislative districts | ph-pork-graph `data/` (Wikipedia + OpenHalalan, Oct 2026); localities are matched to PSGC by name in the build |
| `deo_district_map.csv` | DPWH District Engineering Office → legislative district (`exact`) or province/city (`locality`) | ph-pork-graph `data/`, reviewed; `not-a-deo` / `unmatched` offices are not placed below region |
| `scripts/curated/known_bill_errors.csv` | page-checked misprints in the bill that the release explains instead of "fixing" | hand-curated |
