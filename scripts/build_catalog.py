"""生成交互式目录与阅读器：docs/index.html。

模板与数据分离：模板在 scripts/templates/catalog.html，用 __NAME__ 占位符替换，
不做任何模板语法的解析，因此 CSS/JS 里的花括号无需转义。

输入
    data/catalog.json   权威条目目录（受版本控制）
    data/sources.json   专藏清单，用于把 source slug 渲染成可点的馆藏名
输出
    docs/index.html     GitHub Pages 入口

图片相对 images/ 定位，images/ 不入库；前端在图片 404 时渲染排版封面而不是碎图。
"""

import hashlib
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

TEMPLATE = os.path.join(paths.SCRIPTS, "templates", "catalog.html")

#: docs/index.html 相对 images/ 的前缀。图片不入库，缺失时前端回退为排版封面。
ASSET_PREFIX = "../images/"

#: 国别的固定次序模板里定义（前端排序用）；这里保留一份用于打印与自检，
#: 与模板不一致时构建会报错，免得新增国别后静默落到列表末尾。
COUNTRY_ORDER = ["中国", "日本", "印度", "拉美", "俄国", "德国", "奥地利", "捷克",
                 "波兰", "匈牙利", "荷兰", "英国", "爱尔兰", "法国", "西班牙",
                 "葡萄牙", "意大利", "美国"]


def load_records():
    recs = catalog.load()
    if not recs:
        raise SystemExit(f"找不到 {paths.CATALOG}，请先运行 scripts/migrate_catalog.py")
    return recs


def load_sources():
    """slug -> {t: 展示名, u: 入口}；文件缺失时返回空表，页面退化为显示 slug。"""
    if not os.path.exists(paths.SOURCES):
        return {}
    with open(paths.SOURCES, encoding="utf-8") as f:
        raw = json.load(f).get("sources", [])
    out = {}
    for s in raw:
        out[s["slug"]] = {"t": s.get("title", s["slug"]), "u": s.get("url", "")}
    return out


def build_payload(recs):
    """把目录记录压成前端用的小键对象，并丢掉全空字段以省体积。"""
    rows = []
    for i, r in enumerate(recs):
        d = {
            "i": i,
            "k": "book" if r["kind"] == catalog.KIND_BOOK else "single",
            "c": r["country"],
            "y": r["year"],
            "t": r["title"],
            "tz": r["title_zh"],
            "n": r["pages"] or 1,
            "d": r["dir"],
            "cv": r["cover"],
            "st": r["stance"],
            "s": r["source"],
        }
        # 没有的值不写键，前端一律按 "" 处理
        if r["pdf"]:
            d["pdf"] = r["pdf"]
        if r["url"]:
            d["u"] = r["url"]
        rows.append(d)
    return rows


def build_stats(recs):
    books = [r for r in recs if r["kind"] == catalog.KIND_BOOK]
    countries = {r["country"] for r in recs if r["country"]}
    return {
        "total": len(recs),
        "books": len(books),
        "singles": len(recs) - len(books),
        "countries": len(countries),
        "pages": sum(r["pages"] for r in books),
        "stances": len({r["stance"] for r in recs if r["stance"]}),
        "sources": len({r["source"] for r in recs if r["source"]}),
    }


def main():
    recs = load_records()
    sources = load_sources()
    data = build_payload(recs)
    stats = build_stats(recs)

    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()

    # 只注入被引用到的来源，避免把整份 38 条清单塞进页面
    used = {d["s"] for d in data if d["s"]}
    srcs = {k: v for k, v in sources.items() if k in used}

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # </script> 出现在标题里会提前闭合脚本块
    payload = payload.replace("</", "<\\/")

    # 页面标识用数据指纹，不用构建时间：同一份数据必须产出同一份 HTML，
    # 否则 CI 的「产物与提交一致」校验每次都失败。
    stamp = "目录 " + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]

    out = (html
           .replace("__ASSET__", ASSET_PREFIX)
           .replace("__DATA__", payload)
           .replace("__STATS__", json.dumps(stats, ensure_ascii=False))
           .replace("__SOURCES__", json.dumps(srcs, ensure_ascii=False, separators=(",", ":")))
           .replace("__BUILD__", stamp))

    leftover = [t for t in ("__ASSET__", "__DATA__", "__STATS__", "__SOURCES__", "__BUILD__")
                if t in out]
    if leftover:
        raise SystemExit(f"模板占位符未替换：{'、'.join(leftover)}")

    # 模板里的国别次序必须与这里的常量一致：新增国别却只改了一处时，构建直接失败，
    # 而不是让它在筛选栏里静默落到末尾。
    import re

    m = re.search(r"const COUNTRY_ORDER = \[(.*?)\];", html, re.S)
    tpl_order = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    if tpl_order != COUNTRY_ORDER:
        only_tpl = [c for c in tpl_order if c not in COUNTRY_ORDER]
        only_py = [c for c in COUNTRY_ORDER if c not in tpl_order]
        raise SystemExit(
            "国别次序在模板与 build_catalog.py 里不一致："
            f"仅模板有 {only_tpl}，仅脚本有 {only_py}")

    paths.ensure_dir(paths.DOCS)
    with open(paths.SITE, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)

    order = [c for c in COUNTRY_ORDER if any(d["c"] == c for d in data)]
    # 数据里出现但次序表没有的国别：打印出来提醒补进表里
    unlisted = [c for c in sorted({d["c"] for d in data}) if c not in order]
    order += unlisted

    total = len(recs)
    gaps = [f"{k} {v}/{total}" for k, v in (
        ("立场未标", sum(1 for r in recs if not r["stance"])),
        ("来源未归属", sum(1 for r in recs if not r["source"])),
        ("年份不详", sum(1 for r in recs if not r["year"])),
        ("无 PDF", sum(1 for r in recs if not r["pdf"])),
    )]

    print(f"docs/index.html：小册子 {stats['books']} 本、单页 {stats['singles']} 件；"
          f"国家 {stats['countries']} 个、立场 {stats['stances']} 种；"
          f"来源覆盖 {stats['sources']} 个专藏")
    print(f"缺口 {' · '.join(gaps)}")
    if unlisted:
        print(f"⚠ 次序表未收录的国别（已排到末尾）：{'、'.join(unlisted)}"
              f"——请补进 templates/catalog.html 与 build_catalog.py 的 COUNTRY_ORDER")
    print(f"数据指纹 {stamp}")
    print(f"体积 {os.path.getsize(paths.SITE) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
