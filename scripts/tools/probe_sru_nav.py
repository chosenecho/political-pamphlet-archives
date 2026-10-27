"""改用导航方式取 Gallica SRU（fetch 被 Cloudflare 拦，导航可过）。"""

import urllib.parse

from lxml import etree
from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"
NS = {"srw": "http://www.loc.gov/zing/srw/",
      "oai": "http://www.openarchives.org/OAI/2.0/oai_dc/",
      "dc": "http://purl.org/dc/elements/1.1/"}

QS = [
    'dc.subject all "communisme"',
    'dc.subject all "propagande" and dc.date all "1940"',
]

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.new_page()

    for q in QS:
        url = ("https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query="
               + urllib.parse.quote(q) + "&maximumRecords=5")
        try:
            r = page.goto(url, wait_until="commit", timeout=60000)
            body = r.body() if r else b""
            print(f"\n[{q}]  status={r.status if r else '?'}  bytes={len(body)}")
            head = body[:120].decode("utf-8", "replace").replace("\n", " ")
            print("   head:", head)
            if b"searchRetrieveResponse" in body:
                root = etree.fromstring(body)
                total = root.findtext(".//srw:numberOfRecords", namespaces=NS)
                recs = root.findall(".//srw:record", namespaces=NS)
                print("   命中:", total, "记录:", len(recs))
                for rec in recs[:2]:
                    dc = rec.find(".//oai:dc", namespaces=NS)
                    if dc is not None:
                        print("     -", (dc.findtext("dc:title", namespaces=NS) or "")[:60])
        except Exception as e:
            print(f"[{q}] ERR {type(e).__name__} {str(e)[:80]}")
    page.close()
