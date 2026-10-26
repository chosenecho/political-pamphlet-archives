"""连接专用 Chrome（9333），测试 Gallica / Hoover 是否已过 Cloudflare。"""

import sys

from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"

with sync_playwright() as p:
    try:
        browser = p.chromium.connect_over_cdp(ENDPOINT)
    except Exception as e:
        print("CONNECT-FAIL", type(e).__name__, str(e)[:200])
        sys.exit(1)

    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    print("已连接，页面数:", len(ctx.pages))

    page = ctx.new_page()
    targets = [
        ("Gallica tracts", "https://gallica.bnf.fr/accueil/fr/html/les-tracts-de-la-seconde-guerre-mondiale-a-la-reserve-des-livres-rares"),
        ("Hoover posters", "https://www.hoover.org/library-archives/collections/posters"),
        ("Hoover digital", "https://digitalcollections.hoover.org/objects/310/poster-collection"),
    ]
    for name, url in targets:
        try:
            r = page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            t = page.title()
            body = page.inner_text("body")
            print("")
            print(name)
            print("  status=", (r.status if r else None), " title=", t[:70])
            print("  正文长度=", len(body), " 首段=", body[:100].replace("\n", " "))
            print("  疑似拦截=", ("Just a moment" in t or len(body) < 400))
        except Exception as e:
            print("")
            print(name)
            print("  ERR", type(e).__name__, str(e)[:120])
    page.close()
