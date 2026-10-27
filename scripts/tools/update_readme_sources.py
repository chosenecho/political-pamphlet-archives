"""把 README 里随数据变化的表述整节重写，避免手抄表与 data/ 各说各话。

管两件事：
  1. 「## 已核实的 N 个专藏（节选）」整节 —— 由 lib/readme_sources.render() 生成，
     名称/地区/规模全部取自 data/sources.json。手改 README 没有意义，
     下次跑这个脚本会覆盖回去；要改内容请改 sources.json 或那个模块的 SECTIONS。
  2. 散落在正文里的计数（N 个专藏、manifest 覆盖数、source 回填比）——
     一律按当前数据实算，不写字面量。

幂等：连跑多次结果一致。挂在 build_catalog.py 之后由人手动跑，或直接跑本脚本。
"""

import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import readme_sources

README = os.path.join(BASE, "README.md")
SECTION_HEAD = "## 已核实的"
SECTION_NEXT = "## 检索提示"


def load_data():
    sources = json.load(open(os.path.join(BASE, "data", "sources.json"),
                             encoding="utf-8"))["sources"]
    catalog = json.load(open(os.path.join(BASE, "data", "catalog.json"),
                             encoding="utf-8"))
    manifest = json.load(open(os.path.join(BASE, "data", "manifest.json"),
                              encoding="utf-8"))
    return sources, catalog, manifest


def rewrite_excerpt_section(text, sources):
    """替换整节。找不到边界就报错——静默不动会让人以为改成功了。"""
    lines = text.split("\n")
    start = next((i for i, l in enumerate(lines) if l.startswith(SECTION_HEAD)), None)
    end = next((i for i, l in enumerate(lines) if l.startswith(SECTION_NEXT)), None)
    if start is None or end is None or end <= start:
        raise SystemExit(f"README 里找不到「{SECTION_HEAD}」到「{SECTION_NEXT}」这一节，"
                         f"start={start} end={end}")

    body = readme_sources.render(sources)
    new = [f"{SECTION_HEAD} {len(sources)} 个专藏（节选）", "",
           "完整表见 [`docs/COLLECTIONS.md`](docs/COLLECTIONS.md)。"
           "跨地区的几组：", ""]
    new += body.split("\n")
    # 本节末尾补一个空行，与下一节隔开
    new += [""]
    return "\n".join(lines[:start] + new + lines[end:])


def sync_counts(text, sources, catalog, manifest):
    """正文里的计数改为实算值。

    这些句子散在各处且措辞会变，所以只替换「数字」，不重写整句：
    锚点用句子里的固定词，数字部分用 \\d+。
    """
    nsrc = len(sources)
    man = {r["slug"] for r in manifest}
    covered = sum(1 for s in sources if s["slug"] in man)
    notried = nsrc - covered
    linked = sum(1 for r in catalog if r.get("source"))
    total = len(catalog)
    # 只能按 URL 唯一判定的才算「可归属」；其余留空
    unlinked = total - linked

    subs = [
        (r"仓库把 \d+ 个已有数字化或可检索的专藏整理成一张表",
         f"仓库把 {nsrc} 个已有数字化或可检索的专藏整理成一张表"),
        (r"\*\*\d+ 个专藏\*\*的清单",
         f"**{nsrc} 个专藏**的清单"),
        (r"\d+ 个专藏的可点击清单与抓取状态",
         f"{nsrc} 个专藏的可点击清单与抓取状态"),
        (r"\d+ 个专藏中：\d+ 个抓到可读正文，\d+ 个只有说明文件（403/429），"
         r"\d+ 个仅登记入口、正文待取。`data/manifest\.json` 覆盖 \d+/\d+ 个源，"
         r"其余 \d+ 个尚未尝试。",
         f"{nsrc} 个专藏中：{_count_status(sources)}。"
         f"`data/manifest.json` 覆盖 {covered}/{nsrc} 个源，"
         f"其余 {notried} 个尚未尝试。"),
        (r"目前回填 \d+/\d+ 条",
         f"目前回填 {linked}/{total} 条"),
        (r"剩下 \d+ 条的 `url` 只记到站点根",
         f"剩下 {unlinked} 条的 `url` 只记到站点根"),
    ]
    for pat, rep in subs:
        text, n = re.subn(pat, rep, text)
        if n == 0:
            print(f"  ！未匹配：{pat[:40]}…")
    return text


def _count_status(sources):
    """按 notes/ 正文字符数复算三类状态，与 build_index.py 同口径。"""
    ok = part = only = 0
    for s in sources:
        p = os.path.join(BASE, "notes", s["slug"] + ".txt")
        if os.path.exists(p):
            n = len(io.open(p, encoding="utf-8", errors="replace").read())
            if n > 500:
                ok += 1
            else:
                part += 1
        else:
            only += 1
    return f"{ok} 个抓到可读正文，{part} 个只有说明文件（403/429），{only} 个仅登记入口、正文待取"


def main():
    sources, catalog, manifest = load_data()
    text = io.open(README, encoding="utf-8").read()
    orig = text

    text = sync_counts(text, sources, catalog, manifest)
    text = rewrite_excerpt_section(text, sources)

    if text != orig:
        io.open(README, "w", encoding="utf-8", newline="\n").write(text)
        print("README 已更新")
    else:
        print("README 无需改动")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
