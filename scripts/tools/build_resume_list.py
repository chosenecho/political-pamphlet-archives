"""生成断点续传清单：把 ia-gap 与 ia-deep 两批的候选汇总成一份 JSON。

ia-gap 的候选来自 harvest_ia_gap.py 的召回逻辑（不下载），
ia-deep 的候选来自 harvest_ia_deep.py 的白名单。
本脚本只做汇总与页数核对，不下载。
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import ssl

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import http

UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only)")

#: ia-deep 白名单（逐条核验过，见 harvest_ia_deep.py 的 KEEP）
DEEP_KEEP = [
    ("mkbook0300mkga", "印度", "民族主义"),
    ("mkgpamphlet0400mkga", "印度", "民族主义"),
    ("mkgpamphlet0300mkga", "印度", "民族主义"),
    ("mkbook1700mkga", "印度", "民族主义"),
    ("mkbook1600mkga", "印度", "民族主义"),
    ("mkbook2200mkga", "印度", "民族主义"),
    ("villageindustrie00bhar", "印度", "民族主义"),
    ("agrarianproblemi00ahma", "印度", "民族主义"),
    ("chairmansspeech400gidw", "印度", "民族主义"),
    ("memorandumtomemb00indiuoft", "印度", "民族主义"),
    ("translationoflea00cawn", "印度", "共产主义"),
    ("futureofindiapre00sinhiala", "印度", "民族主义"),
    ("manifestodelpart00part", "拉美", "自由主义"),
    ("ElFuturoPresidente_Bastitta_1919", "拉美", "选举宣传"),
    ("programmastatuto00azio", "意大利", "天主教民众派"),
    ("1248955", "意大利", "天主教民众派"),
]


def meta(ident):
    return http.fetch_json(f"https://archive.org/metadata/{ident}", timeout=60)


def pick_pdf(m):
    best, best_size = None, 0
    for f in m.get("files", []):
        if not str(f.get("name", "")).endswith(".pdf"):
            continue
        try:
            sz = int(f.get("size") or 0)
        except (TypeError, ValueError):
            sz = 0
        if best is None or (sz and sz < best_size):
            best, best_size = f["name"], sz
    if best and best_size <= 20 * 1048576:
        return best
    return None


def _j(v):
    return " | ".join(str(x) for x in v) if isinstance(v, list) else str(v or "")


def main():
    # 现有目录里的 URL，用于去重
    recs = json.load(open(os.path.join(BASE, "data", "catalog.json"), encoding="utf-8"))
    have = {r.get("url", "").rsplit("/", 1)[-1] for r in recs if r.get("url")}

    items = []

    # --- ia-deep：跳过已收录 ---
    n = 0
    for ident, country, stance in DEEP_KEEP:
        if ident in have:
            print(f"deep 跳过（已收录）{ident}")
            continue
        try:
            d = meta(ident)
        except Exception as e:
            print(f"deep 跳过 {ident}: {type(e).__name__}")
            continue
        md = d.get("metadata", {}) or {}
        title = str(md.get("title") or "").strip()
        if not title:
            print(f"deep 跳过 {ident}: 无标题")
            continue
        try:
            pages = int(md.get("imagecount") or 0)
        except (TypeError, ValueError):
            pages = 0
        if pages < 8:
            print(f"deep 跳过 {ident}: 页数 {pages}")
            continue
        year = str(md.get("date") or md.get("year") or "")[:4]
        if not year.isdigit():
            import re as _re
            m = _re.search(r"(1[89]\d{2}|19\d{2})", str(md.get("date") or ""))
            year = m.group(1) if m else ""
        n += 1
        items.append({
            "no": n, "batch": "ia-deep", "ident": ident, "country": country,
            "stance": stance, "title": title, "year": year,
            "pages": min(pages, 64), "target": min(pages, 64),
            "pdf_name": pick_pdf(d), "url": f"https://archive.org/details/{ident}",
        })
        time.sleep(0.12)

    out = os.path.join(BASE, "images", "_resume.json")
    json.dump(items, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n清单 {len(items)} 项 -> {out}")
    for it in items:
        print(f"  {it['batch']:8s} {it['country']:4s} {it['year']:4s} "
              f"{it['target']:3d}p {it['ident'][:30]:30s} {it['title'][:40]}")


if __name__ == "__main__":
    main()
