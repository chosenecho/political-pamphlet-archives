"""逐条校验目录中封面文件可用性（不依赖浏览器懒加载）。"""

import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

records = catalog.load()
bad = []
for r in records:
    p = os.path.join(paths.IMAGES, r["cover"].replace("/", os.sep))
    if not os.path.exists(p):
        bad.append((r["country"], r["title"][:40], "缺失"))
        continue
    try:
        with Image.open(p) as im:
            im.verify()
    except Exception as e:
        bad.append((r["country"], r["title"][:40], type(e).__name__))

print(f"目录 {len(records)} 条，问题文件 {len(bad)}")
for b in bad:
    print("   ", b)
sys.exit(1 if bad else 0)
