"""补齐此前因 Internet Archive 不可达而未下完的两本。

2026-10 那轮 IA 整站超时约一小时，两本只下到部分页图，按要求未入目录：
  · mkgpamphlet0300mkga 甘地《素食的道德基础》  14/40 页
  · programmeofilpun00mann 《I.L.P. 纲领与失业》  3/24 页

现在 IA 已恢复，本脚本按 images/_ia_recovered.json 的记录补抓缺页。
已存在的页图跳过，只补缺的；PDF 若缺也一并取。
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMG = os.path.join(BASE, "images")

UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only)")

#: 只补这两本
PENDING = {
    "ia-deep": [3],
    "ia-gap": [5],
}


def fetch_page(ident, idx, dest, timeout=90):
    url = f"https://archive.org/download/{ident}/page/n{idx}_w1000.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if len(data) < 2000:
        raise ValueError(f"too small {len(data)}")
    with open(dest, "wb") as f:
        f.write(data)


def main():
    spec = json.load(open(os.path.join(IMG, "_ia_recovered.json"), encoding="utf-8"))
    total_got = 0

    for batch, nos in PENDING.items():
        for it in spec.get(batch, []):
            if it["no"] not in nos:
                continue
            ident = it["ident"]
            root = os.path.join(IMG, batch, "raw", f"{it['no']:03d}")
            pages = os.path.join(root, "pages")
            os.makedirs(pages, exist_ok=True)
            have = {f for f in os.listdir(pages) if f.endswith(".jpg")}
            target = int(it["target"])
            missing = [i for i in range(target)
                       if f"p-{i + 1:05d}.jpg" not in have]
            print(f"\n[{ident}] {it['title'][:44]}")
            print(f"  已有 {len(have)}/{target}，缺 {len(missing)}")

            got, fails = 0, 0
            for idx in missing:
                dest = os.path.join(pages, f"p-{idx + 1:05d}.jpg")
                try:
                    fetch_page(ident, idx, dest)
                    got += 1
                    fails = 0
                    time.sleep(0.12)
                except Exception as e:
                    fails += 1
                    print(f"    页 {idx} 失败 {type(e).__name__}")
                    if fails >= 5:
                        print("    连续失败 5 次，停")
                        break
                    time.sleep(2 * fails)

            now = len([f for f in os.listdir(pages) if f.endswith(".jpg")])
            total_got += got
            print(f"  -> {now}/{target}" + ("  完整" if now >= target else "  仍缺"))

    print(f"\n本轮补 {total_got} 页")


if __name__ == "__main__":
    main()
