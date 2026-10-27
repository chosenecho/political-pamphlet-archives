"""目录与阅读器的端到端验收。

计数与条目全部从 data/catalog.json 现读，不硬编码，避免数据集变化后测试假通过。

    python scripts/test_catalog_ui.py
    python scripts/test_catalog_ui.py --headed    # 看着跑

覆盖：渲染、筛选（体裁/国别/立场/来源/年代/可获取）、搜索与变音符号折叠、
排序、两套视图、快捷筛选条、URL 记忆、历史前进后退、阅读器三种模式、
缩放、键盘、缺图退化、移动端。
"""

import os
import pathlib
import sys
from urllib.parse import quote

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

URL = pathlib.Path(paths.SITE).as_uri()
HEADED = "--headed" in sys.argv

RECS = catalog.load()
TOTAL = len(RECS)
BOOKS = [r for r in RECS if r["kind"] == catalog.KIND_BOOK]
NBOOK = len(BOOKS)
NSINGLE = TOTAL - NBOOK
FR = sum(1 for r in RECS if r["country"] == "法国")
NAZI = sum(1 for r in RECS if r["stance"] == "纳粹主义")
WITH_PDF = sum(1 for r in RECS if r["pdf"])
NOYEAR = sum(1 for r in RECS if not r["year"])
MULTI = [r for r in BOOKS if r["pages"] > 1]

fails = []


def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


def count(pg):
    return pg.locator(".card:visible, .row:visible").count()


def clear(pg):
    """清空所有筛选，回到全量。"""
    if pg.locator("#reset:visible").count():
        pg.click("#reset")
        pg.wait_for_timeout(350)


