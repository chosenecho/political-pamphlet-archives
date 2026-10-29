"""从 Commons 分类回填瑞士批次的用途与部分立场。

背景
    瑞士 85 条里有 53 条的 `title_zh` 是当年为卡片不空白补的占位译名
    「瑞士选举海报（NNNN，作者）」，档案号 `CH-000957-X-*` 本身不含题材，
    所以 `label_purpose.py` 显式跳过它们，这 53 条 purpose 一直是空的。

    但这批条目在 Commons 上带着**结构化分类**，是可靠判据（不是我们生成的
    东西）。实测 54 条 CH-000957 里：

      Referendum posters in Switzerland   35 条
      Election posters in Switzerland     19 条
      —— 两者零冲突，每条恰好命中一个

      Anti-communism in Switzerland       14 条
      Social Democratic Party of Switz.    6 条
      Free Democratic Party of Switz.      3 条
      Liberal-Demokratische Partei         3 条
      —— 有 5 条同时命中「反共」与「自民党」

判定纪律
    1. **只补 purpose 与 stance，不动 title_zh。** 译名要重做是另一件事，
       混在一个提交里会让"这条译名对不对"和"这条用途对不对"搅在一起。
    2. **用途只看两个零冲突的分类。** 一条同时属于两个用途分类的，留空不猜。
    3. **立场有冲突时留空。** 同时命中「反共」与具体政党的 5 条，是"某党针对
       共产党的竞选海报"——现有 `stance` 是单值字段，装不下「政党 × 议题」
       两个维度（那正是要拆 `actor`/`agenda` 的理由）。硬选一个会让数据说谎，
       留空并在依据里写明冲突。
    4. 作者、许可、年份分类一律不作判据。

用法
    python scripts/enrich_swiss_categories.py --dry
    python scripts/enrich_swiss_categories.py
"""

import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http
from lib import index as catalog
from lib import vocab

API = "https://commons.wikimedia.org/w/api.php"

#: Commons 分类 -> 用途。只收**零冲突**的两个：实测 54 条里没有一条同时命中。
PURPOSE_FROM_CAT = {
    "Referendum posters in Switzerland": "公投动员",
    "Election posters in Switzerland": "竞选宣传",
}

#: Commons 分类 -> 立场。只在**没有冲突**时使用。
STANCE_FROM_CAT = {
    "Social Democratic Party of Switzerland": "社会民主党",
    "Free Democratic Party of Switzerland": "自由民主党",
    "Liberal-Demokratische Partei (Basel-Stadt)": "自由民主党",
    "Anti-communism in Switzerland": "反共宣传",
    "Christian Democratic People's Party of Switzerland": "基督教社会党",
}

#: 已知会造成语义冲突的组合：同时出现说明是「某党的反共材料」，
#: 组织与议题两层信息，单值 stance 装不下。这组一律留空。
CONFLICT_SETS = [
    {"反共宣传", "自由民主党"},
    {"反共宣传", "社会民主党"},
    {"反共宣传", "基督教社会党"},
]


def norm(s):
    """Commons 标题在 URL 里是下划线、在 API 返回里是空格，统一掉。"""
    return re.sub(r"[_\s]+", " ", urllib.parse.unquote(s or "")).strip().lower()


def fetch_categories(titles):
    """批量取 extmetadata 里的 Categories 与描述。

    返回 {Commons 标题: {"cats": [...], "desc": "..."}}。
    描述也取，是因为分类里的党名不一定是刊发者——见 COMMITTEE_HINT。
    """
    out = {}
    tag = re.compile(r"<[^>]+>")
    for i in range(0, len(titles), 10):
        chunk = titles[i:i + 10]
        params = {
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "extmetadata", "titles": "|".join(chunk),
        }
        try:
            d = http.fetch_json(API + "?" + urllib.parse.urlencode(params), timeout=60)
        except Exception as e:
            print(f"  批次 {i // 10 + 1} 失败：{type(e).__name__}: {e}")
            continue
        for page in (d.get("query") or {}).get("pages", {}).values():
            t = page.get("title")
            ii = (page.get("imageinfo") or [{}])[0]
            md = ii.get("extmetadata") or {}
            raw = (md.get("Categories") or {}).get("value") or ""
            desc = tag.sub(" ", str((md.get("ImageDescription") or {}).get("value") or ""))
            out[t] = {
                "cats": [c.strip() for c in raw.split("|") if c.strip()],
                "desc": re.sub(r"\s+", " ", desc).strip(),
            }
    return out


