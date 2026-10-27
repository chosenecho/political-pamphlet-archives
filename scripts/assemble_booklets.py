"""组装最终结构：只把小册子放进主目录，单页传单/海报另置，互不混淆。"""

import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

BASE = paths.BASE
IMG = paths.IMAGES
RAW = os.path.join(IMG, "小册子国际", "raw")

# 经人工核对可用的小册子：(目录号, 国别, 年份, 标题)
KEEP = [
    ("001", "美国", "1946", "Voters' Pamphlet 1946"),
    ("002", "美国", "1966", "Voters' Pamphlet 1966"),
    ("003", "美国", "1960", "Voters' Pamphlet 1960"),
    ("004", "美国", "1962", "Voters' Pamphlet 1962"),
    ("005", "美国", "1983", "Voters' Pamphlet 1983"),
    ("027", "美国", "1942", "Voters' Pamphlet 1942"),
    ("028", "美国", "1975", "Voters' Pamphlet 1975"),
    ("029", "美国", "1924", "Voters' Pamphlet 1924"),
    ("032", "美国", "1896", "Address to the People of Delaware on the Approaching Presidential Election"),
    ("033", "美国", "1840", "Address to the People of Rhode Island on the Approaching Election"),
    ("034", "美国", "1840", "An Address to the People of the United States on the Presidential Election"),
    ("036", "美国", "1936", "The Communist Election Platform, 1936"),
    ("037", "美国", "1940", "Election Platform of the Communist Party of the U.S.A., 1940"),
    ("031", "英国", "1957", "Fabian Tract"),
    ("038", "法国", "1830", "Profession de foi des libéraux"),
    ("039", "德国", "1848", "Manifesto of the Communist Party"),
]

BAD = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=52):
    s = BAD.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


BK = os.path.join(IMG, "小册子")
os.makedirs(BK, exist_ok=True)

# 中国 20 本已在 images/中国
cn_src = os.path.join(IMG, "中国")
cn_dst = os.path.join(BK, "中国")
if os.path.isdir(cn_src) and not os.path.isdir(cn_dst):
    shutil.move(cn_src, cn_dst)

index = []
cn_old = catalog.load()
for r in cn_old:
    if r["country"] != "中国":
        continue
    index.append({"kind": "小册子", "country": "中国", "year": str(r["year"]),
                  "title": r["title"], "pages": r["pages"],
                  "dir": "小册子/" + r["dir"], "cover": "小册子/" + r["cover"],
                  "pdf": None, "url": r["url"]})

for fid, country, year, title in KEEP:
    src = os.path.join(RAW, fid)
    if not os.path.isdir(src):
        print("缺失", fid)
        continue
    folders = [f for f in os.listdir(os.path.join(BK, country))] if os.path.isdir(os.path.join(BK, country)) else []
    rel = f"{len(folders)+1:03d}_{year}_{safe(title)}"
    dst = os.path.join(BK, country, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.isdir(dst):
        shutil.move(src, dst)
    pages = [f for f in os.listdir(os.path.join(dst, "pages")) if f.endswith(".jpg")]
    index.append({"kind": "小册子", "country": country, "year": year, "title": title,
                  "pages": len(pages), "dir": f"小册子/{country}/{rel}",
                  "cover": f"小册子/{country}/{rel}/pages/p-00001.jpg",
                  "pdf": f"小册子/{country}/{rel}/doc.pdf" if os.path.exists(os.path.join(dst, "doc.pdf")) else None,
                  "url": "https://commons.wikimedia.org/"})

# 单页宣传品另置
src_intl = os.path.join(IMG, "国际")
if os.path.isdir(src_intl):
    os.makedirs(os.path.join(IMG, "传单与海报"), exist_ok=True)
    for r in cn_old:
        if r["country"] == "中国":
            continue
        s = os.path.join(IMG, r["cover"])
        d = os.path.join(IMG, "传单与海报", r["cover"].replace("国际/", ""))
        if os.path.exists(s):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            if not os.path.exists(d):
                shutil.move(s, d)
            index.append({"kind": "单页", "country": r["country"], "year": str(r["year"]),
                          "title": r["title"], "pages": 1,
                          "dir": os.path.dirname(d).replace(IMG + os.sep, "").replace("\\", "/"),
                          "cover": d.replace(IMG + os.sep, "").replace("\\", "/"),
                          "pdf": None, "url": r["url"]})
    shutil.rmtree(src_intl, ignore_errors=True)

for junk in ("小册子国际", "总览", "_核对.jpg"):
    p = os.path.join(IMG, junk)
    if os.path.isdir(p):
        shutil.rmtree(p)
    elif os.path.exists(p):
        os.remove(p)

catalog.save(index)

bk = [r for r in index if r["kind"] == "小册子"]
print(f"小册子 {len(bk)} 本（中国 {sum(1 for r in bk if r['country']=='中国')}，国际 {sum(1 for r in bk if r['country']!='中国')}）")
print(f"单页 {len(index)-len(bk)} 件（另置，不计入小册子）")
from collections import Counter
for k, v in Counter(r["country"] for r in bk).most_common():
    print(f"   {k:5s} {v}")