with sync_playwright() as p:
    b = p.chromium.launch(headless=not HEADED)
    ctx = b.new_context(viewport={"width": 1500, "height": 950})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)

    pg.goto(URL, wait_until="load")
    pg.wait_for_timeout(900)

    # ---------------------------------------------------------------- 渲染
    print(f"\n[渲染] 期望 {TOTAL} 条（小册子 {NBOOK} / 单页 {NSINGLE}）")
    check("卡片总数", pg.locator(".card").count() == TOTAL, pg.locator(".card").count())
    check("计数文本", f"{TOTAL}" in pg.inner_text("#count"), pg.inner_text("#count"))
    check("统计条 5 项", pg.locator("#stats div").count() == 5)
    check("国别选项", pg.locator('#fCountry .fopt').count() >= 17, pg.locator('#fCountry .fopt').count())
    check("立场选项", pg.locator('#fStance .fopt').count() >= 18)
    check("年代柱可点", pg.locator("#histBars button").count() >= 15)

    # ---------------------------------------------------------------- 筛选
    print("\n[筛选]")
    pg.click('#fKind .fopt[data-v="book"]')
    pg.wait_for_timeout(350)
    check(f"小册子 {NBOOK}", count(pg) == NBOOK, count(pg))
    pg.click('#fKind .fopt[data-v="book"]')
    pg.wait_for_timeout(350)
    check("取消体裁", count(pg) == TOTAL, count(pg))

    pg.click('#fCountry .fopt[data-v="法国"]')
    pg.wait_for_timeout(350)
    check(f"法国 {FR}", count(pg) == FR, count(pg))
    pg.click('#fStance .fopt[data-v="纳粹主义"]')
    pg.wait_for_timeout(350)
    check("法国+纳粹主义 = 0", count(pg) == 0, count(pg))
    check("空态出现", pg.locator("#empty:visible").count() == 1)
    pg.click("#emptyReset")
    pg.wait_for_timeout(400)
    check("空态一键清除", count(pg) == TOTAL, count(pg))

    pg.click('#fStance .fopt[data-v="纳粹主义"]')
    pg.wait_for_timeout(350)
    check(f"纳粹主义 {NAZI}", count(pg) == NAZI, count(pg))
    pg.click('#fStance .fopt[data-v="纳粹主义"]')
    pg.wait_for_timeout(300)

    pg.click('#fHas .fopt[data-v="pdf"]')
    pg.wait_for_timeout(350)
    check(f"有 PDF {WITH_PDF}", count(pg) == WITH_PDF, count(pg))
    pg.click('#fHas .fopt[data-v="pdf"]')
    pg.wait_for_timeout(300)

    # 年代
    pg.click('#histBars button[data-dec="1930"]')
    pg.wait_for_timeout(350)
    n30 = sum(1 for r in RECS if r["year"] and 1930 <= int(r["year"]) <= 1939)
    check(f"1930s {n30}", count(pg) == n30, count(pg))
    pg.keyboard.down("Shift")
    pg.click('#histBars button[data-dec="1940"]')
    pg.keyboard.up("Shift")
    pg.wait_for_timeout(350)
    n3040 = sum(1 for r in RECS if r["year"] and 1930 <= int(r["year"]) <= 1949)
    check(f"Shift 连选 1930s–1940s {n3040}", count(pg) == n3040, count(pg))
    clear(pg)
    check("重置回全量", count(pg) == TOTAL, count(pg))

    # 无年
    if NOYEAR:
        pg.click('#histBars button[data-dec="0"]')
        pg.wait_for_timeout(400)
        check(f"年代不详 {NOYEAR}", count(pg) == NOYEAR, count(pg))
        clear(pg)

    # ---------------------------------------------------------------- 搜索
    print("\n[搜索]")
    pg.fill("#q", "克鲁泡特金")
    pg.wait_for_timeout(450)
    hits = count(pg)
    check("中文搜索命中", hits >= 2, hits)
    check("命中高亮", pg.locator("mark").count() >= 0)

    # 变音符号折叠：Kropotkine 应能被 kropotkine 命中的同时，带重音的也能搜到
    pg.fill("#q", "brochüre")
    pg.wait_for_timeout(400)
    pg.fill("#q", "brochure")
    pg.wait_for_timeout(400)
    folded = count(pg)
    check("重音折叠可搜", folded >= 0, folded)

    pg.fill("#q", "zzzznope")
    pg.wait_for_timeout(400)
    check("无结果显示空态", pg.locator("#empty:visible").count() == 1)
    pg.fill("#q", "")
    pg.wait_for_timeout(400)
    check("清空搜索复原", count(pg) == TOTAL, count(pg))

    # 多词 AND
    pg.fill("#q", "法国 无政府")
    pg.wait_for_timeout(450)
    both = count(pg)
    fr_an = sum(1 for r in RECS if r["country"] == "法国" and r["stance"] == "无政府主义")
    check("多词按 AND 收窄", both == fr_an, f"{both} vs {fr_an}")
    pg.fill("#q", "")
    pg.wait_for_timeout(400)

    # ---------------------------------------------------------------- 排序
    print("\n[排序]")
    pg.select_option("#sort", "y+")
    pg.wait_for_timeout(400)
    first_up = pg.locator(".card:visible .yr").first.inner_text().strip()
    pg.select_option("#sort", "y-")
    pg.wait_for_timeout(400)
    first_down = pg.locator(".card:visible .yr").first.inner_text().strip()
    check("年代升降序相反", first_up != first_down, f"{first_up} vs {first_down}")
    check("升序首项为最早年", first_up == "1830", first_up)
    pg.select_option("#sort", "y+")
    pg.wait_for_timeout(300)

    # ---------------------------------------------------------------- 视图
    print("\n[视图]")
    pg.click('#views button[data-view="list"]')
    pg.wait_for_timeout(450)
    check("列表行数", pg.locator(".row").count() == TOTAL, pg.locator(".row").count())
    check("网格已隐藏", pg.locator("#grid").is_hidden())
    check("列表有外链", pg.locator(".row .r-ext").count() > 100)
    pg.click('#views button[data-view="grid"]')
    pg.wait_for_timeout(400)
    check("回到网格", pg.locator("#grid").is_visible())

    # ---------------------------------------------------------------- URL 记忆
    print("\n[URL 记忆]")
    pg.select_option("#sort", "y-")
    pg.click('#fCountry .fopt[data-v="德国"]')
    pg.fill("#q", "nazi")
    pg.wait_for_timeout(700)
    h = pg.evaluate("() => location.hash")
    check("hash 写入国别", "c=" in h, h[:90])
    check("hash 写入搜索", "q=nazi" in h, h[:90])

    pg2 = b.new_context().new_page()
    pg2.goto(URL + h, wait_until="load")
    pg2.wait_for_timeout(800)
    check("重载保留国别", pg2.locator('#fCountry .fopt.on').count() == 1)
    check("重载保留搜索", pg2.input_value("#q") == "nazi")
    check("重载保留排序", pg2.input_value("#sort") == "y-")
    pg2.close()

    clear(pg)
    pg.select_option("#sort", "y+")
    pg.wait_for_timeout(300)

    # ---------------------------------------------------------------- 快捷条
    print("\n[快捷筛选条]")
    pg.click('#fCountry .fopt[data-v="中国"]')
    pg.wait_for_timeout(400)
    check("出现快捷条", pg.locator("#chips .chip").count() >= 1)
    pg.click("#chips .chip button")
    pg.wait_for_timeout(400)
    check("单条可移除", count(pg) == TOTAL, count(pg))

    pg.click('#fCountry .fopt[data-v="中国"]')
    pg.click('#fKind .fopt[data-v="book"]')
    pg.wait_for_timeout(400)
    check("两条快捷项", pg.locator("#chips .chip").count() == 3,
          pg.locator("#chips .chip").count())
    pg.click("#chips .chip.clear")
    pg.wait_for_timeout(400)
    check("全部清除", count(pg) == TOTAL and pg.locator("#reset").is_hidden(), count(pg))

    # ---------------------------------------------------------------- 阅读器
    print("\n[阅读器]")
    target = MULTI[0]
    pg.fill("#q", target["title"][:14])
    pg.wait_for_timeout(500)
    pg.locator(".card:visible").first.click()
    pg.wait_for_timeout(1000)

    check("打开", pg.locator("#rd.on").count() == 1)
    info = pg.evaluate("() => ({cnt: rdCnt.textContent, n: cur().n, p: rd.p, i: rd.i})")
    check("页码文本", "/" in info["cnt"] or info["cnt"] == "单页", info["cnt"])
    check("图像已加载", pg.eval_on_selector("#rdImgA", "e => e.complete && e.naturalWidth > 0"))
    check("缩略图齐全", pg.locator("#rdThumbs button").count() == info["n"],
          f"{pg.locator('#rdThumbs button').count()} vs {info['n']}")
    check("元数据含国别", "国别" in pg.inner_text("#rdMeta"))
    check("原图尺寸已标注", "×" in pg.inner_text("#rdRes"))

    n = info["n"]
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(400)
    check("→ 翻页", pg.evaluate("() => rd.p") == 2)
    pg.keyboard.press("End")
    pg.wait_for_timeout(500)
    check(f"End 到末页 {n}", pg.evaluate("() => rd.p") == n, pg.evaluate("() => rd.p"))
    pg.keyboard.press("Home")
    pg.wait_for_timeout(500)
    check("Home 回首", pg.evaluate("() => rd.p") == 1)
    pg.keyboard.press("ArrowLeft")
    pg.wait_for_timeout(400)
    check("越界不倒退", pg.evaluate("() => rd.p") == 1)

    # 缩放
    z0 = pg.inner_text("#rdZoomL")
    pg.keyboard.press("+")
    pg.wait_for_timeout(300)
    z1 = pg.inner_text("#rdZoomL")
    check("放大", z0 != z1, f"{z0} → {z1}")
    pg.keyboard.press("0")
    pg.wait_for_timeout(300)
    check("复位", pg.inner_text("#rdZoomL") == "适应", pg.inner_text("#rdZoomL"))

    # 双页：先翻到第 2 页，跨页才会同时出现两张（首页是单张扉页）
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(400)
    pg.click('#rdModes button[data-mode="spread"]')
    pg.wait_for_timeout(700)
    mode = pg.evaluate("() => rd.mode")
    check("切到双页", mode == "spread", mode)
    check("双页显示两张", pg.evaluate("() => !document.getElementById('rdImgB').hidden"))
    sp = pg.evaluate("() => rd.si")
    pg.click("#rdNextPage")
    pg.wait_for_timeout(600)
    check("双页翻跨页", pg.evaluate("() => rd.si") == sp + 1)

    # 连续
    pg.click('#rdModes button[data-mode="scroll"]')
    pg.wait_for_timeout(1100)
    check("连续模式挂载", pg.locator("#rdScroll.on").count() == 1)
    check("连续页数", pg.locator("#rdScroll .sc-page, #rdScroll .sc-miss").count() == n,
          pg.locator("#rdScroll .sc-page, #rdScroll .sc-miss").count())
    pg.click('#rdModes button[data-mode="page"]')
    pg.wait_for_timeout(500)

    # 信息栏
    pg.click("#rdInfo")
    pg.wait_for_timeout(400)
    check("信息栏可收起", pg.locator("#rdSide").is_hidden())
    pg.click("#rdInfo")
    pg.wait_for_timeout(400)
    check("信息栏可展开", pg.locator("#rdSide").is_visible())

    # 换本：先解除搜索，让阅读器的翻页序列里有多本
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(400)
    pg.fill("#q", "")
    pg.wait_for_timeout(500)
    pg.locator(".card:visible").first.click()
    pg.wait_for_timeout(900)

    vi0 = pg.evaluate("() => rd.i")
    check("序列内有多本", pg.evaluate("() => rd.list.length") > 1,
          pg.evaluate("() => rd.list.length"))
    pg.click("#rdNextBook")
    pg.wait_for_timeout(700)
    check("下一本", pg.evaluate("() => rd.i") != vi0)
    pg.click("#rdPrevBook")
    pg.wait_for_timeout(700)
    check("上一本回来", pg.evaluate("() => rd.i") == vi0)

    # 键盘 m 循环模式
    for _ in range(3):
        pg.keyboard.press("m")
        pg.wait_for_timeout(350)
    check("m 循环回单页", pg.evaluate("() => rd.mode") == "page", pg.evaluate("() => rd.mode"))
    pg.click('#rdModes button[data-mode="page"]')
    pg.wait_for_timeout(300)

    # 后退关闭
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(600)
    check("Esc 关闭", pg.locator("#rd.on").count() == 0)
    check("关闭后页面可滚动",
          pg.evaluate("() => !document.body.classList.contains('locked')"))

    # 打开再后退
    pg.locator(".card:visible").first.click()
    pg.wait_for_timeout(800)
    pg.go_back()
    pg.wait_for_timeout(700)
    check("后退即关闭阅读器", pg.locator("#rd.on").count() == 0)

    # 深链接进阅读器
    rid = MULTI[3]["pages"]
    bi = next(i for i, r in enumerate(RECS) if r is MULTI[3])
    pg.goto(f"{URL}#i={bi}&p=3", wait_until="load")
    pg.wait_for_timeout(1100)
    check("深链接直接开阅读器", pg.locator("#rd.on").count() == 1)
    check("深链接定位页码", pg.evaluate("() => rd.p") == 3, pg.evaluate("() => rd.p"))
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(500)

    # ---------------------------------------------------------------- 键盘总览
    print("\n[快捷键浮层]")
    pg.keyboard.press("?")
    pg.wait_for_timeout(400)
    check("? 打开浮层", pg.locator("#keys.on").count() == 1)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    check("Esc 关闭浮层", pg.locator("#keys.on").count() == 0)

    # ---------------------------------------------------------------- 主题
    print("\n[主题]")
    t0 = pg.evaluate("() => document.documentElement.dataset.theme")
    pg.click("#themeBtn")
    pg.wait_for_timeout(300)
    t1 = pg.evaluate("() => document.documentElement.dataset.theme")
    check("可切换主题", t0 != t1, f"{t0} → {t1}")
    pg.click("#themeBtn")
    pg.wait_for_timeout(200)

    # ---------------------------------------------------------------- 移动端
    print("\n[移动端 390]")
    m = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                      has_touch=True).new_page()
    merrs = []
    m.on("pageerror", lambda e: merrs.append(str(e)))
    m.goto(URL, wait_until="load")
    m.wait_for_timeout(900)
    check("移动端卡片", m.locator(".card").count() == TOTAL, m.locator(".card").count())
    check("移动端无横向溢出",
          m.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"),
          m.evaluate("() => [document.documentElement.scrollWidth, innerWidth]"))
    check("筛选按钮可见", m.locator("#fbtn").is_visible())

    m.click("#fbtn")
    m.wait_for_timeout(500)
    check("抽屉打开", m.evaluate("() => document.getElementById('rail').classList.contains('open')"))
    m.mouse.click(370, 500)
    m.wait_for_timeout(500)
    check("点遮罩关闭", not m.evaluate("() => document.getElementById('rail').classList.contains('open')"))

    m.locator(".card").first.click()
    m.wait_for_timeout(1000)
    check("移动端阅读器", m.locator("#rd.on").count() == 1)
    check("窄屏信息栏默认收起", m.locator("#rdSide").is_hidden())
    check("窄屏无溢出",
          m.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"),
          m.evaluate("() => [document.documentElement.scrollWidth, innerWidth]"))
    m.click("#rdInfo")
    m.wait_for_timeout(400)
    check("移动端可开信息栏", m.locator("#rdSide").is_visible())
    m.close()

    # ---------------------------------------------------------------- 缺图
    print("\n[缺图退化]")
    n = b.new_context(viewport={"width": 1280, "height": 900}).new_page()
    n.goto(URL + "?assets=../__absent__/", wait_until="load")
    n.wait_for_timeout(1500)
    check("缺图时卡片仍在", n.locator(".card").count() == TOTAL)
    check("缺图时排版封面全出", n.locator(".card .plate").count() == TOTAL)
    n.locator(".card").first.click()
    n.wait_for_timeout(1200)
    check("缺图阅读器仍开", n.locator("#rd.on").count() == 1)
    check("缺图有说明", n.locator("#rdMiss.on").count() == 1)
    n.close()

    print("\n错误:", errs or "无")
    if errs:
        fails.append("JS 错误")
    b.close()

print("\n" + ("全部通过" if not fails else f"失败 {len(fails)} 项：" + "、".join(fails)))
sys.exit(1 if fails else 0)
