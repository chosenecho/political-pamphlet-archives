"""回填 manifest 中缺失的 via 字段。

依据：crawl.py 在抓取成功时写出 raw/{slug}.html。文件存在即证明该记录由
urllib 抓取产生，因此可安全标注 via="urllib-crawl"，不是猜测。
没有任何证据的保持为空。
"""

import json
import os

MAN = 'data/manifest.json'
RAW = 'raw'

raw = {f[:-5] for f in os.listdir(RAW) if f.endswith('.html')}
man = json.load(open(MAN, encoding='utf-8'))

filled = kept = 0
for r in man:
    if r.get('via'):
        continue
    if r['slug'] in raw:
        r['via'] = 'urllib-crawl'
        filled += 1
    else:
        kept += 1

json.dump(man, open(MAN, 'w', encoding='utf-8', newline='\n'),
          ensure_ascii=False, indent=2)
print(f'回填 {filled} 条，无证据保持为空 {kept} 条')
