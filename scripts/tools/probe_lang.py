"""验证 IA 语言字段的正确写法（MARC 代码 vs 全称）。"""

import json
import ssl
import urllib.parse
import urllib.request

UA = "PamphletArchiveBot/1.0 (https://github.com/chosenecho/political-pamphlet-archives; research@example.org)"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def count(q):
    p = {"q": q, "fl[]": ["identifier"], "rows": "0", "output": "json"}
    u = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(p, doseq=True)
    d = json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60).read())
    return d["response"]["numFound"]


TESTS = [
    'language:(German)',
    'language:(ger)',
    'language:(German) AND subject:(Sozialismus)',
    'language:(ger) AND subject:(Sozialismus)',
    'language:(fre) AND subject:(politique)',
    'language:(rus) AND subject:(revolution)',
    'language:(ita) AND subject:(politica)',
    'language:(spa) AND subject:(política)',
    'language:(dut) AND subject:(politiek)',
    'language:(pol) AND subject:(polityka)',
]

for q in TESTS:
    try:
        print(f"{count(q):>8}  {q}")
    except Exception as e:
        print(f"     ERR  {q}  {type(e).__name__}")

print("\n=== 带页数限制后 ===")
LANG = {"ger": "德国", "fre": "法国", "rus": "俄国", "ita": "意大利",
        "spa": "西班牙", "dut": "荷兰", "pol": "波兰", "swe": "瑞典", "hun": "匈牙利"}
for code, name in LANG.items():
    q = f'language:({code}) AND imagecount:[10 TO 64] AND year:[1880 TO 1945]'
    try:
        print(f"{count(q):>8}  {name} ({code})")
    except Exception as e:
        print(f"     ERR  {name}")
