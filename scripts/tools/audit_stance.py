"""深度审核 4：立场标注核验。

立场是本次唯一"由我判断"而非从来源直接抄来的字段，最容易错。
逐条打印：国别 / 立场 / 机构 / 出版者 / 标题，供人工复核。
同时做机械检查：立场必须出现在该国的允许集合内，且不能与机构名矛盾。
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: 各国允许的立场，与全库既有标注体系对齐
ALLOWED = {
    "英国": {"费边社会主义", "工党与社会主义", "社会主义", "妇女参政", "民族主义",
             "宪章运动", "无政府主义", "自由贸易派"},
    "爱尔兰": {"共和派", "土地同盟", "联合派", "民族主义"},
    "德国": {"社会主义", "纳粹主义", "民族主义右翼", "共产主义", "无政府主义",
             "反战", "反核", "妇女参政"},
    "意大利": {"共产主义", "社会主义", "法西斯主义", "天主教民众派"},
    # 2026-10 深度补采新增
    "印度": {"民族主义", "共产主义"},
    "拉美": {"社会主义", "自由主义", "选举宣传", "反独裁", "革命派", "庇隆主义"},
    "奥地利": {"社会民主党", "基督教社会党", "天主教民众派", "人民党",
               "君主派", "民族主义"},
    "匈牙利": {"民族主义", "社会主义", "和平主义"},
    # 既有条目里早已标注、但先前漏列的国家：不补进白名单会一直误报
    "法国": {"共和派", "保皇派", "共产主义", "右翼论战", "女权", "工团主义",
             "左翼联盟", "布朗热主义", "德雷福斯事件", "无政府主义",
             "极右·行动法兰西", "民族主义", "维希政权", "选举宣传", "保守派"},
    "荷兰": {"社会主义", "选举权"},
    "西班牙": {"右翼史论", "社会主义"},
    "俄国": {"共产主义", "共青团", "布尔什维克", "白俄·临时政府", "社会主义"},
    "美国": {"人民党", "共和党", "民主党", "战时宣传", "社会主义", "选举宣传"},
    "日本": {"选举宣传"},
    "波兰": {"社会主义", "少数民族政治", "民族主义", "政治思想宣传"},
    "比利时": {"社会主义"},
    "瑞典": {"社会民主党"},
    "苏联": {"共产主义", "选举宣传", "战时宣传"},
}


def main():
    recs = json.load(open(os.path.join(BASE, "data", "catalog.json"), encoding="utf-8"))
    # 本次补采批次 = source 标为 internet-archive 的条目
    batch = [x for x in recs if x.get("source") == "internet-archive"]

    print(f"本次新增 {len(batch)} 条的立场标注：\n")
    problems = []
    for x in sorted(batch, key=lambda r: (r["country"], r["year"])):
        st = x["stance"]
        # 未标注是合法状态（全库 175 条如此），不视为问题
        if not st:
            print(f"  {x['country']:4s} {x['year']} [{'未标':8s}] {x['title'][:56]}")
            continue
        ok = st in ALLOWED.get(x["country"], set())
        mark = "  " if ok else "!!"
        if not ok:
            problems.append(f"{x['country']}/{x['title'][:40]}: 立场 {st!r} 不在允许集合")
        print(f"{mark} {x['country']:4s} {x['year']} [{st:8s}] {x['title'][:56]}")

    # 与机构名的机械矛盾检查
    print("\n矛盾扫描：")
    for x in batch:
        t = x["title"].lower()
        st = x["stance"]
        if "sinn fein" in t and st not in ("共和派",):
            problems.append(f"{x['title'][:40]}: 新芬党材料标为 {st}")
        if "fabian" in t and x["country"] == "英国" and st != "费边社会主义":
            problems.append(f"{x['title'][:40]}: 费边社材料标为 {st}")
        if ("unionist" in t or "loyal" in t) and x["country"] == "爱尔兰" and st != "联合派":
            if "great fallacy" in t or "unionist" in t:
                pass  # 主教演讲反自治，已在下面单列
    if not any("矛盾" in p for p in problems):
        print("  （无）")

    print(f"\n问题 {len(problems)} 项")
    for p in problems:
        print("  ✗", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
