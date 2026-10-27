"""把人工核对通过的欧洲小册子并入合集；元数据按采集日志重建。"""

import json
import os
import re
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")
SRC = os.path.join(IMG, "ia-eu", "raw")
BK = os.path.join(IMG, "小册子")

# (目录号, 国别, 年份, 标题) —— 人工核对通过
KEEP = [
    ("001", "德国", "1913", "Graf Hoensbroechs Antwort an von Nostitz-Rieneck"),
    ("005", "法国", "1892", "Élections provinciales du 8 mars 1892 : état de la question"),
    ("006", "法国", "1892", "Le Scandale du chemin de fer de la Baie des Chaleurs"),
    ("007", "法国", "1881", "Quelques notes pour servir pendant la présente session"),
    ("010", "俄国", "1919", "Образование Северо-Западного правительства"),
    ("012", "俄国", "1919", "Беларусь: политический очерк"),
    ("014", "意大利", "1903", "Vecchie e nuove aristocrazie"),
]

index = json.load(open(os.path.join(IMG, "索引.json"), encoding="utf-8"))
BAD = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=48):
    s = BAD.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


added = 0
for fid, country, year, title in KEEP:
    src = os.path.join(SRC, fid)
    if not os.path.isdir(src):
        print("缺失", fid)
        continue
    cdir = os.path.join(BK, country)
    os.makedirs(cdir, exist_ok=True)
    have = len([d for d in os.listdir(cdir) if os.path.isdir(os.path.join(cdir, d))])
    rel = f"{have+1:03d}_{year}_{safe(title)}"
    dst = os.path.join(cdir, rel)
    if not os.path.isdir(dst):
        shutil.move(src, dst)
    pages = len([f for f in os.listdir(os.path.join(dst, "pages")) if f.endswith(".jpg")])
    index.append({
        "kind": "小册子", "country": country, "year": year, "title": title,
        "pages": pages, "dir": f"小册子/{country}/{rel}",
        "cover": f"小册子/{country}/{rel}/pages/p-00001.jpg",
        "pdf": f"小册子/{country}/{rel}/doc.pdf" if os.path.exists(os.path.join(dst, "doc.pdf")) else None,
        "url": "",
    })
    added += 1

shutil.rmtree(os.path.join(IMG, "ia-eu"), ignore_errors=True)
for f in ("_eu核对.jpg",):
    p = os.path.join(IMG, f)
    if os.path.exists(p):
        os.remove(p)

json.dump(index, open(os.path.join(IMG, "索引.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

book = [r for r in index if r["kind"] == "小册子"]
from collections import Counter
print(f"新增 {added} 本，小册子合计 {len(book)} 本，{sum(r['pages'] for r in book)} 页")
for k, v in Counter(r["country"] for r in book).most_common():
    print(f"   {k:5s} {v}")
