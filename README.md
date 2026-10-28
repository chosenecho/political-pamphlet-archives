# 歷史宣傳材料檔案目录 · Political Pamphlet Archives

十九至二十世纪政治组织、政治家、政治派系散发的宣传小册子、传单、竞选材料、政治海报的**馆藏索引与可复现抓取工具**。

这个仓库解决的问题很具体：这类材料散落在各国国家图书馆、党的档案馆、社会运动专门机构里，编目语种不同、征引方式各异，找起来比一般出版物麻烦得多。仓库把 40 个已有数字化或可检索的专藏整理成一张表，并附上能跑的采集脚本。

> **声明**　本仓库的内容由 AI 辅助生成与整理，**仅供学术研究与交流**；不保证准确、完整，也不对使用后果负责。所收录材料为历史文献，**收录不等于认同**。若权利人或其他方面认为内容不当，提出后**立即下架**。完整条款见 [DISCLAIMER.md](DISCLAIMER.md)。

## 包含什么

| 内容 | 说明 |
|---|---|
| [`data/catalog.json`](data/catalog.json) | **权威条目目录**：347 条（146 本小册子 + 201 件单页），统一 schema，含标题、译名、国别、年份、页数、立场、来源归属 |
| [`data/sources.json`](data/sources.json) | **40 个专藏**的清单：名称、国别、类型、入口 URL、规模注记 |
| [`data/index.csv`](data/index.csv) | 同一份专藏清单的表格版，带抓取状态，Excel 可直接打开 |
| [`data/manifest.json`](data/manifest.json) | 专藏的抓取记录：HTTP 状态、字节数、正文字符数、失败原因 |
| [`metadata/`](metadata/) | 逐条抓取日志（中国 1920–1949、西方 1815–1948），记录每个下载项的 IIIF 地址与页数 |
| [`notes/`](notes/) | 已抓取的收藏说明页正文纯文本，可直接 grep |
| [`docs/index.html`](docs/index.html) | **目录与阅读器**：多维筛选、年代直方图、网格/列表双视图、URL 记忆、单页·双页·连续三种阅读模式；**仅本地打开**，线上不发布（见「公开站点为何留白」） |
| [`docs/COLLECTIONS.md`](docs/COLLECTIONS.md) | 40 个专藏的可点击清单与抓取状态 |
| [`docs/FINDING-AIDS.md`](docs/FINDING-AIDS.md) | **检索手册**：14 种语言的体裁检索词、按出版社反查、各类型馆藏查法 |
| [`scripts/`](scripts/) | 采集与构建脚本，见下 |

`docs/index.html` 由 `scripts/templates/catalog.html` 加 `data/catalog.json` 生成，不要手改；改了源数据或模板要重跑构建，CI 会校验两者是否一致，并跑一遍页面交互验收。

### 目录页的设计取舍

页面上有几处不是装饰，而是被数据逼出来的决定：

- **图像缺席时，封面不是错误态。** `images/` 不入库，Pages 上 347 张图全部 404。所以卡片在图片加载失败时渲染一块**排版封面**——小册子照扉页排（年份、题名、原名、国别页数），单页照招贴排（年份色条、大字号题名）。有图时它被图盖住，没有时它就是封面本身，目录在任何情况下都读得下去。
- **封面不裁切。** 实测封面宽高比从 0.38 到 2.08，单页海报多是横版 1.3–1.5。原来的 `aspect-ratio:2/3 + object-fit:cover` 会把横版海报裁掉三分之一，现在改成衬纸 `contain`。
- **主筛选维度是国别与年代，不是立场。** `stance` 只有 172/347 有值，`source` 只有 329/347。把立场做成主筛选器会让人以为库里只有这些立场；页面上因此显式标注了「另 N 条未标注」，不把缺口伪装成不存在。
- **年代用可点直方图。** 跨度 1830–1993，76 个年份做成下拉没人愿意滚；直方图一眼看到 1910s、1930s、1940s 三个峰，点击或 Shift 连选收窄。
- **列表视图是给研究用的。** 网格给浏览，列表给核对：一屏 20 余条，题名、原名、国别、体裁、页数、立场对齐成列，命中词高亮。

