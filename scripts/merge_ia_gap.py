"""把 harvest_ia_gap 采到的批次并入 data/catalog.json。

与 merge_ia_stances 的差别：
  - 国别与立场来自采集阶段的判定结果（有依据字段 basis 可回溯），不再另设 KEEP 白名单；
  - 目录序号按国别现有数量续排，不覆盖已有目录；
  - PDF 与页图都搬进 images/小册子/<国别>/，源目录随后清理。

用法：
    python scripts/merge_ia_gap.py --dry    # 预演
    python scripts/merge_ia_gap.py          # 实际并入
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
ROOT = os.path.join(IMG, "ia-gap")
SRC = os.path.join(ROOT, "raw")
BK = os.path.join(IMG, "小册子")

BAD_CHARS = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=44):
    s = BAD_CHARS.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def main():
    dry = "--dry" in sys.argv
    if not os.path.exists(os.path.join(ROOT, "metadata.json")):
        print(f"没有找到 {ROOT}/metadata.json，先跑 harvest_ia_gap.py")
        return 1

    meta = json.load(open(os.path.join(ROOT, "metadata.json"), encoding="utf-8"))
    records = catalog.load()

    # 已有 URL 与标题，防止重复并入
    have_urls = {r.get("url", "") for r in records if r.get("url")}
    have_titles = {re.sub(r"[^a-z0-9]+", "", r.get("title", "").lower())[:30] for r in records}

    added, skipped = [], []
    #: 本轮每个国家已分配的序号，预演时不搬目录也能正确递增
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

    for m in meta:
        src = os.path.join(SRC, f"{m['no']:03d}")
        if not os.path.isdir(src):
            skipped.append((m["title"], "源目录缺失"))
            continue
        if m.get("url") in have_urls:
            skipped.append((m["title"], "URL 已收录"))
            continue
        tkey = re.sub(r"[^a-z0-9]+", "", m.get("title", "").lower())[:30]
        if tkey in have_titles:
            skipped.append((m["title"], "标题已收录"))
            continue

        pages_dir = os.path.join(src, "pages")
        page_files = sorted(f for f in os.listdir(pages_dir) if f.endswith(".jpg")) \
            if os.path.isdir(pages_dir) else []
        if len(page_files) < 4:
            skipped.append((m["title"], f"页图不足（{len(page_files)}）"))
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
                  f"pdf{'✓' if has_pdf else '×'}  {rel[:60]}")
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            print(f"  并入 {country:5s} {year} {len(page_files):>3d}p "
                  f"pdf{'✓' if has_pdf else '×'}  {rel[:60]}", flush=True)

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
            # source 必须是 data/sources.json 的 slug。Internet Archive 本身
            # 不是那 38 个专藏之一，其余 37 条 IA 条目的 source 也留空，
            # 这里保持一致，不造一个 sources.json 里不存在的 slug。
            "source": "",
        })
        have_urls.add(m.get("url", ""))
        have_titles.add(tkey)

    print(f"\n可并入 {len(added)} 本，跳过 {len(skipped)} 本")
    for title, why in skipped:
        print(f"  跳过（{why}）{title[:54]}")

    if dry:
        return 0

    if added:
        catalog.save(records + added)
        print("已写入 data/catalog.json")
    else:
        print("没有新条目，catalog 未改动")

    # 清理采集临时目录
    if os.path.isdir(SRC) and not [d for d in os.listdir(SRC) if os.path.isdir(os.path.join(SRC, d))]:
        shutil.rmtree(SRC, ignore_errors=True)

    allr = catalog.load()
    books = [r for r in allr if r["kind"] == "小册子"]
    from collections import Counter
    print(f"\n目录合计 {len(allr)} 条：小册子 {len(books)} 本 / {sum(r['pages'] for r in books)} 页")
    print("国别：")
    for k, v in Counter(r["country"] for r in books).most_common():
        print(f"   {k:6s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
