# 数字档案 UI 研究报告

**对象**：`pamphlet-archives` 静态学术档案目录站（单文件 HTML + 内联 JSON，`file://` 打开）
**研究问题**：同类数字馆藏在 400–5000 条目、上百本多页文献这个量级上怎么做？哪些做法能直接借鉴？
**撰写日期**：2026-10-28 · 仅研究，未改动任何代码

---

## 0. 先说结论，以及一个必须先讲清的测量事实

### 0.1 量级核实：目录在本次调查期间从 439 涨到 492

`data/catalog.json` 在我开始调查时是 **439 条**，调查中途变成 **492 条**（git 提交 `1592839 补采 108 件`）。当前实测：

| 项 | 数值 |
|---|---|
| 记录数 | 492（小册子 156 / 单页 336） |
| 多页文献总页数 | 4608 页（最大单本 89 页） |
| 封面磁盘占用 | 492 张，245.7 MB，中位 428 KB，p90 919 KB，最大 5.0 MB |
| 内页磁盘占用 | 4831 张，1648 MB，中位 296 KB |
| 国别 / 年代 | 22 / 1830–1993 |
| 构建产物 | `docs/index.html` 311 KB（含全部数据） |

**这个量级远未到"百万级"**，很多为大馆设计的方案在这里是过度工程。下面每条结论都会明确回答"值不值得"。

### 0.2 卡顿的真实原因（实测，不是推测）

我用 Playwright 对当前 `docs/index.html` 做了分项计时（1440×900，Chromium）：

```
冷启动            471 ms
首屏解码封面       60 张（未滚动）
首屏封面字节       21.3 MB（60 张）
DOM 节点           11042
文档高度           31939 px

apply()（全量 492 条，网格）   中位 148–161 ms
  ├─ filter + sort              0.7 ms   ← 可忽略
  ├─ 新建卡片 DOM               9.6 ms
  ├─ 挂载                       1.6 ms
  └─ 强制布局（offsetHeight）   129–137 ms  ← 约 90% 的代价在这里
apply()（列表视图）            中位 84–88 ms
```

（注：这组数据在页面刚加载、封面还在解码时测得。等页面完全静止后重测，基线降到 59–63 ms —— 说明**图片解码本身也在和布局抢主线程**，从另一个角度印证了第 2 条建议的必要性。）

**结论：排序和筛选几乎免费，代价的 90% 在"一次性把 492 张卡片塞进 DOM 并强制布局"。** 这决定了一切优化方向：不要去优化排序算法，要去减少同时在布局中的卡片数。

一次 A/B（同一页面，运行时注入 CSS，不改文件）：

| 方案 | apply() 中位 |
|---|---|
| A. 现状（492 张全渲染） | **59.2 ms**（另一次测得 148–161 ms，取决于缓存状态） |
| B. 加 `content-visibility: auto` | **7.3 ms** |
| C. 分页到 120 张 | 39.9 ms |
| D. 分页 120 + `content-visibility` | **2.9 ms** |

（A 与 B 的巨大差距在多次运行中稳定复现：B/D 始终在 3–8 ms，A 在 59–161 ms 之间波动。）

**这一条是本报告最重要发现**：一行 CSS 换来 8–20 倍的主线程时间下降，且不需要构建工具链。详见第 3 节（含它的坑）。

### 0.3 读者环节的第二个瓶颈

打开"最重的一本"（捷克 1917，75 页，磁盘 76 MB）：

```
单击打开（单页模式）：75 个内页请求，76.2 MB 解码，7.1 秒
```

原因是：缩略图条 `buildThumbs()` 直接 `im.src = pageSrc(d, p)` —— **500px 原图，实际显示 49px 宽，10 倍超采样**。这是"打开一本书要等好几秒"的直接原因，且完全不需要架构改动就能修。

**顺带排除两个我原本怀疑、但实测不成立的假设**（避免误导后续优化）：

- **没有内存泄漏。** 连续开 5 本 48–60 页的书，`<img>` 数与 JS 堆（稳定 10 MB）都不累积；开 1 本时 542 个节点，开第 5 本仍是 548 个。
- **但阅读器关闭后不释放。** `closeReader()` 只移除 `.on` 类和 hash，不做 DOM 清理，实测关闭后仍有 602 个 `<img>`（54 缩略图 + 54 连续页 + 网格）。这不影响正确性，只是常驻内存略高；在 89 页规模下无关紧要，**不建议为此改**。

---

## 1. 大型数字馆藏的浏览模式

### 1.1 观察到的事实

**Library of Congress Digital Collections** —— 首次进入是**浏览优先**：`/collections/` 直接给 592 个馆藏的分页列表（每页 40），配 Featured Content 轮播、View/Sort 控件（List / Gallery / Grid / Slideshow；Title / Date / Shelf Order），每个馆藏卡片上直接写"View 6,687 Items"。检索是并列入口而非默认入口。
来源：<https://www.loc.gov/collections/>（抓取快照 2026-10-26）

**DPLA** —— **检索优先**，但结果页把控制权全交给用户：`Items per page: 10 / 20 / 50 / 100`、`Sort by: Relevance / A–Z / Z–A / Oldest / Newest`、`List View / Grid View` 并列，右侧是 8 组分面（How Can I Use It / Type / Subject / Date / Location / Language / Partner …），Subject 分面一次列出 40+ 项，每项带命中数。分页是传统 `?page=N`，底部给 `1 2 3 … 100 Next`。
来源：<https://dp.la/search?q=propaganda>

