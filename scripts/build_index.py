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
        "note": s.get("note", ""),
    })

with open(paths.INDEX_CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["slug", "title", "region", "kind", "url",
                                      "chars", "status", "has_manifest", "via", "note"])
    w.writeheader()
    w.writerows(rows)

ok = [r for r in rows if r["status"] == "ok"]
part = [r for r in rows if r["status"] == "partial"]
only = [r for r in rows if r["status"] == "index-only"]

L = ["# 专藏清单与抓取状态", "",
     f"源数 {len(rows)}　|　已取正文 {len(ok)}　|　仅登记入口 {len(only)}", "",
     "> 声明：本清单由 AI 辅助整理，仅供学术研究与交流；内容可能有误，不对使用后果负责。"
     "如有版权或内容问题，提出后立即移除。详见 [DISCLAIMER.md](../DISCLAIMER.md)。", "",
     "| # | 专藏 | 地区 | 类型 | 正文字符 | 状态 |", "|---|---|---|---|---|---|"]
MARK = {"ok": "✅", "partial": "⚠️", "index-only": "○"}
for i, r in enumerate(rows, 1):
    L.append(f"| {i} | [{r['title']}]({r['url']}) | {r['region']} | {r['kind']} | {r['chars']} | "
             f"{MARK[r['status']]} |")

L += ["", "## 状态说明", ""]
L += [f"- ✅ 共 {len(ok)} 个源抓到了可读正文。"]
L += [f"- ⚠️ 共 {len(part)} 个源只有说明文件：" + "、".join(r["slug"] for r in part) + "。"]
L += ["  这些站点对自动化访问返回 403 / 429，或正文全在 JS 前端。`notes/` 里保留了失败原因与已知信息，未编造正文。"]
L += [f"- ○ 共 {len(only)} 个源已核实入口但尚未抓取正文；清单可用，内容待取。"]
L += [""]

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
open(os.path.join(BASE, "docs", "COLLECTIONS.md"), "w", encoding="utf-8").write("\n".join(L))

print(f"sources={len(rows)} ok={len(ok)} partial={len(part)} index-only={len(only)}")
print(f"notes={len(os.listdir(NOTES)) if os.path.isdir(NOTES) else 0} "
      f"raw={len(os.listdir(RAW)) if os.path.isdir(RAW) else 0}")
