"""全面实测目录页交互（计数从索引动态读取，避免硬编码过期）。"""

import json
import os
import pathlib

from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = pathlib.Path(os.path.join(BASE, "images", "目录.html")).as_uri()

IDX = json.load(open(os.path.join(BASE, "images", "索引.json"), encoding="utf-8"))
TOTAL = len(IDX)
NBOOK = sum(1 for r in IDX if r["kind"] == "小册子")
NSINGLE = TOTAL - NBOOK
NFR = sum(1 for r in IDX if r["country"] == "法国")

fails = []


def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + (("  " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1500, "height": 950})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    pg.goto(URL, wait_until="load")
    pg.wait_for_timeout(900)

    print(f"\n[初始渲染] 期望 {TOTAL} 条（小册子 {NBOOK} / 单页 {NSINGLE}）")
    check("卡片总数", pg.locator(".card").count() == TOTAL, pg.locator(".card").count())
    check("计数文本", f"{TOTAL} / {TOTAL}" in pg.inner_text("#count"), pg.inner_text("#count"))
    check("国别下拉有项", pg.locator("#fc option").count() > 5)
    check("立场下拉有项", pg.locator("#fs option").count() > 5)

    print("\n[筛选]")
    pg.select_option("#fc", "法国")
    pg.wait_for_timeout(350)
    check(f"筛法国 {NFR}", pg.locator(".card").count() == NFR, pg.locator(".card").count())
    pg.select_option("#fs", "社会主义")
    pg.wait_for_timeout(300)
    check("法国+社会主义", pg.locator(".card").count() == 0)
    pg.select_option("#fc", "")
    pg.wait_for_timeout(300)
    check("社会主义 3", pg.locator(".card").count() == 3, pg.locator(".card").count())

    print("\n[搜索]")
    pg.select_option("#fs", "")
    pg.fill("#q", "克鲁泡特金")
    pg.wait_for_timeout(400)
    check("中文搜索命中", pg.locator(".card").count() >= 2, pg.locator(".card").count())
    pg.fill("#q", "zzzznope")
    pg.wait_for_timeout(300)
    check("无结果提示", pg.locator(".empty").count() == 1)
    pg.fill("#q", "")
    pg.wait_for_timeout(300)

    print("\n[类型切换]")
    pg.click('#fk button[data-k="single"]')
    pg.wait_for_timeout(400)
    check(f"单页 {NSINGLE}", pg.locator(".card").count() == NSINGLE, pg.locator(".card").count())
    pg.click('#fk button[data-k="book"]')
    pg.wait_for_timeout(400)
    check(f"小册子 {NBOOK}", pg.locator(".card").count() == NBOOK, pg.locator(".card").count())

    print("\n[排序]")
    pg.select_option("#sort", "y-")
    pg.wait_for_timeout(400)
    d1 = pg.locator(".card .yr").first.inner_text()
    pg.select_option("#sort", "y+")
    pg.wait_for_timeout(400)
    d2 = pg.locator(".card .yr").first.inner_text()
    check("升降序不同", d1 != d2, f"{d1} vs {d2}")

    print("\n[URL 记忆]")
    pg.select_option("#sort", "i")
    pg.select_option("#fc", "德国")
    pg.fill("#q", "nazi")
    pg.wait_for_timeout(500)
    h = pg.evaluate("() => location.hash")
    check("hash 写入", "c=" in h, h)
    pg2 = b.new_page()
    pg2.goto(URL + h, wait_until="load")
    pg2.wait_for_timeout(700)
    check("重载保留国别", pg2.input_value("#fc") == "德国")
    check("重载保留搜索", pg2.input_value("#q") == "nazi")
    pg2.close()

    print("\n[重置]")
    pg.click("#reset")
    pg.wait_for_timeout(400)
    check("重置回全量", pg.locator(".card").count() == TOTAL, pg.locator(".card").count())

    print("\n[阅读器]")
    pg.locator(".card").first.click()
    pg.wait_for_timeout(700)
    check("打开", pg.locator("#viewer.on").count() == 1)
    info = pg.evaluate("() => ({cnt: document.getElementById('cnt').textContent, n: visible[vi].n})")
    check("页码", "/" in info["cnt"] or info["cnt"] == "单页", info["cnt"])
    check("图片加载", pg.eval_on_selector("#vimg", "e => e.complete && e.naturalWidth > 0"))
    if info["n"] > 1:
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(350)
        check("→ 翻页", pg.inner_text("#cnt").startswith("2"), pg.inner_text("#cnt"))
        pg.keyboard.press("End")
        pg.wait_for_timeout(350)
        check("End 末页", pg.inner_text("#cnt").startswith(str(info["n"])))
        pg.keyboard.press("Home")
        pg.wait_for_timeout(350)
        check("Home 首页", pg.inner_text("#cnt").startswith("1"))

    print("\n[缩放]")
    z0 = pg.inner_text("#zl")
    pg.click("#zin")
    pg.wait_for_timeout(250)
    check("放大", pg.inner_text("#zl") != z0, f"{z0}→{pg.inner_text('#zl')}")
    pg.click("#zfit")
    pg.wait_for_timeout(250)
    check("复位", pg.inner_text("#zl") == "100%")

    print("\n[换本/关闭]")
    v0 = pg.evaluate("() => vi")
    pg.click("#nextbook")
    pg.wait_for_timeout(400)
    check("下一本", pg.evaluate("() => vi") == v0 + 1)
    pg.click("#prevbook")
    pg.wait_for_timeout(400)
    check("上一本", pg.evaluate("() => vi") == v0)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    check("Esc 关闭", pg.locator("#viewer.on").count() == 0)

    print("\n[移动端]")
    m = b.new_page(viewport={"width": 390, "height": 844})
    m.goto(URL, wait_until="load")
    m.wait_for_timeout(800)
    check("移动端卡片", m.locator(".card").count() == TOTAL, m.locator(".card").count())
    m.locator(".card").first.click()
    m.wait_for_timeout(500)
    check("移动端阅读器", m.locator("#viewer.on").count() == 1)
    m.close()

    print("\n错误:", errs or "无")
    if errs:
        fails.append("JS 错误")
    b.close()

print("\n" + ("全部通过" if not fails else "失败：" + "、".join(fails)))
