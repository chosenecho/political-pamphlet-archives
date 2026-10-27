"""Internet Archive 缺口国补采（第三轮，机构名与出版地双重锚定）。

三轮修正的教训，记在这里免得再踩：

  1. 检索式里写国名不可靠——写"奥地利"返回的是 Berlin / Jena / Breslau 出的
     德国书。国别必须落证据：机构名（creator）或出版地（publisher）。
  2. 靠标题模糊匹配国别会污染。`home rule` 不只是爱尔兰的，纽约、俄勒冈、
     加州都有"municipal home rule"；`englischen` 出现在德语书标题里。
     所以标题不参与国别判定。
  3. 标题为 `Fabian tract` / `Fabian tracts` 的是年度合订本（volume 1959-60），
     不是单册宣传品，必须排除。单册的特征是有独立篇名。
  4. JSTOR 抽印本（jstor-*）、期刊论文、年报、报刊，一律不是宣传小册子。

判定顺序：机构名 → 出版地 → 丢弃。判不出就丢，不猜。

用法：
    python scripts/harvest_ia_gap.py --dry     # 只列候选与判定依据
    python scripts/harvest_ia_gap.py           # 下载到 images/ia-gap/
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only)")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "images", "ia-gap")
RAW = os.path.join(ROOT, "raw")
CATALOG = os.path.join(BASE, "data", "catalog.json")

MINP, MAXP = 8, 64
PDF_MAX_MB = 18
MAX_PAGES_DL = 64
#: 每国上限，按现有馆藏缺口分配（爱尔兰此前为 0，是新增国别）
LIMIT_PER_COUNTRY = {"英国": 12, "爱尔兰": 10, "德国": 4, "意大利": 2,
                     "奥地利": 4, "荷兰": 3, "西班牙": 3, "匈牙利": 3}

#: 机构名 -> (国别, 立场)。命中 creator 或 subject 才算数，标题不算。
ORG_RULES = [
    ("爱尔兰", "共和派", r"sinn\s*fein"),
    ("爱尔兰", "土地同盟", r"(Irish\s+National\s+League|United\s+Irish\s+League|"
                          r"Land\s+League|Irish\s+Land\s+and\s+Labour)"),
    ("爱尔兰", "联合派", r"(Irish\s+Unionist\s+Alliance|Irish\s+Loyal\s+and\s+Patriotic|"
                        r"Ulster\s+Unionist)"),
    ("爱尔兰", "民族主义", r"(Irish\s+Party|Irish\s+Parliamentary\s+Party|"
                          r"Irish\s+Nationalist|Irish\s+Publicity\s+League|"
                          r"National\s+League\s+of\s+Ireland)"),
    ("英国", "费边社会主义", r"fabian\s+(society|society\s+\(great\s+britain\)|"
                            r"research|publications|society,\s+london)"),
    ("英国", "工党与社会主义", r"(Independent\s+Labour\s+Party|Labour\s+Party\s*"
                              r"\(great\s+britain\)|Labour\s+Representation|"
                              r"Labour\s+Research\s+Department|"
                              r"Social[- ]Democratic\s+Federation|"
                              r"Trades\s+Union\s+Congress|"
                              r"National\s+Labour\s+Press)"),
    ("英国", "妇女参政", r"(Women'?s\s+Social\s+and\s+Political\s+Union|"
                        r"National\s+Union\s+of\s+Women'?s\s+Suffrage|"
                        r"Women'?s\s+Freedom\s+League)"),
    ("意大利", "共产主义", r"partito\s+comunista\s+italiano"),
    ("意大利", "社会主义", r"partito\s+socialista\s+italiano"),    ("意大利", "法西斯主义", r"partito\s+nazionale\s+fascista"),
    ("意大利", "天主教民众派", r"partito\s+popolare\s+italiano"),
    ("德国", "社会主义", r"(Sozialdemokratische\s+Partei\s+Deutschlands|"
                        r"Sozialdemokratische\s+Arbeiterpartei)"),
    ("德国", "民族主义右翼", r"(Deutschnationale\s+Volkspartei|Deutsche\s+Volkspartei|"
                            r"Deutschnationaler)"),
    ("德国", "纳粹主义", r"(Nationalsozialistische|NSDAP)"),
    ("奥地利", "基督教社会党", r"christlichsoziale?\s+partei"),
    ("奥地利", "社会民主党", r"sozialdemokratische\s+arbeiterpartei\s+"
                            r"(in\s+)?(deutsch)?[öo]sterreich"),
    ("荷兰", "社会主义", r"(Sociaal-?Democratische\s+Arbeiderspartij|SDAP)"),
    ("西班牙", "无政府主义", r"(Confederaci[oó]n\s+Nacional\s+del\s+Trabajo|CNT|"
                            r"Federaci[oó]n\s+Anarquista\s+Ib[eé]rica)"),
    ("西班牙", "社会主义", r"partido\s+socialista\s+obrero\s+espa[ñn]ol"),
    ("西班牙", "长枪党", r"(Falange\s+Espa[ñn]ola|FET\s+y\s+de\s+las\s+JONS)"),
    ("匈牙利", "社会主义", r"(Magyarorsz[aá]gi\s+Szoci[aá]ldemokrata\s+P[aá]rt|MSZDP)"),
]

#: 出版地 -> 国别。仅当机构名判不出时使用。
PLACE_RULES = [
    ("爱尔兰", r"\b(dublin|cork|belfast|limerick|waterford|galway|sligo|athlone)\b"),
    ("英国", r"\b(london|manchester|glasgow|edinburgh|birmingham|leeds|leicester|"
             r"westminster|letchworth|oxford|cambridge|cardiff|haslemere|liverpool)\b"),
    ("意大利", r"\b(roma|rome|milano|milan|torino|turin|firenze|florence|"
               r"napoli|naples|bologna|sarno|genova|genoa|palermo|venezia)\b"),
    ("奥地利", r"\b(wien|vienna)\b"),
    ("德国", r"\b(berlin|leipzig|münchen|munich|hamburg|frankfurt|stuttgart|"
             r"jena|breslau|dresden|köln|cologne|bonn|nürnberg|kiel|zürich|"
             r"hottingen)\b"),
    ("法国", r"\b(paris|lyon|marseille|bordeaux|lille)\b"),
    ("荷兰", r"\b(amsterdam|den\s+haag|'s-gravenhage|the\s+hague|rotterdam|utrecht|haarlem)\b"),
    ("西班牙", r"\b(madrid|barcelona|valencia|sevilla|bilbao|zaragoza)\b"),
    ("匈牙利", r"\b(budapest|pozsony|kolozsv[aá]r|debrecen)\b"),
]

#: 北美出版地：明确排除。爱尔兰材料大量在美加翻印，混进来会张冠李戴。
NORTH_AMERICA = re.compile(
    r"\b(new\s+york|boston|chicago|philadelphia|baltimore|minneapolis|"
    r"ottawa|toronto|montreal|qu[eé]bec|hamilton,\s*ont|nova\s+scotia|"
    r"madison|wisconsin|california|oregon|toledo|huntington|concord,\s*n\.?h|"
    r"washington|cincinnati|detroit|cleveland|pittsburgh|st\.\s*louis|"
    r"san\s+francisco|los\s+angeles|new\s+haven|princeton|ithaca|urbana)\b", re.I)

#: 其他英语区：同样排除。悉尼的 Fabian Society of NSW 不是英国费边社，
#: 墨尔本、惠灵顿、多伦多都有同名组织，靠名字判会全挂到英国。
OTHER_ANGLOPHONE = re.compile(
    r"\b(sydney|melbourne|adelaide|brisbane|perth|hobart|auckland|"
    r"wellington|christchurch|dunedin|toronto|montreal|vancouver|"
    r"new\s+south\s+wales|victoria,\s*aust|queensland)\b", re.I)

#: 不合体裁：期刊、年报、图册、词典、名册、JSTOR 抽印本、报刊
BAD = re.compile(
    r"(\bnovel|poems?|\bpoesie|gedichte|\bverses?|sermon|hymn|cookery|recipe|dictionary|"
    r"encyclop|almanac|yearbook|kalender|adressbuch|directory|\bjournal\b|magazine|"
    r"\breview\b|quarterly|annals|proceedings|argus|herald|tribune|gazette|"
    r"newspaper|zeitung|courier|sentinel|\bbulletin|statutes|code\s+of|compiled\s+laws|"
    r"session\s+laws|report\s+of\s+the|minutes\s+of|annual\s+report|jahresbericht|"
    r"rechenschaftsbericht|bericht\s+der|katalog|catalogue|bibliograph|index\s+and|"
    r"\bromans?\b|romanzo|erzählung|novelle|biography|memoir|autobiograph|"
    r"address\s*book|guide\s+to|handbook\s+of|textbook|grammar|prayer|architektur|"
    r"\bkunst\b|schulungsbrief|volkskalender|almanach|entomolog|\bflora\b|\bfauna\b|"
    r"who'?s\s+who|list\s+of|nullification|bilingualism|"
    r"souvenir\s+program|official\s+programme|"
    r"married\s+to\s+a\s+suffragette|suffragette\s+town\s+meeting|"
    r"the\s+suffragette\s+has\s+come|\ba\s+play\s+in\s+one\s+act)", re.I)

#: 合订本：标题就是系列名，没有独立篇名
SERIAL_TITLE = re.compile(r"^(fabian\s+tracts?|tracts?)\s*$", re.I)

#: 非实体宣传品：JSTOR 抽印本、HMSO 文书、缩微号占位
JUNK_ID = re.compile(r"^(jstor-|op1|ldpd_|sc_|b\d{7,}|annualreport)", re.I)


#: 检索式。只做召回，国别靠 ORG_RULES / PLACE_RULES 判。
QUERIES = [
    ('subject:("Fabian Society") OR creator:("Fabian Society")'),
    ('title:("Fabian tract") AND NOT title:("Fabian tracts")'),
    ('creator:("Independent Labour Party") OR title:("Independent Labour Party")'),
    ('creator:("Social Democratic Federation") OR subject:("Social Democratic Federation")'),
    ('creator:("Labour Party (Great Britain)") OR subject:("Labour Party (Great Britain)")'),
    ('subject:("Trades Union Congress") OR creator:("Trades Union Congress")'),
    ('creator:("Sinn Fein") OR subject:("Sinn Fein")'),
    ('creator:("Irish National League" OR "United Irish League" OR "Land League") '
     'OR subject:("Land League (Ireland)")'),
    ('creator:("Irish Unionist Alliance" OR "Irish Loyal and Patriotic Union" '
     'OR "Ulster Unionist Council")'),
    ('creator:("Partito comunista italiano" OR "Partito socialista italiano" '
     'OR "Partito popolare italiano")'),
    ('subject:("Partito socialista italiano" OR "Partito comunista italiano" '
     'OR "Partito popolare italiano" OR "Partito nazionale fascista")'),
    ('creator:("Sozialdemokratische Partei Deutschlands" OR "Deutschnationale Volkspartei" '
     'OR "Deutsche Volkspartei")'),
    ('creator:("Christlichsoziale Partei" OR "Sozialdemokratische Arbeiterpartei")'),
    ('subject:("Christlichsoziale Partei") OR subject:("Sozialdemokratische '
     'Arbeiterpartei Österreichs")'),
    ('creator:("Sociaal-Democratische Arbeiderspartij") OR '
     'subject:("Sociaal-Democratische Arbeiderspartij")'),
    ('creator:("Confederación Nacional del Trabajo" OR "Falange Española" '
     'OR "Partido Socialista Obrero")'),
]


def get_json(url, timeout=60, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                return json.loads(r.read())
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


def fetch_file(url, path, timeout=180, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                data = r.read()
            if len(data) < 4000:
                raise ValueError("too small")
            with open(path, "wb") as f:
                f.write(data)
            return len(data)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))


def search(q, rows=80):
    params = {"q": q, "fl[]": ["identifier", "title", "year", "language", "imagecount"],
              "rows": str(rows), "output": "json", "sort[]": "downloads desc"}
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return get_json(url)


def pick_pdf(meta):
    best, best_size = None, 0
    for f in meta.get("files", []):
        if not str(f.get("name", "")).endswith(".pdf"):
            continue
        try:
            sz = int(f.get("size") or 0)
        except (TypeError, ValueError):
            sz = 0
        if best is None or (sz and sz < best_size):
            best, best_size = f["name"], sz
    if best and best_size <= PDF_MAX_MB * 1048576:
        return best, best_size
    return None, 0


def _join(v):
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return str(v or "")


def attribute(md):
    """返回 (国别, 立场, 依据)。判不出返回 ("", "", "")。

    证据强弱：出版者机构名 > 作者机构名 > 出版地 > 主题词。
      - 出版者/作者是政党、工会、宣传机构本身时，国别按该组织的政治出身定
        （与既有目录一致：1848 年伦敦印的《共产党宣言》归"德国"）。
      - 作者是个人时不能靠 subject 判——《Die Italienische Sozialistische Partei》
        是汉堡的共产国际出版社出的德文书，subject 里有 Partito socialista italiano，
        按 subject 会误挂到意大利。
      - 北美出版地优先排除：爱尔兰与英国材料在美加大量翻印。
    """
    creator = _join(md.get("creator"))
    pub = _join(md.get("publisher"))
    subject = _join(md.get("subject"))

    # metadata 完全为空：无从核验，直接丢弃
    if not (creator or pub):
        return "", "", "metadata 为空"

    if NORTH_AMERICA.search(pub) or OTHER_ANGLOPHONE.search(pub):
        return "", "", "非目标国出版地排除"

    for country, stance, pat in ORG_RULES:
        if re.search(pat, pub, re.I):
            return country, stance, "出版者"
    for country, stance, pat in ORG_RULES:
        if re.search(pat, creator, re.I):
            return country, stance, "作者机构"

    low = pub.lower()
    for country, pat in PLACE_RULES:
        if re.search(pat, low):
            stance = {
                "爱尔兰": "民族主义", "英国": "工党与社会主义",
                "意大利": "社会主义", "德国": "社会主义",
                "奥地利": "社会民主党", "荷兰": "社会主义",
                "西班牙": "社会主义", "匈牙利": "社会主义",
                "法国": "社会主义",
            }.get(country, "")
            return country, stance, "出版地"

    # 最后才看主题词，且必须同时有可判定的出版地，否则宁可丢弃
    for country, stance, pat in ORG_RULES:
        if re.search(pat, subject, re.I):
            return "", "", "仅主题词命中，无出版地佐证"
    return "", "", ""


def safe(s, n=44):
    s = re.sub(r'[\\/:*?"<>|]+', "_", re.sub(r"<[^>]+>", "", str(s)))
    return re.sub(r"\s+", " ", s).strip()[:n].strip(" ._-") or "untitled"


def known_keys():
    recs = json.load(open(CATALOG, encoding="utf-8"))
    ids, titles = set(), set()
    for r in recs:
        u = r.get("url", "")
        if "archive.org/details/" in u:
            ids.add(u.rsplit("/", 1)[-1].split("?")[0])
        titles.add(re.sub(r"[^a-z0-9]+", "", r.get("title", "").lower())[:30])
    return ids, titles


def norm(t):
    return re.sub(r"[^a-z0-9]+", "", str(t).lower())[:30]


def collect():
    known_ids, known_titles = known_keys()
    seen_ids, seen_titles = set(), set()
    dropped = {}
    out = []

    def drop(reason):
        dropped[reason] = dropped.get(reason, 0) + 1

    for q in QUERIES:
        full = f'{q} AND imagecount:[{MINP} TO {MAXP}] AND year:[1840 TO 1955] AND mediatype:texts'
        try:
            d = search(full)
        except Exception as e:
            print(f"  检索失败 {q[:44]}: {type(e).__name__}")
            continue
        for doc in (d.get("response") or {}).get("docs", []):
            ident = str(doc.get("identifier") or "")
            title = re.sub(r"<[^>]+>", "", str(doc.get("title") or "")).strip()
            if not ident or ident in known_ids or ident in seen_ids:
                drop("已收录或重复")
                continue
            if JUNK_ID.match(ident):
                drop("抽印本/文书/缩微占位")
                continue
            if not title or SERIAL_TITLE.match(title):
                drop("系列合订本")
                continue
            if BAD.search(title):
                drop("不合体裁")
                continue
            if norm(title) in known_titles or norm(title) in seen_titles:
                drop("标题重复")
                continue
            try:
                ic = int(doc.get("imagecount") or 0)
            except (TypeError, ValueError):
                drop("页数未知")
                continue
            if not (MINP <= ic <= MAXP):
                drop("页数越界")
                continue
            year = str(doc.get("year") or "")[:4]
            if not year.isdigit() or not (1840 <= int(year) <= 1955):
                drop("年份越界")
                continue

            try:
                meta = get_json(f"https://archive.org/metadata/{ident}")
            except Exception:
                drop("metadata 失败")
                continue
            md = meta.get("metadata", {}) or {}
            country, stance, basis = attribute(md)
            if not country:
                drop(basis or "国别判不出")
                continue

            pdf_name, pdf_size = pick_pdf(meta)
            seen_ids.add(ident)
            seen_titles.add(norm(title))
            out.append({
                "country": country, "stance": stance, "identifier": ident,
                "title": title, "year": year, "pages": ic, "basis": basis,
                "creator": _join(md.get("creator"))[:100],
                "publisher": _join(md.get("publisher"))[:80],
                "url": f"https://archive.org/details/{ident}",
                "pdf_name": pdf_name, "pdf_size": pdf_size,
            })
            time.sleep(0.15)
    return out, dropped


def main():
    dry = "--dry" in sys.argv
    print("召回中（机构名 → 出版地 → 丢弃）…\n")
    cands, dropped = collect()

    from collections import Counter
    print(f"候选 {len(cands)} 本：")
    for k, v in Counter(c["country"] for c in cands).most_common():
        print(f"   {k:6s} {v}")
    print("\n丢弃原因：")
    for k, v in sorted(dropped.items(), key=lambda kv: -kv[1]):
        print(f"   {k:24s} {v}")

    print()
    for c in cands:
        print(f"  {c['country']:6s} {c['year']:4s} {c['pages']:3d}p [{c['basis']:4s}] "
              f"{c['identifier'][:30]:30s} {c['publisher'][:26]:26s} {c['title'][:38]}")

    if dry:
        return

    os.makedirs(RAW, exist_ok=True)
    records, taken = [], Counter()

    for c in cands:
        if taken[c["country"]] >= LIMIT_PER_COUNTRY.get(c["country"], 4):
            continue
        n = len(records) + 1
        folder = os.path.join(RAW, f"{n:03d}")
        os.makedirs(os.path.join(folder, "pages"), exist_ok=True)

        rec = {k: v for k, v in c.items() if k not in ("pdf_name", "pdf_size")}
        rec["no"] = n
        rec["pdf"] = False
        if c["pdf_name"]:
            try:
                fetch_file(
                    f"https://archive.org/download/{c['identifier']}/{urllib.parse.quote(c['pdf_name'])}",
                    os.path.join(folder, "doc.pdf"))
                rec["pdf"] = True
                rec["pdf_size"] = c["pdf_size"]
            except Exception as e:
                rec["pdf_error"] = type(e).__name__

        ok = 0
        for p in range(min(c["pages"], MAX_PAGES_DL)):
            try:
                fetch_file(f"https://archive.org/download/{c['identifier']}/page/n{p}_w1000.jpg",
                           os.path.join(folder, "pages", f"p-{p + 1:05d}.jpg"), timeout=90)
                ok += 1
            except Exception:
                pass
            time.sleep(0.05)
        rec["pages_got"] = ok

        if ok < 4:
            import shutil
            print(f"  丢弃 {c['identifier']}: 只取到 {ok} 页")
            shutil.rmtree(folder, ignore_errors=True)
            continue

        taken[c["country"]] += 1
        records.append(rec)
        print(f"  {c['country']:6s} {c['year']:4s} 图{ok:>3d} "
              f"pdf{'✓' if rec['pdf'] else '×'}  {c['title'][:46]}", flush=True)
        time.sleep(0.3)

    json.dump(records, open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n=== 采到 {len(records)} 本 ===")
    for k, v in Counter(r["country"] for r in records).most_common():
        print(f"   {k:6s} {v}")


if __name__ == "__main__":
    main()
