"""只收多页小册子：从 Commons 找 PDF，下载整本 + 逐页缩略图。

判定标准：文件为 PDF、pagecount 4–60、标题/描述含政党或竞选语义。
"""

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

QUOTA = 5          # 每国最多
MINP, MAXP = 4, 60  # 页数范围（排除单页传单与长篇著作）
MAX_MB = 30        # 单个 PDF 体积上限

REGIONS = {
    "美国": ["campaign literature United States", "campaign pamphlet", "election platform",
             "political pamphlet United States"],
    "英国": ["Fabian tract", "election address England", "Labour Party pamphlet",
             "political pamphlet England"],
    "德国": ["Wahlprogramm", "Wahlaufruf", "Parteiprogramm", "Flugschrift Politik"],
    "法国": ["profession de foi", "programme électoral France", "brochure politique"],
    "意大利": ["programma elettorale", "opuscolo politico"],
    "西班牙": ["programa electoral", "folleto político"],
    "俄国": ["программа партии", "брошюра политическая", "листовка"],
    "荷兰": ["verkiezingsprogramma"],
    "波兰": ["program wyborczy", "broszura polityczna"],
    "捷克": ["volební program"],
    "日本": ["選挙公報", "政綱"],
    "印度": ["election manifesto India"],
    "拉美": ["programa electoral", "folleto electoral"],
    "北欧": ["valprogram", "valmanifest"],
}


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


def fetch(url, path, retries=3, timeout=120):
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


def safe(s, n=44):
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", re.sub(r"<[^>]+>", "", str(s)))
    return s[:n].strip(" ._-") or "untitled"


records, seen, n = [], set(), 0

for region, queries in REGIONS.items():
    got = 0
    for q in queries:
        if got >= QUOTA:
            break
        try:
            d = api({"action": "query", "format": "json", "list": "search",
                     "srsearch": q + " filemime:application/pdf",
                     "srnamespace": "6", "srlimit": "20"})
        except Exception as e:
            print(f"  ERR search {q}: {type(e).__name__}", flush=True)
            continue

        hits = (d.get("query") or {}).get("search") or []
        for h in hits:
            if got >= QUOTA:
                break
            title = h["title"]
            if title in seen:
                continue
            try:
                info = api({"action": "query", "format": "json", "titles": title,
                            "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
                            "iiurlwidth": "500"})
            except Exception:
                continue
            page = list((info.get("query") or {}).get("pages", {}).values())[0]
            ii = (page.get("imageinfo") or [{}])[0]
            pc = ii.get("pagecount") or 0
            size = ii.get("size") or 0
            if not (MINP <= pc <= MAXP) or size > MAX_MB * 1048576:
                continue

            seen.add(title)
            n += 1
            got += 1
            name = title.replace("File:", "")
            folder = os.path.join(RAW, f"{n:03d}")
            os.makedirs(os.path.join(folder, "pages"), exist_ok=True)

            rec = {"no": n, "region": region, "query": q, "title": name,
                   "pages": pc, "pdf_bytes": size,
                   "descurl": ii.get("descriptionurl") or "",
                   "file": f"{n:03d}"}
            try:
                rec["pdf"] = fetch(ii["url"], os.path.join(folder, "doc.pdf")) and "doc.pdf"
            except Exception as e:
                rec["pdf"] = None
                rec["error"] = type(e).__name__

            thumb = (ii.get("thumburl") or "").replace("page1-", "page{p}-")
            ok = 0
            for p in range(1, pc + 1):
                fp = os.path.join(folder, "pages", f"p-{p:05d}.jpg")
                if thumb:
                    try:
                        fetch(thumb.format(p=p), fp, timeout=60)
                        ok += 1
                    except Exception:
                        pass
                time.sleep(0.15)
            rec["pages_got"] = ok
            records.append(rec)
            print(f"  {region} {n:03d} {pc:2d}p {size/1048576:5.1f}MB 缩略 {ok:2d}  {name[:44]}", flush=True)
            time.sleep(1.2)
    print(f"[{region}] {got} 本", flush=True)

json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
ok = [r for r in records if r.get("pdf")]
print(f"\n=== 共 {len(records)} 本，PDF 完整 {len(ok)} ===")
from collections import Counter
for k, v in Counter(r["region"] for r in records).most_common():
    print(f"   {k:6s} {v}")
