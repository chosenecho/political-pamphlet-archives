"""生成画廊 HTML：图片存在就显示，不存在则降级为条目卡片（供公开仓库使用）。

注意：页面顶部的声明条与页脚弃权声明写在 BANNER / FOOTER 里，修改页面时不要删掉；
条款正文见仓库根目录的 DISCLAIMER.md。
"""

import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")
REPO_URL = "https://github.com/chosenecho/political-pamphlet-archives"

BANNER = """<div class="disc" role="note">
<b>声明</b>　本目录由 AI 辅助生成与整理，<b>仅供学术研究与交流</b>；内容可能有误，不保证准确、完整，也不对使用后果负责。所收录材料为历史宣传品，收录不等于认同其立场。若权利人或其他方面认为内容不当，<a href="{repo}/issues">提出即删</a>。完整条款见 <a href="{repo}/blob/main/DISCLAIMER.md">DISCLAIMER.md</a>。
</div>"""

FOOTER = """<footer class="foot">
<p><b>声明与免责</b>　本页与仓库内容由 AI 辅助生成与整理，仅供历史学、图书馆学与政治传播史方向的研究、教学与检索方法交流，不构成法律、版权或政治意见。维护者不对内容的准确性、完整性作保证，也不对因使用或无法使用这些内容而产生的后果负责。</p>
<p>书目信息与馆藏描述摘自已公开的图书馆、档案馆页面，著作权归各原机构与捐赠者；扫描图像<b>不随仓库分发</b>。所收录材料为十九至二十世纪各政党与派系的宣传品，其中包含今日看来极具争议的内容，<b>收录不等于认同</b>。</p>
<p>若任何机构或个人认为某条目、摘录或链接侵犯其权利或不宜公开，请在 <a href="{repo}/issues">Issues</a> 留言，核实后<b>立即下架</b>相关条目或整库。完整条款与英文说明见 <a href="{repo}/blob/main/DISCLAIMER.md">DISCLAIMER.md</a>。</p>
</footer>"""



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


def load_index():
    """读 images/索引.json —— 当前采集结构（小册子 + 单页）。"""
    p = os.path.join(IMG, "索引.json")
    if not os.path.exists(p):
        return [], []
    recs = json.load(open(p, encoding="utf-8"))
    books = [r for r in recs if r.get("kind") == "小册子"]
    singles = [r for r in recs if r.get("kind") != "小册子"]
    for r in books + singles:
        r["has_cover"] = os.path.exists(os.path.join(IMG, r["cover"]))
    return books, singles


def card_idx(r):
    title = re.sub(r"<[^>]+>", "", str(r.get("title", "")))
    year = r.get("year") or ""
    rel = "images/" + r["cover"]
    src = r.get("url") or "#"
    badge = f'<span class="pg">{r["pages"]} 页</span>' if int(r.get("pages") or 1) > 1 else ""
    if r["has_cover"]:
        media = (f'<a href="{rel}" target="_blank">'
                 f'<img loading="lazy" src="{rel}" alt="{title}" '
                 f'onerror="this.parentNode.innerHTML=\'<div class=ph>图像未随仓库分发</div>\'"></a>')
    else:
        media = '<div class="ph">图像未随仓库分发<br><small>运行 scripts/ 下的采集脚本后出现</small></div>'
    return f"""<figure class="c">{media}
<figcaption><b>{year}</b> {title[:52]} {badge}<br>
<a class="src" href="{src}" target="_blank">来源 ↗</a></figcaption></figure>"""


def page_idx(items, heading, note):
    return f"""<h2>{heading} <small>{len(items)}</small></h2><p class="note">{note}</p>
<div class="grid">{''.join(card_idx(r) for r in items)}</div>"""


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


books, singles = load_index()
if not books:
    mh = load("modernhistory")
    cm = load("commons")
    total = len(mh) + len(cm)
    body = (page(mh, "中国 · 1920–1949", "来源：抗日战争与近代中日关系文献数据平台。") +
            page(cm, "西方 · 1815–1948", "来源：Wikimedia Commons。"))
    lede = f"共 {total} 条记录（中国 {len(mh)} 件，西方 {len(cm)} 件）。"
else:
    total = len(books) + len(singles)
    groups = {}
    for r in books:
        groups.setdefault(r["country"], []).append(r)
    body = ""
    for c in ["中国", "美国", "英国", "法国", "德国", "俄国", "意大利"]:
        if c in groups:
            body += page_idx(sorted(groups[c], key=lambda x: str(x["year"])),
                             f"小册子 · {c}", "多页装订印刷品，整本采集。")
    body += page_idx(singles[:60], "单页传单与海报",
                     f"单张宣传品，不计入小册子统计；共 {len(singles)} 件，此处列前 60 件。")
    lede = (f"共 {len(books)} 本多页小册子 + {len(singles)} 件单页宣传品。"
            "图像文件不随仓库分发，按 README 的脚本可自行抓取。")

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
.disc{{margin:0 0 20px;padding:10px 14px;background:#fdf7e8;border:1px solid #ecdcae;
border-left:4px solid #c08a1e;border-radius:6px;font-size:13px;line-height:1.65;color:#5b4a24}}
.disc a{{color:#8a5a00}}
.foot{{margin:36px 0 0;padding-top:16px;border-top:1px solid #e3e1db;color:#7a756c;
font-size:12.5px;line-height:1.7;max-width:900px}}
.foot p{{margin:0 0 8px}}
.foot b{{color:#1d1d1b}}
.foot a{{color:#4a6fa5}}
</style></head><body>
{BANNER.format(repo=REPO_URL)}
<h1>政党与政治派系宣传品 · 目录</h1>
<p class="lede">{lede}</p>
{body}
{FOOTER.format(repo=REPO_URL)}
</body></html>"""

os.makedirs(os.path.join(BASE, "docs"), exist_ok=True)
open(os.path.join(BASE, "docs", "index.html"), "w", encoding="utf-8").write(html)

print(f"docs/index.html: {total} 条")
print("books:", len(books), "singles:", len(singles))
