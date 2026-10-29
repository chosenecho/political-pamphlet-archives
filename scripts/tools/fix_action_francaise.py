"""修正标题已明示组织、stance 却与之矛盾的条目。

起因：`tools/audit_stance.py` 的机构名矛盾检查抓出 `L'Action française-1918.jpg`
标成了「选举宣传」。回源 Commons 元数据核实：

    ImageDescription: A partir du 10 avril, lire dans l'Action française, journal
                      quotidien, 5 c[entim]es, la Vermine du monde, roman (inédit)
                      de l'espionnage allemand par Léon Daudet : [affiche]
    Categories:       Action française posters and leaflets | Political posters of France
    DateTimeOriginal: 1918

这是《法兰西行动报》的订阅广告海报（Léon Daudet 的连载小说宣传），不是选举材料。
法兰西行动是保皇派/极右翼组织，目录里已有专用立场「极右·行动法兰西」，
`tools/fix_poster_stance.py` 对 action française 也是这么判的。

判据是 Commons 的分类与描述，不是标题关键词猜测。逐条写明依据，不批量改。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog

#: (标题, 目标立场, 依据)
FIX = [
    ("L'Action française-1918.jpg", "极右·行动法兰西",
     "Commons 分类 Action française posters and leaflets + 描述为该报连载小说订阅广告"),
]


def main():
    recs = catalog.load()
    by_title = {}
    for r in recs:
        by_title.setdefault(r["title"], []).append(r)

    changed = 0
    for title, stance, why in FIX:
        rows = by_title.get(title)
        if not rows:
            print(f"!! 目录里找不到 {title!r}，跳过")
            continue
        for r in rows:
            old = r["stance"]
            if old == stance:
                print(f"   {title:40s} 已是 {stance}")
                continue
            r["stance"] = stance
            changed += 1
            print(f"   {title:40s} {old or '(未标)'} → {stance}")
            print(f"      依据：{why}")

    if changed:
        catalog.save(recs)
        print(f"\n已修正 {changed} 条")
    else:
        print("\n无需改动")
    return 0


if __name__ == "__main__":
    sys.exit(main())
