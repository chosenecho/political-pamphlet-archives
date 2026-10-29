"""按标签打印候选池，供逐条核验国别与立场。

只读 images/round10/pool2.json，不发请求。用 --label 过滤，--grep 搜题名。

用法：
    python scripts/tools/review_round10.py                      # 全部标签的计数
    python scripts/tools/review_round10.py --label 葡萄牙
    python scripts/tools/review_round10.py --label 奥地 --full
"""

import collections
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POOL = os.path.join(BASE, "images", "round10", "pool2.json")


def main():
    if not os.path.exists(POOL):
        print(f"缺候选池：{POOL}（先跑 probe_round10c.py）")
        return 1
    with open(POOL, encoding="utf-8") as f:
        pool = json.load(f)

    label = None
    full = "--full" in sys.argv
    if "--label" in sys.argv:
        label = sys.argv[sys.argv.index("--label") + 1]
    grep = None
    if "--grep" in sys.argv:
        grep = sys.argv[sys.argv.index("--grep") + 1].lower()

    if not label and not grep:
        for k, v in collections.Counter(c["label"] for c in pool).most_common():
            print(f"{v:4d}  {k}")
        print(f"\n合计 {len(pool)}")
        return 0

    sel = [c for c in pool
           if (not label or label in c["label"])
           and (not grep or grep in c["title"].lower()
                or grep in c.get("publisher", "").lower())]
    print(f"命中 {len(sel)} 条\n")
    for c in sel:
        print(f'{c["identifier"]}  {c["year"]} {c["pages"]:>3}p {c["language"][:10]:10s} '
              f'[{c["label"]}]')
        print(f'   T {c["title"][:140]}')
        if full:
            print(f'   P {c["publisher"][:140]}')
            print(f'   C {c["creator"][:140]}')
            print(f'   S {c["subject"][:140]}')
            print(f'   G {c["collection"][:100]}')
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
