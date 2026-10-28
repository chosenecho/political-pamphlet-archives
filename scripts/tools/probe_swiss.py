"""核验第六轮候选：瑞士国家图书馆海报集（CH-NB Poster Collection）。

瑞士此前没有任何条目。这批 SNL POL 系列来自瑞士国家图书馆，
需确认年代与题材是否属十九至二十世纪政治宣传品。
"""

import os
import sys
import re
import time
import urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import http


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return http.fetch_json(url, timeout=45, retries=4)


def year_of(info):
    md = (info or {}).get("extmetadata") or {}
    for k in ("DateTimeOriginal", "DateTime", "Date", "DateTimeDigitized"):
        v = (md.get(k) or {}).get("value")
        if v:
            m = re.search(r"(1[6-9]\d{2}|20\d{2})", str(v))
            if m:
                return m.group(1)
    return ""


def main():
    # 先枚举瑞士分类全部文件
    d = api({"action": "query", "format": "json", "list": "categorymembers",
             "cmtitle": "Category:Political posters of Switzerland",
             "cmtype": "file", "cmlimit": "50"})
    mem = (d.get("query") or {}).get("categorymembers", [])
    titles = [m["title"] for m in mem]
    print(f"瑞士分类 {len(titles)} 个文件\n")

    # 批量取 imageinfo
    infos = {}
    for i in range(0, len(titles), 15):
        chunk = titles[i:i + 15]
        try:
            dd = api({"action": "query", "format": "json", "prop": "imageinfo",
                      "iiprop": "url|size|extmetadata", "titles": "|".join(chunk)})
        except Exception as e:
            print(f"  取 imageinfo 失败 {type(e).__name__}")
            continue
        for page in (dd.get("query") or {}).get("pages", {}).values():
            ii = page.get("imageinfo")
            if ii:
                infos[page.get("title")] = ii[0]
        time.sleep(1)

    for t in titles:
        info = infos.get(t)
        if not info:
            print(f"  {t[:66]}  (无 imageinfo)")
            continue
        y = year_of(info)
        w, h = info.get("width") or 0, info.get("height") or 0
        print(f"  {y or '????':4s} {w:>5}x{h:<5} {t.split(':',1)[-1][:62]}")


if __name__ == "__main__":
    main()
