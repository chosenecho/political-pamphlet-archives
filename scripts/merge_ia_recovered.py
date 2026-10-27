"""并入 IA 两批已下载但缺 metadata.json 的记录。

IA 中途不可达，两个采集脚本都没写出 metadata.json。身份从已下载 PDF
的 XMP 元数据反推（见 images/_ia_recovered.json），页数以实际页图为准。

残缺处理：页图少于 PDF 页数的，如实并入并在 pages 记录实际张数，
不虚报。README 的缺口段会说明哪一本未抓全。
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
RECOVER = os.path.join(IMG, "_ia_recovered.json")

BAD_CHARS = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=44):
    s = BAD_CHARS.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def main():
    dry = "--dry" in sys.argv
    spec = json.load(open(RECOVER, encoding="utf-8"))
    records = catalog.load()
    have_urls = {r.get("url", "") for r in records if r.get("url")}
    have_titles = {re.sub(r"[^a-z0-9]+", "", r.get("title", "").lower())[:30]
                   for r in records}

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

    added, skipped, skip_incomplete = [], [], []
    for batch, items in spec.items():
        if batch.startswith("_"):
            continue
        print(f"\n[{batch}] {len(items)} 项")
        for it in items:
            src = os.path.join(IMG, batch, "raw", f"{it['no']:03d}")
            if not os.path.isdir(src):
                skipped.append((it["title"], "源目录缺失"))
                continue
            url = f"https://archive.org/details/{it['ident']}"
            if url in have_urls:
                skipped.append((it["title"], "URL 已收录"))
                continue
            key = re.sub(r"[^a-z0-9]+", "", it["title"].lower())[:30]
            if key in have_titles:
                skipped.append((it["title"], "标题已收录"))
                continue

            pages_dir = os.path.join(src, "pages")
            pages = sorted(f for f in os.listdir(pages_dir) if f.endswith(".jpg")) \
                if os.path.isdir(pages_dir) else []
            if len(pages) < 3:
                skipped.append((it["title"], f"页图仅 {len(pages)} 张"))
                continue

            # 只收完整的：页图数少于 IA 记录的 imagecount 的，说明下载中途
            # 被限流打断。残缺件不入目录，保留在 raw/ 下等 IA 恢复后续传。
            if len(pages) < int(it["target"]):
                skip_incomplete.append(
                    (it["title"], f"{len(pages)}/{it['target']} 页，待续传"))
                continue

            country = it["country"]
            seq = next_seq(country)
            rel = f"{seq:03d}_{it['year']}_{safe(it['title'])}"
            dst = os.path.join(BK, country, rel)
            while os.path.exists(dst):
                seq = next_seq(country)
                rel = f"{seq:03d}_{it['year']}_{safe(it['title'])}"
                dst = os.path.join(BK, country, rel)

            incomplete = False   # 残缺件已被上面拦下，走到这里的都是完整的
            mark = ""

            if dry:
                print(f"  [预演] {country:4s} {it['year']} {len(pages)}/{it['target']}p {rel[:50]}{mark}")
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)
                print(f"  并入 {country:4s} {it['year']} {len(pages)}/{it['target']}p "
                      f"{rel[:50]}{mark}", flush=True)

            has_pdf = os.path.exists(os.path.join(dst, "doc.pdf"))
            added.append({
                "kind": "小册子",
                "country": country,
                "year": str(it["year"]),
                "title": it["title"],
                "title_zh": "",
                "pages": len(pages),
                "dir": f"小册子/{country}/{rel}",
                "cover": f"小册子/{country}/{rel}/pages/{pages[0]}",
                "pdf": f"小册子/{country}/{rel}/doc.pdf" if has_pdf else "",
                "url": url,
                "stance": it["stance"],
                "source": "internet-archive",
            })
            have_urls.add(url)
            have_titles.add(key)

    print(f"\n可并入 {len(added)} 本，跳过 {len(skipped)} 项")
    for t, why in skipped:
        print(f"  跳过（{why}）{t[:56]}")
    if skip_incomplete:
        print(f"\n待续传 {len(skip_incomplete)} 本（已保留在 images/，IA 恢复后补齐）")
        for t, why in skip_incomplete:
            print(f"  待补（{why}）{t[:56]}")

    if dry:
        return 0

    if added:
        catalog.save(records + added)
        print("已写入 data/catalog.json")

    # 只清理已并入后变空的批次目录；残缺件所在的目录保留，等 IA 恢复续传
    for batch in spec:
        if batch.startswith("_"):
            continue
        r = os.path.join(IMG, batch, "raw")
        if os.path.isdir(r) and not [d for d in os.listdir(r)
                                     if os.path.isdir(os.path.join(r, d))]:
            shutil.rmtree(r, ignore_errors=True)
        elif os.path.isdir(r):
            left = [d for d in os.listdir(r) if os.path.isdir(os.path.join(r, d))]
            print(f"保留 {batch}/raw 下 {len(left)} 个待续传目录：{left}")

    allr = catalog.load()
    books = [r for r in allr if r["kind"] == "小册子"]
    from collections import Counter
    print(f"\n目录合计 {len(allr)} 条，小册子 {len(books)} 本 / "
          f"{sum(r['pages'] for r in books)} 页")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
