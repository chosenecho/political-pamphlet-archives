"""解析 Gallica SRU 返回，确认命中数与 ark 字段。"""

import json
import re

from lxml import etree
from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"
NS = {"srw": "http://www.loc.gov/zing/srw/",
      "oai": "http://www.openarchives.org/OAI/2.0/oai_dc/",
      "dc": "http://purl.org/dc/elements/1.1/"}

QUERIES = [
    ('dc.type all "tract"', 5),
    ('dc.type all "brochure" and dc.subject all "politique"', 5),
    ('dc.title all "élections" and dc.date all "1936"', 5),
    ('dc.subject all "propagande" and dc.date all "1940"', 5),
]


def sru(page, query, n):
    url = ("https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query="
           + __import__("urllib.parse", fromlist=["quote"]).quote(query)
           + f"&maximumRecords={n}")
    return page.evaluate("""async (u) => {
        const r = await fetch(u, {credentials:'include'});
        return await r.text();
    }""", url)


with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    if "gallica.bnf.fr" not in page.url:
        page.goto("https://gallica.bnf.fr/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

    for q, n in QUERIES:
        xml = sru(page, q, n)
        root = etree.fromstring(xml.encode("utf-8"))
        total = root.findtext(".//srw:numberOfRecords", namespaces=NS)
        recs = root.findall(".//srw:record", namespaces=NS)
        print(f"\n[{q}]  total={total}  records={len(recs)}")
        for rec in recs[:3]:
            dc = rec.find(".//oai:dc", namespaces=NS)
            if dc is None:
                continue
            title = (dc.findtext("dc:title", namespaces=NS) or "").strip()
            ident = [i.text.strip() for i in dc.findall("dc:identifier", namespaces=NS) if i.text]
            date = dc.findtext("dc:date", namespaces=NS) or ""
            typ = [t.text.strip() for t in dc.findall("dc:type", namespaces=NS) if t.text]
            print("   ", title[:58])
            print("     date:", date, "| type:", typ[:2])
            print("     ids :", ident[:3])
