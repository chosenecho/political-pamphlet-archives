"""经本机代理采集 Internet Archive（16 线程并发）。

背景：直连 archive.org 长期不可达，而本机 127.0.0.1:10808 是可用的 HTTP/SOCKS
代理。实测经代理：metadata 可读、页图可取，单项延迟约 7–9 秒。

并发度实测（24 张页图）：
    4 线程   17/24  0.40 张/秒
    8 线程   19/24  1.16 张/秒
   16 线程   22/24  1.91 张/秒   ← 最优
   24 线程   10/24  0.88 张/秒   ← 触发限流，成功率骤降
故固定 16 线程。失败单张重试一次，仍失败则跳过，不拖住整本。

目标：葡萄牙、瑞典——全库仅剩这两个国别没有小册子。

用法：
    python scripts/harvest_ia_proxy.py --probe        # 只搜候选
    python scripts/harvest_ia_proxy.py --dry          # 列白名单
    python scripts/harvest_ia_proxy.py                # 下载
"""

import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "images", "ia-proxy")
RAW = os.path.join(ROOT, "raw")
CATALOG = os.path.join(BASE, "data", "catalog.json")

PROXY = "http://127.0.0.1:10808"
UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only)")
WORKERS = 16
MAX_PAGES = 80
PDF_MAX_MB = 25

#: 检索式：(国别, 立场, 查询)。葡萄牙与瑞典的政党材料。
#: 前几轮已试过母语种与西文编目两类；本轮经代理重试，并补充
#: 「政党名 + 年份」与「宣传册体裁词」的组合。
QUERIES = [
    # 葡萄牙
    ("葡萄牙", "共和派", 'language:por AND subject:(republica OR republicano) '
                         'AND year:[1890 TO 1933]'),
    ("葡萄牙", "共和派", 'title:(propaganda OR programa OR manifesto) AND language:por'),
    ("葡萄牙", "社会主义", 'subject:("Partido Republicano Português" OR "Partido Socialista Português")'),
    ("葡萄牙", "共和派", 'subject:(Portugal AND (republica OR monarquia)) AND mediatype:texts'),
    ("葡萄牙", "社会主义", 'title:(operario OR operária OR sindical) AND language:por'),
    # 瑞典
    ("瑞典", "社会民主党", 'language:swe AND subject:(socialdemokrati OR arbetarrörelse)'),
    ("瑞典", "社会民主党", 'title:(valprogram OR partiprogram OR arbetareprogram)'),
    ("瑞典", "社会主义", 'creator:("Sveriges socialdemokratiska arbetareparti")'),
    ("瑞典", "社会民主党", 'subject:(Sweden AND "social democratic") AND language:eng'),
    ("瑞典", "社会主义", 'title:(Sweden AND (labour OR labor)) AND language:eng '
                         'AND year:[1890 TO 1940]'),
]

#: 不合体裁
BAD = re.compile(
    r"(novel|poems?|sermon|hymn|cookery|dictionary|encyclop|almanac|yearbook|"
    r"kalender|adressbuch|directory|\bjournal\b|magazine|\breview\b|quarterly|"
    r"annals|proceedings|argus|herald|tribune|gazette|newspaper|zeitung|courier|"
    r"\bbulletin|statutes|compiled laws|report of the|minutes of|annual report|"
    r"jahresbericht|berättelse|katalog|catalogue|bibliograph|"
    r"midsummer|festival|program\s+for|sångbok|visbok|kokbok)", re.I)


def opener():
    op = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    op.addheaders = [("User-Agent", UA)]
    return op


def fetch(op, url, timeout=90):
    with op.open(url, timeout=timeout) as r:
        return r.read()


def fetch_json(op, url, timeout=60):
    return json.loads(fetch(op, url, timeout=timeout))


def search(op, q, rows=30):
    params = {"q": q, "fl[]": ["identifier", "title", "year", "language", "imagecount"],
              "rows": str(rows), "output": "json", "sort[]": "downloads desc"}
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return fetch_json(op, url)


def _join(v):
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return str(v or "")


def pick_pdf(meta):
    best, size = None, 0
    for f in meta.get("files", []):
        if not str(f.get("name", "")).endswith(".pdf"):
            continue
        try:
            sz = int(f.get("size") or 0)
        except (TypeError, ValueError):
            sz = 0
        if best is None or (sz and sz < size):
            best, size = f["name"], sz
    if best and size <= PDF_MAX_MB * 1048576:
        return best
    return None


