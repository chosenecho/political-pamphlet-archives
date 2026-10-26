"""中文小册子定稿：按候选顺序取满 20 件完整本。"""

import json
import os
import shutil
import ssl
import time
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "images", "小册子")
OUT = os.path.join(ROOT, "raw")
TARGET = 20

pool = json.load(open(os.path.join(ROOT, "候选.json"), encoding="utf-8"))


def fetch(url, path, retries=2):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
            with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
                data = r.read()
            if len(data) < 3000:
                raise ValueError("small")
            open(path, "wb").write(data)
            return True
        except Exception:
            if i == retries - 1:
                return False
            time.sleep(1.5)


def page_url(base, n):
    return f"{base.rsplit('_', 1)[0]}_{n:05d}.jpg/full/1000,/0/default.jpg"


kept, dropped = [], []
for idx, rec in enumerate(pool, 1):
    if len(kept) >= TARGET:
        break
    rid = f"{idx:03d}"
    d = os.path.join(OUT, rid)
    pdir = os.path.join(d, "pages")
    os.makedirs(pdir, exist_ok=True)
    cover = os.path.join(d, "cover.jpg")

    if not (os.path.exists(cover) and os.path.getsize(cover) > 3000):
        if not fetch(page_url(rec["iiif"], 1), cover):
            dropped.append(rid)
            continue

    ok = 0
    for p in range(1, rec["pages"] + 1):
        fp = os.path.join(pdir, f"p-{p:05d}.jpg")
        if os.path.exists(fp) and os.path.getsize(fp) > 3000:
            ok += 1
            continue
        if fetch(page_url(rec["iiif"], p), fp):
            ok += 1
        time.sleep(0.1)

    if ok < rec["pages"]:
        dropped.append(f"{rid}({ok}/{rec['pages']})")
        continue

    rec2 = dict(rec)
    rec2.update({"id": rid, "pages_got": ok})
    kept.append(rec2)

keep_ids = {r["id"] for r in kept}
for name in os.listdir(OUT):
    p = os.path.join(OUT, name)
    if os.path.isdir(p) and name not in keep_ids:
        shutil.rmtree(p)

json.dump(kept, open(os.path.join(ROOT, "选定20.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

print(f"保留 {len(kept)} 件，完整 {sum(r['pages_got'] for r in kept)} 页")
print(f"跳过 {len(dropped)} 件：{', '.join(dropped[:10])}")
for r in kept:
    print(f"  {r['id']} {r['year']} {r['pages']:2d}p  {r['title'][:38]}")
