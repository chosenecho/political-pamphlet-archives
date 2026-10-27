"""从 manifest 取真实 image service 基址，并试取第一页。"""

import base64
import json

from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"
ARK = "bpt6k320440p"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    if "gallica.bnf.fr" not in page.url:
        page.goto("https://gallica.bnf.fr/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)

    murl = f"https://gallica.bnf.fr/iiif/ark:/12148/{ARK}/manifest.json"
    txt = page.evaluate("""async (u) => {
        const r = await fetch(u, {credentials:'include'});
        return await r.text();
    }""", murl)
    man = json.loads(txt)
    canv = man["sequences"][0]["canvases"]
    print("canvases:", len(canv))

    res0 = canv[0]["images"][0]["resource"]
    print("resource @id:", res0.get("@id"))
    svc = res0.get("service") or {}
    print("service @id:", svc.get("@id"))
    print("service keys:", sorted(svc.keys()))

    # 试几种尺寸参数
    sid = svc.get("@id") or res0.get("@id")
    cands = []
    if sid:
        for spec in ["full/1000,/0/default.jpg", "full/1000,/0/native.jpg",
                     "full/full/0/default.jpg", "full/max/0/default.jpg"]:
            cands.append(sid.rstrip("/") + "/" + spec)

    for u in cands:
        r = page.evaluate("""async (u) => {
            const r = await fetch(u, {credentials:'include'});
            const ct = r.headers.get('content-type') || '';
            if (!r.ok) return {status: r.status, ct, len: 0};
            const b = await r.arrayBuffer();
            return {status: r.status, ct, len: b.byteLength};
        }""", u)
        print(f"  {r['status']} {r.get('len')} {r.get('ct')[:24]:24s} {u[-56:]}")

    # 也试试页面里 img 的真实地址
    page.goto(f"https://gallica.bnf.fr/ark:/12148/{ARK}/f1.item", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    srcs = page.evaluate("""() => Array.from(document.images).map(i=>i.currentSrc||i.src).filter(s=>s.includes('iiif')||s.includes('image'))""")
    print("\n页面图片地址样本:", len(srcs))
    for s in srcs[:5]:
        print("   ", s[:120])
