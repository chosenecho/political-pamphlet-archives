"""探针 7：核验候选条目的出版者、出版地与作者，用于判定国别归属。

国别不能靠检索式推断——检索式里写了"奥地利"，返回的可能是德国出版物。
逐条读 IA metadata，把 publisher / date / creator 打出来人工判读。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http

# 待核验：(候选归属国, identifier)
CANDIDATES = [
    ("奥地利?", "sozialdemokrati00bebegoog"),
    ("奥地利?", "diesozialdemokra00sozi"),
    ("奥地利?", "sozialdemokratis00haen"),
    ("奥地利?", "derdeutschnation00schu"),
    ("奥地利?", "deutschnationale00kube"),
    ("意大利?", "statutodelpartit00part"),
    ("意大利?", "La-dottrina-del-fascismo-e-il-"),
    ("意大利?", "2734133"),
    ("意大利?", "ilpattodiromaela00amenuoft"),
    ("英国?", "impossibilitieso00shawuoft"),
    ("英国?", "fabianismfiscalq00shawrich"),
    ("英国?", "socialismsuperio559shaw"),
    ("英国?", "socialismmadepla00soci"),
    ("英国?", "childlaborunder? b22460536"),
    ("英国?", "whatdoyouknowabo09fabi"),
    ("英国?", "labourpilgrimspr597mugg"),
    ("爱尔兰?", "issuecaseforsinn00lect"),
    ("爱尔兰?", "devchurchillbooklet"),
    ("爱尔兰?", "truthaboutlandle00arno_1"),
    ("爱尔兰?", "impressionsofsin00shee"),
]


def meta(ident):
    return http.fetch_json(f"https://archive.org/metadata/{ident}", timeout=60)


def main():
    for label, ident in CANDIDATES:
        ident = ident.split()[-1]
        try:
            d = meta(ident)
        except Exception as e:
            print(f"\n[{label}] {ident} 失败 {type(e).__name__}")
            continue
        md = d.get("metadata", {}) or {}
        print(f"\n[{label}] {ident}")
        for k in ("title", "creator", "publisher", "date", "year", "language", "subject"):
            v = md.get(k)
            if v:
                print(f"    {k:10s} {str(v)[:120]}")


if __name__ == "__main__":
    main()
