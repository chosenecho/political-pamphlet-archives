#!/usr/bin/env python3
"""校验 data/catalog.json：字段齐全、kind 合法、封面不重复。

CI 与本地都用它做前置检查。退出码非 0 即失败。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths


def main():
    records = catalog.load()
    if not records:
        print(f"目录为空或不存在：{paths.CATALOG}")
        return 1

    st = catalog.stats(records)
    print(f"目录 {st['total']} 条：小册子 {st['books']}、单页 {st['singles']}；"
          f"国家 {st['countries']}、立场 {st['stances']}；"
          f"中文译名 {st['with_zh']}、已归属来源 {st['linked']}")

    # 结构问题：必须失败
    problems = [p for p in catalog.validate(records) if "cover 文件不存在" not in p]
    # 封面缺失：只警告。images/ 不入库，CI 上没有图片属正常
    missing = [p for p in catalog.validate(records) if "cover 文件不存在" in p]

    for p in problems[:20]:
        print("  ✗", p)
    if problems:
        print(f"\n结构问题 {len(problems)} 条")
        return 1

    if missing:
        print(f"  （封面文件 {len(missing)} 个不在本地，images/ 不入库，跳过不视为错误）")

    # 模板占位符：目录页由模板生成，占位符写错会让整页空白
    tpl = os.path.join(paths.SCRIPTS, "templates", "catalog.html")
    if not os.path.exists(tpl):
        print(f"  ✗ 模板缺失：{tpl}")
        return 1
    with open(tpl, encoding="utf-8") as f:
        html = f.read()
    need = ["__DATA__", "__STATS__", "__SOURCES__", "__ASSET__", "__BUILD__"]
    absent = [k for k in need if k not in html]
    if absent:
        print(f"  ✗ 模板缺占位符：{'、'.join(absent)}")
        return 1

    # 数据缺口：报告但不失败。这些是已知且已声明的，不是回归
    gaps = {
        "立场未标注": sum(1 for r in records if not r["stance"]),
        "来源未归属": sum(1 for r in records if not r["source"]),
        "年份不详": sum(1 for r in records if not r["year"]),
        "无 PDF": sum(1 for r in records if not r["pdf"]),
    }
    print("  缺口：" + " · ".join(f"{k} {v}/{len(records)}" for k, v in gaps.items()))

    print("校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
