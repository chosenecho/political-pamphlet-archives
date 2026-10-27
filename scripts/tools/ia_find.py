"""按标题词查 identifier，并打印完整 metadata。用于核验被截断的 identifier。"""

import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http


def search(q, rows=10):
    params = {"q": q, "fl[]": ["identifier", "title", "year", "imagecount"],
              "rows": str(rows), "output": "json"}
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return http.fetch_json(url, timeout=60)


def show(ident):
    try:
        d = http.fetch_json(f"https://archive.org/metadata/{ident}", timeout=45)
    except Exception as e:
        print(f"    metadata 失败 {type(e).__name__}")
        return
    md = d.get("metadata", {}) or {}
    print(f"    metadata 键 {len(md)} 个")
    for k in ("title", "creator", "publisher", "subject", "date", "year", "language"):
        v = md.get(k)
        if v:
            print(f"      {k:10s} {str(v)[:150]}")


if __name__ == "__main__":
    for q in sys.argv[1:]:
        print(f"=== {q}")
        try:
            d = search(q)
        except Exception as e:
            print(f"  检索失败 {type(e).__name__}")
            continue
        for doc in (d.get("response") or {}).get("docs", []):
            print(f"  {doc.get('identifier')}  | {doc.get('year')} | "
                  f"{str(doc.get('title'))[:60]}")
            show(doc.get("identifier"))