def commons_title(url):
    m = re.search(r"/wiki/File:(.+)$", url or "")
    return ("File:" + urllib.parse.unquote(m.group(1))) if m else None


#: 描述文本 -> 用途。用于**没有用途分类、但有描述**的条目。
#:
#: 瑞士这批的描述往往是海报原文（`Gerechtigkeit erhöht ein Volk,
#: Eidgenossen, am 13. Okt. stimmet: Ja!`），判据比中文译名可靠——那译名
#: 是我们自己写的。只收德语/法语表决用语与明确的选举词。
#:
#: 不收 `Freiheit, Schweiz` 这种只有口号的：它可能是竞选也可能是公投。
DESC_PURPOSE = [
    (re.compile(r"stimmet?\s*:?\s*(ja|nein)|abstimmung|volksbegehren|"
                r"votation|référendum|referendum|initiative", re.I), "公投动员"),
    (re.compile(r"wahl|élection|election|liste\s*\d|scrutin|"
                r"nationalrat|ständerat|candidat", re.I), "竞选宣传"),
]

#: 描述里的党名 -> 立场。与分类同构，但描述比分类更接近原件文本。
DESC_STANCE = [
    (re.compile(r"sozialdemokratisch|sozialdemokrat", re.I), "社会民主党"),
    (re.compile(r"freisinnig|radikal|liberal", re.I), "自由民主党"),
    (re.compile(r"bolschewis|bolchevis|kommunis", re.I), "反共宣传"),
]

#: 描述里出现这些词时，说明主体不是政党而是跨党派委员会/行动团体，
#: 此时分类里的党名属于「参与方」而非「刊发者」，不能拿来定 stance。
#:
#: 实例：`Bild Plakat Majorz Proporz.jpg` 的分类含
#: `Social Democratic Party of Switzerland`，但 Commons 描述写的是
#: 「Plakat des Schweizerischen Actions-Comités für den Nationalrats-Proporz」
#: ——它是跨党派的国民院比例代表制行动委员会海报，归给社民党不准确。
COMMITTEE_HINT = re.compile(
    r"Actions-?Comit|Action Committee|Komitee|Comité|"
    r"Aktionskomitee|committee|Kommission|Ligue|League|Bund\b",
    re.I)


