"""最终整理：中国 20 件多页小册子 + 国际 15 国 144 件单页素材，按国别分目录。"""

import csv
import json
import os
import re
import shutil
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

BASE = paths.BASE
IMG = paths.IMAGES
CN_SRC = os.path.join(IMG, "小册子", "raw")
CN_META = os.path.join(IMG, "小册子", "选定20.json")
INTL_SRC = os.path.join(IMG, "国际", "raw")
INTL_META = os.path.join(IMG, "国际", "精选.json")

CN = os.path.join(IMG, "中国")
INTL = os.path.join(IMG, "国际", "按国别")
SHEETS = os.path.join(IMG, "总览")

BAD = re.compile(r'[\\/:*?"<>|]+')


def safe(s, limit=44):
    s = BAD.sub("_", re.sub(r"<[^>]+>", "", str(s or "")))
    s = re.sub(r"\s+", " ", s).strip()[:limit]
    return s.strip(" ._-") or "untitled"


def font(size):
    for f in ("msyh.ttc", "simhei.ttf", "simsun.ttc"):
        p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", f)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


F_T, F_L = font(17), font(12)

# ---------- 1. 中国 ----------
cn_meta = json.load(open(CN_META, encoding="utf-8"))
os.makedirs(CN, exist_ok=True)
cn_out = []
for rec in cn_meta:
    d = os.path.join(CN_SRC, rec["id"])
    name = f'{rec["id"]}_{rec["year"]}_{safe(rec["title"])}'
    dst = os.path.join(CN, name)
    if not os.path.isdir(dst):
        shutil.move(d, dst)
    pages = len([f for f in os.listdir(os.path.join(dst, "pages")) if f.endswith(".jpg")])
    cn_out.append({"country": "中国", "id": rec["id"], "year": rec["year"],
                   "title": re.sub(r"<[^>]+>", "", rec["title"]), "pages": pages,
                   "publisher": rec.get("publisher", ""), "dir": f"中国/{name}",
                   "cover": f"中国/{name}/cover.jpg",
                   "url": "https://www.modernhistory.org.cn/#/DocumentDetails_ts_da?fileCode=" + rec.get("file_code", "")})
if os.path.isdir(CN_SRC):
    shutil.rmtree(CN_SRC)

# ---------- 2. 国际 ----------
intl_meta = json.load(open(INTL_META, encoding="utf-8"))
os.makedirs(INTL, exist_ok=True)
intl_out = []
by_country = {}
for r in intl_meta:
    by_country.setdefault(r["country"], []).append(r)

ORDER = ["俄国", "德国", "法国", "英国", "美国", "意大利", "西班牙", "葡萄牙",
         "荷兰", "奥地利", "捷克", "波兰", "日本", "印度", "拉美"]
for i, c in enumerate(ORDER, 1):
    if c in by_country:
        by_country[c] = sorted(by_country[c], key=lambda x: x["year"])
        globals().setdefault("_cd", {})[c] = f"{i:02d}-{c}"

for c, items in by_country.items():
    folder = os.path.join(INTL, f"{ORDER.index(c)+1:02d}-{c}" if c in ORDER else c)
    os.makedirs(folder, exist_ok=True)
    for j, r in enumerate(items, 1):
        src = os.path.join(INTL_SRC, r["file"])
        nm = f'{j:03d}_{r["year"]}_{safe(r["title"], 40)}.jpg'
        dst = os.path.join(folder, nm)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.move(src, dst)
        if os.path.exists(dst):
            rel = os.path.relpath(dst, IMG).replace("\\", "/")
            intl_out.append({"country": c, "year": r["year"], "title": r["title"],
                             "license": r.get("license", ""), "credit": r.get("credit", ""),
                             "cover": rel, "dir": os.path.dirname(rel), "pages": 1,
                             "url": r.get("descurl", "")})
# 清掉国际临时目录
for p in (INTL_SRC, os.path.join(IMG, "国际", "raw")):
    if os.path.isdir(p):
        shutil.rmtree(p)

# ---------- 3. 目录 ----------
allrec = cn_out + intl_out
catalog.save(allrec)

with open(os.path.join(IMG, "目录.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["国别", "年份", "标题", "页数", "出版者/来源", "许可", "本地路径", "来源链接"])
    for r in allrec:
        w.writerow([r["country"], r["year"], r["title"], r["pages"],
                    r.get("publisher") or r.get("credit", ""), r.get("license", ""),
                    r["dir"], r["url"]])

# ---------- 4. 每国总览 ----------
os.makedirs(SHEETS, exist_ok=True)
COLS, CW, CH = 6, 200, 280
groups = {}
for r in allrec:
    groups.setdefault(r["country"], []).append(r)

for c, items in sorted(groups.items()):
    cells = []
    for r in items:
        fp = os.path.join(IMG, r["cover"])
        if not os.path.exists(fp):
            continue
        try:
            im = Image.open(fp).convert("RGB")
            im.thumbnail((CW - 10, CH - 10), Image.LANCZOS)
            cells.append((r, im))
        except Exception:
            pass
    if not cells:
        continue
    rows = (len(cells) + COLS - 1) // COLS
    pad, top = 8, 46
    W = COLS * (CW + pad) + pad
    H = top + rows * (CH + pad + 20) + pad
    sh = Image.new("RGB", (W, H), (247, 246, 243))
    dr = ImageDraw.Draw(sh)
    dr.text((pad + 2, 13), f"{c} · {len(cells)} 件", fill=(30, 30, 30), font=F_T)
    for i, (r, im) in enumerate(cells):
        cx = pad + (i % COLS) * (CW + pad)
        cy = top + (i // COLS) * (CH + pad + 20)
        dr.rectangle([cx, cy, cx + CW, cy + CH], fill=(232, 230, 225))
        sh.paste(im, (cx + (CW - im.width) // 2, cy + (CH - im.height) // 2))
        dr.text((cx + 3, cy + CH + 3), f'{r["year"]} {r["title"][:14]}', fill=(85, 85, 85), font=F_L)
    sh.save(os.path.join(SHEETS, f"{c}.jpg"), "JPEG", quality=84)

print(f"中国 {len(cn_out)} 件 / 国际 {len(intl_out)} 件 / 合计 {len(allrec)} 件")
print("国别分布：")
from collections import Counter
for k, v in Counter(r["country"] for r in allrec).most_common():
    print(f"   {k:6s} {v:3d}")
