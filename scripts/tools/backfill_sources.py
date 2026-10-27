"""回填条目来源：把能按 URL 唯一确定的条目挂到对应专藏。

现状（main 337 条）：
  - 242 条有 URL 但 source 为空
    · 41 条指向 archive.org/details/  —— 可唯一归属 internet-archive
    · 201 条指向 commons.wikimedia.org/wiki/File —— Commons 尚未登记为专藏
  - 18 条 URL 只是站点根（如 https://commons.wikimedia.org/），无条目路径，
    无法判定具体来源，保持留空

本脚本做三件事：
  1. 在 sources.json 登记 Wikimedia Commons 为第 40 个专藏
  2. 在 lib/index.py 的域名映射里补上两个来源
  3. 按新映射回填 catalog 的 source 字段

判定纪律不变：只有 URL 里确有条目路径才归属；站点根一律留空，不猜。
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import index as catalog
from lib import paths

COMMONS_SLUG = "wiki-commons"

COMMONS_ENTRY = {
    "slug": COMMONS_SLUG,
    "title": "Wikimedia Commons · 政治海报与传单扫描件",
    "region": "跨国",
    "kind": "数字馆藏(免费)",
    "url": "https://commons.wikimedia.org/",
    "note": "各国档案馆与图书馆上传的历史政治海报、竞选招贴、传单扫描件；"
            "本目录已收录 200 余件，1848-1990",
    "lang": "en",
    "terms": ["political poster", "election poster", "campaign poster",
              "propaganda poster", "leaflet", "handbill", "suffragette poster"],
}


def ensure_source():
    """在 sources.json 登记 Commons（幂等）。"""
    p = paths.SOURCES
    doc = json.load(open(p, encoding="utf-8"))
    srcs = doc["sources"]
    if any(s["slug"] == COMMONS_SLUG for s in srcs):
        print(f"sources.json：已含 {COMMONS_SLUG}")
        return False
    srcs.append(COMMONS_ENTRY)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"sources.json：登记 {COMMONS_SLUG}，现有 {len(srcs)} 个专藏")
    return True


def main():
    dry = "--dry" in sys.argv
    recs = catalog.load()

    before = sum(1 for r in recs if r["source"])
    # 用新映射回填
    kat = json.load(open(paths.SOURCES, encoding="utf-8"))["sources"]
    if not any(s["slug"] == COMMONS_SLUG for s in kat):
        kat = kat + [COMMONS_ENTRY]
    catalog.attach_sources(recs, kat)
    after = sum(1 for r in recs if r["source"])

    print(f"\n来源归属：{before} → {after} 条（+{after - before}）")
    from collections import Counter
    for k, v in Counter(r["source"] for r in recs if r["source"]).most_common():
        print(f"   {k:26s} {v}")

    # 仍未归属的，说明原因
    left = [r for r in recs if not r["source"]]
    root = [r for r in left if r["url"].rstrip("/") in
            ("https://commons.wikimedia.org", "https://archive.org", "")]
    print(f"\n仍未归属 {len(left)} 条，其中 URL 为站点根 {len(root)} 条（不可判定，保持留空）")

    if dry:
        print("\n[预演] 未写入")
        return 0

    catalog.save(recs)
    print("\n已写入 data/catalog.json")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
