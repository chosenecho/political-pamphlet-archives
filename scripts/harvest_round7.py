"""第八轮补采：美国妇女参政海报与其他国别（约 50 件）。

上一轮调查显示可采量大：
  美国妇女参政 109、英国 33、法国 26、奥地利 9、荷兰 9、
  德国反战 7、西班牙 4、意大利 3、比利时 2、波兰 2、爱尔兰 5

本脚本按国别配额挑选，优先美国妇女参政（此前该主题只有少量单页）。
筛 1945 年前、JPEG 格式、最小边 700px。

用法：
    python scripts/harvest_round7.py --dry
    python scripts/harvest_round7.py
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

ROOT = os.path.join(BASE, "images", "round7")
RAW = os.path.join(ROOT, "raw")
CATALOG = os.path.join(BASE, "data", "catalog.json")

UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only) "
      "Python-urllib")

YEAR_MAX = 1945
MIN_SIDE = 700
MAX_SIDE = 2000
QUALITY = 88

#: (国别, 立场, 分类, 配额)
JOBS = [
    ("美国", "妇女参政", "Category:Women's suffrage in the United States", 22),
    ("英国", "工党与社会主义", "Category:Political posters of the United Kingdom", 8),
    ("法国", "选举宣传", "Category:Political posters of France", 8),
    ("奥地利", "社会民主党", "Category:Political posters of Austria", 5),
    ("荷兰", "社会主义", "Category:Political posters of the Netherlands", 5),
    ("德国", "反战", "Category:Anti-war posters", 4),
    ("西班牙", "共和派", "Category:Political posters of Spain", 3),
    ("意大利", "法西斯主义", "Category:Political posters of Italy", 2),
    ("爱尔兰", "民族主义", "Category:Political posters of Ireland", 3),
]

#: 明显不是历史宣传品的（现代照片、活动记录、展陈照）
BAD = re.compile(
    r"(DSC[_-]?\d|IMG[_-]?\d|P\d{7}|SAM\s*\d|panoramio|Flickr|"
    r"\.svg$|\.pdf$|\.djvu$|\.ogg$|\.webm$|"
    r"museum of|exhibition|kundgebung|demonstration\s+in|"
    r"parade|conference\s+photo|portrait\s+photo)", re.I)


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
        try:
            d = api(p)
        except Exception:
            break
        out.extend((d.get("query") or {}).get("categorymembers", []))
        cont = (d.get("continue") or {}).get("cmcontinue")
        if not cont:
            break
        time.sleep(0.5)
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
        time.sleep(0.4)
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


def known_titles():
    recs = json.load(open(CATALOG, encoding="utf-8"))
    return {re.sub(r"[^a-z0-9]+", "", (r.get("title") or "").lower())[:40]
            for r in recs}


def download(url, path, retries=3, timeout=120):
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

    picked = []
    seen = set()
    for country, stance, cat, quota in JOBS:
        mem = listcat(cat)
        if not mem:
            print(f"[{country}] {cat.split(':')[-1][:36]}  空")
            continue
        titles = [m["title"] for m in mem]
        infos = imageinfo(titles)
        got = 0
        for t in titles:
            if got >= quota:
                break
            info = infos.get(t)
            if not info:
                continue
            ext = os.path.splitext(t)[1].lower()
            if ext not in (".jpg", ".jpeg"):
                continue
            name = t.split(":", 1)[-1]
            if BAD.search(name):
                continue
            y = year_of(info)
            if not y or int(y) > YEAR_MAX:
                continue
            w, h = info.get("width") or 0, info.get("height") or 0
            if min(w, h) < MIN_SIDE:
                continue
            key = re.sub(r"[^a-z0-9]+", "", name.lower())[:40]
            if key in have or key in seen:
                continue
            seen.add(key)
            md = info.get("extmetadata") or {}
            picked.append({
                "country": country, "stance": stance, "title": name, "year": y,
                "width": w, "height": h, "url": info.get("url", ""),
                "desc_url": info.get("descriptionurl", ""),
                "desc": clean((md.get("ImageDescription") or {}).get("value")),
                "artist": clean((md.get("Artist") or {}).get("value")),
                "category": cat,
            })
            got += 1
        print(f"[{country}] {cat.split(':')[-1][:36]}  选 {got}")

    print(f"\n合计入选 {len(picked)} 件：")
    for p in picked:
        print(f"  {p['country']:4s} {p['year']} {p['width']:>5}x{p['height']:<5} "
              f"{p['title'][:50]}")

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
                im = im.convert("RGB")
                w0, h0 = im.size
                scale = min(1.0, MAX_SIDE / max(w0, h0))
                if scale < 1.0:
                    im = im.resize((int(w0 * scale), int(h0 * scale)), Image.LANCZOS)
                im.save(dest, "JPEG", quality=QUALITY, optimize=True)
            if os.path.abspath(src) != os.path.abspath(dest):
                os.remove(src)
        except Exception as e:
            print(f"  处理失败 {p['title'][:40]}: {type(e).__name__}")
            continue

        p["no"] = i
        p["file"] = "p-00001.jpg"
        records.append(p)
        print(f"  {p['country']:4s} {p['year']} {os.path.getsize(dest)//1024}KB "
              f"{p['title'][:44]}", flush=True)
        time.sleep(0.4)

    json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    from collections import Counter
    total = sum(os.path.getsize(os.path.join(RAW, f"{r['no']:03d}", "p-00001.jpg"))
                for r in records)
    print(f"\n=== 采到 {len(records)} 件，{total / 1048576:.1f} MB ===")
    for k, v in Counter(r["country"] for r in records).most_common():
        print(f"   {k:5s} {v}")


if __name__ == "__main__":
    main()
