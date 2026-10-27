"""探查捷克 Kramerius API 与 IIIF。"""

from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"

CANDS = [
    "https://api.digitalniknihovna.cz/search/api/client/v7.0/search?q=bro%C5%BEura&rows=3",
    "https://api.digitalniknihovna.cz/search/api/client/v7.0/search?q=bro%C5%BEura&rows=3&fl=pid,title",
    "https://www.digitalniknihovna.cz/search/api/client/v7.0/search?q=bro%C5%BEura&rows=3",
    "https://api.kramerius.nkp.cz/search/api/client/v7.0/search?q=bro%C5%BEura&rows=3",
]

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.new_page()
    page.goto("https://www.digitalniknihovna.cz/nkp", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    print("页面:", page.url[:80])

    for u in CANDS:
        r = page.evaluate("""async (u) => {
            try {
                const r = await fetch(u, {credentials:'include'});
                const t = await r.text();
                return {s: r.status, len: t.length, head: t.slice(0,150)};
            } catch (e) { return {s:-1, err:String(e)}; }
        }""", u)
        print(f"\n{u[:78]}")
        print("  ", r)

    # 试 IIIF manifest（Kramerius v7: /search/api/client/v7.0/... 之外，iiif 在 /search/iiif/）
    print("\n== 页面内搜索框结构 ==")
    html = page.evaluate("() => document.body.innerText.slice(0, 400)")
    print(html.replace("\n", " | ")[:350])
    page.close()
