"""actor 轴可行性审计：结论是**现在做不了**，这个脚本给出可复算的依据。

为什么要留一个"不做"的脚本
    拆轴不是越多越好。`purpose` 能做成是因为未判定的主因是「标题里没有判据」，
    换个判据（Commons 分类、描述）就能解决；而 `actor` 未判定的主因是
    「我们的元数据里根本没收刊发者」——那是采集侧的工作，标注侧无论怎么写
    规则都变不出来。

    这种判断不该只是一句话。跑一遍这个脚本就能看到分母有多小，
    下次有人想加 actor 时先看这里。

三个硬来源及其局限：
    A. Internet Archive 的 creator
       形态可靠（`Social Democratic Federation`、
       `Sozialdemokratische Arbeiterpartei Deutschösterreichs`），
       但**只对留存了中间数据的批次可用**。当前 catalog 148 条 IA 条目里，
       只有 round10 那 53 条有本地 metadata（`images/round10/metadata.json`），
       其余 95 条的 creator 在采集时就丢了。

    B. modernhistory 的 publisher / responsible
       有组织名（`总政治部`、`辽吉省委宣传部`），但 catalog 里只有 19 条中国
       条目，其中 15 条属早期批次、metadata 未留存，能取到的只有 3 条。

    C. Commons 的政党分类
       只有精选批次带（瑞士 54 条，已用于 stance）。384 条 Commons 单页里
       实测 8 条命中组织分类，且多数是 `Images from the Library of Congress`
       这类**馆藏方**而不是刊发者。

补数据的三个方向（按性价比）：
    1. 回源 Internet Archive 重取 95 条旧条目的 creator —— 一条命令的事，
       但要联网、archive.org 近期整站超时过。做完能到 ~22%（148/593）。
    2. 逐条打开馆藏详情页取「出版者」—— 人工量大，但 19 条中国条目值得做。
    3. 读图 OCR 取海报上的刊发者署名 —— 成本最高，效果最不确定。

跑法：
    python scripts/tools/audit_actor_feasibility.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

#: 组织形态特征。IA 的 creator 是 `作者名, 生卒年 | 组织名` 合串，需拆分。
ORG_FORM = re.compile(
    r"(Party|Partei|Parti|Partito|Partido|Society|Gesellschaft|Société|"
    r"League|Liga|Ligue|Union|Unionist|Association|Verband|Bund\b|"
    r"Committee|Komitee|Comité|Council|Rat\b|Congress|Kongress|"
    r"Federation|Föderation|Alliance|Institute|Institut|"
    r"Government|Office|Department|Bureau|Agency|Ministry|"
    r"Press|Verlag|Buchhandlung|Tipografiia|"
    r"部|会|社|联军|委员会|团|党|军|馆|局|所|联合会|总政)",
    re.I)


def split_creator(s):
    """IA creator 常是 `A | B | C`，拆开并分出组织与人名。"""
    parts = [x.strip() for x in str(s or "").split("|") if x.strip()]
    orgs = [x for x in parts if ORG_FORM.search(x)]
    return orgs, [x for x in parts if x not in orgs]


def main():
    recs = catalog.load()
    total = len(recs)
    print(f"全库 {total} 条\n")

    # ---- A: IA creator ----
    r10 = os.path.join(paths.IMAGES, "round10", "metadata.json")
    md10 = json.load(open(r10, encoding="utf-8")) if os.path.exists(r10) else []
    by_url = {r["url"]: r for r in recs if r["url"]}
    ia = [r for r in recs if r["source"] == "internet-archive"]
    matched = [m for m in md10 if m.get("url") in by_url]

    a_org = []
    for m in matched:
        r = by_url[m["url"]]
        orgs, _ = split_creator(m.get("creator"))
        pub = str(m.get("publisher") or "").strip()
        if pub and ORG_FORM.search(pub):
            orgs.append(pub)
        if orgs:
            a_org.append((r, orgs))

    print("A. Internet Archive 的 creator")
    print(f"   catalog 里 IA 条目 {len(ia)} 条")
    print(f"   本地留存 metadata 的 {len(matched)} 条"
          f"（缺 {len(ia) - len(matched)} 条，采集时未保留 creator）")
    print(f"   其中 creator/publisher 含组织 {len(a_org)} 条")
    for r, orgs in a_org[:6]:
        print(f"     {r['country']:4s} {orgs[0][:46]}")
    if len(a_org) > 6:
        print(f"     …另 {len(a_org) - 6} 条")

    # ---- B: modernhistory publisher/responsible ----
    mh_path = os.path.join(paths.METADATA, "modernhistory.json")
    mh = json.load(open(mh_path, encoding="utf-8")) if os.path.exists(mh_path) else []
    by_title = {}
    for m in mh:
        by_title.setdefault(m["title"].strip(), []).append(m)
    cn = [r for r in recs if r["source"] == "modernhistory-cn"]
    b_org, b_missing = [], 0
    for r in cn:
        cand = by_title.get(r["title"].strip())
        if not cand:
            b_missing += 1
            continue
        m = cand[0]
        pub = str(m.get("publisher") or "").strip()
        resp = str(m.get("responsible") or "").strip()
        v = pub if (pub and pub != "--") else (resp if resp not in ("不详", "--", "") else "")
        if v and ORG_FORM.search(v):
            b_org.append((r, v))

    print("\nB. modernhistory 的 publisher / responsible")
    print(f"   catalog 里中国条目 {len(cn)} 条，其中 {b_missing} 条"
          f"在仓库 metadata 里没有（早期批次未留存）")
    print(f"   能取到组织 {len(b_org)} 条")

    # ---- C: Commons 分类 ----
    wiki_n = sum(1 for r in recs if r["source"] == "wiki-commons")
    print("\nC. Commons 的政党分类")
    print(f"   384 条单页里只有瑞士 54 条带政党分类（已用于 stance）")
    print(f"   其余 {wiki_n - 54} 条只有作者与许可——馆藏方不是刊发者")

    got = len(a_org) + len(b_org)
    print("\n结论")
    print(f"   可得的 actor：{len(a_org)} + {len(b_org)} = {got} 条"
          f"（{got / total * 100:.1f}%）")
    print(f"   未判定 {total - got} 条（{(total - got) / total * 100:.1f}%）")
    print("\n   这个比例不支持把 actor 做成筛选项。与 purpose 的差别在于缺口性质：")
    print("   purpose 缺的是「判据」，能换方法解决；actor 缺的是「数据」，")
    print("   得从采集侧补。硬做成筛选项只会让用户点开看到几十条。")
    print("\n   下一步若要做，优先回源 IA 重取 95 条旧条目的 creator")
    print("   （做完约 22%），其次逐条取中国 19 条的出版者。")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
