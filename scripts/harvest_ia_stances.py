"""Internet Archive 按语种 × 政治立场采集（德/意/西/法/俄）。"""

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
ROOT = os.path.join(BASE, "images", "ia-stance")
RAW = os.path.join(ROOT, "raw")
os.makedirs(RAW, exist_ok=True)

MINP, MAXP = 10, 64
PDF_MAX_MB = 18
PER_QUERY = 3

QUERIES = [
    ("德国", "ger", "Nationalsozialismus OR Faschismus"),
    ("德国", "ger", "Sozialdemokratie OR Kommunismus"),
    ("德国", "ger", "Zentrum OR Katholizismus"),
    ("意大利", "ita", "fascismo"),
    ("意大利", "ita", "socialismo OR comunismo"),
    ("意大利", "ita", "cattolicesimo OR popolare"),
    ("西班牙", "spa", "falange OR anarquismo"),
    ("西班牙", "spa", "socialismo OR comunismo"),
    ("西班牙", "spa", "carlismo OR monarquia"),
    ("法国", "fre", "socialisme OR communisme"),
    ("法国", "fre", "royalisme OR nationalisme"),
    ("俄国", "rus", "revolution"),
    ("俄国", "rus", "bolshevik OR menshevik"),
    ("荷兰", "dut", "socialisme OR katholiek"),
    ("波兰", "pol", "socjalizm OR narodowy"),
]

BAD = re.compile(
    r"(novel|poems|sermon|hymn|cookery|recipe|dictionary|encyclopedia|almanac|yearbook|"
    r"catalog|directory|journal|magazine|argus|herald|tribune|gazette|newspaper|"
    r"courier|sentinel|bulletin|statutes|code of|compiled laws|session laws|"
    r"report of the|proceedings of|minutes of|annual report|kalender|adressbuch|"
    r"romans?|gedichte|romanzo|poesie|romance)", re.I)


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


def search(q, rows=30):
    params = {"q": q, "fl[]": ["identifier", "title", "year", "subject", "imagecount"],
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


records, seen, titles = [], set(), set()

for country, code, subj in QUERIES:
    q = (f'language:({code}) AND subject:({subj}) AND '
         f'imagecount:[{MINP} TO {MAXP}] AND year:[1880 TO 1948] AND mediatype:texts')
    try:
        d = search(q)
    except Exception as e:
        print(f"ERR {country}/{subj}: {type(e).__name__}", flush=True)
        continue

    got = 0
    for doc in (d.get("response") or {}).get("docs", []):
        if got >= PER_QUERY:
            break
        ident = doc.get("identifier")
        title = re.sub(r"<[^>]+>", "", str(doc.get("title") or ""))
        if not ident or ident in seen or BAD.search(title):
            continue
        tk = re.sub(r"[^a-z0-9]+", "", title.lower())[:30]
        if tk in titles:
            continue
        try:
            ic = int(doc.get("imagecount") or 0)
        except Exception:
            ic = 0
        if not (MINP <= ic <= MAXP):
            continue
        year = str(doc.get("year") or "")[:4]
        if not year.isdigit() or not (1800 <= int(year) <= 1999):
            continue

        try:
            meta = get_json(f"https://archive.org/metadata/{ident}")
        except Exception:
            continue
        pdf_name, pdf_size = None, 0
        for f in meta.get("files", []):
            if f.get("name", "").endswith(".pdf"):
                sz = int(f.get("size") or 0)
                if pdf_name is None or sz < pdf_size:
                    pdf_name, pdf_size = f["name"], sz

        seen.add(ident)
        titles.add(tk)
        n = len(records) + 1
        got += 1
        folder = os.path.join(RAW, f"{n:03d}")
        os.makedirs(os.path.join(folder, "pages"), exist_ok=True)
        rec = {"no": n, "country": country, "stance": subj, "title": title,
               "year": year, "pages": ic, "identifier": ident,
               "url": f"https://archive.org/details/{ident}"}
        if pdf_name and pdf_size <= PDF_MAX_MB * 1048576:
            try:
                fetch(f"https://archive.org/download/{ident}/{urllib.parse.quote(pdf_name)}",
                      os.path.join(folder, "doc.pdf"))
                rec["pdf"] = True
            except Exception:
                rec["pdf"] = False
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
            time.sleep(0.08)
        rec["pages_got"] = ok
        records.append(rec)
        print(f"  {country} {n:02d} {year} {ic:2d}p 图{ok:2d}  {title[:44]}", flush=True)
        time.sleep(0.4)

json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
from collections import Counter
print(f"\n=== 共 {len(records)} 本 ===", flush=True)
for k, v in Counter(r["country"] for r in records).most_common():
    print(f"   {k:5s} {v}", flush=True)
