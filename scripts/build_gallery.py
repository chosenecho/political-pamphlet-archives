"""生成画廊 HTML：图片存在就显示，不存在则降级为条目卡片（供公开仓库使用）。"""

import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")


def load(folder):
    """优先读本地抓取结果；仓库里没有 images/ 时回退到 metadata/。"""
    p = os.path.join(IMG, folder, "metadata.json")
    if not os.path.exists(p):
        p = os.path.join(BASE, "metadata", folder + ".json")
    if not os.path.exists(p):
        return []
    out = []
    for r in json.load(open(p, encoding="utf-8")):
        if not r.get("ok"):
            continue
        r["folder"] = folder
        cover = os.path.join(IMG, folder, r.get("file", ""))
        r["has_cover"] = os.path.exists(cover)
        r["has_pages"] = bool(r.get("pages_downloaded"))
        out.append(r)
    return out


def card(r):
    title = re.sub(r"<[^>]+>", "", str(r.get("title", "")))
    year = r.get("year") or ""
    rel = f'images/{r["folder"]}/{r["file"]}'
    src = r.get("detail_url") or r.get("descurl") or r.get("iiif") or "#"
    meta = " · ".join(x for x in [
        r.get("publisher") or "",
        r.get("responsible") or "",
        r.get("license") or "",
    ] if x)
    pages = len(r["pages_downloaded"]) if r.get("pages_downloaded") else 0
    badge = f'<span class="pg">{pages} 页</span>' if pages else ""

    if r["has_cover"]:
        media = (f'<a href="{rel}" target="_blank">'
                 f'<img loading="lazy" src="{rel}" alt="{title}" '
                 f'onerror="this.parentNode.innerHTML=\'<div class=ph>图像未随仓库分发</div>\'"></a>')
    else:
        media = '<div class="ph">图像未随仓库分发<br><small>运行 scripts/harvest_*.py 后出现</small></div>'

    return f"""<figure class="c">{media}
<figcaption><b>{year}</b> {title[:58]} {badge}<br><span>{meta[:70]}</span><br>
<a class="src" href="{src}" target="_blank">来源条目 ↗</a></figcaption></figure>"""


def page(items, heading, note):
    return f"""<h2>{heading}</h2><p class="note">{note}</p>
<div class="grid">{''.join(card(r) for r in items)}</div>"""


mh = load("modernhistory")
cm = load("commons")
total = len(mh) + len(cm)

html = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>政党宣传品图像集 · 目录</title>
<style>
:root{{color-scheme:light}}
body{{margin:0;padding:28px;background:#f7f6f3;color:#1d1d1b;
font:15px/1.6 -apple-system,"Segoe UI","Noto Sans SC",sans-serif}}
h1{{font-size:25px;margin:0 0 6px}}
h2{{font-size:17px;margin:30px 0 4px;padding-top:18px;border-top:1px solid #e3e1db}}
.lede{{color:#666;margin:0;font-size:14px}}
.note{{color:#888;font-size:13px;margin:0 0 16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(198px,1fr));gap:16px}}
.c{{margin:0;background:#fff;border:1px solid #e3e1db;border-radius:10px;overflow:hidden;
display:flex;flex-direction:column}}
.c img{{width:100%;display:block;aspect-ratio:2/3;object-fit:cover;background:#eee}}
.ph{{aspect-ratio:2/3;display:flex;flex-direction:column;align-items:center;justify-content:center;
background:#f2f0ec;color:#9a958c;font-size:12px;text-align:center;padding:12px;gap:4px}}
figcaption{{padding:10px 12px 12px;font-size:12.5px;line-height:1.5;color:#333}}
figcaption b{{color:#981722}}
figcaption span{{color:#777}}
.pg{{display:inline-block;background:#eef2f7;color:#40618c;border-radius:4px;
padding:0 5px;font-size:11px}}
.src{{color:#4a6fa5;text-decoration:none}}
.src:hover{{text-decoration:underline}}
</style></head><body>
<h1>政党与政治派系宣传品 · 图像目录</h1>
<p class="lede">共 {total} 条记录（中国 {len(mh)} 件，西方 {len(cm)} 件）。
图像文件不随仓库分发，按 README 的脚本可自行抓取。</p>
{page(mh, "中国 · 1920–1949", "来源：抗日战争与近代中日关系文献数据平台。1949 年前原版。")}
{page(cm, "西方 · 1815–1948", "来源：Wikimedia Commons。许可证见各条记录。")}
</body></html>"""

os.makedirs(os.path.join(BASE, "docs"), exist_ok=True)
open(os.path.join(BASE, "docs", "index.html"), "w", encoding="utf-8").write(html)

print(f"gallery.html: {total} 条（中国 {len(mh)} / 西方 {len(cm)}）")
print("covers present:", sum(1 for r in mh + cm if r["has_cover"]))
print("with pages:", sum(1 for r in mh + cm if r["has_pages"]))
