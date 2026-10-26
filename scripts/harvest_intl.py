"""Wikimedia Commons 国际采集（按国家配额版）：每个地区约 15 件，力求多样化。"""

import json
import os
import re
import shutil
import ssl
import time
import urllib.parse
import urllib.request

UA = ("PamphletArchiveBot/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research@example.org)")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "images", "国际", "raw")
if os.path.isdir(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT, exist_ok=True)

QUOTA = 15   # 每国上限

REGIONS = {
    "德国": ["Wahlplakat", "Flugblatt Weimar", "KPD Plakat", "SPD Plakat", "NSDAP Plakat", "Wahlaufruf"],
    "法国": ["affiche électorale France", "tract politique France", "SFIO", "PCF affiche", "Front populaire"],
    "意大利": ["manifesto elettorale", "propaganda fascista", "PCI manifesto", "Democrazia Cristiana"],
    "西班牙": ["cartel guerra civil", "PSOE cartel", "CNT cartel", "Falange cartel"],
    "葡萄牙": ["cartaz eleitoral", "propaganda Estado Novo"],
    "英国": ["election leaflet UK", "Labour Party poster", "Conservative Party poster", "suffragette leaflet"],
    "美国": ["campaign poster USA", "campaign leaflet", "political broadside"],
    "俄国": ["листовка", "плакат", "Bolshevik poster", "RSDRP"],
    "波兰": ["plakat wyborczy", "plakat propagandowy"],
    "捷克": ["volební plakát", "propaganda plakát"],
    "荷兰": ["verkiezingsaffiche", "propagandaposter"],
    "瑞典": ["valaffisch", "propagandaffisch"],
    "奥地利": ["Wahlplakat Österreich", "Plakat Erste Republik"],
    "日本": ["選挙ポスター", "プロパガンダ ポスター"],
    "印度": ["Indian National Congress poster", "election leaflet India"],
    "拉美": ["cartel electoral", "panfleto político", "propaganda electoral México"],
}

YEAR_RE = re.compile(r"(1[89]\d{2}|19\d{2})")


def api(params, retries=4):
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


def download(url, path, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
            with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
                data = r.read()
            if len(data) < 5000:
                raise ValueError("small")
            open(path, "wb").write(data)
            return len(data)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(4 * (i + 1))


def safe_name(s):
    s = re.sub(r"[^\w\u4e00-\u9fff\u0400-\u04ff\u0600-\u06ff]+", "_", s)
    return s[:46].strip(" ._-") or "untitled"


records, seen, n = [], set(), 0

for region, terms in REGIONS.items():
    got = 0
    for term in terms:
        if got >= QUOTA:
            break
        try:
            d = api({"action": "query", "format": "json", "generator": "search",
                     "gsrsearch": term, "gsrnamespace": "6", "gsrlimit": "20",
                     "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
                     "iiurlwidth": "1400"})
        except Exception as e:
            print(f"  ERR {region}/{term}: {type(e).__name__}", flush=True)
            continue

        pages = (d.get("query") or {}).get("pages") or {}
        for pid, p in pages.items():
            if got >= QUOTA:
                break
            ii = (p.get("imageinfo") or [{}])[0]
            src = ii.get("thumburl") or ii.get("url")
            title = (p.get("title") or "").replace("File:", "")
            if not src or title in seen or not (ii.get("mime") or "").startswith("image"):
                continue
            meta = ii.get("extmetadata") or {}
            date_raw = re.sub(r"<[^>]+>", "", (meta.get("DateTimeOriginal") or {}).get("value") or "")
            desc = re.sub(r"<[^>]+>", "", (meta.get("ImageDescription") or {}).get("value") or "")[:300]
            ym = YEAR_RE.search(title) or YEAR_RE.search(date_raw) or YEAR_RE.search(desc)
            year = int(ym.group(1)) if ym else None
            if year is None or not (1840 <= year <= 1999):
                continue

            seen.add(title)
            n += 1
            got += 1
            fname = f"{n:04d}_{year}_{safe_name(title)}.jpg"
            rec = {"no": n, "region": region, "term": term, "title": title, "year": year,
                   "desc": desc[:160],
                   "credit": re.sub(r"<[^>]+>", "", (meta.get("Credit") or {}).get("value", ""))[:80],
                   "license": (meta.get("LicenseShortName") or {}).get("value", "")[:30],
                   "descurl": "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(title.replace(" ", "_")),
                   "src": src, "file": fname}
            try:
                rec["bytes"] = download(src, os.path.join(OUT, fname))
                rec["ok"] = True
            except Exception as e:
                rec["ok"] = False
                rec["error"] = type(e).__name__
            records.append(rec)
            time.sleep(1.0)
    print(f"[{region}] {got} 件，累计 {sum(1 for r in records if r.get('ok'))}", flush=True)

json.dump(records, open(os.path.join(OUT, "metadata.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

ok = [r for r in records if r.get("ok")]
from collections import Counter
print(f"\n=== 完成 {len(ok)}/{len(records)} ===")
for k, v in Counter(r["region"] for r in ok).most_common():
    print(f"   {k:6s} {v}")
