"""把 data/sources.json 的 region 字段统一成中文名（可重复执行）。

问题
    该字段原本混用三种写法：ISO 代码（`UK`/`US`/`DE`/`FR`/`NL`/`CH`/`ES`/
    `CN`/`JP`/`BE`）、中文名（`智利`/`奥地利`/`跨国`/`欧洲`…）、复合值
    （`US/UK`/`俄/美`/`印度/美`）。24 种取值描述 40 条记录。

    后果不是「不好看」，而是下游各写各的映射：add_terms.py 的 REGION_LANG
    要同时列出 `UK` 和「英国」才勉强覆盖，漏一个就静默退回英文检索词；
    build_index.py 直接把它写进 csv 与 COLLECTIONS.md，文档里一半中文一半代码。

本脚本只动数据，不改语义
    把每种写法换成统一的那个中文名。复合值保持「甲/乙」形状——它表达的是
    「两地合藏」或「跨国机构」，压成单一国家会失真。

    region 改了之后，add_terms.py 重跑即可让 lang/terms 跟上（见该脚本）。

幂等
    连跑多次结果一致。转换表在 scripts/lib/regions.py，与读取侧共用一份。
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import paths
from lib import regions


def main():
    p = paths.SOURCES
    doc = json.load(open(p, encoding="utf-8"))
    srcs = doc["sources"]

    changes = []
    for s in srcs:
        old = (s.get("region") or "").strip()
        new = regions.to_zh(old)
        if old != new:
            s["region"] = new
            changes.append((s["slug"], old, new))
        elif s.get("region") != new:
            # 只是去空白
            s["region"] = new

    if not changes:
        print("sources.json：region 已全部是统一写法，无需改动")
    else:
        print(f"sources.json：转换 {len(changes)} 条 region")
        for slug, old, new in changes:
            print(f"  ~ {slug:32s} {old!r} -> {new!r}")

        with open(p, "w", encoding="utf-8", newline="\n") as f:
            # indent=2：data/sources.json 原本就是 2 空格。用 json 默认的 indent=1
            # 会把整个文件重新缩进，上千行与内容无关的 diff 会把真正的改动埋掉。
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")

    # 统一后不该再有词表外的取值
    unknown = sorted({s["region"] for s in srcs if not regions.is_known(s["region"])})
    if unknown:
        print(f"\n⚠ 词表外的取值（请补进 scripts/lib/regions.py 的 CANONICAL）：{unknown}")
        return 1
    print(f"\n全部 {len(srcs)} 条 region 均在词表内（{len(regions.CANONICAL)} 种取值）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
