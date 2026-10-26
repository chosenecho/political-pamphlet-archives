"""逐条校验索引文件可用性（不依赖浏览器懒加载）。"""

import json
import os

from PIL import Image

d = json.load(open("images/索引.json", encoding="utf-8"))

bad = []
for r in d:
    p = os.path.join("images", r["cover"])
    if not os.path.exists(p):
        bad.append((r["country"], r["title"][:40], "缺失"))
        continue
    try:
        with Image.open(p) as im:
            im.verify()
    except Exception as e:
        bad.append((r["country"], r["title"][:40], type(e).__name__))

print(f"索引 {len(d)} 条，问题文件 {len(bad)}")
for b in bad:
    print("   ", b)
