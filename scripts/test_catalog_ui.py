"""全面实测目录页交互。"""

import os
import pathlib

from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = pathlib.Path(os.path.join(BASE, "images", "目录.html")).as_uri()

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
    pg.on("requestfailed", lambda r: errs.append("404:" + r.url.split("/")[-1][:40])
          if r.url.split("?")[0].endswith(".jpg") else None)

    pg.goto(URL, wait_until="load")
    pg.wait_for_timeout(900)

    print("\n[初始渲染]")
    check("卡片 248 张", pg.locator(".card").count() == 248, pg.locator(".card").count())
    check("计数文本", "248" in pg.inner_text("#count"), pg.inner_text("#count"))
    check("国别下拉有项", pg.locator("#fc option").count() > 5)
    check("立场下拉有项", pg.locator("#fs option").count() > 5)

    print("\n[筛选]")
    pg.select_option("#fc", "法国")
    pg.wait_for_timeout(300)
    n_fr = pg.locator(".card").count()
    check("筛法国（30 册 + 12 单页）", n_fr == 42, n_fr)
    pg.select_option("#fs", "社会主义")
    pg.wait_for_timeout(300)
    check("法国+社会主义 = 0", pg.locator(".card").count() == 0)
    pg.select_option("#fc", "")
    pg.wait_for_timeout(300)
    check("社会主义 3 本", pg.locator(".card").count() == 3, pg.locator(".card").count())

    print("\n[搜索]")
    pg.select_option("#fs", "")
    pg.fill("#q", "kropotkine")
    pg.wait_for_timeout(400)
    check("搜 kropotkine 有结果", pg.locator(".card").count() >= 2, pg.locator(".card").count())
    pg.fill("#q", "zzzznotexist")
    pg.wait_for_timeout(300)
    check("无结果提示", pg.locator(".empty").count() == 1)
    pg.fill("#q", "")
    pg.wait_for_timeout(300)

    print("\n[类型切换]")
    pg.click('#fk button[data-k="single"]')
    pg.wait_for_timeout(400)
    check("单页 144", pg.locator(".card").count() == 144, pg.locator(".card").count())
    pg.click('#fk button[data-k="book"]')
    pg.wait_for_timeout(400)
    check("小册子 104", pg.locator(".card").count() == 104, pg.locator(".card").count())

    print("\n[排序]")
    pg.select_option("#sort", "y-")
    pg.wait_for_timeout(400)
    first_y = pg.locator(".card .yr").first.inner_text()
    pg.select_option("#sort", "y+")
    pg.wait_for_timeout(400)
    first_y_asc = pg.locator(".card .yr").first.inner_text()
    check("年份降序首项 != 升序首项", first_y != first_y_asc, f"{first_y} vs {first_y_asc}")

    print("\n[URL 记忆]")
    pg.select_option("#sort", "i")
    pg.select_option("#fc", "德国")
    pg.fill("#q", "nazi")
    pg.wait_for_timeout(500)
    h1 = pg.evaluate("() => location.hash")
    check("hash 已写入", "c=%E5%BE%B7%E5%9B%BD" in h1 or "c=" in h1, h1)
    pg2 = b.new_page()
    pg2.goto(URL + h1, wait_until="load")
    pg2.wait_for_timeout(700)
    check("重新加载后保留筛选", pg2.input_value("#fc") == "德国", pg2.input_value("#fc"))
    check("重新加载后保留搜索", pg2.input_value("#q") == "nazi", pg2.input_value("#q"))
    pg2.close()

    print("\n[重置]")
    pg.click("#reset")
    pg.wait_for_timeout(400)
    check("重置后全量", pg.locator(".card").count() == 248, pg.locator(".card").count())
    check("重置后 hash 清空", pg.evaluate("() => location.hash") in ("", "#"), pg.evaluate("() => location.hash"))

    print("\n[阅读器]")
    pg.locator(".card").first.click()
    pg.wait_for_timeout(600)
    check("阅读器打开", pg.locator("#viewer.on").count() == 1)
    info = pg.evaluate("() => ({cnt: document.getElementById('cnt').textContent, n: visible[vi].n, t: visible[vi].t})")
    check("页码显示", "/" in info["cnt"] or info["cnt"] == "单页", info["cnt"])
    check("图片加载", pg.eval_on_selector("#vimg", "e => e.complete && e.naturalWidth > 0"))

    if info["n"] > 1:
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(400)
        check("→ 翻页", pg.inner_text("#cnt").startswith("2"), pg.inner_text("#cnt"))
        pg.keyboard.press("End")
        pg.wait_for_timeout(400)
        check("End 跳末页", pg.inner_text("#cnt").startswith(str(info["n"])), pg.inner_text("#cnt"))
        pg.keyboard.press("Home")
        pg.wait_for_timeout(400)
        check("Home 回首页", pg.inner_text("#cnt").startswith("1"), pg.inner_text("#cnt"))

    print("\n[缩放]")
    z0 = pg.inner_text("#zl")
    pg.click("#zin")
    pg.wait_for_timeout(300)
    z1 = pg.inner_text("#zl")
    check("放大生效", z0 != z1, f"{z0} → {z1}")
    pg.click("#zfit")
    pg.wait_for_timeout(300)
    check("适应复位", pg.inner_text("#zl") == "100%", pg.inner_text("#zl"))

    print("\n[换本]")
    before = pg.evaluate("() => vi")
    pg.click("#nextbook")
    pg.wait_for_timeout(500)
    after = pg.evaluate("() => vi")
    check("下一本", after == before + 1, f"{before}→{after}")
    pg.click("#prevbook")
    pg.wait_for_timeout(500)
    check("上一本回来", pg.evaluate("() => vi") == before)

    print("\n[关闭]")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    check("Esc 关闭", pg.locator("#viewer.on").count() == 0)

    print("\n[键盘快捷]")
    pg.keyboard.press("/")
    pg.wait_for_timeout(250)
    check("/ 聚焦搜索框", pg.evaluate("() => document.activeElement.id") == "q")

    print("\n[移动端视口]")
    m = b.new_page(viewport={"width": 390, "height": 844})
    m.goto(URL, wait_until="load")
    m.wait_for_timeout(700)
    check("移动端卡片渲染", m.locator(".card").count() == 248, m.locator(".card").count())
    m.locator(".card").first.click()
    m.wait_for_timeout(500)
    check("移动端阅读器可开", m.locator("#viewer.on").count() == 1)
    m.close()

    print("\n错误:")
    real = [e for e in errs if not e.startswith("404:")]
    print("  ", real if real else "无 JS 错误")
    if real:
        fails.append("JS 错误")

    b.close()

print("\n" + ("全部通过" if not fails else "失败项：" + "、".join(fails)))
