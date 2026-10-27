"""探针 2：换检索式与换源，探北欧/比利时/奥地利/匈牙利/荷兰的可抓性。

覆盖三种入口：
  1. IA 去语言过滤，改按标题词（valgprogram / partiprogram / vaaliohjelma 等）
  2. Wikimedia Commons 分类检索（政党海报/传单，多为单页）
  3. 各国国家图书馆的 OAI/检索接口（Delpher、Nasjonalbiblioteket 等）

只打印命中，不下载。
"""

import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http

# --- 1. IA 标题词检索（不限语言，靠标题词命中本语种材料） ---
IA_TITLE_PROBES = [
    ("瑞典", 'title:(valprogram OR partiprogram OR "socialdemokratiska" OR flygblad)'),
    ("丹麦", 'title:(valgprogram OR partiprogram OR "socialdemokratiet" OR flyveblad)'),
    ("芬兰", 'title:(vaaliohjelma OR puolueohjelma OR "sosialidemokraatti")'),
    ("比利时", 'title:(programme OR "parti ouvrier" OR "christen" OR verkiezing) AND language:(fre OR dut)'),
    ("奥地利", 'title:(wahlprogramm OR parteiprogramm OR "sozialdemokratische") AND language:ger'),
    ("匈牙利", 'title:(program OR "választási" OR szocialista) AND language:hun'),
    ("荷兰", 'title:(program OR "sociaal-democratische" OR verkiezing) AND language:dut'),
    ("爱尔兰", 'title:("home rule" OR nationalist OR republican OR "land league")'),
]

# --- 2. Wikimedia Commons 分类检索 ---
COMMONS_CATS = [
    ("瑞典", "Category:Political posters of Sweden"),
    ("丹麦", "Category:Political posters of Denmark"),
    ("芬兰", "Category:Political posters of Finland"),
    ("挪威", "Category:Political posters of Norway"),
    ("北欧传单", "Category:Political leaflets"),
    ("选举材料", "Category:Election posters"),
]

# --- 3. 国家图书馆检索端点 ---
NB_ENDPOINTS = [
    ("荷兰 Delpher", "https://api.delpher.nl/v1/search?q=verkiezingspropaganda"),
    ("丹麦 Det Kgl.", "https://www.statsbiblioteket.dk/"),
    ("瑞典 KB", "https://libris.kb.se/"),
    ("挪威 NB", "https://api.nb.no/catalog/v1/items?q=valgprogram"),
]


def ia_search(q, rows=25):
    params = {
        "q": q,
        "fl[]": ["identifier", "title", "year", "language", "imagecount"],
        "rows": str(rows),
        "output": "json",
        "sort[]": "downloads desc",
    }
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return http.fetch_json(url, timeout=60)


def commons_cat(cat, limit=8):
    params = {
        "action": "query", "format": "json", "list": "categorymembers",
        "cmtitle": cat, "cmtype": "file", "cmlimit": str(limit),
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return http.fetch_json(url, timeout=45)


def main():
    print("=" * 70)
    print("1) IA 标题词检索")
    print("=" * 70)
    for country, q in IA_TITLE_PROBES:
        full = f'{q} AND imagecount:[8 TO 64] AND year:[1880 TO 1955] AND mediatype:texts'
        try:
            d = ia_search(full)
        except Exception as e:
            print(f"[{country}] 失败 {type(e).__name__}: {str(e)[:50]}")
            continue
        docs = (d.get("response") or {}).get("docs", [])
        print(f"\n[{country}] 命中 {d.get('response',{}).get('numFound','?')}")
        for doc in docs[:5]:
            print(f"   {doc.get('year','?')} {str(doc.get('imagecount','?')):>3}p "
                  f"{str(doc.get('language',''))[:12]:12s} {doc.get('identifier','')[:32]:32s} "
                  f"{str(doc.get('title') or '')[:46]}")

    print("\n" + "=" * 70)
    print("2) Wikimedia Commons 分类")
    print("=" * 70)
    for label, cat in COMMONS_CATS:
        try:
            d = commons_cat(cat)
        except Exception as e:
            print(f"[{label}] {cat} 失败 {type(e).__name__}")
            continue
        members = (d.get("query") or {}).get("categorymembers", [])
        print(f"[{label}] {cat} -> {len(members)} 个文件")
        for m in members[:4]:
            print(f"     {m.get('title','')[:70]}")

    print("\n" + "=" * 70)
    print("3) 国家图书馆接口")
    print("=" * 70)
    for label, url in NB_ENDPOINTS:
        try:
            t = http.fetch(url, timeout=25, retries=2)
            print(f"[{label}] OK {len(t)} 字节")
        except Exception as e:
            print(f"[{label}] {type(e).__name__}: {str(e)[:60]}")


if __name__ == "__main__":
    main()
