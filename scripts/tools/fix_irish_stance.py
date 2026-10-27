"""修正本次补采中 5 条爱尔兰条目的立场标注。

问题：这 5 条的 creator 是个人（De Valera、Mac Neill、Sheehy-Skeffington 等）
或商业出版社，采集时 ORG_RULES 未命中机构名，退回出版地兜底给了"民族主义"。
但它们的 IA subject 明确含 "Sinn Fein"，标题亦直指新芬党，应标"共和派"。

只改这 5 条，其余不动；逐条回源确认 subject 后再改，不靠猜。
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import http
from lib import index as catalog

#: 人工核验结论：(identifier, 依据的 IA subject 片段, 目标立场)
FIX = [
    ("countplunkettman00redd", "Sinn Fein", "共和派"),
    ("testamentofrepub00deva", "Sinn Fein", "共和派"),
    ("impressionsofsin00shee", "Sinn Fein", "共和派"),
    ("issuecaseforsinn00lect", "Sinn Fein", "共和派"),
    ("danieloconnellsi00macn", "Sinn Fein", "共和派"),
]


def main():
    recs = catalog.load()
    by_ident = {}
    for r in recs:
        by_ident.setdefault(r.get("url", "").rsplit("/", 1)[-1], []).append(r)

    changed = 0
    for ident, needle, stance in FIX:
        rows = by_ident.get(ident)
        if not rows:
            print(f"!! 目录里找不到 {ident}，跳过")
            continue

        # 回源复核：subject 里必须真有该片段，否则不动
        try:
            d = http.fetch_json(f"https://archive.org/metadata/{ident}", timeout=60)
        except Exception as e:
            print(f"!! {ident} 回源失败 {type(e).__name__}，保守起见不改")
            continue
        md = d.get("metadata", {}) or {}
        subj = md.get("subject")
        subj_txt = " | ".join(subj) if isinstance(subj, list) else str(subj or "")
        if needle.lower() not in subj_txt.lower():
            print(f"!! {ident} 的 subject 里没有 {needle!r}，保守起见不改")
            continue

        for r in rows:
            old = r["stance"]
            if old != stance:
                r["stance"] = stance
                changed += 1
                print(f"   {ident:26s} {old} → {stance}")

    if changed:
        catalog.save(recs)
        print(f"\n已修正 {changed} 条")
    else:
        print("\n无需改动")
    return 0


if __name__ == "__main__":
    sys.exit(main())
