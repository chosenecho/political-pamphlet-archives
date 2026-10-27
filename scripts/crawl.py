"""Crawl the 20+ pamphlet/ephemera collections' landing pages into local raw + text.

Writes:
  raw/<slug>.html   original bytes
  txt/<slug>.txt    extracted readable text (lxml)
  manifest.json     per-source result record
"""
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request

from lxml import html as LH

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
TXT = os.path.join(BASE, "txt")
os.makedirs(RAW, exist_ok=True)
os.makedirs(TXT, exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,de;q=0.7,fr;q=0.6",
    "Cache-Control": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

SOURCES = [
    ("jstor-19c-british-pamphlets", "JSTOR · 19th Century British Pamphlets", "UK",
     "https://www.jstor.org/site/primary-sources/19th-century-british-pamphlets/"),
    ("bodleian-john-johnson", "Bodleian · John Johnson Collection of Printed Ephemera", "UK",
     "https://www.bodleian.ox.ac.uk/collections-and-resources/special-collections/catalogues/johnson"),
    ("bishopsgate-labour-socialist", "Bishopsgate Institute · Labour and Socialist History", "UK",
     "https://www.bishopsgate.org.uk/collections/labour-and-socialist-history/"),
    ("phm-labour-history-archive", "People's History Museum · Labour History Archive & Study Centre", "UK",
     "https://phm.org.uk/collection/labour-history-archive-study-centre/"),
    ("lse-digital-library", "LSE Digital Library · Collections", "UK",
     "https://digital.library.lse.ac.uk/collections"),
    ("nyu-tamiment-cpusa", "NYU Tamiment · Printed Ephemera Collection on the CPUSA", "US",
     "https://findingaids.library.nyu.edu/tamwag/pe_031/"),
    ("umich-labadie", "University of Michigan · Joseph A. Labadie Collection", "US",
     "https://www.lib.umich.edu/collections/collecting-areas/special-collections/joseph-labadie-collection/"),
    ("hoover-posters", "Hoover Institution · Poster Collection", "US",
     "https://www.hoover.org/library-archives/collections/posters"),
    ("hoover-digital-collections", "Hoover Institution · Digital Collections", "US",
     "https://www.hoover.org/library-archives/collections/digital-collections"),
    ("loc-printed-ephemera", "Library of Congress · Printed Ephemera / An American Time Capsule", "US",
     "https://www.loc.gov/collections/"),
    ("iisg-collections", "IISH Amsterdam · Collections", "NL",
     "https://iisg.amsterdam/en/collections"),
    ("sozialarchiv-zuerich", "Schweizerisches Sozialarchiv", "CH",
     "https://www.sozialarchiv.ch/"),
    ("fes-adsd", "Friedrich-Ebert-Stiftung · Archiv der sozialen Demokratie", "DE",
     "https://www.fes.de/archiv-der-sozialen-demokratie"),
    ("fes-digitale-bibliothek", "FES · Digitale Bibliothek (retro-digitalised periodicals & series)", "DE",
     "https://www.fes.de/bibliothek/zeitschriften-digitalisierung"),
    ("kas-archiv-bibliothek", "Konrad-Adenauer-Stiftung · Archiv für Christlich-Demokratische Politik", "DE",
     "https://www.kas.de/de/archiv-und-bibliothek"),
    ("wlb-zeit-der-weltkriege", "Württembergische Landesbibliothek · Zeit der Weltkriege", "DE",
     "https://www.wlb-stuttgart.de/sammlungen/zeit-der-weltkriege"),
    ("la-contemporaine", "La Contemporaine · Collections", "FR",
     "https://www.lacontemporaine.fr/en/collections/"),
    ("francearchives-tracts", "FranceArchives · Fonds des tracts politiques", "FR",
     "https://francearchives.gouv.fr/fr/findingaid/1e48faec7165e984c693396f23969f5e00008e55"),
    ("gallica-tracts-ww2", "Gallica (BnF) · Tracts de la Seconde Guerre mondiale", "FR",
     "https://gallica.bnf.fr/accueil/fr/html/les-tracts-de-la-seconde-guerre-mondiale-a-la-reserve-des-livres-rares"),
    ("pares-carteles", "PARES · Carteles de la España Republicana", "ES",
     "https://pares.cultura.gob.es/ParesBusquedas20/catalogo/description/117015"),
    ("gale-political-extremism", "Gale · Political Extremism and Radicalism", "US/UK",
     "https://www.gale.com/primary-sources/political-extremism-and-radicalism"),
    ("modernhistory-cn", "抗日战争与近代中日关系文献数据平台", "CN",
     "https://www.modernhistory.org.cn/"),
    ("ndl-digital-collections", "国立国会図書館デジタルコレクション", "JP",
     "https://dl.ndl.go.jp/"),
    ("amsab-isg", "Amsab-ISG · Institute of Social History", "BE",
     "https://www.amsab.be/en/"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def extract_text(raw_bytes, encoding_guess=None):
    doc = LH.fromstring(raw_bytes)
    for bad in doc.xpath("//script|//style|//noscript|//svg"):
        bad.getparent().remove(bad)
    for tag in doc.xpath("//br"):
        tag.tail = "\n" + (tag.tail or "")
    text = doc.text_content()
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in text.splitlines()]
    out = []
    for ln in lines:
        if ln:
            out.append(ln)
        elif out and out[-1] != "":
            out.append("")
    return "\n".join(out)


def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.status, r.read(), r.geturl()


#: 正文字符数下限。低于此值多半不是「正文本来就短」，而是反爬拦截或 JS 门禁
#: 返回的空壳页——页面能连上，但没有任何可用正文。与 build_index.py 判定
#: notes/ 状态用的阈值一致，两处口径相同才不会互相打架。
MIN_CHARS = 500


def judge(rec):
    """判定一次抓取，返回 (fetched, readable, 原因)。

    要分开两件事，合成一个布尔值就说不清了：
      fetched   直连有没有拿到 2xx 响应
      readable  最终有没有可读正文（正文也可能来自人工/其它渠道，见 via）

    例如 kas-archiv-bibliothek 直连 403，但用 firecrawl 取到了 2000+ 字符正文：
    fetched=False、readable=True。旧写法只记一个 ok，把这种情况要么说成「成功」
    （掩盖被反爬拦截的事实），要么说成「失败」（抹掉实际到手的正文）。
    """
    status = rec.get("status")
    chars = rec.get("chars") or 0

    if not isinstance(status, int):
        return False, False, rec.get("error") or "没有 HTTP 状态"
    if rec.get("text_error"):
        return False, False, rec["text_error"]

    fetched = status < 400
    readable = chars >= MIN_CHARS
    if fetched and not readable:
        return True, False, (f"正文仅 {chars} 字符（下限 {MIN_CHARS}），"
                             f"疑似 JS 门禁或空壳页")
    if not fetched and readable:
        # 直连被拒但正文够长：正文是绕过后取得的，不是这次直连的成果
        return False, True, f"HTTP {status}（正文另行取得）"
    if not fetched:
        return False, False, f"HTTP {status}"
    return True, True, ""


manifest = []

for slug, title, region, url in SOURCES:
    rec = {"slug": slug, "title": title, "region": region, "url": url}
    t0 = time.time()
    try:
        status, body, final_url = fetch(url)
        rec["status"] = status
        rec["final_url"] = final_url
        rec["bytes"] = len(body)
        with open(os.path.join(RAW, slug + ".html"), "wb") as f:
            f.write(body)
        try:
            text = extract_text(body)
            rec["chars"] = len(text)
            with open(os.path.join(TXT, slug + ".txt"), "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:  # noqa: BLE001
            rec["text_error"] = f"{type(e).__name__}: {e}"
    except urllib.error.HTTPError as e:
        rec["status"] = e.code
        rec["error"] = f"HTTP {e.code} {e.reason}"
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"

    # ok 统一由 judge 判定：拿到 403/429 的响应页或 JS 空壳页都不算抓到
    rec["fetched"], rec["readable"], why = judge(rec)
    rec["ok"] = rec["readable"]
    if why:
        rec["error"] = why
    rec["seconds"] = round(time.time() - t0, 1)
    rec["via"] = "urllib-crawl"
    manifest.append(rec)
    flag = "OK " if rec["ok"] else "ERR"
    print(f"{flag} {slug:34s} {rec.get('status', '-'):>4} "
          f"{rec.get('chars', rec.get('error', ''))}")
    time.sleep(1.5)

with open(os.path.join(BASE, "data", "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

ok = sum(1 for r in manifest if r.get("ok"))
print(f"\n{ok}/{len(manifest)} fetched")