### 看得到图，还是看不到图

**在本机**：跑过采集脚本、`images/` 有了内容之后，直接双击 `docs/index.html` 打开即可，封面与内页都会正常显示，不需要起服务器——页面用相对路径 `../images/` 定位，`file://` 下能解析到。

**在公开站点上**：不发布任何内容。站点只剩一个空白页，详见下节「公开站点为何留白」。本地打开的体验不受影响。

要让页面指向别处的图（例如把图放在另一块盘），加查询参数：

```
docs/index.html?assets=/path/to/images/
```

阅读器侧栏会显示每页原图的实际像素尺寸——部分来源的分辨率本身就很低（最窄的一本只有 330×584），放大到顶就是原图，不是加载失败。

### 公开站点为何留白

公开站点不显示任何内容，**不是故障，是刻意为之**：为规避法律风险，连简介也不放。

- 发布源是独立的 `gh-pages` 分支，只含一个无标题、无正文的空白 `index.html`、`.nojekyll` 与 `Disallow: /` 的 `robots.txt`。
- 构建产物 `docs/index.html` 仍照常生成在 `main` 上，供本地打开；二者已解耦，所以 `build_catalog.py` 重跑**不会**把目录重新推上线。
- 恢复公开浏览：把 Pages 发布源改回 `main` / `/docs` 即可，无需改代码。

判断站点是否正常，看根路径是否为空白页即可；不要以「页面没有目录」为由去「修复」它。

## 图像不随仓库分发

已抓取的实体材料：**146 本多页小册子（4009 页）** + **201 件单页传单／海报**，覆盖 21 国。都没有放进仓库，原因有二：体积，以及**扫描件的版权属于各原藏机构与捐赠者**，公开再分发不合适。

`images/` 因此被 .gitignore 排除。条目元数据完整保留在 `data/catalog.json`，所以任何人都能按下面的步骤把图抓回来。目录页在图片缺失时会显示占位块，不会破损。

```bash
pip install -r requirements.txt

python scripts/harvest_mh2.py            # 抗战平台：按主题搜索并下载封面
python scripts/harvest_pages.py          # 抗战平台：补抓内页（短篇全本，长篇首尾）
python scripts/harvest_ia.py             # Internet Archive
python scripts/harvest_ia_gap.py --dry   # IA 缺口国候选（先看清单与国别判定依据）
python scripts/harvest_ia_gap.py         # IA 缺口国下载
python scripts/merge_ia_gap.py           # 并入 catalog（--dry 预演）
python scripts/harvest_commons_new.py    # Commons 历史海报（主题搜索 + 年代过滤）
python scripts/harvest_posters.py        # Commons 海报批量（读候选清单，按国别配额）
python scripts/merge_posters.py --dry    # 并入 catalog（--dry 预演）
python scripts/harvest_gallica.py        # Gallica（需 Playwright 浏览器会话）

python scripts/validate_catalog.py       # 校验 data/catalog.json
python scripts/build_catalog.py          # 由模板与目录生成 docs/index.html
python scripts/build_index.py            # 重建 index.csv 与 COLLECTIONS.md
python scripts/test_catalog_ui.py        # 目录页与阅读器的端到端验收（需 playwright）
python scripts/shot_ui.py --dark         # 截图到 images/_ui/，目视检查
python scripts/organize_images.py        # 按议题把图分到 15 类（先加 --dry 看结果）
python scripts/build_category_sheets.py  # 每类一张缩略总览
```

### 脚本目录结构

