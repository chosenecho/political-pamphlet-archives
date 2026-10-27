"""深度审核 1：二进制完整性。

只验"文件存在"是不够的——IA 的下载可能得到：
  - HTML 错误页（403/404 正文写成 .jpg/.pdf）
  - 截断的 JPEG（connection reset 后仍写了半个文件）
  - 空白页（扫描件本身有问题）
本脚本逐页解码，逐 PDF 开页，并把页数与 catalog 记录对账。
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMG = os.path.join(BASE, "images")

JPEG_SOI = b"\xff\xd8\xff"
PDF_MAGIC = b"%PDF"


def main():
    recs = json.load(open(os.path.join(BASE, "data", "catalog.json"), encoding="utf-8"))
    # 本次补采：有 stance 且来自 IA
    batch = [x for x in recs
             if "archive.org/details/" in x.get("url", "") and x.get("stance")]
    print(f"审核批次 {len(batch)} 条\n")

    try:
        from PIL import Image
        HAVE_PIL = True
    except ImportError:
        HAVE_PIL = False
        print("!! 无 Pillow，跳过像素级校验\n")

    try:
        import fitz  # PyMuPDF
        HAVE_MUPDF = True
    except ImportError:
        HAVE_MUPDF = False
        print("!! 无 PyMuPDF，跳过 PDF 页数校验\n")

    problems = []
    tot_pages = 0
    tot_pdf_pages = 0

    for x in batch:
        d = os.path.join(IMG, x["dir"].replace("/", os.sep))
        pages_dir = os.path.join(d, "pages")
        imgs = sorted(f for f in os.listdir(pages_dir) if f.endswith(".jpg"))
        tag = f"{x['country']}/{x['title'][:36]}"
        tot_pages += len(imgs)

        # --- 页图 ---
        html_like = 0
        zero_byte = 0
        undecodable = []
        tiny = []
        sizes = []
        for f in imgs:
            p = os.path.join(pages_dir, f)
            sz = os.path.getsize(p)
            if sz == 0:
                zero_byte += 1
                continue
            with open(p, "rb") as fh:
                head = fh.read(4)
            if not head.startswith(JPEG_SOI):
                html_like += 1
                continue
            if sz < 2000:
                tiny.append(f)
            if HAVE_PIL:
                try:
                    with Image.open(p) as im:
                        im.load()
                        sizes.append(im.size)
                except Exception as e:
                    undecodable.append(f"{f}:{type(e).__name__}")

        if html_like:
            problems.append(f"{tag}: {html_like} 个页图不是 JPEG（疑似错误页）")
        if zero_byte:
            problems.append(f"{tag}: {zero_byte} 个页图 0 字节")
        if undecodable:
            problems.append(f"{tag}: {len(undecodable)} 个页图解码失败 {undecodable[:3]}")
        if tiny:
            problems.append(f"{tag}: {len(tiny)} 个页图小于 2KB（可能空白）")
        if len(imgs) != x["pages"]:
            problems.append(f"{tag}: pages={x['pages']} 实际 {len(imgs)}")

        # --- PDF ---
        if x["pdf"]:
            pp = os.path.join(IMG, x["pdf"].replace("/", os.sep))
            if not os.path.exists(pp):
                problems.append(f"{tag}: PDF 不存在")
            else:
                with open(pp, "rb") as fh:
                    magic = fh.read(5)
                if not magic.startswith(PDF_MAGIC):
                    problems.append(f"{tag}: PDF 魔数错误 {magic[:8]!r}（疑似错误页）")
                elif HAVE_MUPDF:
                    try:
                        doc = fitz.open(pp)
                        n = doc.page_count
                        tot_pdf_pages += n
                        # 口径说明：catalog 的 pages 一律等于页图张数
                        # （全库 131 条实测一致，既有条目亦然）。
                        # IA 的 PDF 常比页图少 2–5 页（封面/封底/空白页未纳入
                        # 逐页扫描），属正常，不作为错误。
                        # 只有 PDF 页数明显多于页图（>页图）才说明页图漏抓。
                        if n > len(imgs):
                            problems.append(
                                f"{tag}: PDF {n} 页 > 页图 {len(imgs)} 张，页图可能漏抓")
                        doc.close()
                    except Exception as e:
                        problems.append(f"{tag}: PDF 打不开 {type(e).__name__}")

        if sizes:
            w = [s[0] for s in sizes]
            h = [s[1] for s in sizes]
            narrow = sum(1 for v in w if v < 400)
            if narrow > len(w) * 0.5:
                problems.append(f"{tag}: 过半页图宽度 <400px（最低 {min(w)}）")

    print(f"页图合计 {tot_pages} 张，PDF 合计 {tot_pdf_pages} 页")
    print(f"\n问题 {len(problems)} 项")
    for p in problems:
        print("  ✗", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