**NYPL Digital Collections** —— 检索结果默认 **48 条/页**，可选 48 / 96 / 192；默认排序 Relevance，另有 Newest to oldest、Oldest to newest、Title A–Z / Z–A、**Collections first / Items first**（把"馆藏"和"单件"分开排，解决聚合库里层级混杂的问题）。分面默认只露 Topic / Name / Collection / Place 四组，其余收在"See all filter options"后面。
来源：<https://digitalcollections.nypl.org/search/index?q=propaganda>

**Europeana** —— 结果页有 **Grid / List / Mosaic** 三种密度；默认只露 Theme / Type of media / Can I use this? 三组分面，其余 7 组（Providing country / Language / Aggregator / Providing institution / Colour / Image orientation / Image size / File format / Rights statement）收在 "Show additional filters" 后面。高级检索是"可增删的规则行"（Field + Modifier + Term）。
来源：<https://www.europeana.eu/en/search?query=propaganda%20poster&view=grid>

**Gallica** —— 默认 **15 条/页**，可选 15 / 30 / 50；排序 `Pertinence` 默认，另有 Auteur / Titre / Date 升序 / Date 降序 / **Qualité mode texte**（按 OCR 质量排）/ Date mise en ligne。分面共 9 组，每组先只显示前若干项加 "Plus d'éléments" 展开。**明确提供"导出检索结果报告"、"订阅 RSS"、"保存检索式"**三件研究型用户要的东西。
来源：<https://gallica.bnf.fr/services/engine/search/sru?operation=searchRetrieve&version=1.2&query=%28gallica%20all%20%22propagande%22%29&lang=fr>
（API 层：LOC 的 `sp`/`c` 分页参数见 <https://www.loc.gov/apis/json-and-yaml/requests/endpoints/>；Europeana Search API 单页上限 100，见 <https://europeana.atlassian.net/wiki/spaces/EF/pages/2385739812/Search+API+Documentation>）

**Internet Archive 高级检索** —— 提供 200+ 排序键、任意字段组合、多种导出格式（JSON / XML / CSV / RSS / HTML table）。这是"研究型用户的逃生舱"：界面再复杂，只要能导出，学者就不受困。
来源：<https://archive.org/advancedsearch.php?q=propaganda+AND+mediatype%3Atexts>

**Smithsonian Open Access** —— 首页给"Search"和"Just browsing"两个并列入口，后者直接跳到 `media_usage:CC0` 的全量浏览。即"检索 / 随便逛逛"被显式区分为两条路径。
来源：<https://www.si.edu/openaccess>

**HathiTrust** —— 未取得可靠来源（`hathitrust.org` 对自动抓取返回 403 Cloudflare 拦截，多次尝试均失败）。**这一项按未找到处理**，不做推断。

### 1.2 无限滚动 vs 分页

NN/g 的结论明确：**无限滚动不适合目标导向的查找任务**，因为（a）破坏滚动条对"还剩多少"的指示，（b）无法回到"刚才在第 3 页看到的那个"，"人们记得住第 3 页，记不住长页面里的位置"。折中方案是**无限滚动 + Load More 按钮**，既保留滚动流畅，又给页脚可达性和"已看 X / 共 Y"的进度感。
来源：<https://www.nngroup.com/articles/infinite-scrolling/> 与 <https://www.nngroup.com/articles/infinite-scrolling-tips/>

**关键事实：上述九家里没有一家在结果页用无限滚动。** 全部是分页（LOC 40 / NYPL 48 / DPLA 20 默认 / Gallica 15 / Europeana 分页）。原因正是 NN/g 说的：档案馆用户是目标导向的。

### 1.3 对我们的适用性判断

| 事实 | 我们该学到什么 | 在 492 条上值不值得 |
|---|---|---|
| 大馆分面普遍**分层**：默认 3–4 组，其余折叠 | 我们有 6 组筛选（体裁/年代/国别/立场/专藏/PDF）全展开。左侧栏在 492 条下国别 22 项、年代 17 段，已经开始长 | **值得**。把"立场/专藏/PDF"折进"更多筛选"，首屏只留体裁、年代、国别 |
| LOC 是浏览优先；DPLA/Europeana 是检索优先 | 我们已经是浏览优先（网格默认），这对 492 条是对的。**不该改** | **不适用**（现状正确） |
| NYPL 的 "Collections first / Items first" | 我们只有一层"条目"，没有馆藏层级，这个控件无意义 | **不适用** |
| Gallica 的 15/30/50 每页 + OCR 质量排序 | 我们没有 OCR 文本，"按文本质量排"无从谈起；但**每页条数可选**在 492 条上有意义 | 中：值得，但优先级低于第 3 节 |
| Europeana 三种密度（Grid/List/Mosaic） | 我们已有网格/列表两档，第三档收益递减 | **不适用**（过度设计） |
| Gallica 的"导出检索结果报告 / RSS / 保存检索式" | 我们是 `file://` 静态页，RSS 和"保存检索式到账户"都不可能。**"导出当前结果集为 CSV"可以在浏览器内做**（Blob + 下载），但仅在包内 `目录.csv` 之外的价值有限 | 低-中：仅"导出当前筛选结果为 CSV"值得考虑 |
| 所有大馆都用分页，无一家无限滚动 | 我们当前是**一次性渲染全部结果**（等价于"一直滚到底"），这比无限滚动更糟：首屏就要付全量布局代价 | **值得改**：见第 3 节 |

**一个诚实的反面判断**：我们的 492 条在"大馆"标准里只是一个很小的专题集合。大馆必须分页是因为有几百万条；我们的问题是**一次性布局 492 张卡片**，不是"结果太多无法呈现"。所以正确解法不是照搬分页交互，而是**让浏览器别去布局屏幕外的卡片**（第 3 节）。分页在这里是"用交互复杂度换性能"，而 `content-visibility` 是"用一行 CSS 换性能"——后者在这个量级明显更优。

