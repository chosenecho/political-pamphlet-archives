"""测试经页面内 fetch 取页图（base64 回传）。"""

import base64
import json

from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"
ARK = "bpt6k320440p"

JS = """async (u) => {
  const r = await fetch(u, {credentials:'include'});
  if (!r.ok) return {status: r.status, b64: null};
  const buf = await r.arrayBuffer();
  let bin = '';
  const bytes = new Uint8Array(buf);
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return {status: r.status, b64: btoa(bin), len: bytes.length};
}"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    if "gallica.bnf.fr" not in page.url:
        page.goto("https://gallica.bnf.fr/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)

    for variant in [
        f"https://gallica.bnf.fr/iiif/ark:/12148/{ARK}/f1/full/1000,/0/native.jpg",
        f"https://gallica.bnf.fr/iiif/ark:/12148/{ARK}/f1/full/full/0/native.jpg",
        f"https://gallica.bnf.fr/ark:/12148/{ARK}/f1.highres",
    ]:
        res = page.evaluate(JS, variant)
        print(f"{res['status']}  len={res.get('len')}  {variant[-52:]}")
        if res.get("b64"):
            raw = base64.b64decode(res["b64"])
            head = raw[:4]
            print("   字节头:", head, "→", "JPEG" if head[:2] == b"\xff\xd8" else "非JPEG")
            break
