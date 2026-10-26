"""探测 Commons 上的多页小册子（PDF/DjVu）以及如何取全部页。"""

import json
import ssl
import urllib.parse
import urllib.request

UA = ("PamphletArchiveBot/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research@example.org)")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read())


print("=== 1. PDF 的 imageinfo 是否给页数 ===")
for t in ["File:Voters' pamphlet 1946.pdf", "File:Political pamphlet test.pdf"]:
    try:
        d = api({"action": "query", "format": "json", "titles": t,
                 "prop": "imageinfo", "iiprop": "url|size|mime|dimensions"})
        pages = (d.get("query") or {}).get("pages") or {}
        for pid, p in pages.items():
            if "missing" in p:
                print(f"  缺失: {t}")
                continue
            ii = (p.get("imageinfo") or [{}])[0]
            print(f"  {t}")
            print("    keys:", sorted(ii.keys()))
            print("    size:", ii.get("width"), ii.get("height"), "| mime:", ii.get("mime"))
            print("    pagecount:", ii.get("pagecount"))
            print("    thumburl:", (ii.get("thumburl") or "")[:120])
    except Exception as e:
        print("ERR", type(e).__name__, str(e)[:100])

print("\n=== 2. 搜多页小册子 PDF ===")
QUERIES = [
    "filemime:application/pdf pamphlet",
    "filemime:application/pdf political pamphlet",
    "filemime:application/pdf tract politics",
    "filemime:application/pdf election address",
    "filemime:application/pdf Wahlprogramm",
    "filemime:application/pdf brochure politique",
]
for q in QUERIES:
    try:
        d = api({"action": "query", "format": "json", "list": "search",
                 "srsearch": q, "srnamespace": "6", "srlimit": "5"})
        hits = (d.get("query") or {}).get("search") or []
        print(f"\n[{q}] {len(hits)}")
        for h in hits:
            print("   ", h.get("title"))
    except Exception as e:
        print(f"ERR {q}: {type(e).__name__}")
