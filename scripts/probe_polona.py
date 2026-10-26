"""探查波兰 Polona 的检索与 IIIF 清单结构。"""

from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.new_page()

    print("== 检索页 ==")
    page.goto("https://polona.pl/search/?query=pamflet&categories=&hasFacets=false",
              wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    print("url:", page.url[:90])
    print("title:", page.title()[:60])
    links = page.evaluate("""() => Array.from(document.querySelectorAll('a[href*="/item/"]')).map(a=>a.href).slice(0,8)""")
    print("item 链接数:", len(links))
    for l in links[:5]:
        print("   ", l)

    if links:
        print("\n== 条目页 ==")
        page.goto(links[0], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        print("url:", page.url[:90])
        print("title:", page.title()[:70])
        info = page.evaluate("""() => {
            const out = {iiif: null, canvas: null, imgs: []};
            document.querySelectorAll('a,link').forEach(e => {
                const h = e.getAttribute('href') || '';
                if (h.includes('manifest')) out.iiif = out.iiif || h;
            });
            out.imgs = Array.from(document.images).map(i=>i.currentSrc||i.src)
                .filter(s=>s.includes('iiif')||s.includes('image')).slice(0,4);
            return out;
        }""")
        print("manifest:", info.get("iiif"))
        for s in info.get("imgs", [])[:4]:
            print("   img:", s[:120])

        # 试取 manifest
        mid = page.url.rstrip("/").split("/item/")[-1].split("/")[0]
        for cand in [f"https://polona.pl/iiif/{mid}/manifest.json",
                     f"https://polona.pl/item/{mid}/manifest.json"]:
            r = page.evaluate("""async (u) => {
                try { const r = await fetch(u); const t = await r.text();
                  return {s:r.status, len:t.length, head:t.slice(0,80)}; }
                catch(e){ return {s:-1, err:String(e)}; }
            }""", cand)
            print(f"   manifest试 {cand[-40:]} → {r}")
    page.close()
