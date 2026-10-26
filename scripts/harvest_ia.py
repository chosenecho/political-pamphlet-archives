"""Internet Archive 采集：只收 12–64 页的政治小册子，下载整本 PDF + 页图。"""

import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request

UA = "PamphletArchiveBot/1.0 (https://github.com/chosenecho/political-pamphlet-archives; research@example.org)"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "images", "ia")
RAW = os.path.join(ROOT, "raw")
os.makedirs(RAW, exist_ok=True)

MINP, MAXP = 8, 64
PDF_MAX_MB = 18
TARGET = 18

QUERIES = [
    ('subject:("campaign literature") AND imagecount:[12 TO 64] AND year:[1840 TO 1900]', "美国"),
    ('subject:("campaign literature") AND imagecount:[12 TO 64] AND year:[1900 TO 1960]', "美国"),
    ('subject:("Fabian tract") AND imagecount:[12 TO 64]', "英国"),
    ('subject:("socialism") AND imagecount:[12 TO 64] AND year:[1880 TO 1930]', "英国"),
    ('title:("wahlprogramm" OR "parteiprogramm" OR "wahlaufruf") AND imagecount:[8 TO 64]', "德国"),
    ('title:(manifeste OR "programme electoral" OR "profession de foi") AND imagecount:[8 TO 64]', "法国"),
]

BAD = re.compile(
    r"(novel|poems|sermon|hymn|cookery|recipe|dictionary|encyclopedia|almanac|yearbook|"
    r"catalog|directory|journal|magazine|argus|herald|tribune|gazette|newspaper|"
    r"courier|sentinel|bulletin|election law|statutes|code of|compiled laws|"
    r"session laws|report of the|proceedings of|minutes of|annual report)", re.I)


def get_json(url, timeout=60, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return json.loads(r.read())
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


def search(q, rows=40):
    params = {"q": q, "fl[]": ["identifier", "title", "date", "year", "subject", "imagecount"],
              "rows": str(rows), "output": "json", "sort[]": "downloads desc"}
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return get_json(url)


def fetch(url, path, timeout=180, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                data = r.read()
            if len(data) < 4000:
                raise ValueError("small")
            open(path, "wb").write(data)
            return len(data)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))


records, seen, seen_titles = [], set(), set()
n = 0
for q, region in QUERIES:
    if len(records) >= TARGET:
        break
    try:
        d = search(q)
    except Exception as e:
        print(f"ERR search {q[:40]}: {type(e).__name__}", flush=True)
        continue

    for doc in (d.get("response") or {}).get("docs", []):
        if len(records) >= TARGET:
            break
        ident = doc.get("identifier")
        title = re.sub(r"<[^>]+>", "", str(doc.get("title") or ""))
        if not ident or ident in seen:
            continue
        if BAD.search(title):
            continue
        tkey = re.sub(r"[^a-z0-9]+", "", title.lower())[:32]
        if tkey in seen_titles:
            continue
        try:
            ic = int(doc.get("imagecount") or 0)
        except Exception:
            ic = 0
        if not (MINP <= ic <= MAXP):
            continue
        year = str(doc.get("year") or doc.get("date") or "")[:4]
        if not year.isdigit() or not (1800 <= int(year) <= 1999):
            continue

        try:
            meta = get_json(f"https://archive.org/metadata/{ident}")
        except Exception:
            continue
        pdf_name, pdf_size = None, 0
        for f in meta.get("files", []):
            nm = f.get("name", "")
            if nm.endswith(".pdf"):
                sz = int(f.get("size") or 0)
                if pdf_name is None or sz < pdf_size:
                    pdf_name, pdf_size = nm, sz
        have_pdf = bool(pdf_name) and pdf_size <= PDF_MAX_MB * 1048576

        seen.add(ident)
        seen_titles.add(tkey)
        n += 1
        folder = os.path.join(RAW, f"{n:03d}")
        os.makedirs(os.path.join(folder, "pages"), exist_ok=True)
        rec = {"no": n, "region": region, "title": title, "year": year,
               "pages": ic, "identifier": ident,
               "url": f"https://archive.org/details/{ident}",
               "subject": str(doc.get("subject"))[:100]}
        if have_pdf:
            try:
                fetch(f"https://archive.org/download/{ident}/{urllib.parse.quote(pdf_name)}",
                      os.path.join(folder, "doc.pdf"))
                rec["pdf"] = True
            except Exception as e:
                rec["pdf"] = False
                rec["error"] = type(e).__name__
        else:
            rec["pdf"] = False

        ok = 0
        for p in range(ic):
            fp = os.path.join(folder, "pages", f"p-{p+1:05d}.jpg")
            try:
                fetch(f"https://archive.org/download/{ident}/page/n{p}_w1000.jpg", fp, timeout=90)
                ok += 1
            except Exception:
                pass
            time.sleep(0.1)
        rec["pages_got"] = ok
        records.append(rec)
        print(f"  {n:02d} {region} {year} {ic:2d}p {pdf_size/1048576:4.1f}MB 图{ok:2d}  {title[:44]}", flush=True)
        time.sleep(0.6)

json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"\n=== 共 {len(records)} 本 ===")
