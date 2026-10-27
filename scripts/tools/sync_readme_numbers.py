"""把 README 里的目录统计数字更新为数据实算值。

并发协作时 README 常被其他会话改动，逐处手工编辑容易冲突。
本脚本按固定模式替换，幂等，可反复运行。
"""

import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
README = os.path.join(BASE, "README.md")


def main():
    recs = json.load(open(os.path.join(BASE, "data", "catalog.json"), encoding="utf-8"))
    books = [r for r in recs if r["kind"] == "小册子"]
    total, nb, npages = len(recs), len(books), sum(r["pages"] for r in books)
    singles = total - nb
    countries = len({r["country"] for r in recs})
    st = sum(1 for r in recs if r["stance"])
    src = sum(1 for r in recs if r["source"])

    s = io.open(README, encoding="utf-8").read()
    orig = s
    subs = [
        # 目录条目表
        (r"\*\*权威条目目录\*\*：\d+ 条（\d+ 本小册子 \+ \d+ 件单页）",
         f"**权威条目目录**：{total} 条（{nb} 本小册子 + {singles} 件单页）"),
        # 图像缺席说明
        (r"Pages 上 \d+ 张图全部 404",
         f"Pages 上 {total} 张图全部 404"),
        # 筛选维度说明
        (r"`stance` 只有 \d+/\d+ 有值，`source` 只有 \d+/\d+",
         f"`stance` 只有 {st}/{total} 有值，`source` 只有 {src}/{total}"),
        # 实体材料统计
        (r"\*\*\d+ 本多页小册子（\d+ 页）\*\* \+ \*\*\d+ 件单页传单／海报\*\*，覆盖 \d+ 国",
         f"**{nb} 本多页小册子（{npages} 页）** + **{singles} 件单页传单／海报**，覆盖 {countries} 国"),
        # 来源回填
        (r"目前回填 \d+/\d+ 条",
         f"目前回填 {src}/{total} 条"),
    ]
    for pat, rep in subs:
        s2, n = re.subn(pat, rep, s)
        if n:
            print(f"  替换 {n} 处：{pat[:44]}")
        s = s2

    if s != orig:
        io.open(README, "w", encoding="utf-8", newline="\n").write(s)
        print("README 已更新")
    else:
        print("README 无需改动")

    print(f"\n实际：{total} 条 / 小册子 {nb} 本 {npages} 页 / 单页 {singles} 件 / "
          f"{countries} 国 / 立场 {st} / 来源 {src}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