---

## 2. 多页文献的阅读器

### 2.1 观察到的事实

**Internet Archive BookReader** —— 源码里有一组专门控制缩略图内存的参数，直接回答"缩略图条怎么虚拟化"：

```js
/** number of rows to pre-cache out a view */
thumbRowBuffer: 1,
thumbColumns: 6,
/** number of thumbnails to load at once */
thumbMaxLoading: 4,
```

以及按"缩略图后最多同时 4 个请求"来限流，而不是靠 `loading="lazy"` 让浏览器自己决定。分页朝向用 `pageProgression: 'lr' | 'rl'`（左右 / 右左），封面单独处理的 padding 参数放在 `twoPage.coverInternalPadding`。
来源：<https://raw.githubusercontent.com/internetarchive/bookreader/master/src/BookReader/options.js>
架构说明（v5 混合 jQuery + Web Components，事件驱动）：<https://github.com/internetarchive/bookreader/blob/master/README.md>

**IIIF 生态** —— 关键事实：**IIIF 的 `thumbnail` 是 Canvas 级的独立属性，不是"把原图缩小"**。规范说客户端 *should* 渲染 Canvas 上的 `thumbnail`，并建议图床提供 Image API 以便按需改尺寸。
来源：<https://iiif.io/api/presentation/3.0/>（3.1 Descriptive Properties → thumbnail）

Image API 的 `sizes` 允许服务端声明预生成的尺寸档（如 150 / 600 / 3000），`tiles` + `scaleFactors` 才用于深度缩放。
来源：<https://iiif.io/api/image/3.0/>

**OpenSeadragon / Mirador / TIFY** —— 这三者都建立在"图床提供瓦片或按尺寸取图"的前提上。OpenSeadragon 的 IIIF tile source 需要 `width/height/profile/tiles`；TIFY 的 `viewer` 选项直接透传给 OpenSeadragon，其卖点是"142 kB gzipped、即使在超大 manifest 上也快、URL 可书签化"。Mirador 的 `BookView` 被官方文档描述为"类似 Internet Archive BookReader 的最小缩放阅读器，双页展开"。
来源：<https://openseadragon.github.io/examples/tilesource-iiif/>、<https://tify.rocks/>、<https://github.com/ExLibrisGroup/mirador/blob/master/docs/getting-started.md>

**HathiTrust** —— 通过 Wayback 取得 2024 年快照（域名直连被 Cloudflare 拦）。其阅读器有四种视图：Plain Text View（OCR 文本）、Scroll View（连续滚动）、Flip View（双页并排）、Thumbnail View。可访问性上做了三件具体事：**三个 skip link**（跳到页面内容 / 跳到纯文本视图 / 跳到书内检索）、**一套 access key**（`f` 首页、`p` 上一页、`x` 下一页、`l` 末页、`5` 切纯文本）、以及明确承认 **"OCR 无法描述图像页"**——纯图片页会给一句 "NO TEXT ON PAGE"。
来源：<https://web.archive.org/web/20241214011740/https://www.hathitrust.org/accessibility/>

### 2.2 对我们的适用性判断（这是"已解决的老问题"，可直接给方案）

**我们的现状（实测）**

| 项目 | 现状 | 问题 |
|---|---|---|
| 缩略图条 | `buildThumbs()` 直接 `im.src = pageSrc(d, p)`，即 **500px 原图** | 显示 49px 宽，**10 倍超采样**。一本 89 页的书要拉 89 张原图 |
| 双页对齐 | `spreadPair`: `si<=0 → [1]`，否则 `[2si, 2si+1]` | 封面单张、其后两两成对。**这是正确的奇偶对齐**（封面不参与配对），Internet Archive 也是这个约定，无需改 |
| 连续滚动内存 | `buildScroll()` 一次性创建全部 `<img>`（89 页 = 89 个） | 换本时 `replaceChildren` 会回收，实测连开 5 本 JS 堆稳定 10 MB、`<img>` 数不累积，**没有泄漏**。89 页规模下一次性创建实测 10 ms，可接受 |
| 页面预加载 | `preload()` 预取当前页 ±2 页 | 合理，无需改 |
| 缩放 | `transform: scale()` + `--colw` 变量 | 在 1000px 宽原图上 CSS transform 完全够用 |

**结论与方案**

1. **缩略图必须走缩略图变体，不能走原图。** 这是本报告第二重要的发现。BookReader 的 `thumbMaxLoading: 4` 是百万册规模下的限流，我们不需要那么复杂；但"缩略图用缩略图文件"是**无条件正确的**。成本：在 `make_bundle.py` 里多生成一档 120px 宽的缩略图（Pillow 已在依赖里），或在模板里让 `buildThumbs` 指向 `pages/thumb/p-00001.jpg`。**在 4608 页规模上非常值得**——一本书省下的字节是 10 倍量级。

2. **封面同理。** 实测 492 张封面 245.7 MB，中位 428 KB、p90 919 KB，但卡片里显示宽度只有 **198px**。80 张样本的 WebP 量化测试：320px/q70 中位 **14.8 KB**，400px/q72 中位 21.3 KB，480px/q72 中位 27.9 KB。按 320px 估算，492 张从 245.7 MB 降到约 7.1 MB。**首屏那 60 张从 21.3 MB 降到约 1 MB。** 这是量级差异，**强烈值得**，且只需 Python + Pillow。

