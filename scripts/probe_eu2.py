"""探测欧洲开放接口：Kramerius(捷)、Polona(波)、Finna(芬)、Europeana、Hispana(西)。"""

import json
import ssl
import urllib.parse
import urllib.request

UA = ("PamphletArchiveBot/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research@example.org)")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def get(url, timeout=45, want_json=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        data = r.read()
        return (json.loads(data) if want_json else (r.status, len(data), r.headers.get("Content-Type")))


TESTS = [
    # 捷克 Kramerius（多机构共用 v7 API）
    ("Kramerius MZK", "https://api.kramerius.mzk.cz/search/api/client/v7.0/search?q=bro%C5%BEura&rows=3"),
    ("Kramerius NKP", "https://api.kramerius.nkp.cz/search/api/client/v7.0/search?q=bro%C5%BEura&rows=3"),
    # 波兰 Polona
    ("Polona API", "https://polona.pl/api/entities/?query=pamflet&size=3"),
    ("Polona 主页", "https://polona.pl/"),
    # 芬兰 Finna
    ("Finna 搜索", "https://api.finna.fi/v1/search?lookfor=pamfletti&limit=3&field[]=title&field[]=images&field[]=year"),
    # Europeana
    ("Europeana", "https://api.europeana.eu/record/v2/search.json?query=pamphlet%20AND%20politics&rows=3&wskey=api2demo"),
    # 西班牙
    ("Hispana OAI", "https://hispana.mecd.es/catalogo2/oai?verb=Identify"),
    ("BVPH", "https://www.bvpb.mecd.es/"),
    # 奥地利 ANNO
    ("ANNO", "https://anno.onb.ac.at/"),
]

for name, url in TESTS:
    try:
        if any(k in url for k in ("oai", "ANNO", "bvpb", "polona.pl/")):
            st, ln, ct = get(url, want_json=False)
            print(f"OK  {st} {ln:>8}B {str(ct)[:28]:28s} {name}")
        else:
            d = get(url)
            print(f"OK  json keys={list(d)[:6]}  {name}")
            print("     ", json.dumps(d, ensure_ascii=False)[:220])
    except Exception as e:
        print(f"ERR {type(e).__name__}: {str(e)[:60]}  {name}")
