"""整理 IA 已下载但缺失 metadata.json 的批次。

IA 中途不可达，两轮采集都没写出 metadata.json，但已下载的
doc.pdf 与页图完好。本脚本从**已下载的文件**反推身份：

  - PDF 内的 XMP/Info 元数据里有 IA 的 identifier
  - 或 PDF 首页文本能读出标题

反推不出的不猜，列出来人工处理。
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMG = os.path.join(BASE, "images")


def pdf_meta(path):
    try:
        import fitz
    except ImportError:
        return {}
    try:
        doc = fitz.open(path)
        meta = doc.metadata or {}
        first = ""
        if doc.page_count:
            first = doc[0].get_text()[:400]
        n = doc.page_count
        doc.close()
        return {"meta": meta, "first": first, "pages": n}
    except Exception as e:
        return {"error": type(e).__name__}


def main():
    for batch in ("ia-deep", "ia-gap"):
        root = os.path.join(IMG, batch, "raw")
        if not os.path.isdir(root):
            continue
        print("=" * 74)
        print(batch)
        print("=" * 74)
        for d in sorted(os.listdir(root)):
            folder = os.path.join(root, d)
            if not os.path.isdir(folder):
                continue
            pdf = os.path.join(folder, "doc.pdf")
            pages = len([f for f in os.listdir(os.path.join(folder, "pages"))
                         if f.endswith(".jpg")]) \
                if os.path.isdir(os.path.join(folder, "pages")) else 0
            print(f"\n[{d}] 页图 {pages}")
            if not os.path.exists(pdf):
                print("    无 PDF，无法反推")
                continue
            info = pdf_meta(pdf)
            if "error" in info:
                print(f"    PDF 打不开 {info['error']}")
                continue
            m = info.get("meta", {})
            for k in ("title", "author", "subject", "keywords", "producer",
                      "creator", "creationDate"):
                v = m.get(k)
                if v:
                    print(f"    {k:12s} {str(v)[:110]}")
            print(f"    PDF 页数     {info.get('pages')}")
            first = re.sub(r"\s+", " ", info.get("first", "")).strip()
            if first:
                print(f"    首页文字     {first[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
