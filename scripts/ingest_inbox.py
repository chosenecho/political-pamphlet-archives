"""接入工作流：把手工获取的 PDF/图片放进 inbox/，自动归入小册子合集。

用法：
    python scripts/ingest_inbox.py                # 预览
    python scripts/ingest_inbox.py --commit       # 实际并入

inbox/ 目录结构（可任意深，按子目录推断国别）：
    inbox/德国/*.pdf
    inbox/法国/*.pdf
国家名必须是 images/小册子/ 下已有目录名，或下列允许值之一。
"""

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
INBOX = paths.INBOX
BK = os.path.join(IMG, "小册子")

COUNTRIES = ["中国", "美国", "英国", "法国", "德国", "俄国", "意大利", "西班牙",
             "葡萄牙", "荷兰", "奥地利", "捷克", "波兰", "匈牙利", "瑞典",
             "丹麦", "芬兰", "比利时", "爱尔兰", "印度", "拉美"]
BAD = re.compile(r'[\\/:*?"<>|]+')
MINP, MAXP = 2, 200


def safe(s, n=48):
    s = BAD.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def guess_year(name):
    m = re.search(r"(1[89]\d{2}|19\d{2})", name)
    return m.group(1) if m else ""


def render_pdf(pdf, outdir, width=1000):
    try:
        import fitz
    except ImportError:
        raise SystemExit("需要 PyMuPDF：pip install pymupdf（用 Python 3.12 运行）")
    os.makedirs(outdir, exist_ok=True)
    doc = fitz.open(pdf)
    n = doc.page_count
    for i in range(n):
        page = doc.load_page(i)
        zoom = width / page.rect.width if page.rect.width else 1
        doc.load_page(i).get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(
            os.path.join(outdir, f"p-{i+1:05d}.jpg"))
    doc.close()
    return n


commit = "--commit" in sys.argv
if not os.path.isdir(INBOX):
    os.makedirs(INBOX, exist_ok=True)
    for c in ("德国", "法国", "英国", "意大利", "西班牙"):
        os.makedirs(os.path.join(INBOX, c), exist_ok=True)
    print(f"已创建 inbox/ 及示例子目录（按国别）。把 PDF 放进去后重跑。")
    sys.exit(0)

found = []
for root, _, files in os.walk(INBOX):
    for f in files:
        if f.lower().endswith(".pdf"):
            found.append(os.path.join(root, f))
        elif f.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
            found.append(os.path.join(root, f))

if not found:
    print("inbox/ 里没有文件。按国别建子目录，把 PDF 或扫描图放进去。")
    sys.exit(0)

index = catalog.load()
added = 0
for path in found:
    rel_dir = os.path.relpath(os.path.dirname(path), INBOX)
    country = rel_dir.split(os.sep)[0] if rel_dir != "." else ""
    if country not in COUNTRIES:
        print(f"跳过（无法判定国别）: {os.path.relpath(path, INBOX)}")
        continue
    name = os.path.splitext(os.path.basename(path))[0]
    title = re.sub(r"[_]+", " ", name).strip()
    year = guess_year(name)

    if not commit:
        print(f"[预览] {country} {year} {title[:50]}")
        continue

    cdir = os.path.join(BK, country)
    os.makedirs(cdir, exist_ok=True)
    have = len([d for d in os.listdir(cdir) if os.path.isdir(os.path.join(cdir, d))])
    item = f"{have+1:03d}_{year}_{safe(title)}"
    dst = os.path.join(cdir, item)
    os.makedirs(os.path.join(dst, "pages"), exist_ok=True)

    if path.lower().endswith(".pdf"):
        shutil.copy2(path, os.path.join(dst, "doc.pdf"))
        pages = render_pdf(path, os.path.join(dst, "pages"))
    else:
        pages = render_pdf(path, os.path.join(dst, "pages")) if path.lower().endswith(
            (".tif", ".tiff")) else 0
        if pages == 0:
            shutil.copy2(path, os.path.join(dst, "pages", "p-00001.jpg"))
            pages = 1

    if not (MINP <= pages <= MAXP):
        shutil.rmtree(dst)
        print(f"跳过（{pages} 页，不在 {MINP}-{MAXP} 范围）: {title[:40]}")
        continue

    index.append({
        "kind": "小册子", "country": country, "year": year, "title": title,
        "pages": pages, "dir": f"小册子/{country}/{item}",
        "cover": f"小册子/{country}/{item}/pages/p-00001.jpg",
        "pdf": f"小册子/{country}/{item}/doc.pdf" if os.path.exists(
            os.path.join(dst, "doc.pdf")) else None,
        "url": "",
    })
    added += 1
    print(f"并入 {country} {year} {pages}p  {title[:44]}")

if commit and added:
    catalog.save(index)
    print(f"\n完成，并入 {added} 本。接着跑：python scripts/build_catalog.py")
else:
    print(f"\n共发现 {len(found)} 个文件。加 --commit 执行并入。")
