"""深度审核 5：中文译名核验。

译名由我人工填写，没有外部比对源，只能把原文与译名并排打印供复核，
并做几项机械检查：
  - 译名不能为空
  - 译名不应残留大段原文（说明只是复制未翻译）
  - 译名里的年份若存在，必须与 year 字段一致
  - 中国条目译名应为空（原文即中文）
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    recs = json.load(open(os.path.join(BASE, "data", "catalog.json"), encoding="utf-8"))
    # 本次补采批次 = source 标为 internet-archive 的条目
    batch = [x for x in recs if x.get("source") == "internet-archive"]

    problems = []
    print(f"本次新增 {len(batch)} 条的译名并排：\n")
    for x in sorted(batch, key=lambda r: (r["country"], r["year"])):
        zh = x["title_zh"]
        en = x["title"]
        print(f"[{x['country']} {x['year']}]")
        print(f"   原: {en}")
        print(f"   译: {zh}")

        if not zh:
            problems.append(f"{en[:40]}: 译名为空")
            continue
        # 残留原文判定：译名里连续出现 >=12 个 ASCII 字母
        if re.search(r"[A-Za-z]{12,}", zh):
            problems.append(f"{en[:40]}: 译名残留原文 {zh!r}")
        # 年份一致性。译名常如实反映材料内文年份，与出版年（year 字段）
        # 不完全相同属正常，不都是错：
        #   - "Verhandlungen ... Oktober 1887" 出版年 1888（会议次年印行）
        #   - "Sozialdemokratische Arbeitsgemeinschaft 1915/1916" 出版年 1916
        #   - "1st October 1886 to 31st March 1887" 出版年 1887
        #   - 苏厄德 1858 年罗切斯特演说，1860 年出版（演说先于出版两年）
        # 只有相差 >3 年才提示复查——再远就多半是真错。
        for y in re.findall(r"(1[89]\d{2}|20\d{2})", zh):
            try:
                delta = abs(int(y) - int(x["year"]))
            except ValueError:
                continue
            if delta > 3:
                problems.append(f"{en[:40]}: 译名含年份 {y}，与 year={x['year']} 相差 {delta} 年")
        # 译名不该是原文的逐字复制
        if zh == en:
            problems.append(f"{en[:40]}: 译名与原文完全相同")

    # 中国条目
    cn = [x for x in recs if x["country"] == "中国" and x["title_zh"]]
    if cn:
        problems.append(f"中国条目有 {len(cn)} 条填了 title_zh，应为空")

    print(f"\n问题 {len(problems)} 项")
    for p in problems:
        print("  ✗", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
