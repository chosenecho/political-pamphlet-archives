"""验收离线包：解压到全新目录，用浏览器打开，确认能一键使用。

只信任"解压后的真实结果"——开发目录里测通不算，因为路径关系可能被开发
环境的目录结构兜住。
"""

import os
import shutil
import sys
import tempfile
import zipfile

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

fails = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


def pick_zip():
    if len(sys.argv) > 1 and sys.argv[1].endswith(".zip"):
        return sys.argv[1]
    dist = os.path.join(paths.BASE, "dist")
    zips = sorted(f for f in os.listdir(dist) if f.endswith(".zip"))
    if not zips:
        raise SystemExit("dist/ 里没有 zip，先跑 scripts/make_bundle.py")
    return os.path.join(dist, zips[-1])


zip_path = pick_zip()
print(f"验收对象：{os.path.basename(zip_path)}")
print(f"体积 {os.path.getsize(zip_path)/1e6:.0f} MB\n")

tmp = tempfile.mkdtemp(prefix="pkgcheck-")
try:
    # 模拟"对方收到后解压"：解到一个干净目录
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        z.extractall(tmp)

    print("[解压]")
    check("含 index.html", "index.html" in names)
    check("含目录.csv", any(n.endswith("目录.csv") for n in names))
    check("含使用说明", any("使用说明" in n for n in names))
    check("含免责声明", any("免责声明" in n for n in names))
    check("图像在 pages/ 下", sum(1 for n in names if n.startswith("pages/")) > 1000,
          sum(1 for n in names if n.startswith("pages/")))
    # 文件名全 ASCII 是刻意设计：中文名在部分解压工具里会乱码
    non_ascii = [n for n in names if any(ord(c) > 127 for c in n)]
    check("图像路径全 ASCII（防解压乱码）",
          not any(n.startswith("pages/") for n in non_ascii),
          non_ascii[:3])

    recs = catalog.load()
    total = len(recs)
    index = os.path.join(tmp, "index.html")
    url = "file:///" + index.replace("\\", "/")

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 940})
        bad, errs = [], []
        pg.on("response", lambda r: bad.append((r.status, r.url.rsplit("/", 1)[-1]))
              if r.status >= 400 else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))

        pg.goto(url, wait_until="load")
        pg.wait_for_timeout(2500)

        print("\n[目录页]")
        check("卡片数等于目录条数", pg.locator(".card").count() == total,
              f"{pg.locator('.card').count()} vs {total}")
        shown = pg.eval_on_selector_all(
            ".card .mat img", "els => els.filter(e => e.complete && e.naturalWidth > 0).length")
        check("封面图真的加载出来", shown > 0, shown)
        check("无 404", not bad, bad[:4])

        print("\n[阅读器]")
        pg.locator(".card").first.click()
        pg.wait_for_timeout(2200)
        check("打开", pg.locator("#rd.on").count() == 1)
        check("主图已加载",
              pg.eval_on_selector("#rdImgA", "e => e.complete && e.naturalWidth > 0"))
        check("无缺图提示", pg.locator("#rdMiss.on").count() == 0)
        n = pg.evaluate("() => cur().n")
        if n > 1:
            pg.keyboard.press("ArrowRight")
            pg.wait_for_timeout(1200)
            check("可翻页", pg.evaluate("() => rd.p") == 2)
            check("翻页后图仍正常",
                  pg.eval_on_selector("#rdImgA", "e => e.complete && e.naturalWidth > 0"))
            th = pg.eval_on_selector_all(
                "#rdThumbs img", "els => els.filter(e => e.complete && e.naturalWidth > 0).length")
            check("缩略图加载", th > 0, th)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)

        print("\n[筛选与搜索]")
        pg.click('#fCountry .fopt[data-v="中国"]')
        pg.wait_for_timeout(600)
        cn = pg.locator(".card").count()
        check("国别筛选可用", 0 < cn < total, cn)
        pg.click("#reset")
        pg.wait_for_timeout(500)
        pg.fill("#q", "克鲁泡特金")
        pg.wait_for_timeout(600)
        check("搜索可用", pg.locator(".card").count() >= 2, pg.locator(".card").count())

        print("\n[离线自足]")
        check("无 JS 异常", not errs, errs[:2])
        # 页面不应引用任何远程资源，否则离线会缺样式
        remote = pg.evaluate("""() => [...document.querySelectorAll('link[href],script[src],img[src]')]
            .map(e => e.getAttribute('href') || e.getAttribute('src'))
            .filter(u => u && /^https?:/i.test(u))""")
        check("不依赖远程资源", not remote, remote[:5])
        b.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n" + ("离线包验收通过" if not fails else f"失败 {len(fails)} 项：" + "、".join(fails)))
sys.exit(1 if fails else 0)
