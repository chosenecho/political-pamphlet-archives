"""Internet Archive 第十轮补采：只补多页小册子（约 50 本）。

背景：目录里单页传单／海报已 384 件，小册子只有 156 本。本轮按用户要求
只收多页宣传册，不再收单页。

检索路径（三轮探针试出来的，记下来免得重走）：
  · subject:(国别 AND party/program/…) 的大类检索命中率不到两成，
    其余是教会史、主教名录、地质报告、渔业传单与 NASA 技术备忘录。
  · 按 publisher:("Partito Socialista Italiano") 反查命中数极低；
    放宽到 publisher:(Budapest) 这类地名，又把巴塞罗那的加泰罗尼亚独幕剧、
    巴勒莫的歌剧台本大量捞进来——出版者名里带 "Società"/"Regional"。
  · 真正有效的是两条并用：LCSH「<国别> -- Politics and government」标目
    + 政党出版物体裁词（Parteitag/Bericht、profession de foi、discorso agli
    elettori、address of the … committee、platform）。868 条候选池再按
    「出版者是政党/工会」打分粗筛到 129 条，逐条读 publisher/creator 定夺。

因此本版仍是**显式白名单**，每条写明国别、立场与核验依据。国别判定沿用
目录既有口径：出版者是政党/工会本身时按该组织的政治出身定（伦敦印的
《共产党宣言》归德国那一类）。

用法：
    python scripts/harvest_ia_round10.py --dry
    python scripts/harvest_ia_round10.py
"""

import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "images", "round10")
RAW = os.path.join(ROOT, "raw")
CATALOG = os.path.join(BASE, "data", "catalog.json")

PROXY = "http://127.0.0.1:10808"
UA = ("PoliticalPamphletArchives/1.0 "
      "(https://github.com/chosenecho/political-pamphlet-archives; research-only)")
WORKERS = 16
MAX_PAGES = 90
PDF_MAX_MB = 25

