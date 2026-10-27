"""核验并修正海报批次的年份。

年份取自 Commons 的 extmetadata 日期字段，但该字段有时是**上传日期**
或**档案编目日期**，不是海报本身的年份。逐条比对标题里能读出的年份，
不一致的以标题为准并记录理由。
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
META = os.path.join(BASE, "images", "posters-new", "metadata.json")

#: 逐条人工核验的年份修正：(no, 正确年份, 依据)
FIX = {
    32: ("1889", "标题明写 Élections législatives du 22 septembre 1889；"
                 "extmetadata 的 1943 是 BnF 编目/上传日期"),
    53: ("1900", "标题即 Capitalist pyramid 1900，图为 1900 年作；"
                 "extmetadata 的 1901 是编目日期"),
}

#: 标题含年份但记录属正确的（引用历史事件、或描述里的无关年份）。
#: 列出以免每次运行都重复报警，也留存判断依据。
FALSE_ALARM = {
    22: "《Nie mehr Februar 1934》是 1949 年奥地利大选海报，"
        "标题引用 1934 年二月内战，1949 才对",
    60: "Stevenson–Sparkman 是 1952 年美国总统竞选海报；"
        "标题中的 1972 来自文件描述里的其他信息",
}


def main():
    items = json.load(open(META, encoding="utf-8"))
    changed = 0
    for it in items:
        if it["no"] in FIX:
            y, why = FIX[it["no"]]
            print(f"  {it['no']:03d} {it['year']} -> {y}  {it['title'][:50]}\n      {why}")
            it["year"] = y
            changed += 1

    # 逐条对照标题里的四位年份，发现不一致就报出来（已核验豁免的不报）
    print("\n标题含年份且与记录不符的：")
    suspect = 0
    for it in items:
        ys = set(re.findall(r"\b(1[89]\d{2}|19\d{2})\b", it["title"]))
        if ys and it["year"] not in ys and it["no"] not in FALSE_ALARM:
            print(f"  {it['no']:03d} 记录 {it['year']} vs 标题 {sorted(ys)}  {it['title'][:56]}")
            suspect += 1
    if not suspect:
        print("  （无）")
    if FALSE_ALARM:
        print("\n已核验判定为无误的：")
        for no, why in FALSE_ALARM.items():
            print(f"  {no:03d} {why}")

    json.dump(items, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n修正 {changed} 条；疑似不一致 {suspect} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
