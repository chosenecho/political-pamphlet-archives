"""Internet Archive 第五轮补采：第四轮思路的延续，仅 2 条合格。

第五轮（西文编目 + 主题词）命中质量明显低于第四轮，大部分是宪法文本、
农产品市场报告、博物学论文。逐条核验后只收 2 条。

明确排除的代表：
  · electionsinportu0000band —— 加拿大学者的葡萄牙选举研究，非政党出版物
  · rebellionindubli00dubl / sinnfeinrebellio00unse —— 1916 年当时报刊报道
  · jstor-29738470 —— JSTOR 期刊论文
  · cihm_73530 —— 蒙特利尔天主教行动宣传，属加拿大材料
  · 大量宪法文本（Constitution of Japan 等）—— 官方文书，非宣传品

用法：
    python scripts/harvest_ia_round5.py --dry
    python scripts/harvest_ia_round5.py
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
ROOT = os.path.join(BASE, "images", "ia-round5")
RAW = os.path.join(ROOT, "raw")
CATALOG = os.path.join(BASE, "data", "catalog.json")

MAX_PAGES_DL = 90
PDF_MAX_MB = 30

KEEP = [
    ("hirtenbriefuberw0000gfol", "奥地利", "反纳粹",
     "林茨主教格弗尔纳《论真假民族主义牧函》，天主教新闻社 1933，反对纳粹民族主义"),
    ("micro_IA40244302_0249", "匈牙利", "社会主义",
     "《走向社会主义的五年计划》，匈牙利人民共和国第一个五年计划法律，1950"),
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
        return best
    return None


def _join(v):
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return str(v or "")


def known_ids():
    recs = json.load(open(CATALOG, encoding="utf-8"))
    return {r["url"].rsplit("/", 1)[-1].split("?")[0]
            for r in recs if "archive.org/details/" in r.get("url", "")}


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
        title = re.sub(r"<[^>]+>", " ", str(md.get("title") or "")).strip()
        title = re.sub(r"\s+", " ", title)
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

        items.append({
            "country": country, "stance": stance, "identifier": ident,
            "title": title, "year": year, "pages": min(pages, MAX_PAGES_DL),
            "creator": _join(md.get("creator"))[:100],
            "publisher": _join(md.get("publisher"))[:80],
            "url": f"https://archive.org/details/{ident}",
            "basis": basis, "pdf_name": pick_pdf(meta),
        })
        time.sleep(0.15)

    print(f"\n白名单可用 {len(items)} 本：")
    for c in items:
        print(f"  {c['country']:4s} {c['year']:4s} {c['pages']:3d}p "
              f"{c['identifier'][:32]:32s} {c['basis'][:40]}")

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
    print(f"\n=== 采到 {len(records)} 本 ===")


if __name__ == "__main__":
    main()
