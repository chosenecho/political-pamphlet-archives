"""把深度补采（ia-deep）与缺口补采（ia-gap）两批一并并入 catalog。

两者结构相同（raw/NNN/{doc.pdf,pages/} + metadata.json），差别只在
来源目录。本脚本按批次顺序并入，逐条去重，国别序号续排。

用法：
    python scripts/merge_ia_deep.py --dry
    python scripts/merge_ia_deep.py
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
BK = os.path.join(IMG, "小册子")

#: 依次处理的批次目录（先深度、后缺口；两批互不重叠）
BATCHES = ["ia-deep", "ia-gap"]

BAD_CHARS = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=44):
    s = BAD_CHARS.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def norm(t):
    return re.sub(r"[^a-z0-9]+", "", str(t).lower())[:30]


def main():
    dry = "--dry" in sys.argv
    records = catalog.load()

    have_urls = {r.get("url", "") for r in records if r.get("url")}
    have_titles = {norm(r.get("title", "")) for r in records}

    seq_next = {}

    def next_seq(country):
        if country not in seq_next:
            cdir = os.path.join(BK, country)
            seq_next[country] = (len([d for d in os.listdir(cdir)
                                      if os.path.isdir(os.path.join(cdir, d))])
                                 if os.path.isdir(cdir) else 0) + 1
        v = seq_next[country]
        seq_next[country] = v + 1
        return v

    added, skipped = [], []
    for batch in BATCHES:
        root = os.path.join(IMG, batch)
        meta_path = os.path.join(root, "metadata.json")
        if not os.path.exists(meta_path):
            print(f"[{batch}] 无 metadata.json，跳过")
            continue
        meta = json.load(open(meta_path, encoding="utf-8"))
        src_root = os.path.join(root, "raw")
        print(f"\n[{batch}] 批次 {len(meta)} 条")

        for m in meta:
            src = os.path.join(src_root, f"{m['no']:03d}")
            if not os.path.isdir(src):
                skipped.append((m.get("title", "")[:40], "源目录缺失"))
                continue
            if m.get("url") in have_urls:
                skipped.append((m.get("title", "")[:40], "URL 已收录"))
                continue
            tkey = norm(m.get("title", ""))
            if tkey in have_titles:
                skipped.append((m.get("title", "")[:40], "标题已收录"))
                continue

            pages_dir = os.path.join(src, "pages")
            page_files = sorted(f for f in os.listdir(pages_dir) if f.endswith(".jpg")) \
                if os.path.isdir(pages_dir) else []
            if len(page_files) < 4:
                skipped.append((m.get("title", "")[:40], f"页图不足（{len(page_files)}）"))
                continue

            country = m["country"]
            year = str(m.get("year") or "")
            seq = next_seq(country)
            rel = f"{seq:03d}_{year}_{safe(m.get('title', ''))}"
            dst = os.path.join(BK, country, rel)
            while os.path.exists(dst):
                seq = next_seq(country)
                rel = f"{seq:03d}_{year}_{safe(m.get('title', ''))}"
                dst = os.path.join(BK, country, rel)

            has_pdf = os.path.exists(os.path.join(src, "doc.pdf"))
            if dry:
                print(f"  [预演] {country:5s} {year} {len(page_files):>3d}p "
                      f"pdf{'✓' if has_pdf else '×'}  {rel[:56]}")
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)
                print(f"  并入 {country:5s} {year} {len(page_files):>3d}p "
                      f"pdf{'✓' if has_pdf else '×'}  {rel[:56]}", flush=True)

            added.append({
                "kind": "小册子",
                "country": country,
                "year": year,
                "title": m.get("title", ""),
                "title_zh": "",
                "pages": len(page_files),
                "dir": f"小册子/{country}/{rel}",
                "cover": f"小册子/{country}/{rel}/pages/{page_files[0]}",
                "pdf": f"小册子/{country}/{rel}/doc.pdf" if has_pdf else "",
                "url": m.get("url", ""),
                "stance": m.get("stance", ""),
                "source": "internet-archive",
            })
            have_urls.add(m.get("url", ""))
            have_titles.add(tkey)

    print(f"\n可并入 {len(added)} 本，跳过 {len(skipped)} 本")
    for t, why in skipped:
        print(f"  跳过（{why}）{t}")

    if dry:
        return 0

    if added:
        catalog.save(records + added)
        print("已写入 data/catalog.json")
    else:
        print("没有新条目")

    for batch in BATCHES:
        r = os.path.join(IMG, batch, "raw")
        if os.path.isdir(r) and not [d for d in os.listdir(r)
                                     if os.path.isdir(os.path.join(r, d))]:
            shutil.rmtree(r, ignore_errors=True)

    allr = catalog.load()
    books = [r for r in allr if r["kind"] == "小册子"]
    from collections import Counter
    print(f"\n目录合计 {len(allr)} 条：小册子 {len(books)} 本 / "
          f"{sum(r['pages'] for r in books)} 页")
    print("国别：")
    for k, v in Counter(r["country"] for r in books).most_common():
        print(f"   {k:6s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
