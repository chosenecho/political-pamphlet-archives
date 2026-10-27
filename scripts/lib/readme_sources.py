"""README 里那节「已核实的 N 个专藏（节选）」的单一来源。

为什么单独成一个模块
    README 的节选表是手抄的，`data/sources.json` 是权威的。两份一旦分开维护就会
    漂：名称改了口径、地区从 UK 改成英文、规模注记被缩写到意思变样，都没人发现。
    PR #3 的审核为此点过名，但当时只建议「另开 PR 处理」，于是照旧漂着。

    现在把「节选哪几行、每行怎么渲染」收进这里，README 里的那一节由
    `scripts/tools/update_readme_sources.py` 整节重写，`audit_readme.py` 用它
    反查是否一致。两边共用同一份生成函数，就不会再各说各话。

地区显示
    早期 `data/sources.json` 的 `region` 混用 ISO 代码与中文名，本模块曾自带
    一份 REGION_ZH 做显示层转换。现在数据已统一为中文名（见 `lib/regions.py`
    与 `tools/normalize_regions.py`），转换交给 `regions.to_zh()`，本模块不再
    维护第二份表——两份表正是漂移的来源。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import regions


#: 节选哪几条，以及分几个小标题。顺序即 README 里的顺序。
#: 用 slug 而不是名称做键：名称会变，slug 不会。
SECTIONS = [
    ("综合与聚合入口", [
        "social-history-portal",
        "jstor-19c-british-pamphlets",
    ]),
    ("党档案馆（往往比国家馆更全）", [
        "fes-adsd",
        "kas-archiv-bibliothek",
        "fpabloiglesias",
        "phm-labour-history-archive",
    ]),
    ("社会运动与冷战专门机构", [
        "iisg-collections",
        "sozialarchiv-zuerich",
        "osa-archivum",
        "vga-wien",
    ]),
    ("亚洲与拉美", [
        "modernhistory-cn",
        "ohara-institute",
        "loc-newdelhi-pamphlets",
        "memoria-chilena-panfletos",
    ]),
]


def all_slugs():
    return [s for _title, slugs in SECTIONS for s in slugs]


def excerpt_rows(sources):
    """按 SECTIONS 取出要展示的记录；缺 slug 时报错而不是静默少一行。"""
    by_slug = {s["slug"]: s for s in sources}
    missing = [s for s in all_slugs() if s not in by_slug]
    if missing:
        raise KeyError(f"sources.json 缺少这些 slug：{'、'.join(missing)}")
    return by_slug


def render(sources):
    """生成 README 那一节的 Markdown（不含二级标题）。

    每行的「规模」列一律取 sources.json 的 note。note 为空时留「—」，
    不拿别处的描述来填——那样又会出现「README 有、数据无」的漂移。
    """
    by_slug = excerpt_rows(sources)
    out = []
    for title, slugs in SECTIONS:
        out.append(f"**{title}**")
        out.append("")
        out.append("| 专藏 | 地区 | 规模 |")
        out.append("|---|---|---|")
        for slug in slugs:
            s = by_slug[slug]
            note = (s.get("note") or "").strip() or "—"
            out.append(f"| [{s['title']}]({s['url']}) | "
                       f"{regions.to_zh(s.get('region'))} | {note} |")
        out.append("")
    return "\n".join(out).rstrip("\n")
