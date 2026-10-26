# 政党宣传品档案目录 · Political Pamphlet Archives

十九至二十世纪政党、政治家、政治派系散发的宣传小册子、传单、竞选材料、政治海报的**馆藏索引与可复现抓取工具**。

这个仓库解决的问题很具体：这类材料散落在各国国家图书馆、党的档案馆、社会运动专门机构里，编目语种不同、征引方式各异，找起来比一般出版物麻烦得多。仓库把 24 个已有数字化或可检索的专藏整理成一张表，并附上能跑的采集脚本。

## 包含什么

| 内容 | 说明 |
|---|---|
| [`data/sources.json`](data/sources.json) | **38 个专藏**的清单：名称、国别、类型、入口 URL、规模注记 |
| [`data/index.csv`](data/index.csv) | 同一份清单的表格版，带抓取状态，Excel 可直接打开 |
| [`data/manifest.json`](data/manifest.json) | 每个源的抓取记录：HTTP 状态、字节数、正文字符数、失败原因 |
| [`metadata/`](metadata/) | 条目级元数据（中国 1920–1949、西方 1815–1948），含标题、年份、出版者、页数、来源链接 |
| [`notes/`](notes/) | 已抓取的收藏说明页正文纯文本，可直接 grep |
| [`docs/index.html`](docs/index.html) | 图像目录页，按来源分列；开启 GitHub Pages 即可浏览 |
| [`docs/COLLECTIONS.md`](docs/COLLECTIONS.md) | 38 个专藏的可点击清单与抓取状态 |
| [`scripts/`](scripts/) | 采集脚本，见下 |

## 图像不随仓库分发

图片本身（160 张封面 + 1052 张内页，约 186 MB）没有放进仓库。原因有二：体积，以及**扫描件的版权属于各原藏机构与捐赠者**，公开再分发不合适。

条目元数据完整保留，所以任何人都能按下面的步骤把图抓回来。

```bash
pip install pillow    # 仅生成画廊预览时需要

python scripts/harvest_mh2.py         # 抗战平台：按主题搜索并下载封面
python scripts/harvest_pages.py       # 抗战平台：补抓内页（短篇全本，长篇首尾）
python scripts/harvest_commons2.py    # Wikimedia Commons：竞选材料
python scripts/retry_commons2.py      # 对 429 失败的条目重试
python scripts/build_gallery.py       # 重新生成 docs/index.html
python scripts/build_index.py         # 重建 index.csv 与 COLLECTIONS.md
python scripts/organize_images.py     # 按议题把图分到 15 类（先加 --dry 看结果）
python scripts/build_category_sheets.py  # 每类一张缩略总览
```

## 采集方式说明

各站点对自动化访问的态度差别很大，脚本里的处理对应这些差异：

- **抗日战争与近代中日关系文献数据平台**：纯前端渲染，普通抓取拿不到内容。用 Playwright 监听 XHR 找出后台接口 `backend-prod/esBook/findByPage`，直接 POST 检索，再从返回的 `imageUrl` 拼 IIIF 地址（`/full/1000,/0/default.jpg`；`/full/pct:100/0/default.jpg` 取全幅）。按 `publishTime` 过滤，只留 1949 年前原版——不加这一步，检索结果里绝大多数是 1980 年代的资料汇编。
- **Wikimedia Commons**：必须使用符合其[用户代理政策](https://meta.wikimedia.org/wiki/User-Agent_policy)的 UA，否则缩略图服务会持续返回 429。换成 `ToolName/1.0 (URL; mail)` 形式后一次通过。抓取间隔不要低于 1 秒。
- **Gallica / Hoover / 西班牙 PARES**：Cloudflare 挑战页，本轮未突破。Gallica 的 SRU 与 IIIF 接口对脚本请求返回 403。

## 已核实的 38 个专藏（节选）

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

这类材料在目录里按**体裁**而非主题标引，换词比换库更有效：

- 英文 `pamphlet` `leaflet` `handbill` `broadside` `tract`；德文 `Flugschrift` `Flugblatt`；法文 `brochure` `tract`；西文 `folleto` `panfleto`；俄文 `брошюра` `листовка`
- 竞选材料单独成类：`election addresses`（英）、`profession de foi`（法）、`Wahlaufruf`（德）
- 按**出版机构**反查命中率最高：Dietz Verlag、Lawrence & Wishart、Editions Sociales、人民出版社、东北书店

## 授权

- 代码：MIT，见 [LICENSE](LICENSE)。
- `metadata/` 与 `notes/` 中的书目信息与馆藏描述摘自已公开的图书馆、档案馆页面，著作权属原机构，仅供研究索引之用。
- 图像不在本仓库内。若自行抓取，请遵守各馆的引用与复制规定。

## 已知缺口

- 西班牙内战海报（PARES）、法国二战 9000 份传单（Gallica）、胡佛 10 万张海报——自动化访问被 Cloudflare 拦截，未接入。
- 中东（奥斯曼档案、以色列国家图书馆）、撒哈拉以南非洲、东南亚的民族主义政党宣传品尚未覆盖。
- 14 个专藏只登记了入口，正文未抓取（清单状态标 ○）。
- 抗战平台有 7 张内页取不到，源站对该页返回 403。
