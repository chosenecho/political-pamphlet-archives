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

#: 文案替换表。键是旧串，值是统一后的新串；重复执行不会叠加。
def normalize_title(s):
    """把站名的任何中间态与重复嵌套统一成 TITLE_ZH，且只留一层。

    做法：把「已知中间态」与「任意层叠的目标值」全部抹成空串，最后统一插入
    一次 TITLE_ZH。抹除比替换更安全——替换会让目标值里含有的子串再匹配一次，
    这正是之前叠成「歷史宣傳歷史宣傳材料檔案」的原因。
    """
    # 先把已叠的任何层数清掉：循环剥掉最外层的「歷史宣傳」，剩一个完整目标值
    while TITLE_ZH + TITLE_ZH in s:
        s = s.replace(TITLE_ZH + TITLE_ZH, TITLE_ZH)
    # 把「歷史宣傳」重复前缀压掉：歷史宣傳*N 材料檔案 -> 歷史宣傳材料檔案
    s = re.sub(r"(?:歷史宣傳)+(歷史宣傳材料檔案)", r"\1", s)
    # 中间态直接换成目标值（此步之后 TITLE_ZH 已不含待替换子串）
    for mid in ("政黨宣傳品檔案", "材料檔案", "材料档案"):
        s = s.replace(mid, TITLE_ZH)
    # 上一步可能又叠（材料檔案 是 TITLE_ZH 的子串），再压一次
    while TITLE_ZH + TITLE_ZH in s:
        s = s.replace(TITLE_ZH + TITLE_ZH, TITLE_ZH)
    s = re.sub(r"(?:歷史宣傳)+(歷史宣傳材料檔案)", r"\1", s)
    return s


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