#: (identifier, 国别, 立场, 年份覆盖或 None, 核验依据)
KEEP = [
    # ---------- 英国 ----------
    ("socialismmadepla00soci", "英国", "社会主义", None,
     "社会民主同盟（SDF）《社会主义浅说》，即该盟社会与政治宣言，伦敦 1884"),
    ("addresstotrades00lanegoog", "英国", "社会主义", None,
     "社会主义同盟理事会《告工会书》，伦敦 1885，巴克斯与莱恩署名"),
    ("secondfrontmrchu00gall", "英国", "共产主义", None,
     "英共议员加拉赫在下院要求开辟第二战场的演说，共产党出版社 1942"),

    # ---------- 德国 ----------
    ("bub_gb_HzAvAAAAYAAJ", "德国", "社会主义", None,
     "伯恩施坦《社会所有制与私有制》，为解释社会主义纲领而作，前进报出版社 1891"),
    ("conservativeinma00frieuoft", "德国", "保守主义", None,
     "萨克森保守党德累斯顿代表大会报告《保守主义：最后时刻的警号》，1892"),
    ("wochensprucheder01reic", "德国", "纳粹主义", None,
     "纳粹党帝国宣传总部《每周箴言》，党中央出版社 1942"),

    # ---------- 奥地利 ----------
    # 代表大会年度报告，IA 的 year 字段一律写成 1900，改按 identifier 里的年份。
    ("berichtderpartei1902soziuoft", "奥地利", "社会民主党", "1902",
     "奥地利社会民主工人党执委会向代表大会的报告，维也纳 1902"),
    ("berichtderpartei1905soziuoft", "奥地利", "社会民主党", "1905",
     "奥地利社会民主工人党执委会向代表大会的报告，维也纳 1905"),
    ("berichtderpartei1909soziuoft", "奥地利", "社会民主党", "1909",
     "奥地利社会民主工人党执委会向代表大会的报告，维也纳 1909"),
    ("berichtderpartei1912soziuoft", "奥地利", "社会民主党", "1912",
     "奥地利社会民主工人党执委会向代表大会的报告，维也纳 1912"),
    ("protokollberdi00chriuoft", "奥地利", "天主教社会运动", "1911",
     "奥地利基督教社会工人第九次代表大会会议记录，维也纳 1911"),

    # ---------- 俄国 / 苏联 ----------
    ("komubytsamoderzh00ross", "俄国", "社会主义", None,
     "俄国社会民主工党《谁来做全俄的专制者？》，日内瓦《火星报》出版社 1905"),
    ("prostyiariechiov00mart", "俄国", "社会主义", None,
     "马尔托夫《关于内部敌人的浅近讲话》，日内瓦《火星报》出版社 1905"),
    ("istoriiarevoliut11thun", "俄国", "社会主义革命党", None,
     "图恩《俄国革命运动史》，社会革命党印刷所，巴黎 1903"),
    ("centrallocalauth00kame", "苏联", "共产主义", None,
     "加米涅夫在全俄苏维埃第七次代表大会上关于苏维埃建设的报告，全俄工会中央理事会 1920"),

    # ---------- 波兰 ----------
    ("wiediepolenihref00lozy", "波兰", "民族主义", None,
     "洛津斯基《波兰人如何理解自己的自由》，1915，波兰问题论战册"),

    # ---------- 意大利 ----------
    ("discorsodellonor00marc", "意大利", "选举宣传", None,
     "马尔切洛伯爵向第二选区选民的竞选演说，威尼斯 1909"),
    ("paroledelcogirol00marc_0", "意大利", "选举宣传", None,
     "马尔切洛伯爵在穆拉诺地方选举集会上的演说，1905"),

    # ---------- 西班牙 ----------
    ("spaininchains00gilr", "西班牙", "天主教右翼", None,
     "希尔·罗夫莱斯《被锁链束缚的西班牙》，纽约美洲出版社 1937，CEDA 领袖的战时宣传"),

    # ---------- 荷兰 ----------
    ("aanteekeningenvo00unse", "荷兰", "选举宣传", None,
     "《一九〇五年投票辩论札记》，荷兰大选前的辩论手册 1905"),

    # ---------- 印度 ----------
    ("caseforindiapres00besarich", "印度", "民族主义", None,
     "贝桑特夫人在国大党第三十二届年会（加尔各答 1917）的主席演说《印度的理由》"),
    ("futureofindiapre00sinhiala", "印度", "民族主义", None,
     "辛哈《印度的未来》，国大党年会主席演说 1916"),
    ("noncooperation00andruoft", "印度", "民族主义", "1920",
     "安德鲁斯《不合作》，马德拉斯 Ganesh 出版，1920 年前后，甘地不合作运动的宣传册"),
    ("indienundderwelt00euro", "印度", "民族主义", None,
     "《印度与世界和平》，印度国民党欧洲中央委员会印行，斯德哥尔摩 1918"),

    # ---------- 中国 ----------
    ("guotiwentilun018800", "中国", "政治思想宣传", None,
     "梁启超《国体问题论》，上海广智书局 1915，反对袁世凯称帝"),

    # ---------- 土耳其 ----------
    ("tablettesrvolu00fehm", "土耳其", "青年土耳其党", None,
     "《一个青年土耳其人的革命札记》，巴黎 1903，青年土耳其党流亡宣传"),

    # ---------- 拉美 ----------
    ("cubacontraespa00varo", "拉美", "民族主义", None,
     "古巴革命党《古巴对抗西班牙——告西语美洲各民族宣言》，纽约 1895"),
    ("cartaqueeljen00unseguat", "拉美", "自由主义", None,
     "危地马拉总统巴里奥斯《致中美洲自由党友人书》，1883"),
    ("manifiestodelje00unseguat", "拉美", "自由主义", None,
     "萨尔瓦多总统赫拉尔多·巴里奥斯《告萨尔瓦多及中美洲各民族书》，1857"),
    ("manifiestojustif00juar", "拉美", "共和派", None,
     "华雷斯《克雷塔罗国民刑罚辩护书》，墨西哥 1868"),

    # ---------- 爱尔兰 ----------
    ("foundationofrepu00deva", "爱尔兰", "共和派", None,
     "德瓦莱拉《爱尔兰共和国奠定于人民的投票》，1919"),
    ("correspondenceof02deva", "爱尔兰", "共和派", None,
     "德瓦莱拉等人书信集，1922，反对英爱条约一方的主张"),
    ("freestatepromise00omal", "爱尔兰", "共和派", None,
     "《自由邦的许诺是真的吗？》，1921，反条约宣传册"),
    ("problemofulster00craw", "爱尔兰", "联合派", None,
     "克劳福德《阿尔斯特问题》，1920"),
    ("convictedrecordo00malc", "爱尔兰", "民族主义", None,
     "《被判罪者：不忠言论、决议、传单与海报的记录》，1912，都柏林城堡查扣材料汇编"),

    # ---------- 美国 ----------
    ("addresstodemocra00demo", "美国", "民主党", None,
     "民主党全国执行委员会《告民主派与美国人民书》，华盛顿 1860"),
    ("congressionaladd00unit", "美国", "民主党", None,
     "第三十八届国会民主党议员《国会宣言》，华盛顿 1864"),
    ("addressbyunionle00unio", "美国", "共和党", None,
     "费城联盟同盟《告宾夕法尼亚公民书》，支持林肯连任，1864"),
    ("republicanleader00smal", "美国", "共和党", None,
     "共和党全国委员会《共和党领袖：加菲尔德与阿瑟传略》，1880"),
    ("ldpd_6516722_000", "美国", "社会主义", None,
     "杜埃《好日子来了！》，社会主义劳工党执行委员会出版，1884"),
    ("whyfarmersuffer00mckirich", "美国", "共和党", None,
     "麦金莱《农民为何受苦》，共和党全国委员会 1896"),
    ("horsesense00alle", "美国", "共和党", None,
     "阿勒顿《常识》，共和党全国委员会 1896 竞选册"),
    ("moneyquestion00mortrich", "美国", "民主党", None,
     "莫顿《货币问题》，全国民主党（杰斐逊派）宾州州委员会 1896"),
    ("isdemocraticpart00popu", "美国", "平民党", None,
     "北卡平民党州中央委员会《民主党诚实吗？事实陈述》，1898"),
    ("commentsbystated00demo", "美国", "民主党", None,
     "北卡民主党州执委会《评平民党手册》，1898"),
    ("contractwithpeop00prog", "美国", "进步党", None,
     "进步党第一次全国代表大会（芝加哥 1912）通过的《与人民订约》政纲"),
    ("nationalprogress00prog", "美国", "进步党", None,
     "进步党全国代表大会日程册，芝加哥 1912"),
    ("speechofhonhenry00lodg", "美国", "共和党", None,
     "洛奇在麻州共和党州代表大会的演说，波士顿 1912"),
    ("congressionalpla00soci", "美国", "社会主义", None,
     "美国社会党 1918 年国会竞选纲领，党全国总部（芝加哥）印行"),
    ("democraticplatfo00demo", "美国", "民主党", None,
     "北卡民主党州代表大会 1920 年州与全国政纲"),
    ("whopaysunderwils00repu", "美国", "共和党", None,
     "共和党全国委员会《威尔逊治下谁在纳税？》，1920 竞选册"),
    ("wilsonsfatalpoli00repu", "美国", "共和党", None,
     "共和党全国委员会《威尔逊在墨西哥的致命政策》，1920"),
    ("220904-cpa-labordaymanifesto", "美国", "共产主义", None,
     "统一共产党《告美国工人书》，1922 劳动节宣言"),
]


