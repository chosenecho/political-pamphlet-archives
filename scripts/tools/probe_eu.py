"""探测 FES 数字图书馆与 La Contemporaine 的 PDF 可获取性。"""

import json
import re
import ssl
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "text/html,application/xhtml+xml,*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.status, r.read(), r.geturl()


CANDIDATES = [
    ("FES 数字图书馆", "https://library.fes.de/digitalisate/"),
    ("FES 图书馆主页", "https://library.fes.de/"),
    ("FES 数字期刊", "https://library.fes.de/zeitschriften/"),
    ("FES Archiv", "https://www.fes.de/archiv-der-sozialen-demokratie"),
    ("La Contemporaine 数字", "https://www.lacontemporaine.fr/en/collections/"),
    ("Gallica tracts", "https://gallica.bnf.fr/accueil/fr/html/les-tracts-de-la-seconde-guerre-mondiale-a-la-reserve-des-livres-rares"),
]

for name, url in CANDIDATES:
    try:
        st, body, final = get(url)
        txt = body.decode("utf-8", "replace")
        pdfs = re.findall(r'href="([^"]+\.pdf)"', txt, re.I)
        print(f"OK  {st} {len(body):>8}B  pdf链接={len(pdfs):>3}  {name}")
        for p in pdfs[:3]:
            print("     ", p[:110])
    except Exception as e:
        print(f"ERR {name}: {type(e).__name__} {str(e)[:70]}")

print("\n=== FES 是否有检索接口 ===")
for u in ["https://library.fes.de/opac/",
          "https://library.fes.de/digitalisate/digitalisate.html",
          "https://library.fes.de/sozdem/"]:
    try:
        st, body, final = get(u)
        print(f"OK {st} {len(body):>8}B {body.decode('utf-8','replace').count('.pdf')} pdf词频  {u}")
    except Exception as e:
        print(f"ERR {type(e).__name__} {u}")
