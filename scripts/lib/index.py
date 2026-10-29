"""文献目录（catalog）的读写与规范化。

权威文件是 data/catalog.json，受版本控制。
images/ 目录只存二进制，不再存放索引。

记录 schema（所有字段始终存在，避免下游 `.get` 靠运气）：

    kind       str   "小册子" | "单页"
    country    str   展示用国家名
    year       str   "1936"；未知为 ""
    title      str   原始标题
    title_zh   str   中文译名；无则 ""
    pages      int   页数
    dir        str   相对 images/ 的目录
    cover      str   相对 images/ 的封面路径
    pdf        str   相对 images/ 的 PDF；无则 ""
    url        str   来源 URL；无则 ""
    stance     str   政治立场；未标注为 ""
    source     str   对应 data/sources.json 的 slug；无法归属为 ""
"""

import json
import os

from . import paths
from . import vocab

KIND_BOOK = "小册子"
KIND_SINGLE = "单页"
KINDS = (KIND_BOOK, KIND_SINGLE)


class VocabularyError(ValueError):
    """写入了未登记的 stance 取值。见 `vocab` 模块与 `save()`。"""


SCHEMA = {
    "kind": str,
    "country": str,
    "year": str,
    "title": str,
    "title_zh": str,
    "pages": int,
    "dir": str,
    "cover": str,
    "pdf": str,
    "url": str,
    "stance": str,
    "source": str,
}

#: 历史遗留键名 -> 规范键名
_ALIASES = {"region": "country", "cover_path": "cover"}


def _empty(key):
    return 0 if SCHEMA[key] is int else ""


def load(path=None):
    """读 catalog；文件不存在时返回空列表而不是抛错。"""
    path = path or paths.CATALOG
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(records, path=None):
    """写 catalog，保证字段齐全、顺序稳定、末尾换行（便于 git diff）。

    写入前校验 stance 词表：未登记的值一律拒绝，抛 `VocabularyError`。

    这是全库唯一该长这张闸门的地方——24 处 `catalog.save()` 调用全部经过这里，
    而 `scripts/` 下 21 个脚本各自持有立场字面量、没有任何公共层。如果不在写入
    路径上拦，新值就会像过去八批采集那样，从某个 `merge_*.py` 里静默流进数据，
    直到界面上出现第 61 个筛选项才有人发现。

    **为什么是抛错而不是警告**：这个项目对缺口的态度是"显式声明、不伪装"
    （见 README「主筛选维度是国别与年代」），同样的标准适用于词表——一个
    没经过判断的值不该被写进去，而不是写进去之后在日志里留一行没人看的字。
    真要新增，去 `vocab.STANCE` 登记并写明依据，那是一次有意识的决定。
    """
    path = path or paths.CATALOG
    paths.ensure_dir(os.path.dirname(path))
    clean = [normalize(r) for r in records]

    problems = vocab.validate(clean)
    if problems:
        detail = "\n".join("  " + p for p in problems[:20])
        more = f"\n  …另有 {len(problems) - 20} 条" if len(problems) > 20 else ""
        raise VocabularyError(
            f"stance 有 {len(problems)} 个未登记取值，拒绝写入 {os.path.basename(path)}：\n"
            f"{detail}{more}\n"
            "在 scripts/lib/vocab.py 的 STANCE 里登记这些值并写明依据，再重跑。\n"
            "（未登记不等于错——但需要一次显式判断，而不是让脚本替你做。）")

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(clean, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return path


def normalize(rec):
    """补齐缺失字段、修正类型、丢弃未知键，返回新 dict。"""
    out = {}
    for key, typ in SCHEMA.items():
        val = rec.get(key, rec.get(_ALIASES.get(key, key), _empty(key)))
        if val is None:
            val = _empty(key)
        if typ is int:
            try:
                val = int(val)
            except (TypeError, ValueError):
                val = 0
        else:
            val = str(val)
        out[key] = val
    if out["kind"] not in KINDS:
        raise ValueError(f"未知 kind={out['kind']!r}，title={out['title']!r}")
    return out


def validate(records):
    """返回问题列表；空列表表示通过。"""
    problems = []
    seen = {}
    for i, r in enumerate(records):
        tag = f"[{i}] {r.get('title', '?')[:40]}"
        for key in SCHEMA:
            if key not in r:
                problems.append(f"{tag}: 缺字段 {key}")
        if r.get("kind") not in KINDS:
            problems.append(f"{tag}: kind 非法 {r.get('kind')!r}")
        if not r.get("title"):
            problems.append(f"{tag}: title 为空")
        if not r.get("cover"):
            problems.append(f"{tag}: cover 为空")
        else:
            full = os.path.join(paths.IMAGES, r["cover"].replace("/", os.sep))
            if not os.path.exists(full):
                problems.append(f"{tag}: cover 文件不存在 {r['cover']}")
        key = r.get("cover")
        if key:
            if key in seen:
                problems.append(f"{tag}: cover 与 [{seen[key]}] 重复")
            seen[key] = i
    return problems


def stats(records):
    """统计概况。对未 normalize 的原始记录同样可用。"""
    books = [r for r in records if r.get("kind") == KIND_BOOK]
    return {
        "total": len(records),
        "books": len(books),
        "singles": len(records) - len(books),
        "countries": len({r["country"] for r in records if r.get("country")}),
        "stances": len({r["stance"] for r in records if r.get("stance")}),
        "with_zh": sum(1 for r in records if r.get("title_zh")),
        "linked": sum(1 for r in records if r.get("source")),
    }


# --- 来源归属 ---------------------------------------------------------------

#: 文档 URL 域名 -> data/sources.json 的 slug。
#: 无法唯一确定的留空，由调用方显式标 "" 而不是猜。
_DOMAIN_TO_SLUG = {
    "www.modernhistory.org.cn": "modernhistory-cn",
    "gallica.bnf.fr": "gallica-tracts-ww2",
    "www.europeana.eu": "social-history-portal",
}

#: arc hive 标识符 -> slug
_IA_COLLECTION_TO_SLUG = {
    "modernhistory": "modernhistory-cn",
}


def _slug_from_url(url):
    from urllib.parse import urlparse

    url = url or ""
    host = urlparse(url).netloc.lower()
    if host in _DOMAIN_TO_SLUG:
        return _DOMAIN_TO_SLUG[host]
    # 同域但路径不同的来源，必须先判路径：
    #   modernhistory.org.cn 与 europeana 的具体条目都在别的路径下
    if host.endswith("archive.org"):
        for marker, slug in _IA_COLLECTION_TO_SLUG.items():
            if marker in url:
                return slug
    # 只有 URL 里确有条目路径才归属；站点根（https://commons.wikimedia.org/）
    # 无法指向具体条目，留空而不是猜。
    if host == "commons.wikimedia.org":
        if "/wiki/File:" in url or "/wiki/file:" in url.lower():
            return "wiki-commons"
        return ""
    if host in ("archive.org", "www.archive.org"):
        if "/details/" in url:
            return "internet-archive"
        return ""
    return ""


def attach_sources(records, sources=None):
    """按 URL 域名回填 source 字段。已有值的不覆盖。"""
    known = {s["slug"] for s in (sources or [])}
    for r in records:
        if r.get("source"):
            continue
        slug = _slug_from_url(r.get("url", ""))
        r["source"] = slug if slug in known else ""
    return records
