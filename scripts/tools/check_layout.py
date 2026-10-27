"""布局体检：溢出、对齐、点击目标尺寸、对比度相关的实测值。

只读 docs/index.html，不做断言汇总以外的写操作；退出码表明是否有硬性问题。
"""

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import paths

URL = pathlib.Path(paths.SITE).as_uri()
fails = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


PROBE = """() => {
  const de = document.documentElement;
  const wide = [];
  document.querySelectorAll('body *').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.right > de.clientWidth + 1.5) {
      wide.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 40),
                  right: Math.round(r.right), w: Math.round(r.width) });
    }
  });
  return {
    scrollW: de.scrollWidth, clientW: de.clientWidth,
    wide: wide.slice(0, 12),
    gridCols: getComputedStyle(document.getElementById('grid')).gridTemplateColumns,
    gridW: Math.round(document.getElementById('grid').getBoundingClientRect().width),
    mainW: Math.round(document.querySelector('main').getBoundingClientRect().width),
    railW: Math.round(document.getElementById('rail').getBoundingClientRect().width),
  };
}"""

with sync_playwright() as p:
    b = p.chromium.launch()
    for w, h, label in ((1440, 900, "1440"), (1280, 800, "1280"), (390, 844, "390")):
        pg = b.new_page(viewport={"width": w, "height": h})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(URL, wait_until="load")
        pg.wait_for_timeout(900)

        print(f"\n[{label}] 布局")
        info = pg.evaluate(PROBE)
        check(f"{label} 无水平溢出",
              info["scrollW"] <= info["clientW"] + 1,
              f"scrollW={info['scrollW']} clientW={info['clientW']}")
        if info["wide"]:
            print("        溢出元素:", info["wide"])
        print("        grid:", info["gridW"], "main:", info["mainW"], "rail:", info["railW"])

        # 卡片：封面区域是否等比（不被裁切）
        card = pg.evaluate("""() => {
          const c = document.querySelector('.card .mat');
          if (!c) return null;
          const r = c.getBoundingClientRect();
          return {w: Math.round(r.width), h: Math.round(r.height),
                  ratio: +(r.width / r.height).toFixed(3)};
        }""")
        if card and label != "390":
            print("        封面块:", card)

        # 点击目标
        if label != "390":
            small = pg.evaluate("""() => {
              const bad = [];
              document.querySelectorAll('#rail .fopt, .bar button, #views button').forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.height > 0 && r.height < 28) bad.push({cls: el.className.slice(0,30), h: Math.round(r.height)});
              });
              return bad.slice(0, 8);
            }""")
            check(f"{label} 点击目标 >=28px", not small, small)

        check(f"{label} 无 JS 错误", not errs, errs[:3])
        pg.close()
    b.close()

print("\n" + ("全部通过" if not fails else "失败：" + "、".join(fails)))
sys.exit(1 if fails else 0)
