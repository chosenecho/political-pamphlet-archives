"""给目录页与阅读器截图，用于目视检查。

用法
    python scripts/shot_ui.py            # 全量截图到 images/_ui/
    python scripts/shot_ui.py --dark     # 同时出暗色版

图片不入库；本脚本只读 docs/index.html，不参与构建。
"""

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import paths

URL = pathlib.Path(paths.SITE).as_uri()
OUT = os.path.join(paths.IMAGES, "_ui")
DARK = "--dark" in sys.argv


def shot(pg, name):
    pg.screenshot(path=os.path.join(OUT, name))
    print("  ", name)


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 940}, device_scale_factor=2)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console." + m.type + ": " + m.text)
              if m.type == "error" else None)

        pg.goto(URL, wait_until="load")
        pg.wait_for_timeout(1600)
        shot(pg, "1-catalog.png")

        # 列表视图
        pg.click('#views button[data-view="list"]')
        pg.wait_for_timeout(500)
        shot(pg, "2-list.png")
        pg.click('#views button[data-view="grid"]')
        pg.wait_for_timeout(300)

        # 筛选：纳粹主义（三本，德国）
        pg.click('#rail .fopt[data-v="纳粹主义"]')
        pg.wait_for_timeout(600)
        shot(pg, "3-filter.png")
        pg.click('#rail .fopt[data-v="纳粹主义"]')
        pg.wait_for_timeout(300)

        # 年代区间：1930s + 1940s
        pg.click('#histBars button[data-dec="1930"]')
        pg.keyboard.down("Shift")
        pg.click('#histBars button[data-dec="1940"]')
        pg.keyboard.up("Shift")
        pg.wait_for_timeout(600)
        shot(pg, "4-decade.png")
        pg.click('#histBars button[data-dec="1930"]')
        pg.click('#histBars button[data-dec="1940"]')
        pg.wait_for_timeout(300)

        # 搜索
        pg.fill("#q", "克鲁泡特金")
        pg.wait_for_timeout(500)
        shot(pg, "5-search.png")
        pg.fill("#q", "")
        pg.wait_for_timeout(400)

        # 阅读器
        pg.locator(".card").first.click()
        pg.wait_for_timeout(1400)
        shot(pg, "6-reader.png")

        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(900)
        shot(pg, "7-reader-p2.png")

        # 双页
        pg.click('#rdModes button[data-mode="spread"]')
        pg.wait_for_timeout(900)
        shot(pg, "8-reader-spread.png")

        # 连续
        pg.click('#rdModes button[data-mode="scroll"]')
        pg.wait_for_timeout(1400)
        shot(pg, "9-reader-scroll.png")
        pg.click('#rdModes button[data-mode="page"]')
        pg.wait_for_timeout(400)

        # 信息栏收起
        pg.click("#rdInfo")
        pg.wait_for_timeout(500)
        shot(pg, "10-reader-noside.png")
        pg.click("#rdInfo")
        pg.wait_for_timeout(300)

        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)
        ctx.close()

        # 暗色
        if DARK:
            ctx2 = b.new_context(viewport={"width": 1440, "height": 940},
                                 device_scale_factor=2, color_scheme="dark")
            pg2 = ctx2.new_page()
            pg2.on("pageerror", lambda e: errs.append("dark: " + str(e)))
            pg2.goto(URL, wait_until="load")
            pg2.wait_for_timeout(1400)
            shot(pg2, "11-dark.png")
            pg2.locator(".card").first.click()
            pg2.wait_for_timeout(1200)
            shot(pg2, "12-dark-reader.png")
            ctx2.close()

        # 移动端
        m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3,
                          is_mobile=True, has_touch=True)
        mp = m.new_page()
        mp.on("pageerror", lambda e: errs.append("mobile: " + str(e)))
        mp.goto(URL, wait_until="load")
        mp.wait_for_timeout(1300)
        shot(mp, "13-mobile.png")
        mp.click("#fbtn")
        mp.wait_for_timeout(600)
        shot(mp, "14-mobile-rail.png")
        # 抽屉宽 310px，点它右侧的遮罩区域（点中心会落在抽屉上）
        mp.mouse.click(370, 500)
        mp.wait_for_timeout(500)
        mp.locator(".card").first.click()
        mp.wait_for_timeout(1200)
        shot(mp, "15-mobile-reader.png")
        m.close()

        b.close()

    if errs:
        print("\n[页面错误]")
        for e in errs[:20]:
            print("  ", e)
    else:
        print("\n无 JS 错误")

    print()
    for f in sorted(os.listdir(OUT)):
        print(f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")


if __name__ == "__main__":
    main()
