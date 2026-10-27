"""解决 rebase 冲突：站名一律采用 main（HEAD）版本。

冲突成因：main 上有一次站名统一改动（「政党宣传品」→「歷史宣傳材料檔案」），
本分支基于改名前的版本，两边的标题行因此冲突。站名属于对方已经定稿的
内容，一律取 HEAD。

只处理 README.md 与 scripts/templates/catalog.html 里的冲突块；
docs/index.html 不在此处理——它由 build_catalog.py 从数据重建。
"""

import io
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resolve_head(path):
    """把每个冲突块替换为 HEAD 侧内容。"""
    s = io.open(path, encoding="utf-8").read()
    if "<<<<<<<" not in s:
        return 0, s
    out, n, i = [], 0, 0
    lines = s.split("\n")
    mode = None
    for ln in lines:
        if ln.startswith("<<<<<<<"):
            mode = "head"
            n += 1
            continue
        if ln.startswith("=======") and mode == "head":
            mode = "theirs"
            continue
        if ln.startswith(">>>>>>>") and mode == "theirs":
            mode = None
            continue
        if mode == "theirs":
            continue
        out.append(ln)
    return n, "\n".join(out)


def main():
    total = 0
    for rel in ("README.md", "scripts/templates/catalog.html"):
        p = os.path.join(BASE, rel)
        n, s = resolve_head(p)
        if n:
            io.open(p, "w", encoding="utf-8", newline="\n").write(s)
            print(f"{rel}: 解决 {n} 处冲突（取 HEAD）")
            total += n
        else:
            print(f"{rel}: 无冲突")
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
