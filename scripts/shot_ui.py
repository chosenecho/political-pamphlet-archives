"""给目录页与阅读器截图，用于目视检查。"""

import os
import pathlib

from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = pathlib.Path(os.path.join(BASE, "images", "目录.html")).as_uri()
OUT = os.path.join(BASE, "images", "_ui")

os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)

    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(URL, wait_until="load")
    pg.wait_for_timeout(1200)
    pg.screenshot(path=os.path.join(OUT, "1-grid.png"))

    pg.select_option("#fs", "纳粹主义")
    pg.wait_for_timeout(500)
    pg.screenshot(path=os.path.join(OUT, "2-filter.png"))

    pg.select_option("#fs", "")
    pg.wait_for_timeout(300)
    pg.locator(".card").first.click()
    pg.wait_for_timeout(1200)
    pg.screenshot(path=os.path.join(OUT, "3-reader.png"))

    pg.keyboard.press("End")
    pg.wait_for_timeout(700)
    pg.screenshot(path=os.path.join(OUT, "4-reader-last.png"))

    pg.close()

    m = b.new_page(viewport={"width": 390, "height": 844})
    m.goto(URL, wait_until="load")
    m.wait_for_timeout(1000)
    m.screenshot(path=os.path.join(OUT, "5-mobile.png"))
    m.close()

    b.close()

for f in sorted(os.listdir(OUT)):
    print(f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")
