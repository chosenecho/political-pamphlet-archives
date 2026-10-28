"""探针：IA 已恢复，为仍缺小册子的国别再探一轮。

当前无小册子的国别：拉美、捷克、日本、波兰、葡萄牙、比利时、瑞典、苏联。
上一轮的结论是这些国别在 IA 上命中多为期刊/法令/学术论文。
本轮换检索角度再试：馆藏集合、语种+体裁词、题名里的政党组织名。
"""

import os
import sys
import urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import http

BASE_Q = "imagecount:[8 TO 80] AND year:[1840 TO 1970] AND mediatype:texts"

PROBES = [
    # --- 苏联 / 俄国：政纲、代表大会材料 ---
    ("苏联 党纲汇编", 'language:rus AND title:(программа OR устав OR резолюция) AND year:[1917 TO 1950]'),
    ("苏联 宣传册", 'language:rus AND subject:(пропаганда OR агитация) AND year:[1917 TO 1950]'),
    ("苏联 各加盟共和国", 'language:rus AND title:(Латвия OR Азербайджан OR Украина) AND year:[1920 TO 1950]'),

    # --- 波兰 ---
    ("波兰 政党纲", 'language:pol AND title:(program OR statut OR uchwała OR odezwa)'),
    ("波兰 流亡政府", 'language:pol AND subject:(Polska AND (polityka OR rząd OR emigracja))'),
    ("波兰 战后", 'language:pol AND year:[1944 TO 1960] AND subject:(partia OR zjazd)'),

    # --- 捷克 ---
    ("捷克 政党", 'language:cze AND title:(program OR stanovy OR provolání OR rezoluce)'),
    ("捷克 斯洛伐克", 'language:slo AND title:(program OR vyhlásenie)'),
    ("捷克 1948", 'language:cze AND year:[1945 TO 1960] AND subject:(politika OR strana)'),

    # --- 日本 ---
    ("日本 政纲", 'language:jpn AND title:(宣言 OR 綱領 OR 規約 OR 決議)'),
    ("日本 選挙", 'language:jpn AND subject:(選挙 OR 政党 OR 労働)'),
    ("日本 無産", 'language:jpn AND year:[1920 TO 1940] AND subject:(社会 OR 労働 OR 農民)'),

    # --- 葡萄牙 ---
    ("葡萄牙 共和国", 'language:por AND title:(programa OR manifesto OR estatuto)'),
    ("葡萄牙 政团", 'language:por AND subject:(Portugal AND (republica OR partido OR politica))'),
    ("葡萄牙 萨拉查", 'language:por AND subject:(Salazar OR "Estado Novo")'),

    # --- 拉美 ---
    ("拉美 墨西哥政纲", 'language:spa AND subject:(México AND (partido OR programa OR plan))'),
    ("拉美 阿根廷", 'language:spa AND subject:(Argentina AND (partido OR programa)) AND year:[1890 TO 1960]'),
    ("拉美 智利政党", 'language:spa AND subject:(Chile AND (partido OR programa))'),
    ("拉美 古巴", 'language:spa AND subject:(Cuba AND (partido OR programa OR revolucion))'),

    # --- 比利时 ---
    ("比利时 法语", 'language:fre AND subject:(Belgique AND (parti OR programme))'),
    ("比利时 荷语", 'language:dut AND subject:(België AND (partij OR programma))'),

    # --- 瑞典 ---
    ("瑞典 社民", 'language:swe AND subject:(socialdemokrati OR arbetarrörelse OR valprogram)'),
    ("瑞典 政党", 'language:swe AND title:(program OR stadgar OR valmanifest)'),

    # --- 已有但偏少：奥地利/荷兰/西班牙/匈牙利 ---
    ("奥地利 社民党", 'language:ger AND title:(Programm OR Parteitag) AND subject:(Österreich)'),
    ("荷兰 政党", 'language:dut AND title:(program OR beginselen OR statuten)'),
    ("西班牙 政党册", 'language:spa AND title:(programa OR estatutos OR manifiesto) AND year:[1880 TO 1939]'),
    ("匈牙利 政党", 'language:hun AND title:(program OR alapszabály OR kiáltvány)'),
]


def search(q, rows=15):
    params = {"q": q, "fl[]": ["identifier", "title", "year", "language", "imagecount"],
              "rows": str(rows), "output": "json", "sort[]": "downloads desc"}
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    return http.fetch_json(url, timeout=60)


def main():
    for label, q in PROBES:
        full = f"{q} AND {BASE_Q}"
        try:
            d = search(full)
        except Exception as e:
            print(f"\n[{label}] 失败 {type(e).__name__}")
            continue
        resp = d.get("response") or {}
        docs = resp.get("docs", [])
        print(f"\n[{label}] numFound={resp.get('numFound')}")
        for doc in docs[:5]:
            print(f"   {str(doc.get('year')):6s} {str(doc.get('imagecount')):>3}p "
                  f"{str(doc.get('identifier'))[:32]:32s} {str(doc.get('title'))[:44]}")


if __name__ == "__main__":
    main()
