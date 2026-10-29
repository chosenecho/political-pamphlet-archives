"""立场、国别、体裁的词表：**唯一**的登记处。

为什么要有这个模块
    与 `lib/regions.py` 同一类问题，只是更严重。

    立场字段没有词表。60 个取值不是设计出来的，是分八批采集时各自追加的：
    每个 `harvest_*.py` 在自己的 `SEARCHES` / `ORG_RULES` / `RULES` 里直接
    写字面量，`merge_*.py` 再把它抄进条目。扫一遍 scripts/ 有 21 个脚本定义
    或引用立场字面量，`lib/` 下 0 个。后果：

      - `audit_stance.py` 的白名单是手写的，19 个国家（漏中国、瑞士、葡萄牙），
        还留着 4 个从未落地的值（卡洛斯派、土地同盟、天主教民众派、革命派）。
        按它现在跑会报 129 条违规，其中 55 条是瑞士的「选举宣传」——那批是
        `tools/label_swiss_tiff.py` 有意标到较宽类别的，不是错。
      - 瑞士批次单独造出 12 个「XX议题」值，全部只出现在瑞士，共 24 条。
        它们和「社会主义」这类词不在同一逻辑层级，却平铺成同级筛选项。
      - 结果界面上出现 60 个选项，其中 23 个只出现 1 次。

    所以这里做两件事：
      1. 把现有取值登记成词表（**内容不改**，只集中到一处）；
      2. 让写入路径拒绝未登记的新值——新增必须在这里加一行并给出依据。

    词表本身不做语义归并。`stance` 现在同时承担「思潮」「政党」「议题」「用途」
    四件事，拆成多轴是另一件事（见 UI-AUDIT-STANCE.md 的 P1），在那之前先
    把"谁能被写进这个字段"关起来。**先关闸，再拆轴**：顺序反了，拆完的轴会
    按同样的方式再长歪一次。

怎么加一个新值
    在 `STANCE` 里加，并在同一行的注释里写明依据（哪批材料、判据是什么）。
    只加值不加依据的条目会在 `audit_stance.py` 里被标出来。

怎么把一个值退役
    不要直接删——`data/catalog.json` 里还有条目挂着它，删了会让那些条目
    变成未登记值。先批量改数据，再把它从 `STANCE` 移到 `RETIRED`。
"""

#: 全部已登记的政治立场取值。加值时写清依据。
#: 排序无意义（界面按出现频次排），这里按码位排，便于查重。
STANCE = [
    "人民党",              # 奥地利 ÖVP / 美国 People's Party 的通行译名
    "保守派",              # 有明确保守立场、但读不出具体组织
    "保守派防御宣传",       # 瑞士 1919–22 反革命/反通胀的保卫性宣传，无独立组织名
    "保皇派",              # 法国 Gallica 批次
    "公共卫生议题",         # 瑞士公投议题（医院建设）
    "公投议题",            # 瑞士：能读出公投、读不出党派的
    "共产主义",            # 各界共产党通用
    "共和党",              # 美国 Republican Party
    "共和派",              # 爱尔兰共和派 / 法国共和派 / 西班牙共和派
    "共青团",              # 俄国 Komsomol 出版物
    "养老与残障保险议题",   # 瑞士 Rothenberger 倡议
    "反德宣传",            # 比利时一战
    "反战",                # 读得出反战、读不出组织
    "反核",                # 1980 年代西德
    "反独裁",              # 拉美反皮诺切特等
    "右翼史论",            # 西班牙：右翼立场的历史论述，非宣传品
    "右翼论战",            # 法国：右翼论战册
    "君主派",              # 奥地利哈布斯堡
    "和平主义",            # 匈牙利反战
    "国际联盟议题",         # 瑞士国联加入公投
    "基督教社会党",         # 奥地利 CS / 瑞士 CVP
    "女权",                # 法国 Gallica：女权论述
    "妇女参政",            # 英美 suffragist / suffragette 材料
    "宪章运动",            # 英国 Chartist
    "少数民族政治",         # 波兰犹太社群
    "就业议题",            # 瑞士
    "工党与社会主义",       # 英国 Labour Party / ILP 等
    "工团主义",            # 法国 syndicalism
    "工时法议题",          # 瑞士 48 小时工作制公投
    "左翼联盟",            # 法国 Cartel des gauches
    "布尔什维克",          # 俄国，与「共产主义」区分：特指布尔什维克派
    "布朗热主义",          # 法国布朗热运动
    "庇隆主义",            # 阿根廷 Peronism
    "德雷福斯事件",         # 法国，事件性材料
    "战时宣传",            # 战争期官方/半官方宣传
    "政治思想宣传",         # 读得出思想宣传性质、读不出具体思潮
    "无政府主义",          # 各国
    "极右·行动法兰西",      # 法国 Action française，单列因组织即立场
    "民主党",              # 美国 Democratic Party
    "民族主义",            # 各国
    "民族主义右翼",         # 魏玛钢盔团/自由军团等
    "法西斯主义",          # 意大利 PNF
    "白俄·临时政府",        # 俄国流亡政权
    "社会主义",            # 通用
    "社会民主党",          # 奥地利/瑞士/瑞典 SPD 系
    "禁酒议题",            # 瑞士
    "粮食与面包价格议题",   # 瑞士
    "纳粹主义",            # NSDAP
    "维希政权",            # 法国 1940–44
    "联合派",              # 爱尔兰 Unionist（支持英爱合并）
    "自由主义",            # 智利 Partido Liberal 等
    "自由民主党",          # 瑞士 FDP
    "自由议题",            # 瑞士
    "自由贸易派",          # 英国 1903–10 关税改革论战
    "行商法议题",          # 瑞士
    "财产税议题",          # 瑞士
    "费边社会主义",         # 英国 Fabian Society
    "选举制度议题",         # 瑞士比例代表制
    "选举宣传",            # 读得出是竞选材料、读不出党派立场
    "选举权",              # 荷兰/瑞士等普选权运动，与「妇女参政」区分
]

