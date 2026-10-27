"""审核 sources.json 的 region 词表一致性。

这个字段曾经混用 ISO 代码、中文名与复合值三种写法，24 种取值描述 40 条记录。
后果不是「不好看」：`add_terms.py` 的 REGION_LANG 要同时列出 `UK` 和「英国」
才勉强覆盖，漏一个就静默退回英文检索词；`build_index.py` 把它原样写进
csv 与 COLLECTIONS.md，文档里一半中文一半代码。

现在数据统一成中文名，转换表在 `scripts/lib/regions.py`。本审核守三件事：

  1. 每条记录的 region 都在词表内（新增国别必须登记，不许悄悄混进来）
  2. 每条记录都能查到对应语言（查不到就不能编检索词，宁可报错）
  3. 记录的 lang/terms 与词表推出的语言一致（防止有人手改单条造成分叉）

不做的事：不去比 region 的「正确性」。某个专藏该算「欧洲」还是「跨国」
是编目判断，脚本无权替人决定。
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import regions

#: 语言 → 检索词的期望条数下限。只查「有没有」，不查具体词——词是会调整的。
MIN_TERMS = 3


def main():
    src = json.load(open(os.path.join(BASE, "data", "sources.json"),
                         encoding="utf-8"))["sources"]
    print(f"专藏 {len(src)} 条\n")

    problems = []

    # 1. 词表覆盖
    #    直接比**原始值**，不经 to_zh() 归一。否则词表外的代码写法（比如再混
    #    进来一个 `UK`）会被 to_zh 悄悄换成「英国」而算作已知——审核就白做了。
    #    数据文件里就该是规范写法；兼容旧写法是读取侧的事，不是数据的事。
    unknown = {}
    for s in src:
        raw = (s.get("region") or "").strip()
        if raw not in regions.CANONICAL:
            unknown.setdefault(raw, []).append(s["slug"])
    print(f"[词表] 已登记 {len(regions.CANONICAL)} 种取值")
    for region, slugs in unknown.items():
        hint = ""
        if regions.to_zh(region) != region:
            hint = f"（该写法会被归一成 {regions.to_zh(region)!r}，请直接写规范值）"
        problems.append(f"region {region!r} 不在词表内（{len(slugs)} 条：{slugs[:3]}…）"
                        f"{hint}——跑 scripts/tools/normalize_regions.py")

    # 2. 语言可查
    no_lang = [(s["slug"], s.get("region")) for s in src
               if regions.language_of(s.get("region")) is None]
    print(f"[语言] 查不到语言的 {len(no_lang)} 条")
    for slug, region in no_lang:
        problems.append(f"{slug}: region={region!r} 查不到语言，无法编检索词"
                        f"——补进 scripts/lib/regions.py 的 LANGUAGE")

    # 3. 记录与词表一致
    print("[一致] 逐条核对 lang / terms")
    for s in src:
        want = regions.language_of(s.get("region"))
        if want is None:
            continue          # 已在第 2 项报过
        if s.get("lang") != want:
            problems.append(f"{s['slug']}: lang={s.get('lang')!r}，"
                            f"按 region={s.get('region')!r} 应为 {want!r}"
                            f"——跑 scripts/add_terms.py")
        terms = s.get("terms") or []
        if len(terms) < MIN_TERMS:
            problems.append(f"{s['slug']}: terms 只有 {len(terms)} 条（下限 {MIN_TERMS}）")

    # 地区分布，供人一眼核对
    from collections import Counter
    cc = Counter(s.get("region") for s in src)
    print(f"\n地区分布（{len(cc)} 种）：")
    for k, v in sorted(cc.items(), key=lambda kv: (-kv[1], kv[0] or "")):
        print(f"   {k or '(空)':8s} {v}")

    print(f"\n问题 {len(problems)} 项")
    for p in problems:
        print("  ✗", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
