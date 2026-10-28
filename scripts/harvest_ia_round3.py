"""Internet Archive 第三轮补采：按人工核验结果逐条收录。

本轮针对「仍无小册子」的国别（波兰、拉美、苏联）与偏少的国别。
第三轮探测命中的多数是同形词——`programa`（节目单）、`estatuto`（协会章程）、
`program`（活动手册），逐条读 publisher / creator / subject 才分得清。
因此本版仍是**显式白名单**，每条都写了核验依据。

明确排除的（读元数据后判定非政党宣传品）：
  · 捷克 stanovypraidlaop00inte —— 芝加哥铁匠工会章程（捷克语，但是美国工会）
  · 荷兰 calvijneenstrijd00proo —— 加尔文研究专著，非政党文献
  · 荷兰 statutenderveree00vere —— 苏门答腊农业矿业协会章程
  · 荷兰 b30631427 —— 莱顿医学史学会章程
  · 苏联 B-001-018-007 —— 立宪民主党纲领，但 metadata 只剩 SINGLE_PAGE_JPG，
    无从核验页数，不收（同书正文另有可核验版本时再补）
  · 苏联 Ustav_Obshchegos_soiuza_trudiash —— metadata 为空
  · 瑞典 midsummerprogram* —— 仲夏节活动手册，与政党无关

用法：
    python scripts/harvest_ia_round3.py --dry
    python scripts/harvest_ia_round3.py
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only)")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "images", "ia-round3")
RAW = os.path.join(ROOT, "raw")
CATALOG = os.path.join(BASE, "data", "catalog.json")

MAX_PAGES_DL = 80
PDF_MAX_MB = 25

#: (identifier, 国别, 立场, 核验依据)
KEEP = [
    # --- 波兰 ---
    ("programpolskiego00stro", "波兰", "民族主义",
     "民族民主党 1905 年利沃夫代表大会通过的民族民主党纲领（1906 印行）"),
    ("programtaktykaor00polsuoft", "波兰", "社会主义",
     "波兰社会党（PPS）纲领、策略与组织，1908"),
    ("odezwadonarodows00hoen", "波兰", "政治思想宣传",
     "霍恩-弗龙斯基《告斯拉夫各民族书》，1848，波兰弥赛亚主义政治檄文"),

    # --- 拉美 ---
    ("plataformadeacci00part", "拉美", "选举宣传",
     "墨西哥国家反连任党 1927 年代表大会通过的政治行动纲领"),
    ("laconquistadelgo01dick", "拉美", "社会主义",
     "迪克曼《市政权力的夺取》，阿根廷社会党出版物，1914"),
    ("manifestodelpart00part", "拉美", "自由主义",
     "智利自由党《告同仁宣言》，1896"),

    # --- 苏联 ---
    ("khitraya_mekhanika", "苏联", "共产主义",
     "《狡猾的机械》，1919 年苏俄内战政治宣传读物"),
    ("belofinskoe_zvere", "苏联", "战时宣传",
     "《白芬兰野兽》，1943 年苏联战时宣传册"),
]


def get_json(url, timeout=60, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                return json.loads(r.read())
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


def fetch_file(url, path, timeout=240, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                data = r.read()
            if len(data) < 3000:
                raise ValueError("too small")
            with open(path, "wb") as f:
                f.write(data)
            return len(data)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))


def pick_pdf(meta):
    best, best_size = None, 0
    for f in meta.get("files", []):
        if not str(f.get("name", "")).endswith(".pdf"):
            continue
        try:
            sz = int(f.get("size") or 0)
        except (TypeError, ValueError):
            sz = 0
        if best is None or (sz and sz < best_size):
            best, best_size = f["name"], sz
    if best and best_size <= PDF_MAX_MB * 1048576:
        return best, best_size
    return None, 0


def _join(v):
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return str(v or "")


def known_ids():
    recs = json.load(open(CATALOG, encoding="utf-8"))
    out = set()
    for r in recs:
        u = r.get("url", "")
        if "archive.org/details/" in u:
            out.add(u.rsplit("/", 1)[-1].split("?")[0])
    return out


def main():
    dry = "--dry" in sys.argv
    have = known_ids()

    items = []
    for ident, country, stance, basis in KEEP:
        if ident in have:
            print(f"  跳过（已收录）{ident}")
            continue
        try:
            meta = get_json(f"https://archive.org/metadata/{ident}")
        except Exception as e:
            print(f"  跳过 {ident}: metadata 失败 {type(e).__name__}")
            continue
        md = meta.get("metadata", {}) or {}
        title = re.sub(r"<[^>]+>", "", str(md.get("title") or "")).strip()
        if not title:
            print(f"  跳过 {ident}: 无标题")
            continue
        try:
            pages = int(md.get("imagecount") or 0)
        except (TypeError, ValueError):
            pages = 0
        if pages < 8:
            print(f"  跳过 {ident}: 页数 {pages}")
            continue
        year = str(md.get("date") or md.get("year") or "")[:4]
        if not year.isdigit():
            m = re.search(r"(1[89]\d{2}|19\d{2})", str(md.get("date") or ""))
            year = m.group(1) if m else ""

        pdf_name, _ = pick_pdf(meta)
        items.append({
            "country": country, "stance": stance, "identifier": ident,
            "title": title, "year": year, "pages": min(pages, MAX_PAGES_DL),
            "creator": _join(md.get("creator"))[:100],
            "publisher": _join(md.get("publisher"))[:80],
            "url": f"https://archive.org/details/{ident}",
            "basis": basis, "pdf_name": pdf_name,
        })
        time.sleep(0.15)

    print(f"\n白名单可用 {len(items)} 本：")
    for c in items:
        print(f"  {c['country']:4s} {c['year']:4s} {c['pages']:3d}p "
              f"{c['identifier'][:30]:30s} {c['basis'][:42]}")

    if dry:
        return

    os.makedirs(RAW, exist_ok=True)
    records = []
    for c in items:
        n = len(records) + 1
        folder = os.path.join(RAW, f"{n:03d}")
        os.makedirs(os.path.join(folder, "pages"), exist_ok=True)

        rec = {k: v for k, v in c.items() if k != "pdf_name"}
        rec["no"] = n
        rec["pdf"] = False
        if c["pdf_name"]:
            try:
                fetch_file(
                    f"https://archive.org/download/{c['identifier']}/{urllib.parse.quote(c['pdf_name'])}",
                    os.path.join(folder, "doc.pdf"))
                rec["pdf"] = True
            except Exception as e:
                rec["pdf_error"] = type(e).__name__

        ok = 0
        for p in range(min(c["pages"], MAX_PAGES_DL)):
            try:
                fetch_file(f"https://archive.org/download/{c['identifier']}/page/n{p}_w1000.jpg",
                           os.path.join(folder, "pages", f"p-{p + 1:05d}.jpg"), timeout=120)
                ok += 1
            except Exception:
                pass
            time.sleep(0.06)
        rec["pages_got"] = ok

        if ok < 4:
            import shutil
            print(f"  丢弃 {c['identifier']}: 只取到 {ok} 页")
            shutil.rmtree(folder, ignore_errors=True)
            continue

        records.append(rec)
        print(f"  {c['country']:4s} {c['year']:4s} 图{ok:>3d} "
              f"pdf{'✓' if rec['pdf'] else '×'}  {c['title'][:40]}", flush=True)
        time.sleep(0.3)

    json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    from collections import Counter
    print(f"\n=== 采到 {len(records)} 本 ===")
    for k, v in Counter(r["country"] for r in records).most_common():
        print(f"   {k:5s} {v}")


if __name__ == "__main__":
    main()
