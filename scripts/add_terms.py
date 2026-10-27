"""给每个专藏补上当地语言的检索词，并生成检索手册。

语言判定不再由本脚本自带映射，改从 scripts/lib/regions.py 取——那里同时
管着 region 的词表。早先两处各存一份，新增国别只改了一处就会静默退回英文。
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import regions

P = os.path.join(BASE, "data", "sources.json")

# 语言 → 检索词（体裁词优先，因为编目按体裁标引）
TERMS = {
    "en": ["pamphlet", "leaflet", "handbill", "broadside", "tract",
           "campaign literature", "election address", "election platform"],
    "de": ["Flugschrift", "Flugblatt", "Broschüre", "Wahlaufruf",
           "Wahlprogramm", "Parteiprogramm", "Handzettel"],
    "fr": ["brochure", "tract", "profession de foi", "affiche", "feuille volante"],
    "it": ["opuscolo", "volantino", "manifesto", "programma elettorale"],
    "es": ["folleto", "panfleto", "hoja volante", "cartel", "programa electoral"],
    "pt": ["folheto", "panfleto", "cartaz", "profissão de fé"],
    "ru": ["брошюра", "листовка", "программа партии", "воззвание"],
    "pl": ["broszura", "ulotka", "plakat wyborczy", "program wyborczy"],
    "cs": ["brožura", "leták", "volební program"],
    "nl": ["brochure", "pamflet", "vlugschrift", "verkiezingsprogramma"],
    "sv": ["broschyr", "pamflett", "valprogram"],
    "hu": ["röpirat", "brosúra", "választási program"],
    "ja": ["パンフレット", "ビラ", "選挙公報", "政綱"],
    "zh": ["小册子", "传单", "宣传品", "标语", "宣言"],
}

data = json.load(open(P, encoding="utf-8"))
upd = 0
filled = 0
unknown = []
for s in data["sources"]:
    lang = regions.language_of(s.get("region"))
    if lang is None:
        # 不兜底成 en：那会让新增国别「看起来正常」却拿到错误的检索词
        unknown.append((s["slug"], s.get("region")))
        continue
    s["lang"] = lang
    # terms 只在缺失时按语言填。已有的不覆盖——有的专藏手写过更贴切的词
    # （internet-archive 的 `Fabian tract`、wiki-commons 的 7 个海报词），
    # 无条件覆盖会把它们冲成通用英文词，是内容损失而非整理。
    if not s.get("terms"):
        s["terms"] = TERMS.get(lang, TERMS["en"])
        filled += 1
    upd += 1

if unknown:
    print("⚠ 这些条目的 region 在 regions.py 里查不到语言，未改动：")
    for slug, region in unknown:
        print(f"   {slug}  region={region!r}")
    sys.exit(1)

with open(P, "w", encoding="utf-8", newline="\n") as f:
    # indent=2 与既有格式一致；indent=1（json 默认）会重排整个文件
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\n")

# 生成检索手册
L = ["# 检索手册", "",
     f"这份索引里 {len(data['sources'])} 个专藏的编目方式各不相同。"
     "真正决定能否找到的，是**用当地语言的体裁词**去检索，"
     "而不是把「小册子」直译成英文。", "",
     "## 一、按语言查体裁词", "",
     "| 语言 | 检索词 |", "|---|---|"]
for code, terms in TERMS.items():
    L.append(f"| {code} | {' · '.join('`'+t+'`' for t in terms)} |")

L += ["", "## 二、为什么用体裁词", "",
      "这类材料在图书馆目录里通常不按主题标引，而是单独设一个馆藏位置或体裁字段：",
      "",
      "- 英美编目：著录为 `Pamphlets`、`Tracts`、`Campaign literature`、`Broadsides`，"
      "或位置字段写 `Pamphlet` / `Tracts` 专架",
      "- 德语区：`Flugschrift`（传单式论著）、`Flugblatt`（单页传单）、`Broschüre` 分列",
      "- 法语区：`tract` 指街头散发的传单，`brochure` 指装订小册，二者不通用",
      "- 东亚：中文用「小册子／传单／宣传品」，日文用「パンフレット／ビラ」，"
      "「ビラ」特指街头传单",
      "",
      "## 三、按出版机构反查", "",
      "命中率最高的一招：直接检索党的出版社。",
      "",
      "| 机构 | 归属 |", "|---|---|",
      "| Dietz Verlag | 德国社民党／东德统一社会党 |",
      "| Vorwärts | 德国社民党机关 |",
      "| Lawrence & Wishart | 英国共产党 |",
      "| Victor Gollancz | 英国左翼读书会 |",
      "| Editions Sociales | 法国共产党 |",
      "| Foreign Languages Press | 中国外文局 |",
      "| 人民出版社 / 新华书店 / 东北书店 | 中共系统 |",
      "| Cooperative Press / Kerr | 美国社会主义者 |",
      "",
      "## 四、各类型专藏的检索入口差异", "",
      "| 类型 | 怎么查 | 举例 |", "|---|---|---|",
      "| 国家图书馆 | 馆藏目录按体裁词 + 出版年 | BnF、ÖNB、NDL |",
      "| 党档案馆 | 先查 Bestandsübersicht／finding aid，再调档 | FES AdsD、KAS ACDP、Pablo Iglesias |",
      "| 社会运动机构 | 按组织名查全宗，传单多在系列内 | IISH、Schweizerisches Sozialarchiv、BAM |",
      "| 聚合门户 | 跨馆一次检索 | Social History Portal (IALHI) |",
      "| 商业库 | 按专题子集浏览 | Gale《Political Extremism and Radicalism》 |",
      "",
      "## 五、三个容易忽略的线索", "",
      "1. **警察与情报档案**：被查扣的传单大量留存在 PIDE（葡萄牙）、Stasi（东德）、"
      "沙俄 Okhrana 档案里，往往是某份传单唯一存世的副本。",
      "2. **地方档案馆**：选区一级的竞选传单几乎只存在于郡／省级档案馆，国家级馆不收。",
      "3. **党代表大会文件**：党纲与竞选纲领通常作为代表大会文件的一部分印刷，"
      "查会议记录（Proceedings／Protokolle／Compte rendu）能连带找到。",
      "",
      "---", "",
      "> 声明：本手册由 AI 辅助整理，仅供学术研究与交流，不对使用后果负责。"
      "检索词、界面与馆藏状态随时会变，请以各馆现行界面为准；"
      "如有错误或版权问题，提出后立即更正或移除。"
      "完整条款见 [DISCLAIMER.md](../DISCLAIMER.md)。", ""]

os.makedirs(os.path.join(BASE, "docs"), exist_ok=True)
# newline="\n"：Windows 上默认会把 \n 转成 \r\n，产物与提交就对不上了
with open(os.path.join(BASE, "docs", "FINDING-AIDS.md"), "w",
          encoding="utf-8", newline="\n") as f:
    f.write("\n".join(L))

print(f"已核对 {upd} 个专藏的语言，其中 {filled} 个按语言补了检索词"
      f"（其余保留手写词），生成 docs/FINDING-AIDS.md（{len('\n'.join(L))} 字符）")
