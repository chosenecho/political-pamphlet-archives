"""深度审核 6：README 与文档陈述的事实性核验。

文档里的每个数字都要用脚本能算出来的真实值去比。查不实陈述，
包括我自己写的"覆盖 18 国""3630 页""210/230 译名"等。
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    recs = json.load(open(os.path.join(BASE, "data", "catalog.json"), encoding="utf-8"))
    books = [r for r in recs if r["kind"] == "小册子"]
    singles = [r for r in recs if r["kind"] == "单页"]

    truth = {
        "总条目": len(recs),
        "小册子": len(books),
        "单页": len(singles),
        "小册子页数": sum(r["pages"] for r in books),
        "国家数": len({r["country"] for r in recs}),
        "立场种类": len({r["stance"] for r in recs if r["stance"]}),
        "有译名": sum(1 for r in recs if r["title_zh"]),
        "有立场": sum(1 for r in recs if r["stance"]),
        "有来源": sum(1 for r in recs if r["source"]),
        "有小册子国家": len({r["country"] for r in books}),
    }
    print("实际数据：")
    for k, v in truth.items():
        print(f"   {k:12s} {v}")

    # 按国别统计小册子
    from collections import Counter
    cc = Counter(r["country"] for r in books)
    print("\n各国小册子：")
    for k, v in sorted(cc.items(), key=lambda kv: -kv[1]):
        print(f"   {k:6s} {v}")

    # --- 抓 README 里的断言 ---
    readme = open(os.path.join(BASE, "README.md"), encoding="utf-8").read()
    print("\nREADME 中的数字断言：")
    checks = [
        (r"(\d+) 条（(\d+) 本小册子 \+ (\d+) 件单页）", "目录总数/小册子/单页"),
        (r"\*\*(\d+) 本多页小册子（(\d+) 页）\*\*", "小册子数与页数"),
        (r"\*\*(\d+) 件单页传单", "单页数"),
        (r"覆盖 (\d+) 国", "覆盖国家数"),
        (r"`stance` 只有 (\d+)/(\d+) 有值", "立场有值比"),
        (r"`source` 只有 (\d+)/(\d+)", "来源有值比"),
        (r"Pages 上 (\d+) 张图", "页面图片数"),
        (r"回填 (\d+)/(\d+) 条", "来源回填比"),
    ]
    problems = []
    for pat, label in checks:
        for m in re.finditer(pat, readme):
            nums = [int(g) for g in m.groups() if g]
            print(f"   [{label}] {m.group(0)}  -> {nums}")
            # 逐项对照
            if label == "目录总数/小册子/单页":
                if nums != [truth["总条目"], truth["小册子"], truth["单页"]]:
                    problems.append(f"{label}: README {nums} vs 实际 "
                                    f"{[truth['总条目'], truth['小册子'], truth['单页']]}")
            elif label == "小册子数与页数":
                if nums != [truth["小册子"], truth["小册子页数"]]:
                    problems.append(f"{label}: README {nums} vs 实际 "
                                    f"{[truth['小册子'], truth['小册子页数']]}")
            elif label == "单页数":
                if nums != [truth["单页"]]:
                    problems.append(f"{label}: README {nums} vs 实际 {truth['单页']}")
            elif label == "覆盖国家数":
                if nums != [truth["国家数"]]:
                    problems.append(f"{label}: README {nums} vs 实际 {truth['国家数']}")
            elif label == "立场有值比":
                if nums != [truth["有立场"], truth["总条目"]]:
                    problems.append(f"{label}: README {nums} vs 实际 "
                                    f"{[truth['有立场'], truth['总条目']]}")
            elif label == "来源有值比":
                if nums != [truth["有来源"], truth["总条目"]]:
                    problems.append(f"{label}: README {nums} vs 实际 "
                                    f"{[truth['有来源'], truth['总条目']]}")
            elif label == "页面图片数":
                if nums != [truth["总条目"]]:
                    problems.append(f"{label}: README {nums} vs 实际条目 {truth['总条目']}")
            elif label == "来源回填比":
                if nums != [truth["有来源"], truth["总条目"]]:
                    problems.append(f"{label}: README {nums} vs 实际 "
                                    f"{[truth['有来源'], truth['总条目']]}")

    print(f"\n问题 {len(problems)} 项")
    for p in problems:
        print("  ✗", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
