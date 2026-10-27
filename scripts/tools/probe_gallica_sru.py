"""在 Gallica 页面上下文中调用 SRU，验证能否结构化取条目。"""

import json
import sys

from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"

JS = """
async (args) => {
  const url = args.url;
  const r = await fetch(url, {credentials: 'include'});
  const text = await r.text();
  return {status: r.status, len: text.length, head: text.slice(0, 600)};
}
"""

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    if "gallica.bnf.fr" not in page.url:
        page.goto("https://gallica.bnf.fr/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

    queries = [
        ("tracts ww2", 'https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query=dc.type%20all%20%22tract%22&maximumRecords=5'),
        ("brochure politique", 'https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query=dc.subject%20all%20%22politique%22%20and%20dc.type%20all%20%22brochure%22&maximumRecords=5'),
    ]
    for name, url in queries:
        try:
            res = page.evaluate(JS, {"url": url})
            print("==", name)
            print("  status:", res["status"], "len:", res["len"])
            print("  head:", res["head"][:400].replace("\n", " "))
        except Exception as e:
            print("==", name, "ERR", type(e).__name__, str(e)[:120])
