"""检查 Europeana 条目是否给出 IIIF 清单 / 多页对象地址。"""

import json
import ssl
import urllib.parse
import urllib.request

UA = ("PamphletArchiveBot/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research@example.org)")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def get(url, timeout=50, want_json=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        data = r.read()
    return json.loads(data) if want_json else data


params = {
    "query": 'pamphlet AND (politics OR election)',
    "rows": "12",
    "wskey": "api2demo",
    "profile": "rich",
    "reusability": "open",
    "media": "true",
}
url = "https://api.europeana.eu/record/v2/search.json?" + urllib.parse.urlencode(params)
d = get(url)
print("total:", d.get("totalResults"))
items = d.get("items", [])

keys = set()
for it in items:
    keys.update(it.keys())
print("字段:", sorted(k for k in keys if "Shown" in k or "Referenced" in k or "provider" in k or "Service" in k or "rights" in k.lower()))

for it in items[:6]:
    print("\n---", (it.get("title") or [""])[0][:70])
    print("  country :", it.get("country"))
    print("  provider:", (it.get("dataProvider") or [""])[0], "|", (it.get("provider") or [""])[0])
    print("  shownBy :", (it.get("edmIsShownBy") or [""])[0][:110])
    ref = (it.get("dctermsIsReferencedBy") or [])
    print("  referBy :", (ref[0] if ref else "")[:110])
    svc = it.get("svcsHasService") or []
    print("  service :", (svc[0] if svc else "")[:110])
    print("  type    :", it.get("type"))
    print("  rights  :", (it.get("rights") or [""])[0][:60])

# 找一个 IIIF manifest 试试
cands = []
for it in items:
    for k in ("dctermsIsReferencedBy", "svcsHasService", "edmIsShownBy"):
        for v in (it.get(k) or []):
            if "manifest" in v.lower() or "/iiif/" in v.lower():
                cands.append(v)
print("\n候选 IIIF 地址:", len(cands))
for c in cands[:3]:
    try:
        m = get(c)
        print("  OK manifest, canvases:", len(m.get("sequences", [{}])[0].get("canvases", [])) if "sequences" in m else len(m.get("items", [])))
        print("   ", c[:100])
    except Exception as e:
        print("  ERR", type(e).__name__, c[:90])
