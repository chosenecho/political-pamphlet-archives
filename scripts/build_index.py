"""重建 CSV 索引与专藏清单文档（docs/COLLECTIONS.md）。不触碰 README。"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import paths

BASE = paths.BASE
NOTES = paths.NOTES
RAW = os.path.join(BASE, "raw")

with open(paths.SOURCES, encoding="utf-8") as f:
    src = json.load(f)
with open(paths.MANIFEST, encoding="utf-8") as f:
    man = {r["slug"]: r for r in json.load(f)}

# 「抓到了落地页」和「真的产生了条目」是两件事，读者最容易被这两个数搞混：
# manifest 覆盖 20 来个源，看起来像是都入库了；但 catalog 里带 URL 的条目
# 实际只落在少数几个域名上，其余源只是抓了首页正文存进 notes/。
# 所以这里按 source 字段实时统计条目数，不写进 manifest——catalog 一直在变，
# 写死就会过时，每次构建重算才是准的。
catalog_recs = []
if os.path.exists(paths.CATALOG):
    with open(paths.CATALOG, encoding="utf-8") as f:
        catalog_recs = json.load(f)
entries_by_slug = {}
for r in catalog_recs:
    slug = (r.get("source") or "").strip()
    if slug:
        entries_by_slug[slug] = entries_by_slug.get(slug, 0) + 1
unattributed = sum(1 for r in catalog_recs if not (r.get("source") or "").strip())

rows = []
for s in src["sources"]:
    slug = s["slug"]
    p = os.path.join(NOTES, slug + ".txt")
    exists = os.path.exists(p)
    chars = len(open(p, encoding="utf-8").read()) if exists else 0
    if chars > 500:
        status = "ok"
    elif exists:
        status = "partial"
    else:
        status = "index-only"
    rows.append({
        "slug": slug,
        "title": s["title"],
        "region": s["region"],
        "kind": s["kind"],
        "url": s["url"],
        "chars": chars,
        "status": status,
        # via 为空有两种情况，必须分清：无抓取记录 / 有记录但未记抓取方式
        "via": (man.get(slug, {}).get("via") or ""),
        "has_manifest": slug in man,
        # 该源在 catalog 里实际产生的条目数。0 表示只抓了入口页，没有条目入库
        "entries": entries_by_slug.get(slug, 0),
        "note": s.get("note", ""),
    })

with open(paths.INDEX_CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["slug", "title", "region", "kind", "url",
                                      "chars", "status", "has_manifest", "via",
                                      "entries", "note"],
                       # csv 默认 \r\n；仓库里存的是 LF，不显式指定会让
                       # Windows 上重建的产物与提交不一致，CI 的产物校验必红
                       lineterminator="\n")
    w.writeheader()
    w.writerows(rows)

ok = [r for r in rows if r["status"] == "ok"]
part = [r for r in rows if r["status"] == "partial"]
only = [r for r in rows if r["status"] == "index-only"]

L = ["# 专藏清单与抓取状态", "",
     f"源数 {len(rows)}　|　已取正文 {len(ok)}　|　仅登记入口 {len(only)}　|　"
     f"catalog 条目 {len(catalog_recs)}", "",
     "> 声明：本清单由 AI 辅助整理，仅供学术研究与交流；内容可能有误，不对使用后果负责。"
     "如有版权或内容问题，提出后立即移除。详见 [DISCLAIMER.md](../DISCLAIMER.md)。", "",
     "| # | 专藏 | 地区 | 类型 | 正文字符 | 条目 | 状态 |", "|---|---|---|---|---|---|---|"]
MARK = {"ok": "✅", "partial": "⚠️", "index-only": "○"}
for i, r in enumerate(rows, 1):
    L.append(f"| {i} | [{r['title']}]({r['url']}) | {r['region']} | {r['kind']} | "
             f"{r['chars']} | {r['entries'] or '—'} | {MARK[r['status']]} |")

L += ["", "## 状态说明", ""]
L += [f"- ✅ 共 {len(ok)} 个源抓到了可读正文。"]
L += [f"- ⚠️ 共 {len(part)} 个源只有说明文件：" + "、".join(r["slug"] for r in part) + "。"]
L += ["  这些站点对自动化访问返回 403 / 429，或正文全在 JS 前端。`notes/` 里保留了失败原因与已知信息，未编造正文。"]
L += [f"- ○ 共 {len(only)} 个源已核实入口但尚未抓取正文；清单可用，内容待取。"]
L += [""]

# 「抓到了落地页」≠「有条目入库」。这一节专门把这层区别摊开，否则读者看到
# 「覆盖 N 个源」会以为这些源的内容都进库了。
producing = [r for r in rows if r["entries"]]
L += ["## 条目来源分布", "",
      f"`data/catalog.json` 共 {len(catalog_recs)} 条条目。按 `source` 字段归属到专藏：", ""]
if producing:
    L += ["| 专藏 | 条目数 |", "|---|---|"]
    for r in sorted(producing, key=lambda x: -x["entries"]):
        L.append(f"| {r['title']} | {r['entries']} |")
if unattributed:
    L += ["", f"- 另有 **{unattributed}** 条条目未标注所属专藏（`source` 为空），"
              f"未计入上表，也未猜断归属。"]
L += ["", f"**{len(rows) - len(producing)} 个源只抓到了入口页正文，没有条目入库。**"
          "「已取正文」指落地页抓到了可读文本，不等于该源的材料已进入目录。", ""]

no_manifest = [r["slug"] for r in rows if not r["has_manifest"]]
no_via = [r["slug"] for r in rows if r["has_manifest"] and not r["via"]]
L += ["## 抓取记录覆盖", ""]
L += [f"`data/manifest.json` 共 {len(man)} 条抓取明细，覆盖 {len(rows) - len(no_manifest)}/{len(rows)} 个源。"]
if no_manifest:
    L += ["", f"- {len(no_manifest)} 个源**尚无抓取记录**（未尝试，非失败）："
          + "、".join(f"`{s}`" for s in no_manifest)]
if no_via:
    L += [f"- {len(no_via)} 个源有记录但未填写抓取方式（`via` 为空），不影响正文可用性。"]
L += [""]

os.makedirs(os.path.join(BASE, "docs"), exist_ok=True)
# newline="\n"：Windows 上默认会把 \n 转成 \r\n，产物与提交就对不上了
with open(os.path.join(BASE, "docs", "COLLECTIONS.md"), "w",
          encoding="utf-8", newline="\n") as f:
    f.write("\n".join(L))

print(f"sources={len(rows)} ok={len(ok)} partial={len(part)} index-only={len(only)}")
print(f"notes={len(os.listdir(NOTES)) if os.path.isdir(NOTES) else 0} "
      f"raw={len(os.listdir(RAW)) if os.path.isdir(RAW) else 0}")
