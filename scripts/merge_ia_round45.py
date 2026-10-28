"""并入第四、五轮补采（11 本）。

第四轮 10 本（捷克 4、比利时 2、日本 1、奥地利 1、意大利 1、西班牙 1）
第五轮  1 本（匈牙利 1）—— 同批另一本奥地利材料页图 0 页，源站未开放，未收。
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
BAD_CHARS = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=44):
    s = BAD_CHARS.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def norm(t):
    """标题归一化。保留任意文字字母数字——只留 ASCII 会把西里尔/中日韩
    标题剥成空串，空串互相相等导致误判重复（前一轮踩过）。"""
    s = re.sub(r"[^\w]+", "", str(t).lower(), flags=re.UNICODE)
    return s[:40]


def main():
    dry = "--dry" in sys.argv
    records = catalog.load()
    have_urls = {r.get("url", "") for r in records if r.get("url")}
    have_titles = {norm(r.get("title", "")) for r in records}
    have_titles.discard("")

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

    for batch in ("ia-round4", "ia-round5"):
        mp = os.path.join(IMG, batch, "metadata.json")
        if not os.path.exists(mp):
            print(f"[{batch}] 无 metadata，跳过")
            continue
        meta = json.load(open(mp, encoding="utf-8"))
        print(f"\n[{batch}] {len(meta)} 条")

        for m in meta:
            src = os.path.join(IMG, batch, "raw", f"{m['no']:03d}")
            if not os.path.isdir(src):
                skipped.append((m["title"], "源目录缺失"))
                continue
            if m.get("url") in have_urls:
                skipped.append((m["title"], "URL 已收录"))
                continue
            tkey = norm(m.get("title", ""))
            if tkey in have_titles:
                skipped.append((m["title"], "标题已收录"))
                continue

            pages_dir = os.path.join(src, "pages")
            pages = sorted(f for f in os.listdir(pages_dir) if f.endswith(".jpg")) \
                if os.path.isdir(pages_dir) else []
            if len(pages) < 8:
                skipped.append((m["title"], f"页图仅 {len(pages)} 张"))
                continue

            country = m["country"]
            seq = next_seq(country)
            rel = f"{seq:03d}_{m.get('year','')}_{safe(m.get('title',''))}"
            dst = os.path.join(BK, country, rel)
            while os.path.exists(dst):
                seq = next_seq(country)
                rel = f"{seq:03d}_{m.get('year','')}_{safe(m.get('title',''))}"
                dst = os.path.join(BK, country, rel)

            has_pdf = os.path.exists(os.path.join(src, "doc.pdf"))
            if dry:
                print(f"  [预演] {country:4s} {m.get('year')} {len(pages):3d}p "
                      f"pdf{'Y' if has_pdf else 'N'}  {rel[:50]}")
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)
                print(f"  并入 {country:4s} {m.get('year')} {len(pages):3d}p "
                      f"pdf{'Y' if has_pdf else 'N'}  {rel[:50]}", flush=True)

            added.append({
                "kind": "小册子", "country": country, "year": str(m.get("year", "")),
                "title": m.get("title", ""), "title_zh": "", "pages": len(pages),
                "dir": f"小册子/{country}/{rel}",
                "cover": f"小册子/{country}/{rel}/pages/{pages[0]}",
                "pdf": f"小册子/{country}/{rel}/doc.pdf" if has_pdf else "",
                "url": m.get("url", ""), "stance": m.get("stance", ""),
                "source": "internet-archive",
            })
            have_urls.add(m.get("url", ""))
            have_titles.add(tkey)

    print(f"\n可并入 {len(added)} 本，跳过 {len(skipped)} 本")
    for t, why in skipped:
        print(f"  跳过（{why}）{t[:50]}")

    if dry:
        return 0

    if added:
        catalog.save(records + added)
        print("已写入 data/catalog.json")

    for d in ("ia-round4", "ia-round5"):
        r = os.path.join(IMG, d, "raw")
        if os.path.isdir(r) and not [x for x in os.listdir(r)
                                     if os.path.isdir(os.path.join(r, x))]:
            shutil.rmtree(os.path.join(IMG, d), ignore_errors=True)

    allr = catalog.load()
    books = [r for r in allr if r["kind"] == "小册子"]
    from collections import Counter
    print(f"\n目录合计 {len(allr)} 条：小册子 {len(books)} 本 / "
          f"{sum(r['pages'] for r in books)} 页")
    print("小册子国别：")
    for k, v in Counter(r["country"] for r in books).most_common():
        print(f"   {k:6s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
