"""探针 3：绕开 language 过滤，改用馆藏集合、国名词与专题词探测缺口国家。

思路：IA 的 language 字段对北欧小语种覆盖差，但馆藏集合（collection:）与
题名里的政党名/机构名往往可用。逐个集合与逐个关键词试探，记录真实命中数。
"""

import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http

BASE = 'imagecount:[8 TO 64] AND year:[1880 TO 1955] AND mediatype:texts'

# 集合级探测：这些 collection 里政治宣传品密度高
COLLECTION_PROBES = [
    ("politics 通俗政治册", "collection:folkscanomy_politics"),
    ("universal library", "collection:universallibrary AND subject:(politics OR socialism)"),
    ("toronto 缩微", "collection:toronto AND subject:(politics OR socialism OR election)"),
    ("加拿大缩微 cihm", "collection:cihm AND subject:(politics OR election)"),
]

# 国名/政党名关键词探测（不加 language）
KEYWORD_PROBES = [
    ("瑞典", '("Sveriges socialdemokratiska" OR "Högerns" OR "folkpartiet" OR "Sverige" ) AND subject:(politics OR socialism OR election)'),
    ("丹麦", '("Socialdemokratiet" OR "Venstre" OR "Radikale" OR Denmark) AND subject:(politics OR socialism OR election)'),
    ("芬兰", '("Suomen" OR "Sosialidemokraattinen" OR Finland) AND subject:(politics OR socialism OR election)'),
    ("挪威", '("Arbeiderpartiet" OR "Høyre" OR Norge) AND subject:(politics OR socialism OR election)'),
    ("比利时", '("Belgique" OR "België" OR "parti ouvrier belge") AND subject:(politics OR socialism OR election)'),
    ("奥地利", '("Österreich" OR "Austria") AND subject:(politics OR socialism OR christlichsozial)'),
    ("匈牙利", '("Magyar" OR Hungary) AND subject:(politics OR socialism OR election)'),
    ("荷兰", '("SDAP" OR "Nederland" OR "Katholieke") AND subject:(politics OR socialism OR election)'),
    ("意大利", '("Italia" OR Italy) AND subject:(fascismo OR socialism OR "partito popolare")'),
    ("西班牙", '("España" OR Spain) AND subject:(política OR socialismo OR falange)'),
    ("英国", '("Fabian" OR "Labour" OR "suffrage") AND subject:(politics OR socialism OR election)'),
]


def ia_search(q, rows=30):
    params = {
        "q": q,
        "fl[]": ["identifier", "title", "year", "language", "imagecount", "collection"],
        "rows": str(rows),
        "output": "json",
        "sort[]": "downloads desc",
    }
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return http.fetch_json(url, timeout=60)


def run(label, q):
    full = f'{q} AND {BASE}'
    try:
        d = ia_search(full)
    except Exception as e:
        print(f"[{label}] 失败 {type(e).__name__}: {str(e)[:50]}")
        return 0
    resp = d.get("response") or {}
    docs = resp.get("docs", [])
    print(f"\n[{label}] numFound={resp.get('numFound','?')}")
    for doc in docs[:6]:
        print(f"   {doc.get('year','?')} {str(doc.get('imagecount','?')):>3}p "
              f"{str(doc.get('language',''))[:10]:10s} {doc.get('identifier','')[:30]:30s} "
              f"{str(doc.get('title') or '')[:44]}")
    return len(docs)


def main():
    print("=" * 70)
    print("A) 馆藏集合")
    print("=" * 70)
    for label, q in COLLECTION_PROBES:
        run(label, q)

    print("\n" + "=" * 70)
    print("B) 国名/政党名关键词")
    print("=" * 70)
    for label, q in KEYWORD_PROBES:
        run(label, q)


if __name__ == "__main__":
    main()