```
scripts/
  templates/  目录页模板（catalog.html），与数据分离，占位符替换
  lib/        公共层：paths（仓库路径）、index（目录读写与校验）、http（统一 UA 与重试）、text
  *.py        生产线：harvest_* 采集 → merge_* 并入 → build_* 构建产物
  tools/      接口探针、布局体检、缺图验收等一次性工具，不属于发布链路
  archive/    已被取代的旧脚本（含退役的 build_gallery.py），保留备查
```

采集脚本统一从 `lib.http.fetch` 取数据，UA 与重试策略只有一处；早期各脚本里复制了十几份的 `safe()` / `fetch()` 已收拢。

## 采集方式说明

各站点对自动化访问的态度差别很大，脚本里的处理对应这些差异：

- **抗日战争与近代中日关系文献数据平台**：纯前端渲染，普通抓取拿不到内容。用 Playwright 监听 XHR 找出后台接口 `backend-prod/esBook/findByPage`，直接 POST 检索，再从返回的 `imageUrl` 拼 IIIF 地址（`/full/1000,/0/default.jpg`；`/full/pct:100/0/default.jpg` 取全幅）。按 `publishTime` 过滤，只留 1949 年前原版——不加这一步，检索结果里绝大多数是 1980 年代的资料汇编。
- **Wikimedia Commons**：必须使用符合其[用户代理政策](https://meta.wikimedia.org/wiki/User-Agent_policy)的 UA，否则缩略图服务会持续返回 429。用在 `lib/http.py` 里的 `ToolName/1.0 (URL; mail)` 形式。抓取间隔不要低于 1 秒。分类不宜按目录批量抓——`Political posters of Poland` 里是当代抗议照片，`Political posters of Japan` 里混着街景。`harvest_commons_new.py` 因此改用主题搜索 + 年代过滤 + 分辨率门槛，并按主题去重（同一张海报常有多个版本上传）。原图动辄 7000×12000，`postprocess_commons_new.py` 统一压到长边 2000px 再入库。

  Commons 的 `extmetadata` 日期字段**不能直接当作品年份**：它常常是上传日期或馆藏编目日期。实测 `Elections législatives du 22 septembre 1889` 被标成 1943（BnF 编目年份），`Capitalist pyramid 1900` 被标成 1901。`fix_poster_year.py` 因此逐条比对标题里能读出的年份，凡不一致的都以标题为准并留存判断依据；标题年份属于引用历史事件的（如 1949 年奥地利海报《Nie mehr Februar 1934》）则登记为已验证无误，避免每次重跑重复告警。

  立场也不能直接套分类名。`Political posters of Germany` 里既有社民党反纳粹海报、也有钢盔团与自由军团的民族主义右翼宣传，还有纳粹反犹书页；`Political posters of the United Kingdom` 里大半是 1890 年代无政府主义集会海报与自由贸易宣传，不是工党材料；`Political posters of France` 里 1940–1942 是维希政权宣传。`fix_poster_stance.py` 按标题里能读出的组织名、口号、人名逐条判定，读不出的标「未标注」而不硬套分类默认值。
- **Internet Archive**：元数据字段齐全，是补国别缺口最省事的源，但**国别不能从检索式推**。`harvest_ia_gap.py` 因此把判定收成一条有证据的链：出版者是政党/工会/宣传机构本身时按该组织的政治出身定（与目录既有口径一致——1848 年伦敦印的《共产党宣言》归德国）；其次看作者机构；再次看出版地；主题词单独命中而无出版地佐证的一律丢弃。三类反例都是实测踩出来的：检索式写"奥地利"返回的全是 Berlin / Jena / Breslau 的德国书；`home rule` 把纽约、俄勒冈、加州的市政自治全捞进来；悉尼的 Fabian Society of NSW 与伦敦费边社同名。此外标题恰为 `Fabian tract(s)` 的是年度装订合订本（`volume 1959-60`），须排除，只收有独立篇名的单册。
- **Internet Archive 的批量下载会被限流，且可能整站不可达**。页图走 `download/{id}/page/nN_w1000.jpg`，每本 8–64 页，连续抓十几本后连接能建立但不返回数据。`harvest_resume.py` 为此做了三件事：已存在的页图跳过（断点续传）、连续失败按 2/5/10/20/40/60/90 秒指数退避、连续失败 6 次整体熔断并保留现场。2026-10 那次 `archive.org` 全部端点超时约一小时，同期 Commons 与抗战平台正常，属对方站点故障而非本地网络。
- **Gallica / Hoover / 西班牙 PARES**：Cloudflare 挑战页，本轮未突破。Gallica 的 SRU 与 IIIF 接口对脚本请求返回 403。

## 已核实的 40 个专藏（节选）

完整表见 [`docs/COLLECTIONS.md`](docs/COLLECTIONS.md)。跨地区的几组：

**综合与聚合入口**

| 专藏 | 地区 | 规模 |
|---|---|---|
| [Social History Portal (IALHI 聚合)](https://www.socialhistoryportal.org/) | 欧洲 | 国际劳工史机构协会（IALHI）门户，跨馆检索社会运动与工运档案、100 余种期刊目次 |
| [JSTOR · 19th Century British Pamphlets](https://about.jstor.org/products/journals-and-primary-sources/licensed-collections/19th-century-british-pamphlets/) | 英国 | 2.6 万册 / 逾 100 万页，7 所英国大学馆藏合并 |

**党档案馆（往往比国家馆更全）**

| 专藏 | 地区 | 规模 |
|---|---|---|
| [Friedrich-Ebert-Stiftung · Archiv der sozialen Demokratie](https://www.fes.de/archiv-der-sozialen-demokratie) | 德国 | 社会民主党档案馆；提供馆藏总览、图书馆目录与数字化来源三个检索入口 |
| [Konrad-Adenauer-Stiftung · ACDP 档案馆与图书馆](https://www.kas.de/de/archiv-und-bibliothek) | 德国 | 1900 余个档案群、逾 19 架公里档案；联邦议院 CDU/CSU 党团的传单与新闻稿可全文检索 |
| [Fundación Pablo Iglesias](https://fpabloiglesias.es/archivo-y-biblioteca/) | 西班牙 | PSOE、UGT、JSE 及主要领导人（Pablo Iglesias、Largo Caballero 等）的历史档案与书刊 |
| [People's History Museum · Labour History Archive & Study Centre](https://phm.org.uk/collection/labour-history-archive-study-centre/) | 英国 | 工党与英国共产党的完整全宗，另有工人阶级组织档案与 9.5 万余张照片 |

**社会运动与冷战专门机构**

| 专藏 | 地区 | 规模 |
|---|---|---|
| [IISH Amsterdam · Collections](https://iisg.amsterdam/en/collections) | 荷兰 | — |
| [Schweizerisches Sozialarchiv](https://www.sozialarchiv.ch/) | 瑞士 | 约 1000 个档案群；文献部藏有小册子、传单与新闻剪报 |
| [Blinken OSA Archivum](https://archivum.org/) | 匈牙利 | 冷战、自由欧洲电台、samizdat（地下出版物）与人权材料，1956 匈牙利革命专题 |
| [Verein für Geschichte der ArbeiterInnenbewegung](https://www.vga.at/) | 奥地利 | 经「zeithistorischer politischer Archive」平台可在线检索 6000 余张政治海报 |

**亚洲与拉美**

| 专藏 | 地区 | 规模 |
|---|---|---|
| [抗日战争与近代中日关系文献数据平台](https://www.modernhistory.org.cn/) | 中国 | 含红色文献专题库、中共党史/组织史专题库 |
| [法政大学大原社会問題研究所](https://oisr-org.ws.hosei.ac.jp/) | 日本 | 日本社会运动史核心机构，藏有大量政党、工会的ビラ（传单）与パンフレット |
| [LoC 新德里办事处政治小册子集](https://www.loc.gov/item/2009345307) | 印度/美 | 美国国会图书馆新德里办公室收集整理的南亚政治小册子（1959–2009，含孟加拉语、印地语等） |
| [Memoria Chilena · Panfletos 1973–1988](https://www.memoriachilena.gob.cl/602/w3-article-3641.html) | 智利 | 军事独裁时期政党活动被禁，传单成为主要宣传形式；该专题收录此期 panfletos |

## 检索提示

这类材料在目录里按**体裁**而非主题标引，换词比换库更有效。完整对照表见 [`docs/FINDING-AIDS.md`](docs/FINDING-AIDS.md)：

- 英文 `pamphlet` `leaflet` `handbill` `broadside` `tract`；德文 `Flugschrift` `Flugblatt`；法文 `brochure` `tract`；西文 `folleto` `panfleto`；俄文 `брошюра` `листовка`
- 竞选材料单独成类：`election addresses`（英）、`profession de foi`（法）、`Wahlaufruf`（德）
- 按**出版机构**反查命中率最高：Dietz Verlag、Lawrence & Wishart、Editions Sociales、人民出版社、东北书店
- 别忽略**警察与情报档案**：被查扣的传单往往是某份材料唯一存世的副本

## 授权

- 代码：MIT，见 [LICENSE](LICENSE)。
- 说明文字与整理后的元数据：由 AI 辅助生成与整理，仅供学术交流，条款见 [DISCLAIMER.md](DISCLAIMER.md)。
- `data/catalog.json` 与 `notes/` 中的书目信息与馆藏描述摘自已公开的图书馆、档案馆页面，著作权属原机构，仅供研究索引之用。
- 图像不在本仓库内。若自行抓取，请遵守各馆的引用与复制规定。

## 声明与免责

本仓库的说明文字、检索手册、页面与条目整理由 AI（大语言模型）辅助生成，经脚本批处理；元数据字段抓取自各原藏机构的公开页面。AI 辅助整理会出错——字段错配、年份误判、机构情况过时都有可能——维护者未逐条人工复核，**不对内容的准确性、完整性、时效性作任何保证**。

用途限于历史学、图书馆学、政治传播史等方向的研究、教学与检索方法交流，不构成法律、版权或政治意见。所收录材料是十九至二十世纪各政党与派系的宣传品，其中包含法西斯主义、殖民主义、种族主义等今日极具争议的内容；**收录不等于认同**，本仓库不代表任何政党、组织或政治立场。

书目信息与馆藏描述的著作权归各原机构与捐赠者，扫描图像不在本仓库内。若任何机构或个人认为某条记录、某段摘录或某个链接侵犯其权利或不宜公开，请在 [Issues](https://github.com/chosenecho/political-pamphlet-archives/issues) 留言；收到有效请求后将**立即删除**相关记录，或按请求范围下架整个仓库。勘误同样走 Issues。

内容按「现状」提供，维护者不对因使用或无法使用本仓库内容而产生的直接或间接损失承担责任。完整条款与英文说明见 [DISCLAIMER.md](DISCLAIMER.md)。

## 已知缺口

- 西班牙内战海报（PARES）、法国二战 9000 份传单（Gallica）、胡佛 10 万张海报——自动化访问被 Cloudflare 拦截，未接入。
- 中东（奥斯曼档案、以色列国家图书馆）、撒哈拉以南非洲、东南亚的民族主义政党的宣传材料尚未覆盖。
- 北欧（瑞典、丹麦、芬兰、挪威）与比利时：按母语种与组织名多轮检索 Internet Archive，**没有一条合格的多页宣传材料**。检索并非零命中，但命中的都不是目标体裁——例如芬兰语 politica 命中的 20 条全是芬匈协会期刊《Suomi-Unkari》的各期，比利时命中的 106 条实为加拿大魁北克的法语政治演说（`language:fre` 不区分法国、比利时与魁北克）。两国材料只能走国家图书馆到馆或申请复制。
- 奥地利、荷兰、西班牙、匈牙利的小册子仍各只有 1–4 本。这四国的政党文献主要藏在维也纳、阿姆斯特丹、马德里与布达佩斯的专门机构，公开数字化的部分是期刊与年报，不符合"多页宣传小册子"的收录体裁。
- **日本、捷克、葡萄牙至今没有一本小册子**。按母语种检索 Internet Archive，这三国的命中主要是期刊、法令汇编与学术论文：捷克语政治类命中为 0，日语政治类命中为 0，葡萄牙语命中的多是咖啡与关税经济文书、协会章程。这三地目前只有单页海报／传单（日本 10、葡萄牙 9、捷克 4）。
- 波兰已从 IA 补到 3 本（2026-10-28）：民族民主党 1905 年利沃夫纲领、社会党第十次代表大会《纲领·策略·组织》（1908）、霍恩-弗龙斯基《告斯拉夫各民族书》（1848，弥赛亚主义政治檄文）。同批检索到的捷克语材料只有芝加哥铁匠工会章程，非政党文献，未收。
- 比利时、瑞典仍只有单页而没有小册子：比利时 1 件（1942 年《与工人士兵一起为社会主义》）、瑞典 1 件（1930 年社民党《我们在建设国家》）。这两国的政党小册子在 Commons 上未数字化。
- 苏联已从 IA 补到 2 本（2026-10-28）：《狡猾的机械》（1919 年苏俄内战政治宣传读物）、《白芬兰野兽》（1943 年战时宣传册）。
- **2026-10 那次 Internet Archive 中途不可达**（`archive.org` 全部端点超时，同期 Commons 与抗战平台正常，属单点故障而非本地网络问题）导致两本只下到部分页图：《素食的道德基础》（14/40 页）、《I.L.P. 纲领与失业》（3/24 页）。IA 恢复后已用 `scripts/tools/resume_pending.py` 续传补齐（40/40、24/24），两本均已入目录。断点续传与熔断逻辑见 `scripts/harvest_resume.py`。
- 40 个专藏中：21 个抓到可读正文，3 个只有说明文件（403/429），16 个仅登记入口、正文待取。`data/manifest.json` 覆盖 24/40 个源，其余 16 个尚未尝试。
- 抗战平台有 7 张内页取不到，源站对该页返回 403。
- **`Voters' Pamphlet 1975` 缺 1 页**：PDF 有 33 页，`pages/` 只有 32 张，缺口在第 33 页。它与下面那条的填充页不是一回事——那是多出来的，这是少了。
- 12 条记录的 `url` 为空：原值与目录里其余条目一起指向 `https://commons.wikimedia.org/`（站点根，回溯不到具体文件），已清空。其中 4 条的出处已从扫描件 PDF 内嵌的 `archive.org/details/...` 标识符找回并回填，其余 12 条 PDF 内无出处，留空待补，没有按标题去猜。
- `data/catalog.json` 的 `source` 字段（条目归属哪个专藏）目前回填 329/347 条——可按 URL 域名唯一确定的已填，其余留空未猜。剩下 18 条的 `url` 只记到站点根（如 `https://commons.wikimedia.org/`），无法指向具体条目，保持留空而不猜。
- **页数是"真实页数"，不等于 `pages/` 里的文件数。** 早期抓取脚本在内页不足时会把最后一页重复存一遍凑数，这些填充页与真页字节完全相同。`pages` 现在按「文件数 − 尾部连续重复块长度」计算，块内第一张也算填充（它和后面几张是同一份字节流）。53 本小册子曾受影响，共 197 个填充文件、其中 144 个是纯冗余。对照 PDF 页数交叉验证 94 本，93 本吻合，唯一不一致的就是上面那条缺页。校验脚本 `scripts/tools/fix_duplicates.py --verify` 可复现该结论。
