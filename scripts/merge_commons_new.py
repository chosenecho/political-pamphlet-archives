"""把 Commons 采到的单页宣传品并入 catalog。

与 IA 小册子批次不同，Commons 这批是**单页**（kind=单页），
目录结构沿用既有的 传单与海报/按国别/NN-国别。

并入规则：
  - 国家目录若不存在则按既有次序表新建
  - 文件名沿用 Commons 原始文件名（去扩展名），保留可回溯性
  - stance 用采集时的判定；title_zh 待后续统一补

用法：
    python scripts/merge_commons_new.py --dry
    python scripts/merge_commons_new.py
"""

import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

IMG = paths.IMAGES
ROOT = os.path.join(IMG, "commons-new")
RAW = os.path.join(ROOT, "raw")
SINGLES = os.path.join(IMG, "传单与海报", "按国别")

BAD_CHARS = re.compile(r'[\\/:*?"<>|]+')

#: 国别目录次序（与既有目录一致；新国别追加在后）
ORDER = ["俄国", "德国", "法国", "英国", "美国", "意大利", "西班牙", "葡萄牙",
         "荷兰", "奥地利", "匈牙利", "捷克", "波兰", "拉美", "印度", "日本",
         "中国", "爱尔兰"]


def safe(s, n=60):
    s = BAD_CHARS.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def ensure_country_dir(country):
    """返回该国别的单页目录（相对 images/）。"""
    if os.path.isdir(SINGLES):
        for d in os.listdir(SINGLES):
            if d.endswith(country) and os.path.isdir(os.path.join(SINGLES, d)):
                return f"传单与海报/按国别/{d}"
    # 新建
    existing = [d for d in os.listdir(SINGLES)] if os.path.isdir(SINGLES) else []
    nums = [int(m.group(1)) for d in existing
            if (m := re.match(r"(\d+)", d))]
    idx = ORDER.index(country) + 1 if country in ORDER else len(existing) + 1
    while f"{idx:02d}-{country}" in existing:
        idx += 1
    name = f"{idx:02d}-{country}"
    os.makedirs(os.path.join(SINGLES, name), exist_ok=True)
    return f"传单与海报/按国别/{name}"


def main():
    dry = "--dry" in sys.argv
    if not os.path.exists(os.path.join(ROOT, "metadata.json")):
        print("没有 metadata.json")
        return 1

    items = json.load(open(os.path.join(ROOT, "metadata.json"), encoding="utf-8"))
    records = catalog.load()
    have_titles = {re.sub(r"[^a-z0-9]+", "", r.get("title", "").lower())[:30]
                   for r in records}

    added, skipped = [], []
    for it in items:
        key = re.sub(r"[^a-z0-9]+", "", it["title"].lower())[:30]
        if key in have_titles:
            skipped.append((it["title"], "标题已收录"))
            continue
        folder = os.path.join(RAW, f"{it['no']:03d}")
        src = os.path.join(folder, "p-00001.jpg")
        if not os.path.exists(src):
            skipped.append((it["title"], "文件缺失"))
            continue

        country = it["country"]
        rel_dir = ensure_country_dir(country)
        stem = safe(os.path.splitext(it["title"])[0])
        rel = f"{rel_dir}/{stem}.jpg"
        dst = os.path.join(IMG, rel.replace("/", os.sep))

        if dry:
            print(f"  [预演] {country:4s} {it['year']} {rel}")
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(dst):
                n = 2
                while os.path.exists(dst):
                    rel = f"{rel_dir}/{stem}_{n}.jpg"
                    dst = os.path.join(IMG, rel.replace("/", os.sep))
                    n += 1
            shutil.move(src, dst)
            print(f"  并入 {country:4s} {it['year']} {rel[:64]}", flush=True)

        added.append({
            "kind": "单页",
            "country": country,
            "year": str(it["year"]),
            "title": it["title"],
            "title_zh": "",
            "pages": 1,
            "dir": rel_dir,
            "cover": rel,
            "pdf": "",
            "url": it.get("desc_url", ""),
            "stance": it.get("stance", ""),
            "source": "",       # Commons 不在 sources.json 的专藏表内
        })
        have_titles.add(key)

    print(f"\n可并入 {len(added)} 件，跳过 {len(skipped)} 件")
    for t, why in skipped:
        print(f"  跳过（{why}）{t[:60]}")

    if dry:
        return 0

    if added:
        catalog.save(records + added)
        print("已写入 data/catalog.json")

    if os.path.isdir(RAW) and not [d for d in os.listdir(RAW)
                                   if os.path.isdir(os.path.join(RAW, d))]:
        shutil.rmtree(RAW, ignore_errors=True)

    allr = catalog.load()
    from collections import Counter
    print(f"\n目录合计 {len(allr)} 条")
    print("单页国别：")
    for k, v in Counter(r["country"] for r in allr
                        if r["kind"] == "单页").most_common():
        print(f"   {k:6s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