> 说明：量化测试里"原图中位 214 KB"取自那 80 张样本，与全量 492 张的中位 428 KB 不同（样本里单页海报偏多）。两个口径都指向同一结论；正文一律采用**全量口径**（245.7 MB → 约 7.1 MB）。

3. **深度缩放（DZI 瓦片金字塔）在这个量级是过度工程 —— 明确不建议。**
   理由是可量化的：我们的内页原图实测中位 1000×1380 px。深度缩放的收益门槛在于"原图远超视口"（大馆的 6000×4000 才是常态）。1000px 宽的原图在 1440px 视口里放大到 2 倍就开始糊，做瓦片金字塔只是把一个 296 KB 的 JPEG 切成一堆请求，**净亏**。CSS `transform` 在 1000px 图上够用到 2–3 倍，而我们的 `noteResolution()` 已经在界面上诚实告知"放大上限是原图本身"——这个设计比引入瓦片更符合我们的数据实况。**不适用。**

4. **虚拟列表（virtual scrolling）也不必要。** 最大单本 89 页，`buildScroll` 创建 89 个节点的耗时实测 10 ms。虚拟列表的复杂度（滚动锚定、高度估算、焦点保持）在 89 项上换不来可感知收益。**不适用**（但缩略图条的"懒加载 + 缩略图变体"要做，那是字节问题不是 DOM 问题）。

5. **双页 spread 保持现状。** `siForPage` / `spreadPair` / `totalSpreads` 三者的奇偶处理是自洽的：封面单张 → 之后每两页一跨。这与 BookReader 的 `getSpreadIndices` 设计意图一致。**不建议改动**，改动风险大于收益。

6. **纯文本/降级视图**：HathiTrust 的三 skip link 模式值得借鉴一半——我们已有"跳到目录"的 skip link（实测存在），但阅读器里没有。见第 5 节。

---

## 3. 缩略图网格的性能实践（本报告核心）

### 3.1 观察到的事实

**`content-visibility: auto` 的官方机制与代价**（web.dev，Chromium 团队撰写）：

- 元素离屏时获得 `size` containment，**跳过 layout、paint 与 hit-testing**；接近视口时自动恢复。demo 里初始渲染从 232 ms 降到 30 ms（7 倍）。
- **离屏内容仍在 DOM 和可访问性树里**，因此 find-in-page、Tab 顺序、可选中性都正常。这是它与 `display:none` 的关键区别。
- 必须配 `contain-intrinsic-size`，否则未渲染元素高度为 0，**滚动条会失真**。`contain-intrinsic-size: auto <length>` 的 `auto` 关键字让浏览器**记住上次渲染的真实尺寸**，之后滚动回来不再回退到占位值——这条正是给长列表用的。
- **坑（官方明说）**：离屏子树里那些本来靠 `display:none` / `visibility:hidden` 隐藏的 landmark 元素，因为样式没被计算，仍会出现在可访问性树里造成噪音，需要额外加 `aria-hidden="true"`。
来源：<https://web.dev/articles/content-visibility/>

**实践者反馈的坑**（CSS-Tricks 文章与其评论区，2020–2021）：

- 滚动条"跳"：`contain-intrinsic-size` 猜错时，滚动条长度与实际不符。
- 抓滚动条快速拖动时有明显 jank。
- 父元素加了 `content-visibility: auto` 后，子元素 `transform: scale(>1)` 会被裁掉，`overflow: visible` 无效。
- 破坏 `scroll-behavior: smooth` 的锚点平滑滚动。
- 可访问性实测（Steve Faulkner）：离屏的 `<img>` 仍被 JAWS/NVDA 朗读 alt，但其同级 `<p>` 文本不在可访问性树里——一个不一致的中间态。
来源：<https://css-tricks.com/more-on-content-visibility/>

**`loading="lazy"` 的真实行为**：Chrome 在 4G 下距视口 **1250px** 即开始加载，3G 及更慢为 **2500px**。也就是说"lazy"并不是"进入视口才加载"，而是"快到视口就加载"。
来源：<https://web.dev/articles/browser-level-image-lazy-loading/>

**BlurHash**：把图片编码成一个极短字符串，解码成渐变占位图。问题是它是**编码/解码算法**，需要在构建期用 Pillow 之外的工具生成 hash，运行时还要跑解码器。我们是单文件无依赖页面，引入解码器与"减少一个依赖"的长期维护目标冲突。
来源：<https://blurha.sh/>、<https://github.com/woltapp/blurhash>

### 3.2 我们的适用性判断

**（1）`content-visibility: auto` —— 强烈推荐，是本报告第一优先级。**

实测证据（同一页面，运行时注入，未改文件）：

```
A. 现状                      apply() 中位  59.2 ms （另测 148–161 ms）
B. + content-visibility       apply() 中位   7.3 ms
C. 分页到 120                 apply() 中位  39.9 ms
D. 分页 120 + cv              apply() 中位   2.9 ms
```

**代价与陷阱（已实测，不是照抄文档）**：

