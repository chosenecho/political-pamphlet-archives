"""把中文译名写入索引。可重复运行。"""

import json
import sys

sys.path.insert(0, "scripts")
from title_zh import TITLE_ZH

P = "images/索引.json"
d = json.load(open(P, encoding="utf-8"))

n = 0
for r in d:
    if r["country"] == "中国":
        r["title_zh"] = ""
        continue
    zh = TITLE_ZH.get(r["title"], "")
    r["title_zh"] = zh
    n += 1

json.dump(d, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

have = sum(1 for r in d if r.get("title_zh"))
print(f"已写入 title_zh：{have}/{len(d)} 条（中国 {sum(1 for r in d if r['country']=='中国')} 条无需翻译）")
