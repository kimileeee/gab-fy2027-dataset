"""The three stages of HB 10858 in the release, and where each parser copy's pages live.

Parser copies (pipeline/build/gab_pdf.py): A and B are the two halves of Committee Report 638 (CR00638.pdf); C is the four
"HB 10858 FOR 3RD READING" volumes, which the parsers append after CR00638's 7,408 pages. pdf_ref() turns a parser page number into
the file and page a reader actually opens."""

STAGE = {'A': 'GAB_FILED', 'B': 'GAB_2R', 'C': 'GAB_3R'}
ORDER = ('GAB_FILED', 'GAB_2R', 'GAB_3R')
PAIRS = (('GAB_FILED', 'GAB_2R'), ('GAB_2R', 'GAB_3R'), ('GAB_FILED', 'GAB_3R'))   # each step, then filed -> final
CR_PAGES = 7408
VOLS = (('HB10858_3R_VOL_I-A.pdf', 1339), ('HB10858_3R_VOL_I-B.pdf', 982), ('HB10858_3R_VOL_I-C.pdf', 942), ('HB10858_3R_VOL_II.pdf', 610))

def page_cols(page):
    f, p = pdf_ref(page); return dict(pdf_file=f, pdf_page=p)

def comparison(a, b): return f'{a}_to_{b}'

def pdf_ref(page):
    """Parser page -> (pdf_file, 1-based page in that file)."""
    p = int(page)
    if p <= CR_PAGES: return 'CR00638.pdf', p
    p -= CR_PAGES
    for f, n in VOLS:
        if p <= n: return f, p
        p -= n
    raise ValueError(f'page {page} is past the last 3rd-reading volume')

if __name__ == '__main__':
    assert pdf_ref(3536) == ('CR00638.pdf', 3536) and pdf_ref(7409) == ('HB10858_3R_VOL_I-A.pdf', 1)
    assert pdf_ref(7408 + 1339 + 1) == ('HB10858_3R_VOL_I-B.pdf', 1) and pdf_ref(7408 + 3873) == ('HB10858_3R_VOL_II.pdf', 610)
    print('ok')
