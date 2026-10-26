import json
import os

IMG = os.path.join("images")
plan = json.load(open(os.path.join(IMG, "分类.json"), encoding="utf-8"))

bad = [p for p in plan if not os.path.exists(os.path.join(IMG, p["cover"]))]
print(f"条目 {len(plan)}，封面路径无效 {len(bad)}")
for p in bad[:10]:
    print("  ", p["no"], p["cover"])

no_pages = [p for p in plan if p["page_count"] == 0]
print(f"无内页条目 {len(no_pages)}（西方 39 件预期无内页）")
for p in no_pages[:8]:
    print("  ", p["no"], p["year"], p["title"][:30], p["cat"])

# 检查空目录
empty = []
for cat in sorted(os.listdir(os.path.join(IMG, "分类"))):
    cp = os.path.join(IMG, "分类", cat)
    for it in sorted(os.listdir(cp)):
        ip = os.path.join(cp, it)
        if not os.path.isdir(ip):
            continue
        files = os.listdir(ip)
        if "cover.jpg" not in files:
            empty.append(f"{cat}/{it}")
print(f"缺 cover.jpg 的文件夹 {len(empty)}")
for e in empty[:10]:
    print("  ", e)

# 统计
tot_pages = sum(p["page_count"] for p in plan)
size = sum(os.path.getsize(os.path.join(dp, f))
           for dp, _, fs in os.walk(os.path.join(IMG, "分类")) for f in fs)
print(f"\n内页合计 {tot_pages} 张，总体积 {size/1048576:.1f} MB")
