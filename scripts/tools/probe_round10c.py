"""第十轮候选池（定稿检索式）：按国别 + LCSH「Politics and government」标目。

前两版探针都不合用，记在这里免得下次重走：

  · probe_round10.py 用 subject:(国别 AND party/program/…) 的大类检索，
    128 条候选里真正的政党宣传册不到两成，其余是教会史、主教名录、
    地质报告、渔业传单与 NASA 技术备忘录。
  · probe_round10b.py 改按出版机构反查（publisher:("Partito Socialista Italiano") …）。
    命中数极低（多数检索式 0 条），而放宽到 publisher:(Budapest) 这类地名后，
    又把巴塞罗那的加泰罗尼亚独幕剧、巴勒莫的歌剧台本大量捞进来——
    这些出版者名字里都带 "Società"/"Regional" 之类词，被 PARTY 正则误判。

本版收敛到一条：美国国会图书馆给政治宣传品编目时，几乎都挂在
`<国别> -- Politics and government -- <年份>` 这个标目下。按它检索，
条数不多但体裁对得上；再由人逐条读 publisher / creator 定国别与立场。

用法：
    python scripts/tools/probe_round10c.py           # 拉全池并写 pool2.json
    python scripts/tools/probe_round10c.py --show    # 只打印
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CATALOG = os.path.join(BASE, "data", "catalog.json")
OUT = os.path.join(BASE, "images", "round10", "pool2.json")

PROXY = "http://127.0.0.1:10808"
UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only)")
FIELDS = ["identifier", "title", "year", "language", "imagecount",
          "publisher", "creator", "subject", "collection"]

BASE_Q = " AND imagecount:[8 TO 90] AND mediatype:texts"

#: (标签, 检索式)。标签写「国别 线索」。
QUERIES = [
    ("德国 社民党", 'subject:("Sozialdemokratische Partei Deutschlands")'),
    ("德国 政治", 'subject:(Germany AND "Politics and government") AND year:[1890 TO 1945]'),
    ("德国 政党", 'subject:("Political parties" AND Germany) AND year:[1890 TO 1933]'),
    ("奥地利 政治", 'subject:(Austria AND "Politics and government") AND year:[1900 TO 1938]'),
    ("匈牙利 政治", 'subject:(Hungary AND "Politics and government") AND year:[1900 TO 1949]'),
    ("捷克 政治", 'subject:(Czechoslovakia AND "Politics and government")'),
    ("波兰 政治", 'subject:(Poland AND "Politics and government") AND year:[1900 TO 1939]'),
    ("巴尔干 政治", 'subject:(Bulgaria OR Serbia OR Yugoslavia OR Romania OR Greece) '
                    'AND "Politics and government" AND year:[1900 TO 1945]'),
    ("西班牙 政治", 'subject:(Spain AND "Politics and government") AND year:[1900 TO 1939]'),
    ("意大利 政治", 'subject:(Italy AND "Politics and government") AND year:[1900 TO 1945]'),
    ("葡萄牙 政治", 'subject:(Portugal AND "Politics and government") AND year:[1890 TO 1933]'),
    ("荷兰 政治", 'subject:(Netherlands AND "Politics and government") AND year:[1890 TO 1945]'),
    ("比利时 政治", 'subject:(Belgium AND "Politics and government") AND year:[1890 TO 1945]'),
    ("北欧 政治", 'subject:(Sweden OR Norway OR Denmark OR Finland) '
                  'AND "Politics and government" AND year:[1890 TO 1950]'),
    ("俄国 政治", 'subject:(Russia AND "Politics and government") AND year:[1890 TO 1917]'),
    ("苏联 政治", 'subject:("Soviet Union" AND "Politics and government") '
                  'AND year:[1917 TO 1945]'),
    ("土耳其 政治", 'subject:(Turkey AND "Politics and government") AND year:[1900 TO 1945]'),
    ("埃及 政治", 'subject:(Egypt OR Palestine OR Syria) AND "Politics and government" '
                  'AND year:[1900 TO 1948]'),
    ("中国 政治", 'subject:(China AND "Politics and government") AND year:[1900 TO 1949]'),
    ("日本 政治", 'subject:(Japan AND "Politics and government") AND year:[1890 TO 1945]'),
    ("印度 政治", 'subject:(India AND "Politics and government") AND year:[1900 TO 1947]'),
    ("爱尔兰 政治", 'subject:(Ireland AND "Politics and government") AND year:[1900 TO 1939]'),
    ("美国 竞选", 'subject:("Campaign literature") AND year:[1880 TO 1920]'),
    ("拉美 政治", 'subject:("America" OR "Latin America") AND "Politics and government" '
                  'AND year:[1890 TO 1945]'),
    ("澳大利亚 政治", 'subject:(Australia AND "Politics and government") '
                      'AND year:[1890 TO 1945]'),

    # ---- 体裁词：政党自己的出版物（代表大会记录、竞选演说、纲领） ----
    # 前一版只按 LCSH 国别标目检索，命中的多是学术论著与议会文件；
    # 政党自己印的东西要用体裁词才查得到。
    ("体裁 党代表大会", 'title:(Parteitag OR Protokoll OR Verhandlungen OR Kongress) '
                        'AND subject:(Partei OR Sozialdemokratie OR socialist)'),
    ("体裁 竞选演说", 'title:(discorso AND (elettori OR collegio)) AND language:ita'),
    ("体裁 竞选演说 法", 'title:("profession de foi" OR "aux électeurs" OR "à Messieurs les '
                          'électeurs")'),
    ("体裁 宣传册 英", 'title:(manifesto OR "open letter" OR address) AND subject:("Campaign '
                       'literature" OR propaganda OR socialism OR nationalism)'),
    ("体裁 小册 德", 'subject:("Flugschriften" OR "Politische Flugschrift" OR Flugblatt)'),
    ("体裁 小册 法", 'subject:("Brochures politiques" OR "Tracts" OR "Propagande")'),
    ("体裁 小册 西", 'subject:("Folleto" OR "Panfleto" OR "Propaganda política")'),

    # ---- 策展小册子集藏 ----
    ("集藏 哥大", 'collection:columbiamrlpamphlets AND subject:(socialism OR communism OR '
                  'nationalism OR elections OR propaganda OR suffrage)'),
    ("集藏 布特勒一战", 'collection:butlerlibrarywwipamphlets AND subject:(propaganda OR '
                        'Germany OR Austria OR France)'),
    ("集藏 印度", 'collection:GandhiBhavan'),
    ("集藏 爱尔兰", 'collection:irishstudies AND subject:(politics OR nationalist OR '
                    'Sinn Fein OR labour OR home rule)'),
    ("集藏 锡安", 'subject:(Zionism OR "Jewish nationalism") AND title:(pamphlet OR address '
                  'OR programme OR manifesto)'),
]

#: 题名里明显不是政治宣传册的
BAD = re.compile(
    r"(novel|poems?|sermon|hymn|cookery|recipe|dictionary|encyclop|almanac|yearbook|"
    r"kalender|adressbuch|directory|\bjournal\b|magazine|\breview\b|quarterly|"
    r"annals|proceedings|argus|herald|tribune|gazette|newspaper|zeitung|courier|"
    r"\bbulletin|statutes|compiled laws|report of the|minutes of|annual report|"
    r"jahresbericht|berättelse|katalog|catalogue|bibliograph|sångbok|visbok|"
    r"kokbok|midsummer|festival|calendario|almanaque|geology|geological|"
    r"fishery|fisheries|astronom|botan|zoolog|medical|anatomy|surgery|"
    r"catechism|liturgy|hymnal|bible|gospel|devotion|prayer|"
    # 加拿大缩微复制系列（CIHM）多为地方史与教会文献，且非目标国别
    r"^cihm[_-]|microform|microforme)", re.I)


def check_proxy():
    op = urllib.request.build_opener(urllib.request.ProxyHandler(
        {"http": PROXY, "https": PROXY}))
    return op


def get_json(op, url, timeout=90, retries=4):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with op.open(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            last = e
            if i == retries - 1:
                raise
            time.sleep(2 + 2 * i)
    raise last


def search(op, q, rows=400):
    params = {"q": q, "fl[]": FIELDS, "rows": str(rows), "output": "json"}
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return get_json(op, url)["response"]


def _join(v, n=200):
    if isinstance(v, list):
        v = " | ".join(str(x) for x in v)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(v or ""))).strip()[:n]


def known_ids():
    with open(CATALOG, encoding="utf-8") as f:
        recs = json.load(f)
    return {r["url"].rsplit("/", 1)[-1].split("?")[0]
            for r in recs if "archive.org/details/" in r.get("url", "")}


def main():
    show_only = "--show" in sys.argv
    op = check_proxy()
    have = known_ids()
    seen, pool = set(), []

    for label, q in QUERIES:
        try:
            r = search(op, q + BASE_Q)
        except Exception as e:
            print(f"[{label}] 检索失败 {type(e).__name__}: {str(e)[:40]}")
            continue
        docs = r.get("docs", [])
        n = 0
        for doc in docs:
            ident = str(doc.get("identifier") or "")
            title = _join(doc.get("title"), 240)
            if not ident or ident in have or ident in seen or not title:
                continue
            if BAD.search(title):
                continue
            try:
                ic = int(doc.get("imagecount") or 0)
            except (TypeError, ValueError):
                continue
            if not (8 <= ic <= 90):
                continue
            y = str(doc.get("year") or "")[:4]
            if not y.isdigit() or not (1840 <= int(y) <= 1980):
                continue
            seen.add(ident)
            pool.append({
                "label": label, "identifier": ident, "title": title, "year": y,
                "pages": ic, "language": _join(doc.get("language"), 30),
                "publisher": _join(doc.get("publisher"), 160),
                "creator": _join(doc.get("creator"), 160),
                "subject": _join(doc.get("subject"), 200),
                "collection": _join(doc.get("collection"), 100),
            })
            n += 1
        print(f"[{label}] numFound={r.get('numFound')} 命中 {len(docs)}，新候选 {n}",
              flush=True)
        time.sleep(1.2)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=1)

    print(f"\n候选池 {len(pool)} 条 → {OUT}")
    if show_only:
        for c in pool:
            print(f'\n[{c["label"]}] {c["identifier"]}  {c["year"]} {c["pages"]}p '
                  f'{c["language"]}')
            print(f'   T {c["title"][:110]}')
            print(f'   P {c["publisher"][:100]}')
            print(f'   C {c["creator"][:80]}')
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
