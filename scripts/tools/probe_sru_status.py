"""诊断 Gallica SRU 返回状态。"""

import urllib.parse

from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"

QS = [
    'dc.subject all "communisme"',
    'dc.subject all "propagande" and dc.date all "1940"',
    'dc.subject all "socialisme"',
    'gallica all "communisme"',
    'dc.title all "socialisme"',
]

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.new_page()
    page.goto("https://gallica.bnf.fr/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    print("page:", page.url[:60])

    for q in QS:
        url = ("https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query="
               + urllib.parse.quote(q) + "&maximumRecords=3")
        res = page.evaluate("""async (u) => {
            try {
                const r = await fetch(u, {credentials:'include'});
                const t = await r.text();
                return {status: r.status, len: t.length, head: t.slice(0, 200)};
            } catch (e) { return {status: -1, len: 0, head: String(e)}; }
        }""", url)
        print(f"\n[{q}]")
        print(f"   status={res['status']} len={res['len']}")
        print(f"   {res['head'][:170]}".replace("\n", " "))
    page.close()