def classify(cats, desc=""):
    """返回 (用途, 立场, 说明)。判不出的项为 ""。

    判据有优先级：**分类 > 描述**。分类是人工归类过的，描述是原件的题名
    转录，两者不一致时以分类为准。
    """
    notes = []

    purposes = {PURPOSE_FROM_CAT[c] for c in cats if c in PURPOSE_FROM_CAT}
    if len(purposes) > 1:
        notes.append(f"用途分类冲突 {sorted(purposes)}")
        purpose = ""
    elif purposes:
        purpose = next(iter(purposes))
    else:
        # 分类里没有用途信息，退到描述。瑞士那 20 条就是这种：描述是
        # 海报原文（`... am 13. Okt. stimmet: Ja!`），比中文译名可靠。
        hit = {p for pat, p in DESC_PURPOSE if pat.search(desc or "")}
        if len(hit) > 1:
            # 「Wahl ... stimmet」同时命中两类的，说明是公投里的选举议题，不猜
            notes.append(f"描述同时命中 {sorted(hit)}")
            purpose = ""
        elif hit:
            purpose = next(iter(hit))
            notes.append(f"用途取自描述 {purpose}")
        else:
            purpose = ""

    stances = {STANCE_FROM_CAT[c] for c in cats if c in STANCE_FROM_CAT}
    for bad in CONFLICT_SETS:
        if bad <= stances:
            notes.append(f"组织×议题冲突 {sorted(bad)}，单值 stance 装不下")
            stances = set()
            break
    if stances and COMMITTEE_HINT.search(desc or ""):
        notes.append(f"描述指向跨党派委员会，分类里的党名不作判据：{(desc or '')[:50]}")
        stances = set()
    if not stances:
        # 分类里没有党名，退到描述文本里的党名（原件题名转录）。
        # 注意不要与上面的"用途取自描述" note 互斥——它们是两条独立的轴。
        hit = {s for pat, s in DESC_STANCE if pat.search(desc or "")}
        if len(hit) == 1:
            stances = hit
            notes.append(f"立场取自描述 {next(iter(hit))}")
        elif len(hit) > 1:
            notes.append(f"描述命中多个立场 {sorted(hit)}，不猜")
    if len(stances) > 1:
        notes.append(f"立场分类冲突 {sorted(stances)}")
        stance = ""
    else:
        stance = next(iter(stances), "")

    return purpose, stance, "；".join(notes)


def main():
    dry = "--dry" in sys.argv
    verbose = "--verbose" in sys.argv or dry

    recs = catalog.load()
    swiss = [r for r in recs if r["country"] == "瑞士"]
    if not swiss:
        print("目录里没有瑞士条目")
        return 1

    pairs = [(r, commons_title(r["url"])) for r in swiss]
    pairs = [(r, t) for r, t in pairs if t]
    print(f"瑞士 {len(swiss)} 条，可解析出 Commons 标题 {len(pairs)} 条")
    print("从 Commons 取分类…")

    cats_by_title = fetch_categories([t for _, t in pairs])
    by_norm = {norm(k.replace("File:", "")): v for k, v in cats_by_title.items()}
    print(f"取回 {len(cats_by_title)} 条的元数据\n")

    got_p = got_s = unchanged = no_cats = 0
    for r, t in pairs:
        meta = by_norm.get(norm(t.replace("File:", "")))
        if meta is None:
            no_cats += 1
            if verbose:
                print(f"  ? 无元数据 {r['title'][:40]}")
            continue

        purpose, stance, note = classify(meta["cats"], meta["desc"])
        old_p = vocab.normalize(r.get("purpose"))
        old_s = vocab.normalize(r.get("stance"))

        changed = False
        if purpose and purpose != old_p:
            if verbose:
                print(f"  用途 {r['title'][:38]:40s} {old_p or '(空)'} → {purpose}")
            changed = True
            got_p += 1
            if not dry:
                r["purpose"] = purpose
        if stance and stance != old_s:
            if verbose:
                print(f"  立场 {r['title'][:38]:40s} {old_s or '(空)'} → {stance}")
            changed = True
            got_s += 1
            if not dry:
                r["stance"] = stance
        if note and verbose:
            print(f"      留空理由：{note}")
        if not changed:
            unchanged += 1

    print(f"\n用途补入 {got_p} 条、立场补入 {got_s} 条；无改动 {unchanged} 条；"
          f"无元数据 {no_cats} 条")

    if dry:
        print("\n（试运行，未写文件）")
        return 0

    catalog.save(recs)

    ps = vocab.purpose_stats(recs)
    print(f"写入后：用途覆盖 {len(recs) - ps['unmarked']}/{len(recs)}"
          f"（{(len(recs) - ps['unmarked']) / len(recs) * 100:.0f}%）")
    sw_after = [r for r in recs if r["country"] == "瑞士"]
    print(f"瑞士 {len(sw_after)} 条：有用途 "
          f"{sum(1 for r in sw_after if r.get('purpose'))}、"
          f"有立场 {sum(1 for r in sw_after if r.get('stance'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
