"""经浏览器会话探测其他国家的数字图书馆可否访问。"""

import sys

from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"

SITES = [
    ("荷兰 Delpher", "https://www.delpher.nl/"),
    ("波兰 Polona", "https://polona.pl/"),
    ("捷克 Kramerius NKP", "https://www.digitalniknihovna.cz/nkp"),
    ("奥地利 ANNO", "https://anno.onb.ac.at/"),
    ("西班牙 BVPH", "https://www.bvpb.mecd.es/"),
    ("德国 BSB digi", "https://www.digitale-sammlungen.de/"),
    ("意大利 Internet Culturale", "https://www.internetculturale.it/"),
    ("瑞典 KB", "https://www.kb.se/"),
    ("丹麦 KB", "https://www.kb.dk/"),
    ("爱尔兰 DRI", "https://repository.dri.ie/"),
]

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.new_page()
    for name, url in SITES:
        try:
            r = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            body = page.inner_text("body")
            print(f"{name:22s} {r.status if r else '?':>4}  正文{len(body):>6}  {page.title()[:44]}")
        except Exception as e:
            print(f"{name:22s}  ERR  {type(e).__name__}: {str(e)[:60]}")
    page.close()
