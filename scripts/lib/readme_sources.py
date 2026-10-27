"""README 里那节「已核实的 N 个专藏（节选）」的单一来源。

为什么单独成一个模块
    README 的节选表是手抄的，`data/sources.json` 是权威的。两份一旦分开维护就会
    漂：名称改了口径、地区从 UK 改成英文、规模注记被缩写到意思变样，都没人发现。
    PR #3 的审核为此点过名，但当时只建议「另开 PR 处理」，于是照旧漂着。

    现在把「节选哪几行、每行怎么渲染」收进这里，README 里的那一节由
    `scripts/tools/update_readme_sources.py` 整节重写，`audit_readme.py` 用它
    反查是否一致。两边共用同一份生成函数，就不会再各说各话。

地区为什么在渲染层转换
    `sources.json` 的 `region` 取值是混用的（`UK`/`US`/`DE` 是代码，`智利`/`跨国`
    是中文名，另有 `US/UK`、`俄/美` 这类复合值），24 个取值 40 条记录。直接改成
    全中文会牵动 `add_terms.py` 的 REGION_LANG 映射与 docs/COLLECTIONS.md 的
    既有显示，属于另一件事。所以这里只做**显示层转换**：数据不动，README 里显示
    中文。REGION_ZH 里没有的值原样输出，新增国别不会静默消失。
"""

#: sources.json 的 region 代码 → README 显示用的中文名。
#: 只覆盖代码型取值；中文型取值（智利、跨国、欧洲…）原样通过。
REGION_ZH = {
    "UK": "英国",
    "US": "美国",
    "DE": "德国",
    "FR": "法国",
    "NL": "荷兰",
    "CH": "瑞士",
    "ES": "西班牙",
    "CN": "中国",
    "JP": "日本",
    "BE": "比利时",
    "PT": "葡萄牙",
    "PL": "波兰",
    "SE": "瑞典",
    "IT": "意大利",
    "RU": "俄国",
    "HU": "匈牙利",
    "AT": "奥地利",
    "CZ": "捷克",
}

#: 复合取值单独给，避免 "US/UK" 被逐段替换后变成 "美国/英国" 这类想当然的猜测。
#: 这里保留原始写法，因为它是「两地合藏」还是「跨国机构」本就说不清，
#: 交给读者自己判断比替它决定更好。
REGION_COMPOSITE = {
    "US/UK": "美/英",
    "俄/美": "俄/美",
    "印度/美": "印度/美",
}


def region_zh(region):
    """region 的显示名。未知取值原样返回，不吞、不猜。"""
    r = (region or "").strip()
    if r in REGION_COMPOSITE:
        return REGION_COMPOSITE[r]
    return REGION_ZH.get(r, r)


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
                       f"{region_zh(s.get('region'))} | {note} |")
        out.append("")
    return "\n".join(out).rstrip("\n")
