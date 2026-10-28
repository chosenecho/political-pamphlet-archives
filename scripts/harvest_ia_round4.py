"""Internet Archive 第四轮补采：换编目语种找此前检索不到的材料。

前三轮针对捷克/比利时/日本/葡萄牙/瑞典用的是「母语种 + 政党名」，
IA 上这些国别的材料多为他国图书馆以西文编目，母语种检索大量漏掉。
本轮改用英文/法文/德文的国别名与政党名，命中质量明显提高。

仍是逐条核验后的显式白名单，每条附核验依据。

明确排除的：
  · dekomendestembus00treu —— 荷兰自由派学者的选举论著，非政党出版物
  · czechoslovakstat00pergrich —— 侨居美国的捷克斯洛伐克艺术俱乐部出版，属文化宣传
  · czechoslovakiasg00unse / whereisczechoslo00repr —— 1940 年伦敦、1968 年地拉那
    的第三方政治评论，非政党自身材料
  · administrativere00japa —— 日本驻朝鲜统监府行政改革文件，殖民官方文书
  · historicalcauses00trevuoft —— 牛津讲座讲稿，学术演讲
  · ItalyToday —— 反法西斯团体编印，立场属评论而非政党宣传
  · hungaryroumania00jancrich —— 民族问题论著，非政党纲领

用法：
    python scripts/harvest_ia_round4.py --dry
    python scripts/harvest_ia_round4.py
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
ROOT = os.path.join(BASE, "images", "ia-round4")
RAW = os.path.join(ROOT, "raw")
CATALOG = os.path.join(BASE, "data", "catalog.json")

MAX_PAGES_DL = 80
PDF_MAX_MB = 25

#: (identifier, 国别, 立场, 核验依据)
KEEP = [
    # --- 捷克 ---
    ("actionprogrammeo08komu", "捷克", "共产主义",
     "捷克斯洛伐克共产党 1968 年四月行动纲领（布拉格之春），英译本 1970"),
    ("voiceofoppressed00masa", "捷克", "民族主义",
     "马萨里克《受压迫民族之声》，波希米亚民族同盟（芝加哥）1917"),
    ("bohemiaabriefev00benegoog", "捷克", "民族主义",
     "《波希米亚：其对文明的贡献简述》，波希米亚民族同盟 1917"),
    ("budoucechy00masa", "捷克", "民族主义",
     "马萨里克《捷克的未来》，1919"),

    # --- 比利时 ---
    ("sc_197405444_00000001704775", "比利时", "社会主义",
     "比利时工人党第三十二次年会正式记录（安特卫普人民宫，1921年3月26–28日）"),
    ("germanattemptsto00beckrich", "比利时", "反德宣传",
     "贝克尔《德国分裂比利时的企图》，1918 协约国宣传"),

    # --- 日本 ---
    ("bwb_W7-CXD-777", "日本", "共产主义",
     "内珀《日本共产党概观》，《日本时报》社出版，1913"),

    # --- 奥地利 ---
    ("revolutionaryess00kunb", "奥地利", "社会主义",
     "贝拉·库恩《革命文集》，英国社会党出版，1919"),

    # --- 意大利 ---
    ("wfl_b2f24", "意大利", "法西斯主义",
     "墨索里尼《法西斯主义学说》，法西斯青年团印行，1932"),

    # --- 西班牙 ---
    ("2916970.0001.001.umich.edu", "西班牙", "无政府主义",
     "安古洛《费雷尔的「审判」》，纽约劳工新闻社 1911，为西班牙无政府主义者辩护"),
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
              f"{c['identifier'][:30]:30s} {c['basis'][:40]}")

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
