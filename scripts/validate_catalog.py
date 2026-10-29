#!/usr/bin/env python3
"""校验 data/catalog.json：字段齐全、kind 合法、封面不重复、立场在词表内。

CI 与本地都用它做前置检查。退出码非 0 即失败。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths
from lib import vocab


def duplicate_padding(records):
    """检查 pages/ 尾部是否有字节相同的重复页，且 pages 把填充页也算了进去。

    返回 [(dir, 文件数, 重复块长度, 真实页数)]；images/ 不存在时返回 None。
    与 fix_duplicates.py 用同一条判据，两边必须一致，否则修完仍会报错。
    """
    import hashlib

    images_root = os.environ.get("DSH_PAMPHLET_IMAGES") or paths.IMAGES
    if not os.path.isdir(images_root):
        return None
    bad = []
    for r in records:
        if r["kind"] != catalog.KIND_BOOK:
            continue
        pages_dir = os.path.join(images_root, r["dir"].replace("/", os.sep), "pages")
        if not os.path.isdir(pages_dir):
            continue
        files = sorted(f for f in os.listdir(pages_dir) if f.lower().endswith(".jpg"))
        if len(files) < 2:
            continue
        hashes = []
        for f in files:
            with open(os.path.join(pages_dir, f), "rb") as fh:
                hashes.append(hashlib.md5(fh.read()).hexdigest())
        block = 0
        for i in range(len(hashes) - 1, 0, -1):
            if hashes[i] == hashes[i - 1]:
                block += 1
            else:
                break
        block = block + 1 if block else 0
        true_pages = len(files) - block
        if block and r["pages"] != true_pages:
            bad.append((r["dir"], len(files), block, true_pages))
    return bad



def main():
    records = catalog.load()
    if not records:
        print(f"目录为空或不存在：{paths.CATALOG}")
        return 1

    st = catalog.stats(records)
    print(f"目录 {st['total']} 条：小册子 {st['books']}、单页 {st['singles']}；"
          f"国家 {st['countries']}、立场 {st['stances']}；"
          f"中文译名 {st['with_zh']}、已归属来源 {st['linked']}")

    # 结构问题：必须失败
    problems = [p for p in catalog.validate(records) if "cover 文件不存在" not in p]
    # 封面缺失：只警告。images/ 不入库，CI 上没有图片属正常
    missing = [p for p in catalog.validate(records) if "cover 文件不存在" in p]

    for p in problems[:20]:
        print("  ✗", p)
    if problems:
        print(f"\n结构问题 {len(problems)} 条")
        return 1

    if missing:
        print(f"  （封面文件 {len(missing)} 个不在本地，images/ 不入库，跳过不视为错误）")

    # 立场词表：未登记的值一律失败。`catalog.save()` 写入时已经拦过一次，
    # 这里再查一遍是为了挡住"绕过 save 直接改 json"的情况——那种改动在
    # git diff 里看起来和正常数据一模一样，只有词表能发现它。
    unregistered = vocab.unknown(r["stance"] for r in records)
    if unregistered:
        for v, n in unregistered:
            print(f"  ✗ stance 未登记：{v!r}（{n} 条）")
        print(f"\n未登记立场 {len(unregistered)} 个——在 scripts/lib/vocab.py 的 "
              f"STANCE 里登记并写明依据")
        return 1

    # 填充页：抓取脚本在内页不足时会把最后一页重复存一遍凑数，pages 若照文件数写
    # 就会把填充页算成真页。这里只在 images/ 存在时检查，CI 上没有图属正常。
    padded = duplicate_padding(records)
    if padded is None:
        print("  （images/ 不在本地，跳过填充页检查）")
    elif padded:
        for dir_, n_files, block, true_pages in padded[:10]:
            print(f"  ✗ {dir_}: {n_files} 个页文件里尾部有 {block} 张字节完全相同，"
                  f"真实页数应为 {true_pages}")
        print(f"\n填充页问题 {len(padded)} 本——先跑 scripts/tools/fix_duplicates.py")
        return 1

    # 模板占位符：目录页由模板生成，占位符写错会让整页空白
    tpl = os.path.join(paths.SCRIPTS, "templates", "catalog.html")
    if not os.path.exists(tpl):
        print(f"  ✗ 模板缺失：{tpl}")
        return 1
    with open(tpl, encoding="utf-8") as f:
        html = f.read()
    need = ["__DATA__", "__STATS__", "__SOURCES__", "__ASSET__", "__BUILD__"]
    absent = [k for k in need if k not in html]
    if absent:
        print(f"  ✗ 模板缺占位符：{'、'.join(absent)}")
        return 1

    # 数据缺口：报告但不失败。这些是已知且已声明的，不是回归
    vs = vocab.stats(records)
    gaps = {
        "立场未标注": vs["unmarked"],
        "来源未归属": sum(1 for r in records if not r["source"]),
        "年份不详": sum(1 for r in records if not r["year"]),
        "无 PDF": sum(1 for r in records if not r["pdf"]),
    }
    print("  缺口：" + " · ".join(f"{k} {v}/{len(records)}" for k, v in gaps.items()))
    print(f"  立场词表：登记 {vs['registered']} 个，已用 {vs['used']} 个"
          + (f"；预留未命中 {vs['reserved']}" if not vs["reserved_hit"] else ""))

    print("校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
