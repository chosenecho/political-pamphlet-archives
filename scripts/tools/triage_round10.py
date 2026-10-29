"""候选池粗筛：把 868 条压到能人工逐条读的量。

两版探针的候选混着三类东西：政党自己印的宣传品、第三方论著（学术、
报刊、政府公报）、以及完全不搭界的（剧作、歌剧台本、地质报告）。
第三类已由 BAD 正则滤掉，这里再区分前两类。

判据：
  1. 出版者是政党组织 / 工会 / 宣传机构 —— 最强信号，与 README 里
     「按出版机构反查命中率最高」的经验一致。
  2. 题名是这类材料的典型体裁词：manifesto、programme、Aufruf、
     profession de foi、discorso agli elettori、open letter、platform。
  3. 出版者是国家机关、大学出版社、商业出版社 —— 降权。

用法：
    python scripts/tools/triage_round10.py                 # 按分数分组计数
    python scripts/tools/triage_round10.py --top 60        # 打印前 60 条
    python scripts/tools/triage_round10.py --country 德国
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POOL = os.path.join(BASE, "images", "round10", "pool2.json")

#: 出版者/作者里出现这些词 → 政党、工会、宣传机构
PARTY = re.compile(
    r"(parti|partido|partito|partei|party\b|partij|strana\b|stronnictwo|"
    r"communist|kommunist|socialist|sozialdem|social-dem|socialdem|sociaal|"
    r"labour party|labor party|workers? party|ouvrier|obrero|arbeiter|"
    r"trade union|federation of|central committee|comit[eé] central|"
    r"national committee|national council|national league|league of|"
    r"zionist|falange|sinn f[eé]in|fianna|kuomintang|nationalist|"
    r"propaganda|aufkl[aä]rung|bildungsausschuss|parteivorstand|"
    r"volksverein|gewerkschaft|syndicat|sindicato|cooperativa)", re.I)

#: 题名里出现这些词 → 宣传册体裁
GENRE = re.compile(
    r"(manifesto|manifest|programme|programma|programm\b|program\b|aufruf|"
    r"wahlaufruf|profession de foi|open letter|lettre ouverte|address to|"
    r"an die w[aä]hler|agli elettori|aux [eé]lecteurs|a los electores|"
    r"platform|plataforma|statuten|statutes|satzung|resolution|entschliessung|"
    r"flugschrift|flugblatt|brochure|pamphlet|leaflet|tract\b|"
    r"rede\b|discorso|discours|speech|bericht|protokoll|verhandlungen|"
    r"kongress|congress|parteitag|konferenz)", re.I)

#: 出版者是国家机关、大学出版社或商业出版社 → 多为第三方论著
OFFICIAL = re.compile(
    r"(govt\.? print|government printing|stationery office|h\.?m\.?s\.?o|"
    r"imprimerie nationale|druckerei|staatsdruckerei|"
    r"university press|university|universit|hochschule|"
    r"macmillan|hodder|putnam|doran|mcgraw|harper|longman|murray|"
    r"clarendon|teubner|nijhoff|payot|larose|"
    r"foreign policy association|institute of|institut |society for|"
    r"church|mission|catholic|christian)", re.I)


def score(c):
    """返回 (分数, 理由列表)。分数只用于排序，最终仍逐条人工判。"""
    blob = " ".join([c.get("publisher", ""), c.get("creator", "")])
    s, why = 0, []
    if PARTY.search(blob):
        s += 4
        why.append("政党出版者")
    if GENRE.search(c["title"]):
        s += 3
        why.append("体裁词")
    subj = c.get("subject", "")
    if re.search(r"(campaign literature|propaganda|parties|elections|suffrage)", subj, re.I):
        s += 2
        why.append("主题标目")
    if OFFICIAL.search(blob):
        s -= 3
        why.append("官方/学术出版")
    if not c.get("publisher"):
        s -= 1
        why.append("无出版者")
    if re.search(r"\[from old catalog\]", blob):
        s -= 1
    return s, why


def main():
    with open(POOL, encoding="utf-8") as f:
        pool = json.load(f)
    for c in pool:
        c["score"], c["why"] = score(c)

    country = None
    if "--country" in sys.argv:
        country = sys.argv[sys.argv.index("--country") + 1]
        pool = [c for c in pool if country in c["label"]]

    top = 60
    if "--top" in sys.argv:
        top = int(sys.argv[sys.argv.index("--top") + 1])

    if "--top" not in sys.argv and not country:
        import collections
        for k, v in sorted(collections.Counter(c["score"] for c in pool).items(),
                           reverse=True):
            print(f"  分数 {k:>2}  {v:>4} 条")
        print(f"\n合计 {len(pool)}；分数 ≥4 的 {sum(1 for c in pool if c['score'] >= 4)} 条")
        return 0

    pool.sort(key=lambda c: (-c["score"], c["year"]))
    print(f"共 {len(pool)} 条，打印前 {min(top, len(pool))}：\n")
    for c in pool[:top]:
        print(f'{c["score"]:>2} {c["identifier"]}  {c["year"]} {c["pages"]:>3}p '
              f'{c["language"][:8]:8s} [{c["label"]}] {"·".join(c["why"])}')
        print(f'   T {c["title"][:120]}')
        print(f'   P {c["publisher"][:110]}')
        print(f'   C {c["creator"][:90]}')
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
