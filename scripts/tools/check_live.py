"""线上地址冒烟：确认 GitHub Pages 上的真实表现（图像 404、目录仍可读）。

与 check_noimg.py 的区别：那个用本地文件 + 假 assets 路径，这个打真网址，
验证的是"部署后到底长什么样"，包括缓存与 CDN 行为。
"""

import sys

from playwright.sync_api import sync_playwright

URL = "https://chosenecho.github.io/political-pamphlet-archives/"
fails = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 940})
    errs = []
    bad = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("response", lambda r: bad.append(r.url) if r.status >= 400 else None)

    pg.goto(URL, wait_until="load", timeout=60000)
    pg.wait_for_timeout(2500)

    print("\n[线上目录]")
    n = pg.locator(".card").count()
    check("卡片渲染", n > 200, n)
    check("排版封面全出（线上无图是常态）", pg.locator(".card .plate").count() == n,
          pg.locator(".card .plate").count())
    check("无 JS 错误", not errs, errs[:2])

    # 图像 404 是预期的，但要确认没有别的东西 404
    non_img = [u for u in bad if not any(x in u.lower() for x in (".jpg", ".jpeg", ".png", ".webp"))]
    check("除图像外无 404", not non_img, non_img[:5])
    print(f"       图像 404 计 {len(bad) - len(non_img)} 个（预期；images/ 不入库）")

    print("\n[线上阅读器]")
    pg.locator(".card").first.click()
    pg.wait_for_timeout(2000)
    check("阅读器可打开", pg.locator("#rd.on").count() == 1)
    check("缺图有说明", pg.locator("#rdMiss.on").count() == 1)
    check("元数据完整", "国别" in pg.inner_text("#rdMeta"))
    check("缺图时仍可翻页", not pg.evaluate("() => document.getElementById('rdNextPage').disabled"))
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(600)
    check("翻页生效", pg.evaluate("() => rd.p") == 2, pg.evaluate("() => rd.p"))

    print("\n[线上筛选]")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(500)
    pg.click('#fCountry .fopt[data-v="中国"]')
    pg.wait_for_timeout(600)
    cn = pg.locator(".card").count()
    check("国别筛选可用", 0 < cn < n, cn)

    b.close()

print("\n" + ("线上全部通过" if not fails else "线上问题：" + "、".join(fails)))
sys.exit(1 if fails else 0)
