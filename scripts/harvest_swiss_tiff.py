"""采集瑞士 TIFF 版历史选举海报（经由 Commons 缩略图接口）。

上一轮只收了 JPEG，另有 20 件 1945 年前的 TIFF 未收。
TIFF 原图 2879x4096（约 20MB），浏览器与阅读器都显示不了。
MediaWiki 的 iiurlwidth 接口可以按需生成 JPEG 缩略图
（/thumb/.../lossy-page1-1920px-xxx.tif.jpg），直接取 1920px 即可，
既免去下载 20MB 原图，也免去本地转码。

用法：
    python scripts/harvest_swiss_tiff.py --dry
    python scripts/harvest_swiss_tiff.py
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

ROOT = os.path.join(BASE, "images", "swiss-tiff")
RAW = os.path.join(ROOT, "raw")
CATALOG = os.path.join(BASE, "data", "catalog.json")

UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only) "
      "Python-urllib")

YEAR_MAX = 1945
THUMB_W = 1920
CATS = [
    "Category:Election posters in Switzerland",
    "Category:Referendum posters in Switzerland",
]


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return http.fetch_json(url, timeout=45, retries=4)


def listcat(cat, limit=200):
    out, cont = [], None
    for _ in range(4):
        p = {"action": "query", "format": "json", "list": "categorymembers",
             "cmtitle": cat, "cmtype": "file", "cmlimit": str(limit)}
        if cont:
            p["cmcontinue"] = cont
        d = api(p)
        out.extend((d.get("query") or {}).get("categorymembers", []))
        cont = (d.get("continue") or {}).get("cmcontinue")
        if not cont:
            break
        time.sleep(0.5)
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


def download(url, path, retries=3, timeout=180):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) < 5000:
                raise ValueError("too small")
            with open(path, "wb") as f:
                f.write(data)
            return len(data)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


def known_titles():
    recs = json.load(open(CATALOG, encoding="utf-8"))
    return {re.sub(r"[^a-z0-9]+", "", (r.get("title") or "").lower())[:40]
            for r in recs}


def main():
    dry = "--dry" in sys.argv
    have = known_titles()

    titles = []
    for c in CATS:
        mem = listcat(c)
        titles.extend(m["title"] for m in mem)
    titles = sorted(set(titles))
    print(f"候选 {len(titles)} 个文件")

    picked = []
    for i in range(0, len(titles), 15):
        chunk = titles[i:i + 15]
        try:
            d = api({"action": "query", "format": "json", "prop": "imageinfo",
                     "iiprop": "url|size|extmetadata", "iiurlwidth": str(THUMB_W),
                     "titles": "|".join(chunk)})
        except Exception as e:
            print(f"  批次失败 {type(e).__name__}")
            continue
        for page in (d.get("query") or {}).get("pages", {}).values():
            t = page.get("title")
            ii = page.get("imageinfo")
            if not t or not ii:
                continue
            info = ii[0]
            ext = os.path.splitext(t)[1].lower()
            if ext not in (".tif", ".tiff"):
                continue
            y = year_of(info)
            if not y or int(y) > YEAR_MAX:
                continue
            name = t.split(":", 1)[-1]
            key = re.sub(r"[^a-z0-9]+", "", name.lower())[:40]
            if key in have:
                continue
            thumb = info.get("thumburl")
            if not thumb:
                print(f"  跳过（无缩略图）{name[:50]}")
                continue
            md = info.get("extmetadata") or {}
            picked.append({
                "title": name, "year": y,
                "width": info.get("width"), "height": info.get("height"),
                "thumb": thumb,
                "desc_url": info.get("descriptionurl", ""),
                "desc": clean((md.get("ImageDescription") or {}).get("value")),
                "artist": clean((md.get("Artist") or {}).get("value")),
            })
        time.sleep(0.5)

    picked.sort(key=lambda x: (x["year"], x["title"]))
    print(f"\n入选 {len(picked)} 件：")
    for p in picked:
        print(f"  {p['year']} {p['width']}x{p['height']} {p['title'][:48]}")
        print(f"      {p['desc'][:90]}")

    if dry:
        return

    os.makedirs(RAW, exist_ok=True)
    from PIL import Image

    records = []
    for i, p in enumerate(picked, 1):
        folder = os.path.join(RAW, f"{i:03d}")
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, "p-00001.jpg")
        try:
            download(p["thumb"], dest)
        except Exception as e:
            print(f"  下载失败 {p['title'][:40]}: {type(e).__name__}")
            continue
        # 统一到 2000px 以内并重编码，控制体积
        try:
            with Image.open(dest) as im:
                im = im.convert("RGB")
                w0, h0 = im.size
                scale = min(1.0, 2000 / max(w0, h0))
                if scale < 1.0:
                    im = im.resize((int(w0 * scale), int(h0 * scale)), Image.LANCZOS)
                im.save(dest, "JPEG", quality=88, optimize=True)
        except Exception as e:
            print(f"  处理失败 {p['title'][:40]}: {type(e).__name__}")
            continue

        p["no"] = i
        p["file"] = "p-00001.jpg"
        records.append(p)
        print(f"  {p['year']} -> {os.path.getsize(dest)//1024}KB {p['title'][:44]}",
              flush=True)
        time.sleep(0.4)

    json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    total = sum(os.path.getsize(os.path.join(RAW, f"{r['no']:03d}", "p-00001.jpg"))
                for r in records)
    print(f"\n=== 采到 {len(records)} 件，合计 {total / 1048576:.1f} MB ===")


if __name__ == "__main__":
    main()
