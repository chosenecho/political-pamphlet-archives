"""探针 4：按缺口国枚举候选，套用与 harvest_ia_stances 相同的过滤，输出候选清单。

只检索与打印，不下载。目的是在动手前看清每个国家能收到什么、
以及有多少是重复或不合体裁的。
"""

import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http

MINP, MAXP = 8, 64

# (国别, 检索式) —— 检索式里已带国别/党名锚点，避免泛政治书混入
QUERIES = [
    ("英国", '("Fabian tract" OR "Fabian Society") AND mediatype:texts'),
    ("英国", '("Labour Party" OR "Independent Labour Party" OR "Social Democratic Federation") '
             'AND subject:(politics OR socialism OR election) AND mediatype:texts'),
    ("意大利", 'subject:(fascismo OR "partito nazionale fascista") AND mediatype:texts'),
    ("意大利", 'subject:(socialismo OR comunismo OR "partito popolare") AND language:ita AND mediatype:texts'),
    ("奥地利", 'language:ger AND subject:(sozialdemokratie OR christlichsozial OR "Austria") '
               'AND year:[1880 TO 1938] AND mediatype:texts'),
    ("匈牙利", 'subject:(szocializmus OR "keresztény" OR valasztas OR politika) AND language:hun AND mediatype:texts'),
    ("爱尔兰", 'subject:("home rule" OR nationalism OR republicanism) AND language:eng AND mediatype:texts'),
    ("德国", 'subject:(nationalsozialismus OR sozialdemokratie OR zentrum OR kommunismus) AND language:ger AND mediatype:texts'),
    ("荷兰", 'subject:(socialisme OR sdap OR "katholieke partij") AND language:dut AND mediatype:texts'),
    ("西班牙", 'subject:(falange OR anarquismo OR socialismo OR carlismo) AND language:spa AND mediatype:texts'),
]

# 不合体裁：小说、诗集、年鉴、期刊、名册、报告、法律汇编
BAD = re.compile(
    r"(novel|poems?|poesie|gedichte|verses?|sermon|hymn|cookery|recipe|dictionary|"
    r"encyclop|almanac|yearbook|kalender|adressbuch|directory|journal|magazine|"
    r"review|argus|herald|tribune|gazette|newspaper|zeitung|courier|sentinel|bulletin|"
    r"statutes|code of|compiled laws|session laws|report of the|proceedings of|"
    r"minutes of|annual report|jahresbericht|rechenschaftsbericht|katalog|catalog|"
    r"romans?|romanzo|erzählung|novelle|biography|memoir|address book|"
    r"guide to|handbook of|textbook|school|grammar|prayer)", re.I)

# 体裁判定：题名里出现这些词，才算宣传品
GOOD = re.compile(
    r"(tract|pamphlet|leaflet|flugschrift|flugblatt|brochure|folleto|panfleto|"
    r"manifesto|manifes|programme|program|programma|wahlaufruf|aufruf|appell|"
    r"speech|rede|discours|discurso|address|rede|"
    r"socialism|sozialismus|socialismo|socialisme|communis|kommunis|"
    r"labour|labor|arbeiter|ouvrier|obrero|operai|"
    r"election|wahl|valg|verkiezing|elecci|"
    r"party|partei|partito|parti|partido|"
    r"suffrage|stemrecht|frauen|women|woman|"
    r"fascis|nazis|nationalsozial|falange|carlis|anarch|syndical|"
    r"fabian|soviet|bolshev|lenin|marx|kautsky|berns)", re.I)


def search(q, rows=60):
    params = {
        "q": q,
        "fl[]": ["identifier", "title", "year", "language", "imagecount", "subject"],
        "rows": str(rows),
        "output": "json",
        "sort[]": "downloads desc",
    }
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return http.fetch_json(url, timeout=60)


def known_identifiers():
    """已收录的 IA identifier，用于去重。"""
    import glob

    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "data", "catalog.json")
    recs = json.load(open(path, encoding="utf-8"))
    out = set()
    for r in recs:
        u = r.get("url", "")
        if "archive.org/details/" in u:
            out.add(u.rsplit("/", 1)[-1].split("?")[0])
    return out


def main():
    known = known_identifiers()
    seen = set()
    print(f"已收录 IA 条目 {len(known)} 个，将排除\n")

    total = 0
    for country, q in QUERIES:
        full = f'{q} AND imagecount:[{MINP} TO {MAXP}] AND year:[1840 TO 1955]'
        try:
            d = search(full)
        except Exception as e:
            print(f"[{country}] 检索失败 {type(e).__name__}: {str(e)[:50]}\n")
            continue

        resp = d.get("response") or {}
        docs = resp.get("docs", [])
        kept, dropped_dup, dropped_type = [], 0, 0
        for doc in docs:
            ident = doc.get("identifier")
            title = re.sub(r"<[^>]+>", "", str(doc.get("title") or "")).strip()
            if not ident or ident in known or ident in seen:
                dropped_dup += 1
                continue
            if BAD.search(title) or not GOOD.search(title):
                dropped_type += 1
                continue
            try:
                ic = int(doc.get("imagecount") or 0)
            except (TypeError, ValueError):
                ic = 0
            if not (MINP <= ic <= MAXP):
                dropped_type += 1
                continue
            year = str(doc.get("year") or "")[:4]
            if not year.isdigit() or not (1840 <= int(year) <= 1955):
                dropped_type += 1
                continue
            seen.add(ident)
            kept.append({"country": country, "identifier": ident, "title": title,
                         "year": year, "pages": ic,
                         "url": f"https://archive.org/details/{ident}"})

        total += len(kept)
        print(f"[{country}] numFound={resp.get('numFound','?')} 取回{len(docs)} "
              f"合格{len(kept)} 重复{dropped_dup} 不合体裁{dropped_type}")
        for k in kept[:8]:
            print(f"     {k['year']} {k['pages']:>3}p {k['identifier'][:32]:32s} {k['title'][:44]}")
        print()

    print(f"=== 候选合计 {total} ===")


if __name__ == "__main__":
    main()
