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

KIND_BOOK = "小册子"
KIND_SINGLE = "单页"
KINDS = (KIND_BOOK, KIND_SINGLE)

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
    """写 catalog，保证字段齐全、顺序稳定、末尾换行（便于 git diff）。"""
    path = path or paths.CATALOG
    paths.ensure_dir(os.path.dirname(path))
    clean = [normalize(r) for r in records]
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

    host = urlparse(url or "").netloc.lower()
    if host in _DOMAIN_TO_SLUG:
        return _DOMAIN_TO_SLUG[host]
    if host.endswith("archive.org"):
        for marker, slug in _IA_COLLECTION_TO_SLUG.items():
            if marker in url:
                return slug
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
