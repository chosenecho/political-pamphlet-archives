"""逐条修正海报批次的立场标注。

采集时按 Commons 分类预设了立场，但分类与材料实际立场常常不符：
  - `Political posters of Germany` 里既有 SPD 反纳粹海报，也有
    Stahlhelm（钢盔团，右翼退伍军人组织）与民族主义宣传
  - `Political posters of the United Kingdom` 里有大量 1890s 无政府主义
    集会海报与自由贸易宣传，不是工党材料
  - `Political posters of France` 里 1940–1942 是维希政权宣传，
    与"共和派"正相反

这里按标题逐条判定。判据优先用标题里能直接读出的组织名与口号，
读不出的标"未标注"，不硬套分类默认值。
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
META = os.path.join(BASE, "images", "posters-new", "metadata.json")

#: 标题关键词 -> (国家, 立场)。按顺序匹配，先命中先用。
#: 每条的判断依据写在注释里，便于复核。
RULES = [
    # --- 德国 ---
    (r"stahlhelm", "德国", "民族主义右翼"),          # 钢盔团：右翼退伍军人组织
    (r"freischar|freikorps", "德国", "民族主义右翼"),  # 自由军团
    (r"vaterlands-?partei", "德国", "民族主义右翼"),   # 祖国党
    (r"schleswig ist deutsch", "德国", "民族主义右翼"),  # 石勒苏益格归属宣传
    (r"hände weg vom ruhrgebiet", "德国", "民族主义右翼"),  # 鲁尔区民族主义
    (r"bei deutschland dauern der wohlstand", "德国", "民族主义右翼"),  # 德波对立宣传
    (r"gelbe fleck|wider den undeutschen", "德国", "纳粹主义"),  # 纳粹反犹书页
    (r"das dritte reich|anti-ns|eisernen front|freiheit und arbeit", "德国", "社会主义"),  # SPD 反纳粹
    (r"frauentag", "德国", "妇女参政"),               # 妇女节争取选举权
    (r"bücherverbrennung|buecherverbrennung", "德国", "社会主义"),  # 反焚书传单
    (r"erwürgt nicht die junge freiheit", "德国", "社会主义"),
    (r"eure schuld", "德国", "反战"),                 # 1945 战争罪责
    (r"brennstaebe", "德国", "反核"),                 # 1983 反核
    (r"an-das-weltgewissen", "德国", "反战"),
    (r"deutsche volkspartei", "德国", "民族主义右翼"),

    # --- 奥地利 ---
    (r"övp|keine klassen", "奥地利", "人民党"),
    (r"nie mehr februar|keine neue wehrmacht", "奥地利", "社会民主党"),
    (r"kehrt aus|wählt sozialdemokratisch|sozialdemokratisch", "奥地利", "社会民主党"),
    (r"die dort sind an unserem elend schuld", "奥地利", "社会民主党"),
    (r"kriegsanleihe|kaiser karl", "奥地利", "君主派"),
    (r"volksabstimmung|plebiscit", "奥地利", "民族主义"),  # 公投宣传

    # --- 法国 ---
    (r"travail-famille-patrie|révolution nationale", "法国", "维希政权"),
    (r"anticommuniste|le communisme c'est", "法国", "保守派"),
    (r"patrie française", "法国", "民族主义"),
    (r"cartel-vie-chère", "法国", "左翼联盟"),
    (r"action française", "法国", "极右·行动法兰西"),
    (r"election|électorale|élections", "法国", "选举宣传"),
    (r"dernier mot", "法国", "共和派"),

    # --- 英国 ---
    (r"anarch", "英国", "无政府主义"),                # 1890s 无政府主义集会海报
    (r"bludgeon starving workers", "英国", "无政府主义"),
    (r"chartist", "英国", "宪章运动"),
    (r"free trader|free trade|tariff|fair foreign competition|"
     r"british workman|british factory|radical", "英国", "自由贸易派"),
    (r"beveridge", "英国", "工党与社会主义"),
    (r"each for all and all for each", "英国", "社会主义"),
    (r"question of control", "英国", "社会主义"),

    # --- 荷兰 ---
    (r"kiesrecht", "荷兰", "选举权"),                 # 普选权宣传
    (r"sdap|socialist", "荷兰", "社会主义"),
    (r"jeugd bezint", "荷兰", "社会主义"),
    (r"volksdagblad", "荷兰", "社会主义"),
    (r"groote nationale betooging", "荷兰", "选举权"),
    (r"laat mij binnen", "荷兰", "选举权"),

    # --- 比利时 / 瑞典 ---
    (r"pour le socialisme", "比利时", "社会主义"),
    (r"vi bygger landet", "瑞典", "社会民主党"),

    # --- 俄国 / 苏联 ---
    (r"записался|добровольцем", "俄国", "共产主义"),   # 摩尔「你报名了吗」
    (r"capitalist pyramid", "俄国", "社会主义"),
    (r"workers' block|general elections", "苏联", "共产主义"),

    # --- 意大利 ---
    (r"corpo truppe volontarie|ordinamento corporativo", "意大利", "法西斯主义"),

    # --- 美国 ---
    (r"populist", "美国", "人民党"),
    (r"socialist", "美国", "社会主义"),
    (r"democratic", "美国", "民主党"),
    (r"republican", "美国", "共和党"),
    (r"i want you|fdr", "美国", "战时宣传"),
    (r"stevenson", "美国", "民主党"),
    (r"available candidate|union soup", "美国", "选举宣传"),

    # --- 日本 ---
    (r"general election|election posters", "日本", "选举宣传"),

    # --- 爱尔兰 ---
    (r"cumann na ngaedheal", "爱尔兰", "联合派"),      # 支持英爱条约的执政党
    (r"easter lily", "爱尔兰", "共和派"),             # 复活节百合：共和派纪念

    # --- 匈牙利 ---
    (r"szociáldemokrata", "匈牙利", "社会主义"),

    # --- 拉美 ---
    (r"alfonsín|radical", "拉美", "选举宣传"),
    (r"cámpora|peronista|lealtad|libertad y amnistia", "拉美", "庇隆主义"),
    (r"altamirano|unidad popular|allende", "拉美", "社会主义"),
    (r"empadronamiento|abdualjad", "拉美", "选举宣传"),

    # --- 波兰 ---
    (r"jewish community", "波兰", "少数民族政治"),
    (r"pracujemy", "波兰", "社会主义"),
]


def main():
    items = json.load(open(META, encoding="utf-8"))

    # 国别以采集时的分类为准，规则只改立场。
    # 上一版让规则同时改国别，`democratic`/`general election` 这类英文词
    # 跨语言误匹配，把阿塞拜疆海报挂到法国、1904socialist 挂到荷兰。
    orig_country = {it["no"]: it["country"] for it in items}
    changed = 0
    unknown = []

    for it in items:
        t = it["title"]
        hit = None
        for pat, country, stance in RULES:
            if re.search(pat, t, re.I):
                hit = stance
                break
        if it["country"] != orig_country[it["no"]]:
            it["country"] = orig_country[it["no"]]

        if hit:
            if it["stance"] != hit:
                print(f"  {it['no']:03d} {it['stance']:12s} -> {hit:12s} {t[:50]}")
                it["stance"] = hit
                changed += 1
        else:
            if it["stance"]:
                print(f"  {it['no']:03d} {it['stance']:12s} -> （未标注）{t[:50]}")
                it["stance"] = ""
                changed += 1
            unknown.append(t)

    json.dump(items, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n修正 {changed} 条；无法判定 {len(unknown)} 条")
    for t in unknown:
        print(f"   未标：{t[:66]}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
