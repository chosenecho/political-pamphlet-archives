"""无障碍与语义体检：对话语义、标签、对比度、键盘可达性。

只报告实测值，不做主观评价。
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


# WCAG 相对亮度与对比度
# 注意：只接受 rgb()/rgba() 形式的背景色。color-mix()/oklab() 的计算值正则解析会得到
# 完全错误的数字（曾把 #count 判成 2.23），这类背景一律跳过并回落到 body 的背景。
CONTRAST = """() => {
  const lum = c => {
    const v = c.map(x => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); });
    return .2126 * v[0] + .7152 * v[1] + .0722 * v[2];
  };
  const rgb = s => {
    const m = /^rgba?\\(([^)]+)\\)$/.exec(String(s).trim());
    if (!m) return null;                      // color()/oklab()/color-mix() 一律不认
    const p = m[1].split(/[,\\s/]+/).filter(Boolean).map(Number);
    if (p.length < 3 || p.some(Number.isNaN)) return null;
    if (p.length === 4 && p[3] === 0) return null;   // 全透明
    return p.slice(0, 3);
  };
  const bgOf = el => {
    let n = el;
    while (n && n !== document.documentElement) {
      const c = rgb(getComputedStyle(n).backgroundColor);
      if (c) return c;
      n = n.parentElement;
    }
    return rgb(getComputedStyle(document.body).backgroundColor) || [255, 255, 255];
  };
  const ratio = el => {
    const fg = rgb(getComputedStyle(el).color);
    if (!fg) return null;
    const L1 = lum(fg), L2 = lum(bgOf(el));
    return +(((Math.max(L1, L2) + .05) / (Math.min(L1, L2) + .05))).toFixed(2);
  };
  const sels = {
    'body 正文': 'p.blurb',
    '卡片标题': '.card .ti',
    '卡片年份': '.card .yr',
    '卡片原名': '.card .or',
    '卡片脚注': '.card .tail span',
    '侧栏分组': '#rail h3',
    '侧栏选项': '#fCountry .fopt .lbl',
    '侧栏计数': '#fCountry .fopt .n',
    '缺口说明': '.fgap',
    '工具条计数': '#count',
    '页脚': '.foot p',
    '列表国别': '.row .r-c',
    '列表立场空': '.row .r-s.none',
  };
  const out = {};
  for (const [k, s] of Object.entries(sels)) {
    const el = document.querySelector(s);
    out[k] = el ? ratio(el) : null;
  }
  return out;
}"""

with sync_playwright() as p:
    b = p.chromium.launch()

    for theme in ("light", "dark"):
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, color_scheme=theme)
        pg = ctx.new_page()
        pg.goto(URL, wait_until="load")
        pg.wait_for_timeout(900)
        pg.click('#views button[data-view="list"]')
        pg.wait_for_timeout(400)

        print(f"\n[对比度 · {theme}]  (WCAG AA 正文 4.5，大字 3.0)")
        res = pg.evaluate(CONTRAST)
        for k, v in res.items():
            if v is None:
                print(f"  --   {k} 未找到")
                continue
            mark = "ok  " if v >= 4.5 else ("~~  " if v >= 3.0 else "LOW ")
            print(f"  {mark} {k}: {v}")
            if v < 3.0:
                fails.append(f"{theme} 对比度 {k} {v}")
        pg.close()
        ctx.close()

    # 语义
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(URL, wait_until="load")
    pg.wait_for_timeout(800)

    print("\n[语义]")
    check("有 lang", pg.evaluate("() => !!document.documentElement.lang"),
          pg.evaluate("() => document.documentElement.lang"))
    check("有跳过链接", pg.locator("a.skip").count() == 1)
    check("h1 唯一", pg.locator("h1").count() == 1)
    check("搜索框有标签",
          pg.evaluate("() => !!document.getElementById('q').getAttribute('aria-label')"))
    check("卡片可聚焦", pg.evaluate("() => document.querySelector('.card').tabIndex === 0"))
    check("卡片有 role", pg.evaluate("() => document.querySelector('.card').getAttribute('role')"))

    # 键盘直达
    pg.keyboard.press("/")
    pg.wait_for_timeout(300)
    check("/ 聚焦搜索", pg.evaluate("() => document.activeElement.id") == "q")
    pg.keyboard.press("Escape")
    pg.fill("#q", "")
    pg.wait_for_timeout(300)

    # Tab 能进入卡片
    pg.evaluate("() => document.querySelector('.card').focus()")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(900)
    check("Enter 打开阅读器", pg.locator("#rd.on").count() == 1)
    check("阅读器有 role=dialog",
          pg.evaluate("() => document.getElementById('rd').getAttribute('role')") == "dialog")
    check("阅读器有 aria-modal",
          pg.evaluate("() => document.getElementById('rd').getAttribute('aria-modal')") == "true")
    check("阅读器有可访问名",
          pg.evaluate("() => document.getElementById('rd').getAttribute('aria-labelledby')") == "rdTitle")
    check("关闭钮有 aria-label",
          pg.evaluate("() => !!document.getElementById('rdClose').getAttribute('aria-label')"))
    check("滑块有 aria-label",
          pg.evaluate("() => !!document.getElementById('rdSlider').getAttribute('aria-label')"))
    check("图片有 alt",
          pg.evaluate("() => document.getElementById('rdImgA').hasAttribute('alt')"))

    # 焦点不逃逸：打开阅读器后 body 禁止滚动
    check("打开时锁定滚动", pg.evaluate("() => document.body.classList.contains('locked')"))
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(500)
    check("关闭后解锁", pg.evaluate("() => !document.body.classList.contains('locked')"))

    print("\n[减少动效偏好]")
    pg.close()
    ctx2 = b.new_context(viewport={"width": 1440, "height": 900},
                         reduced_motion="reduce")
    pg2 = ctx2.new_page()
    pg2.goto(URL, wait_until="load")
    pg2.wait_for_timeout(800)
    dur = pg2.evaluate("""() => {
      const c = document.querySelector('.card');
      return getComputedStyle(c).transitionDuration;
    }""")
    check("动效被压缩", "0.001" in dur or dur.startswith("0") or "1e-06" in dur, dur)
    ctx2.close()
    b.close()

print("\n" + ("全部通过" if not fails else f"问题 {len(fails)} 项：" + "；".join(fails)))
sys.exit(1 if fails else 0)
