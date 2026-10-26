"""实测连续翻页：跨条目边界是否顺畅。"""

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
    pg.on("requestfailed", lambda r: errs.append("404:" + r.url.split("/")[-1]) if r.url.endswith(".jpg") else None)

    pg.goto(HTML, wait_until="load")
    pg.wait_for_timeout(600)

    # 单页条目（国际）应当能继续往后翻
    i = pg.evaluate("()=>D.findIndex(d=>d.n===1)")
    d = pg.evaluate(f"()=>({{c:D[{i}].c,t:D[{i}].t,n:D[{i}].n,i:D[{i}].i}})")
    print("单页条目:", d["c"], d["t"][:34])
    pg.locator(f'.c[data-i="{i}"]').click()
    pg.wait_for_timeout(500)
    print("  打开:", pg.inner_text("#cnt"), "| 下一条禁用:", pg.eval_on_selector('#foot button[data-step="1"]', "e=>e.disabled"))

    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(500)
    nd = pg.evaluate("()=>({c:D.find(x=>x.i===cur.i).c,t:cur.t,i:cur.i})")
    print("  按→之后:", pg.inner_text("#cnt"), "| 条目 index:", nd["i"], "|", nd["c"], nd["t"][:30])
    print("  是否进入了下一条:", nd["i"] == i + 1)

    # 跨页条目末尾 → 下一条
    j = pg.evaluate("()=>D.findIndex(x=>x.n>1)")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(200)
    pg.locator(f'.c[data-i="{j}"]').click()
    pg.wait_for_timeout(400)
    n = pg.evaluate(f"()=>D[{j}].n")
    for _ in range(n):
        pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(500)
    k = pg.evaluate("()=>cur.i")
    print(f"  多页条目({n}p)翻到末页后再→: 条目 index {k}（应为 {j+1}）")

    # 反向：单页条目首按← 回到上一条末页
    pg.keyboard.press("Escape")
    m = pg.evaluate("()=>D.findIndex(x=>x.n===1 && x.i>0)")
    pg.keyboard.press("Escape")
    pg.locator(f'.c[data-i="{m}"]').click()
    pg.wait_for_timeout(400)
    pg.keyboard.press("ArrowLeft")
    pg.wait_for_timeout(400)
    back = pg.evaluate("()=>({i:cur.i,cnt:document.getElementById('cnt').textContent})")
    print(f"  单页条目按←: 回到 index {back['i']}，显示 {back['cnt']}")

    # 全局边界
    pg.keyboard.press("Escape")
    pg.locator('.c[data-i="0"]').click()
    pg.wait_for_timeout(300)
    for _ in range(6):
        pg.keyboard.press("ArrowLeft")
    print("  首条首页再按←: 条目 index", pg.evaluate("()=>cur.i"), "| 按钮禁用:", pg.eval_on_selector('#foot button[data-step="-1"]', "e=>e.disabled"))

    print("错误:", errs[:4] if errs else "无")
    b.close()
