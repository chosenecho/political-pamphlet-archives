#!/usr/bin/env python3
"""修复目录中的重复与失真：尾部填充页、同一本书重复登记、无来源的站点根 URL。

背景
    抓取脚本在内页不足时会把最后一页再存一遍凑数，同一张图因此占了多个页码文件。
    catalog.json 的 pages 当时是照文件数写的，于是把填充页也算成了真页。
    肉眼看不出来：文件齐、页数"对得上"、校验脚本也过，只有比对 PDF 才露馅。

本脚本做四件事，每件都可单独跑：

    1. pages  —— 按尾部重复块求真实页数（交叉验证见 --verify）
    2. dup     —— 把同一本书的重复登记合并掉
    3. url     —— 清掉指向站点根、无法回溯到具体条目的 URL
    4. prune   —— 打印冗余填充页清单（配合 --prune-files 才真删）

    真实页数 = 文件数 - 尾部连续重复块长度
    块内第一张也算填充：它和后面几张是同一个字节流，不是那一页的真扫描。

只改 data/catalog.json；物理文件默认不动。

用法
    python scripts/tools/fix_duplicates.py --dry            # 只看会改什么
    python scripts/tools/fix_duplicates.py                  # 改 catalog
    python scripts/tools/fix_duplicates.py --prune-files    # 另把冗余填充页移入隔离区
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import index as catalog
from lib import paths

#: images/ 不在版本控制里，因此 repair worktree 往往没有图。
#: 用 DSH_PAMPHLET_IMAGES 指向真正存图的那份工作目录。
IMAGES = os.environ.get("DSH_PAMPHLET_IMAGES") or paths.IMAGES

#: 冗余填充页的隔离目录（与 purge_misfiled.py 的 images/_隔离 并列，不入库）
QUARANTINE = os.path.join(IMAGES, "_填充页")

#: 指向站点根、无法回溯到具体条目的 URL。这类值等于把 url 字段作废，
#: 留着比留空更坏：下游按域名回填 source 时会把整站误认成来源。
ROOT_URLS = {
    "https://commons.wikimedia.org",
    "http://commons.wikimedia.org",
    "https://archive.org",
    "http://archive.org",
}


# --- 1. 真实页数 -----------------------------------------------------------

def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pdf_page_objects(path):
    """数 PDF 里可见的 /Type /Page 对象；对象流压缩过的返回 0（无法判断）。"""
    if not os.path.isfile(path):
        return 0
    with open(path, "rb") as f:
        data = f.read()
    return len(re.findall(rb"/Type\s*/Page(?![s])", data))


def tail_block(hashes):
    """尾部连续字节相同的最长一段长度；没有重复返回 0。"""
    k = 0
    for i in range(len(hashes) - 1, 0, -1):
        if hashes[i] == hashes[i - 1]:
            k += 1
        else:
            break
    return k + 1 if k else 0


def scan_booklet(rec):
    """返回该小册子的页文件分析结果；目录不存在时返回 None。"""
    folder = os.path.join(IMAGES, rec["dir"].replace("/", os.sep))
    pages_dir = os.path.join(folder, "pages")
    if not os.path.isdir(pages_dir):
        return None
    files = sorted(f for f in os.listdir(pages_dir) if f.lower().endswith(".jpg"))
    if not files:
        return None
    hashes = [md5(os.path.join(pages_dir, f)) for f in files]
    block = tail_block(hashes)
    return {
        "folder": folder,
        "pages_dir": pages_dir,
        "files": files,
        "hashes": hashes,
        "n_files": len(files),
        "block": block,
        "true_pages": len(files) - block,
        "first_filler": len(files) - block + 1 if block else None,
        "pdf_pages": pdf_page_objects(os.path.join(folder, "doc.pdf")),
    }


# --- 2. 重复登记 -----------------------------------------------------------

def merge_duplicates(records):
    """同一本实体书被登记两次时合并：保留有 url 的一条，页数取真值。

    判据是页图字节流高度重合，而不是标题——同一作品的不同版次标题也可能一样。
    这里只在「页图完全重合」时才合并，宁可少合并也不误删。
    """
    books = [r for r in records if r["kind"] == catalog.KIND_BOOK]
    scans = {}
    for r in books:
        s = scan_booklet(r)
        if s:
            scans[r["dir"]] = s

    groups = []
    seen = set()
    for a in books:
        if a["dir"] in seen or a["dir"] not in scans:
            continue
        sa = scans[a["dir"]]
        seta = set(sa["hashes"])
        group = [a]
        for b in books:
            if b is a or b["dir"] in seen or b["dir"] not in scans:
                continue
            sb = scans[b["dir"]]
            # 页数一致且页图集合完全相同时才认定为同一实体
            if sa["true_pages"] == sb["true_pages"] and seta == set(sb["hashes"]):
                group.append(b)
        if len(group) > 1:
            groups.append(group)
            seen.update(x["dir"] for x in group)
    return groups, scans


def pick_survivor(group, scans):
    """组内保留哪条：优先有 url 的，其次页数等于真值的，最后取先登记的。"""
    def score(r):
        s = scans.get(r["dir"])
        true_pages = s["true_pages"] if s else r["pages"]
        return (
            1 if r.get("url") else 0,
            1 if r["pages"] == true_pages else 0,
            1 if r.get("pdf") else 0,
        )
    return sorted(group, key=score, reverse=True)[0]


# --- 3. 无来源的站点根 URL -------------------------------------------------

def normalize_root_url(url):
    return (url or "").strip().rstrip("/").lower()


def is_root_url(url):
    return normalize_root_url(url) in {u.rstrip("/").lower() for u in ROOT_URLS}


def provenance_from_pdf(folder):
    """从扫描件自带的元数据里找回真实出处。

    只认 PDF 里**写死的标识符**：archive.org 的 details 路径、Commons 的 File: 页。
    标题、Creator 之类的自由文本不作依据——那只能证明"某人数字化过"，指不回条目。
    """
    path = os.path.join(folder, "doc.pdf")
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as f:
        data = f.read()
    for pattern, template in (
        (rb"archive\.org/details/([A-Za-z0-9._\-]{4,80})",
         "https://archive.org/details/{}"),
        (rb"commons\.wikimedia\.org/wiki/File:([^\s\)>\"']{4,120})",
         "https://commons.wikimedia.org/wiki/File:{}"),
    ):
        m = re.search(pattern, data)
        if m:
            return template.format(m.group(1).decode("utf-8", "replace"))
    return ""


# --- main ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只报告，不写文件")
    ap.add_argument("--prune-files", action="store_true",
                    help="把冗余填充页移入 images/_填充页/（可回滚，不删除）")
    ap.add_argument("--verify", action="store_true",
                    help="与 PDF 页数交叉验证，仅报告不一致")
    args = ap.parse_args()

    records = catalog.load()
    if not records:
        raise SystemExit(f"目录为空：{paths.CATALOG}")
    before = len(records)

    # --- 2. 合并重复登记（先做，避免对即将移除的记录算页数）
    groups, scans = merge_duplicates(records)
    drop = set()
    merges = []
    for g in groups:
        keep = pick_survivor(g, scans)
        for r in g:
            if r is not keep:
                drop.add(r["dir"])
                merges.append((r, keep))
    records = [r for r in records if r["dir"] not in drop]

    # --- 1. 页数按真值回写
    page_fixes = []
    for r in records:
        if r["kind"] != catalog.KIND_BOOK:
            continue
        s = scans.get(r["dir"]) or scan_booklet(r)
        if not s:
            continue
        if r["pages"] != s["true_pages"]:
            page_fixes.append((r, r["pages"], s["true_pages"]))
            r["pages"] = s["true_pages"]

    # --- 3. 站点根 URL：能从扫描件元数据找回真出处的就回填，否则清空
    url_fixes = []
    recovered = []
    for r in records:
        if not is_root_url(r.get("url")):
            continue
        folder = os.path.join(IMAGES, r["dir"].replace("/", os.sep))
        real = provenance_from_pdf(folder)
        if real:
            recovered.append((r, r["url"], real))
            r["url"] = real
        else:
            url_fixes.append((r, r["url"]))
            r["url"] = ""

    # --- 报告
    print(f"目录 {before} 条" + (f" → {len(records)} 条" if drop else ""))
    print()
    if merges:
        print(f"合并重复登记 {len(merges)} 条：")
        for r, keep in merges:
            print(f"  删除 {r['country']}/{r['title'][:44]}")
            print(f"       └ 并入 {keep['country']}/{os.path.basename(keep['dir'])[:44]}"
                  f"  (url={keep.get('url') or '无'})")
    else:
        print("合并重复登记：无")
    print()
    if page_fixes:
        print(f"页数回写 {len(page_fixes)} 条（文件数 → 真实页数）：")
        for r, old, new in page_fixes:
            print(f"  {old:>3} → {new:>3}  {r['country']}/{r['title'][:52]}")
    else:
        print("页数回写：无")
    print()
    if recovered:
        print(f"从扫描件元数据找回出处 {len(recovered)} 条：")
        for r, old, new in recovered:
            print(f"  {r['country']}/{r['title'][:44]}")
            print(f"      {new}")
    else:
        print("从扫描件元数据找回出处：无")
    print()
    if url_fixes:
        print(f"清除站点根 URL {len(url_fixes)} 条（PDF 内无出处，留空而非猜测）：")
        for r, u in url_fixes:
            print(f"  {u}  {r['country']}/{r['title'][:48]}")
    else:
        print("清除站点根 URL：无")

    if args.verify:
        print("\n与 PDF 页数交叉验证：")
        agree = diff = unknown = 0
        for r in records:
            if r["kind"] != catalog.KIND_BOOK:
                continue
            s = scan_booklet(r)
            if not s:
                continue
            if not s["pdf_pages"]:
                unknown += 1
            elif s["pdf_pages"] == s["true_pages"]:
                agree += 1
            else:
                diff += 1
                print(f"  ✗ {r['country']}/{r['title'][:44]}"
                      f"  页图={s['true_pages']} PDF={s['pdf_pages']}")
        print(f"  一致 {agree}　不一致 {diff}　PDF 不可解析 {unknown}")

    # --- 隔离冗余填充页
    if args.prune_files:
        moved = 0
        for r in records:
            s = scans.get(r["dir"]) or scan_booklet(r)
            if not s or not s["block"]:
                continue
            dest = os.path.join(QUARANTINE, r["dir"].replace("/", os.sep), "pages")
            os.makedirs(dest, exist_ok=True)
            for f in s["files"][s["true_pages"]:]:
                src = os.path.join(s["pages_dir"], f)
                dst = os.path.join(dest, f)
                if os.path.exists(dst):
                    continue
                shutil.move(src, dst)
                moved += 1
        print(f"\n隔离冗余填充页 {moved} 张 → {QUARANTINE}")

    if args.dry:
        print("\n[dry] 未写入。")
        return 0

    if not (merges or page_fixes or url_fixes or recovered):
        print("\n无需改动。")
        return 0

    catalog.save(records)
    print(f"\n已写入 {paths.CATALOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
