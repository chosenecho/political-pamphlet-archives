"""并入瑞士 TIFF 批次（55 件，经 Commons 缩略图接口取得 JPEG）。

这是瑞士的第二批：上一轮收了 30 件 JPEG，本轮补齐同分类下 1945 年前的
TIFF 条目——TIFF 原图浏览器显示不了，改用 MediaWiki 的 iiurlwidth
接口取 1920px JPEG 缩略图，再统一压到 2000px 以内。
"""

import json
import os
import re
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import index as catalog
from lib import paths

IMG = paths.IMAGES
ROOT = os.path.join(IMG, "swiss-tiff")
RAW = os.path.join(ROOT, "raw")
SINGLES = os.path.join(IMG, "传单与海报", "按国别")

BAD_CHARS = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=70):
    s = BAD_CHARS.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def norm(t):
    s = re.sub(r"[^\w]+", "", str(t).lower(), flags=re.UNICODE)
    return s[:40]


def ensure_country_dir(country):
    if os.path.isdir(SINGLES):
        for d in os.listdir(SINGLES):
            if d.endswith(country) and os.path.isdir(os.path.join(SINGLES, d)):
                return f"传单与海报/按国别/{d}"
    raise SystemExit(f"找不到 {country} 的单页目录")


def main():
    dry = "--dry" in sys.argv
    meta_path = os.path.join(ROOT, "metadata.json")
    if not os.path.exists(meta_path):
        print("没有 metadata.json")
        return 1

    items = json.load(open(meta_path, encoding="utf-8"))
    records = catalog.load()
    have = {norm(r.get("title", "")) for r in records}
    have.discard("")

    rel_dir = ensure_country_dir("瑞士")
    added, skipped = [], []

    for it in items:
        key = norm(it["title"])
        if key in have:
            skipped.append((it["title"], "标题已收录"))
            continue
        src = os.path.join(RAW, f"{it['no']:03d}", "p-00001.jpg")
        if not os.path.exists(src):
            skipped.append((it["title"], "文件缺失"))
            continue

        stem = safe(os.path.splitext(it["title"])[0])
        rel = f"{rel_dir}/{stem}.jpg"
        dst = os.path.join(IMG, rel.replace("/", os.sep))
        if dry:
            print(f"  [预演] {it['year']} {rel[:70]}")
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            n = 2
            while os.path.exists(dst):
                rel = f"{rel_dir}/{stem}_{n}.jpg"
                dst = os.path.join(IMG, rel.replace("/", os.sep))
                n += 1
            shutil.move(src, dst)
            print(f"  并入 {it['year']} {rel[:64]}", flush=True)

        added.append({
            "kind": "单页", "country": "瑞士", "year": str(it["year"]),
            "title": it["title"], "title_zh": "", "pages": 1,
            "dir": rel_dir, "cover": rel, "pdf": "",
            "url": it.get("desc_url", ""), "stance": "",
            "source": "wiki-commons",
        })
        have.add(key)

    print(f"\n可并入 {len(added)} 件，跳过 {len(skipped)} 件")
    for t, why in skipped:
        print(f"  跳过（{why}）{t[:56]}")

    if dry:
        return 0

    if added:
        catalog.save(records + added)
        print("已写入 data/catalog.json")

    if os.path.isdir(RAW) and not [d for d in os.listdir(RAW)
                                   if os.path.isdir(os.path.join(RAW, d))]:
        shutil.rmtree(ROOT, ignore_errors=True)

    allr = catalog.load()
    print(f"\n目录合计 {len(allr)} 条，瑞士 "
          f"{sum(1 for r in allr if r['country']=='瑞士')} 件")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
