"""Gallica 按政治立场分路采集：左翼、右翼、天主教、自由主义、女权、和平主义等。"""

import json
import os
import re
import time
import urllib.parse

from lxml import etree
from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "images", "gallica2")
RAW = os.path.join(ROOT, "raw")
os.makedirs(RAW, exist_ok=True)

MINP, MAXP = 5, 64
CAP = 30
NS = {"srw": "http://www.loc.gov/zing/srw/",
      "oai": "http://www.openarchives.org/OAI/2.0/oai_dc/",
      "dc": "http://purl.org/dc/elements/1.1/"}

# (检索式, 立场标签) —— 刻意覆盖对立阵营
#: 标签必须是 scripts/lib/vocab.py 里登记过的值，否则 merge_gallica.py 写入
#: 目录时会被 catalog.save() 的校验拦下。原先这里写 `"行动法兰西"`，与目录里
#: 已有的 `"极右·行动法兰西"` 是同一概念的两种写法，收成后者。
QUERIES = [
    ('dc.subject all "communisme" and dc.date all "1925"', "共产主义"),
    ('dc.subject all "socialisme" and dc.date all "1910"', "社会主义"),
    ('dc.subject all "anarchisme"', "无政府主义"),
    ('dc.subject all "syndicalisme" and dc.date all "1910"', "工团主义"),
    ('dc.subject all "nationalisme" and dc.date all "1910"', "民族主义"),
    ('dc.subject all "royalisme"', "保皇派"),
    ('dc.subject all "Action française"', "极右·行动法兰西"),
    ('dc.subject all "catholicisme" and dc.date all "1905"', "天主教"),
    ('dc.subject all "libéralisme" and dc.date all "1900"', "自由主义"),
    ('dc.subject all "radicalisme" and dc.date all "1905"', "激进派"),
    ('dc.subject all "féminisme"', "女权"),
    ('dc.subject all "pacifisme" and dc.date all "1920"', "和平主义"),
    ('dc.subject all "colonialisme"', "殖民主义"),
    ('dc.subject all "antiparlementarisme"', "反议会"),
    ('dc.subject all "boulangisme"', "布朗热主义"),
    ('dc.subject all "dreyfus" and dc.date all "1898"', "德雷福斯事件"),
]


def sru(page, query, n=25, retries=3):
    """SRU 走导航（fetch 会被 Cloudflare 403）。"""
    url = ("https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query="
           + urllib.parse.quote(query) + f"&maximumRecords={n}")
    for i in range(retries):
        try:
            r = page.goto(url, wait_until="commit", timeout=60000)
            body = r.body() if r else b""
            if body and b"searchRetrieveResponse" in body:
                return body.decode("utf-8", "replace")
        except Exception:
            pass
        time.sleep(3 * (i + 1))
    return ""


def manifest_pages(page, ark, retries=3):
    url = f"https://gallica.bnf.fr/iiif/ark:/12148/{ark}/manifest.json"
    for i in range(retries):
        try:
            r = page.goto(url, wait_until="commit", timeout=60000)
            body = r.body() if r else b""
            txt = body.decode("utf-8", "replace")
            if txt.strip().startswith("{"):
                man = json.loads(txt)
                seqs = man.get("sequences") or []
                if seqs:
                    return len(seqs[0].get("canvases") or [])
        except Exception:
            pass
        time.sleep(2 * (i + 1))
    return 0


def grab(page, ark, n, path, retries=3):
    url = f"https://gallica.bnf.fr/iiif/ark:/12148/{ark}/f{n}/full/1000,/0/native.jpg"
    for i in range(retries):
        try:
            resp = page.goto(url, wait_until="commit", timeout=60000)
            data = resp.body() if resp else b""
            if data[:2] == b"\xff\xd8" and len(data) > 8000:
                open(path, "wb").write(data)
                return len(data)
        except Exception:
            pass
        time.sleep(1.2 + i)
    return 0


records, seen = [], set()

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.new_page()
    page.goto("https://gallica.bnf.fr/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)

    for q, label in QUERIES:
        if len(records) >= CAP:
            break
        xml = sru(page, q)
        if not xml:
            print(f"[{label}] SRU 空", flush=True)
            continue
        root = etree.fromstring(xml.encode("utf-8"))
        recs = root.findall(".//srw:record", namespaces=NS)
        print(f"[{label}] {len(recs)} 条", flush=True)

        for rec in recs:
            if len(records) >= CAP:
                break
            dc = rec.find(".//oai:dc", namespaces=NS)
            if dc is None:
                continue
            title = (dc.findtext("dc:title", namespaces=NS) or "").strip()
            ark = None
            for i in dc.findall("dc:identifier", namespaces=NS):
                m = re.search(r"ark:/12148/([a-z0-9]+)", i.text or "")
                if m:
                    ark = m.group(1)
                    break
            if not ark or ark in seen:
                continue
            typ = " ".join(t.text for t in dc.findall("dc:type", namespaces=NS) if t.text)
            if "image fixe" in typ:
                continue

            pages = manifest_pages(page, ark)
            if not (MINP <= pages <= MAXP):
                continue

            seen.add(ark)
            n = len(records) + 1
            folder = os.path.join(RAW, f"{n:03d}")
            os.makedirs(os.path.join(folder, "pages"), exist_ok=True)
            ok = 0
            for i in range(1, pages + 1):
                if grab(page, ark, i, os.path.join(folder, "pages", f"p-{i:05d}.jpg")):
                    ok += 1
                time.sleep(0.35)

            date = dc.findtext("dc:date", namespaces=NS) or ""
            ym = re.search(r"(1[89]\d{2}|19\d{2})", date)
            record = {"no": n, "ark": ark, "title": title, "stance": label,
                      "year": ym.group(1) if ym else "", "pages": pages, "pages_got": ok,
                      "url": f"https://gallica.bnf.fr/ark:/12148/{ark}"}
            records.append(record)
            print(f"  {n:02d} [{label}] {record['year']} {pages:2d}p 取{ok:2d}  {title[:42]}", flush=True)
            time.sleep(0.6)

    page.close()

json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
from collections import Counter
print(f"\n=== 共 {len(records)} 本 ===", flush=True)
for k, v in Counter(r["stance"] for r in records).most_common():
    print(f"   {k:8s} {v}", flush=True)
