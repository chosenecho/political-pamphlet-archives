"""Commons 采集后处理：统一成适度的 JPG，并写并入所需元数据。

Commons 原图动辄 7000x12000 / 74MB，直接入库会让目录页与阅读器卡顿，
也不便于归档。处理策略：
  - 长边压到 2000px 以内（足够看清海报文字与版式）
  - 统一存为 JPEG，质量 88
  - 保留原始 Commons 页面 URL 供回溯
  - 同时写入 metadata.json，字段与 ia 批次一致，便于统一并入
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "images", "commons-new")
RAW = os.path.join(ROOT, "raw")

MAX_SIDE = 2000
QUALITY = 88


def main():
    from PIL import Image

    meta_path = os.path.join(ROOT, "metadata.json")
    items = json.load(open(meta_path, encoding="utf-8"))
    print(f"处理 {len(items)} 件\n")

    for it in items:
        folder = os.path.join(RAW, f"{it['no']:03d}")
        files = [f for f in os.listdir(folder) if not f.endswith(".part")]
        if not files:
            print(f"  {it['no']:03d} 无文件，跳过")
            continue
        src = os.path.join(folder, files[0])
        dest = os.path.join(folder, "p-00001.jpg")

        try:
            with Image.open(src) as im:
                w0, h0 = im.size
                im = im.convert("RGB")
                scale = min(1.0, MAX_SIDE / max(w0, h0))
                if scale < 1.0:
                    im = im.resize((max(1, int(w0 * scale)), max(1, int(h0 * scale))),
                                   Image.LANCZOS)
                im.save(dest, "JPEG", quality=QUALITY, optimize=True)
            if os.path.abspath(src) != os.path.abspath(dest):
                os.remove(src)
            sz = os.path.getsize(dest) / 1024
            print(f"  {it['no']:03d} {it['country']:4s} {it['year']} "
                  f"{w0}x{h0} -> {im.size[0]}x{im.size[1]}  {sz:.0f}KB")
            it["file"] = "p-00001.jpg"
            it["orig_size"] = [w0, h0]
        except Exception as e:
            print(f"  {it['no']:03d} 处理失败 {type(e).__name__}")

    json.dump(items, open(meta_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    total = sum(os.path.getsize(os.path.join(RAW, d, "p-00001.jpg"))
                for d in os.listdir(RAW)
                if os.path.exists(os.path.join(RAW, d, "p-00001.jpg")))
    print(f"\n合计 {total / 1048576:.1f} MB")


if __name__ == "__main__":
    main()
