"""Wikimedia Commons 历史政党海报/传单采集。

IA 当前不可达，改从 Commons 补单页宣传品。Commons 的分类混入大量
现代照片，因此不按分类批量抓，而用**主题搜索 + 年代过滤 + 关键词白名单**
逐条判定，只收 1840–1960 年间、明确的政党/政治组织宣传品。

收录后写入 images/commons-new/，由 merge_commons_new.py 并入目录。

用法：
    python scripts/harvest_commons_new.py --dry
    python scripts/harvest_commons_new.py
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

ROOT = os.path.join(BASE, "images", "commons-new")
RAW = os.path.join(ROOT, "raw")

UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only) "
      "Python-urllib")

#: 搜索式：(查询, 国别, 立场)
SEARCHES = [
    # 爱尔兰
    ('incategory:"Election posters in Ireland" Fianna', "爱尔兰", "共和派"),
    ('incategory:"Election posters in Ireland" Fine Gael', "爱尔兰", "民族主义"),
    ('Irish nationalism poster Carsonism', "爱尔兰", "联合派"),
    ('incategory:"Election posters in Ireland" Labour', "爱尔兰", "工党与社会主义"),
    ('"Gaelic League" poster', "爱尔兰", "民族主义"),
    ('Irish "foundation of the republic" vote', "爱尔兰", "共和派"),

    # 奥地利
    ('incategory:"Election posters in Austria" 1919', "奥地利", "社会民主党"),
    ('incategory:"Election posters in Austria" 1920', "奥地利", "基督教社会党"),
    ('"wähle Sozialistische Partei"', "奥地利", "社会民主党"),
    ('"Deutsche Christen Rettet Osterreich"', "奥地利", "基督教社会党"),

    # 匈牙利
    ('incategory:"Election posters in Hungary" 1922', "匈牙利", "民族主义"),
    ('"Magyar Polgári Párt" plakát', "匈牙利", "民族主义"),
    ('"Mihály Bíró" anti-war poster', "匈牙利", "和平主义"),

    # 拉美
    ('incategory:"Election posters in Argentina" 1946', "拉美", "选举宣传"),
    ('incategory:"Election posters in Chile" 1970', "拉美", "社会主义"),
    ('"Afiches políticos" Pinochet', "拉美", "反独裁"),
    ('Mexican "Plan de" manifesto pamphlet', "拉美", "革命派"),
]

#: 必须是历史宣传品：1840–1980（拉美反独裁海报延到 1990）
YEAR_MIN, YEAR_MAX = 1840, 1990

#: 排除现代照片、数码摄影、无关题材
BAD = re.compile(
    r"(DSC[_-]?\d|IMG[_-]?\d|P\d{7}|\(\d{3,}\)\.jpg|"
    r"geograph|Flickr|panoramio|"
    r"\.tif$|\.svg$|\.ogg$|\.webm$|\.pdf$|"
    r"bus\s*stop|Bushaltestelle|街|station|"
    r"redbook|yearbook|almanac|"
    r"portrait\s+of|photograph)", re.I)

#: 同一题材的重复文件：只留分辨率最高的那件。
#: 键为归一化主题，值为(保留的分辨率下限)。抓取时先按主题分组挑最高清。
DEDUP_HINT = re.compile(
    r"(seachtain\s+na\s+gaeilge|deutsche\s+christen|braden\s+o\s+per|"
    r"tomic|pinochet)", re.I)

#: 最小边长：低于此值的扫描件在阅读器里没有研究价值
MIN_SIDE = 500


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return http.fetch_json(url, timeout=45)


def search(q, limit=20):
    return api({"action": "query", "format": "json", "list": "search",
                "srsearch": q, "srnamespace": "6", "srlimit": str(limit)})


def imageinfo(titles):
    """批量取文件 URL、尺寸、上传年份。"""
    if not titles:
        return {}
    out = {}
    for i in range(0, len(titles), 10):
        chunk = titles[i:i + 10]
        d = api({"action": "query", "format": "json", "prop": "imageinfo",
                 "iiprop": "url|size|extmetadata", "titles": "|".join(chunk)})
        for page in (d.get("query") or {}).get("pages", {}).values():
            ii = page.get("imageinfo")
            if ii:
                out[page.get("title")] = ii[0]
    return out


def file_year(info):
    """从 extmetadata 里找日期，取四位年份。"""
    md = (info or {}).get("extmetadata") or {}
    for k in ("DateTimeOriginal", "DateTime", "Date", "DateTimeDigitized"):
        v = (md.get(k) or {}).get("value")
        if not v:
            continue
        m = re.search(r"(1[6-9]\d{2}|20\d{2})", str(v))
        if m:
            return m.group(1)
    return ""


def download(url, path, retries=3, timeout=90):
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


def safe(s, n=44):
    s = re.sub(r'[\\/:*?"<>|]+', "_", str(s))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def known_titles():
    cat = os.path.join(BASE, "data", "catalog.json")
    recs = json.load(open(cat, encoding="utf-8"))
    return {re.sub(r"[^a-z0-9]+", "", r.get("title", "").lower())[:30] for r in recs}


def main():
    dry = "--dry" in sys.argv
    known = known_titles()

    cands = []
    seen = set()
    for q, country, stance in SEARCHES:
        try:
            d = search(q)
        except Exception as e:
            print(f"  搜索失败 {q[:34]}: {type(e).__name__}")
            continue
        hits = (d.get("query") or {}).get("search", [])
        titles = [h["title"] for h in hits if h.get("title") not in seen]
        infos = imageinfo(titles)
        for t in titles:
            if t in seen:
                continue
            name = t.split(":", 1)[-1]
            if BAD.search(name):
                continue
            info = infos.get(t)
            if not info:
                continue
            year = file_year(info)
            if not year or not (YEAR_MIN <= int(year) <= YEAR_MAX):
                continue
            key = re.sub(r"[^a-z0-9]+", "", name.lower())[:30]
            if key in known:
                continue
            seen.add(t)
            cands.append({
                "country": country, "stance": stance, "title": name,
                "desc_url": info.get("descriptionurl", ""),
                "url": info.get("url", ""),
                "width": info.get("width"), "height": info.get("height"),
                "year": year,
            })
        time.sleep(0.3)

    print(f"\n候选 {len(cands)} 件（去重前）：")

    # --- 同题材去重：只保留分辨率最高的一件 ---
    groups = {}
    kept = []
    for c in cands:
        m = DEDUP_HINT.search(c["title"])
        if m:
            key = m.group(1).lower()
            groups.setdefault(key, []).append(c)
        else:
            kept.append(c)
    for key, lst in groups.items():
        lst.sort(key=lambda x: (x.get("width") or 0) * (x.get("height") or 0),
                 reverse=True)
        kept.append(lst[0])
        if len(lst) > 1:
            print(f"  去重 {key}: 保 1 弃 {len(lst) - 1}（保留最高分辨率）")

    # --- 最小边长：低于阈值的扫描件没有研究价值 ---
    before = len(kept)
    kept = [c for c in kept
            if min(c.get("width") or 0, c.get("height") or 0) >= MIN_SIDE]
    if before != len(kept):
        print(f"  剔除过小扫描件 {before - len(kept)} 件（边长 < {MIN_SIDE}）")

    cands = kept
    print(f"\n实际入库 {len(cands)} 件：")
    for c in cands:
        print(f"  {c['country']:4s} {c['year']} {c['width']}x{c['height']} "
              f"{c['title'][:64]}")

    if dry:
        return

    os.makedirs(RAW, exist_ok=True)
    records = []
    for i, c in enumerate(cands, 1):
        folder = os.path.join(RAW, f"{i:03d}")
        os.makedirs(folder, exist_ok=True)
        ext = os.path.splitext(c["url"].split("?")[0])[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png"):
            print(f"  跳过 {c['title'][:40]}: 扩展名 {ext}")
            continue
        dest = os.path.join(folder, f"p-00001{ext}")
        try:
            download(c["url"], dest)
        except Exception as e:
            print(f"  下载失败 {c['title'][:40]}: {type(e).__name__}")
            continue
        c["no"] = i
        c["file"] = os.path.basename(dest)
        records.append(c)
        print(f"  {c['country']:4s} {c['year']} {c['title'][:52]}", flush=True)
        time.sleep(0.6)

    json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n=== 采到 {len(records)} 件 ===")


if __name__ == "__main__":
    main()
