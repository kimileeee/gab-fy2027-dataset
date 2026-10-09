# PH budget dataset (GAB FY2027)

The Philippine national budget as printed in each legislative document, rebuilt as flat, joinable tables for analysts and
as a derived graph for relationship questions.

## Documents and stages

**NEP** (National Expenditure Program):
The executive's budget proposal, prepared by DBM and submitted to Congress. BetterGov publishes it as UACS line items.
_Avoid_: proposal, President's budget

**GAB** (General Appropriations Bill):
Congress's version of the budget bill. Here, always the House bill HB 10858 as printed in Committee Report 638.
_Avoid_: HGAB (use GAB + stage), House budget

**GAA** (General Appropriations Act):
The enacted budget law after bicam ratification and presidential signature/veto.
_Avoid_: budget law, enacted GAB

**Stage**:
Which point in the budget process a figure comes from: `NEP` → `GAB_FILED` → `GAB_2R` → `GAB_3R` → (Senate, bicam, `GAA`).
_Avoid_: version, copy (outside parser internals)

**Copy A / B / C**:
Parser-internal names for the three printings: A = `GAB_FILED` (CR 638 first half, as filed), B = `GAB_2R` (CR 638 second half,
2nd reading — its print stamp says [3RD READING]), C = `GAB_3R` (the four HB 10858 FOR 3RD READING volumes, 8 Oct 2026).
_Avoid_: using A/B in published tables — use the stage name

## Budget structure

**Department**:
A Roman-numeral heading in the GAB; corresponds to a UACS department code.
_Avoid_: ministry

**Agency**:
A unit under a department that receives its own appropriation (lettered in the GAB; 3-digit UACS agency code). Each state university or college is its own agency.
_Avoid_: office (an office is below an agency)

**SUC region group**:
The lettered regional grouping (A–S) under State Universities and Colleges that sits between department and institution. Presentation only; it is not an agency.

**Category**:
The top tier of an agency's program table: General Administration and Support, Support to Operations, Operations, or Projects (Locally-Funded / Foreign-Assisted).

**PAP** (Program, Activity, Project):
A funded line in the program table; its official identifier is the UACS PREXC FPAP code.

**Operating unit**:
The office the money is released to (Central Office, Regional Office, DEO, Division, school, hospital, campus).
_Avoid_: implementing office (unless quoting the bill)

**Division Office - Proper**:
A DepEd line covering the schools division office plus every school in that division the bill does not list by name; its amount is the division total minus the itemized schools.

**Central Office**:
An agency's national headquarters operating unit. Printed under NCR but means national, not Metro Manila, spending.

**Expense class**:
PS, MOOE, FinEx or CO — the four object-of-expenditure classes (UACS codes 1, 2, 3, 6).

## Dataset

**Leaf**:
A printed amount row with nothing printed beneath it in the program table; the unit of the fact table. Leaves sum to the agency total.
_Avoid_: item (the parser's `role=item` is not always a leaf)

**Declared total**:
A printed group, sub-total, total or lead amount; the bill's own claim about the sum of the rows beneath it.
_Avoid_: subtotal (as a generic term)

**Tie-out**:
The check that a declared total equals the sum of its leaves.

**Drill-down**:
A finer itemization the bill prints elsewhere for one or more leaves (DPWH Vol I-C projects, FMR/NIA/HFEP/SBDP annexes), linked to its parent leaf and never summed together with it.

**Coverage**:
Drill-down sum divided by the parent leaf amount.

**PSGC** (Philippine Standard Geographic Code):
PSA's 10-digit code for every region, province, city, municipality and barangay; the join key for places and maps. Its 2-digit region prefix is the UACS region id.
_Avoid_: slug ids as join keys

**Geo level**:
The finest place a row's money can honestly be attributed to: national, central office, region, province, city/municipality, district, or barangay.
