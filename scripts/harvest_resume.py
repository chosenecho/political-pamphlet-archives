"""Internet Archive 断点续传采集器。

背景：IA 的 download 端点会在批量抓取后限流（HEAD 与页面图请求双双超时），
前面两轮采集因此卡死，但已下载的页图与 PDF 完好。本脚本的设计：

  1. 断点续传 —— 已存在的页图跳过，只补缺失的；PDF 已存在则不重下。
  2. 自适应退避 —— 连续失败就指数加长间隔，不硬撞；恢复后自动缩短。
  3. 熔断 —— 连续失败超过阈值就整体停下并保留现场，等下轮再续。
  4. 完整性校验 —— 每项收尾时核对页图数是否达到预期。

输入是一份简单的清单文件（JSON），每项：
    {"ident","country","stance","title","year","pages","target"}

用法：
    python scripts/harvest_resume.py --list images/_resume.json --dry
    python scripts/harvest_resume.py --list images/_resume.json
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only)")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")

#: 单次请求超时。IA 限流时连接能建立但不返回，只能靠短超时快速失败。
PAGE_TIMEOUT = 35
PDF_TIMEOUT = 200

#: 连续失败多少次就认为被限流，整体熔断
BREAKER = 6

#: 退避序列（秒）
BACKOFF = [2, 5, 10, 20, 40, 60, 90]


def _get(url, timeout, dest=None):
    """取一个 URL。dest 为 None 时只读头部长度，否则写文件。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        data = r.read()
    if len(data) < 2000:
        raise ValueError(f"too small ({len(data)} bytes)")
    if dest:
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, dest)
    return len(data)


def fetch_pdf(ident, pdf_name, dest):
    url = f"https://archive.org/download/{ident}/{urllib.parse.quote(pdf_name)}"
    return _get(url, PDF_TIMEOUT, dest)


def fetch_page(ident, idx, dest):
    url = f"https://archive.org/download/{ident}/page/n{idx}_w1000.jpg"
    return _get(url, PAGE_TIMEOUT, dest)


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    list_path = None
    if "--list" in args:
        list_path = args[args.index("--list") + 1]
    if not list_path or not os.path.exists(list_path):
        print("用法：--list <清单 JSON> [--dry]")
        return 1

    items = json.load(open(list_path, encoding="utf-8"))
    print(f"清单 {len(items)} 项\n")

    fails = 0
    done = 0
    pause = 0

    for it in items:
        ident = it["ident"]
        target = int(it.get("target") or it.get("pages") or 0)
        root = os.path.join(IMG, it["batch"], "raw", f"{it['no']:03d}")
        pages_dir = os.path.join(root, "pages")
        os.makedirs(pages_dir, exist_ok=True)

        have = {f for f in os.listdir(pages_dir) if f.endswith(".jpg")}
        missing = [i for i in range(target)
                   if f"p-{i + 1:05d}.jpg" not in have]

        pdf_path = os.path.join(root, "doc.pdf")
        need_pdf = bool(it.get("pdf_name")) and not os.path.exists(pdf_path)

        print(f"[{ident}] 目标 {target} 页，已有 {len(have)}，缺 {len(missing)}"
              f"{'，需 PDF' if need_pdf else ''}")
        if dry:
            continue

        # --- PDF ---
        if need_pdf:
            try:
                n = fetch_pdf(ident, it["pdf_name"], pdf_path)
                print(f"    PDF {n / 1048576:.1f} MB")
                fails = 0
                pause = 0
            except Exception as e:
                print(f"    PDF 失败 {type(e).__name__}")
                fails += 1

        # --- 逐页 ---
        got = 0
        for idx in missing:
            if fails >= BREAKER:
                print(f"    熔断（连续失败 {fails} 次），保留现场稍后续传")
                break
            dest = os.path.join(pages_dir, f"p-{idx + 1:05d}.jpg")
            if pause:
                time.sleep(pause)
            try:
                fetch_page(ident, idx, dest)
                got += 1
                fails = 0
                pause = 0
                time.sleep(0.12)
            except Exception as e:
                fails += 1
                pause = BACKOFF[min(fails - 1, len(BACKOFF) - 1)]
                print(f"    页 {idx} 失败（连续 {fails}），等 {pause}s")

        total = len([f for f in os.listdir(pages_dir) if f.endswith(".jpg")])
        status = "完整" if total >= target else f"仍缺 {target - total}"
        print(f"    -> {total}/{target} 页（{status}），本轮补 {got}\n")
        if total >= target:
            done += 1

        if fails >= BREAKER:
            print("整体熔断，停止本轮。已下载内容保留，可稍后重跑续传。")
            break

    print(f"\n本轮完成 {done} 项")

    # 回写进度，供下一轮使用
    for it in items:
        root = os.path.join(IMG, it["batch"], "raw", f"{it['no']:03d}")
        pages_dir = os.path.join(root, "pages")
        if os.path.isdir(pages_dir):
            it["have"] = len([f for f in os.listdir(pages_dir) if f.endswith(".jpg")])
        it["has_pdf"] = os.path.exists(os.path.join(root, "doc.pdf"))
    json.dump(items, open(list_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
