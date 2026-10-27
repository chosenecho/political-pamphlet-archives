"""把中文译名写入目录。可重复运行（幂等）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths

sys.path.insert(0, paths.SCRIPTS)
from title_zh import TITLE_ZH

d = catalog.load()

n = 0
for r in d:
    if r["country"] == "中国":
        r["title_zh"] = ""
        continue
    zh = TITLE_ZH.get(r["title"], "")
    r["title_zh"] = zh
    n += 1

catalog.save(d)

have = sum(1 for r in d if r.get("title_zh"))
zh_cn = sum(1 for r in d if r["country"] == "中国")
print(f"已写入 title_zh：{have}/{len(d)} 条（中国 {zh_cn} 条无需翻译）")
