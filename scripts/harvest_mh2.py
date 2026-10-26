"""抗战平台：只抓 1949 年前的原版小册子/传单封面。"""

import json
import os
import re
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
OUT = os.path.join(BASE, "images", "modernhistory")
if os.path.isdir(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT, exist_ok=True)

API = "https://www.modernhistory.org.cn/backend-prod/esBook/findByPage"

KEYWORDS = [
    ("传单", "ts"), ("宣言", "ts"), ("纲领", "ts"), ("标语", "ts"),
    ("布告", "ts"), ("宣传", "ts"), ("小册子", "ts"), ("告同胞", "ts"),
    ("抗日", "ts"), ("救亡", "ts"), ("民众动员", "ts"), ("妇女", "ts"),
    ("工人", "ts"), ("农民", "ts"), ("青年", "ts"), ("学生", "ts"),
    ("共产党", "ts"), ("国民党", "ts"), ("三民主义", "ts"), ("抗战建国", "ts"),
    ("木刻", "tp"), ("宣传画", "tp"), ("传单", "tp"),
]

TAG_RE = re.compile(r"<[^>]+>")
YEAR_RE = re.compile(r"(1[89]\d{2})")
PER_KEYWORD = 8


def clean(s):
    if isinstance(s, (list, tuple)):
        s = "；".join(clean(x) for x in s if x)
    if not isinstance(s, str):
        s = "" if s is None else str(s)
    return TAG_RE.sub("", s).strip()


def post_json(url, payload, timeout=60, retries=3):
    data = json.dumps(payload).encode()
    for attempt in range(retries):
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
            if attempt == retries - 1:
                raise
            time.sleep(2)


def search(keyword, doc_type, size=50, page=1):
    return post_json(API, {
        "secondKeyword": "", "currentPage": page, "docType": doc_type,
        "keyword": keyword, "pageSize": size, "firstFieldName": "",
        "secondFieldName": "", "secondFieldValue": "", "orderByDownload": "",
        "orderByGmtCreate": "", "orderByPublishTime": "",
    })


def download(url, path, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        data = r.read()
    if len(data) < 4000:
        raise ValueError(f"too small: {len(data)}")
    open(path, "wb").write(data)
    return len(data)


records, seen, n = [], set(), 0

for keyword, doc_type in KEYWORDS:
    try:
        res = search(keyword, doc_type).get("result", {})
    except Exception as e:
        print(f"SEARCH-ERR {keyword}: {type(e).__name__}")
        continue

    items = res.get("dataList") or []
    picked = 0
    for it in items:
        if picked >= PER_KEYWORD:
            break
        img = it.get("imageUrl")
        if not img or img in seen:
            continue
        ptime = str(it.get("publishTime") or "")
        m = YEAR_RE.search(ptime)
        year = int(m.group(1)) if m else None
        # 只要 1949 年（含）前的原版
        if year is None or year > 1949:
            continue
        seen.add(img)
        picked += 1
        n += 1

        title = clean(it.get("title")) or "untitled"
        safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", title)[:55]
        fname = f"{n:03d}_{year}_{safe}.jpg"
        path = os.path.join(OUT, fname)

        rec = {
            "no": n, "keyword": keyword, "doc_type": doc_type,
            "title": title, "year": year, "publish_time": ptime,
            "publisher": clean(it.get("publisher")),
            "responsible": clean(it.get("firstResponsible")),
            "pages": it.get("pageAmount") or "",
            "iiif": img, "file": fname,
            "detail_url": "https://www.modernhistory.org.cn/#/DocumentDetails_ts_da?fileCode=" + (it.get("fileCode") or ""),
        }
        try:
            rec["bytes"] = download(f"{img}/full/1000,/0/default.jpg", path)
            rec["ok"] = True
            print(f"  OK  {n:03d} {year} {rec['bytes']/1024:6.0f}KB  {title[:36]}")
        except Exception as e:
            rec["ok"] = False
            rec["error"] = f"{type(e).__name__}: {str(e)[:60]}"
            print(f"  ERR {n:03d} {year} {rec['error'][:36]}  {title[:28]}")
        records.append(rec)
        time.sleep(0.3)

    print(f"[{keyword}/{doc_type}] total={res.get('totalSize')} 采用={picked}")

json.dump(records, open(os.path.join(OUT, "metadata.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
ok = sum(1 for r in records if r.get("ok"))
print(f"\n=== 完成 {ok}/{len(records)}，均为 1949 年前版本 ===")
