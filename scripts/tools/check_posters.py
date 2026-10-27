"""核验 posters-new 批次：逐张解码、对账元数据、报告异常。"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.join(BASE, "images", "posters-new")
RAW = os.path.join(ROOT, "raw")


def main():
    from PIL import Image

    meta = json.load(open(os.path.join(ROOT, "metadata.json"), encoding="utf-8"))
    print(f"元数据 {len(meta)} 件\n")

    problems = []
    total = 0
    for it in meta:
        folder = os.path.join(RAW, f"{it['no']:03d}")
        p = os.path.join(folder, "p-00001.jpg")
        if not os.path.exists(p):
            problems.append(f"{it['no']:03d} 文件缺失 {it['title'][:40]}")
            continue
        sz = os.path.getsize(p)
        total += sz
        if sz < 20000:
            problems.append(f"{it['no']:03d} 文件过小 {sz}B {it['title'][:40]}")
        try:
            with Image.open(p) as im:
                im.load()
                w, h = im.size
            if min(w, h) < 400:
                problems.append(f"{it['no']:03d} 尺寸过小 {w}x{h} {it['title'][:40]}")
        except Exception as e:
            problems.append(f"{it['no']:03d} 解码失败 {type(e).__name__} {it['title'][:40]}")

    print(f"合计 {total / 1048576:.1f} MB")
    print(f"问题 {len(problems)} 项")
    for p in problems:
        print("  ✗", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
