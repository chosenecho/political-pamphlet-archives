"""缺图场景验收：指向不存在的图像目录，检查排版封面与阅读器缺图态。

这就是 GitHub Pages 的真实情形——images/ 不入库，所有图 404。
"""

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

BASE = pathlib.Path(paths.SITE).as_uri()
URL = BASE + "?assets=../__no_such_dir__/"
OUT = os.path.join(paths.IMAGES, "_ui")
os.makedirs(OUT, exist_ok=True)

RECS = catalog.load()
TOTAL = len(RECS)
fails = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 940}, device_scale_factor=2)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_timeout(1800)

    print(f"\n[缺图 · 目录] 共 {TOTAL} 条")
    check("卡片全部渲染", pg.locator(".card").count() == TOTAL, pg.locator(".card").count())
    check("排版封面全部可见", pg.locator(".card .plate").count() == TOTAL,
          pg.locator(".card .plate").count())
    check("破图已隐藏",
          pg.evaluate("() => [...document.querySelectorAll('.mat img')].every(i => i.hidden || !i.complete || i.naturalWidth === 0)"))
    # 排版封面里要有年份与标题
    first = pg.locator(".card .plate").first
    check("封面含年份", bool(first.locator(".py").inner_text().strip()))
    check("封面含题名", len(first.locator(".pt").inner_text().strip()) > 1)

    pg.screenshot(path=os.path.join(OUT, "20-noimg-grid.png"))

    print("\n[缺图 · 文字层完好]")
    check("卡片仍可点开", pg.locator(".card").first.is_enabled())
    check("筛选计数正确", TOTAL > 0 and pg.locator(".fopt").count() > 10)

    pg.locator(".card").first.click()
    pg.wait_for_timeout(1600)
    print("\n[缺图 · 阅读器]")
    check("阅读器打开", pg.locator("#rd.on").count() == 1)
    check("缺图提示出现", pg.locator("#rdMiss.on").count() == 1)
    check("缺图时仍可翻页",
          pg.evaluate("() => !document.getElementById('rdNextPage').disabled") or
          pg.evaluate("() => document.getElementById('rdSlider').disabled"))
    # 左右点击区不被缺图层盖住
    hit = pg.evaluate("""() => {
      const el = document.getElementById('rdNext');
      const r = el.getBoundingClientRect();
      const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return top ? (top.id || top.className) : null;
    }""")
    check("缺图层不吃点击", hit in ("rdNext", "rd-hit r"), hit)
    check("元数据完整", "国别" in pg.inner_text("#rdMeta"))
    pg.screenshot(path=os.path.join(OUT, "21-noimg-reader.png"))

    print("\n[缺图 · 缩略图退化]")
    th = pg.evaluate("""() => {
      const bs = [...document.querySelectorAll('#rdThumbs button')];
      return {n: bs.length, miss: bs.filter(b => b.classList.contains('miss')).length};
    }""")
    print("       缩略图", th)
    if th["n"]:
        check("缩略图全部标记缺图", th["miss"] == th["n"], th)

    print("\n错误:", errs or "无")
    if errs:
        fails.append("JS 错误")
    b.close()

print("\n" + ("全部通过" if not fails else "失败：" + "、".join(fails)))
sys.exit(1 if fails else 0)
