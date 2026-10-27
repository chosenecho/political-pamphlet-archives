"""检验译名在目录页与阅读器中的呈现与搜索。"""

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import paths

URL = pathlib.Path(paths.SITE).as_uri()
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

    print("\n[卡片双行标题]")
    pg.select_option("#fc", "德国")
    pg.wait_for_timeout(400)
    first = pg.locator(".card").first
    ti = first.locator(".ti").inner_text()
    to = first.locator(".to").count()
    check("卡片主标题为中文", any('\u4e00' <= ch <= '\u9fff' for ch in ti), ti)
    check("卡片带原文小字", to == 1, to)

    print("\n[中文搜索]")
    pg.select_option("#fc", "")
    pg.fill("#q", "无政府")
    pg.wait_for_timeout(400)
    n1 = pg.locator(".card").count()
    check("搜「无政府」有结果", n1 >= 2, n1)
    pg.fill("#q", "选民手册")
    pg.wait_for_timeout(400)
    n2 = pg.locator(".card").count()
    check("搜「选民手册」命中美国册子", n2 >= 6, n2)

    print("\n[外文搜索仍可用]")
    pg.fill("#q", "kropotkine")
    pg.wait_for_timeout(400)
    n3 = pg.locator(".card").count()
    check("原外文标题仍可搜", n3 >= 2, n3)

    print("\n[阅读器]")
    pg.fill("#q", "克鲁泡特金")
    pg.wait_for_timeout(400)
    check("搜译者惯用名也命中", pg.locator(".card").count() >= 1, pg.locator(".card").count())
    pg.locator(".card").first.click()
    pg.wait_for_timeout(700)
    vt = pg.inner_text("#vtitle")
    vm = pg.inner_text("#vmeta")
    check("阅读器标题为中文", any('\u4e00' <= ch <= '\u9fff' for ch in vt), vt)
    check("阅读器显示原文", "Kropotkine" in vm or "kropotkine" in vm.lower(), vm)
    check("阅读器显示元信息", "法国" in vm or "无政府" in vm, vm)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)

    print("\n[中国条目不受影响]")
    pg.fill("#q", "")
    pg.select_option("#fc", "中国")
    pg.wait_for_timeout(400)
    c1 = pg.locator(".card").first
    check("中国条目无原文小字", c1.locator(".to").count() == 0)

    print("\n错误:", errs or "无")
    if errs:
        fails.append("JS 错误")
    b.close()

print("\n" + ("全部通过" if not fails else "失败：" + "、".join(fails)))
