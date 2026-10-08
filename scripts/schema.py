"""The data dictionary: one place that describes every release table and column. scripts/package.py turns it into
release/datapackage.json (Frictionless Data Package) and release/DATA_DICTIONARY.md, and validates the CSVs against it."""

# Columns that mean the same thing in every table they appear in: (type, description)
F = {
    'appropriation_id': ('string', 'Stable id of one appropriation line, the same in every stage: hash of UACS agency + the printed hierarchy (normalised) + label + occurrence. Join key across stages and to appropriations_compared.'),
    'stage': ('string', 'Budget document the figure comes from: GAB_FILED = House bill HB 10858 as filed (copy A of Committee Report 638, identical to the NEP as submitted); GAB_3R = the House bill on 3rd reading (copy B).'),
    'fiscal_year': ('integer', 'Fiscal year of the appropriation (2027).'),
    'dept_id': ('string', 'UACS department code (2 digits), the same as `department` in BetterGov\'s gaa / nep-2027 datasets. See departments.csv.'),
    'agency_id': ('string', 'UACS department + agency code, "DD-AAA" (BetterGov `department` + `agency`). Matched to NEP 2027 by the agency\'s exact appropriation. See agencies.csv.'),
    'dept_printed': ('string', 'Department name as printed in the bill (the department this row is printed under in this stage).'),
    'agency_printed': ('string', 'Agency name as printed in the bill\'s Table of Contents.'),
    'category': ('string', 'Top tier of the agency\'s program table: General Administration and Support, Support to Operations, Operations, Locally-Funded Projects, Foreign-Assisted Projects.'),
    'program': ('string', 'PROGRAM heading (upper case in the bill), if any.'),
    'sub_program': ('string', 'SUB-PROGRAM heading, if any.'),
    'pap': ('string', 'Activity or project name (the PAP: program/activity/project line).'),
    'sub_pap': ('string', 'Deeper activity levels below `pap`, joined with " > ", if any.'),
    'funding_source': ('string', 'For foreign-assisted projects: Loan Proceeds or GOP Counterpart (Philippine government share). Blank otherwise.'),
    'region_printed': ('string', 'Region heading as printed above this row (blank = no region printed: a national lump sum).'),
    'region_code': ('string', '2-digit region code, derived from the printed region name (not its numeral, which the bill misprints at least once). Equal to the PSGC region prefix and to BetterGov\'s `uacs_reg_id`: 13 NCR, 14 CAR, 01-12 Regions I-XII, 16 Caraga, 17 MIMAROPA, 18 NIR, 19 BARMM. See regions.csv.'),
    'operating_unit': ('string', 'Office the money is released to, as printed (Central Office, Regional Office, DPWH District Engineering Office, DepEd Division, hospital, campus...).'),
    'sub_unit': ('string', 'Units printed below the operating unit (e.g. a school under a DepEd Division), joined with " > ".'),
    'geo_level': ('string', 'Finest place the money can honestly be attributed to: national (no region printed), central_office (agency HQ: printed under NCR but NOT Metro Manila spending - keep off maps), region, province, city, municipality, district (legislative district, DPWH), barangay (drill-downs only).'),
    'psgc_code': ('string', 'PSA PSGC 10-digit code of that place (PSGC 2Q-2026). Region-level rows carry the region code; blank for national and central_office. See localities.csv / regions.csv.'),
    'province_psgc': ('string', 'PSGC code of the province (or independent city) containing the place, for province-level maps.'),
    'district_id': ('string', 'Legislative district id (districts.csv), for DPWH District Engineering Office rows mapped to exactly one district.'),
    'geo_basis': ('string', 'Which rule placed this row (e.g. "DEO map", "office prefix (Division/PENRO/CENRO/PARO)", "place name in office name", "regional office", "no region printed"). Filter on it to keep only placements you trust.'),
    'drilldown_group_id': ('string', 'Links an appropriation to the itemized list the bill prints for it elsewhere (drilldown_items.csv, drilldown_coverage.csv). Blank for most rows.'),
    'label': ('string', 'This row\'s own printed text.'),
    'ps': ('integer', 'Personnel Services, pesos (blank = none printed).'),
    'mooe': ('integer', 'Maintenance and Other Operating Expenses, pesos.'),
    'finex': ('integer', 'Financial Expenses, pesos.'),
    'co': ('integer', 'Capital Outlays, pesos.'),
    'amount': ('integer', 'Total appropriation of the row, pesos (= ps + mooe + finex + co).'),
    'prexc_fpap_id': ('string', 'UACS PREXC program/activity/project code of the matching NEP 2027 line (BetterGov `prexc_fpap_id`). Join key to BetterGov nep-2027 / gaa.'),
    'nep_match': ('string', 'How the row matched NEP 2027: unique (amount signature unique in the agency), disambiguated (by region + names), residual (the bill line sums all NEP units it does not itemize, e.g. DepEd "Division Office - Proper"), none, no_filed_counterpart (GAB_3R line with no GAB_FILED twin: added or relabelled).'),
    'pdf_page': ('integer', 'Page of CR00638.pdf the row is printed on (1-based PDF page, not the bill\'s printed page number).'),
    'path_printed': ('string', 'The printed hierarchy above this row, " > "-joined, exactly as in the bill (for audit).'),
    'source_row_id': ('string', 'Row id in the parser output (pipeline/data), for tracing a value back to its parse.'),
}

