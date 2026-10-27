"""并入 Europeana 中人工核对的 3 本，其余丢弃。"""

import json
import os
import re
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")
SRC = os.path.join(IMG, "europeana", "raw")
BK = os.path.join(IMG, "小册子")

# 人工核对通过：(目录号, 国别, 标题覆盖)
KEEP = [
    ("001", "奥地利", ""),   # Waffenstillstand oder Winter-Feldzug, Wiener Montagblatt
    ("011", "匈牙利", ""),   # Halál a halálbüntetésre!
    ("012", "匈牙利", ""),   # Politikai röpirat
]

meta = {f"{r['no']:03d}": r for r in json.load(
    open(os.path.join(IMG, "europeana", "metadata.json"), encoding="utf-8"))}
index = json.load(open(os.path.join(IMG, "索引.json"), encoding="utf-8"))
BAD = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=48):
    s = BAD.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


added = 0
for fid, country, _ in KEEP:
    src = os.path.join(SRC, fid)
    m = meta.get(fid, {})
    if not os.path.isdir(src):
        print("缺失", fid)
        continue
    title = m.get("title") or fid
    year = m.get("year") or ""
    cdir = os.path.join(BK, country)
    os.makedirs(cdir, exist_ok=True)
    have = len([d for d in os.listdir(cdir) if os.path.isdir(os.path.join(cdir, d))])
    rel = f"{have+1:03d}_{year}_{safe(title)}"
    dst = os.path.join(cdir, rel)
    if not os.path.isdir(dst):
        shutil.move(src, dst)
    pages = len([f for f in os.listdir(os.path.join(dst, "pages")) if f.endswith(".jpg")])
    index.append({
        "kind": "小册子", "country": country, "year": str(year), "title": title,
        "pages": pages, "dir": f"小册子/{country}/{rel}",
        "cover": f"小册子/{country}/{rel}/pages/p-00001.jpg",
        "pdf": f"小册子/{country}/{rel}/doc.pdf" if os.path.exists(os.path.join(dst, "doc.pdf")) else None,
        "url": m.get("url", ""),
    })
    added += 1

shutil.rmtree(os.path.join(IMG, "europeana"), ignore_errors=True)
p = os.path.join(IMG, "_eu核对2.jpg")
if os.path.exists(p):
    os.remove(p)

json.dump(index, open(os.path.join(IMG, "索引.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

book = [r for r in index if r["kind"] == "小册子"]
from collections import Counter
print(f"新增 {added}，小册子合计 {len(book)} 本，{sum(r['pages'] for r in book)} 页")
for k, v in Counter(r["country"] for r in book).most_common():
    print(f"   {k:5s} {v}")
