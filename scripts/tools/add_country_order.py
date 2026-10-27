"""把新增国别补进次序表（build_catalog.py 与 templates/catalog.html 两处）。

背景：2026-10 第二批海报采入苏联、比利时、瑞典三个新国别，
这两份次序表都未收录，构建时会被排到列表末尾并告警。
两份表必须保持一致，构建脚本会自检。

本脚本幂等：已收录的国别不会重复插入。
"""

import io
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = os.path.join(BASE, "scripts", "build_catalog.py")
TPL = os.path.join(BASE, "scripts", "templates", "catalog.html")

NEW = ["苏联", "比利时", "瑞典"]


def patch_py():
    s = io.open(PY, encoding="utf-8").read()
    m = re.search(r"COUNTRY_ORDER = \[(.*?)\]", s, re.S)
    if not m:
        return "未找到 COUNTRY_ORDER"
    cur = re.findall(r'"([^"]+)"', m.group(1))
    add = [c for c in NEW if c not in cur]
    if not add:
        return "已含全部新国别"
    merged = cur + add
    # 按每行 3 项重排，保持可读
    lines = []
    for i in range(0, len(merged), 3):
        chunk = ", ".join(f'"{c}"' for c in merged[i:i + 3])
        lines.append(chunk)
    body = ("COUNTRY_ORDER = [" + ",\n                 ".join(lines) + "]")
    s = s[:m.start()] + body + s[m.end():]
    io.open(PY, "w", encoding="utf-8", newline="\n").write(s)
    return f"补入 {add}"


def patch_tpl():
    s = io.open(TPL, encoding="utf-8").read()
    m = re.search(r"const COUNTRY_ORDER = \[(.*?)\];", s, re.S)
    if not m:
        return "未找到 const COUNTRY_ORDER"
    cur = re.findall(r'"([^"]+)"', m.group(1))
    add = [c for c in NEW if c not in cur]
    if not add:
        return "已含全部新国别"
    merged = cur + add
    body = "const COUNTRY_ORDER = [\n  " + ",\n  ".join(f'"{c}"' for c in merged) + "];"
    s = s[:m.start()] + body + s[m.end():]
    io.open(TPL, "w", encoding="utf-8", newline="\n").write(s)
    return f"补入 {add}"


def main():
    print("build_catalog.py:", patch_py())
    print("catalog.html    :", patch_tpl())
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
