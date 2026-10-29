"""并入第十轮补采：53 本多页小册子。

与前面几轮的差别：本轮只收 `小册子`，不再收单页。国别分布如下（含此前
只有 1–2 本的国别）：

    美国 17、奥地利 5、爱尔兰 5、印度 4、拉美 4、德国 3、英国 3、
    俄国 3、意大利 2、波兰 / 西班牙 / 荷兰 / 中国 / 土耳其 / 苏联 各 1

荷兰、中国、土耳其此前小册子分别为 1、1、0 本，本轮各补 1 本；
西班牙补 1 本（此前 5 本）。

用法：
    python scripts/merge_round10.py --dry
    python scripts/merge_round10.py
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
ROOT = os.path.join(IMG, "round10")
RAW = os.path.join(ROOT, "raw")
BK = os.path.join(IMG, "小册子")

BAD_CHARS = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=44):
    s = BAD_CHARS.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def norm(t, year=""):
    """去重键：标题归一化 + 年份。

    只按标题去重会把同一政党不同年度的同名报告并成一条：奥地利社会民主
    工人党的《Bericht der Parteivertretung an den Parteitag》每年出一册，
    1902/1905/1909/1912 是四份不同的实物（页数分别是 48/76/84/66）。
    这里把年份并进键里，同标题不同年份即视为不同条目。
    """
    s = re.sub(r"[^\w]+", "", str(t).lower(), flags=re.UNICODE)
    return f"{s[:40]}|{year}"


def main():
    dry = "--dry" in sys.argv
    records = catalog.load()
    have_urls = {r.get("url", "") for r in records if r.get("url")}
    have_titles = {norm(r.get("title", ""), r.get("year", "")) for r in records}
    have_titles.discard("")

    seq_next = {}

    def next_seq(country):
        """按国别目录内已有子目录数取下一个序号。

        号段不沿用「目录数 + 1」的老写法会导致重号：中国有 20 个子目录但
        编号到 021（中间删过一条），直接 +1 会撞上 021。这里逐个试到空位。
        """
        cdir = os.path.join(BK, country)
        if country not in seq_next:
            seq_next[country] = len([d for d in os.listdir(cdir)
                                     if os.path.isdir(os.path.join(cdir, d))]) \
                if os.path.isdir(cdir) else 0
        while True:
            seq_next[country] += 1
            v = seq_next[country]
            if not any(d.startswith(f"{v:03d}_") for d in os.listdir(cdir)) \
                    if os.path.isdir(cdir) else True:
                return v

    meta_path = os.path.join(ROOT, "metadata.json")
    if not os.path.exists(meta_path):
        print(f"缺 {meta_path}，先跑 scripts/harvest_ia_round10.py")
        return 1
    items = json.load(open(meta_path, encoding="utf-8"))
    print(f"[round10] {len(items)} 本")

    added, skipped = [], []
    for m in items:
        src = os.path.join(RAW, f"{m['no']:03d}")
        if not os.path.isdir(src):
            skipped.append((m["title"], "源目录缺失"))
            continue
        if m.get("url") in have_urls:
            skipped.append((m["title"], "URL 已收录"))
            continue
        tkey = norm(m.get("title", ""), str(m.get("year", "")))
        if tkey in have_titles:
            skipped.append((m["title"], "标题与年份已收录"))
            continue

        pages_dir = os.path.join(src, "pages")
        pages = sorted(f for f in os.listdir(pages_dir) if f.endswith(".jpg")) \
            if os.path.isdir(pages_dir) else []
        if len(pages) < 8:
            skipped.append((m["title"], f"页图仅 {len(pages)} 张"))
            continue

        country = m["country"]
        seq = next_seq(country)
        rel = f"{seq:03d}_{m.get('year', '')}_{safe(m.get('title', ''))}"
        dst = os.path.join(BK, country, rel)
        while os.path.exists(dst):
            seq = next_seq(country)
            rel = f"{seq:03d}_{m.get('year', '')}_{safe(m.get('title', ''))}"
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

    print(f"\n可并入 {len(added)} 本，跳过 {len(skipped)} 本")
    for t, why in skipped:
        print(f"  跳过（{why}）{t[:52]}")

    if dry:
        return 0

    if added:
        catalog.save(records + added)
        print("已写入 data/catalog.json")

    if os.path.isdir(RAW) and not [d for d in os.listdir(RAW)
                                   if os.path.isdir(os.path.join(RAW, d))]:
        shutil.rmtree(ROOT, ignore_errors=True)

    allr = catalog.load()
    books = [r for r in allr if r["kind"] == "小册子"]
    from collections import Counter
    print(f"\n目录合计 {len(allr)} 条：小册子 {len(books)} 本 / "
          f"{sum(r['pages'] for r in books)} 页，"
          f"单页 {len(allr) - len(books)} 件")
    print("小册子国别：")
    for k, v in Counter(r["country"] for r in books).most_common():
        print(f"   {k:6s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
