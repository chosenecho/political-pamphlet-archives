"""专抓小册子：只收 ≤48 页的短篇，且整本下载（不再只取首尾页）。

输出：images/小册子/raw/<id>/{cover.jpg, pages/p-00001.jpg ...}
"""

import json
import os
import re
import ssl
import time
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "images", "小册子", "raw")
os.makedirs(OUT, exist_ok=True)

API = "https://www.modernhistory.org.cn/backend-prod/esBook/findByPage"

KEYWORDS = [
    "传单", "宣言", "纲领", "标语", "口号", "布告", "告同胞书", "告民众书",
    "小册子", "宣传", "救亡", "抗日", "抗战", "动员", "游击", "政治工作",
    "共产党", "国民党", "三民主义", "新民主主义", "土地改革", "农民",
    "工人", "青年", "学生", "妇女", "儿童", "歌谣", "木刻", "壁画",
    "陕甘宁", "晋察冀", "八路军", "新四军", "边区", "解放区",
    "二七", "五卅", "九一八", "七七", "双十", "总理遗嘱",
]

MAX_PAGES = 48      # 小册子上限
TARGET = 80         # 目标件数
TAG = re.compile(r"<[^>]+>")


def clean(s):
    if isinstance(s, (list, tuple)):
        s = "；".join(clean(x) for x in s if x)
    if not isinstance(s, str):
        s = "" if s is None else str(s)
    return TAG.sub("", s).strip()


def post_json(url, payload, timeout=60, retries=3):
    data = json.dumps(payload).encode()
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, method="POST", headers={
                "User-Agent": UA, "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.modernhistory.org.cn",
                "Referer": "https://www.modernhistory.org.cn/",
            })
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return json.loads(r.read())
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2)


def search(keyword, page=1, size=50):
    return post_json(API, {
        "secondKeyword": "", "currentPage": page, "docType": "ts",
        "keyword": keyword, "pageSize": size, "firstFieldName": "",
        "secondFieldName": "", "secondFieldValue": "", "orderByDownload": "",
        "orderByGmtCreate": "", "orderByPublishTime": "",
    })


def page_count(rec):
    m = re.search(r"(\d+)", str(rec.get("pageAmount") or ""))
    return int(m.group(1)) if m else 0


def year_of(rec):
    m = re.search(r"(1[89]\d{2}|19[0-4]\d)", str(rec.get("publishTime") or ""))
    return int(m.group(1)) if m else None


# ---------- 1. 收集候选 ----------
pool, seen = [], set()
for kw in KEYWORDS:
    try:
        for pg in (1, 2):
            res = search(kw, pg).get("result", {})
            items = res.get("dataList") or []
            if not items:
                break
            for it in items:
                img = it.get("imageUrl")
                pc = page_count(it)
                yr = year_of(it)
                if not img or img in seen or not yr or yr > 1949:
                    continue
                if not (1 <= pc <= MAX_PAGES):
                    continue
                seen.add(img)
                pool.append({
                    "iiif": img, "title": clean(it.get("title")),
                    "year": yr, "pages": pc,
                    "publisher": clean(it.get("publisher")),
                    "responsible": clean(it.get("firstResponsible")),
                    "file_code": it.get("fileCode") or "",
                    "keyword": kw,
                })
            time.sleep(0.4)
    except Exception as e:
        print(f"SEARCH-ERR {kw}: {type(e).__name__}", flush=True)
    print(f"  [{kw}] 累计候选 {len(pool)}", flush=True)

# 按页数升序优先（更像小册子），再按年份
pool.sort(key=lambda x: (x["pages"], x["year"]))
pool = pool[:TARGET]
print(f"\n选定 {len(pool)} 件，合计 {sum(p['pages'] for p in pool)} 页")

# ---------- 2. 整本下载 ----------
json.dump(pool, open(os.path.join(BASE, "images", "小册子", "候选.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)


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


def page_url(base, n):
    stem = base.rsplit("_", 1)[0]
    return f"{stem}_{n:05d}.jpg/full/1000,/0/default.jpg"


total_ok = 0
for idx, rec in enumerate(pool, 1):
    item_dir = os.path.join(OUT, f"{idx:03d}")
    pdir = os.path.join(item_dir, "pages")
    os.makedirs(pdir, exist_ok=True)
    rec["id"] = f"{idx:03d}"

    cover = os.path.join(item_dir, "cover.jpg")
    if not (os.path.exists(cover) and os.path.getsize(cover) > 3000):
        try:
            fetch(page_url(rec["iiif"], 1), cover)
        except Exception:
            pass

    got = 0
    for p in range(1, rec["pages"] + 1):
        fp = os.path.join(pdir, f"p-{p:05d}.jpg")
        if os.path.exists(fp) and os.path.getsize(fp) > 3000:
            got += 1
            continue
        try:
            fetch(page_url(rec["iiif"], p), fp)
            got += 1
        except Exception:
            pass
        time.sleep(0.12)
    rec["pages_got"] = got
    total_ok += got
    if idx % 10 == 0:
        print(f"  [{idx}/{len(pool)}] {rec['title'][:26]} {got}/{rec['pages']}p 累计 {total_ok}", flush=True)

json.dump(pool, open(os.path.join(BASE, "images", "小册子", "候选.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"\n=== 完成 {len(pool)} 件，{total_ok} 页 ===")
