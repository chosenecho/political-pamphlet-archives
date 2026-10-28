"""并入第三批补采（53 件）：美国妇女参政为主，另有英法德奥荷西爱。

美国妇女参政是此前只有少量单页的主题，本轮补 22 件。
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
ROOT = os.path.join(IMG, "round7")
RAW = os.path.join(ROOT, "raw")
SINGLES = os.path.join(IMG, "传单与海报", "按国别")

BAD_CHARS = re.compile(r'[\\/:*?"<>|]+')
ORDER = ["俄国", "德国", "法国", "英国", "美国", "意大利", "西班牙", "葡萄牙",
         "荷兰", "奥地利", "匈牙利", "捷克", "波兰", "拉美", "印度", "日本",
         "中国", "爱尔兰", "比利时", "瑞典", "苏联", "瑞士"]


def safe(s, n=70):
    s = BAD_CHARS.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def norm(t):
    return re.sub(r"[^\w]+", "", str(t).lower(), flags=re.UNICODE)[:40]


def ensure_country_dir(country):
    if os.path.isdir(SINGLES):
        for d in os.listdir(SINGLES):
            if d.endswith(country) and os.path.isdir(os.path.join(SINGLES, d)):
                return f"传单与海报/按国别/{d}"
    existing = os.listdir(SINGLES) if os.path.isdir(SINGLES) else []
    idx = ORDER.index(country) + 1 if country in ORDER else len(existing) + 1
    while f"{idx:02d}-{country}" in existing:
        idx += 1
    name = f"{idx:02d}-{country}"
    os.makedirs(os.path.join(SINGLES, name), exist_ok=True)
    return f"传单与海报/按国别/{name}"


def main():
    dry = "--dry" in sys.argv
    items = json.load(open(os.path.join(ROOT, "metadata.json"), encoding="utf-8"))
    records = catalog.load()
    have = {norm(r.get("title", "")) for r in records}
    have.discard("")

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

        country = it["country"]
        rel_dir = ensure_country_dir(country)
        stem = safe(os.path.splitext(it["title"])[0])
        rel = f"{rel_dir}/{stem}.jpg"
        dst = os.path.join(IMG, rel.replace("/", os.sep))
        if dry:
            print(f"  [预演] {country:4s} {it['year']} [{it['stance']:8s}] {rel[:60]}")
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            n = 2
            while os.path.exists(dst):
                rel = f"{rel_dir}/{stem}_{n}.jpg"
                dst = os.path.join(IMG, rel.replace("/", os.sep))
                n += 1
            shutil.move(src, dst)
            print(f"  并入 {country:4s} {it['year']} {rel[:56]}", flush=True)

        added.append({
            "kind": "单页", "country": country, "year": str(it["year"]),
            "title": it["title"], "title_zh": "", "pages": 1,
            "dir": rel_dir, "cover": rel, "pdf": "",
            "url": it.get("desc_url", ""), "stance": it.get("stance", ""),
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
    from collections import Counter
    print(f"\n目录合计 {len(allr)} 条：小册子 "
          f"{sum(1 for r in allr if r['kind']=='小册子')} 本，单页 "
          f"{sum(1 for r in allr if r['kind']=='单页')} 件")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
