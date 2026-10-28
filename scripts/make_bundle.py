"""把目录与阅读器打成可直接分发的离线包。

为什么需要单独打包，而不是把仓库目录 zip 一下：
  仓库里 docs/index.html 用 ../images/ 定位图像，依赖它上一级有 images/。
  压缩包发出去后，对方多半只解压一个子目录，或者解压工具多套一层文件夹，
  相对路径就断了——对方打开看到满屏"图像不在本机"，会以为是空壳。
  所以包内重新组织：页面与图像同级，双击即生效。

另一个坑是文件名。仓库存的是中文目录（小册子/中国/001_...），
zip 里写 UTF-8 名虽然有 0x800 标志位，但部分解压工具仍按本地代码页解读，
解出来就是乱码。包内因此改用纯 ASCII 目录，中文标题存在 HTML 数据里，
文件名对不对得上不影响阅读。

两种档位
  lite  700px WebP，实测该档正文字仍清晰可读；约 300 MB
  full  原始分辨率，仅重编码为 WebP 无损尺寸；约 1.0–1.3 GB
"""

import argparse
import csv
import io
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import zipfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths
from templates import render

OUT_DIR = os.path.join(paths.BASE, "dist")
BUILD = os.path.join(paths.BASE, "build")

#: 分发包内的目录名，全部 ASCII，避免任何解压工具的编码问题
PKG_PAGES = "pages"

#: 包内页面规则：d.d 就是内页目录，页文件名 p-00001.<ext>。
#: dir 必须带结尾斜杠——d.d 是 "pages/000"（无尾斜杠），少了它拼出来的
#: 是 "pages/000p-00001.webp"，静默 404。线上的 "/pages/" 同理。
#: ext 随档位变化：精简版 .webp，全分辨率版 .jpg（见 page_rule()）。
def page_rule(tier):
    ext = ".jpg" if TIERS[tier]["copy"] else ".webp"
    return {"dir": '"/"', "prefix": '"p-"', "ext": f'"{ext}"', "pad": "5"}

#: 档位参数。copy=True 表示直接拷原始文件、不做任何重编码。
TIERS = {
    "lite": {"max_w": 700, "quality": 75, "label": "精简版", "copy": False},
    # 全分辨率档直接拷原始 jpg，不转 WebP：原始扫描件已是 JPEG，再转属有损二次
    # 压缩，实测只小 7%，却多留一道压缩痕迹。拷原图既保真又快。
    "full": {"max_w": None, "quality": 0, "label": "全分辨率版", "copy": True},
}

BANNER = """歷史宣傳材料檔案 · 离线包
==================================================

怎么打开
  解压后双击 index.html，用浏览器打开即可。
  不需要安装任何东西，不需要联网，不需要起服务器。

包内结构
  index.html        目录与阅读器（全部条目、筛选、翻页）
  目录.csv          同样的条目表，可用 Excel 打开
  pages/            扫描图像，按条目编号分目录
  免责声明.txt      使用边界与来源说明

注意
  本包含有法西斯主义、殖民主义、种族主义等今日极具争议的历史材料，
  收录不等于认同。仅供学术研究与教学使用，请勿再分发。
  扫描件版权属各原藏机构与捐赠者。

生成于 {date}
"""


def slug(i):
    """包内编号：与目录里的顺序一一对应，便于人工核对。"""
    return f"{i:03d}"


def encode(src, dst, max_w, quality):
    """转成 WebP。已是目标尺寸的也重编码一次，统一格式与体积。

    method=4 而非最高档 6：实测 6 档每张多花约一倍时间，体积只小 3%，
    这里几万张图，时间比那 3% 值钱。反正最终还要 zip 再压一次。
    """
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB")
        if max_w and im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        im.save(dst, "WEBP", quality=quality, method=4)


def _encode_job(args):
    """多进程入口：顶层函数，才能被 pickle。"""
    src, dst, max_w, quality, copy = args
    try:
        if copy:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
        else:
            encode(src, dst, max_w, quality)
        return (dst, None)
    except Exception as e:                     # 单张失败不该中断整包
        return (dst, f"{type(e).__name__}: {e}")


