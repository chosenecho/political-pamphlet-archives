"""删除误收条目：移入 images/_误收 而非直接销毁，可回滚。"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

QUAR = os.path.join(paths.IMAGES, "_误收")

d = catalog.load()

# 判定标准：译名里已标注「误收」，或明显非政宣材料
def is_misfiled(r):
    zh = r.get("title_zh") or ""
    if "误收" in zh:
        return True
    t = (r["title"] or "").lower()
    return any(k in t for k in (
        "we can do it", "rosie the riveter", "nerium oleander",
        "quo vadis", "aida poster", "gillette de narbonne",
        "le mage", "trans-australian railway", "jupiter inlet",
        "urbanscape".lower(),
    ))

bad = [r for r in d if r["country"] != "中国" and is_misfiled(r)]
good = [r for r in d if r not in bad]

print(f"待删 {len(bad)} 条：")
for r in bad:
    print(f'  {r["country"]}\t{r.get("year","")}\t{(r.get("title_zh") or r["title"])[:52]}')

os.makedirs(QUAR, exist_ok=True)
moved_dir = moved_file = 0
for r in bad:
    src = os.path.join(paths.IMAGES, r["dir"].replace("/", os.sep))
    dst = os.path.join(QUAR, r["country"], os.path.basename(r["dir"]))
    if os.path.isdir(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):
            shutil.move(src, dst)
            moved_dir += 1
    else:
        f = os.path.join(paths.IMAGES, r["cover"].replace("/", os.sep))
        if os.path.isfile(f):
            os.makedirs(os.path.join(QUAR, r["country"]), exist_ok=True)
            dstf = os.path.join(QUAR, r["country"], os.path.basename(f))
            if not os.path.exists(dstf):
                shutil.move(f, dstf)
                moved_file += 1

catalog.save(good)

from collections import Counter
print(f"\n移走目录 {moved_dir} 个、文件 {moved_file} 个")
print(f"索引剩 {len(good)} 条（原 {len(d)}）")
print("国别：", dict(Counter(r["country"] for r in good).most_common()))