def opener():
    op = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    op.addheaders = [("User-Agent", UA)]
    return op


def get_json(op, url, timeout=90, retries=4):
    last = None
    for i in range(retries):
        try:
            with op.open(url, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            last = e
            if i == retries - 1:
                raise
            time.sleep(2 + 2 * i)
    raise last


def pick_pdf(meta):
    best, size = None, 0
    for f in meta.get("files", []):
        if not str(f.get("name", "")).endswith(".pdf"):
            continue
        try:
            sz = int(f.get("size") or 0)
        except (TypeError, ValueError):
            sz = 0
        if best is None or (sz and sz < size):
            best, size = f["name"], sz
    if best and size <= PDF_MAX_MB * 1048576:
        return best
    return None


def _join(v, n=160):
    if isinstance(v, list):
        v = " | ".join(str(x) for x in v)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(v or ""))).strip()[:n]


def known_ids():
    with open(CATALOG, encoding="utf-8") as f:
        recs = json.load(f)
    return {r["url"].rsplit("/", 1)[-1].split("?")[0]
            for r in recs if "archive.org/details/" in r.get("url", "")}


def main():
    dry = "--dry" in sys.argv
    op = opener()
    have = known_ids()

    items = []
    for ident, country, stance, year_fix, basis in KEEP:
        if ident in have:
            print(f"  跳过（已收录）{ident}")
            continue
        try:
            meta = get_json(op, f"https://archive.org/metadata/{ident}")
        except Exception as e:
            print(f"  跳过 {ident}: metadata 失败 {type(e).__name__}")
            continue
        md = meta.get("metadata", {}) or {}
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(md.get("title") or ""))).strip()
        if not title:
            print(f"  跳过 {ident}: 无标题")
            continue
        try:
            pages = int(md.get("imagecount") or 0)
        except (TypeError, ValueError):
            pages = 0
        if pages < 8:
            print(f"  跳过 {ident}: 页数 {pages}（不足 8 页，不是小册子）")
            continue
        year = year_fix or str(md.get("date") or md.get("year") or "")[:4]
        if not year.isdigit():
            m = re.search(r"(1[89]\d{2}|19\d{2})", str(md.get("date") or ""))
            year = m.group(1) if m else ""

        items.append({
            "country": country, "stance": stance, "identifier": ident,
            "title": title, "year": year, "pages": min(pages, MAX_PAGES),
            "creator": _join(md.get("creator")),
            "publisher": _join(md.get("publisher")),
            "url": f"https://archive.org/details/{ident}",
            "basis": basis, "pdf_name": pick_pdf(meta),
        })
        time.sleep(0.1)

    print(f"\n白名单可用 {len(items)} 本：")
    for c in items:
        print(f"  {c['country']:4s} {c['year']:4s} {c['pages']:3d}p "
              f"{c['identifier'][:32]:32s} {c['basis'][:40]}")

    if dry:
        return 0

    os.makedirs(RAW, exist_ok=True)
    records = []
    for c in items:
        n = len(records) + 1
        folder = os.path.join(RAW, f"{n:03d}")
        os.makedirs(os.path.join(folder, "pages"), exist_ok=True)

        rec = {k: v for k, v in c.items() if k != "pdf_name"}
        rec["no"] = n
        rec["pdf"] = False
        if c["pdf_name"]:
            try:
                data = _fetch(op, f"https://archive.org/download/{c['identifier']}/"
                                  f"{urllib.parse.quote(c['pdf_name'])}", timeout=300)
                with open(os.path.join(folder, "doc.pdf"), "wb") as f:
                    f.write(data)
                rec["pdf"] = True
            except Exception as e:
                rec["pdf_error"] = type(e).__name__

        def one(p, _ident=c["identifier"], _folder=folder):
            url = f"https://archive.org/download/{_ident}/page/n{p}_w1000.jpg"
            for attempt in range(2):
                try:
                    data = _fetch(op, url, timeout=120)
                    if len(data) > 2000:
                        with open(os.path.join(_folder, "pages", f"p-{p + 1:05d}.jpg"),
                                  "wb") as f:
                            f.write(data)
                        return True
                except Exception:
                    time.sleep(1 + attempt)
            return False

        t0 = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            res = list(ex.map(one, range(min(c["pages"], MAX_PAGES))))
        ok = sum(1 for r in res if r)
        rec["pages_got"] = ok
        el = time.time() - t0

        if ok < 8:
            import shutil
            print(f"  丢弃 {c['identifier'][:32]}: 只取到 {ok} 页")
            shutil.rmtree(folder, ignore_errors=True)
            continue

        records.append(rec)
        print(f"  {c['country']:4s} {c['year']:4s} 图{ok:>3d}/{c['pages']:<3d} "
              f"pdf{'Y' if rec['pdf'] else 'N'} {el:5.1f}s  {c['title'][:38]}", flush=True)

    with open(os.path.join(ROOT, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    from collections import Counter
    print(f"\n=== 采到 {len(records)} 本 ===")
    for k, v in Counter(r["country"] for r in records).most_common():
        print(f"   {k:5s} {v}")
    return 0


def _fetch(op, url, timeout=120, retries=3):
    last = None
    for i in range(retries):
        try:
            with op.open(url, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise last


if __name__ == "__main__":
    sys.exit(main() or 0)
