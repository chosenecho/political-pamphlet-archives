"""查重清理：删除确认重复的两条记录。

一、中国《李长胜捉俘虏》（1946，晋察冀边区教育阵地社）
    两条 URL 完全相同（fileCode=0001_ts_311051），是同一份文献的两次抓取：
      · 006 —— 10 页，较早的不完整抓取
      · 011 —— 13 页，更完整，且图像质量更好
    两版页图哈希无一相同（不同批次扫描），但封面视觉比对确认为同一本书
    （版式、题名、插图、出版项完全一致）。保留 011，删除 006。

二、德国反犹选举海报（1921 年 Fuchs 书中收录的 1920 年国会选举海报）
    Commons 上同一图像有「cropped」与完整两个版本：
      · 007 —— 1683×2025，文件名带 cropped
      · 008 —— 1791×2205，完整版
    保留完整的 008，删除裁切版 007。

其余标题相同的条目经核验不是重复：
  · American Library Association 三条 —— NARA 编号 20801784 / 20801786 / 20801782，
    是三张不同海报，标题被截断才显得相同
  · Food Administration 三条 —— NARA 31482308 / 31482466 / 31482366，同理

默认只改 catalog，不动磁盘文件；加 --prune-files 才把目录移入隔离区。
"""

import json
import os
import re
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import index as catalog
from lib import paths

#: (要删除的 dir, 保留的 dir, 理由)
DROP = [
    ("小册子/中国/006_1946_李长胜捉俘虏",
     "小册子/中国/011_1946_李长胜捉俘虏",
     "同一 URL 的两次抓取，006 仅 10 页，011 有 13 页更完整"),
    ("传单与海报/按国别/02-德国", None,
     None),  # 这条按 cover 单独判定，见下
]

#: 同一图像的 cropped 版本：url 里含 "cropped"，且去掉该词后能找到对应完整版。
#: 注意 url 里的括号是百分号编码（%28cropped%29），不能用 endswith("cropped.jpg")。
def base_name(url):
    """解码 url 里的 Commons 文件名，去掉尺寸/裁切等版本后缀，用于配对。

    注意顺序：先解码百分号编码（括号在 url 里是 %28cropped%29），
    再去掉扩展名，最后剥掉版本后缀。扩展名不去掉的话 "cropped" 后面
    还跟着 "jpg"，正则匹配不到字符串末尾，裁切版就识别不出来。
    """
    s = (url or "").split("/File:")[-1]
    s = re.sub(r"%([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r"\.(jpg|jpeg|png|gif)$", "", s, flags=re.I)
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", s).lower()
    s = re.sub(r"(cropped|hqed|digitalisedversion|smooth)$", "", s)
    return s


def find_cropped_dupes(records):
    """返回需要删除的 cropped 条目：同基名存在非 cropped 版本时，删 cropped。"""
    groups = {}
    for r in records:
        u = r.get("url", "")
        if not u:
            continue
        groups.setdefault(base_name(u), []).append(r)
    drop = []
    for k, v in groups.items():
        if len(v) < 2:
            continue
        full = [x for x in v if "cropped" not in (x.get("url") or "").lower()]
        crop = [x for x in v if "cropped" in (x.get("url") or "").lower()]
        if full and crop:
            for c in crop:
                drop.append((c, f"同一图像的裁切版，已保留完整版（{full[0]['title'][:40]}）"))
    return drop


QUARANTINE = os.path.join(paths.IMAGES, "_重复")


def main():
    dry = "--dry" in sys.argv
    prune = "--prune-files" in sys.argv
    recs = catalog.load()
    before = len(recs)

    keep = []
    removed = []

    for r in recs:
        # 1) 中国那本：dir 精确匹配
        if r["dir"] == "小册子/中国/006_1946_李长胜捉俘虏":
            removed.append((r, "中国《李长胜捉俘虏》10 页旧抓取，011 更完整"))
            continue
        # 2) cropped 版本由 find_cropped_dupes() 统一处理，见下
        keep.append(r)

    # 2) cropped 版本：同基名存在完整版时删裁切版
    crop_drop = find_cropped_dupes(keep)
    if crop_drop:
        drop_ids = {id(r) for r, _ in crop_drop}
        keep = [r for r in keep if id(r) not in drop_ids]
        removed.extend(crop_drop)

    print(f"目录 {before} → {len(keep)} 条，删除 {len(removed)} 条\n")
    for r, why in removed:
        print(f"  删除 {r['country']} {r['year']} {r['title'][:52]}")
        print(f"       {why}")
        print(f"       dir={r['dir']}")

    if dry:
        print("\n[预演] 未写入")
        return 0

    catalog.save(keep)
    print("\n已写入 data/catalog.json")

    if prune:
        for r, _ in removed:
            src = os.path.join(paths.IMAGES, r["dir"].replace("/", os.sep))
            if not os.path.isdir(src):
                continue
            dst = os.path.join(QUARANTINE, r["dir"].replace("/", os.sep))
            if os.path.exists(dst):
                print(f"  隔离区已存在，跳过 {r['dir']}")
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            print(f"  移入隔离区 {r['dir'][:60]}")
    else:
        print("（磁盘文件未动；加 --prune-files 可移到 images/_重复/）")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
