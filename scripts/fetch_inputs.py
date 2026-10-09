"""Get and verify the source files (inputs/SOURCES.md): python scripts/fetch_inputs.py

Downloads the bill PDFs (House of Representatives; the 3rd-reading volumes from Google Drive) and BetterGov's NEP 2027 CSV if they are missing; the PSGC file must be
downloaded by hand (psa.gov.ph sits behind a browser check). Every file is verified against its SHA-256 - a different file would silently change the release."""
import hashlib, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
DRIVE_ID = {'I-A': '1B2cSHSNzScFH_eu9WCgxxJQHWb2aUbta', 'I-B': '1nJWHmmyPpQ26wRaEhGpDCigAgnwgAahq', 'I-C': '1lspNh4ZlfJZ4B8pilkAKy6CDrv69kdbV', 'II': '1o0IWjrJ-HAy936jclT94sCHO8wEZdDSz'}   # file ids in the Drive folder listed in inputs/SOURCES.md
FILES = [  # (path, sha256, url to download automatically or None, where to get it by hand)
    (os.path.join('pipeline', 'raw', 'hb10858', 'CR00638.pdf'), '3242a248d1436be5d15c2bd81628c1c9691e0b796fc4a58552d063f18177b6b0',
     'https://docs.congress.hrep.online/legisdocs/first_20/CR00638.pdf', 'House of Representatives, Committee Report No. 638 on HB 10858'),
    *[(os.path.join('pipeline', 'raw', 'hb10858_3r', f'HB10858_3R_VOL_{v}.pdf'), h,
       f'https://drive.usercontent.google.com/download?id={DRIVE_ID[v]}&export=download&confirm=t',
       'HB 10858 "FOR 3RD READING" Vol ' + v + ', Google Drive folder https://drive.google.com/drive/folders/1gs7q6NIw3E13JsWt190MLZmqzwvRxHB0')
      for v, h in (('I-A', '79f56b8d577246342b59cc996afdd707523268f0bde10378e3c1b5ef844451fd'), ('I-B', '4cc0f17e472d1af380ea6d3972561f6bb241137826fd85ed7e7e70bcd92986b9'),
                   ('I-C', '48cb7a11e391bd4da89d4f47cf39a2eba8fe9bfe636dba101c8284b224ac1b1b'), ('II', '376ddaf7291e2beaa839b606c77e07ed82c49ec7eca7276c68e86959c1e80750'))],
    (os.path.join('inputs', 'NEP-FY2027.csv'), '5236dba760e9cd5628ed9b48cd8930e18dc2afe5ae4cbd65c524b8c60a259874',
     'https://huggingface.co/datasets/bettergovph/nep-2027/resolve/main/NEP-FY2027.csv', 'huggingface.co/datasets/bettergovph/nep-2027'),
    (os.path.join('inputs', 'PSGC-2Q-2026-Publication-Datafile.xlsx'), '31892bc2bdde3ea0682562d9412b5bab4d45a0be5e5a5b4f6c9d7714b94bca5d', None,
     'psa.gov.ph/classification/psgc (2nd Quarter 2026 publication datafile)'),
]

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

if __name__ == '__main__':
    bad = 0
    for rel, digest, url, where in FILES:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p) and url:
            os.makedirs(os.path.dirname(p), exist_ok=True); print('downloading', url)
            urllib.request.urlretrieve(url, p)
        if not os.path.exists(p): print(f'MISSING  {rel}\n         get it from: {where}'); bad += 1
        elif sha256(p) != digest: print(f'WRONG    {rel} (SHA-256 differs; expected {digest})'); bad += 1
        else: print(f'ok       {rel}')
    sys.exit(bad)
