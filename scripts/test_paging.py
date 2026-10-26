"""实测小册子阅读器：整本翻页、跨本连续、PDF 链接、搜索。"""

import os
import pathlib

from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = pathlib.Path(os.path.join(BASE, "images", "目录.html")).as_uri()

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1500, "height": 950})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("requestfailed", lambda r: errs.append("404:" + r.url.split("/")[-1][:40])
          if r.url.split("?")[0].endswith(".jpg") else None)

    pg.goto(HTML, wait_until="load")
    pg.wait_for_timeout(700)

    print("卡片数:", pg.locator(".c").count())
    print("小册子:", pg.evaluate("() => BOOKS.length"))
    print("页数分布:", pg.evaluate("() => [Math.min(...BOOKS.map(b=>b.n)), Math.max(...BOOKS.map(b=>b.n))]"))

    first = pg.evaluate("() => BOOKS[0]")
    print(f"第一本: {first['c']} {first['y']} {first['t'][:30]} ({first['n']}p)")

    pg.locator(f'.c[data-i="{first["i"]}"]').click()
    pg.wait_for_timeout(500)
    print("  打开:", pg.inner_text("#cnt"), "| PDF 链接:", pg.get_attribute("#bar .pdf", "href"))

    for _ in range(first["n"] - 1):
        pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(300)
    print("  末页:", pg.inner_text("#cnt"))
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(500)
    nxt = pg.evaluate("() => ({c:cur.c, t:cur.t, i:cur.i})")
    print("  跨本后:", pg.inner_text("#cnt"), "| 是否第二本:", nxt["i"] == pg.evaluate("() => BOOKS[1].i"))

    pg.keyboard.press("ArrowLeft")
    pg.wait_for_timeout(400)
    print("  往回:", pg.inner_text("#cnt"), "| 回到第一本末页:", pg.evaluate("() => cur.i === BOOKS[0].i"))

    nat = pg.eval_on_selector("#v img", "e => [e.complete, e.naturalWidth]")
    print("  图片加载:", nat)

    pg.fill("#q", "美国")
    pg.wait_for_timeout(400)
    print("搜索美国可见:", pg.evaluate("() => Array.from(document.querySelectorAll('.c')).filter(c=>c.style.display!=='none').length"))

    print("错误:", sorted(set(errs))[:4] if errs else "无")
    b.close()
