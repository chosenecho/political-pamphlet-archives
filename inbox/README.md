# inbox —— 手工获取的材料投递箱

有些馆藏必须登录、到馆或走复制申请才能拿到。拿到 PDF 后放到这里，会自动并入合集。

## 怎么用

1. 按国别建子目录，把 PDF 或扫描图放进去：

```text
inbox/
├── 德国/
│   └── 1928_sozialdemokratische_flugschrift.pdf
├── 法国/
│   └── 1936_profession_de_foi.pdf
```

2. 文件名里带四位年份更好（会写入元数据，如 `1928`）。
3. 运行：

```bash
python scripts/ingest_inbox.py            # 先预览会并入什么
python scripts/ingest_inbox.py --commit   # 实际并入
python scripts/build_catalog.py           # 更新目录页
```

脚本会：复制 PDF 进 `images/小册子/<国别>/`、渲染成 1000px 页图、写入 `images/索引.json`。
页数不在 2–200 之间的跳过。需要 PyMuPDF（`pip install pymupdf`）。

## 国别目录名

必须是下列之一（与 `images/小册子/` 一致）：
中国、美国、英国、法国、德国、俄国、意大利、西班牙、葡萄牙、荷兰、奥地利、
捷克、波兰、匈牙利、瑞典、丹麦、芬兰、比利时、爱尔兰、印度、拉美

## 哪些馆藏值得这样拿

| 馆藏 | 需要什么 |
|---|---|
| Gallica 二战传单（9000 份） | 浏览器可正常打开；脚本被 Cloudflare 拦 |
| Hoover 政治海报（10 万张） | 同上 |
| JSTOR 19th Century British Pamphlets（2.6 万册） | 机构订阅 |
| Gale Political Extremism | 机构订阅 |
| FES AdsD / KAS ACDP | 到馆或付费复制 |
| IISH / Schweizerisches Sozialarchiv | 到馆 |
| PARES 西班牙内战海报 | 站点限流，浏览器可取 |
