"""给 README 节选表里的专藏补齐 note，只填入 notes/ 原文能支撑的内容。

原则
    能查到出处的，补进 sources.json 的 note（成为唯一来源，README 从它渲染）；
    查不到出处的，留空，README 显示「—」。不为了让表格好看而保留无据数字。

逐条核实结果（notes/ 原文）
    kas-archiv-bibliothek   ✓ "über 1.900 Archivbestände"
                            ✓ "Archivalien im Umfang von über 19 laufenden Regalkilometern"
                            ✓ "Flugblätter und Pressemitteilungen der CDU/CSU-Fraktion …
                                im Volltext recherchierbar"
    phm-labour-history-archive ✓ "complete holdings of the national Labour Party and
                                  Communist Party of Great Britain"
                               ✓ "over 95,000 photographs"
    fes-adsd                ✓ 有 Bestandsübersicht / Bibliothekskatalog / Digitalisierte
                              Quellen 三个入口；但**没有**任何规模数字
                              （README 原写的「期刊与小册子回溯数字化」也无原文支撑）
    iisg-collections        ✗ notes 只有导航与地址，没有任何馆藏规模数字
    sozialarchiv-zuerich    ✓ "1'000 Archivbestände"（档案群，不是「18 万册小册子」）
                            ✗ 「18 万册小册子与传单」无原文支撑
    modernhistory-cn        ✗ 无页数；「5000 万页以上」查无出处
    vga-wien                ✗ 无 notes 文件；「6000 余张」仅存在于 sources.json 自身
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: slug -> note。只写 notes/ 原文能对上的内容。
NOTE_UPDATES = {
    "kas-archiv-bibliothek":
        "1900 余个档案群、逾 19 架公里档案；联邦议院 CDU/CSU 党团的传单与新闻稿可全文检索",
    "phm-labour-history-archive":
        "工党与英国共产党的完整全宗，另有工人阶级组织档案与 9.5 万余张照片",
    "fes-adsd":
        "社会民主党档案馆；提供馆藏总览、图书馆目录与数字化来源三个检索入口",
    "sozialarchiv-zuerich":
        "约 1000 个档案群；文献部藏有小册子、传单与新闻剪报",
}


def main():
    p = os.path.join(BASE, "data", "sources.json")
    doc = json.load(open(p, encoding="utf-8"))
    by_slug = {s["slug"]: s for s in doc["sources"]}

    changed = []
    for slug, note in NOTE_UPDATES.items():
        if slug not in by_slug:
            raise SystemExit(f"sources.json 里没有 {slug}")
        old = (by_slug[slug].get("note") or "").strip()
        if old == note:
            print(f"  = {slug}: 已是目标值")
            continue
        by_slug[slug]["note"] = note
        changed.append((slug, old, note))

    if not changed:
        print("sources.json 无需改动")
        return 0

    for slug, old, new in changed:
        print(f"  ~ {slug}\n      旧: {old or '(空)'}\n      新: {new}")

    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\n已写入 {p}（{len(changed)} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
