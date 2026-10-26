"""给已抓图片分类：按主题建目录，逐件一个文件夹（封面 + 内页）。

用法：
    python scripts/organize_images.py --dry    # 只看分类结果，不动文件
    python scripts/organize_images.py          # 实际整理
"""

import csv
import json
import os
import re
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")
DEST = os.path.join(IMG, "分类")

# ---------- 中文：关键词规则（顺序即优先级） ----------
CN_RULES = [
    ("05-妇女运动", ["妇女", "女工", "女性"]),
    ("06-工人运动", ["工人", "工会", "工仇", "罢工", "劳动"]),
    ("04-青年与学生", ["青年", "学生", "少年", "童子军"]),
    ("03-农民与土地", ["农民", "土地", "土改", "农会", "农村"]),
    ("07-国民党与三民主义", ["三民主义", "孙中山", "孙文"]),
    ("08-反蒋与时局", ["蒋介石", "汪精卫", "反动派", "总账", "祸国", "卖国"]),
    ("01-党纲与党建", ["共产党宣言", "共产党员", "什么是共产党", "论共产党", "党纲",
                    "第三国际", "哥达纲领", "奋斗史", "论新阶段", "必读", "党章",
                    "党的政策", "党的建设"]),
    ("09-马列与苏联文献", ["列宁", "马克思", "马恩列斯", "马、恩、列、斯", "恩格斯",
                     "民族殖民地", "苏联", "俄国社会民主", "斯大林"]),
    ("02-抗战动员与军事", ["抗日", "抗战", "游击", "动员", "标语", "口号", "政治工作",
                     "救亡", "战争", "根据地", "大渡河", "军政", "队伍", "士兵"]),
    ("10-宣传文艺与通俗读物", ["小品文", "宣教", "大众集", "诗歌", "歌声", "歌曲",
                        "故事", "课本", "丛刊", "汇刊", "毛泽东颂", "无敌"]),
]

# 规则兜不住或会误判的，手工指定
CN_OVERRIDE = {
    1: "10-宣传文艺与通俗读物",    # 洋铁桶的故事
    8: "01-党纲与党建",            # 第三国际议案及宣言
    9: "02-抗战动员与军事",        # 东北抗日联军第八军成立宣言
    10: "01-党纲与党建",           # 哥达纲领批判
    11: "01-党纲与党建",
    19: "02-抗战动员与军事",       # 农村与城市目前适用的口号
    23: "08-反蒋与时局",           # 哈尔滨解放（下）
    24: "08-反蒋与时局",           # 新民主法令辑览
    26: "03-农民与土地",           # 中国土地法大纲
    27: "02-抗战动员与军事",       # 论宣传教育
    31: "10-宣传文艺与通俗读物",   # 脂粉下的狞鬼
    35: "09-马列与苏联文献",       # 俄国社会民主党人底任务
    40: "02-抗战动员与军事",       # 图表格与用品
    41: "10-宣传文艺与通俗读物",   # 美国革命史（8）
    43: "06-工人运动",             # 二七工仇
    68: "08-反蒋与时局",           # 汪精卫卖国罪证
    73: "05-妇女运动",             # 世界民主妇女文集
    84: "03-农民与土地",
    88: "10-宣传文艺与通俗读物",   # 德国农民战争
    105: "02-抗战动员与军事",      # 人民的队伍
    107: "02-抗战动员与军事",      # 聂荣臻大战孙连仲
    122: "02-抗战动员与军事",      # 从七七到八一五
    123: "07-国民党与三民主义",    # 纪念孙中山批判蒋介石
    125: "07-国民党与三民主义",
    131: "01-党纲与党建",          # 新民主主义的理论与实践
    133: "02-抗战动员与军事",      # 论战争
    135: "08-反蒋与时局",          # 民主建设讲话
    139: "09-马列与苏联文献",      # 毛主席三大名著
    140: "02-抗战动员与军事",      # 抗战建国论
    15: "01-党纲与党建",           # 新民主主义注解问答
    17: "10-宣传文艺与通俗读物",   # 到自由幸福之路
    56: "02-抗战动员与军事",       # 和平！奋斗！救中国！
    124: "08-反蒋与时局",          # 和平建设新中国
}

