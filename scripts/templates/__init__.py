"""模板装配：线上页面与离线包共用同一份模板，只换数据与路径规则。

两个构建器（build_catalog.py 生成 docs/index.html，make_bundle.py 生成
离线包）必须对同一份模板做同一套替换，否则一边改了占位符、另一边忘了，
出来的是两种页面。这里把替换逻辑收成一处。
"""

import hashlib
import json
import os
import re

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog.html")

PLACEHOLDERS = ("__ASSET__", "__DATA__", "__STATS__", "__SOURCES__", "__BUILD__",
                "__PAGE_DIR__", "__PAGE_PREFIX__", "__PAGE_EXT__", "__PAGE_PAD__")


def load():
    with open(TEMPLATE, encoding="utf-8") as f:
        return f.read()


def country_order():
    """从模板读出固定的国别次序，供构建器核对自身的常量。"""
    html = load()
    m = re.search(r"const COUNTRY_ORDER = \[(.*?)\];", html, re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


def render(rows, stats, sources, asset_prefix, page_rule, stamp_prefix="目录"):
    """把数据与路径规则灌进模板，返回 HTML 文本。

    rows        前端用的条目数组
    stats       顶部统计条
    sources     slug -> {t, u}
    asset_prefix 图像根前缀；离线包为 ""（图像就在页面同级）
    page_rule   {"dir","prefix","ext","pad"}，值需已带 JS 引号
    """
    html = load()
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    stamp = (stamp_prefix + " "
             + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10])

    out = (html
           .replace("__ASSET__", asset_prefix)
           .replace("__DATA__", payload)
           .replace("__STATS__", json.dumps(stats, ensure_ascii=False))
           .replace("__SOURCES__", json.dumps(sources, ensure_ascii=False,
                                              separators=(",", ":")))
           .replace("__BUILD__", stamp)
           .replace("__PAGE_DIR__", page_rule["dir"])
           .replace("__PAGE_PREFIX__", page_rule["prefix"])
           .replace("__PAGE_EXT__", page_rule["ext"])
           .replace("__PAGE_PAD__", page_rule["pad"]))

    leftover = [t for t in PLACEHOLDERS if t in out]
    if leftover:
        raise SystemExit(f"模板占位符未替换：{'、'.join(leftover)}")
    return out, stamp
