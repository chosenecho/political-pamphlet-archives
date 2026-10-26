"""补抓内页：短篇取全本，长篇取前 6 页 + 末尾 2 页。"""

import json
import os
import re
import ssl
import sys
import time
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "images", "modernhistory")
OUT = os.path.join(SRC, "pages")
os.makedirs(OUT, exist_ok=True)

FULL_CAP = 30      # 页数 ≤ 30 的整本抓
HEAD, TAIL = 6, 2  # 长篇取前 6 后 2


def log(m):
    print(m, flush=True)


def total_pages(rec):
    m = re.search(r"(\d+)", str(rec.get("pages") or ""))
    return int(m.group(1)) if m else 0


def page_url(base, n):
    stem = base.rsplit("_", 1)[0]
    return f"{stem}_{n:05d}.jpg/full/1000,/0/default.jpg"


def fetch(url, path, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
            with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
                data = r.read()
            if len(data) < 3000:
                raise ValueError(f"small {len(data)}")
            open(path, "wb").write(data)
            return len(data)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


records = [x for x in json.load(open(os.path.join(SRC, "metadata.json"), encoding="utf-8")) if x.get("ok")]
log(f"条目 {len(records)}")

done_files = 0
for idx, rec in enumerate(records, 1):
    tp = total_pages(rec)
    if tp <= 0:
        continue
    if tp <= FULL_CAP:
        wanted = list(range(1, tp + 1))
        mode = "full"
    else:
        wanted = list(range(1, HEAD + 1)) + list(range(max(HEAD + 1, tp - TAIL + 1), tp + 1))
        mode = "sample"

    folder = os.path.join(OUT, f"{rec['no']:03d}")
    os.makedirs(folder, exist_ok=True)
    got = []
    for p in wanted:
        path = os.path.join(folder, f"p-{p:05d}.jpg")
        if os.path.exists(path) and os.path.getsize(path) > 3000:
            got.append(p)
            continue
        try:
            fetch(page_url(rec["iiif"], p), path)
            got.append(p)
            done_files += 1
        except Exception as e:
            log(f"   ERR {rec['no']:03d} p{p} {type(e).__name__}")
        time.sleep(0.15)

    rec["pages_dir"] = f"pages/{rec['no']:03d}"
    rec["pages_downloaded"] = got
    rec["page_mode"] = mode
    if idx % 15 == 0:
        log(f"  [{idx}/{len(records)}] {rec['title'][:28]} {mode} {len(got)}p  (累计 {done_files} 张)")

json.dump(records, open(os.path.join(SRC, "metadata.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
total = sum(len(r.get("pages_downloaded", [])) for r in records)
sz = sum(os.path.getsize(os.path.join(dp, f))
         for dp, _, fs in os.walk(OUT) for f in fs)
log(f"\n=== 内页完成：{total} 张，{sz/1048576:.1f} MB ===")
