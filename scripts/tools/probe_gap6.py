"""探针 6：精确定位。

三个待解决问题：
  1. 英国 Fabian tracts 大多是装订合订本（fabiantracts0000unse_*），要单册而非合订；
  2. 英国妇女参政结果里混进美国材料，要按组织名锚定；
  3. 意大利只有零星可用项，需确认到底能收几本。
"""

import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http

TESTS = [
    ("FABIAN 单册(标题含 Tract No.)",
     'title:("Fabian tract") AND NOT title:("Fabian tracts")'),
    ("FABIAN subject 机构",
     'subject:("Fabian Society") AND NOT title:("Fabian tracts")'),
    ("FABIAN 作者锚定", 'creator:("Fabian Society") AND NOT title:("Fabian tracts")'),
    ("英国 工党 ILP 单册",
     'creator:("Independent Labour Party") OR title:("I. L. P." OR "I.L.P.")'),
    ("英国 妇女参政 组织锚定",
     'title:("Women\'s Social and Political Union" OR "National Union of Women\'s Suffrage" '
     'OR suffragette OR "Women\'s Freedom League")'),
    ("英国 费边社作者署名",
     'creator:(Webb OR Shaw OR Wells OR Cole OR Tawney OR Laski) AND subject:("Fabian Society")'),
    ("意大利 可用项",
     'language:ita AND subject:(fascismo OR "partito comunista" OR "partito socialista" '
     'OR "partito popolare") AND year:[1900 TO 1945]'),
    ("意大利 statuto/programma",
     'title:(statuto OR programma OR "relazione" OR "discorso") AND language:ita'),
    ("奥地利 政党册",
     'title:("sozialdemokratische" OR "christlichsoziale" OR "deutschnationale") AND language:ger'),
    ("爱尔兰 排除北美",
     'title:("home rule" OR "Irish question" OR "Sinn Fein" OR "Land League") '
     'AND NOT title:(Canada OR Canadian OR Montreal OR Boston OR "New York" OR Ontario)'),
]


def search(q, rows=30):
    params = {
        "q": q,
        "fl[]": ["identifier", "title", "year", "language", "imagecount", "creator"],
        "rows": str(rows),
        "output": "json",
        "sort[]": "downloads desc",
    }
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return http.fetch_json(url, timeout=60)


def main():
    for label, q in TESTS:
        full = f'{q} AND imagecount:[8 TO 64] AND year:[1840 TO 1955] AND mediatype:texts'
        try:
            d = search(full)
        except Exception as e:
            print(f"\n[{label}] 失败 {type(e).__name__}: {str(e)[:60]}")
            continue
        resp = d.get("response") or {}
        print(f"\n[{label}] numFound={resp.get('numFound')}")
        for doc in resp.get("docs", [])[:8]:
            cr = doc.get("creator")
            cr = "; ".join(cr)[:26] if isinstance(cr, list) else str(cr or "")[:26]
            print(f"   {str(doc.get('year')):6s} {str(doc.get('imagecount')):>3}p "
                  f"{cr:26s} {str(doc.get('identifier'))[:30]:30s} "
                  f"{str(doc.get('title'))[:42]}")


if __name__ == "__main__":
    main()
