"""Internet Archive 深度补采（终选版）：按人工核验结果逐条收录。

前两版脚本靠正则过滤，但印度那批「address / leaflet / speech」里
宗教小册、美国地方演说、殖民史论文占了大半，逐条读 metadata 才能分清。
因此本版改为**显式白名单**：每一条都是我逐条看过 publisher 与 subject
之后判定确属政党/政治组织宣传品的，才收。宁可少收，不收错的。

收录判据（逐条核验）：
  印度 — Navajivan Trust（甘地著作的国大党系出版社）、
          All India Congress Committee、Indian National Congress、
          Cawnpore Socialist Bookshop（印度共产党）
  拉美 — 政党自身的宣言与政纲：智利自由党、乌拉圭总统竞选纲领
  意大利— 天主教行动会、教皇通谕（教会政治干预的原始文献）

明确排除的（核验后判定非政党宣传品）：
  - 美国 Wyoming 历史学会的独立战争纪念碑演说、美国印第安人事务
  - 印度宗教小册（Coomaraswamy、Chamberlain 传教报告、教育会议）
  - 英国下议院鸦片贸易演说、美国参议院关于印度的演说
  - 秘鲁卫生政策、古巴地缘争议演说、乌拉圭剧院节目单
  - 俄国 B-001-* 与 materialy_*：metadata 只剩 SINGLE_PAGE_JPG 或为空，
    无从核验页码与内容，不收

用法：
    python scripts/harvest_ia_deep.py --dry    # 只列白名单
    python scripts/harvest_ia_deep.py          # 下载到 images/ia-deep/
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
ROOT = os.path.join(BASE, "images", "ia-deep")
RAW = os.path.join(ROOT, "raw")
CATALOG = os.path.join(BASE, "data", "catalog.json")

PDF_MAX_MB = 20
MAX_PAGES_DL = 64

#: 逐条核验后的收录清单：(identifier, 国别, 立场, 核验依据)
KEEP = [
    # --- 印度：甘地小册（Navajivan Trust，甘地本人著作的出版机构） ---
    ("mkbook0300mkga", "印度", "民族主义", "Navajivan Trust 出版，甘地著《面包劳动》"),
    ("mkgpamphlet0400mkga", "印度", "民族主义", "Navajivan Trust，甘地著《种姓法》"),
    ("mkgpamphlet0300mkga", "印度", "民族主义", "Navajivan Trust，甘地著《素食的道德基础》"),
    ("mkbook1700mkga", "印度", "民族主义", "Navajivan Trust，甘地著《托管论》"),
    ("mkbook1600mkga", "印度", "民族主义", "甘地著《建设纲领及其意义与地位》"),
    ("mkbook2200mkga", "印度", "民族主义", "Gandhi Smarak Nidhi（甘地纪念基金）出版"),

    # --- 印度：国大党机关文献 ---
    ("villageindustrie00bhar", "印度", "民族主义", "All India Congress Committee 出版"),
    ("agrarianproblemi00ahma", "印度", "民族主义",
     "All India Congress Committee 政治经济情报部出版，尼赫鲁参与"),
    ("chairmansspeech400gidw", "印度", "民族主义", "印度国大党第45届年会（卡拉奇）主席演说"),
    ("memorandumtomemb00indiuoft", "印度", "民族主义", "国大党重组委员会备忘录"),

    # --- 印度：共产党 ---
    ("translationoflea00cawn", "印度", "共产主义",
     "Cawnpore Socialist Bookshop 出版，印共《Bharatiya Samyavadi Dal》传单英译"),

    # --- 印度：国大党领袖演说集 ---
    ("futureofindiapre00sinhiala", "印度", "民族主义",
     "S.P. Sinha 在印度国大党的主席演说（1916）"),

    # --- 拉美：政党宣言与竞选纲领 ---
    ("manifestodelpart00part", "拉美", "自由主义",
     "智利自由党《告同仁宣言》（1896）"),
    ("ElFuturoPresidente_Bastitta_1919", "拉美", "选举宣传",
     "乌拉圭总统候选人 Bastitta 的施政纲领（1919）"),

    # --- 意大利：天主教政治 ---
    ("programmastatuto00azio", "意大利", "天主教民众派",
     "天主教行动会章程与规约（1871）"),
    ("VentanniUnioneuomini? 1248955", "意大利", "天主教民众派",
     "天主教行动会男信徒联合会二十年（1942）"),
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
            if len(data) < 4000:
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
    for raw_ident, country, stance, basis in KEEP:
        ident = raw_ident.split()[-1]
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
            print(f"  跳过 {ident}: 无标题（metadata 不可用）")
            continue
        # 页数以 metadata 的 imagecount 为准；已下载的 PDF 页数可作交叉校验。
        # 不能用 files 里 .jpg 的数量——IA 的逐页图不在 files 列表中，
        # 那里只有一张缩略图。
        try:
            pages = int(md.get("imagecount") or 0)
        except (TypeError, ValueError):
            pages = 0
        if pages < 8:
            # 退回用 PDF 页数
            if pdf_name:
                try:
                    pp = os.path.join(ROOT, "_probe.pdf")
                    os.makedirs(ROOT, exist_ok=True)
                    fetch_file(
                        f"https://archive.org/download/{ident}/{urllib.parse.quote(pdf_name)}",
                        pp, timeout=180)
                    import fitz
                    doc = fitz.open(pp)
                    pages = doc.page_count
                    doc.close()
                    os.remove(pp)
                except Exception:
                    pages = 0
        if pages < 8:
            print(f"  跳过 {ident}: 页数 {pages} < 8")
            continue
        year = str(md.get("date") or md.get("year") or "")[:4]
        if not year.isdigit():
            m = re.search(r"(1[89]\d{2}|19\d{2})", str(md.get("date") or ""))
            year = m.group(1) if m else ""

        pdf_name, pdf_size = pick_pdf(meta)
        items.append({
            "country": country, "stance": stance, "identifier": ident,
            "title": title, "year": year, "pages": min(pages, MAX_PAGES_DL),
            "creator": _join(md.get("creator"))[:100],
            "publisher": _join(md.get("publisher"))[:80],
            "url": f"https://archive.org/details/{ident}",
            "basis": basis, "pdf_name": pdf_name, "pdf_size": pdf_size,
        })
        time.sleep(0.15)

    print(f"\n白名单可用 {len(items)} 本：")
    for c in items:
        print(f"  {c['country']:4s} {c['year']:4s} {c['pages']:3d}p "
              f"{c['identifier'][:28]:28s} {c['basis'][:40]}")

    if dry:
        return

    os.makedirs(RAW, exist_ok=True)
    records = []
    for c in items:
        n = len(records) + 1
        folder = os.path.join(RAW, f"{n:03d}")
        os.makedirs(os.path.join(folder, "pages"), exist_ok=True)

        rec = {k: v for k, v in c.items() if k not in ("pdf_name", "pdf_size")}
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
            time.sleep(0.05)
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
