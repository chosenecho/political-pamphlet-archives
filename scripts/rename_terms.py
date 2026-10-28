"""统一改称（可重复执行）：把面向读者的「政党宣传品」表述改为「材料」。

注意：本文件自身必然含有旧称——替换表必须写出旧串才谈得上替换。
这是全仓唯一允许出现该词的文件；其余文件由 audit() 兜底检查。

背景：并行会话会把同一批文件改回旧版，所以这个脚本必须可重复执行，
跑几遍都得到同一结果（幂等），并与构建绑定成一步。

边界（已与用户确认）
  改：站名、标题、页面描述、README 标题与缺口描述、sources.json 的专藏名与 scope
  不改：免责声明里「不代表任何政党、组织或政治立场」——那是否定式的中立表述，
        是法律边界；也不改馆藏描述里对史实的陈述（「藏有大量政党、工会的ビラ」）。
"""

import json
import os
import re
import sys

# 本脚本在 scripts/ 下，向上两级是仓库根
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLE_ZH = "歷史宣傳材料檔案"
TITLE_CN = "历史宣传材料档案"

#: 站位符：把完整站名先挖走，碎片替换就碰不到它内部了。
#: 用 \x00 包住，正常文本里不可能出现。
_SENTINEL = "\x00TITLE\x00"

#: 完整站名的已有写法，先整体挖掉
_FULL_FORMS = (TITLE_ZH, TITLE_CN)

#: 碎片：旧站名、半截中间态、以及站名自身的简繁前缀。
#: 这些串**都可能是完整站名的子串**，所以必须在上一步之后才处理。
_FRAGMENTS = (
    "政黨宣傳品檔案", "政党宣传品档案",
    "材料檔案", "材料档案",
    "歷史宣傳", "历史宣传",
)


def normalize_title(s):
    """把站名的任何中间态与重复嵌套统一成 TITLE_ZH，且只留一层。

    做法分四步：
      1. 先把**完整站名**（简繁两种写法）换成占位符。这一步是关键：不先挖走，
         后面的碎片替换会命中完整站名内部的「材料檔案」，替换出新的一份完整
         站名，叠成「歷史宣傳 + 歷史宣傳材料檔案」。
      2. 剩下的都是碎片，逐个换成占位符。任意层叠因此自然坍缩成一层。
      3. 连续占位符压成一个。
      4. 占位符还原成 TITLE_ZH。

    早先的实现直接在整串上替换「材料檔案」「材料档案」，并用正则
    r"(?:歷史宣傳)+(歷史宣傳材料檔案)" 压叠。那个正则只认繁体前缀，压不掉
    「历史宣传」+「歷史宣傳材料檔案」这种简繁混写——make_bundle.py 生成的
    文件名就是这样变成「历史宣传歷史宣傳材料檔案-精简版-3999件.zip」的。
    """
    for form in _FULL_FORMS:
        s = s.replace(form, _SENTINEL)
    for frag in _FRAGMENTS:
        s = s.replace(frag, _SENTINEL)
    while _SENTINEL + _SENTINEL in s:
        s = s.replace(_SENTINEL + _SENTINEL, _SENTINEL)
    return s.replace(_SENTINEL, TITLE_ZH)


PAIRS = [
    # —— 对外文案 ——（站名由 normalize_title 单独处理，不放这里）
    ("政党宣传品档案-", TITLE_CN + "-"),
    ("政党宣传品 · 分类目录", "材料 · 分类目录"),
    ("政党宣传品图像集", "材料图像集"),
    ("政党与政治派系宣传品", "政治组织与政治派系材料"),

    # —— 对外描述 ——
    ("十九至二十世纪政党、政治家与政治派系散发的宣传小册子",
     "十九至二十世纪政治组织、政治家与政治派系散发的宣传小册子"),
    ("十九至二十世纪政党、政治家、政治派系散发的宣传小册子",
     "十九至二十世纪政治组织、政治家、政治派系散发的宣传小册子"),
    ("所收录材料为十九至二十世纪各政党与派系的宣传品，包含",
     "所收录材料为十九至二十世纪各政治组织与派系散发的材料，包含"),
    ("所收录材料为十九至二十世纪各政党与派系的宣传品，其中包含",
     "所收录材料为十九至二十世纪各政治组织与派系散发的材料，其中包含"),
    ("所收录材料为历史宣传品，", "所收录材料为历史材料，"),
    ("政治宣传品的色彩由实物自己提供", "这些材料的色彩由实物自己提供"),
    ("这件宣传品的图像不在本机", "这件材料的图像不在本机"),
    ("极具争议的历史宣传品，", "极具争议的历史材料，"),
    ("政党宣传品在图书馆目录里通常不按主题标引",
     "这类材料在图书馆目录里通常不按主题标引"),
    ("民族主义政党宣传品尚未覆盖", "民族主义政党的宣传材料尚未覆盖"),
    ("没有一条合格的政党宣传小册子", "没有一条合格的多页宣传材料"),
    ("按母语种与政党名多轮检索", "按母语种与组织名多轮检索"),

    # —— data/sources.json 里 IA 条目的专藏名（会被页面读出来展示）——
    ('"title": "Internet Archive · 政党与政治宣传品扫描件"',
     f'"title": "Internet Archive · 政治组织与政治材料扫描件"'),
    ('"note": "各国图书馆扫描并托管于 IA 的政党小册子、竞选材料与费边社小册；',
     '"note": "各国图书馆扫描并托管于 IA 的政治组织小册子、竞选材料与费边社小册；'),
    ('"scope": "19-20 世纪政党、政治家、政治派系的宣传小册子/传单/海报/竞选材料专藏"',
     '"scope": "19-20 世纪政治组织、政治家、政治派系的宣传小册子/传单/海报/竞选材料专藏"'),
]

TARGETS = [
    "scripts/templates/catalog.html",
    "README.md",
    "DISCLAIMER.md",
    "docs/FINDING-AIDS.md",
    "data/sources.json",
    "scripts/make_bundle.py",
    "scripts/organize_images.py",
    "scripts/archive/build_gallery.py",
]


def apply():
    grand = 0
    for rel in TARGETS:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        s = open(path, encoding="utf-8").read()
        orig = s
        s = normalize_title(s)
        for old, new in PAIRS:
            if old in s:
                s = s.replace(old, new)
        if s != orig:
            open(path, "w", encoding="utf-8", newline="\n").write(s)
            grand += 1
            print(f"  改 {rel}")
        if rel.endswith(".json"):
            json.loads(s)                      # 改完仍须是合法 JSON
    return grand


def audit():
    """面向读者的文件里不该再有「政党宣传品 / 政黨宣傳品」。"""
    bad = []
    for rel in ("README.md", "docs/index.html", "docs/FINDING-AIDS.md",
                "docs/COLLECTIONS.md", "data/index.csv", "data/sources.json",
                "scripts/templates/catalog.html"):
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        s = open(path, encoding="utf-8").read()
        n = s.count("政党宣传品") + s.count("政黨宣傳品")
        if n:
            bad.append(f"{rel}({n})")
    return bad


if __name__ == "__main__":
    changed = apply()
    print(f"共改 {changed} 个文件")
    problems = audit()
    if problems:
        print("仍有残留：" + "、".join(problems), file=sys.stderr)
        sys.exit(1)
    print("面向读者的文件已无「政党宣传品」")
