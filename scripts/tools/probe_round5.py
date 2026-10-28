"""第五轮探针：继续用「西文编目」思路挖 葡萄牙 / 瑞典 / 日本 及偏少国别。

第四轮证明：这五国的材料在 IA 上以英/法/德文编目为主，母语种检索漏掉很多。
本轮沿此思路深挖，并补探已有国别里数量偏少的（奥地利1、荷兰1、匈牙利2）。
"""

import os
import sys
import urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from lib import http

BASE_Q = "imagecount:[8 TO 90] AND year:[1840 TO 1980] AND mediatype:texts"

PROBES = [
    # --- 葡萄牙：共和国宣传、政党 ---
    ("葡萄牙 共和宣传", 'title:(Portugal AND (republic OR propaganda OR manifesto OR programme)) '
                        'AND language:(eng OR fre OR por)'),
    ("葡萄牙 殖民地", 'subject:("Portuguese colonies" OR "Portugal -- Colonies")'),
    ("葡萄牙 萨拉查英文", 'subject:("Salazar" OR "Estado Novo") AND language:eng'),
    ("葡萄牙 政党册 en", 'subject:(Portugal AND (party OR parties OR socialism OR syndicalism))'),

    # --- 瑞典：工运与社民 ---
    ("瑞典 工运英文", 'subject:(Sweden AND (labour OR labor OR trade union OR socialist))'),
    ("瑞典 社民英文", 'title:(Sweden AND (social democratic OR labour movement OR working class))'),
    ("瑞典 合作社", 'subject:(Sweden AND (cooperative OR housing OR welfare)) AND language:eng'),

    # --- 日本：政论小册 ---
    ("日本 政论英文", 'title:(Japan AND (constitution OR parliament OR suffrage OR liberal))'),
    ("日本 劳工英文", 'subject:(Japan AND (labour OR labor OR peasant OR tenant))'),
    ("日本 满洲宣传", 'title:(Manchuria OR Manchukuo) AND language:eng'),

    # --- 奥地利补量 ---
    ("奥地利 社会党英文", 'subject:("Austrian Social Democracy" OR "Social Democratic Workers Party") '
                          'AND language:eng'),
    ("奥地利 天主教社", 'subject:(Austria AND ("Christian Social" OR "Catholic" ) ) '
                        'AND year:[1880 TO 1938]'),

    # --- 荷兰补量 ---
    ("荷兰 工运英文", 'subject:(Netherlands AND (labour OR socialist OR suffrage)) AND language:eng'),
    ("荷兰 殖民", 'subject:("Dutch East Indies" AND (politics OR nationalism OR party))'),

    # --- 匈牙利补量 ---
    ("匈牙利 1919 苏维埃", 'subject:(Hungary AND ("Soviet Republic" OR Kun OR communist))'),
    ("匈牙利 民族问题", 'title:(Hungary AND (nationality OR minority OR Magyar))'),

    # --- 意大利补量 ---
    ("意大利 天主教人民党", 'subject:("Partito Popolare" OR "Don Sturzo" OR "Catholic Action")'),
    ("意大利 社会主义", 'subject:(Italy AND (socialist OR syndicalist OR anarchist)) '
                        'AND year:[1890 TO 1925]'),

    # --- 西班牙补量 ---
    ("西班牙 无政府", 'subject:(Spain AND (anarchist OR CNT OR syndicalist)) AND language:eng'),
    ("西班牙 卡洛斯", 'subject:(Spain AND (carlist OR traditionalist OR monarchist))'),

    # --- 爱尔兰补量 ---
    ("爱尔兰 复活节起义", 'subject:(Ireland AND ("Easter Rising" OR "Sinn Fein" OR "Irish Republic"))'),

    # --- 印度补量 ---
    ("印度 国大党英文", 'subject:("Indian National Congress" OR "Congress Party") AND language:eng'),
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
                  f"{str(doc.get('language'))[:8]:8s} {str(doc.get('identifier'))[:32]:32s} "
                  f"{str(doc.get('title'))[:44]}")


if __name__ == "__main__":
    main()