def cols(*names, **override):
    return [(n, *(override.get(n) or F[n])) for n in names]

TABLES = {
    'appropriations': dict(
        title='Appropriations (fact table)',
        description='One row per appropriation line x stage: the printed amount rows with nothing printed beneath them (leaves). Leaves sum to every printed total (see declared_totals.csv). Never sum this table together with drilldown_items.',
        primary_key=['appropriation_id', 'stage'],
        foreign_keys=[('agency_id', 'agencies', 'agency_id'), ('dept_id', 'departments', 'dept_id')],
        fields=cols('appropriation_id', 'stage', 'fiscal_year', 'dept_id', 'agency_id', 'dept_printed', 'agency_printed', 'category', 'program',
                    'sub_program', 'pap', 'sub_pap', 'funding_source', 'region_printed', 'region_code', 'operating_unit', 'sub_unit', 'geo_level',
                    'psgc_code', 'province_psgc', 'district_id', 'geo_basis', 'drilldown_group_id', 'label', 'ps', 'mooe', 'finex', 'co', 'amount',
                    'prexc_fpap_id')
               + [('nep_description', 'string', 'Activity description of the matching NEP line (BetterGov `dsc`).'),
                  ('nep_operunit', 'string', 'UACS operating unit code of the matching NEP line (BetterGov `operunit`).'),
                  ('nep_operunit_name', 'string', 'UACS operating unit name (BetterGov `uacs_oper_dsc`), or "N operating units not itemized in the bill" for residual matches.'),
                  ('nep_fund_type', 'string', 'Fund of the matching NEP line: regular, loan_proceeds, gop_counterpart, or mixed.')]
               + cols('nep_match', 'pdf_page', 'path_printed', 'source_row_id')),
    'appropriations_compared': dict(
        title='Appropriations compared across stages',
        description='Every appropriation line with GAB_FILED (_A) and GAB_3R (_B) side by side. Lines pair on appropriation_id, so an agency printed under a different department in GAB_3R (NAPC, PCUP) pairs with itself.',
        primary_key=['appropriation_id'],
        foreign_keys=[('agency_id', 'agencies', 'agency_id')],
        fields=cols('appropriation_id', 'dept_id', 'agency_id')
               + [('dept_printed_A', 'string', 'Department printed above the line in GAB_FILED.'),
                  ('dept_printed_B', 'string', 'Department printed above the line in GAB_3R.'),
                  ('moved_department', 'integer', '1 if the agency is printed under a different department in GAB_3R.')]
               + cols('agency_printed', 'category', 'program', 'sub_program', 'pap', 'sub_pap', 'funding_source', 'region_printed', 'region_code',
                      'operating_unit', 'sub_unit', 'label', 'geo_level', 'psgc_code', 'province_psgc', 'district_id', 'prexc_fpap_id', 'nep_match',
                      'drilldown_group_id')
               + [(f'{k}_{s}', 'integer', f'{F[k][1].split(",")[0]}, {"GAB_FILED" if s == "A" else "GAB_3R"} (blank = line absent in that stage).')
                  for s in 'AB' for k in ('ps', 'mooe', 'finex', 'co', 'amount')]
               + [('delta', 'integer', 'amount_B - amount_A, pesos (absent side counts as 0).'),
                  ('pct_change', 'number', 'delta / amount_A; -1 = removed, 1 = added.'),
                  ('status', 'string', 'unchanged | amount_changed | added (GAB_3R only) | removed (GAB_FILED only).'),
                  ('flag', 'string', 'new_line, removed_line, new_amount (0 -> positive), big_increase / big_decrease (>= 20% and >= P50M; a starting threshold, not an editorial standard).'),
                  ('possible_relabel', 'string', 'For an added/removed line with a same-amount counterpart in the same agency: moved (same label, other parent), same_parent (renamed), same_amount (>= P1M, unique). Read these as one line, not a cut plus an insertion, until checked.'),
                  ('relabel_counterpart_id', 'string', 'appropriation_id of the paired line.'),
                  ('relabel_counterpart_label', 'string', 'Label of the paired line.'),
                  ('pdf_page_A', 'integer', 'Page in CR00638.pdf, GAB_FILED.'), ('pdf_page_B', 'integer', 'Page in CR00638.pdf, GAB_3R.')]),
    'declared_totals': dict(
        title='Declared totals',
        description='Every total the bill prints (group headings with amounts, sub-totals, table totals, the agency lead line), with the sum of the leaves beneath it, so each printed claim can be checked. Tables: detail (program table), summary (by program), object (by object of expenditure, printed in thousands, converted to pesos), lead.',
        primary_key=['declared_id', 'stage'],
        foreign_keys=[('agency_id', 'agencies', 'agency_id')],
        fields=[('declared_id', 'string', 'Stable id of the printed total (hash of agency + table + printed chain + occurrence).')]
               + cols('stage', 'fiscal_year', 'dept_id', 'agency_id', 'dept_printed', 'agency_printed')
               + [('table', 'string', 'detail | summary | object | lead.'),
                  ('role', 'string', 'group | subtotal | total | lead (as the parser read the row).'),
                  ('level', 'integer', 'Depth in the printed tree (0 = table total).')]
               + cols('label', 'category', 'program', 'sub_program', 'pap', 'sub_pap', 'funding_source', 'region_printed', 'operating_unit', 'sub_unit',
                      'ps', 'mooe', 'finex', 'co')
               + [('declared_amount', 'integer', 'The total as printed, pesos.'),
                  ('leaf_sum', 'integer', 'Sum of the leaves beneath it, pesos (blank = nothing to compare).'),
                  ('difference', 'integer', 'leaf_sum - declared_amount.'),
                  ('ties', 'integer', '1 = the printed total equals its leaves, 0 = it does not.'),
                  ('known_bill_error', 'string', 'Page-checked explanation when the mismatch is a misprint in the bill (scripts/curated/known_bill_errors.csv).')]
               + cols('pdf_page', 'path_printed')),
    'object_of_expenditure': dict(
        title='Object of expenditure',
        description='The same money cut by object of expenditure (Basic Salary, Travel, ...): one row per printed object line x stage. Printed in thousands of pesos; converted to pesos here. A different cut of appropriations - do not add the two.',
        primary_key=None, foreign_keys=[('agency_id', 'agencies', 'agency_id')],
        fields=cols('stage', 'fiscal_year', 'dept_id', 'agency_id', 'dept_printed', 'agency_printed')
               + [('expense_class', 'string', 'Personnel Services, Maintenance and Other Operating Expenses, Financial Expenses, Capital Outlays.'),
                  ('object_group', 'string', 'Printed group within the class (e.g. Other Compensation Common to All).'),
                  ('object', 'string', 'Object of expenditure as printed.'),
                  ('amount', 'integer', 'Pesos (printed value x 1,000).')]
               + cols('pdf_page', 'path_printed')),
    'drilldown_items': dict(
        title='Drill-down items',
        description='Finer lists the bill prints for some appropriations: DPWH Vol I-C projects (dpwh_vol_ic) and its locally-funded list (dpwh_tail), DA farm-to-market roads (fmr), DOH Health Facilities Enhancement (hfep), NIA irrigation (nia), DILG Support to Barangay Development barangays (sbdp, no amounts). Never sum together with appropriations.',
        primary_key=['item_id'], foreign_keys=[],
        fields=[('item_id', 'string', 'Stable id of the item (hash of source + parser row id).')] + cols('stage')
               + [('source', 'string', 'dpwh_vol_ic | dpwh_tail | fmr | hfep | nia | sbdp.')]
               + cols('drilldown_group_id')
               + [('section', 'string', 'Program / annex section the item is printed under.')]
               + cols('region_printed', 'region_code')
               + [('office', 'string', 'DPWH District Engineering Office, if printed.'),
                  ('province_printed', 'string', 'Province as printed (annexes).'), ('municipality_printed', 'string', 'Municipality as printed (annexes).'),
                  ('barangay_printed', 'string', 'Barangay as printed (SBDP).'), ('item', 'string', 'Project / item description as printed.'),
                  ('amount', 'integer', 'Pesos (blank for SBDP, which prints no amounts).')]
               + cols('geo_level', 'psgc_code', 'province_psgc', 'district_id', 'geo_basis', 'pdf_page', 'source_row_id')),
    'drilldown_coverage': dict(
        title='Drill-down coverage',
        description='Per drill-down group and stage: the appropriations it itemizes vs the sum of its items. DPWH compares per program and HFEP / the DPWH tail nationally because the program tables print much of that money as Central Office lumps; FMR compares per region.',
        primary_key=['drilldown_group_id', 'stage'], foreign_keys=[],
        fields=cols('drilldown_group_id', 'stage')
               + [('source', 'string', 'Drill-down source (see drilldown_items.source).'), ('description', 'string', 'Program / section (and region) of the group.'),
                  ('parent_rows', 'integer', 'Number of appropriations in the group.'), ('parent_amount', 'integer', 'Their total, pesos.'),
                  ('items', 'integer', 'Number of drill-down items.'), ('drilldown_amount', 'integer', 'Their total, pesos.'),
                  ('coverage', 'number', 'drilldown_amount / parent_amount.'),
                  ('status', 'string', 'complete | partial | exceeds_parent | no_items | no_parent_line | parent_not_parsed (parent is in back matter not parsed yet) | no_amounts.')]),
    'special_provisions': dict(
        title='Special Provisions',
        description='The legal conditions printed with each agency\'s appropriation (earmarks, release rules, reporting duties, use of income), one row per provision x stage, full text. Also kept for back-matter funds (Unprogrammed Appropriations, Pension and Gratuity Fund, ...) whose tables are not parsed yet. No amounts are summed from here.',
        primary_key=['provision_id', 'stage'], foreign_keys=[('agency_id', 'agencies', 'agency_id')],
        fields=[('provision_id', 'string', 'Stable id of the provision, the same in both stages: hash of agency (or scope:department) + normalised title + occurrence.')]
               + cols('stage', 'fiscal_year')
               + [('dept_id', 'string', F['dept_id'][1] + ' Blank for back-matter funds.'), ('agency_id', 'string', F['agency_id'][1] + ' Blank for back-matter funds.'),
                  ('dept_printed', 'string', 'Department heading printed above the provision.'), ('agency_printed', 'string', 'Agency name (Table of Contents form where matched, else the heading as printed).'),
                  ('scope', 'string', 'agency | back_matter (a fund whose tables are not parsed yet; no UACS code).'),
                  ('attribution', 'string', 'How the agency was found: heading (printed above), single-agency department, page range (printed before the agency heading, inside that agency\'s pages).'),
                  ('provision_no', 'integer', 'Number as printed (the bill sometimes skips one; listed in CHECKS.md).'),
                  ('title', 'string', 'Provision title as printed (text up to the first period).'),
                  ('text', 'string', 'Full text after the title, as printed; paragraph breaks kept as newlines where the print indents.'),
                  ('pdf_page_start', 'integer', 'First page in CR00638.pdf.'), ('pdf_page_end', 'integer', 'Last page in CR00638.pdf.'),
                  ('lines', 'integer', 'Printed lines.')]),
    'special_provisions_compared': dict(
        title='Special Provisions compared across stages',
        description='Each provision with its GAB_FILED and GAB_3R text side by side. Pairs on agency + title, so a renumbered provision is still matched; a retitled one shows as removed + added.',
        primary_key=['provision_id'], foreign_keys=[('agency_id', 'agencies', 'agency_id')],
        fields=[('provision_id', 'string', 'See special_provisions.provision_id.'), ('dept_id', 'string', 'UACS department code (blank for back matter).'),
                ('agency_id', 'string', 'UACS agency code (blank for back matter).'), ('dept_printed', 'string', 'Department as printed.'),
                ('agency_printed', 'string', 'Agency name.'), ('scope', 'string', 'agency | back_matter.'), ('title', 'string', 'Provision title.'),
                ('provision_no_A', 'integer', 'Number in GAB_FILED.'), ('provision_no_B', 'integer', 'Number in GAB_3R.'),
                ('status', 'string', 'unchanged | renumbered (same text, other number) | text_changed | added (GAB_3R only) | removed (GAB_FILED only).'),
                ('words_added', 'integer', 'Words in GAB_3R not in GAB_FILED (word-level diff; whole text for an added provision).'),
                ('words_removed', 'integer', 'Words in GAB_FILED not in GAB_3R.'),
                ('text_A', 'string', 'Text in GAB_FILED.'), ('text_B', 'string', 'Text in GAB_3R.'),
                ('pdf_page_A', 'integer', 'First page, GAB_FILED.'), ('pdf_page_B', 'integer', 'First page, GAB_3R.')]),
    'departments': dict(
        title='Departments', description='One row per UACS department in the release.', primary_key=['dept_id'], foreign_keys=[],
        fields=cols('dept_id') + [('gab_dept_code', 'string', 'Roman-numeral department code in the bill (I = Congress ...).'),
                                  ('name_printed', 'string', 'Name as printed in the bill.'), ('name_official', 'string', 'UACS name (DBM), without the acronym.'),
                                  ('acronym', 'string', 'Official acronym.'), ('acronym_source', 'string', 'Where the acronym comes from: UACS name (BetterGov NEP 2027) or the bill text.'),
                                  ('acronym_source_page', 'integer', 'CR00638.pdf page, when the source is the bill text.'),
                                  ('agencies', 'integer', 'Number of agencies in the release.')]),
    'agencies': dict(
        title='Agencies', description='One row per UACS agency. Each state university or college is its own agency (UACS department 08).',
        primary_key=['agency_id'], foreign_keys=[('dept_id', 'departments', 'dept_id')],
        fields=cols('agency_id', 'dept_id') + [
            ('gab_dept_code', 'string', 'Roman-numeral department code in the bill.'), ('gab_agency_code', 'string', 'Agency letter (code) in the bill.'),
            ('suc_region_group_code', 'string', 'SUCs only: the bill\'s regional group letter (A-S).'), ('suc_region_group', 'string', 'SUCs only: the regional group name.'),
            ('name_printed', 'string', 'Name in the bill\'s Table of Contents.'), ('name_official', 'string', 'UACS name (DBM), without the acronym.'),
            ('acronym', 'string', 'Official acronym; blank when no official source gives one (never invented).'),
            ('acronym_source', 'string', 'UACS name (BetterGov NEP 2027) | bill text (HB 10858, CR 638).'),
            ('acronym_source_page', 'integer', 'CR00638.pdf page of the first definition, for bill text.'),
            ('stages', 'string', 'Stages the agency appears in.'), ('dept_printed', 'string', 'Department printed above the agency, per stage.')]),
    'regions': dict(
        title='Regions', description='The 18 regions (PSGC 2Q-2026).', primary_key=['region_code'], foreign_keys=[],
        fields=cols('region_code') + [('psgc_code', 'string', 'PSGC 10-digit code.'), ('name', 'string', 'PSGC name.'),
                                      ('short_name', 'string', 'Short id used in ph-pork-graph (NCR, IV-A, ...).'), ('population_2024', 'integer', '2024 population (PSGC file).')]),
    'localities': dict(
        title='Localities', description='Provinces, cities, municipalities and sub-municipalities (PSGC 2Q-2026); barangays are not included.',
        primary_key=['psgc_code'], foreign_keys=[('region_code', 'regions', 'region_code')],
        fields=[('psgc_code', 'string', 'PSGC 10-digit code.'), ('name', 'string', 'PSGC name.'),
                ('geo_level', 'string', 'province | city | municipality | sub_municipality.'), ('city_class', 'string', 'HUC, ICC or CC (cities).'),
                ('income_class', 'string', 'Income classification (PSGC file).')] + cols('region_code', 'province_psgc')
               + [('population_2024', 'integer', '2024 population (PSGC file).')]),
    'districts': dict(
        title='Legislative districts', description='House legislative districts (from ph-pork-graph), with the PSGC code of the province/city they belong to.',
        primary_key=['district_id'], foreign_keys=[],
        fields=[('district_id', 'string', 'District id (e.g. cebu-3, abra-lone).'), ('name', 'string', 'District name.'),
                ('district_no', 'integer', 'District number (0 = lone district).'), ('psgc_code', 'string', 'PSGC of its province or city (blank for Taguig-Pateros, which spans a city and a municipality).')]
               + cols('region_code')),
    'operating_units': dict(
        title='Operating units', description='One row per agency x region x printed operating unit, with the place it was attributed to and the rule used.',
        primary_key=None, foreign_keys=[('agency_id', 'agencies', 'agency_id')],
        fields=cols('agency_id', 'agency_printed', 'region_code', 'region_printed', 'operating_unit', 'geo_level', 'psgc_code', 'province_psgc',
                    'district_id', 'geo_basis') + [('rows', 'integer', 'Appropriation rows (both stages) under this unit.')]),
}
