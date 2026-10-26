"""Gallica 采集：SRU 检索 → IIIF 清单取页数 → 导航下载页图。

依赖一个开着远程调试的 Chrome（默认 9333），由 connect_over_cdp 接管。
"""

import json
import os
import re
import time
import urllib.parse

from lxml import etree
from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "images", "gallica")
RAW = os.path.join(ROOT, "raw")
os.makedirs(RAW, exist_ok=True)

MINP, MAXP = 5, 64
CAP = 26
NS = {"srw": "http://www.loc.gov/zing/srw/",
      "oai": "http://www.openarchives.org/OAI/2.0/oai_dc/",
      "dc": "http://purl.org/dc/elements/1.1/"}

QUERIES = [
    'dc.subject all "propagande" and dc.date all "1940"',
    'dc.subject all "propagande" and dc.date all "1918"',
    'dc.title all "élections" and dc.date all "1936"',
    'dc.title all "élections" and dc.date all "1928"',
    'dc.subject all "socialisme" and dc.date all "1920"',
    'dc.subject all "communisme" and dc.date all "1930"',
    'dc.subject all "guerre" and dc.date all "1916"',
    'dc.title all "tract" and dc.date all "1944"',
]


def sru(page, query, n=30):
    url = ("https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query="
           + urllib.parse.quote(query) + f"&maximumRecords={n}")
    res = page.evaluate("""async (u) => {
        try {
            const r = await fetch(u, {credentials:'include'});
            const t = await r.text();
            return {status: r.status, len: t.length, text: r.ok ? t : ''};
        } catch (e) { return {status: -1, len: 0, text: '', err: String(e)}; }
    }""", url)
    if not res.get("text"):
        print(f"    SRU 失败 status={res.get('status')} len={res.get('len')} {res.get('err','')}", flush=True)
    return res.get("text") or ""


def manifest_pages(page, ark, retries=3):
    url = f"https://gallica.bnf.fr/iiif/ark:/12148/{ark}/manifest.json"
    for i in range(retries):
        try:
            txt = page.evaluate("""async (u) => {
                const r = await fetch(u, {credentials:'include'});
                return r.ok ? await r.text() : '';
            }""", url)
            if txt and txt.strip().startswith("{"):
                man = json.loads(txt)
                seqs = man.get("sequences") or []
                if seqs:
                    return len(seqs[0].get("canvases") or []), man
        except Exception:
            pass
        time.sleep(2 + i)
    return 0, None


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
        time.sleep(1.5 + i)
    return 0


records, seen = [], set()

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.new_page()
    # 无条件先进入 Gallica，保证后续 fetch 同为同源请求
    page.goto("https://gallica.bnf.fr/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    print("当前页面:", page.url[:60], flush=True)

    for q in QUERIES:
        if len(records) >= CAP:
            break
        xml = sru(page, q)
        if not xml:
            print(f"SRU 空: {q}", flush=True)
            continue
        root = etree.fromstring(xml.encode("utf-8"))
        recs = root.findall(".//srw:record", namespaces=NS)
        print(f"[{q[:44]}] {len(recs)} 条", flush=True)

        for rec in recs:
            if len(records) >= CAP:
                break
            dc = rec.find(".//oai:dc", namespaces=NS)
            if dc is None:
                continue
            title = (dc.findtext("dc:title", namespaces=NS) or "").strip()
            ids = [i.text.strip() for i in dc.findall("dc:identifier", namespaces=NS) if i.text]
            ark = None
            for i in ids:
                m = re.search(r"ark:/12148/([a-z0-9]+)", i)
                if m:
                    ark = m.group(1)
                    break
            if not ark or ark in seen:
                continue
            typ = " ".join(t.text for t in dc.findall("dc:type", namespaces=NS) if t.text)
            if "image fixe" in typ:
                continue

            pages, man = manifest_pages(page, ark)
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
                time.sleep(0.4)

            date = dc.findtext("dc:date", namespaces=NS) or ""
            ym = re.search(r"(1[89]\d{2}|19\d{2})", date)
            rec = {"no": n, "ark": ark, "title": title,
                   "year": ym.group(1) if ym else "",
                   "pages": pages, "pages_got": ok,
                   "url": f"https://gallica.bnf.fr/ark:/12148/{ark}",
                   "type": typ[:60],
                   "publisher": dc.findtext("dc:publisher", namespaces=NS) or ""}
            records.append(rec)
            print(f"  {n:02d} {rec['year']} {pages:2d}p 取{ok:2d}  {title[:48]}", flush=True)
            time.sleep(0.8)

    page.close()

json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"\n=== 共 {len(records)} 本 ===", flush=True)
