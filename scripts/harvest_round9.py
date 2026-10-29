"""第九轮补采：从 Commons 各分类批量筛历史宣传品（1945 年前）。

当前单页 336 件，各分类仍有大量未收：
    美国政治海报 460、美国妇女参政 175、英国 144、德国 111、法国 71、
    日本 57、葡萄牙 50、爱尔兰 41、波兰 30、意大利 24、奥地利 19、
    西班牙 17、瑞典 17、荷兰 14、俄国 7

按国别配额挑选，全部走「年代 + 格式 + 尺寸 + 去重 + 已收过滤」。
目标 60 件上下。

用法：
    python scripts/harvest_round9.py --dry
    python scripts/harvest_round9.py
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

ROOT = os.path.join(BASE, "images", "round9")
RAW = os.path.join(ROOT, "raw")
CATALOG = os.path.join(BASE, "data", "catalog.json")

UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only) "
      "Python-urllib")

PROXY = "http://127.0.0.1:10808"
YEAR_MAX = 1945
MIN_SIDE = 700
MAX_SIDE = 2000
QUALITY = 88

#: (国别, 立场, 分类, 配额)
JOBS = [
    ("美国", "选举宣传", "Category:Election posters in the United States", 10),
    ("美国", "妇女参政", "Category:Women's suffrage in the United States", 10),
    ("日本", "选举宣传", "Category:Political posters of Japan", 8),
    ("德国", "选举宣传", "Category:Political posters of Germany", 8),
    ("英国", "工党与社会主义", "Category:Political posters of the United Kingdom", 6),
    ("法国", "选举宣传", "Category:Political posters of France", 6),
    ("意大利", "法西斯主义", "Category:Political posters of Italy", 5),
    ("波兰", "社会主义", "Category:Political posters of Poland", 4),
    ("爱尔兰", "民族主义", "Category:Political posters of Ireland", 4),
    ("奥地利", "社会民主党", "Category:Political posters of Austria", 4),
    ("西班牙", "共和派", "Category:Political posters of Spain", 3),
    ("葡萄牙", "共和派", "Category:Political posters of Portugal", 3),
    ("瑞典", "社会民主党", "Category:Political posters of Sweden", 3),
    ("荷兰", "社会主义", "Category:Political posters of the Netherlands", 2),
    ("俄国", "社会主义", "Category:Political posters of Russia", 2),
]

#: 非宣传品：现代照片、活动记录、技术图纸、标本、宗教典籍
BAD = re.compile(
    r"(DSC[_-]?\d|IMG[_-]?\d|P\d{7}|SAM\s*\d|panoramio|Flickr|ubt\)|"
    r"\.svg$|\.pdf$|\.djvu$|\.ogg$|\.webm$|\.gif$|\.tif{1,2}$|"
    r"museum of|exhibition|kundgebung|demonstration\s+in|parade|"
    r"portrait\s+photo|Herbier|bdrc-|yn5\d\d|Vitis|"
    r"cover\s+of|front\s+cover|book\s+cover|"
    # 逐条核验后剔除的三类：
    #   Racistcampaignposter / 1 —— 同一文件（LoC cph.3g05342），种族主义竞选宣传
    #   IV Olympische Winterspiele —— 1936 冬奥海报，非政党宣传品
    #   Kreis-Tag der NSDAP —— 党务活动日程，非宣传册
    r"Racistcampaignposter|Olympische Winterspiele|Kreis-Tag)", re.I)


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return http.fetch_json(url, timeout=45, retries=4)


def listcat(cat, limit=500):
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
        time.sleep(0.4)
    return out


def imageinfo(titles):
    out = {}
    for i in range(0, len(titles), 20):
        chunk = titles[i:i + 20]
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


def opener():
    op = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    op.addheaders = [("User-Agent", UA)]
    return op


def download(op, url, path, retries=2, timeout=180):
    for i in range(retries):
        try:
            with op.open(url, timeout=timeout) as r:
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

    picked, seen = [], set()
    for country, stance, cat, quota in JOBS:
        mem = listcat(cat)
        if not mem:
            print(f"[{country}] {cat.split(':')[-1][:34]}  空")
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
            if ext not in (".jpg", ".jpeg", ".png"):
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
            })
            got += 1
        print(f"[{country}] {cat.split(':')[-1][:34]:34s} 选 {got}")

    print(f"\n合计入选 {len(picked)} 件：")
    for p in picked:
        print(f"  {p['country']:4s} {p['year']} {p['width']:>5}x{p['height']:<5} "
              f"{p['title'][:52]}")

    if dry:
        return 0

    os.makedirs(RAW, exist_ok=True)
    from PIL import Image
    op = opener()

    records = []
    for i, p in enumerate(picked, 1):
        folder = os.path.join(RAW, f"{i:03d}")
        os.makedirs(folder, exist_ok=True)
        ext = os.path.splitext(p["url"].split("?")[0])[1].lower() or ".jpg"
        src = os.path.join(folder, f"orig{ext}")
        dest = os.path.join(folder, "p-00001.jpg")
        try:
            download(op, p["url"], src)
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
        print(f"  [{i}/{len(picked)}] {p['country']:4s} {p['year']} "
              f"{os.path.getsize(dest)//1024}KB {p['title'][:40]}", flush=True)
        time.sleep(0.3)

    json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    from collections import Counter
    total = sum(os.path.getsize(os.path.join(RAW, f"{r['no']:03d}", "p-00001.jpg"))
                for r in records)
    print(f"\n=== 采到 {len(records)} 件，{total / 1048576:.1f} MB ===")
    for k, v in Counter(r["country"] for r in records).most_common():
        print(f"   {k:5s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
