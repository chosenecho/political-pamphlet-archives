"""把候选小册子的首页与内页拼成核对图，人工判断是否政治宣传品。"""

import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "images", "小册子国际", "raw")
OUT = os.path.join(BASE, "images", "_核对.jpg")

IDS = [f"{i:03d}" for i in range(1, 40) if os.path.isdir(os.path.join(RAW, f"{i:03d}"))]


def font(sz):
    for f in ("msyh.ttc", "simhei.ttf"):
        p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", f)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


F = font(13)
COLS, CW, CH = 8, 150, 200
cells = []
for i in IDS:
    d = os.path.join(RAW, i, "pages")
    if not os.path.isdir(d):
        continue
    fs = sorted(os.listdir(d))
    if not fs:
        continue
    try:
        im = Image.open(os.path.join(d, fs[1] if len(fs) > 1 else fs[0])).convert("RGB")
        im.thumbnail((CW - 8, CH - 8), Image.LANCZOS)
        cells.append((i, im, len(fs)))
    except Exception:
        pass

rows = (len(cells) + COLS - 1) // COLS
pad, top = 6, 34
W = COLS * (CW + pad) + pad
H = top + rows * (CH + pad + 18) + pad
sheet = Image.new("RGB", (W, H), (250, 249, 246))
dr = ImageDraw.Draw(sheet)
dr.text((pad + 2, 10), f"国际小册子候选核对（第 2 页）共 {len(cells)} 本", fill=(20, 20, 20), font=font(16))

for k, (i, im, npg) in enumerate(cells):
    cx = pad + (k % COLS) * (CW + pad)
    cy = top + (k // COLS) * (CH + pad + 18)
    dr.rectangle([cx, cy, cx + CW, cy + CH], fill=(232, 230, 225))
    sheet.paste(im, (cx + (CW - im.width) // 2, cy + (CH - im.height) // 2))
    dr.text((cx + 3, cy + CH + 3), f"{i}  {npg}p", fill=(70, 70, 70), font=F)

sheet.save(OUT, "JPEG", quality=86)
print("saved", OUT, sheet.size, "本数", len(cells))