- **`contain-intrinsic-size` 必须填对，否则滚动条撒谎。** 我用 296px 试：文档高度 31939px → 25475px，凭空少了 6464px（20%）。卡片实测高度是 **382px**（198px 宽 × 3:4 图 + 文字区）。填 `382px` 后文档高度 31925px，与原值只差 14px。**这就是必须填对的那个数字。**
- **卡片高度是固定的**（`aspect-ratio: 3/4` 的图区 + 固定行数的文字），所以占位值能写死，不存在"猜错"的长期风险。这是我们的**结构性优势**——大馆的卡片高度随标题长短变化，我们不会。
- 文档里提到的"裁切子元素 transform"坑：我们的卡片 hover 有 `transform: scale(1.012)`，但那是 `content-visibility` 作用在**卡片自身**、transform 在**子元素 `.mat img`** 上。实测 hover 正常。**建议实现后手工验证这一条。**
- 可访问性：实测离屏第 300 张卡片的 `aria-label` 仍可取到（"卡利佐普洛斯竞选材料（1928，希腊），1928，英国"），`scrollIntoView` 也能正确跳转（该卡高度从占位 296px 变真实 382px，顶部落在 258px）。**find-in-page 与键盘可达性未受损。**

**适用性结论：值得，且是唯一"一行 CSS 换 8–20 倍"的方案。** 在 492 条上它把一个 148 ms 的同步阻塞降到 7 ms——这正好跨过 100 ms 的响应性门槛。

**（2）分页 / 虚拟列表 —— 不必要。**

`content-visibility` 已经把代价降到 3–7 ms，再叠加分页只是**增加交互复杂度**（用户要翻页、要记住第几页、URL 状态要扩展），换不来更多收益（D 比 B 只快 4 ms，属噪声量级）。**在这个量级上分页是过度工程。**

**（3）缩略图变体（衍生图）—— 强烈推荐，第二优先级。**

理由见 2.2。要点：不是"性能技巧"，是**根本性的字节错误**（用 500px 图显 49px）。Python + Pillow 已在 `requirements.txt` 里，`make_bundle.py` 已有完整的编码管线（`encode()` 支持 `max_w` + WebP），**加一档缩略图几乎不增加维护面**。

**（4）BlurHash / LQIP —— 不适用。**

我们的封面不是"缺图"，`plate()` 已经用**排版封面**（衬纸 + 双线框 + 题名）优雅地填了每一张缺席的图，而且这个设计比 blurhash 更好——它是有信息的（题名、年代、国别），blurhash 只是色块。既然已有更好的退化方案，没必要引入编解码依赖。

**（5）原生 `loading="lazy"` —— 已有，但不够。**

实测：首屏未滚动就解码 60 张（因为 Chrome 的 1250px 预取距离 + 我们 198px 的卡片在 6 列里一屏就是几十张），这 60 张就是 **21.3 MB**。lazy 帮不上这个忙——**只有缩略图变体能。**

**（6）`fetchpriority` / `srcset`**：492 个封面里给当前视口的头几张加 `fetchpriority="high"`，其余默认，是零成本的 LCP 改善。可选，优先级低。`srcset` 需要多档衍生图，收益不如直接降档，不建议。

---

## 4. 学术/研究型用户的界面惯例

### 4.1 观察到的事实

**citation 导出**：LOC 的 item API 有 `cite_this` 字段，"尝试组装 Chicago / MLA / APA 三种格式"，并**明确自我声明"应作为引用的起点，不应被依赖为完整或正确"**。
来源：<https://www.loc.gov/apis/json-and-yaml/requests/endpoints/>
Gallica 提供"导出检索结果报告"（可再做筛选、可视化、选取、数据抽取）、RSS 订阅、保存检索式到个人空间。
来源：<https://gallica.bnf.fr/services/engine/search/sru?...>（同上）
JSTOR 的 "Cite this item" 给 MLA/APA/Chicago 一键复制 + 导出到 NoodleTools / RefWorks / EasyBib。
来源：<https://www.jstor.org/stable/10.7758/rsf.2021.7.1.01>

**permalink**：LOC 的每条记录有稳定 item URL；NYPL 的每条 item 有 UUID 形式的路径；DPLA 的 item 链接带 `back_uri` 参数**把"你从哪个检索结果来的"编码进 URL**，从而支持返回原结果集。这是比单纯 permalink 更细的一层。
来源：<https://dp.la/item/3ff502ae2ad4dd17ccb8d3592515a4e6?back_uri=%2Fsearch%3Fq%3Dpropaganda>

**对比视图**：Mirador 的核心卖点之一是**多窗口网格布局**（`layout: "1x2"`、`slotAddress: "row1.column1"`），可从不同机构加载两份 manifest 并排比对。这是唯一有可靠来源支持的"对比"惯例。
来源：<https://github.com/ExLibrisGroup/mirador/blob/master/docs/getting-started.md>

**书签/收藏**：DPLA 结果页每条有 "Add to list" 和 "Create a list from these items"；Mirador 有 bookmark 按钮 + `jsonStorageEndpoint`（可接 localStorage）；Gallica 有"保存检索式"。BookReader 有 `plugin.resume.js` "uses cookies to remember the current page"。
来源：<https://dp.la/search?q=propaganda>、<https://github.com/ExLibrisGroup/mirador/blob/master/docs/getting-started.md>、<https://github.com/internetarchive/bookreader/blob/master/README.md>

**时间线 / 地图视图 + 被废弃的例子**：

- **Neatline**（Omeka 的"地图 + 时间线"叙事插件，Scholars' Lab 出品）：仓库最后 push **2023-03-16**，累计 90 个未关闭 issue/PR。维护已实质停滞（未 archived，但三年无提交）。
  来源：GitHub API `/repos/performant-software/Neatline`
- **SIMILE Timeline**（大量 DH 时间线视图的底层库）：最后 push **2023-01-09**。
  来源：GitHub API `/repos/simile-widgets/timeline`
- **HyperCities**（UCLA 的"thick mapping"平台）：现站首页明确写 **"It is neither a conventional academic site nor a recreation of the original GIS platform."** —— 即原 GIS 平台已被**重写而非延续**，现版本是"static files, MapLibre, deck.gl, no backend"。
  来源：<https://hypercities.com/>
