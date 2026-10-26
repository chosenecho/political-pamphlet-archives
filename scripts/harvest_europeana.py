"""Europeana 采集：按国家检索政治小册子 PDF，下载后本地渲染成页图。"""

import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request

import fitz  # PyMuPDF

UA = ("PamphletArchiveBot/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research@example.org)")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "images", "europeana")
RAW = os.path.join(ROOT, "raw")
os.makedirs(RAW, exist_ok=True)

MINP, MAXP = 5, 64
PDF_MAX_MB = 20
QUOTA = 4
RENDER_W = 1000

# (Europeana 国别代码, 中文名, 检索词)
GROUPS = [
    ("Ireland", "爱尔兰", "pamphlet"),
    ("Poland", "波兰", "pamflet"),
    ("Poland", "波兰", "ulotka wybory"),
    ("Netherlands", "荷兰", "pamflet verkiezingen"),
    ("Germany", "德国", "Flugschrift"),
    ("Germany", "德国", "Wahlkampf"),
    ("France", "法国", "brochure élections"),
    ("Italy", "意大利", "opuscolo"),
    ("Spain", "西班牙", "folleto elecciones"),
    ("Portugal", "葡萄牙", "folheto"),
    ("Czechia", "捷克", "brožura"),
    ("Hungary", "匈牙利", "röpirat"),
    ("Sweden", "瑞典", "pamflett"),
    ("Denmark", "丹麦", "pamflet valg"),
    ("Austria", "奥地利", "Flugschrift"),
    ("Belgium", "比利时", "pamflet"),
]

BAD = re.compile(r"(novel|poems|sermon|hymn|cookery|recipe|dictionary|almanac|"
                 r"catalog|directory|journal|magazine|newspaper|gazette|atlas|map)",
                 re.I)


def eur(query, country, rows=30):
    params = {
        "query": query, "rows": str(rows), "wskey": "api2demo",
        "profile": "rich", "reusability": "open", "media": "true",
        "qf": f'COUNTRY:"{country}" AND TYPE:"TEXT"',
    }
    url = "https://api.europeana.eu/record/v2/search.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read())


def download(url, path, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        data = r.read()
    if len(data) < 8000:
        raise ValueError("too small")
    open(path, "wb").write(data)
    return len(data)


def render(pdf_path, out_dir, width=RENDER_W):
    doc = fitz.open(pdf_path)
    n = doc.page_count
    made = 0
    for i in range(n):
        page = doc.load_page(i)
        zoom = width / page.rect.width if page.rect.width else 1
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        pix.save(os.path.join(out_dir, f"p-{i+1:05d}.jpg"))
        made += 1
    doc.close()
    return n, made


records, seen = [], set()
n = 0
for country, cn, query in GROUPS:
    try:
        d = eur(query, country)
    except Exception as e:
        print(f"ERR {cn}: {type(e).__name__}", flush=True)
        continue

    got = 0
    for it in d.get("items", []):
        if got >= QUOTA:
            break
        title = (it.get("title") or [""])[0]
        if not title or BAD.search(title):
            continue
        link = (it.get("edmIsShownBy") or [""])[0]
        if not link.lower().split("?")[0].endswith(".pdf"):
            continue
        key = link.split("?")[0]
        if key in seen:
            continue

        n += 1
        folder = os.path.join(RAW, f"{n:03d}")
        pdir = os.path.join(folder, "pages")
        os.makedirs(pdir, exist_ok=True)
        pdf_path = os.path.join(folder, "doc.pdf")

        try:
            size = download(link, pdf_path)
            if size > PDF_MAX_MB * 1048576:
                raise ValueError("too big")
            doc = fitz.open(pdf_path)
            pages = doc.page_count
            doc.close()
            if not (MINP <= pages <= MAXP):
                raise ValueError(f"{pages}p out of range")
        except Exception as e:
            print(f"  skip {type(e).__name__}:{str(e)[:28]}  {title[:40]}", flush=True)
            os.remove(pdf_path) if os.path.exists(pdf_path) else None
            for f in os.listdir(pdir):
                os.remove(os.path.join(pdir, f))
            os.rmdir(pdir)
            os.rmdir(folder)
            n -= 1
            continue

        seen.add(key)
        got += 1
        total, made = render(pdf_path, pdir)
        year_m = re.search(r"(1[89]\d{2}|19\d{2})", str(it.get("year") or "") + " " + title)
        rec = {"no": n, "country": cn, "title": title,
               "year": year_m.group(1) if year_m else "",
               "pages": total, "pdf": True,
               "provider": (it.get("dataProvider") or [""])[0],
               "rights": (it.get("rights") or [""])[0],
               "url": (it.get("guid") or (it.get("edmIsShownAt") or [""])[0]),
               "file_url": link}
        records.append(rec)
        print(f"  {cn} {n:02d} {rec['year']} {total:2d}p  {title[:44]}", flush=True)
        time.sleep(0.6)

json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
from collections import Counter
print(f"\n=== 共 {len(records)} 本 ===")
for k, v in Counter(r["country"] for r in records).most_common():
    print(f"   {k:5s} {v}")