# ---------- 西方：按编号直接指定 ----------
EN_MAP = {
    "W1-竞选材料": [3, 4, 5, 6, 22, 29, 30, 31, 32, 39],
    "W2-社会主义与共产主义": [12, 13, 14, 15, 21],
    "W3-妇女参政": [2, 23, 24, 25, 26, 27, 28],
    "W4-政治讽刺与 broadside": [33, 34, 35, 36, 37, 38],
    "W5-战争与反战宣传": [1, 7, 8, 9, 10, 11, 16, 17, 18, 19, 20],
}

TAG = re.compile(r"<[^>]+>")
BAD = re.compile(r'[\\/:*?"<>|]+')


def clean(s):
    return TAG.sub("", str(s or "")).strip()


def safe(s, limit=40):
    s = BAD.sub("_", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s[:limit]                      # 先截断
    return s.strip(" ._-") or "untitled"   # 再清掉末尾的点和空格（Windows 不允许）


def classify_cn(rec):
    no = rec["no"]
    if no in CN_OVERRIDE:
        return CN_OVERRIDE[no]
    t = clean(rec.get("title"))
    for cat, kws in CN_RULES:
        if any(k in t for k in kws):
            return cat
    return "11-其他"


def classify_en(rec):
    for cat, nos in EN_MAP.items():
        if rec["no"] in nos:
            return cat
    return "W6-其他"


DRY = "--dry" in sys.argv

plan = []

for folder, meta_name, is_cn in [("modernhistory", "modernhistory", True),
                                 ("commons", "commons", False)]:
    meta = json.load(open(os.path.join(BASE, "metadata", meta_name + ".json"), encoding="utf-8"))
    for rec in meta:
        if not rec.get("ok"):
            continue
        cat = classify_cn(rec) if is_cn else classify_en(rec)
        year = rec.get("year") or "0000"
        title = clean(rec.get("title"))
        item = f"{rec['no']:03d}_{year}_{safe(title)}"
        src_cover = os.path.join(IMG, folder, rec.get("file", ""))
        src_pages = os.path.join(IMG, folder, "pages", f"{rec['no']:03d}")
        plan.append({
            "cat": cat, "item": item, "no": rec["no"],
            "title": title, "year": year, "source": folder,
            "publisher": rec.get("publisher") or rec.get("credit") or "",
            "responsible": rec.get("responsible") or "",
            "license": rec.get("license") or "",
            "url": rec.get("detail_url") or rec.get("descurl") or rec.get("iiif") or "",
            "pages": rec.get("pages") or "",
            "cover_src": src_cover,
            "pages_src": src_pages if os.path.isdir(src_pages) else None,
            "has_pages": os.path.isdir(src_pages),
        })

from collections import Counter
print(f"{'分类':32s} 件数")
for c, n in sorted(Counter(p["cat"] for p in plan).items()):
    print(f"{c:32s} {n:4d}")
print(f"\n合计 {len(plan)} 件；含内页 {sum(1 for p in plan if p['has_pages'])} 件")

missing = [p for p in plan if not os.path.exists(p["cover_src"])]
print(f"封面缺失 {len(missing)} 件")
for p in missing[:5]:
    print("   ", p["no"], p["title"][:30], p["cover_src"])

if DRY:
    print("\n[试运行] 未改动文件。抽查前 20 条：")
    for p in plan[:20]:
        print(f"  {p['cat']:26s} {p['no']:3d} {p['year']} {p['title'][:34]}")
    sys.exit(0)

# ---------------- 实际整理 ----------------
os.makedirs(DEST, exist_ok=True)
moved_covers = moved_pages = 0

for p in plan:
    item_dir = os.path.join(DEST, p["cat"], p["item"])
    os.makedirs(item_dir, exist_ok=True)

    dst_cover = os.path.join(item_dir, "cover.jpg")
    if os.path.exists(p["cover_src"]) and not os.path.exists(dst_cover):
        shutil.move(p["cover_src"], dst_cover)
        moved_covers += 1
    p["cover"] = f'分类/{p["cat"]}/{p["item"]}/cover.jpg'

    dst_pages = os.path.join(item_dir, "pages")
    if p["pages_src"]:
        if not os.path.isdir(dst_pages):
            shutil.move(p["pages_src"], dst_pages)
            moved_pages += 1
    p["page_count"] = len(os.listdir(dst_pages)) if os.path.isdir(dst_pages) else 0

    for k in ("cover_src", "pages_src", "has_pages", "source"):
        p.pop(k, None)

print(f"移动封面 {moved_covers} 张，内页目录 {moved_pages} 个")

# 清理空目录
for d in ("modernhistory", "modernhistory/pages", "commons"):
    path = os.path.join(IMG, d)
    if os.path.isdir(path) and not os.listdir(path):
        os.rmdir(path)
        print("cleaned", d)

# ---------------- 索引 ----------------
plan.sort(key=lambda x: (x["cat"], x["year"]))
json.dump(plan, open(os.path.join(IMG, "分类.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

with open(os.path.join(IMG, "分类目录.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["类别", "序号", "年份", "标题", "出版者", "责任者", "页数", "本地目录", "来源链接"])
    for p in plan:
        w.writerow([p["cat"], p["no"], p["year"], p["title"], p["publisher"],
                    p["responsible"], p["page_count"], f'{p["cat"]}/{p["item"]}', p["url"]])

# ---------------- HTML ----------------
groups = {}
for p in plan:
    groups.setdefault(p["cat"], []).append(p)

blocks = []
for cat in sorted(groups):
    items = groups[cat]
    items.sort(key=lambda x: str(x["year"]))
    cards = []
    for p in items:
        pages = f'<span class="pg">{p["page_count"]} 页</span>' if p["page_count"] else ""
        cards.append(f"""<figure class="c">
<a href="{p['cover']}" target="_blank"><img loading="lazy" src="{p['cover']}" alt="{p['title']}"></a>
<figcaption><b>{p['year']}</b> {p['title'][:52]} {pages}<br>
<span>{p['publisher'][:26]}</span><br>
<a class="src" href="{p['url']}" target="_blank">来源条目 ↗</a></figcaption></figure>""")
    blocks.append(f'<h2>{cat} <small>{len(items)} 件</small></h2><div class="grid">{"".join(cards)}</div>')

html = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>政党宣传品 · 分类目录</title>
<style>
:root{{color-scheme:light}}
body{{margin:0;padding:28px;background:#f7f6f3;color:#1d1d1b;
font:15px/1.6 -apple-system,"Segoe UI","Noto Sans SC",sans-serif}}
h1{{font-size:25px;margin:0 0 4px}}
h2{{font-size:16px;margin:34px 0 2px;padding-top:20px;border-top:1px solid #e3e1db}}
h2 small{{color:#9a958c;font-weight:400;font-size:12.5px}}
.lede{{color:#666;margin:0 0 10px;font-size:14px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(186px,1fr));gap:15px;margin-top:14px}}
.c{{margin:0;background:#fff;border:1px solid #e3e1db;border-radius:10px;overflow:hidden;display:flex;flex-direction:column}}
.c img{{width:100%;display:block;aspect-ratio:2/3;object-fit:cover;background:#eee}}
figcaption{{padding:9px 11px 11px;font-size:12.5px;line-height:1.5;color:#333}}
figcaption b{{color:#981722}}
figcaption span{{color:#777}}
.pg{{display:inline-block;background:#eef2f7;color:#40618c;border-radius:4px;padding:0 5px;font-size:11px}}
.src{{color:#4a6fa5;text-decoration:none}}
.src:hover{{text-decoration:underline}}
</style></head><body>
<h1>政党宣传品 · 分类目录</h1>
<p class="lede">共 {len(plan)} 件，{len(groups)} 类。每件一个文件夹：<code>cover.jpg</code> + <code>pages/</code>（内页）。
图片在 <code>images/分类/</code> 下。</p>
{''.join(blocks)}
</body></html>"""

open(os.path.join(IMG, "分类目录.html"), "w", encoding="utf-8").write(html)
print(f"分类目录.html / 分类目录.csv / 分类.json 已生成")
