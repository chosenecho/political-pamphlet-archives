"""查询单条 identifier 的完整 metadata，用于核验国别判定。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http

for ident in sys.argv[1:]:
    try:
        d = http.fetch_json(f"https://archive.org/metadata/{ident}", timeout=45)
    except Exception as e:
        print(f"--- {ident} 失败 {type(e).__name__}")
        continue
    md = d.get("metadata", {}) or {}
    print(f"--- {ident}  （metadata 键 {len(md)} 个）")
    for k in ("title", "creator", "publisher", "subject", "date", "year", "language"):
        v = md.get(k)
        if v:
            print(f"    {k:10s} {str(v)[:150]}")
