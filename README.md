# 政党宣传品档案目录 · Political Pamphlet Archives

十九至二十世纪政党、政治家、政治派系散发的宣传小册子、传单、竞选材料、政治海报的**馆藏索引与可复现抓取工具**。

这个仓库解决的问题很具体：这类材料散落在各国国家图书馆、党的档案馆、社会运动专门机构里，编目语种不同、征引方式各异，找起来比一般出版物麻烦得多。仓库把 39 个已有数字化或可检索的专藏整理成一张表，并附上能跑的采集脚本。

> **声明**　本仓库的内容由 AI 辅助生成与整理，**仅供学术研究与交流**；不保证准确、完整，也不对使用后果负责。所收录材料为历史宣传品，**收录不等于认同**。若权利人或其他方面认为内容不当，提出后**立即下架**。完整条款见 [DISCLAIMER.md](DISCLAIMER.md)。

## 包含什么

| 内容 | 说明 |
|---|---|
| [`data/catalog.json`](data/catalog.json) | **权威条目目录**：230 条（131 本小册子 + 99 件单页），统一 schema，含标题、译名、国别、年份、页数、立场、来源归属 |
| [`data/sources.json`](data/sources.json) | **39 个专藏**的清单：名称、国别、类型、入口 URL、规模注记 |
| [`data/index.csv`](data/index.csv) | 同一份专藏清单的表格版，带抓取状态，Excel 可直接打开 |
| [`data/manifest.json`](data/manifest.json) | 专藏的抓取记录：HTTP 状态、字节数、正文字符数、失败原因 |
| [`metadata/`](metadata/) | 逐条抓取日志（中国 1920–1949、西方 1815–1948），记录每个下载项的 IIIF 地址与页数 |
| [`notes/`](notes/) | 已抓取的收藏说明页正文纯文本，可直接 grep |
| [`docs/index.html`](docs/index.html) | **目录与阅读器**：多维筛选、年代直方图、网格/列表双视图、URL 记忆、单页·双页·连续三种阅读模式；开启 GitHub Pages 即可浏览 |
| [`docs/COLLECTIONS.md`](docs/COLLECTIONS.md) | 39 个专藏的可点击清单与抓取状态 |
| [`docs/FINDING-AIDS.md`](docs/FINDING-AIDS.md) | **检索手册**：14 种语言的体裁检索词、按出版社反查、各类型馆藏查法 |
| [`scripts/`](scripts/) | 采集与构建脚本，见下 |

`docs/index.html` 由 `scripts/templates/catalog.html` 加 `data/catalog.json` 生成，不要手改；改了源数据或模板要重跑构建，CI 会校验两者是否一致，并跑一遍页面交互验收。

### 目录页的设计取舍

页面上有几处不是装饰，而是被数据逼出来的决定：

- **图像缺席时，封面不是错误态。** `images/` 不入库，Pages 上 230 张图全部 404。所以卡片在图片加载失败时渲染一块**排版封面**——小册子照扉页排（年份、题名、原名、国别页数），单页照招贴排（年份色条、大字号题名）。有图时它被图盖住，没有时它就是封面本身，目录在任何情况下都读得下去。
- **封面不裁切。** 实测封面宽高比从 0.38 到 2.08，单页海报多是横版 1.3–1.5。原来的 `aspect-ratio:2/3 + object-fit:cover` 会把横版海报裁掉三分之一，现在改成衬纸 `contain`。
- **主筛选维度是国别与年代，不是立场。** `stance` 只有 57/230 有值，`source` 只有 71/230。把立场做成主筛选器会让人以为库里只有这些立场；页面上因此显式标注了「另 N 条未标注」，不把缺口伪装成不存在。
- **年代用可点直方图。** 跨度 1830–1993，76 个年份做成下拉没人愿意滚；直方图一眼看到 1910s、1930s、1940s 三个峰，点击或 Shift 连选收窄。
- **列表视图是给研究用的。** 网格给浏览，列表给核对：一屏 20 余条，题名、原名、国别、体裁、页数、立场对齐成列，命中词高亮。

### 图像缺失时怎么恢复

页面按 `../images/` 定位图像。要指向别处（例如把自己抓的图放在另一块盘），加查询参数即可：

```
docs/index.html?assets=/path/to/images/
```

阅读器侧栏会显示每页原图的实际像素尺寸——部分来源的分辨率本身就很低（最窄的一本只有 330×584），放大到顶就是原图，不是加载失败。

## 图像不随仓库分发

已抓取的实体材料：**131 本多页小册子（3630 页）** + **99 件单页传单／海报**，覆盖 18 国。都没有放进仓库，原因有二：体积，以及**扫描件的版权属于各原藏机构与捐赠者**，公开再分发不合适。

`images/` 因此被 .gitignore 排除。条目元数据完整保留在 `data/catalog.json`，所以任何人都能按下面的步骤把图抓回来。目录页在图片缺失时会显示占位块，不会破损。