def plan(recs, tier):
    """列出要打包的 (源文件, 包内相对路径, 类型)。

    小册子的 cover.jpg 与 pages/p-00001.jpg 是同一份扫描件（实测全部大小一致），
    所以封面直接复用第一页，不再单独存一份——否则每本多存一张，白白翻倍。
    单页只有一张图，封面与页面就是它自己。

    全分辨率档保留 .jpg 原文件，其余档转 .webp，扩展名随之不同；
    PAGE_RULE_LOCAL 的 ext 必须与这里一致。
    """
    ext = ".jpg" if TIERS[tier]["copy"] else ".webp"
    jobs = []
    for i, r in enumerate(recs):
        n = slug(i)
        if r["kind"] == catalog.KIND_BOOK:
            d = os.path.join(paths.IMAGES, r["dir"].replace("/", os.sep), "pages")
            if os.path.isdir(d):
                for f in sorted(x for x in os.listdir(d) if x.endswith(".jpg")):
                    jobs.append((os.path.join(d, f),
                                 f"{PKG_PAGES}/{n}/{f[:-4]}{ext}", "page"))
        else:
            # 单页：封面即页面
            cover = os.path.join(paths.IMAGES, r["cover"].replace("/", os.sep))
            if os.path.exists(cover):
                jobs.append((cover, f"{PKG_PAGES}/{n}/cover{ext}", "single"))
    return jobs


def build_staging(recs, tier, stage):
    """把页面、数据、说明拷进临时目录，图像边转边写，不落地中间文件。"""
    cfg = TIERS[tier]
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)

    jobs = plan(recs, tier)
    total = len(jobs)
    print(f"  待处理图像 {total} 张")

    # 逐张编码是纯 CPU 活，单线程跑满一个核要 18 分钟；16 核并行后约 1–2 分钟。
    # 用进程池而非线程池：Pillow 的编解码释放 GIL，但 resize 与 RGB 转换不释放。
    args = [(src, os.path.join(stage, rel.replace("/", os.sep)),
             cfg["max_w"], cfg["quality"], cfg["copy"]) for src, rel, _k in jobs]
    workers = min(os.cpu_count() or 4, 12)
    done = 0
    failed = []
    with multiprocessing.Pool(workers) as pool:
        for dst, err in pool.imap_unordered(_encode_job, args, chunksize=8):
            done += 1
            if err:
                failed.append((dst, err))
            if done % 400 == 0 or done == total:
                print(f"    {done}/{total}")
    if failed:
        print(f"  ⚠ {len(failed)} 张失败，将显示排版封面：{failed[:3]}")

    # 重写目录数据：封面与内页路径指向包内 ASCII 结构
    ext = ".jpg" if cfg["copy"] else ".webp"
    rows = []
    for i, r in enumerate(recs):
        n = slug(i)
        is_book = r["kind"] == catalog.KIND_BOOK
        d = {
            "i": i,
            "k": "book" if is_book else "single",
            "c": r["country"], "y": r["year"],
            "t": r["title"], "tz": r["title_zh"],
            "n": r["pages"] or 1,
            "d": f"{PKG_PAGES}/{n}",
            # 小册子封面复用第一页（同一份扫描件），不额外存一份
            "cv": f"{PKG_PAGES}/{n}/p-00001{ext}" if is_book
                  else f"{PKG_PAGES}/{n}/cover{ext}",
            "st": r["stance"], "s": r["source"],
        }
        if r["url"]:
            d["u"] = r["url"]
        # 包内不放 PDF：体积翻倍且与图像重复
        rows.append(d)

    write_page(rows, recs, stage, tier)
    write_csv(recs, stage)
    write_notice(stage, tier)
    shutil.copy2(os.path.join(paths.BASE, "DISCLAIMER.md"),
                 os.path.join(stage, "免责声明.md"))
    return len(jobs)


