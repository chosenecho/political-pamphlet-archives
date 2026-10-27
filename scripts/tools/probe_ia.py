"""探测 Internet Archive 的政治小册子专藏与页面图接口。"""

import json
import ssl
import urllib.parse
import urllib.request

UA = "PamphletArchiveBot/1.0 (https://github.com/chosenecho/political-pamphlet-archives; research@example.org)"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def get(url, timeout=60, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        data = r.read()
        if raw:
            return r.status, len(data), r.headers.get("Content-Type")
        return json.loads(data)


def search(q, rows=5, fl=("identifier", "title", "date", "year", "subject", "collection")):
    params = {"q": q, "fl[]": list(fl), "rows": str(rows), "page": "1",
              "output": "json", "sort[]": "downloads desc"}
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return get(url)


print("=== 政治小册子专藏检索 ===")
for q in ['collection:(politicalpamphlets)',
          'collection:(pamphlets) AND subject:(politics)',
          'subject:("campaign literature")',
          'collection:(pamphlets) AND subject:(election)']:
    try:
        d = search(q, 5)
        resp = d.get("response", {})
        print(f"\n[{q}] numFound={resp.get('numFound')}")
        for doc in resp.get("docs", [])[:5]:
            print("   ", doc.get("identifier"), "|", str(doc.get("title"))[:56], "|", doc.get("year"))
    except Exception as e:
        print(f"ERR {q}: {type(e).__name__} {str(e)[:80]}")

print("\n=== 单条目结构 ===")
d = search('collection:(politicalpamphlets)', 1)
doc = d["response"]["docs"][0]
ident = doc["identifier"]
print("样例:", ident)
try:
    m = get(f"https://archive.org/metadata/{ident}")
    files = m.get("files", [])
    print("  文件数:", len(files))
    kinds = {}
    for f in files:
        kinds[f.get("format")] = kinds.get(f.get("format"), 0) + 1
    print("  格式:", kinds)
    pdfs = [f["name"] for f in files if f["name"].endswith(".pdf")]
    print("  PDF:", pdfs[:2])
    print("  imagecount:", m.get("metadata", {}).get("imagecount"))
    print("  date:", m.get("metadata", {}).get("date"))
except Exception as e:
    print("ERR meta", type(e).__name__, str(e)[:80])

print("\n=== 页面图接口 ===")
for u in [f"https://archive.org/download/{ident}/page/n0_w800.jpg",
          f"https://archive.org/download/{ident}/page/n1_w800.jpg",
          f"https://archive.org/download/{ident}/page/n2_w1200.jpg"]:
    try:
        st, ln, ct = get(u, raw=True)
        print(f"  {st} {ln:>8} {ct}  {u[-28:]}")
    except Exception as e:
        print(f"  ERR {type(e).__name__}  {u[-28:]}")