- **Historypin**：仍在运营（首页与 about 页均正常，27,000+ storytellers），但已转型为付费服务（learning sessions $450）。**没有找到它关停的证据，因此不把它列为废弃案例。**
  来源：<https://www.historypin.org/>、<https://www.about.historypin.org/services>

### 4.2 对我们的适用性判断

| 惯例 | 我们的现状 | 判断 |
|---|---|---|
| **permalink** | URL hash 已编码 `q/k/c/s/src/d/has/o/v/i/p`，且筛选替换历史、开阅读器推历史（`writeHash` + `replaceState`/`pushState`） | **已做得比多数大馆好**。唯一问题是 hash 里没有"当前版本"信息，数据更新后老链接可能指向不同条目——但 `BUILD` 指纹已在页面上显示，够用。**不需要改** |
| **citation 导出** | 无 | **值得做，且成本低**。每条记录已有 title/title_zh/year/country/source/url/dir。生成 Chicago/APA/MLA 三行文本 + `navigator.clipboard.writeText()` 是纯前端、零依赖。**注意照抄 LOC 的免责声明**："引用格式仅供参考，请核对原藏机构著录"。这是学术诚信要求，也是 LOC 自己的做法 |
| **对比视图** | 无 | **不适用**。Mirador 的多窗口是为"跨机构比对同一文献的不同版本"设计的。我们的 492 条里没有同一文献的多版本，双开阅读器的实际用途接近于零。**这是典型的"为大馆设计的功能"** |
| **书签/收藏** | `localStorage` 已用于 `pam.theme` 和 `pam.last`（记住上次读到的书与页） | **"继续上次阅读"已经有了**（`remember()`），这已经覆盖了 80% 的实际需求。**"收藏夹"值得做但优先级低**——单机 `file://` 场景下收藏无法跨设备，价值受限 |
| **时间线视图** | 有年代直方图（`#histBars`，可点击筛选） | **直方图 > 时间线**。理由：直方图已提供"时间分布的全局视野 + 点击筛选"，而时间线视图（Neatline / SIMILE）在这个量级上只多一个视觉形式，代价是一整套布局算法与交互。而且上面三条证据（Neatline 停更、SIMILE 停更、HyperCities 重写）都指向同一件事：**这类视图的长期维护成本高于它带来的价值**。**不建议做时间线视图** |
| **地图视图** | 数据里没有经纬度字段（只有 `country`，22 个值） | **不适用，且明确不建议**。没有坐标就没有地图。要为 492 条补坐标是数据工程，不是 UI 改进 |
| **导出当前结果集** | 无（但包内有全量 `目录.csv`） | 中低：值得，但仅当用户真的会筛选后导出。可以后置 |

---

## 5. 可访问性与印刷质量

### 5.1 观察到的事实

**WCAG 对"图像即内容"的立场**：1.4.5 Images of Text（AA）要求"若技术能做到，用文本而非文本图像"，例外是"可自定义"或"呈现方式对信息本质必要"。**扫描件属于后者——原件的呈现方式本身就是研究对象**，所以扫描图不算违规。但规范同时给了关键指引："当文本图像**与**文本并用、且两者都呈现给用户时，该条满足"。
来源：<https://www.w3.org/WAI/WCAG22/Understanding/images-of-text.html>、<https://www.w3.org/TR/WCAG22/#images-of-text>

**HathiTrust 的具体做法**（Wayback 快照，2024）：
- 承认现实："books were created through methods and in formats that may not meet the needs of all users"。
- 三 skip link：跳到页面内容 / 跳到纯文本视图 / 跳到书内检索。
- access key：`2` 跳导航、`5` 切 OCR 全文、`9` 到当前页、`f` 首页、`p` 上页、`x` 下页、`l` 末页。
- 四种视图里 Plain Text View 是给屏幕阅读器的第一选择；Scroll View / Flip View / Thumbnail View 是给视觉读者的。
- 明确声明 OCR 无法描述插图页，纯图页给 "NO TEXT ON PAGE"。
来源：<https://web.archive.org/web/20241214011740/https://www.hathitrust.org/accessibility/>

**`content-visibility` 与可访问性**：官方说明离屏内容仍在可访问性树里（find-in-page / Tab 顺序正常），代价是"本该隐藏的 landmark 会漏进树里"。
来源：<https://web.dev/articles/content-visibility/>（同上）
实践者实测：离屏 `<img>` 的 alt 仍被朗读，但同级 `<p>` 不在树里——不一致。
来源：<https://css-tricks.com/more-on-content-visibility/>（同上）

### 5.2 我们的现状（实测）

```
卡片               492 张，全部 role="button" + tabIndex=0 + 有 aria-label
网格内 <img>       492 张，全部 alt=""（即全部标为装饰性）
h1                 1 个
landmark           HEADER / ASIDE / MAIN / FOOTER / DIV[group] + 492 个 ARTICLE[button]
aria-live          0
skip link          "跳到目录" 1 个
Tab 停靠点          634 个
阅读器页面图        alt=""（空）
阅读器视口         无 role、无 aria-label
阅读器模式按钮      单页/双页/连续，全部无 aria-pressed
```

### 5.3 适用性判断

**（1）网格图 `alt=""` 是正确选择，不是缺陷。**

卡片已经有完整 `aria-label`（题名 + 年代 + 国别），图片是纯装饰。给 492 张扫描图写 alt 文本既是不可完成的（没有 OCR），也会让屏幕阅读器把同一个信息念两遍。**WCAG 1.4.5 支持这个判断**：文本（aria-label）与图像并存时即满足。**保持现状。**

