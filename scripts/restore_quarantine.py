"""从 _误收 精确恢复：把索引里仍存在的条目文件搬回原位，其余才算真删。"""

import json
import os
import shutil

d = json.load(open("images/索引.json", encoding="utf-8"))
QUAR = "images/_误收"

# 索引里仍存在的条目 → 必须恢复
alive = {}
for r in d:
    alive[os.path.basename(r["cover"])] = r

restored = 0
for root, _, files in os.walk(QUAR):
    for f in files:
        if f not in alive:
            continue
        target = os.path.join("images", alive[f]["dir"])
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
missing = [r for r in d if not os.path.exists(os.path.join("images", r["cover"]))]
print(f"索引 {len(d)} 条，封面仍缺失 {len(missing)}")
for r in missing[:5]:
    print("   ", r["country"], r["title"][:44])