def write_page(rows, recs, stage, tier="lite"):
    """用同一份模板生成页面，只把数据与路径规则换掉，保证与线上同一套交互。

    包内图像结构是 pages/<编号>/p-00001.webp，所以 PAGE 规则要让 d.d 直接
    就是内页目录（dir=""），前缀与扩展名也相应改变。线上是
    <dir>/pages/p-00001.jpg，两者只在规则上不同，共用一套模板。
    """
    stats = {
        "total": len(recs),
        "books": sum(1 for r in recs if r["kind"] == catalog.KIND_BOOK),
        "singles": sum(1 for r in recs if r["kind"] != catalog.KIND_BOOK),
        "countries": len({r["country"] for r in recs if r["country"]}),
        "pages": sum(r["pages"] for r in recs if r["kind"] == catalog.KIND_BOOK),
        "stances": len({r["stance"] for r in recs if r["stance"]}),
        "sources": len({r["source"] for r in recs if r["source"]}),
    }
    with open(paths.SOURCES, encoding="utf-8") as f:
        allsrc = json.load(f)["sources"]
    used = {d["s"] for d in rows if d["s"]}
    srcs = {s["slug"]: {"t": s.get("title", s["slug"]), "u": s.get("url", "")}
            for s in allsrc if s["slug"] in used}

    out, _stamp = render(rows, stats, srcs,
                         asset_prefix="",          # 图像就在页面同级
                         page_rule=page_rule(tier),
                         stamp_prefix="离线包")
    with open(os.path.join(stage, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(out)


def write_csv(recs, stage):
    """目录表：UTF-8 BOM，Excel 直接双击不乱码。"""
    p = os.path.join(stage, "目录.csv")
    cols = [("序号", None), ("体裁", "kind"), ("国别", "country"), ("年份", "year"),
            ("中文题名", "title_zh"), ("原文题名", "title"), ("页数", "pages"),
            ("立场", "stance"), ("来源专藏", "source"), ("来源链接", "url")]
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([c[0] for c in cols])
        for i, r in enumerate(recs):
            w.writerow([slug(i)] + [r.get(k, "") if k else "" for _label, k in cols[1:]])


def write_notice(stage, tier):
    from datetime import datetime

    p = os.path.join(stage, "使用说明.txt")
    text = BANNER.format(date=datetime.now().strftime("%Y-%m-%d"))
    if tier == "lite":
        text = text.replace("包内结构", "画质说明\n  图像已压至 700px 宽，正文字清晰可读，放大到顶即原图边界。\n\n包内结构")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def zip_dir(stage, out_path):
    """打包，只写 STORED 的 webp 会被再压一次很浪费，统一 DEFLATE 6。"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    total = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, _dirs, files in os.walk(stage):
            for fn in sorted(files):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, stage).replace(os.sep, "/")
                z.write(full, rel)
                total += os.path.getsize(full)
    return total


def main():
    ap = argparse.ArgumentParser(description="打包离线分发包")
    ap.add_argument("--tier", choices=["lite", "full", "both"], default="lite")
    ap.add_argument("--keep-staging", action="store_true", help="保留中间目录便于检查")
    args = ap.parse_args()

    recs = catalog.load()
    if not recs:
        raise SystemExit("找不到目录，先运行 migrate_catalog.py")

    have = sum(1 for r in recs
               if os.path.exists(os.path.join(paths.IMAGES, r["cover"].replace("/", os.sep))))
    print(f"目录 {len(recs)} 条，本地可读封面 {have} 张")
    if have < len(recs):
        print(f"⚠ {len(recs) - have} 条缺封面，包里这部分会显示排版封面")

    tiers = ["lite", "full"] if args.tier == "both" else [args.tier]
    os.makedirs(OUT_DIR, exist_ok=True)

    for tier in tiers:
        cfg = TIERS[tier]
        print(f"\n=== {cfg['label']} ({tier}) ===")
        stage = os.path.join(BUILD, f"pkg-{tier}")
        n = build_staging(recs, tier, stage)
        out = os.path.join(OUT_DIR, f"歷史宣傳材料檔案-{cfg['label']}-{n}件.zip")
        raw = zip_dir(stage, out)
        print(f"  打包完成 {out}")
        print(f"  解压后 {raw/1e6:.0f} MB，压缩包 {os.path.getsize(out)/1e6:.0f} MB")
        if not args.keep_staging:
            shutil.rmtree(stage, ignore_errors=True)

    print("\n全部完成，输出在 dist/")


if __name__ == "__main__":
    main()
