"""重建 CSV 索引与专藏清单文档（docs/COLLECTIONS.md）。不触碰 README。"""

import csv
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTES = os.path.join(BASE, "notes")
RAW = os.path.join(BASE, "raw")

src = json.load(open(os.path.join(BASE, "data", "sources.json"), encoding="utf-8"))
man = {r["slug"]: r for r in json.load(open(os.path.join(BASE, "data", "manifest.json"), encoding="utf-8"))}

rows = []
for s in src["sources"]:
    slug = s["slug"]
    p = os.path.join(NOTES, slug + ".txt")
    chars = len(open(p, encoding="utf-8").read()) if os.path.exists(p) else 0
    rows.append({
        "slug": slug,
        "title": s["title"],
        "region": s["region"],
        "kind": s["kind"],
        "url": s["url"],
        "chars": chars,
        "status": "ok" if chars > 500 else "partial",
        "via": man.get(slug, {}).get("via", "urllib"),
        "note": s.get("note", ""),
    })

with open(os.path.join(BASE, "data", "index.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

ok = [r for r in rows if r["status"] == "ok"]
part = [r for r in rows if r["status"] != "ok"]

L = ["# 专藏清单与抓取状态", "",
     f"源数 {len(rows)}　|　取得有效正文 {len(ok)}", "",
     "| # | 专藏 | 地区 | 类型 | 正文字符 | 状态 |", "|---|---|---|---|---|---|"]
for i, r in enumerate(rows, 1):
    L.append(f"| {i} | [{r['title']}]({r['url']}) | {r['region']} | {r['kind']} | {r['chars']} | "
             f"{'✅' if r['status'] == 'ok' else '⚠️'} |")

L += ["", "## 状态说明", ""]
L += [f"- ✅ 共 {len(ok)} 个源抓到了可读正文。"]
L += [f"- ⚠️ 共 {len(part)} 个源只有说明文件：" + "、".join(r["slug"] for r in part) + "。"]
L += ["  这些站点对自动化访问返回 403 / 429，或正文全在 JS 前端。`notes/` 里保留了失败原因与已知信息，未编造正文。"]
L += [""]

os.makedirs(os.path.join(BASE, "docs"), exist_ok=True)
open(os.path.join(BASE, "docs", "COLLECTIONS.md"), "w", encoding="utf-8").write("\n".join(L))

print(f"sources={len(rows)} ok={len(ok)} partial={len(part)}")
print(f"notes={len(os.listdir(NOTES)) if os.path.isdir(NOTES) else 0} "
      f"raw={len(os.listdir(RAW)) if os.path.isdir(RAW) else 0}")
