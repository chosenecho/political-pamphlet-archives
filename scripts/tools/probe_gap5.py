"""探针 5：为意大利/奥地利/匈牙利/荷兰/西班牙找可用的检索式。

前几轮这五国命中为 0 或不合格，逐条试不同字段组合，看哪条真能捞出政宣小册子。
"""

import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http

TESTS = [
    ("IT subject:fascismo", 'subject:(fascismo OR fascista OR "partito nazionale fascista")'),
    ("IT title:ita", 'title:(fascismo OR fascista OR mussolini OR partito) AND language:ita'),
    ("IT subject:ita-any", 'subject:(politica OR partito OR italia) AND language:ita'),
    ("AT subject", 'subject:("sozialdemokratie" OR "christlichsozial" OR oesterreich)'),
    ("AT title", 'title:(wahlprogramm OR parteiprogramm OR parteitag OR oesterreich)'),
    ("AT lang-ger", 'language:ger AND subject:(politik OR sozialismus) AND year:[1880 TO 1934]'),
    ("HU subject", 'subject:(politika OR szocializmus OR valasztas OR tortenelem)'),
    ("HU lang", 'language:hun AND subject:(politika OR tarsadalom)'),
    ("NL subject", 'subject:(socialisme OR "sociaal-democratisch" OR sdap OR katholiek)'),
    ("NL lang", 'language:dut AND subject:(politiek OR socialisme)'),
    ("ES subject", 'subject:(falange OR anarquismo OR socialismo OR republica)'),
    ("ES lang", 'language:spa AND subject:(politica OR socialismo) AND year:[1900 TO 1939]'),
]


def search(q, rows=25):
    params = {
        "q": q,
        "fl[]": ["identifier", "title", "year", "language", "imagecount"],
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
            print(f"[{label}] 失败 {type(e).__name__}")
            continue
        resp = d.get("response") or {}
        print(f"\n[{label}] numFound={resp.get('numFound')}")
        for doc in resp.get("docs", [])[:5]:
            print(f"   {str(doc.get('year')):6s} {str(doc.get('imagecount')):>3}p "
                  f"{str(doc.get('language'))[:8]:8s} {str(doc.get('identifier'))[:30]:30s} "
                  f"{str(doc.get('title'))[:44]}")


if __name__ == "__main__":
    main()
