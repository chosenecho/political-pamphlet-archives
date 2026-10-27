"""Wikimedia Commons 历史政治海报批量采集。

读 images/_poster_candidates.json（由 build_poster_candidates.py 生成），
按国别配额下载，统一压到长边 2000px，写入 images/posters-new/。

配额说明：美国的候选里 1950 年代 NARA 政府宣传画占绝大多数，同一题材
反复出现（Allies for World Peace 有十几个版次）。按题材去重后仍多，
故对美国设较低配额，把名额让给史料密度更高的欧洲。

用法：
    python scripts/harvest_posters.py --dry
    python scripts/harvest_posters.py
"""

import json
import os
import re
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

CAND = os.path.join(BASE, "images", "_poster_candidates.json")
ROOT = os.path.join(BASE, "images", "posters-new")
RAW = os.path.join(ROOT, "raw")

UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only) "
      "Python-urllib")

MAX_SIDE = 2000
QUALITY = 88

#: 各国配额
QUOTA = {
    "德国": 14,
    "英国": 12,
    "法国": 10,
    "奥地利": 8,
    "荷兰": 6,
    "美国": 10,
    "拉美": 8,
    "爱尔兰": 3,
    "意大利": 3,
    "比利时": 3,
    "日本": 3,
    "波兰": 3,
    "葡萄牙": 3,
    "俄国": 2,
    "苏联": 2,
    "瑞典": 1,
    "匈牙利": 1,
}

#: 同题材多版去重：键相同的只留分辨率最高的一件
DEDUP = re.compile(
    r"(allies\s+for\s+world\s+peace|adult\s+education\s+week|"
    r"alphabetically|am\s+i\s+proud|build\s+for\s+the\s+future|"
    r"big\s+things\s+from\s+little|america\s+has\s+plenty|"
    r"have\s+you\s+really\s+tried|wählt\s+sozialdemokratisch|"
    r"kehrt\s+aus|kärntner\s+volksabstimmung|"
    r"das\s+dritte\s+reich)", re.I)

#: 逐条复核后剔除：非宣传品实体
#:   Carte des corps de volontaires —— 1830 年志愿军团分布地图，不是海报
#:   Uchwala KPRP (HistoriaPolski str.137) —— 波兰史书第 137 页的书页扫描
#:   COLL MISC 0519 —— 档案编号，看不出内容，无法核验
#:   Venecia, varios (1984) 05 —— 1984 年威尼斯街头照片
#:   Koninklijk Paleis ... affiches —— 王宫前的海报张贴照，非海报本体
#:   Serie Portugal ... / Portugal, politiek ... —— 1975 年里斯本街头照片
EXCLUDE = re.compile(
    r"(carte\s+des\s+corps|historiapolski|coll\s+misc|"
    r"venecia,\s*varios|koninklijk\s+paleis|"
    r"serie\s+portugal|portugal,\s*politiek|"
    r"cnG\s+1932\s+posters)", re.I)


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


def safe(s, n=56):
    s = re.sub(r'[\\/:*?"<>|]+', "_", str(s))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def norm_title(name):
    """去扩展名、去掉常见的 (2)/(cropped)/HQ Ed 之类后缀。"""
    s = os.path.splitext(name)[0]
    s = re.sub(r"\s*\((?:\d+|cropped|smooth|HQ Ed|digitalised version)\)\s*$", "", s,
               flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", s.lower())[:34]


def main():
    dry = "--dry" in sys.argv
    cands = json.load(open(CAND, encoding="utf-8"))
    print(f"候选 {len(cands)} 件\n")

    # --- 同题材去重：保留面积最大的一件 ---
    groups, kept = {}, []
    for c in cands:
        if EXCLUDE.search(c["title"]):
            continue
        m = DEDUP.search(c["title"])
        if m:
            groups.setdefault(m.group(1).lower(), []).append(c)
        else:
            kept.append(c)
    for k, lst in groups.items():
        lst.sort(key=lambda x: x["width"] * x["height"], reverse=True)
        kept.append(lst[0])
        print(f"  去重 {k[:34]:34s} 保 1 弃 {len(lst) - 1}")
    cands = kept
    print(f"\n去重后 {len(cands)} 件")

    # --- 按国别配额挑选 ---
    from collections import Counter
    taken = Counter()
    chosen = []
    for c in cands:
        lim = QUOTA.get(c["country"], 2)
        if taken[c["country"]] >= lim:
            continue
        taken[c["country"]] += 1
        chosen.append(c)

    print(f"\n入选 {len(chosen)} 件：")
    for c in chosen:
        print(f"  {c['country']:5s} {c['year']} {c['width']:>5}x{c['height']:<5} "
              f"{c['title'][:58]}")

    if dry:
        return

    os.makedirs(RAW, exist_ok=True)
    from PIL import Image

    records = []
    for i, c in enumerate(chosen, 1):
        folder = os.path.join(RAW, f"{i:03d}")
        os.makedirs(folder, exist_ok=True)
        ext = os.path.splitext(c["url"].split("?")[0])[1].lower() or ".jpg"
        src = os.path.join(folder, f"orig{ext}")
        dest = os.path.join(folder, "p-00001.jpg")
        try:
            download(c["url"], src)
        except Exception as e:
            print(f"  下载失败 {c['title'][:44]}: {type(e).__name__}")
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
            os.remove(src)
        except Exception as e:
            print(f"  处理失败 {c['title'][:44]}: {type(e).__name__}")
            continue

        c["no"] = i
        c["file"] = "p-00001.jpg"
        c["orig_size"] = [w0, h0]
        records.append(c)
        sz = os.path.getsize(dest) / 1024
        print(f"  {c['country']:5s} {c['year']} {w0}x{h0} -> {sz:.0f}KB "
              f"{c['title'][:44]}", flush=True)
        time.sleep(0.5)

    json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    total = sum(os.path.getsize(os.path.join(RAW, f"{r['no']:03d}", "p-00001.jpg"))
                for r in records)
    print(f"\n=== 采到 {len(records)} 件，合计 {total / 1048576:.1f} MB ===")
    for k, v in Counter(r["country"] for r in records).most_common():
        print(f"   {k:5s} {v}")


if __name__ == "__main__":
    main()
