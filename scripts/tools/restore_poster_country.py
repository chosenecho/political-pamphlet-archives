"""从候选清单恢复海报批次的国别，并重跑立场修正。

上一版 fix_poster_stance.py 让规则同时改国别，跨语言误匹配把
3 类条目挂错了国别。国别的权威来源是采集时的分类（记录在
images/_poster_candidates.json 里，按 title 可一一对应）。
本脚本以该文件为准恢复国别，立场仍由 fix_poster_stance.py 判定。
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAND = os.path.join(BASE, "images", "_poster_candidates.json")
META = os.path.join(BASE, "images", "posters-new", "metadata.json")


def main():
    cands = json.load(open(CAND, encoding="utf-8"))
    by_title = {c["title"]: c for c in cands}
    items = json.load(open(META, encoding="utf-8"))

    fixed = 0
    missing = []
    for it in items:
        c = by_title.get(it["title"])
        if not c:
            missing.append(it["title"])
            continue
        if it["country"] != c["country"]:
            print(f"  {it['no']:03d} 国别 {it['country']} -> {c['country']}  {it['title'][:50]}")
            it["country"] = c["country"]
            fixed += 1

    json.dump(items, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n恢复 {fixed} 条国别；{len(missing)} 条在候选清单里找不到")
    for t in missing:
        print(f"   缺失：{t[:66]}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