def probe():
    op = opener()
    for country, stance, q in QUERIES:
        full = f'{q} AND imagecount:[8 TO {MAX_PAGES}] AND year:[1860 TO 1955] AND mediatype:texts'
        try:
            d = search(op, full)
        except Exception as e:
            print(f"\n[{country}] 检索失败 {type(e).__name__}: {str(e)[:60]}")
            continue
        resp = d.get("response") or {}
        docs = resp.get("docs", [])
        print(f"\n[{country}] numFound={resp.get('numFound')}")
        for doc in docs[:6]:
            print(f"   {str(doc.get('year')):6s} {str(doc.get('imagecount')):>3}p "
                  f"{str(doc.get('language'))[:8]:8s} {str(doc.get('identifier'))[:32]:32s} "
                  f"{str(doc.get('title'))[:44]}")
        time.sleep(2)
    return 0


def main():
    if "--probe" in sys.argv:
        return probe()

    dry = "--dry" in sys.argv
    op = opener()

    known = {r["url"].rsplit("/", 1)[-1].split("?")[0]
             for r in json.load(open(CATALOG, encoding="utf-8"))
             if "archive.org/details/" in r.get("url", "")}

    cands, seen = [], set()
    for country, stance, q in QUERIES:
        full = f'{q} AND imagecount:[8 TO {MAX_PAGES}] AND year:[1860 TO 1955] AND mediatype:texts'
        try:
            d = search(op, full)
        except Exception as e:
            print(f"[{country}] 检索失败 {type(e).__name__}")
            continue
        for doc in (d.get("response") or {}).get("docs", []):
            ident = str(doc.get("identifier") or "")
            title = re.sub(r"<[^>]+>", " ", str(doc.get("title") or "")).strip()
            if not ident or ident in known or ident in seen:
                continue
            if not title or BAD.search(title):
                continue
            try:
                ic = int(doc.get("imagecount") or 0)
            except (TypeError, ValueError):
                continue
            if not (8 <= ic <= MAX_PAGES):
                continue
            y = str(doc.get("year") or "")[:4]
            if not y.isdigit() or not (1860 <= int(y) <= 1955):
                continue
            seen.add(ident)
            cands.append({"country": country, "stance": stance, "identifier": ident,
                          "title": title, "year": y, "pages": ic})
        time.sleep(2)

    print(f"\n候选 {len(cands)} 本：")
    for c in cands:
        print(f"  {c['country']:4s} {c['year']} {c['pages']:>3}p "
              f"{c['identifier'][:34]:34s} {c['title'][:48]}")
    if dry:
        return 0

    os.makedirs(RAW, exist_ok=True)
    records = []
    from collections import Counter
    taken = Counter()

    for c in cands:
        if taken[c["country"]] >= 8:
            continue
        try:
            meta = fetch_json(op, f"https://archive.org/metadata/{c['identifier']}")
        except Exception as e:
            print(f"  跳过 {c['identifier'][:30]}: metadata {type(e).__name__}")
            continue
        md = meta.get("metadata", {}) or {}
        c["creator"] = _join(md.get("creator"))[:100]
        c["publisher"] = _join(md.get("publisher"))[:80]
        c["url"] = f"https://archive.org/details/{c['identifier']}"
        pdf_name = pick_pdf(meta)

        n = len(records) + 1
        folder = os.path.join(RAW, f"{n:03d}")
        os.makedirs(os.path.join(folder, "pages"), exist_ok=True)

        rec = dict(c)
        rec["no"] = n
        rec["pdf"] = False
        if pdf_name:
            try:
                data = fetch(op, f"https://archive.org/download/{c['identifier']}/"
                                 f"{urllib.parse.quote(pdf_name)}", timeout=300)
                with open(os.path.join(folder, "doc.pdf"), "wb") as f:
                    f.write(data)
                rec["pdf"] = True
            except Exception:
                pass

        def one(p):
            url = f"https://archive.org/download/{c['identifier']}/page/n{p}_w1000.jpg"
            for attempt in range(2):
                try:
                    with op.open(url, timeout=90) as r:
                        data = r.read()
                    if len(data) > 2000:
                        with open(os.path.join(folder, "pages", f"p-{p+1:05d}.jpg"), "wb") as f:
                            f.write(data)
                        return True
                except Exception:
                    time.sleep(1 + attempt)
            return False

        t0 = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            res = list(ex.map(one, range(min(c["pages"], MAX_PAGES))))
        ok = sum(1 for r in res if r)
        rec["pages_got"] = ok
        el = time.time() - t0

        if ok < 8:
            import shutil
            print(f"  丢弃 {c['identifier'][:30]}: 只取到 {ok} 页")
            shutil.rmtree(folder, ignore_errors=True)
            continue

        taken[c["country"]] += 1
        records.append(rec)
        print(f"  {c['country']:4s} {c['year']} 图{ok:>3d}/{c['pages']:<3d} "
              f"pdf{'✓' if rec['pdf'] else '×'} {el:5.1f}s  {c['title'][:36]}", flush=True)

    json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n=== 采到 {len(records)} 本 ===")
    for k, v in Counter(r["country"] for r in records).most_common():
        print(f"   {k:5s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