```bash
pip install -r requirements.txt

python scripts/harvest_mh2.py            # 抗战平台：按主题搜索并下载封面
python scripts/harvest_pages.py          # 抗战平台：补抓内页（短篇全本，长篇首尾）
python scripts/harvest_ia.py             # Internet Archive
python scripts/harvest_ia_gap.py --dry   # IA 缺口国候选（先看清单与国别判定依据）
python scripts/harvest_ia_gap.py         # IA 缺口国下载
python scripts/merge_ia_gap.py           # 并入 catalog（--dry 预演）
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
- **Wikimedia Commons**：必须使用符合其[用户代理政策](https://meta.wikimedia.org/wiki/User-Agent_policy)的 UA，否则缩略图服务会持续返回 429。用在 `lib/http.py` 里的 `ToolName/1.0 (URL; mail)` 形式。抓取间隔不要低于 1 秒。
- **Internet Archive**：元数据字段齐全，是补国别缺口最省事的源，但**国别不能从检索式推**。`harvest_ia_gap.py` 因此把判定收成一条有证据的链：出版者是政党/工会/宣传机构本身时按该组织的政治出身定（与目录既有口径一致——1848 年伦敦印的《共产党宣言》归德国）；其次看作者机构；再次看出版地；主题词单独命中而无出版地佐证的一律丢弃。三类反例都是实测踩出来的：检索式写"奥地利"返回的全是 Berlin / Jena / Breslau 的德国书；`home rule` 把纽约、俄勒冈、加州的市政自治全捞进来；悉尼的 Fabian Society of NSW 与伦敦费边社同名。此外标题恰为 `Fabian tract(s)` 的是年度装订合订本（`volume 1959-60`），须排除，只收有独立篇名的单册。
- **Gallica / Hoover / 西班牙 PARES**：Cloudflare 挑战页，本轮未突破。Gallica 的 SRU 与 IIIF 接口对脚本请求返回 403。

## 已核实的 39 个专藏（节选）

完整表见 [`docs/COLLECTIONS.md`](docs/COLLECTIONS.md)。跨地区的几组：

**综合与聚合入口**

| 专藏 | 地区 | 规模 |
|---|---|---|
| [Social History Portal](https://www.socialhistoryportal.org/) | 欧洲 | IALHI 国际劳工史机构协会门户，跨馆检索社会运动档案与 100 余种期刊目次 |
| [JSTOR 19th Century British Pamphlets](https://about.jstor.org/products/journals-and-primary-sources/licensed-collections/19th-century-british-pamphlets/) | 英国 | 2.6 万册、逾 100 万页，合并 7 所大学馆藏 |

**党档案馆（往往比国家馆更全）**

| 专藏 | 地区 | 规模 |
|---|---|---|
| [FES 社会民主党档案馆](https://www.fes.de/archiv-der-sozialen-demokratie) | 德国 | SPD 党产文献，Digitale Bibliothek 做期刊与小册子回溯数字化 |
| [KAS 基督教民主档案馆](https://www.kas.de/de/archiv-und-bibliothek) | 德国 | CDU/CSU 1900 余个档案群，19 公里档案，Flugblätter 可全文检索 |
| [Fundación Pablo Iglesias](https://fpabloiglesias.es/archivo-y-biblioteca/) | 西班牙 | PSOE、UGT、JSE 历史档案 |
| [People's History Museum](https://phm.org.uk/collection/labour-history-archive-study-centre/) | 英国 | 工党及各左翼压力团体全宗 |

**社会运动与冷战专门机构**

| 专藏 | 地区 | 规模 |
|---|---|---|
| [IISH 阿姆斯特丹](https://iisg.amsterdam/en/collections) | 荷兰 | 100 万册、5445 个档案群 |
| [Schweizerisches Sozialarchiv](https://www.sozialarchiv.ch/) | 瑞士 | 约 18 万册小册子与传单 |
| [Blinken OSA Archivum](https://archivum.org/) | 匈牙利 | 冷战、自由欧洲电台、samizdat |
| [VGA 维也纳](https://www.vga.at/) | 奥地利 | 6000 余张政治海报在线检索 |

**亚洲与拉美**

| 专藏 | 地区 | 规模 |
|---|---|---|
| [抗日战争与近代中日关系文献数据平台](https://www.modernhistory.org.cn/) | 中国 | 5000 万页以上，含红色文献专题库 |
| [法政大学大原社会問題研究所](https://oisr-org.ws.hosei.ac.jp/) | 日本 | 日本社会运动史核心机构，政党与工会ビラ |
| [LoC 新德里政治小册子集](https://www.loc.gov/item/2009345307) | 印度/美 | 南亚政治小册子 1959–2009，多语种 |
| [Memoria Chilena · Panfletos](https://www.memoriachilena.gob.cl/602/w3-article-3641.html) | 智利 | 1973–1988 军政府时期政党传单 |

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
- 中东（奥斯曼档案、以色列国家图书馆）、撒哈拉以南非洲、东南亚的民族主义政党宣传品尚未覆盖。
- 北欧（瑞典、丹麦、芬兰、挪威）与比利时：按母语种与政党名多轮检索 Internet Archive，**没有一条合格的政党宣传小册子**。检索并非零命中，但命中的都不是目标体裁——例如芬兰语 politica 命中的 20 条全是芬匈协会期刊《Suomi-Unkari》的各期，比利时命中的 106 条实为加拿大魁北克的法语政治演说（`language:fre` 不区分法国、比利时与魁北克）。两国材料只能走国家图书馆到馆或申请复制。
- 奥地利、荷兰、西班牙、匈牙利的小册子仍各只有 1–4 本。这三国的政党文献主要藏在维也纳、阿姆斯特丹、马德里与布达佩斯的专门机构，公开数字化的部分是期刊与年报，不符合"多页宣传小册子"的收录体裁。
- 39 个专藏中：21 个抓到可读正文，3 个只有说明文件（403/429），15 个仅登记入口、正文待取。`data/manifest.json` 覆盖 24/39 个源，其余 15 个尚未尝试。
- 抗战平台有 7 张内页取不到，源站对该页返回 403。
- `data/catalog.json` 的 `source` 字段（条目归属哪个专藏）目前回填 71/230 条——可按 URL 域名唯一确定的已填，其余留空未猜。
