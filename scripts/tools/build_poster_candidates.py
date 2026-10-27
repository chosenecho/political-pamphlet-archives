"""从 Commons 分类里筛出历史政治海报，输出候选清单供下载。

判定规则（严）：
  1. 年份 1840–1990，且必须来自 extmetadata 的日期字段
  2. 最小边 >= 700px（低于此看不清海报文字）
  3. 排除现代照片、博物馆展品照、书籍扫描页、地形图
  4. 排除同题材多版（保留分辨率最高的）

输出到 images/_poster_candidates.json，由 harvest_posters.py 读取下载。
"""

import json
import os
import re
import sys
import time
import urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import http

OUT = os.path.join(BASE, "images", "_poster_candidates.json")

YEAR_MIN, YEAR_MAX = 1840, 1990
MIN_SIDE = 700

#: (国别, 立场, 分类) —— 只列确实有历史藏量的分类
CATS = [
    ("德国", "社会主义", "Category:Political posters of Germany"),
    ("德国", "纳粹主义", "Category:Political posters of Nazi Germany"),
    ("德国", "社会主义", "Category:Social Democratic Party of Germany posters"),
    ("奥地利", "基督教社会党", "Category:Political posters of Austria"),
    ("奥地利", "社会民主党", "Category:Election posters in Austria"),
    ("法国", "共和派", "Category:Political posters of France"),
    ("英国", "妇女参政", "Category:Suffragette posters"),
    ("英国", "工党与社会主义", "Category:Labour Party (UK) posters"),
    ("英国", "工党与社会主义", "Category:Political posters of the United Kingdom"),
    ("荷兰", "社会主义", "Category:Political posters of the Netherlands"),
    ("比利时", "社会主义", "Category:Political posters of Belgium"),
    ("瑞典", "社会民主党", "Category:Political posters of Sweden"),
    ("俄国", "社会主义", "Category:Political posters of Russia"),
    ("苏联", "共产主义", "Category:Political posters of the Soviet Union"),
    ("西班牙", "共和派", "Category:Political posters of the Spanish Civil War"),
    ("意大利", "法西斯主义", "Category:Political posters of Italy"),
    ("美国", "选举宣传", "Category:Political posters of the United States"),
    ("日本", "选举宣传", "Category:Election posters in Japan"),
    ("爱尔兰", "民族主义", "Category:Political posters of Ireland"),
    ("匈牙利", "社会主义", "Category:Election posters in Hungary"),
    ("拉美", "选举宣传", "Category:Election posters in Argentina"),
    ("拉美", "社会主义", "Category:Election posters in Chile"),
    ("波兰", "社会主义", "Category:Political posters of Poland"),
    ("葡萄牙", "共和派", "Category:Political posters of Portugal"),
]

#: 现代照片、展品照、书页、无关题材
BAD = re.compile(
    r"(DSC[_-]?\d|IMG[_-]?\d|P\d{7}|SAM\s*\d|RalfR|panoramio|Flickr|ubt\)|"
    r"Museum of World War|Muzeum II Wojny|museum exhibition|"
    r"\.svg$|\.tif$|\.pdf$|\.djvu$|\.ogg$|\.webm$|\.gif$|"
    r"Straßenplakat|street\s*performer|Fahrrad|Fahrradhäuschen|"
    r"Demonstrationen und Proteste|Blockupy|Kundgebung Plakat|"
    r"Stuttgart- Baker|Naturgesetze|Schneckerling|bergpartei|"
    r"Esst die reichen|Fickdeingroßprojekt|Lieber wütend|"
    r"Mainz-Mombach|Diplomatie statt Waffen|Putin und Biden|"
    r"Volkspolizei propaganda poster 1954|Tatort|Pro Reli|"
    r"Deutscher Bundestag Poster|Die-schenker-plakat|Kdf axb01|"
    r"Campaign poster for the Deutsche Wohnen|Bündnis 90 Plakat|"
    r"Angriff auf den SPD|Wahlplakat von hinten|Wahlplakat von MENSCHEN|"
    r"Vorbereitung von Wahlplakaten|Election campaign posters in Stuttgart|"
    r"Wir waren alle noch nie|Vandalismus|Welchen A|Wahlplakat\.JPG|"
    r"Ahaus-Tschernobyl|Bürgerbegehren|Monstertrasse|Röhrse-Suedlink|"
    r"FDP Parteitag|12-10-13-dokument|Aufruf zum Erhalt|"
    r"001 1968|002 1968|003 1968|DDR 062|Der rote krieg|"
    r"Fest-Symphonie|IV Olympische|Olympische Winterspiele|"
    r"The Museum of World War|Poster from the Freikorps|Poster of the Freikorps)", re.I)


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return http.fetch_json(url, timeout=45)


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
    return out


def year_of(info):
    md = (info or {}).get("extmetadata") or {}
    for k in ("DateTimeOriginal", "DateTime", "Date", "DateTimeDigitized"):
        v = (md.get(k) or {}).get("value")
        if not v:
            continue
        m = re.search(r"(1[6-9]\d{2}|20\d{2})", str(v))
        if m:
            return m.group(1)
    return ""


def main():
    cat = json.load(open(os.path.join(BASE, "data", "catalog.json"), encoding="utf-8"))
    have = {re.sub(r"[^a-z0-9]+", "", r.get("title", "").lower())[:30] for r in cat}

    cands = []
    seen = set()
    for country, stance, c in CATS:
        mem = listcat(c)
        if not mem:
            print(f"[{country}] {c} 空或失败")
            continue
        titles = [m["title"] for m in mem]
        infos = imageinfo(titles)
        kept = 0
        for t in titles:
            info = infos.get(t)
            if not info:
                continue
            name = t.split(":", 1)[-1]
            if BAD.search(name):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in (".jpg", ".jpeg", ".png"):
                continue
            y = year_of(info)
            if not y or not (YEAR_MIN <= int(y) <= YEAR_MAX):
                continue
            w, h = info.get("width") or 0, info.get("height") or 0
            if min(w, h) < MIN_SIDE:
                continue
            key = re.sub(r"[^a-z0-9]+", "", name.lower())[:30]
            if key in have or key in seen:
                continue
            seen.add(key)
            cands.append({
                "country": country, "stance": stance, "title": name,
                "year": y, "width": w, "height": h,
                "url": info.get("url", ""),
                "desc_url": info.get("descriptionurl", ""),
                "category": c,
            })
            kept += 1
        print(f"[{country}] {c.split(':')[-1][:40]:40s} 文件 {len(mem):3d} -> 合格 {kept:3d}")
        time.sleep(0.2)

    json.dump(cands, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n候选合计 {len(cands)} -> {OUT}")
    from collections import Counter
    for k, v in Counter(c2["country"] for c2 in cands).most_common():
        print(f"   {k:5s} {v}")


if __name__ == "__main__":
    main()
