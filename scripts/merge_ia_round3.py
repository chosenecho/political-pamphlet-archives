"""并入本轮补采：第三轮 8 本 + 此前续传补齐的 2 本。

续传补齐的两本原本就在 images/_ia_recovered.json 里，页图现已补全：
  · mkgpamphlet0300mkga  甘地《素食的道德基础》 40/40
  · programmeofilpun00mann 《I.L.P. 纲领与失业》 24/24

用法：
    python scripts/merge_ia_round3.py --dry
    python scripts/merge_ia_round3.py
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
    """标题归一化，用于去重。

    注意：只保留 ASCII 字母数字会把「Хитрая механика」这类纯西里尔标题
    剥成空串，空串之间相等，于是所有非拉丁标题互相判定为重复——
    第一版就因此漏掉了两本苏联小册。这里改为保留任意文字字母与数字，
    并跳过空白标题，避免空串当键。
    """
    s = re.sub(r"[^\w]+", "", str(t).lower(), flags=re.UNICODE)
    return s[:40]


def main():
    dry = "--dry" in sys.argv
    records = catalog.load()
    have_urls = {r.get("url", "") for r in records if r.get("url")}
    # 空标题不进集合，否则空串会与任何空串匹配
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

    # ---------- A. 第三轮新采 ----------
    r3 = os.path.join(IMG, "ia-round3", "metadata.json")
    meta3 = json.load(open(r3, encoding="utf-8")) if os.path.exists(r3) else []
    print(f"[ia-round3] {len(meta3)} 条")
    for m in meta3:
        src = os.path.join(IMG, "ia-round3", "raw", f"{m['no']:03d}")
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
        if len(pages) < int(m.get("pages", 0)) * 0.9:
            skipped.append((m["title"], f"页图 {len(pages)}/{m.get('pages')} 不足"))
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
                  f"pdf{'Y' if has_pdf else 'N'}  {rel[:52]}")
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            print(f"  并入 {country:4s} {m.get('year')} {len(pages):3d}p "
                  f"pdf{'Y' if has_pdf else 'N'}  {rel[:52]}", flush=True)

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

    # ---------- B. 续传补齐的两本 ----------
    rec_path = os.path.join(IMG, "_ia_recovered.json")
    if os.path.exists(rec_path):
        spec = json.load(open(rec_path, encoding="utf-8"))
        for batch, nos in (("ia-deep", [3]), ("ia-gap", [5])):
            for it in spec.get(batch, []):
                if it["no"] not in nos:
                    continue
                src = os.path.join(IMG, batch, "raw", f"{it['no']:03d}")
                url = f"https://archive.org/details/{it['ident']}"
                if url in have_urls:
                    skipped.append((it["title"], "URL 已收录"))
                    continue
                if not os.path.isdir(src):
                    skipped.append((it["title"], "源目录缺失"))
                    continue
                pages_dir = os.path.join(src, "pages")
                pages = sorted(f for f in os.listdir(pages_dir) if f.endswith(".jpg"))
                if len(pages) < int(it["target"]) * 0.9:
                    skipped.append((it["title"], f"页图 {len(pages)}/{it['target']} 不足"))
                    continue

                country = it["country"]
                seq = next_seq(country)
                rel = f"{seq:03d}_{it['year']}_{safe(it['title'])}"
                dst = os.path.join(BK, country, rel)
                while os.path.exists(dst):
                    seq = next_seq(country)
                    rel = f"{seq:03d}_{it['year']}_{safe(it['title'])}"
                    dst = os.path.join(BK, country, rel)

                has_pdf = os.path.exists(os.path.join(src, "doc.pdf"))
                if dry:
                    print(f"  [预演·续传] {country:4s} {it['year']} {len(pages):3d}p "
                          f"{rel[:52]}")
                else:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.move(src, dst)
                    print(f"  补入 {country:4s} {it['year']} {len(pages):3d}p "
                          f"{rel[:52]}", flush=True)

                added.append({
                    "kind": "小册子", "country": country, "year": str(it["year"]),
                    "title": it["title"], "title_zh": "", "pages": len(pages),
                    "dir": f"小册子/{country}/{rel}",
                    "cover": f"小册子/{country}/{rel}/pages/{pages[0]}",
                    "pdf": f"小册子/{country}/{rel}/doc.pdf" if has_pdf else "",
                    "url": url, "stance": it["stance"], "source": "internet-archive",
                })
                have_urls.add(url)

    print(f"\n可并入 {len(added)} 本，跳过 {len(skipped)} 本")
    for t, why in skipped:
        print(f"  跳过（{why}）{t[:52]}")

    if dry:
        return 0

    if added:
        catalog.save(records + added)
        print("已写入 data/catalog.json")

    for d in ("ia-round3", "ia-deep", "ia-gap"):
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
