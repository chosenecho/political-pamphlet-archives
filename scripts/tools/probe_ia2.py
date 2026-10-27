"""检查 IA 单条目：页数、PDF、页面图 URL。"""

import json
import ssl
import urllib.request

UA = "PamphletArchiveBot/1.0 (https://github.com/chosenecho/political-pamphlet-archives; research@example.org)"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

IDENT = "republicancampa03commgoog"


def get(url, timeout=60, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        data = r.read()
    return (r.status, len(data), r.headers.get("Content-Type")) if raw else json.loads(data)


m = get(f"https://archive.org/metadata/{IDENT}")
md = m.get("metadata", {})
print("title:", md.get("title"))
print("date:", md.get("date"), "| year:", md.get("year"))
print("imagecount:", md.get("imagecount"))
print("subject:", str(md.get("subject"))[:120])
print("collection:", str(md.get("collection"))[:120])

files = m.get("files", [])
print("文件数:", len(files))
for f in files:
    if f.get("name", "").endswith((".pdf", "_bw.pdf", ".jp2.zip")):
        print("  ", f["name"], f.get("format"), round(int(f.get("size", 0)) / 1048576, 2), "MB")

print("\n页面图测试：")
for n in (0, 1, 5):
    for w in (800, 1200):
        u = f"https://archive.org/download/{IDENT}/page/n{n}_w{w}.jpg"
        try:
            st, ln, ct = get(u, raw=True)
            print(f"  n{n} w{w}: {st} {ln/1024:7.1f}KB {ct}")
        except Exception as e:
            print(f"  n{n} w{w}: ERR {type(e).__name__}")
