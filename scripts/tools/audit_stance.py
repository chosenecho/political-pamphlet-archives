"""立场标注审计：词表一致性 + 与机构名的机械矛盾。

这个脚本原本维护一份手写的「各国允许立场」白名单（19 国，漏中国、瑞士、
葡萄牙，还留着 4 个从未落地的值）。它的问题不是写错了几个值，而是**它本身
就是第三份词表**——和 21 个采集脚本里的字面量、和 `data/catalog.json` 里的
实际取值并列，三者从来没有同步过。按旧版跑会报 129 条违规，其中 55 条是
瑞士的「选举宣传」——那批是 `tools/label_swiss_tiff.py` 有意标到较宽类别的。

现在词表只有一处：`lib/vocab.py`。本脚本改为查四件事：

  1. 目录里的每个取值是否已登记（未登记 = 有人在裸写，必须拦）
  2. RESERVED 里登记了却一直没有条目的（规则可能根本没命中过）
  3. STANCE 里登记了但从未用过的（可能是退役后忘了移走）
  4. 标题能读出机构名、立场却与之矛盾的（机械可判的那几种）

国别与立场的一一对应关系不再检查。理由：立场本来就不该被国别限定——
「社会主义」在 11 个国家都有，强行按国别列白名单会把跨国的思潮拆碎。
原来那句「立场必须出现在该国的允许集合内」是词表分裂的副产品，不是需求。

用法：
    python scripts/tools/audit_stance.py            # 全库
    python scripts/tools/audit_stance.py --country 瑞士
    python scripts/tools/audit_stance.py --unmarked # 只看未标注的
"""

import argparse
import os
import re
import sys

#: scripts/ 之下才是 `lib`，所以要加的是上两级（tools/ → scripts/），不是仓库根。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import vocab

#: 标题里读得出机构名 -> 应当对应的立场。
#:
#: 只收**判据唯一**的：标题写了 Sinn Féin 就不该是「联合派」，写了 Fabian
#: 就不该是别的。这类矛盾是机械可判的，值得报。
#: 反例（不要加进来）：标题有 "socialist" 也可能是反社会主义的论战册，
#: 加了就是误报——这类只能人工读。
ORG_CONFLICT = [
    (r"sinn\s*f[eé]in", {"共和派"}, "新芬党"),
    (r"fabian", {"费边社会主义"}, "费边社"),
    (r"nationalsozialistische|nsdap", {"纳粹主义"}, "纳粹党"),
    (r"partito\s+nazionale\s+fascista", {"法西斯主义"}, "意大利法西斯党"),
    (r"independent\s+labour\s+party|\bI\.\s*L\.\s*P\.", {"工党与社会主义"}, "独立工党"),
    (r"chartist", {"宪章运动"}, "宪章派"),
    (r"cartel\s+des\s+gauches", {"左翼联盟"}, "左翼联盟"),
    (r"action\s+fran[çc]aise", {"极右·行动法兰西"}, "法兰西行动"),
    (r"peronista|justicialista", {"庇隆主义"}, "庇隆主义"),
]


def report(recs, country=None, only_unmarked=False):
    total = len(recs)
    problems = []

    # --- 1. 未登记取值：唯一会导致构建失败的一条 ---
    st = vocab.stats(recs)
    print(f"立场词表：已登记 {st['registered']} 个、预留 {st['reserved']} 个；"
          f"本批 {total} 条里用到 {st['used']} 个值，未标 {st['unmarked']} 条")
    unregistered = vocab.unknown(r["stance"] for r in recs)
    if unregistered:
        print("\n未登记的取值（会被 catalog.save() 拒绝写入）：")
        for v, n in unregistered:
            print(f"  ✗ {v:22s} {n:3d} 条")
            problems.append(f"未登记 {v}")
    else:
        print("  ✓ 全部取值已登记")

    # --- 2. 预留但从未命中 ---
    if st["reserved_hit"]:
        print(f"\n预留值已被写入数据：{st['reserved_hit']}")
        print("  → 把它们从 RESERVED 移到 STANCE，并补一条依据注释")

    # --- 3. 登记但从未使用 ---
    if st["never_used"]:
        print(f"\n登记了但全库无条目：{st['never_used']}")
        print("  → 若确认退役，移到 vocab.RETIRED；若是新登记还没采到，忽略")

    # --- 4. 与机构名的机械矛盾 ---
    conflicts = []
    for r in recs:
        s = vocab.normalize(r["stance"])
        if not s:
            continue
        blob = f"{r['title']} {r['title_zh']}"
        for pat, expect, label in ORG_CONFLICT:
            if re.search(pat, blob, re.I) and s not in expect:
                conflicts.append((r, label, s, sorted(expect)))
    if conflicts:
        print(f"\n标题与立场的矛盾 {len(conflicts)} 条：")
        for r, label, s, expect in conflicts:
            print(f"  ✗ {r['country']:4s} {r['year'] or '????'} [{s}] "
                  f"是{label}材料，应为 {'/'.join(expect)} —— {(r['title_zh'] or r['title'])[:44]}")
        problems.extend(r["title"][:30] for r, *_ in conflicts)
    else:
        print("\n  ✓ 无标题/立场矛盾")

    # --- 未标注清单（不是错误，是待办） ---
    if only_unmarked or not problems:
        blank = [r for r in recs if not vocab.normalize(r["stance"])]
        print(f"\n未标注 {len(blank)}/{total} 条" + ("（按来源）" if not country else ""))
        if not country:
            from collections import Counter
            for k, v in Counter(r["source"] or "(空)" for r in blank).most_common():
                print(f"    {k:22s} {v:4d}")

    print()
    if problems:
        print(f"失败：{len(problems)} 项")
        return 1
    print("通过")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", help="只看某国别")
    ap.add_argument("--unmarked", action="store_true", help="只列未标注的")
    args = ap.parse_args()

    recs = catalog.load()
    if not recs:
        print("目录为空或不存在")
        return 1
    if args.country:
        recs = [r for r in recs if r["country"] == args.country]
    return report(recs, args.country, args.unmarked)


if __name__ == "__main__":
    # Windows 控制台是 GBK，德/法/俄文人名会撞上 UnicodeEncodeError。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
