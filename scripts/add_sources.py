"""把新核实的专藏追加到 data/sources.json（幂等，按 slug 去重）。"""

import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(BASE, "data", "sources.json")

NEW = [
    {"slug": "social-history-portal", "title": "Social History Portal (IALHI 聚合)",
     "region": "欧洲", "kind": "聚合检索",
     "url": "https://www.socialhistoryportal.org/",
     "note": "国际劳工史机构协会（IALHI）门户，跨馆检索社会运动与工运档案、100 余种期刊目次"},
    {"slug": "rgaspi-comintern", "title": "RGASPI 共产国际档案（经 LoC 指南）",
     "region": "俄/美", "kind": "档案馆",
     "url": "https://guides.loc.gov/comintern-archives/",
     "note": "莫斯科 RGASPI 藏 1919–1943 共产国际档案约 2000 万页，各国共产党文献；LoC 提供 INCOMKA 检索指南与缩微"},
    {"slug": "ohara-institute", "title": "法政大学大原社会問題研究所",
     "region": "日本", "kind": "档案馆",
     "url": "https://oisr-org.ws.hosei.ac.jp/",
     "note": "日本社会运动史核心机构，藏有大量政党、工会的ビラ（传单）与パンフレット"},
    {"slug": "osa-archivum", "title": "Blinken OSA Archivum",
     "region": "匈牙利", "kind": "档案馆",
     "url": "https://archivum.org/",
     "note": "冷战、自由欧洲电台、samizdat（地下出版物）与人权材料，1956 匈牙利革命专题"},
    {"slug": "memoria-chilena-panfletos", "title": "Memoria Chilena · Panfletos 1973–1988",
     "region": "智利", "kind": "数字馆藏(免费)",
     "url": "https://www.memoriachilena.gob.cl/602/w3-article-3641.html",
     "note": "军事独裁时期政党活动被禁，传单成为主要宣传形式；该专题收录此期 panfletos"},
    {"slug": "bcn-chile-panfletos", "title": "智利国会图书馆 · Estantería Digital 传单集",
     "region": "智利", "kind": "数字馆藏(免费)",
     "url": "https://www.bcn.cl/estanteriadigital/resultados?terminos=portada_sitio&coleccion=panfletos",
     "note": "含 1969 年政治传单等竞选材料"},
    {"slug": "feltrinelli", "title": "Fondazione Giangiacomo Feltrinelli",
     "region": "意大利", "kind": "档案馆",
     "url": "https://fondazionefeltrinelli.it/",
     "note": "意大利政治社会运动档案与「Archivi del presente」当代运动文献采集项目"},
    {"slug": "fpabloiglesias", "title": "Fundación Pablo Iglesias",
     "region": "西班牙", "kind": "党档案馆",
     "url": "https://fpabloiglesias.es/archivo-y-biblioteca/",
     "note": "PSOE、UGT、JSE 及主要领导人（Pablo Iglesias、Largo Caballero 等）的历史档案与书刊"},
    {"slug": "torre-do-tombo-pide", "title": "Arquivo Nacional Torre do Tombo · PIDE/DGS 档案",
     "region": "葡萄牙", "kind": "档案馆",
     "url": "https://antt.dglab.gov.pt/",
     "note": "政治警察档案，内含大量被查扣的地下传单与政党印刷品"},
    {"slug": "vga-wien", "title": "Verein für Geschichte der ArbeiterInnenbewegung",
     "region": "奥地利", "kind": "档案馆",
     "url": "https://www.vga.at/",
     "note": "经「zeithistorischer politischer Archive」平台可在线检索 6000 余张政治海报"},
    {"slug": "onb-plakate", "title": "Österreichische Nationalbibliothek · 海报与传单",
     "region": "奥地利", "kind": "特藏",
     "url": "https://www.onb.ac.at/sammlungen/bildarchiv-und-grafiksammlung/bestandsuebersicht/plakate-flugblaetter-exlibris",
     "note": "海报收藏约 10 万张、跨三个世纪，另有 Flugblätter（传单）专藏"},
    {"slug": "aan-warszawa", "title": "Archiwum Akt Nowych（波兰新档案）",
     "region": "波兰", "kind": "档案馆",
     "url": "https://aan.gov.pl/",
     "note": "1919 年设立的国家central档案馆，藏 19–20 世纪政党与政治组织档案"},
    {"slug": "arab-stockholm", "title": "Arbetarrörelsens arkiv och bibliotek",
     "region": "瑞典", "kind": "档案馆",
     "url": "https://arbark.se/sv/",
     "note": "瑞典工人运动档案与图书馆，社民党、工会的竞选与宣传材料"},
    {"slug": "loc-newdelhi-pamphlets", "title": "LoC 新德里办事处政治小册子集",
     "region": "印度/美", "kind": "特藏",
     "url": "https://www.loc.gov/item/2009345307",
     "note": "美国国会图书馆新德里办公室收集整理的南亚政治小册子（1959–2009，含孟加拉语、印地语等）"},
]

data = json.load(open(P, encoding="utf-8"))
have = {s["slug"] for s in data["sources"]}
added = 0
for s in NEW:
    if s["slug"] not in have:
        data["sources"].append(s)
        added += 1

json.dump(data, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"新增 {added} 条，现有 {len(data['sources'])} 个专藏")
