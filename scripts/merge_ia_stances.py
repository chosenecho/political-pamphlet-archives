"""并入 IA 分立场采集，按人工核对结果保留 19 本。"""

import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

IMG = paths.IMAGES
ROOT = os.path.join(IMG, "ia-stance")
SRC = os.path.join(ROOT, "raw")
BK = os.path.join(IMG, "小册子")

# (目录号, 国别, 立场)
KEEP = {
    "001": ("德国", "纳粹主义"),
    "002": ("德国", "纳粹主义"),
    "003": ("德国", "纳粹主义"),
    "004": ("德国", "无政府主义"),
    "006": ("意大利", "法西斯主义"),
    "012": ("西班牙", "右翼史论"),
    "013": ("西班牙", "社会主义"),
    "014": ("西班牙", "社会主义"),
    "015": ("西班牙", "社会主义"),
    "017": ("法国", "共产主义"),
    "018": ("法国", "工团主义"),
    "019": ("法国", "右翼论战"),
    "020": ("法国", "极右·行动法兰西"),
    "021": ("法国", "民族主义"),
    "024": ("俄国", "白俄·临时政府"),
    "026": ("俄国", "布尔什维克"),
    "027": ("俄国", "布尔什维克"),
    "028": ("俄国", "共青团"),
    "030": ("荷兰", "选举权"),
}

meta = {f"{r['no']:03d}": r for r in json.load(
    open(os.path.join(ROOT, "metadata.json"), encoding="utf-8"))}
index = catalog.load()
BAD = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=44):
    s = BAD.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


added = 0
for fid, (country, stance) in KEEP.items():
    src = os.path.join(SRC, fid)
    m = meta.get(fid, {})
    if not os.path.isdir(src):
        print("缺失", fid)
        continue
    pages = len([f for f in os.listdir(os.path.join(src, "pages")) if f.endswith(".jpg")])
    if pages < 4:
        continue
    cdir = os.path.join(BK, country)
    os.makedirs(cdir, exist_ok=True)
    have = len([d for d in os.listdir(cdir) if os.path.isdir(os.path.join(cdir, d))])
    rel = f"{have+1:03d}_{m.get('year','')}_{safe(m.get('title',''))}"
    dst = os.path.join(cdir, rel)
    if not os.path.isdir(dst):
        shutil.move(src, dst)
    index.append({
        "kind": "小册子", "country": country, "year": str(m.get("year", "")),
        "title": re.sub(r"<[^>]+>", "", m.get("title", "")), "pages": pages,
        "stance": stance,
        "dir": f"小册子/{country}/{rel}",
        "cover": f"小册子/{country}/{rel}/pages/p-00001.jpg",
        "pdf": f"小册子/{country}/{rel}/doc.pdf" if os.path.exists(os.path.join(dst, "doc.pdf")) else None,
        "url": m.get("url", ""),
    })
    added += 1

shutil.rmtree(ROOT, ignore_errors=True)
p = os.path.join(IMG, "_ia核对3.jpg")
if os.path.exists(p):
    os.remove(p)

catalog.save(index)

book = [r for r in index if r["kind"] == "小册子"]
from collections import Counter
print(f"并入 {added} 本，合计 {len(book)} 本 / {sum(r['pages'] for r in book)} 页")
print("\n国别：")
for k, v in Counter(r["country"] for r in book).most_common():
    print(f"   {k:5s} {v}")
print("\n立场：")
for k, v in Counter(r.get("stance") or "未标注" for r in book).most_common():
    print(f"   {k:14s} {v}")
