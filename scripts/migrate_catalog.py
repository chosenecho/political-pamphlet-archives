#!/usr/bin/env python3
"""把 images/索引.json 迁移为 data/catalog.json 并规范化 schema。

一次性迁移脚本，幂等：重复运行不会改变结果。
遗留的 images/索引.json 在迁移后由 migrate 到此处的旧文件可安全删除，
但本脚本不删除它（删除动作交给显式的清理步骤）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths


def main():
    legacy = os.path.join(paths.IMAGES, "索引.json")
    src = paths.CATALOG if os.path.exists(paths.CATALOG) else legacy
    if not os.path.exists(src):
        print(f"找不到源：{legacy}，也没有 {paths.CATALOG}")
        return 1

    recs = catalog.load(src)
    print(f"读入 {len(recs)} 条（{src}）")

    with open(paths.SOURCES, encoding="utf-8") as f:
        import json

        sources = json.load(f)["sources"]

    before = catalog.stats(recs)
    recs = catalog.attach_sources(recs, sources)
    recs = [catalog.normalize(r) for r in recs]
    after = catalog.stats(recs)

    problems = catalog.validate(recs)
    catalog.save(recs)

    print(f"写出 {paths.CATALOG}")
    print(f"  小册子 {after['books']} / 单页 {after['singles']} / "
          f"国家 {after['countries']} / 立场 {after['stances']}")
    print(f"  中文译名 {after['with_zh']}（迁移前 {before['with_zh']}）")
    print(f"  已归属来源 {after['linked']}/{after['total']}")

    if problems:
        print(f"\n校验发现 {len(problems)} 个问题：")
        for p in problems[:20]:
            print("  -", p)
        if len(problems) > 20:
            print(f"  ...另有 {len(problems) - 20} 条")
        return 1
    print("\n校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
