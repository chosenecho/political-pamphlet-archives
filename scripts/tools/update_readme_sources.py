"""README 里的专藏数与来源归属表述随本轮改动更新。

本轮把 Wikimedia Commons 登记为第 40 个专藏并回填条目来源，
README 里「39 个专藏」「Commons 不在专藏之列、其条目一律留空」两处已过时。
"""

import io
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
README = os.path.join(BASE, "README.md")


def main():
    s = io.open(README, encoding="utf-8").read()
    orig = s

    # 39 → 40 个专藏（各处）
    s = s.replace("仓库把 39 个已有数字化或可检索的专藏整理成一张表",
                  "仓库把 40 个已有数字化或可检索的专藏整理成一张表")
    s = s.replace("**39 个专藏**的清单", "**40 个专藏**的清单")
    s = s.replace("39 个专藏的可点击清单与抓取状态",
                  "40 个专藏的可点击清单与抓取状态")
    s = s.replace("## 已核实的 39 个专藏（节选）", "## 已核实的 40 个专藏（节选）")
    s = s.replace("39 个专藏中：21 个抓到可读正文，3 个只有说明文件（403/429），"
                  "15 个仅登记入口、正文待取。`data/manifest.json` 覆盖 24/39 个源，"
                  "其余 15 个尚未尝试。",
                  "40 个专藏中：21 个抓到可读正文，3 个只有说明文件（403/429），"
                  "16 个仅登记入口、正文待取。`data/manifest.json` 覆盖 24/40 个源，"
                  "其余 16 个尚未尝试。")

    # 来源归属那句：Commons 现已登记为专藏
    s = re.sub(
        r"- `data/catalog\.json` 的 `source` 字段（条目归属哪个专藏）目前回填 \d+/\d+ 条"
        r"——可按 URL 域名唯一确定的已填，其余留空未猜。Wikimedia Commons 同样不在 \d+ 个专藏之列，"
        r"其条目一律留空。",
        "- `data/catalog.json` 的 `source` 字段（条目归属哪个专藏）目前回填 319/337 条"
        "——可按 URL 域名唯一确定的已填，其余留空未猜。剩下 18 条的 `url` 只记到站点根"
        "（如 `https://commons.wikimedia.org/`），无法指向具体条目，保持留空而不猜。",
        s)

    if s != orig:
        io.open(README, "w", encoding="utf-8", newline="\n").write(s)
        print("README 已更新")
    else:
        print("README 无需改动")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