#: 已被脚本引用、但数据里暂无条目的值。
#:
#: 保留它们是为了不打断正在用的规则表：这些是**将来会被写入**的值，登记在案
#: 就说明它经过了一次判断，而不是脚本里随手写的一个字符串。用 `RESERVED`
#: 与 `STANCE` 区分，是为了让审计能问一句"登记了却一直没有条目，是不是规则
#: 根本没命中过"——那通常意味着检索式写错了。
RESERVED = [
    "土地同盟",            # 爱尔兰 Land League，`harvest_ia_gap.py` ORG_RULES 有规则
    "天主教民众派",         # 意大利/奥地利 Partito Popolare，规则表有，尚无命中
    "长枪党",              # 西班牙 Falange，`harvest_ia_gap.py` 有规则
    "卡洛斯派",            # 西班牙 Carlism，仅 `audit_stance.py` 白名单提到
    "革命派",              # 拉美革命派，`harvest_commons_new.py` 检索式提到
    "公民党与中右翼",       # 瑞士 Bürgerpartei，`tools/label_swiss_*.py` 有映射
    "反共宣传",            # 瑞士 1920s 反布尔什维克宣传，`tools/label_swiss_stance.py`
    "天主教",              # 法国 Gallica `catholicisme` 检索路
    "激进派",              # 法国 Parti radical，Gallica `radicalisme` 检索路
    "殖民主义",            # 法国 Gallica `colonialisme` 检索路
    "反议会",              # 法国 antiparlementarisme，Gallica 检索路
]

#: 已退役：保留名字，防止有人以为可以复用。
RETIRED = []

#: 全部合法取值
ALL = STANCE + RESERVED


def is_stance(value):
    """是否为已登记立场。空串是合法状态（未标注），不算未登记。"""
    return value == "" or value in ALL


def normalize(value):
    """把任意写法收敛成词表里的值；未登记的原样返回，由调用方决定报错还是放行。

    与 `regions.to_zh()` 同一策略：**不兜底、不改写**。静默把一个没见过的值
    映射到某个"看起来差不多"的已有值，正是这个词表以前出问题的方式。
    """
    return ("" if value is None else str(value)).strip()


def unknown(values):
    """从一批取值里挑出未登记的，按出现次数降序返回 [(值, 次数)]。"""
    from collections import Counter

    c = Counter(v for v in (normalize(x) for x in values) if v and v not in ALL)
    return c.most_common()


def validate(records):
    """校验一批目录记录的 stance 字段。

    返回问题列表；空列表表示通过。策略是**只拦新增，不追溯历史**：

      - 未登记的值：报错。这是本模块存在的理由。
      - 非 str 类型：报错。
      - 空值：合法（171/540 未标注是已声明的缺口，不是错误）。
    """
    problems = []
    for i, r in enumerate(records):
        raw = r.get("stance")
        if raw is None or isinstance(raw, str):
            v = normalize(raw)
        else:
            problems.append(f"[{i}] stance 类型错误 {type(raw).__name__}")
            continue
        if v and v not in ALL:
            problems.append(
                f"[{i}] stance 未登记：{v!r}（{(r.get('title') or '?')[:32]}）"
                f" —— 在 scripts/lib/vocab.py 的 STANCE 里登记并写明依据")
    return problems


def stats(records):
    """词表规模与使用情况，供审计脚本打印。"""
    used = {}
    for r in records:
        v = normalize(r.get("stance"))
        if v:
            used[v] = used.get(v, 0) + 1
    return {
        "registered": len(STANCE),
        "reserved": len(RESERVED),
        "used": len(used),
        "never_used": [v for v in STANCE if v not in used],
        "reserved_hit": [v for v in RESERVED if v in used],
        "unmarked": sum(1 for r in records if not normalize(r.get("stance"))),
        "total": len(records),
    }
