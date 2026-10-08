"""Get and verify the three source files (inputs/SOURCES.md): python scripts/fetch_inputs.py

Downloads the bill PDF (House of Representatives) and BetterGov's NEP 2027 CSV if they are missing; the PSGC file must be
downloaded by hand (psa.gov.ph sits behind a browser check). Every file is verified against its SHA-256 - a different file would silently change the release."""
import hashlib, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
FILES = [  # (path, sha256, url to download automatically or None, where to get it by hand)
    (os.path.join('pipeline', 'raw', 'hb10858', 'CR00638.pdf'), '3242a248d1436be5d15c2bd81628c1c9691e0b796fc4a58552d063f18177b6b0',
     'https://docs.congress.hrep.online/legisdocs/first_20/CR00638.pdf', 'House of Representatives, Committee Report No. 638 on HB 10858'),
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
