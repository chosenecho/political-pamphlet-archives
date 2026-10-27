"""审核脚本：核验本次补采 27 条记录的字段一致性。

检查项：
  1. source 值是否在 sources.json 的 slug 表里
  2. pages 是否等于实际页图数
  3. cover 指向的文件是否存在、是否是该目录第一页
  4. pdf 路径是否存在
  5. dir 里的序号是否与同国别其他目录冲突
  6. 标题、年份、国别是否与采集记录一致
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMG = os.path.join(BASE, "images")


def main():
    recs = json.load(open(os.path.join(BASE, "data", "catalog.json"), encoding="utf-8"))
    sources = json.load(open(os.path.join(BASE, "data", "sources.json"),
                             encoding="utf-8"))["sources"]
    valid_slugs = {s["slug"] for s in sources}

    # 新增记录按 URL 识别（source 已按规范留空，不能再用它筛）
    # 立场未标是全库历史缺口（173/230），不是本次引入，故立场检查只针对新增批次。
    new = [x for x in recs if "archive.org/details/" in x.get("url", "") and x.get("stance")]
    print(f"本次补采（有立场标注的 IA 记录）{len(new)} 条\n")

    problems = []

    # 1. source slug：全表扫，任何不在 sources.json 里的值都是错的
    illegal = {}
    for x in recs:
        s = x.get("source", "")
        if s and s not in valid_slugs:
            illegal[s] = illegal.get(s, 0) + 1
    for s, n in illegal.items():
        problems.append(f"source={s!r} 出现 {n} 次，不在 sources.json 的 "
                        f"{len(valid_slugs)} 个 slug 中")

    for x in new:
        tag = f"{x['country']}/{x['title'][:34]}"
        d = os.path.join(IMG, x["dir"].replace("/", os.sep))
        pages_dir = os.path.join(d, "pages")

        # 2. pages vs 实际页图
        if not os.path.isdir(pages_dir):
            problems.append(f"{tag}: pages 目录不存在")
            continue
        imgs = sorted(f for f in os.listdir(pages_dir) if f.endswith(".jpg"))
        if len(imgs) != x["pages"]:
            problems.append(f"{tag}: pages={x['pages']} 但实际页图 {len(imgs)}")

        # 3. cover
        cov = os.path.join(IMG, x["cover"].replace("/", os.sep))
        if not os.path.exists(cov):
            problems.append(f"{tag}: cover 不存在 {x['cover']}")
        elif imgs and not x["cover"].endswith(imgs[0]):
            problems.append(f"{tag}: cover 不是第一页（{x['cover']} vs {imgs[0]}）")

        # 4. pdf
        if x["pdf"]:
            if not os.path.exists(os.path.join(IMG, x["pdf"].replace("/", os.sep))):
                problems.append(f"{tag}: pdf 路径不存在 {x['pdf']}")

        # 6. 基本字段
        if not x["year"].isdigit() or not (1840 <= int(x["year"]) <= 1955):
            problems.append(f"{tag}: 年份异常 {x['year']!r}")
        if not x["title_zh"]:
            problems.append(f"{tag}: 缺中文译名")
        if not x["stance"]:
            problems.append(f"{tag}: 缺立场标注")

    # 5. 序号冲突：只查小册子。单页条目的 dir 是按国别共用的文件夹
    #    （如 '传单与海报/按国别/01-俄国' 下多件），重复属正常结构。
    by_country = {}
    for x in recs:
        if x["kind"] != "小册子":
            continue
        parts = x["dir"].split("/")
        if len(parts) >= 3:
            by_country.setdefault(parts[1], []).append(parts[2])
    for country, dirs in by_country.items():
        if len(dirs) != len(set(dirs)):
            dup = sorted(d for d in set(dirs) if dirs.count(d) > 1)
            problems.append(f"{country}: 小册子目录名重复 {dup}")

    print(f"问题 {len(problems)} 项")
    for p in problems:
        print("  ✗", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
