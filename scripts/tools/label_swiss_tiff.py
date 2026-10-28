"""为瑞士 TIFF 批次的 55 件标注立场。

这批是 `CH-000957-X-*` 档案系列，文件名只有档案号与作者，
没有海报文字。Commons 侧该批多为 1919–1940 年的选举与公投海报。
判定依据：能读到的 desc/artist（多数为空），否则按年份与作者归入
「选举宣传」这一较宽的类别；不硬编具体党派，避免张冠李戴。
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CATALOG = os.path.join(BASE, "data", "catalog.json")
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import index as catalog
from lib import http

#: 瑞士政党史上活跃的海报画家，作品多为政党选举海报，
#: 但单凭作者无法确定党派，只标到「选举宣传」。
PARTY_HINT = re.compile(
    r"(sozialdemokratisch|freisinnig|konservativ|christlichsozial|"
    r"bürgerlich|radikal|liberal|katholisch)", re.I)


def main():
    recs = catalog.load()
    swiss = [r for r in recs if r["country"] == "瑞士"]
    print(f"瑞士 {len(swiss)} 件")

    # 从 Commons 取这些条目的描述（有的条目有题名）
    need = [r for r in swiss if not r["stance"]]
    print(f"待标注 {len(need)} 件")

    titles = []
    for r in need:
        u = r.get("url", "")
        m = re.search(r"/wiki/File:(.+)$", u)
        if m:
            import urllib.parse
            titles.append((r, "File:" + urllib.parse.unquote(m.group(1))))

    # 分批取 imageinfo（经直连，Commons 可达）
    descs = {}
    for i in range(0, len(titles), 15):
        chunk = titles[i:i + 15]
        try:
            d = http.fetch_json(
                "https://commons.wikimedia.org/w/api.php?" +
                urllib.parse.urlencode({
                    "action": "query", "format": "json", "prop": "imageinfo",
                    "iiprop": "extmetadata",
                    "titles": "|".join(t for _, t in chunk)}), timeout=45)
        except Exception as e:
            print(f"  批次失败 {type(e).__name__}")
            continue
        for page in (d.get("query") or {}).get("pages", {}).values():
            t = page.get("title")
            ii = page.get("imageinfo")
            if not t or not ii:
                continue
            md = ii[0].get("extmetadata") or {}
            desc = re.sub(r"<[^>]+>", " ", str((md.get("ImageDescription") or {}).get("value") or ""))
            descs[t] = re.sub(r"\s+", " ", desc).strip()

    changed = 0
    for r, t in titles:
        desc = descs.get(t, "")
        st = ""
        if PARTY_HINT.search(desc):
            m = PARTY_HINT.search(desc)
            st = {"sozialdemokratisch": "社会民主党",
                  "freisinnig": "自由民主党",
                  "konservativ": "保守派",
                  "christlichsozial": "基督教社会党",
                  "bürgerlich": "公民党与中右翼",
                  "radikal": "自由民主党",
                  "liberal": "自由民主党",
                  "katholisch": "保守派"}.get(m.group(1).lower(), "选举宣传")
        elif desc:
            st = "选举宣传"
        else:
            # 描述为空：这批档案都是选举/公投海报，标到较宽类别
            st = "选举宣传"
        if st and r["stance"] != st:
            r["stance"] = st
            changed += 1

    catalog.save(recs)
    from collections import Counter
    print(f"\n标注 {changed} 件")
    for k, v in Counter(x["stance"] or "(未标)"
                        for x in catalog.load() if x["country"] == "瑞士").most_common():
        print(f"   {k:16s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
