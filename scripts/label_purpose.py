"""为目录条目标注用途（purpose）：这份材料是用来干什么的。

背景
    `stance` 一个字段同时承担了思潮、组织、议题、用途四件事，60 个取值里
    23 个只出现 1 次。`purpose` 是拆轴的第一步：只回答「用来干什么」，
    与它持什么立场、属于哪个组织无关。

    「选举宣传」现在占 stance 的 105/369（28%），它其实是个用途而不是思潮。
    拆出去之后，`stance` 可以专心表示立场，界面也能问出「有哪些竞选海报
    是社会主义的」这种以前问不出口的问题。

判定纪律（照抄给了 stance 的教训）
    1. **宁可留空，不可错标。** 筛「集会海报」却混进照片和演说文本，这个
       筛选就没用了。留空是已声明的缺口，错标是错误。
    2. **不用生成的数据当判据。** 瑞士 85 条里有 53 条的 `title_zh` 是我们
       自己在 `title_zh.py` 里写的「瑞士选举海报（NNNN，作者）」——那不是
       原件信息，是当初为了卡片不空白补的占位译名。拿它判 purpose 等于
       用结论证明结论。这批一律留空。
    3. **不按来源类型批量套。** 同一批里竞选海报与纲领册子混装是常态。
    4. 规则顺序即优先级；只在标题/译名里能读出判据时才标。

用法
    python scripts/label_purpose.py --dry     # 只看会标成什么
    python scripts/label_purpose.py           # 写入 catalog
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import vocab

#: 生成式译名的特征：这些 `title_zh` 没有原件依据，不能作为判据。
#:
#: 「瑞士选举海报（1919，舍雷尔）」这类是我们看了档案号和作者名补的占位
#: 译名——档案号 CH-000957-X-* 本身不含题材信息，作者是海报画家。
#: 说它是「选举海报」只是因为它出自那批收藏，不是因为它上面写着选举。
GENERATED_ZH = re.compile(r"^瑞士选举海报（\d{4}")
GENERATED_ZH_GENERIC = re.compile(r"^(捷克斯洛伐克海报藏品|F[üu]r\b)")

#: 规则：(用途, 正则, 依据说明)
#:
#: 顺序即优先级。公投排在竞选之前：瑞士与奥地利的 Volksabstimmung 海报
#: 常同时含「投票」字样，先归到公投才对——它是就单一议题的表决，不是
#: 候选人竞选。
RULES = [
    ("公投动员", r"plebiscit|referendum|公投|volksabstimmung|volksbegehren|"
                 r"votation|abstimmung",
     "标题出现公投/表决字样"),

    # 「选民手册」这类是教人怎么投，不是替某个候选人拉票，先于竞选
    ("投票指引", r"voters'?\s*pamphlet|voter\s*guide|选民手册|投票指南|"
                 r"election guide|how to vote|投票须知|election manual",
     "选民手册/投票指南"),

    ("竞选宣传", r"election poster|electoral poster|election campaign|"
                 r"campaign poster|竞选海报|竞选传单|竞选纲领|竞选材料|"
                 r"选举海报|大选海报|wahlplakat|wahlaufruf|"
                 r"wybory|wyborczy|candidat|候选人|general election|"
                 r"presidential election|gubernatorial|constituency|选区|"
                 r"empadronamiento|选民登记|选举呼吁|大选",
     "标题明示竞选/选举"),

    ("集会通告", r"meeting poster|lecture|演讲会|集会海报|集会通告|"
                 r"请出席|demonstration poster|示威海报|kundgebung|"
                 r"versammlung|public meeting|mass meeting|rally poster|"
                 r"大会。（.*）请出席",
     "标题明示集会/演讲会通告"),

    ("征兵与战争动员", r"recruit|征兵|enlist|kriegsanleihe|war loan|"
                       r"战争公债|认购第.次战争公债|军团招募|军团滑雪营|legion\b|"
                       r"战时征集|战时物资|mobilization poster|动员群众|动员计划|"
                       r"反浪费运动|赠书运动|liberty loan|战争债券",
     "标题明示征兵/战争公债/战时物资动员"),

    # 演说排在纲领之前：「优等种族（1919年2月19日国民纪念碑演讲）」同时含
    # 「纪念碑」（纪念规则）与「演讲」（演说规则），它实际是一次演说记录。
    # 判据是「材料本身是什么」，不是「它在哪里讲过」。
    ("演说与报告", r"\bspeech\b| senate speech|演说|讲演|演讲|"
                   r"工作报告|总结报告|指示|讲话|"
                   r"lecture by|congressional record|参议院演说|"
                   r"要对选民讲话",
     "演说记录/工作报告/指示"),

    # `manifesto` 是意/西语里的「海报」，不是英语的「宣言」。原件
    # `Ordinamento Corporativo dello Stato Fascista manifesto storico anni 1930`
    # 是一张海报，译名也写的是「宣传画」。`manifesto storico` 是意语常见搭配
    # （历史海报），用负向先行排除这一形态。
    ("纲领与政策宣示", r"party program|party programme|"
                       r"manifesto(?!\s+storico)|党纲|纲领|宣言|政纲|成立宣言|"
                       r"resolution|决议|章程|statut|by-?laws|"
                       r"platform\b|行动纲领|政治行动纲领",
     "党纲/宣言/章程/决议"),

    ("标语口号", r"标语|口号|slogan|watchword|parole d'ordre",
     "成组标语口号"),

    ("论战与驳斥", r"reply to|answer to|答复|答\s|论战|refutation|"
                   r"反驳|驳斥|批判|warning!|警告|真实答复|问答",
     "针对另一立场的回应/驳斥"),

    ("文艺宣传", r"歌谣|诗歌|故事|小说|木刻|漫画|讽刺画|宣传画|"
                 r"cartoon|caricature|poem|song book|songbook|"
                 r"课本|教科书|读本|ABC",
     "歌谣/故事/漫画/宣传画/读本等通俗读物"),

    ("纪念与追悼", r"memorial|纪念|追悼|commemorat|周年|easter lily|"
                   r"复活节百合|纪念碑",
     "纪念/追悼/周年"),
]


def judge(rec):
    """返回 (用途, 依据)。判不出返回 ("", "")。"""
    zh = vocab.normalize(rec.get("title_zh"))
    # 生成式译名不进判据，但原题仍可用
    usable_zh = "" if (GENERATED_ZH.match(zh) or GENERATED_ZH_GENERIC.match(zh)) else zh
    blob = f"{rec.get('title', '')} {usable_zh}"

    for purpose, pat, why in RULES:
        m = re.search(pat, blob, re.I)
        if m:
            return purpose, f"{why}（命中 {m.group(0)!r}）"
    return "", ""


def main():
    dry = "--dry" in sys.argv
    recs = catalog.load()
    if not recs:
        print("目录为空")
        return 1

    before = sum(1 for r in recs if vocab.normalize(r.get("purpose")))
    planned = {}
    changed = 0

    for r in recs:
        purpose, why = judge(r)
        planned[purpose] = planned.get(purpose, 0) + 1
        old = vocab.normalize(r.get("purpose"))
        if old != purpose:
            changed += 1
            if dry or "--verbose" in sys.argv:
                tag = f"{old} → {purpose}" if old else (purpose or "(留空)")
                print(f"  {r['kind']:4s} {r['country']:4s} {r['year'] or '????'} "
                      f"[{tag:14s}] {(r['title_zh'] or r['title'])[:44]}")
                if why:
                    print(f"        {why}")
            if not dry:
                r["purpose"] = purpose

    from collections import Counter
    print(f"\n{'（试运行）' if dry else ''}判定结果：")
    for p, n in Counter(planned).most_common():
        print(f"  {p or '(留空)':16s} {n:4d}")
    print(f"\n合计 {len(recs)} 条；变动 {changed} 条；"
          f"覆盖率 {(len(recs)-planned.get('', 0))/len(recs)*100:.0f}%"
          f"（改前 {before} 条有值）")

    if dry:
        print("\n试运行不改文件。加 --verbose 看每条的依据。")
        return 0

    catalog.save(recs)
    print("已写入 data/catalog.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
