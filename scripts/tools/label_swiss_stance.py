"""为瑞士海报批次逐条标注立场。

瑞士实行直接民主，选举与公投海报多由政党、行动委员会或行业组织刊发。
按海报上的党派名与议题判定，不宜一律套「选举宣传」。
能识别出党派的标党派，只有议题的标议题类别，两者都不明的留空。
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
META = os.path.join(BASE, "images", "swiss-posters", "metadata.json")

#: 标题/描述关键词 -> 立场
RULES = [
    # 政党
    (r"sozialdemokratisch|sozialdemokrat", "社会民主党"),
    (r"freisinnig|freisinnige|parti radical|radikale", "自由民主党"),
    (r"bürgerlich|bürger-partei|bürgerpartei", "公民党与中右翼"),
    (r"konservativ|christlichsozial|katholisch", "保守派"),
    # 议题（政党或行动委员会刊发）
    (r"völkerbund|société des nations|societe des nations", "国际联盟议题"),
    (r"bolch[ée]visme|bolchevisme|bolschewismus", "反共宣传"),
    (r"arbeitszeit|48 ?h|44 ?stunden|48 ?ore|48 ?heures|lohnarbeit|arbetszeit", "工时法议题"),
    (r"alters-?|invaliden|rottenberg|renten", "养老与残障保险议题"),
    (r"branntwein|schnaps|alkohol|trockenlegung", "禁酒议题"),
    (r"getreide|brot|brotkorb|brotmonopol", "粮食与面包价格议题"),
    (r"proporz|majorz|nationalrat", "选举制度议题"),
    (r"papier oder arbeit", "就业议题"),
    (r"spital|inselspital", "公共卫生议题"),
    (r"hausier", "行商法议题"),
    (r"freiheit", "自由议题"),
    (r"gerechtigkeit", "公投议题"),
    (r"einmalige abgabe|vermögensabgabe|prélèvement|prelevement|liquida", "财产税议题"),
    # 1919–1922 年革命与通胀背景下的防御性宣传（保卫家园、勿受束缚）
    (r"schirm das haus|lass dich nicht binden", "保守派防御宣传"),
    # 意大利语「工作自由」＝反对法定工时限制
    (r"libertà di lavoro|liberta di lavoro", "工时法议题"),
    # 法语养老残障保险（对应德语 Rothenberger 倡议）
    (r"vieillards et les invalides", "养老与残障保险议题"),
]


def main():
    items = json.load(open(META, encoding="utf-8"))
    changed, unknown = 0, []

    for it in items:
        blob = f"{it.get('desc','')} {it.get('artist','')} {it.get('title','')}"
        hit = None
        for pat, stance in RULES:
            if re.search(pat, blob, re.I):
                hit = stance
                break
        it["stance"] = hit or ""
        if hit:
            changed += 1
        else:
            unknown.append(it)

    json.dump(items, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    from collections import Counter
    print(f"标注 {changed} 条，无法判定 {len(unknown)} 条\n")
    for k, v in Counter(it["stance"] or "(未标)" for it in items).most_common():
        print(f"   {k:18s} {v}")
    if unknown:
        print("\n无法判定的：")
        for it in unknown:
            print(f"   {it['no']:02d} {it['year']} {it['title'][:50]}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
