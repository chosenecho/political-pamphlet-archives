"""并入 Gallica 分立场采集结果，并把立场标签写进索引。"""

import json
import os
import re
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")
ROOT = os.path.join(IMG, "gallica2")
SRC = os.path.join(ROOT, "raw")
BK = os.path.join(IMG, "小册子")
BAD = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=46):
    s = BAD.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


meta = json.load(open(os.path.join(ROOT, "metadata.json"), encoding="utf-8"))
index = json.load(open(os.path.join(IMG, "索引.json"), encoding="utf-8"))

added = 0
for rec in meta:
    fid = f"{rec['no']:03d}"
    src = os.path.join(SRC, fid)
    if not os.path.isdir(src):
        continue
    pages = len([f for f in os.listdir(os.path.join(src, "pages")) if f.endswith(".jpg")])
    if pages < 4:
        continue
    cdir = os.path.join(BK, "法国")
    os.makedirs(cdir, exist_ok=True)
    have = len([d for d in os.listdir(cdir) if os.path.isdir(os.path.join(cdir, d))])
    rel = f"{have+1:03d}_{rec['year'] or '无年'}_{safe(rec['title'])}"
    dst = os.path.join(cdir, rel)
    if not os.path.isdir(dst):
        shutil.move(src, dst)
    index.append({
        "kind": "小册子", "country": "法国", "year": str(rec["year"] or ""),
        "title": rec["title"], "pages": pages, "stance": rec.get("stance", ""),
        "dir": f"小册子/法国/{rel}",
        "cover": f"小册子/法国/{rel}/pages/p-00001.jpg",
        "pdf": None, "url": rec["url"],
    })
    added += 1

shutil.rmtree(ROOT, ignore_errors=True)
json.dump(index, open(os.path.join(IMG, "索引.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

book = [r for r in index if r["kind"] == "小册子"]
from collections import Counter
print(f"并入 {added} 本，小册子合计 {len(book)} 本，{sum(r['pages'] for r in book)} 页")
for k, v in Counter(r["country"] for r in book).most_common():
    print(f"   {k:5s} {v}")
print("\n立场分布：")
for k, v in Counter(r.get("stance") or "未标注" for r in book).most_common():
    print(f"   {k:10s} {v}")