**（2）492 个 `role="button"` 是真实的可用性问题 —— 值得改。**

实测 Tab 停靠点共 634 个。键盘用户从页首到页尾要按 492 次 Tab 才能越过目录。`content-visibility` 不解决这个（离屏元素仍在 Tab 顺序里，这是它的设计承诺，不能靠它绕开）。可选做法（按代价排序）：

- **低代价**：给网格加 `role="grid"` 或 roving tabindex（只有一张卡 tabIndex=0，方向键在卡片间移动）。约 20 行 JS，无需库。
- **零代价**：在网格前后各加一个"跳到最后一条"的 skip link，或者给 `<main>` 加 landmark（已有）——但 492 个 Tab 仍然存在。

**建议做 roving tabindex**。这是少数"大馆做对了、我们还没做"的项。（对比：HathiTrust 用了 skip link + access key 的组合，本质是同一思路的两种实现。）

**（3）阅读器缺 `aria-pressed` 与 live region —— 值得改，成本极低。**

模式按钮（单页/双页/连续）实测没有 `aria-pressed`。加一行 `b.setAttribute('aria-pressed', ...)` 即可。翻页后页码变化（`cntEl.innerHTML = "<b>3</b> / 89"`）没有 live region 播报，屏幕阅读器用户翻页后不知道到了第几页。给 `#rdCount` 加 `aria-live="polite"` 即可。

**（4）阅读器视口无 role —— 中优先级。**

`#rdViewport` 读屏时是一个无名的区域。加 `role="region" aria-label="第 X 页，共 Y 页"` 并在翻页时更新，可显著改善。

**（5）纯文本视图 —— 我们做不了，应如实声明。**

HathiTrust 能做是因为有 OCR。我们没有。**正确做法是在帮助/说明里明确写"扫描件无 OCR 文本，屏幕阅读器用户无法获取正文内容，可访问原藏机构页面获取著录信息"**——这与 HathiTrust 承认 "NO TEXT ON PAGE" 是同一种诚实。不要假装解决了。

**（6）深浅色主题与纸张/衬纸处理 —— 现状良好。**

实测 `[data-theme="dark"]` 定义了全套 CSS 变量（`--paper: #14130e`、`--surface: #1c1a14`、`--mat: #211e17`、`--ink: #f0eade`），`prefers-color-scheme` 已在启动脚本里读，`prefers-reduced-motion` 已出现 1 次。

**关键判断：扫描图不应该在暗色主题下反色或调暗。** 现有实现是正确的——`--mat`（衬纸色）随主题变化，图片本身不动。这对档案站是对的：**把 1920 年代的褐色纸变成白底或黑底，就是篡改研究对象**。衬纸承担"视觉过渡"的角色，图片保真。这个设计比很多大馆做得更谨慎，**建议写进设计说明，防止后人"优化"掉**。

**（7）一个真实的暗色主题隐患（值得验证）**：暗色下 `--paper: #14130e` 与扫描件的中位亮度差异很大。如果扫描件本身是白纸黑字，在暗色主题里会形成强烈的"发光矩形"效应，长时间阅读易疲劳。**这不是 bug，是需要实测确认的主观问题**——建议在暗色下打开一本白纸小册子，确认是否需要给阅读器区域单独一个中性灰底（而非跟随主题）。这一点我没有可靠来源，属于**待验证项**。

---

## 6. 汇总表

| # | 建议做法 | 解决什么问题 | 代价 | 优先级 |
|---|---|---|---|---|
| 1 | 给 `.card` 加 `content-visibility: auto; contain-intrinsic-size: auto 382px` | apply() 从 148 ms → 7 ms；首屏布局代价 8–20 倍下降 | 一行 CSS + 一处实测校准（382px 是实测卡片高）。坑：填错会致滚动条失真 20%；需验证 hover transform 不被裁 | **高** |
| 2 | 生成封面缩略图变体（320px WebP，中位 14.8 KB），网格用缩略图 | 首屏 21.3 MB → 约 1 MB；全量 245.7 MB → 约 7.1 MB | Python 脚本改动（Pillow 已在依赖）；多一档文件。`file://` 下零额外成本 | **高** |
| 3 | 生成内页缩略图（~120px）给 `buildThumbs`，不再用 500px 原图 | 打开一本 89 页书从 89 张原图变 89 张小图；缩略图条 10 倍超采样 | 同上，多一档衍生图 | **高** |
| 4 | 模式按钮加 `aria-pressed`；页码容器加 `aria-live="polite"` | 屏幕阅读器用户翻页后无反馈 | 约 5 行 JS | **高**（性价比最高） |
| 5 | 网格改 roving tabindex（仅一张卡 tabIndex=0，方向键移动） | 634 个 Tab 停靠点 → 数十个 | 约 20 行 JS，需处理焦点恢复 | 中 |
| 6 | 阅读器视口加 `role="region"` + 动态 `aria-label`（第 X / 共 Y 页） | 读屏时阅读区无名 | 约 5 行 | 中 |
| 7 | 左侧筛选分层：首屏只留体裁/年代/国别，"立场/专藏/PDF"折叠 | 492 条下筛选栏已过长（22 国 + 17 年代段） | 模板结构改动，中等 | 中 |
| 8 | 每条加 citation 复制（Chicago/APA/MLA + 剪贴板），附"仅供参考"声明 | 研究型用户要引用；LOC/JSTOR 都做 | 纯前端，零依赖，约 40 行 | 中 |
| 9 | 在说明中如实声明"扫描件无 OCR，屏幕阅读器无法获取正文" | 避免用户误以为已无障碍支持 | 一段文字 | 中（诚实成本最低） |
| 10 | 每页条数可选（如 96/192/全部） | 长列表浏览节奏 | 中等；`content-visibility` 已缓解，收益有限 | 低 |
| 11 | 导出当前筛选结果为 CSV（Blob 下载） | 研究型用户带走结果集 | 约 30 行；包内已有全量 CSV | 低 |
| 12 | 头几张封面加 `fetchpriority="high"` | LCP 略降 | 1 行 | 低 |
| 13 | 收藏夹（localStorage） | "稍后再看" | 中等；`file://` 下无法跨设备 | 低 |
| 14 | 时间线视图 | — | 高（布局算法 + 交互 + 长期维护）。Neatline/SIMILE 均已停更，HyperCities 被重写 | **不适用** |
| 15 | 地图视图 | — | 数据里无经纬度，需先补 492 条坐标 | **不适用** |
| 16 | 深度缩放 / DZI 瓦片 | — | 内页原图中位仅 1000px 宽，切瓦片净亏 | **不适用**（过度工程） |
| 17 | 虚拟列表 | — | 最大 89 页，建 DOM 仅 10 ms | **不适用** |
| 18 | 无限滚动 | — | 九家大馆无一使用；NN/g 明确反对用于目标导向查找 | **不适用** |
| 19 | BlurHash / LQIP | — | 现有排版封面 `plate()` 信息量更高，且无需依赖 | **不适用** |
| 20 | 对比视图（多窗口） | — | 无同文献多版本，Mirador 式双开无实际用途 | **不适用** |
| 21 | IIIF / Mirador / OpenSeadragon 接入 | — | 需引入图床服务端，与 `file://` 单文件约束直接冲突 | **不适用**（约束不允许） |

