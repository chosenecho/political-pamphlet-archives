"""把已落在磁盘上、但 catalog 里还没有的本轮小册子补进去。

为什么需要这一步：`merge_round10.py` 先把 `images/round10/raw/NNN` 移进
`images/小册子/<国别>/<序号>_<年>_<题名>`（文件移动不可逆），最后才写
`data/catalog.json`。一旦写库被拦下（本轮就是被 `lib/vocab.py` 的立场词表
拦住，见那里的说明），磁盘与索引就会不一致，而重跑 merge 既不认这些目录、
`raw/` 也已清空。

本脚本按 `images/round10/metadata.json` 逐条回查目录，只补「目录里已就位、
catalog 里没有」的那几条，不碰别的东西。幂等：重复运行第二次会报 0 条。

用法：
    python scripts/fix_round10_catalog.py --dry
    python scripts/fix_round10_catalog.py
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import index as catalog
from lib import paths

IMG = paths.IMAGES
ROOT = os.path.join(IMG, "round10")
BK = os.path.join(IMG, "小册子")

BAD_CHARS = re.compile(r'[\\/:*?"<>|]+')


def safe(s, n=44):
    """与 merge_round10.py 同一套目录名生成规则，两处必须一致。"""
    s = BAD_CHARS.sub("_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def main():
    dry = "--dry" in sys.argv
    meta = json.load(open(os.path.join(ROOT, "metadata.json"), encoding="utf-8"))
    records = catalog.load()
    have_urls = {r.get("url", "") for r in records if r.get("url")}

    added, already, missing = [], [], []
    for m in meta:
        if m.get("url") in have_urls:
            already.append(m["title"])
            continue

        country = m["country"]
        cdir = os.path.join(BK, country)
        if not os.path.isdir(cdir):
            missing.append((m["title"], "国别目录不存在"))
            continue

        # 目录名是「序号_年份_<safe(题名)>」。必须年份与题名同时命中：
        # 只按题名会把奥地利四份同题年度报告（1902/1905/1909/1912）全都
        # 指到同一本；只按年份会撞美国 1860/1864 的多本。
        stem = safe(m.get("title", ""))
        year = str(m.get("year", ""))
        hit = None
        for d in os.listdir(cdir):
            p = os.path.join(cdir, d)
            if not os.path.isdir(p) or stem not in d or f"_{year}_" not in d:
                continue
            pages = os.path.join(p, "pages")
            if not os.path.isdir(pages):
                continue
            if not any(f.endswith(".jpg") for f in os.listdir(pages)):
                continue
            hit = d
            break
        if not hit:
            missing.append((m["title"], "未找到对应目录"))
            continue

        pages_dir = os.path.join(cdir, hit, "pages")
        pages = sorted(f for f in os.listdir(pages_dir) if f.endswith(".jpg"))
        has_pdf = os.path.exists(os.path.join(cdir, hit, "doc.pdf"))
        added.append({
            "kind": "小册子", "country": country, "year": str(m.get("year", "")),
            "title": m.get("title", ""), "title_zh": "", "pages": len(pages),
            "dir": f"小册子/{country}/{hit}",
            "cover": f"小册子/{country}/{hit}/pages/{pages[0]}",
            "pdf": f"小册子/{country}/{hit}/doc.pdf" if has_pdf else "",
            "url": m.get("url", ""), "stance": m.get("stance", ""),
            "source": "internet-archive",
        })
        have_urls.add(m.get("url", ""))

    print(f"本轮 {len(meta)} 条：已在库里 {len(already)}，待补 {len(added)}，"
          f"找不到目录 {len(missing)}")
    for t, why in missing:
        print(f"  未补（{why}）{t[:60]}")
    for a in added:
        print(f"  [待补] {a['country']:4s} {a['year']} {a['pages']:3d}p {a['dir'][:64]}")

    if dry:
        return 0
    if not added:
        print("无需补写")
        return 0

    catalog.save(records + added)
    print(f"已写入 {len(added)} 条到 data/catalog.json")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
