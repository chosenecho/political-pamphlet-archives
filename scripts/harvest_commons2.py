"""Wikimedia Commons 采集（修正版）：直接用 iiurlwidth 给出的缩略图，带退避重试。"""

import json
import os
import re
import shutil
import ssl
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "images", "commons")
if os.path.isdir(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT, exist_ok=True)

SEARCHES = [
    "voters pamphlet election",
    "political pamphlet",
    "election leaflet",
    "campaign leaflet",
    "party programme pamphlet",
    "socialist pamphlet",
    "communist pamphlet",
    "propaganda leaflet",
    "political poster 1900",
    "suffragette leaflet",
    "election poster",
    "political broadside",
    "wahlplakat",
    "affiche electorale",
]

YEAR_RE = re.compile(r"(1[89]\d{2}|19[0-4]\d)")


def api(params, retries=3):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
                return json.loads(r.read())
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))


def download(url, path, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
            with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
                data = r.read()
            if len(data) < 5000:
                raise ValueError(f"too small {len(data)}")
            open(path, "wb").write(data)
            return len(data)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries - 1:
                time.sleep(5 * (i + 1))
                continue
            raise
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))


records, seen, n = [], set(), 0

for term in SEARCHES:
    try:
        d = api({
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": term, "gsrnamespace": "6", "gsrlimit": "15",
            "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": "1400",
        })
    except Exception as e:
        print(f"ERR search {term}: {type(e).__name__}")
        continue

    pages = (d.get("query") or {}).get("pages") or {}
    picked = 0
    for pid, p in pages.items():
        if picked >= 6:
            break
        ii = (p.get("imageinfo") or [{}])[0]
        src = ii.get("thumburl") or ii.get("url")   # 直接用，不再改写
        title = (p.get("title") or "").replace("File:", "")
        if not src or title in seen:
            continue
        if not (ii.get("mime") or "").startswith("image"):
            continue

        meta = ii.get("extmetadata") or {}
        date_raw = re.sub(r"<[^>]+>", "", (meta.get("DateTimeOriginal") or {}).get("value") or "")
        ym = YEAR_RE.search(title) or YEAR_RE.search(date_raw)
        year = int(ym.group(1)) if ym else None
        if year is None or not (1800 <= year <= 1949):
            continue

        seen.add(title)
        picked += 1
        n += 1
        safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", title)[:55]
        fname = f"{n:03d}_{year}_{safe}.jpg"
        path = os.path.join(OUT, fname)
        rec = {
            "no": n, "search": term, "title": title, "year": year,
            "license": (meta.get("LicenseShortName") or {}).get("value", "")[:40],
            "credit": re.sub(r"<[^>]+>", "", (meta.get("Credit") or {}).get("value", ""))[:90],
            "descurl": "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(title.replace(" ", "_")),
            "src": src, "file": fname,
        }
        try:
            rec["bytes"] = download(src, path)
            rec["ok"] = True
            print(f"  OK  {n:03d} {year} {rec['bytes']/1024:6.0f}KB  {title[:44]}")
        except Exception as e:
            rec["ok"] = False
            rec["error"] = f"{type(e).__name__}: {str(e)[:50]}"
            print(f"  ERR {n:03d} {year} {rec['error'][:32]}  {title[:28]}")
        records.append(rec)
        time.sleep(1.3)   # 放慢，避免 429

json.dump(records, open(os.path.join(OUT, "metadata.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
ok = sum(1 for r in records if r.get("ok"))
print(f"\n=== Commons 完成 {ok}/{len(records)} ===")
