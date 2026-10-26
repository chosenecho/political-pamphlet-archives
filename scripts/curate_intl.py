"""国际素材清洗：按标题/描述重新判定国别，去同系列重复，按国家限额。"""

import json
import os
import re
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "images", "国际", "raw", "metadata.json")
OUT = os.path.join(BASE, "images", "国际", "精选.json")

# 国别判定关键词（按顺序匹配，越specific越前）
COUNTRY_HINTS = [
    ("荷兰", ["pvdа", "pvda", "vvd", "cda", "nederland", "dutch", "tweede kamer", "verkiezings"]),
    ("德国", ["cdu", "spd", "kpd", "nsdap", "fdp", "csu", "deutschland", "deutsche",
             "reichstag", "bundestag", "wahlkampf", "wahlplakat", "weimar", "kaiserreich"]),
    ("法国", ["sfio", "pcf", "france", "français", "assemblée", "front populaire", "gaulle"]),
    ("意大利", ["pci", "psi", "democrazia cristiana", "italia", "fascista", "duce", "italian"]),
    ("西班牙", ["psoe", "cnt", "falange", "españa", "espanol", "guerra civil", "republicana"]),
    ("葡萄牙", ["portugal", "estado novo", "salazar", "cartaz"]),
    ("英国", ["labour party", "conservative party", "liberal party", "suffragette",
             "british", "britain", "england", "london"]),
    ("美国", ["campaign", "republican", "democrat", "american", "usa", "united states", "gop"]),
    ("俄国", ["лени", "большевик", "ссср", "soviet", "bolshevik", "листовк", "плакат", "russian"]),
    ("波兰", ["polsk", "polska", "wyborcz"]),
    ("捷克", ["česk", "cesk", "czechoslovak", "praha"]),
    ("奥地利", ["österreich", "osterreich", "austria", "wien"]),
    ("日本", ["日本", "選挙", "ポスター", "japan", "大政", "昭和"]),
    ("印度", ["india", "congress", "gandhi", "nehru"]),
    ("拉美", ["méxico", "mexico", "chile", "argentina", "brasil", "perú", "cuba", "latinoam"]),
]

CAP = 12          # 每国上限
SERIES_CAP = 3    # 同系列上限


def guess_country(rec):
    hay = (rec.get("title", "") + " " + rec.get("desc", "")).lower()
    for country, keys in COUNTRY_HINTS:
        if any(k in hay for k in keys):
            return country
    return rec.get("region", "其他")


def series_key(title):
    """去掉年份与数字，得到系列键。"""
    s = re.sub(r"(18|19)\d{2}", "", title.lower())
    s = re.sub(r"\d+", "", s)
    s = re.sub(r"[_\-\s.]+", "", s)
    return s[:28]


recs = [r for r in json.load(open(SRC, encoding="utf-8")) if r.get("ok")]

for r in recs:
    r["country"] = guess_country(r)

# 系列去重 + 国家限额；优先保留年份分散的
by_country = defaultdict(list)
for r in recs:
    by_country[r["country"]].append(r)

selected, dropped_series, dropped_cap = [], 0, 0
for country, items in by_country.items():
    items.sort(key=lambda x: x["year"])
    seen_series = Counter()
    picked = []
    for r in items:
        k = series_key(r["title"])
        if seen_series[k] >= SERIES_CAP:
            dropped_series += 1
            continue
        if len(picked) >= CAP:
            dropped_cap += 1
            continue
        seen_series[k] += 1
        picked.append(r)
    selected.extend(picked)

selected.sort(key=lambda r: (r["country"], r["year"]))
json.dump(selected, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"原始 {len(recs)} 件 → 精选 {len(selected)} 件")
print(f"（同系列超限去掉 {dropped_series}，国家超限去掉 {dropped_cap}）\n")
for k, v in Counter(r["country"] for r in selected).most_common():
    yrs = [r["year"] for r in selected if r["country"] == k]
    print(f"  {k:6s} {v:3d} 件  {min(yrs)}–{max(yrs)}")
