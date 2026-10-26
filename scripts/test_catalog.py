"""用 Chromium 实测目录页：点开条目、翻页、搜索是否可用。"""

import json
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
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)

    pg.goto(HTML, wait_until="load")
    pg.wait_for_timeout(800)

    cards = pg.locator(".c")
    print("卡片数:", cards.count())

    # 找第一张多页条目（中国）
    idx = pg.evaluate("() => D.findIndex(d => d.n > 1)")
    print("首个多页条目 index:", idx, "页数:", pg.evaluate(f"() => D[{idx}].n"))

    pg.locator(f'.c[data-i="{idx}"]').click()
    pg.wait_for_timeout(600)
    print("阅读器打开:", pg.locator("#v.on").count() == 1)

    src0 = pg.eval_on_selector("#v img", "e => e.getAttribute('src')")
    txt0 = pg.inner_text("#cnt")
    print("第 1 页 src:", src0)
    print("计数:", txt0)

    # 键盘翻页
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(500)
    src1 = pg.eval_on_selector("#v img", "e => e.getAttribute('src')")
    print("右箭头后:", src1, "|", pg.inner_text("#cnt"), "| 变化:", src0 != src1)

    # 点击右侧热区
    pg.mouse.click(1400, 500)
    pg.wait_for_timeout(500)
    print("点右侧后:", pg.eval_on_selector("#v img", "e => e.getAttribute('src')"), "|", pg.inner_text("#cnt"))

    # 图片是否真的加载出来
    nat = pg.eval_on_selector("#v img", "e => [e.naturalWidth, e.naturalHeight]")
    print("图片实际尺寸:", nat)
    complete = pg.eval_on_selector("#v img", "e => e.complete && e.naturalWidth > 0")
    print("图片加载成功:", complete)

    # 上一页
    pg.locator('#foot button[data-step="-1"]').click()
    pg.wait_for_timeout(400)
    print("上一页后:", pg.inner_text("#cnt"))

    # Esc 关闭
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    print("已关闭:", pg.locator("#v.on").count() == 0)

    # 搜索
    pg.fill("#q", "德国")
    pg.wait_for_timeout(400)
    vis = pg.evaluate("() => Array.from(document.querySelectorAll('.c')).filter(c=>c.style.display!=='none').length")
    print("搜索『德国』可见卡片:", vis)

    print("JS 错误:", errs if errs else "无")
    b.close()
