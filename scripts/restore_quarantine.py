"""从 _误收 精确恢复：把目录里仍存在的条目文件搬回原位，其余才算真删。"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

QUAR = os.path.join(paths.IMAGES, "_误收")
d = catalog.load()

# 目录里仍存在的条目 → 必须恢复
alive = {}
for r in d:
    alive[os.path.basename(r["cover"])] = r

restored = 0
for root, _, files in os.walk(QUAR):
    for f in files:
        if f not in alive:
            continue
        target = os.path.join(paths.IMAGES, alive[f]["dir"].replace("/", os.sep))
        os.makedirs(target, exist_ok=True)
        dst = os.path.join(target, f)
        if not os.path.exists(dst):
            shutil.move(os.path.join(root, f), dst)
            restored += 1

# 清掉空的国别目录
for name in os.listdir(QUAR):
    p = os.path.join(QUAR, name)
    if os.path.isdir(p) and not any(os.scandir(p)):
        os.rmdir(p)

left = sum(len(f) for _, _, f in os.walk(QUAR))
print(f"恢复 {restored} 个文件；_误收 剩余 {left} 个（这些才是真误收）")

# 复核
missing = [r for r in d
           if not os.path.exists(os.path.join(paths.IMAGES, r["cover"].replace("/", os.sep)))]
print(f"目录 {len(d)} 条，封面仍缺失 {len(missing)}")
for r in missing[:5]:
    print("   ", r["country"], r["title"][:44])
