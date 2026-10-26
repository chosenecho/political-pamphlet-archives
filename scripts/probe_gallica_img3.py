"""用导航与带 Referer 的请求，测试 Gallica 图片/PDF 的可取性。"""

from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"
ARK = "bpt6k320440p"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://gallica.bnf.fr/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)

    tests = [
        ("iiif 1000", f"https://gallica.bnf.fr/iiif/ark:/12148/{ARK}/f1/full/1000,/0/native.jpg"),
        ("iiif default", f"https://gallica.bnf.fr/iiif/ark:/12148/{ARK}/f1/full/1000,/0/default.jpg"),
        ("pdf", f"https://gallica.bnf.fr/ark:/12148/{ARK}.pdf"),
        ("texte", f"https://gallica.bnf.fr/ark:/12148/{ARK}.texteBrut"),
    ]
    for name, url in tests:
        try:
            r = page.request.get(url, headers={"Referer": "https://gallica.bnf.fr/"})
            print(f"{name:14s} {r.status}  {r.headers.get('content-type','')[:40]:40s} {len(r.body())/1024:.0f} KB")
        except Exception as e:
            print(f"{name:14s} ERR {type(e).__name__} {str(e)[:70]}")

    print("\n导航方式：")
    for name, url in tests[:3]:
        try:
            r = page.goto(url, wait_until="commit", timeout=45000)
            print(f"{name:14s} nav status={r.status if r else None}  ct={r.headers.get('content-type','')[:40] if r else ''}")
        except Exception as e:
            print(f"{name:14s} nav ERR {type(e).__name__} {str(e)[:60]}")
    page.goto("https://gallica.bnf.fr/", wait_until="domcontentloaded", timeout=60000)
