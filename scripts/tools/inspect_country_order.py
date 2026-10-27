"""从 build_catalog.py 与模板中提取「我的次序表改动」为独立补丁。

问题：并发协作下 build_catalog.py 同时含两方改动——我的次序表追加三国，
另一会话的模板渲染重构。直接提交会把对方未完成的重构带上。

做法：把当前文件里 COUNTRY_ORDER 这一处（只含我追加的三国）单独提交，
其余行保持他们工作区里的样子不动。脚本仅用于审计，不修改文件。
"""

import io
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    for rel in ("scripts/build_catalog.py", "scripts/templates/catalog.html"):
        p = os.path.join(BASE, rel)
        s = io.open(p, encoding="utf-8").read()
        m = re.search(r"(?:const\s+)?COUNTRY_ORDER = \[(.*?)\]", s, re.S)
        if not m:
            print(f"{rel}: 未找到 COUNTRY_ORDER")
            continue
        names = re.findall(r'"([^"]+)"', m.group(1))
        print(f"{rel}")
        print(f"  共 {len(names)} 个国别")
        tail = names[-4:]
        print(f"  末尾四项: {tail}")
        for c in ("苏联", "比利时", "瑞典"):
            print(f"  含 {c}: {c in names}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
