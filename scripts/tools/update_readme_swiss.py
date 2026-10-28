"""README 缺口段补入瑞士这一节（瑞士首次入目录）。"""

import io
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
README = os.path.join(BASE, "README.md")

ADD = """- 瑞士此前完全没有条目，2026-10-28 首次补入 **30 件**历史政治海报（1908–1929）。来源是 Commons 上瑞士国家图书馆的 `CH-NB Poster Collection SNL POL` 系列与 `Category:Election posters in Switzerland`。瑞士实行直接民主，题型分两类：**政党选举海报**（自由民主党、社会民主党、公民党，海报上直接印有名单号）与**公投议题海报**（工时法、养老残障保险、财产税、禁酒、面包专卖、国际联盟加入）。同一议题常有德/法/意三种语言版本，已分别收录并在译名中注明。该分类里另有 100 余件 `.tif` 格式，浏览器与阅读器无法直接显示，本轮未收。
"""


def main():
    s = io.open(README, encoding="utf-8").read()
    if "瑞士此前完全没有条目" in s:
        print("已含瑞士段落，跳过")
        return 0

    # 插在「捷克、比利时、日本已从 IA 补到小册子」那条之后
    anchor = "内珀《日本共产党概观》（1913）等。"
    if anchor not in s:
        print("未找到锚点")
        return 1
    s = s.replace(anchor, anchor + "\n" + ADD, 1)

    io.open(README, "w", encoding="utf-8", newline="\n").write(s)
    print("README 已补入瑞士段落")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
