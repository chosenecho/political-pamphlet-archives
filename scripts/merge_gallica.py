"""把 Gallica 抓到的法国小册子并入合集。"""

import json
import os
import re
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")
SRC = os.path.join(IMG, "gallica", "raw")
BK = os.path.join(IMG, "小册子")
BAD = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=48):
    s = BAD.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


meta = json.load(open(os.path.join(IMG, "gallica", "metadata.json"), encoding="utf-8"))
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
    rel = f"{have+1:03d}_{rec['year']}_{safe(rec['title'])}"
    dst = os.path.join(cdir, rel)
    if not os.path.isdir(dst):
        shutil.move(src, dst)
    index.append({
        "kind": "小册子", "country": "法国", "year": str(rec["year"]),
        "title": rec["title"], "pages": pages,
        "dir": f"小册子/法国/{rel}",
        "cover": f"小册子/法国/{rel}/pages/p-00001.jpg",
        "pdf": None, "url": rec["url"],
    })
    added += 1

shutil.rmtree(os.path.join(IMG, "gallica"), ignore_errors=True)
for f in ("_gal核对.jpg", "_gal内页.jpg"):
    p = os.path.join(IMG, f)
    if os.path.exists(p):
        os.remove(p)

json.dump(index, open(os.path.join(IMG, "索引.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

book = [r for r in index if r["kind"] == "小册子"]
from collections import Counter
print(f"并入 {added} 本，小册子合计 {len(book)} 本，{sum(r['pages'] for r in book)} 页")
for k, v in Counter(r["country"] for r in book).most_common():
    print(f"   {k:5s} {v}")
