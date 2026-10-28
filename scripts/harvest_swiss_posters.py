"""瑞士历史选举海报采集（Commons）。

瑞士此前没有任何条目。Commons 上有两个来源：
  · CH-NB Poster Collection SNL POL *  —— 瑞士国家图书馆，JPEG，2560x3600 级
  · CH-000957-X-* —— 档案系列，TIFF，浏览器无法直接显示

本脚本只收 JPEG（.tif 需先转码，浏览器与阅读器都显示不了）。
筛 1945 年及以前、最小边 >= 800px。

用法：
    python scripts/harvest_swiss_posters.py --dry
    python scripts/harvest_swiss_posters.py
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import http

ROOT = os.path.join(BASE, "images", "swiss-posters")
RAW = os.path.join(ROOT, "raw")
CATALOG = os.path.join(BASE, "data", "catalog.json")

UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only) "
      "Python-urllib")

YEAR_MAX = 1945
MIN_SIDE = 800
MAX_SIDE = 2000
QUALITY = 88
QUOTA = 30          # 瑞士首次入目录，一次不超过 30 件

CATS = [
    "Category:Election posters in Switzerland",
    "Category:Referendum posters in Switzerland",
]


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return http.fetch_json(url, timeout=45, retries=4)


def listcat(cat, limit=100):
    out, cont = [], None
    for _ in range(3):
        p = {"action": "query", "format": "json", "list": "categorymembers",
             "cmtitle": cat, "cmtype": "file", "cmlimit": str(limit)}
        if cont:
            p["cmcontinue"] = cont
        d = api(p)
        out.extend((d.get("query") or {}).get("categorymembers", []))
        cont = (d.get("continue") or {}).get("cmcontinue")
        if not cont:
            break
        time.sleep(0.6)
    return out


def imageinfo(titles):
    out = {}
    for i in range(0, len(titles), 15):
        chunk = titles[i:i + 15]
        try:
            d = api({"action": "query", "format": "json", "prop": "imageinfo",
                     "iiprop": "url|size|extmetadata", "titles": "|".join(chunk)})
        except Exception:
            continue
        for page in (d.get("query") or {}).get("pages", {}).values():
            ii = page.get("imageinfo")
            if ii:
                out[page.get("title")] = ii[0]
        time.sleep(0.6)
    return out


def year_of(info):
    md = (info or {}).get("extmetadata") or {}
    for k in ("DateTimeOriginal", "DateTime", "Date", "DateTimeDigitized"):
        v = (md.get(k) or {}).get("value")
        if v:
            m = re.search(r"(1[6-9]\d{2}|20\d{2})", str(v))
            if m:
                return m.group(1)
    return ""


def clean(s):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def desc_of(info):
    md = (info or {}).get("extmetadata") or {}
    return clean((md.get("ImageDescription") or {}).get("value"))


def artist_of(info):
    md = (info or {}).get("extmetadata") or {}
    return clean((md.get("Artist") or {}).get("value"))


def known_titles():
    recs = json.load(open(CATALOG, encoding="utf-8"))
    return {re.sub(r"[^a-z0-9]+", "", (r.get("title") or "").lower())[:40]
            for r in recs}


def download(url, path, retries=3, timeout=180):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) < 3000:
                raise ValueError("too small")
            with open(path, "wb") as f:
                f.write(data)
            return len(data)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


def main():
    dry = "--dry" in sys.argv
    have = known_titles()

    titles = []
    for c in CATS:
        mem = listcat(c)
        print(f"{c}: {len(mem)} 文件")
        titles.extend(m["title"] for m in mem)
    try:
        d = api({"action": "query", "format": "json", "list": "search",
                 "srsearch": "CH-NB Poster Collection SNL POL", "srnamespace": "6",
                 "srlimit": "50"})
        hits = (d.get("query") or {}).get("search", [])
        print(f"SNL POL 搜索: {len(hits)} 条")
        titles.extend(h["title"] for h in hits)
    except Exception as e:
        print(f"SNL POL 搜索失败 {type(e).__name__}")

    titles = sorted(set(titles))
    print(f"\n候选标题 {len(titles)}，取元数据…")
    infos = imageinfo(titles)

    picked = []
    for t in titles:
        info = infos.get(t)
        if not info:
            continue
        ext = os.path.splitext(t)[1].lower()
        if ext not in (".jpg", ".jpeg"):
            continue
        y = year_of(info)
        if not y or int(y) > YEAR_MAX:
            continue
        w, h = info.get("width") or 0, info.get("height") or 0
        if min(w, h) < MIN_SIDE:
            continue
        name = t.split(":", 1)[-1]
        key = re.sub(r"[^a-z0-9]+", "", name.lower())[:40]
        if key in have:
            continue
        picked.append({
            "title": name, "year": y, "width": w, "height": h,
            "url": info.get("url", ""),
            "desc_url": info.get("descriptionurl", ""),
            "desc": desc_of(info), "artist": artist_of(info),
        })

    # 按年份排序，同作者适度分散
    picked.sort(key=lambda x: (x["year"], x["title"]))
    picked = picked[:QUOTA]

    print(f"\n入选 {len(picked)} 件：")
    for p in picked:
        print(f"  {p['year']} {p['width']:>5}x{p['height']:<5} {p['title'][:44]:44s} "
              f"{p['desc'][:40]}")

    if dry:
        return

    os.makedirs(RAW, exist_ok=True)
    from PIL import Image

    records = []
    for i, p in enumerate(picked, 1):
        folder = os.path.join(RAW, f"{i:03d}")
        os.makedirs(folder, exist_ok=True)
        ext = os.path.splitext(p["url"].split("?")[0])[1].lower() or ".jpg"
        src = os.path.join(folder, f"orig{ext}")
        dest = os.path.join(folder, "p-00001.jpg")
        try:
            download(p["url"], src)
        except Exception as e:
            print(f"  下载失败 {p['title'][:40]}: {type(e).__name__}")
            continue
        try:
            with Image.open(src) as im:
                w0, h0 = im.size
                im = im.convert("RGB")
                scale = min(1.0, MAX_SIDE / max(w0, h0))
                if scale < 1.0:
                    im = im.resize((max(1, int(w0 * scale)), max(1, int(h0 * scale))),
                                   Image.LANCZOS)
                im.save(dest, "JPEG", quality=QUALITY, optimize=True)
            if os.path.abspath(src) != os.path.abspath(dest):
                os.remove(src)
        except Exception as e:
            print(f"  处理失败 {p['title'][:40]}: {type(e).__name__}")
            continue

        p["no"] = i
        p["file"] = "p-00001.jpg"
        p["orig_size"] = [w0, h0]
        records.append(p)
        print(f"  {p['year']} {w0}x{h0} -> {os.path.getsize(dest)//1024}KB "
              f"{p['title'][:44]}", flush=True)
        time.sleep(0.5)

    json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    total = sum(os.path.getsize(os.path.join(RAW, f"{r['no']:03d}", "p-00001.jpg"))
                for r in records)
    print(f"\n=== 采到 {len(records)} 件，合计 {total / 1048576:.1f} MB ===")


if __name__ == "__main__":
    main()
