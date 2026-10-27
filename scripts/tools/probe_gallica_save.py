"""用导航取 Gallica 页图并落盘，验证字节有效。"""

import os

from PIL import Image
from playwright.sync_api import sync_playwright

ENDPOINT = "http://127.0.0.1:9333"
ARK = "bpt6k320440p"
OUT = os.path.join("images", "_gallica_test")
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ENDPOINT)
    ctx = b.contexts[0]
    page = ctx.new_page()

    for n in (1, 2, 3):
        url = f"https://gallica.bnf.fr/iiif/ark:/12148/{ARK}/f{n}/full/1000,/0/native.jpg"
        path = os.path.join(OUT, f"p-{n:05d}.jpg")
        try:
            resp = page.goto(url, wait_until="commit", timeout=60000)
            data = resp.body() if resp else b""
            open(path, "wb").write(data)
            im = Image.open(path)
            print(f"p{n}: status={resp.status if resp else None} bytes={len(data)} 尺寸={im.size} 格式={im.format}")
        except Exception as e:
            print(f"p{n}: ERR {type(e).__name__} {str(e)[:90]}")
    page.close()
