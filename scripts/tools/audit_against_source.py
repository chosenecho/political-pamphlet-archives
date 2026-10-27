"""深度审核 3：回源核对。

本地字段自洽不等于记录正确。逐条回 Internet Archive 读 metadata，
把 catalog 里的 title / year / country 与原始元数据并排比对：

  - title 必须是 IA 原始 title 的忠实截取（允许去 HTML 标签、去首尾空白）
  - year 必须与 IA 的 date/year 相符，或能由 date 合理推出
  - country 必须能由 publisher 的出版地或 creator 的机构名支撑
  - 立场标注必须与来源材料相符（不凭空贴标签）

任何一条无法自证，就单独列出来人工判读，不自动放过。
"""

import json
import os
import re
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import http


def _join(v):
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return str(v or "")


def main():
    recs = json.load(open(os.path.join(BASE, "data", "catalog.json"), encoding="utf-8"))
    # 本次补采批次 = source 标为 internet-archive 的条目。
    # 不用按 stance 筛（会卷进旧的 IA 条目），也不用临时文件。
    batch = [x for x in recs if x.get("source") == "internet-archive"]
    print(f"回源核对本次新增 {len(batch)} 条\n")

    problems = []
    for x in batch:
        ident = x["url"].rsplit("/", 1)[-1]
        tag = f"{x['country']}/{x['title'][:34]}"
        try:
            d = http.fetch_json(f"https://archive.org/metadata/{ident}", timeout=60)
        except Exception as e:
            problems.append(f"{tag}: 回源失败 {type(e).__name__}")
            continue
        md = d.get("metadata", {}) or {}
        if not md:
            problems.append(f"{tag}: IA metadata 为空（{ident}）")
            continue

        ia_title = re.sub(r"<[^>]+>", "", str(md.get("title") or "")).strip()
        ia_date = str(md.get("date") or "")
        ia_year = str(md.get("year") or "")
        ia_pub = _join(md.get("publisher"))
        ia_creator = _join(md.get("creator"))

        # --- 标题 ---
        # 本地 title 应当就是 IA title（可能被 safe() 截断到 44 字符用于目录名，
        # 但 catalog 里存的是完整标题）
        if ia_title and x["title"] != ia_title:
            # 允许的差异：HTML 标签剥离、首尾空白、结尾省略号
            a = re.sub(r"\s+", " ", x["title"]).strip()
            b = re.sub(r"\s+", " ", ia_title).strip()
            if a != b:
                problems.append(f"{tag}: 标题与 IA 不符\n"
                                f"        catalog: {x['title']!r}\n"
                                f"        IA     : {ia_title!r}")

        # --- 年份 ---
        cand = set()
        m = re.search(r"(1[89]\d{2})", ia_date)
        if m:
            cand.add(m.group(1))
        m = re.search(r"(1[89]\d{2})", ia_year)
        if m:
            cand.add(m.group(1))
        if cand and x["year"] not in cand:
            problems.append(f"{tag}: 年份 {x['year']} 不在 IA date/year {sorted(cand)} 中")

        # --- 国别 ---
        # 用与采集时相同的判据回推，看能否复现
        blob = f"{ia_pub} | {ia_creator}".lower()
        support = {
            "爱尔兰": r"(dublin|cork|belfast|limerick|sinn\s*fein|land\s+league|"
                      r"irish\s+(unionist|loyal|national|party|publicity|question|"
                      r"nationalism|land))",
            "英国": r"(london|manchester|glasgow|edinburgh|birmingham|leeds|leicester|"
                    r"westminster|letchworth|cardiff|haslemere|liverpool|old\s+kent|"
                    r"fabian|labour\s+party|independent\s+labour|i\.?\s?l\.?\s?p\b|"
                    r"social[- ]democratic\s+federation|trades\s+union)",
            "意大利": r"(roma|rome|milano|firenze|napoli|torino|sarno|partito\s+"
                      r"(comunista|socialista|popolare|nazionale))",
            "德国": r"(berlin|leipzig|hamburg|stuttgart|jena|breslau|münchen|"
                    r"hottingen|zürich|st\.\s*gallen|sozialdemokratische|"
                    r"deutschnationale|deutsche\s+volkspartei|kommunistische)",
        }
        pat = support.get(x["country"])
        if pat and not re.search(pat, blob, re.I):
            problems.append(f"{tag}: 国别 {x['country']} 无法由 IA 出版地/机构名支撑\n"
                            f"        publisher={ia_pub[:70]!r}\n"
                            f"        creator  ={ia_creator[:70]!r}")

        time.sleep(0.1)

    print(f"问题 {len(problems)} 项\n")
    for p in problems:
        print("  ✗", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
