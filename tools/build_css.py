"""Build styles.css: every Tailwind class used in index.html, compiled once.

The app used to compile its styles in the browser on every load (Tailwind's
play script). This runs that same compiler once, in a headless browser, over
every class name found in index.html, and saves the result as styles.css.

Run after changing classes:  python3 tools/build_css.py
Needs: pip install playwright && playwright install chromium
The Tailwind play script comes from TAILWIND_JS (a local file) or the CDN.
"""
import os, re, sys, urllib.request, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
TW_URL = 'https://cdn.tailwindcss.com/3.4.17'

def tailwind_js():
    p = os.environ.get('TAILWIND_JS')
    if p and os.path.exists(p):
        return open(p, encoding='utf-8').read()
    with urllib.request.urlopen(TW_URL) as r:
        return r.read().decode('utf-8')

def selectors(css):
    return set(re.findall(r'(?:^|[}\s,])(\.[^\s{,]+)', css))

def main():
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    config = (ROOT / 'tools' / 'tailwind.config.js').read_text(encoding='utf-8')
    # every token that could be a class name (a few false ones are harmless)
    tokens = set(re.findall(r"[A-Za-z0-9_\-:/\[\]\.%#!()',]+", html))
    tokens = {t.strip("'\",") for t in tokens}
    tokens = sorted(t for t in tokens if 1 < len(t) < 80 and re.search(r'[a-z]', t) and not t.startswith('//'))
    page = f"""<!doctype html><html><head><script>{tailwind_js()}</script><script>tailwind.config = {config}</script></head>
<body><div id="all" class="{' '.join(t.replace('"', '') for t in tokens)}"></div></body></html>"""
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        pg.set_content(page)
        pg.wait_for_timeout(1500)
        css = pg.evaluate("[...document.querySelectorAll('style')].map(s => s.textContent).filter(t => t.includes('--tw-')).pop() || ''")
        b.close()
    if len(css) < 10000:
        sys.exit('Tailwind produced too little CSS; something went wrong')
    if '--check' in sys.argv:
        # CI: fail only if index.html uses classes that the committed styles.css doesn't have
        have = selectors((ROOT / 'styles.css').read_text(encoding='utf-8'))
        missing = sorted(selectors(css) - have)
        if missing:
            sys.exit('styles.css is out of date, run: python3 tools/build_css.py\nMissing: ' + ' '.join(missing[:40]))
        print('styles.css is up to date')
        return
    (ROOT / 'styles.css').write_text('/* Built by tools/build_css.py from the classes in index.html. Do not edit by hand. */\n' + css, encoding='utf-8')
    print(f'styles.css: {len(css):,} bytes from {len(tokens):,} candidate classes')

if __name__ == '__main__':
    main()
