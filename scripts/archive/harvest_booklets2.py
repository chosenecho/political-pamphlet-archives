"""定向补抓：只认明确的政党小册子系列，标题白名单 + 黑名单双重过滤。"""

import json
import os
import re
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
ROOT = os.path.join(BASE, "images", "小册子国际")
RAW = os.path.join(ROOT, "raw")
os.makedirs(RAW, exist_ok=True)

ALLOW = re.compile(
    r"(voters'? pamphlet|fabian tract|campaign literature|election platform|"
    r"parteiprogramm|wahlprogramm|wahlaufruf|party programme|programme du parti|"
    r"partiprogram|valprogram|political pamphlet|election address|address to the people|"
    r"manifesto of the|programa electoral|programma elettorale|program wyborczy|"
    r"volební program|profession de foi|政綱|選挙公報)", re.I)

DENY = re.compile(
    r"(science|faith|confession|catéch|catholique|koor|orkest|concert|wikipédia|"
    r"journal|giornale|gazette|novel|poems|sermon|hymn|recipe|cook|hotel|"
    r"tourism|travel|annual report|directory|calendar)", re.I)

# (检索词, 地区)
QUERIES = [
    ("voters' pamphlet", "美国"),
    ("campaign literature", "美国"),
    ("election platform", "美国"),
    ("fabian tract", "英国"),
    ("election address", "英国"),
    ("address to the people", "美国"),
    ("parteiprogramm", "德国"),
    ("wahlprogramm", "德国"),
    ("wahlaufruf", "德国"),
    ("party programme", "英国"),
    ("programme du parti", "法国"),
    ("profession de foi", "法国"),
    ("programma elettorale", "意大利"),
    ("programa electoral", "西班牙"),
    ("program wyborczy", "波兰"),
    ("volební program", "捷克"),
    ("partiprogram", "北欧"),
    ("valprogram", "北欧"),
]

MINP, MAXP = 8, 64
MAX_MB = 25
QUOTA = 4
start = len([d for d in os.listdir(RAW) if d.isdigit()])
records, seen, n = [], set(), start


def api(params, retries=3):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
                return json.loads(r.read())
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))


def fetch(url, path, retries=3, timeout=180):
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
            time.sleep(4 * (i + 1))


def safe(s, c=44):
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", re.sub(r"<[^>]+>", "", str(s)))
    return s[:c].strip(" ._-") or "untitled"


per_region = {}
for q, region in QUERIES:
    if per_region.get(region, 0) >= QUOTA:
        continue
    try:
        d = api({"action": "query", "format": "json", "list": "search",
                 "srsearch": q + " filemime:application/pdf",
                 "srnamespace": "6", "srlimit": "25"})
    except Exception as e:
        print(f"ERR {q}: {type(e).__name__}", flush=True)
        continue

    for h in (d.get("query") or {}).get("search") or []:
        if per_region.get(region, 0) >= QUOTA:
            break
        title = h["title"]
        name = title.replace("File:", "")
        if title in seen or not ALLOW.search(name) or DENY.search(name):
            continue
        try:
            info = api({"action": "query", "format": "json", "titles": title,
                        "prop": "imageinfo", "iiprop": "url|size|mime",
                        "iiurlwidth": "500"})
        except Exception:
            continue
        page = list((info.get("query") or {}).get("pages", {}).values())[0]
        ii = (page.get("imageinfo") or [{}])[0]
        pc, size = ii.get("pagecount") or 0, ii.get("size") or 0
        if not (MINP <= pc <= MAXP) or size > MAX_MB * 1048576:
            continue

        seen.add(title)
        n += 1
        per_region[region] = per_region.get(region, 0) + 1
        folder = os.path.join(RAW, f"{n:03d}")
        os.makedirs(os.path.join(folder, "pages"), exist_ok=True)
        rec = {"no": n, "region": region, "title": name, "pages": pc,
               "pdf_bytes": size, "descurl": ii.get("descriptionurl") or ""}
        try:
            fetch(ii["url"], os.path.join(folder, "doc.pdf"))
            rec["pdf"] = True
        except Exception as e:
            rec["pdf"] = False
            rec["error"] = type(e).__name__

        thumb = (ii.get("thumburl") or "").replace("page1-", "page{p}-")
        ok = 0
        for p in range(1, pc + 1):
            if thumb:
                try:
                    fetch(thumb.format(p=p), os.path.join(folder, "pages", f"p-{p:05d}.jpg"), timeout=60)
                    ok += 1
                except Exception:
                    pass
            time.sleep(0.12)
        rec["pages_got"] = ok
        records.append(rec)
        print(f"  {region} {n:03d} {pc:2d}p {size/1048576:5.1f}MB 图{ok:2d}  {name[:50]}", flush=True)
        time.sleep(1.0)

json.dump(records, open(os.path.join(ROOT, "补抓.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"\n新增 {len(records)} 本")
