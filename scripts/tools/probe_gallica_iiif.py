"""测试 Gallica IIIF 清单与页图下载（经浏览器会话）。"""

import json

from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"
ARK = "bpt6k320440p"   # 1936 选举结果册

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    if "gallica.bnf.fr" not in page.url:
        page.goto("https://gallica.bnf.fr/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)

    murl = f"https://gallica.bnf.fr/iiif/ark:/12148/{ARK}/manifest.json"
    res = page.evaluate("""async (u) => {
        const r = await fetch(u, {credentials:'include'});
        const t = await r.text();
        return {status: r.status, len: t.length, head: t.slice(0, 300)};
    }""", murl)
    print("manifest status:", res["status"], "len:", res["len"])
    print("head:", res["head"][:200].replace("\n", " "))

    if res["status"] == 200:
        manifest = json.loads(page.evaluate("""async (u) => {
            const r = await fetch(u, {credentials:'include'});
            return await r.text();
        }""", murl))
        canv = manifest.get("sequences", [{}])[0].get("canvases", [])
        print("canvases:", len(canv))
        if canv:
            print("label:", canv[0].get("label"))
            img = canv[0].get("images", [{}])[0]
            print("image res:", json.dumps(img, ensure_ascii=False)[:300])

    # 用 page.request 下页图（共享 cookie）
    pageurl = f"https://gallica.bnf.fr/iiif/ark:/12148/{ARK}/f1/full/1000,/0/native.jpg"
    try:
        resp = page.request.get(pageurl)
        body = resp.body()
        print("page1 status:", resp.status, "bytes:", len(body), "ct:", resp.headers.get("content-type"))
    except Exception as e:
        print("page1 ERR", type(e).__name__, str(e)[:100])
