"""验证 PDF 逐页缩略图 URL 的构造方式。"""

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


def head(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
            d = r.read()
            return r.status, len(d)
    except Exception as e:
        return "ERR", type(e).__name__


TITLE = "File:Voters' pamphlet 1946.pdf"
d = api({"action": "query", "format": "json", "titles": TITLE,
         "prop": "imageinfo", "iiprop": "url|size|mime",
         "iiurlwidth": "1200"})
p = list((d.get("query") or {}).get("pages", {}).values())[0]
ii = p["imageinfo"][0]
print("pagecount:", ii.get("pagecount"))
print("thumburl:", ii.get("thumburl"))
print("url:", ii.get("url")[:130])

# 方法 A：从 thumburl 替换 page1
tu = ii.get("thumburl") or ""
if "page1-" in tu:
    for n in (1, 2, 5):
        u = tu.replace("page1-", f"page{n}-")
        print(f"A page{n}:", head(u), u[:110])

# 方法 B：手工拼 upload.wikimedia.org
name = TITLE.replace("File:", "")
enc = urllib.parse.quote(name.replace(" ", "_"))
h1 = enc[0]
h2 = enc[0] + enc[1] if len(enc) > 1 else enc[0]
for n in (1, 2):
    for width in ("1200", "800"):
        u = f"https://upload.wikimedia.org/wikipedia/commons/thumb/{h1}/{h2}/{enc}/page{n}-{width}px-{enc}.jpg"
        print(f"B page{n} w{width}:", head(u))
