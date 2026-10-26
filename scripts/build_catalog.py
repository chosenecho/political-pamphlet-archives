"""按当前结构生成目录页（分组浏览）与说明文档。"""

import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")
recs = json.load(open(os.path.join(IMG, "索引.json"), encoding="utf-8"))

ORDER = ["中国", "俄国", "德国", "法国", "英国", "美国", "意大利", "西班牙",
         "葡萄牙", "荷兰", "奥地利", "捷克", "波兰", "日本", "印度", "拉美"]

groups = {}
for r in recs:
    groups.setdefault(r["country"], []).append(r)

blocks = []
for c in ORDER:
    if c not in groups:
        continue
    items = sorted(groups[c], key=lambda x: str(x["year"]))
    cards = []
    for r in items:
        pages = f'<span class="pg">{r["pages"]} 页</span>' if r.get("pages", 1) > 1 else ""
        note = (r.get("publisher") or r.get("license") or "")[:30]
        cards.append(f"""<figure class="c">
<a href="{r['cover']}" target="_blank"><img loading="lazy" src="{r['cover']}" alt="{r['title']}"></a>
<figcaption><b>{r['year']}</b> {r['title'][:46]} {pages}<br><span>{note}</span><br>
<a class="src" href="{r['url']}" target="_blank">来源 ↗</a></figcaption></figure>""")
    blocks.append(f'<h2>{c} <small>{len(items)} 件</small></h2><div class="grid">{"".join(cards)}</div>')

html = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>政党宣传品 · 按国别目录</title>
<style>
:root{{color-scheme:light}}
body{{margin:0;padding:28px;background:#f7f6f3;color:#1d1d1b;
font:15px/1.6 -apple-system,"Segoe UI","Noto Sans SC",sans-serif}}
h1{{font-size:25px;margin:0 0 4px}}
h2{{font-size:16px;margin:34px 0 2px;padding-top:20px;border-top:1px solid #e3e1db}}
h2 small{{color:#9a958c;font-weight:400;font-size:12.5px}}
.lede{{color:#666;margin:0 0 10px;font-size:14px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(184px,1fr));gap:14px;margin-top:14px}}
.c{{margin:0;background:#fff;border:1px solid #e3e1db;border-radius:10px;overflow:hidden;display:flex;flex-direction:column}}
.c img{{width:100%;display:block;aspect-ratio:2/3;object-fit:cover;background:#eee}}
figcaption{{padding:9px 11px 11px;font-size:12.5px;line-height:1.5;color:#333}}
figcaption b{{color:#981722}}
figcaption span{{color:#777}}
.pg{{display:inline-block;background:#eef2f7;color:#40618c;border-radius:4px;padding:0 5px;font-size:11px}}
.src{{color:#4a6fa5;text-decoration:none}}
.src:hover{{text-decoration:underline}}
</style></head><body>
<h1>政党宣传品 · 按国别目录</h1>
<p class="lede">{len(recs)} 件，{len(groups)} 个国别/地区。中国为多页小册子（整本），其余为单页传单/海报。
国别归属由标题关键词判定，个别条目可能误归，见 README 说明。</p>
{''.join(blocks)}
</body></html>"""

open(os.path.join(IMG, "目录.html"), "w", encoding="utf-8").write(html)
print(f"目录.html：{len(recs)} 件，{len(groups)} 组")

for c in ORDER:
    if c in groups:
        print(f"   {c:6s} {len(groups[c])} 件")