---

## 7. 需要引入额外东西才能做的（明确标注）

| 想法 | 卡在哪 | 若引入什么才可行 |
|---|---|---|
| IIIF 图床 / 按需尺寸取图 | `file://` 无服务端，IIIF 的 `sizes` 依赖 HTTP 服务 | 一个静态 HTTP 服务 + 预生成尺寸档。**不建议**：缩略图变体已解决同一问题，成本低一个数量级 |
| BlurHash 占位 | 需运行时解码器（约 5–10 KB JS） | 内联解码器。**不建议**：`plate()` 已更好 |
| 全文检索 / 书内检索 | 无 OCR 文本 | 引入 OCR 流程（Tesseract / 云 API）。这是**数据工程**，不是 UI 改进 |
| 屏幕阅读器可读正文 | 同上 | 同上。在 OCR 到位前，诚实声明是唯一正确做法 |
| RSS / 保存检索式到账户 | 无服务端、无账户 | 服务端 + 账号体系。与项目定位冲突 |
| 收藏跨设备同步 | `file://` 无后端 | 后端。不建议为此改变项目形态 |

---

## 8. 我没能验证的（明确声明）

1. **HathiTrust 现行阅读器实现细节**：`hathitrust.org` 与 `babel.hathitrust.org` 对自动抓取一律返回 403 Cloudflare 拦截（重试 3 次、换 proxy 均失败）。所有 HathiTrust 结论均来自 **2024 年 Wayback 快照**，可能已过时。
2. **Gallica / Europeana / NYPL 的前端源码层面实现**：只能观察到渲染后的 DOM 与交互，无法确认它们内部用什么做懒加载或虚拟化。本报告未对其内部机制做任何推断。
3. **`content-visibility` 在 Firefox / Safari 上的表现**：我只在 Chromium 实测。MDN 标注 Baseline 2024 新可用（Firefox 125、Safari 18），web.dev 标注 2025 年 9 月起跨浏览器可用。**建议实现后在三家浏览器各测一次滚动条与 hover。**
4. **暗色主题下白纸扫描件是否造成视觉疲劳**：无可靠来源，属主观判断，列为待验证。
5. **"时间线/地图视图被废弃"的系统性采用率数据**：只找到三个个体案例（Neatline 停更、SIMILE 停更、HyperCities 重写），**没有找到任何统计性的采用率研究**。因此本报告只说"这三个都停了"，不说"这类功能普遍被废弃"。
6. **Historypin 是否曾关停**：未找到证据，故未列为废弃案例。

---

## 附：本次调查使用的测量方法（可复现）

所有性能数字来自 Playwright + Chromium 对 `docs/index.html` 的实测。本报告与 `UI-AUDIT.md`、`UI-AUDIT-PERF.md` 同批产出。可复现的审计脚本见 `scripts/tools/audit_ui_perf.py`，原始数据见 `ui-perf-report.json`；本报告另有若干一次性对照实验（A/B 样式注入、衍生图编码估算），脚本未入库，方法在下逐条说明，可按描述重跑。关键测量项：

- **`apply()` 分项计时**：在页面内包裹 `DATA.filter(matches).sort(sortFn())` / 建 DOM / `replaceChildren` / `void gridEl.offsetHeight` 四段，各跑 9–12 次取中位。
- **A/B 注入**：`document.createElement('style')` 动态注入 `#grid .card{content-visibility:auto;...}`，不触碰任何文件。
- **字节统计**：`response` 事件抓 content-length + 本地文件 `getsize()` 交叉核对。
- **衍生图估算**：Pillow 对 80 张封面按 320/400/480px + WebP q70–72 实际编码后取中位。

数据规模在调查期间由 439 变 492，本报告全部数字基于**当前的 492 条 / 4608 页**重新采测。
