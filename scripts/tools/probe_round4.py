"""第四轮探针：换角度找捷克 / 比利时 / 日本 / 葡萄牙 / 瑞典的小册子。

前三轮针对这五国用的是「母语种 + 政党名/体裁词」，命中多为期刊与协会章程。
本轮换四个角度：
  1. 用英文/法文/德文的国别名 + 主题词（这些国别的材料常被他国图书馆编目）
  2. 具体政党的外文名（如 Czech National Socialist、Belgian Labour Party）
  3. IA 馆藏集合（collection:）里按国别筛
  4. 用「政治宣传」的外文对应词（propaganda / propagande / Propaganda）

同时补探已有国别里偏少的：奥地利 1、荷兰 1、匈牙利 2、意大利 3、西班牙 4。
"""

import os
import sys
import urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import http

BASE_Q = "imagecount:[8 TO 80] AND year:[1840 TO 1970] AND mediatype:texts"

PROBES = [
    # --- 捷克：用英文/德文编目名 ---
    ("捷克 英编目", 'subject:(Czechoslovakia AND (politics OR political OR party))'),
    ("捷克 德编目", 'subject:(Tschechoslowakei AND (Politik OR Partei))'),
    ("捷克 政党英文名", 'subject:("Czech National Socialist" OR "Czechoslovak Social Democratic" '
                        'OR "Agrarian Party" OR "Communist Party of Czechoslovakia")'),
    ("捷克 Beneš/Masaryk", 'creator:("Beneš" OR "Benes" OR "Masaryk") AND NOT title:(memoirs OR speeches)'),

    # --- 比利时：英文/法文编目 ---
    ("比利时 英编目", 'subject:(Belgium AND (politics OR socialism OR party OR election))'),
    ("比利时 政党名", 'subject:("Parti Ouvrier Belge" OR "Belgian Labour Party" OR '
                      '"Parti Socialiste Belge" OR "Christelijke Volkspartij")'),
    ("比利时 天主教党", 'subject:("Parti Catholique" OR "Katholieke Partij") AND language:(fre OR dut)'),

    # --- 日本：英文编目 ---
    ("日本 英编目", 'subject:(Japan AND (politics OR socialism OR "political parties")) '
                    'AND language:eng'),
    ("日本 政党史英文", 'title:(Japan AND (socialist OR proletarian OR suffrage OR "party"))'),
    ("日本 战前", 'subject:("Japan" AND (Taisho OR Showa OR "prewar")) AND language:eng'),

    # --- 葡萄牙：英文/法文编目 ---
    ("葡萄牙 英编目", 'subject:(Portugal AND (republic OR politics OR party OR socialism))'),
    ("葡萄牙 共和国史", 'title:(Portugal AND (republica OR republic) AND (propaganda OR program))'),
    ("葡萄牙 第一共和国", 'subject:("Portuguese Republic" OR "Primeira República")'),

    # --- 瑞典：英文编目 ---
    ("瑞典 英编目", 'subject:(Sweden AND (socialism OR politics OR "social democratic"))'),
    ("瑞典 政党名", 'subject:("Sveriges socialdemokratiska arbetareparti" OR SAP OR "Högern")'),
    ("瑞典 英文小册", 'title:(Sweden AND (labour OR labor OR socialist OR democracy))'),

    # --- 已有偏少：奥地利/荷兰/匈牙利/意大利/西班牙 ---
    ("奥地利 英编目", 'subject:(Austria AND (socialism OR "Christian Social" OR politics)) '
                      'AND year:[1880 TO 1938]'),
    ("奥地利 1918-1934", 'subject:(Austria AND (Republik OR Ständestaat)) AND language:ger'),
    ("荷兰 英编目", 'subject:(Netherlands AND (socialism OR "social democratic" OR politics))'),
    ("荷兰 SDAP", 'subject:("Sociaal-Democratische Arbeiderspartij" OR SDAP OR NASB)'),
    ("匈牙利 英编目", 'subject:(Hungary AND (socialism OR politics OR "party"))'),
    ("意大利 英编目", 'subject:(Italy AND (fascism OR socialism OR "popular party")) '
                      'AND year:[1900 TO 1945]'),
    ("西班牙 英编目", 'subject:(Spain AND (anarchism OR socialism OR falange)) AND year:[1900 TO 1939]'),
]


def search(q, rows=12):
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
        for doc in docs[:6]:
            print(f"   {str(doc.get('year')):6s} {str(doc.get('imagecount')):>3}p "
                  f"{str(doc.get('language'))[:8]:8s} {str(doc.get('identifier'))[:30]:30s} "
                  f"{str(doc.get('title'))[:46]}")


if __name__ == "__main__":
    main()
