"""探针：对缺口国家在 Internet Archive 上试检索，看能返回多少可用候选。

只做检索与字段打印，不下载。用于决定采集配额。
"""

import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http

# (国别, IA 语言码, 主题词)
PROBES = [
    ("瑞典", "swe", 'socialdemokrati OR socialism OR arbetarrörelsen'),
    ("丹麦", "dan", 'socialdemokrati OR arbejderbevaegelse OR valgprogram'),
    ("芬兰", "fin", 'sosiaalidemokratia OR työväenliike OR vaaliohjelma'),
    ("比利时", "dut", 'socialisme OR katholiek OR verkiezing'),
    ("爱尔兰", "eng", '"Irish" AND (nationalism OR "home rule" OR republican)'),
    ("英国", "eng", '("Fabian tract" OR "labour party" OR suffragette)'),
    ("奥地利", "ger", '"Österreich" AND (sozialdemokratie OR christlichsozial)'),
    ("荷兰", "dut", 'socialisme OR sdap OR katholieke'),
    ("意大利", "ita", 'fascismo OR socialismo OR cattolicesimo'),
    ("匈牙利", "hun", 'szocializmus OR keresztény OR választás'),
    ("德国", "ger", 'nationalsozialismus OR sozialdemokratie OR zentrum'),
]

MINP, MAXP = 10, 64


def search(q, rows=40):
    params = {
        "q": q,
        "fl[]": ["identifier", "title", "year", "language", "subject", "imagecount"],
        "rows": str(rows),
        "output": "json",
        "sort[]": "downloads desc",
    }
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return http.fetch_json(url, timeout=60)


def main():
    for country, code, subj in PROBES:
        q = (f'language:({code}) AND subject:({subj}) AND '
             f'imagecount:[{MINP} TO {MAXP}] AND year:[1880 TO 1948] AND mediatype:texts')
        try:
            d = search(q)
        except Exception as e:
            print(f"[{country}] 检索失败 {type(e).__name__}: {str(e)[:60]}")
            continue
        docs = (d.get("response") or {}).get("docs", [])
        print(f"\n[{country}] 命中 {d.get('response',{}).get('numFound','?')}，取回 {len(docs)} 条")
        for doc in docs[:6]:
            title = str(doc.get("title") or "")[:58]
            print(f"   {doc.get('year','?')} {str(doc.get('imagecount','?')):>3}p "
                  f"{doc.get('identifier','')[:34]:34s} {title}")
        if not docs:
            print("   （无）")


if __name__ == "__main__":
    main()
