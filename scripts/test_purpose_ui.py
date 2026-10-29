"""用途轴（purpose）的端到端验收。

验的是「新增一个筛选轴没把别的弄坏」，不是页面美化：
  - 筛选组存在、选项数对得上数据
  - 点选真的筛得动，条数与数据对得上
  - 未判定的条目不被兜进任何用途（缺口不伪装成类别）
  - 与其它轴可叠加、可清除、可经 URL 还原
  - 切列表视图后用途仍可见

跑法：python scripts/test_purpose_ui.py
"""

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths
from lib import vocab

URL = pathlib.Path(paths.SITE).as_uri()
fails = []


def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + (("  " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


RECS = catalog.load()
COUNTS = {}
for r in RECS:
    p = vocab.normalize(r.get("purpose"))
    COUNTS[p] = COUNTS.get(p, 0) + 1
MARKED = {k: v for k, v in COUNTS.items() if k}
BLANK = COUNTS.get("", 0)
TOP = max(MARKED, key=MARKED.get)
TOP_N = MARKED[TOP]


def check_rule_does_not_clobber():
    """`label_purpose.py` 不得清空别的判据补出来的用途。

    这是实际踩到的 bug：规则判不出时它无条件写空串，把
    `enrich_swiss_categories.py` 从 Commons 分类补的 61 条一次清空。
    「本规则读不出」不等于「这条没有用途」——规则只是判据之一。
    """
    print("\n[规则不覆盖其它判据的结果]")
    from label_purpose import judge

    clobber = []
    for r in RECS:
        p, _ = judge(r)
        old = vocab.normalize(r.get("purpose"))
        if not p and old:
            clobber.append((r, old))
    # 这是「可能被清空」的集合；真正跑一遍脚本再看数据有没有变，才算验证。
    import subprocess
    import tempfile
    import hashlib
    import json as _json

    before = hashlib.sha256(
        _json.dumps([r.get("purpose") for r in RECS], ensure_ascii=False).encode()).hexdigest()
    r = subprocess.run([sys.executable, os.path.join(paths.SCRIPTS, "label_purpose.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    after_recs = catalog.load()
    after = hashlib.sha256(
        _json.dumps([x.get("purpose") for x in after_recs], ensure_ascii=False).encode()).hexdigest()
    check("重跑 label_purpose 后数据不变", before == after,
          f"{len(clobber)} 条已有值但规则读不出" if before != after else "")


def main():
    check_rule_does_not_clobber()

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 1500, "height": 950})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(URL, wait_until="load")
        pg.wait_for_timeout(900)

        print("\n[筛选组存在]")
        n_opt = pg.locator("#fPurpose .fopt").count()
        check("用途选项数 = 数据里的用途数", n_opt == len(MARKED), f"{n_opt} vs {len(MARKED)}")
        check("每组选项有分组标记",
              pg.locator('#fPurpose .fopt[data-g="purpose"]').count() == len(MARKED))

        print("\n[缺口披露]")
        gap = pg.locator("#fPurpose .fgap").inner_text() if pg.locator("#fPurpose .fgap").count() else ""
        check("说明了未判定的条数", str(BLANK) in gap.replace(",", ""), gap[:60])

        print(f"\n[点选筛得动：{TOP}]")
        pg.click(f'#fPurpose .fopt[data-v="{TOP}"]')
        pg.wait_for_timeout(500)
        cnt = pg.locator(".card").count()
        check(f"筛「{TOP}」得 {TOP_N} 条", cnt == TOP_N, f"实际 {cnt}")
        check("左栏该项显示为选中",
              pg.locator(f'#fPurpose .fopt[data-v="{TOP}"].on').count() == 1)
        check("出现可移除的 chip", pg.locator(".chip").count() >= 1)

        print("\n[未判定的不混进来]")
        check("总数小于全库", cnt < len(RECS), f"{cnt} < {len(RECS)}")

        print("\n[与其它轴叠加]")
        pg.click('#fKind .fopt[data-v="book"]')
        pg.wait_for_timeout(400)
        books = sum(1 for r in RECS
                    if vocab.normalize(r.get("purpose")) == TOP and r["kind"] == "小册子")
        check("叠加体裁后条数正确", pg.locator(".card").count() == books,
              f"实际 {pg.locator('.card').count()} 应为 {books}")
        pg.click('#fKind .fopt[data-v="book"]')
        pg.wait_for_timeout(400)

        print("\n[从 chip 移除]")
        pg.click(".chip button")
        pg.wait_for_timeout(400)
        check("移除后回到全量", pg.locator(".card").count() == len(RECS),
              pg.locator(".card").count())

        print("\n[URL 记忆]")
        pg.click(f'#fPurpose .fopt[data-v="{TOP}"]')
        pg.wait_for_timeout(400)
        hash_now = pg.evaluate("location.hash")
        check("用途写进了 URL", "pu=" in hash_now, hash_now[:70])
        pg.reload(wait_until="load")
        pg.wait_for_timeout(900)
        check("重载后仍筛选", pg.locator(".card").count() == TOP_N,
              pg.locator(".card").count())
        check("重载后选中态还在",
              pg.locator(f'#fPurpose .fopt[data-v="{TOP}"].on').count() == 1)

        print("\n[重置]")
        pg.click("#reset")
        pg.wait_for_timeout(400)
        check("重置回全量", pg.locator(".card").count() == len(RECS))

        print("\n[列表视图显示用途]")
        pg.click('button[data-view="list"]')
        pg.wait_for_timeout(500)
        check("列表行存在", pg.locator(".row").count() > 0)
        check("列表里有用途标记", pg.locator(".row .r-pu").count() > 0,
              pg.locator(".row .r-pu").count())

        print("\n[阅读器显示用途]")
        pg.click('button[data-view="grid"]')
        pg.wait_for_timeout(400)
        pg.locator(".card").first.click()
        pg.wait_for_timeout(700)
        meta = pg.inner_text("#rdMeta")
        check("信息栏有「用途」一行", "用途" in meta, meta[:80])
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)

        print("\n[搜索]")
        pg.fill("#q", TOP)
        pg.wait_for_timeout(500)
        check(f"搜「{TOP}」有结果", pg.locator(".card").count() >= TOP_N - 2,
              pg.locator(".card").count())

        print("\n[运行期错误]")
        print("  JS 异常:", errs or "无")
        if errs:
            fails.append("JS 错误")
        b.close()

    print("\n" + ("全部通过" if not fails else "失败：" + "、".join(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
