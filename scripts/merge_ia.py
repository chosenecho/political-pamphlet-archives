"""把 Internet Archive 抓到的 18 本并入小册子合集，并重建目录。"""

import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

IMG = paths.IMAGES
IA = os.path.join(IMG, "ia")
BK = os.path.join(IMG, "小册子")

meta = json.load(open(os.path.join(IA, "metadata.json"), encoding="utf-8"))
index = catalog.load()

BAD = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=50):
    s = BAD.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


us_dir = os.path.join(BK, "美国")
os.makedirs(us_dir, exist_ok=True)
have = len([d for d in os.listdir(us_dir) if os.path.isdir(os.path.join(us_dir, d))])

added = 0
for rec in meta:
    src = os.path.join(IA, "raw", rec["no"] if isinstance(rec["no"], str) else f"{rec['no']:03d}")
    if not os.path.isdir(src):
        print("缺失", rec["no"])
        continue
    have += 1
    rel = f"{have:03d}_{rec['year']}_{safe(rec['title'])}"
    dst = os.path.join(us_dir, rel)
    if not os.path.isdir(dst):
        shutil.move(src, dst)
    pages = len([f for f in os.listdir(os.path.join(dst, "pages")) if f.endswith(".jpg")])
    index.append({
        "kind": "小册子", "country": "美国", "year": str(rec["year"]),
        "title": rec["title"], "pages": pages,
        "dir": f"小册子/美国/{rel}",
        "cover": f"小册子/美国/{rel}/pages/p-00001.jpg",
        "pdf": f"小册子/美国/{rel}/doc.pdf" if os.path.exists(os.path.join(dst, "doc.pdf")) else None,
        "url": rec["url"],
    })
    added += 1

shutil.rmtree(IA, ignore_errors=True)
catalog.save(index)

book = [r for r in index if r["kind"] == "小册子"]
from collections import Counter
print(f"新增 {added} 本，合计小册子 {len(book)} 本")
for k, v in Counter(r["country"] for r in book).most_common():
    print(f"   {k:5s} {v}")
print(f"页数范围 {min(r['pages'] for r in book)}–{max(r['pages'] for r in book)}")
