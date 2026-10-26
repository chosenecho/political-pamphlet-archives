"""为每个分类生成一张缩略总览，便于快速浏览。"""

import json
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")
DEST = os.path.join(IMG, "分类")
OUT = os.path.join(IMG, "分类总览")
os.makedirs(OUT, exist_ok=True)

COLS, CW, CH = 6, 214, 300


def load_font(size):
    for name in ("msyh.ttc", "msyhl.ttc", "simhei.ttf", "simsun.ttc",
                 "NotoSansCJK-Regular.ttc", "PingFang.ttc"):
        p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


F_TITLE = load_font(17)
F_LABEL = load_font(13)
plan = json.load(open(os.path.join(IMG, "分类.json"), encoding="utf-8"))

groups = {}
for p in plan:
    groups.setdefault(p["cat"], []).append(p)


def sheet(cat, items):
    cells = []
    for p in sorted(items, key=lambda x: str(x["year"])):
        fp = os.path.join(IMG, p["cover"])
        if not os.path.exists(fp):
            continue
        try:
            im = Image.open(fp).convert("RGB")
            im.thumbnail((CW - 10, CH - 10), Image.LANCZOS)
            cells.append((p, im))
        except Exception as e:
            print(f"   skip {p['no']} {p['title'][:20]}: {type(e).__name__}")
    if not cells:
        return None

    rows = (len(cells) + COLS - 1) // COLS
    pad, top = 8, 50
    W = COLS * (CW + pad) + pad
    H = top + rows * (CH + pad + 22) + pad
    im_out = Image.new("RGB", (W, H), (247, 246, 243))
    d = ImageDraw.Draw(im_out)
    d.text((pad + 2, 14), f"{cat}  ·  {len(cells)} 件", fill=(30, 30, 30), font=F_TITLE)

    for i, (p, im) in enumerate(cells):
        cx = pad + (i % COLS) * (CW + pad)
        cy = top + (i // COLS) * (CH + pad + 22)
        d.rectangle([cx, cy, cx + CW, cy + CH], fill=(232, 230, 225))
        im_out.paste(im, (cx + (CW - im.width) // 2, cy + (CH - im.height) // 2))
        d.text((cx + 3, cy + CH + 4), f'{p["year"]} {p["title"][:14]}', fill=(85, 85, 85), font=F_LABEL)

    path = os.path.join(OUT, cat.replace(" ", "_") + ".jpg")
    im_out.save(path, "JPEG", quality=84)
    return path


made = []
for cat in sorted(groups):
    r = sheet(cat, groups[cat])
    if r:
        made.append((cat, r, os.path.getsize(r)))

print(f"生成 {len(made)} 张分类总览")
for cat, r, sz in made:
    print(f"  {cat:26s} {sz/1024:6.0f} KB")
