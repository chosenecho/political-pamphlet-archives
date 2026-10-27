"""文本清洗小工具。"""

import html
import re

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
#: 把多级目录名压成安全文件名
_UNSAFE = re.compile(r'[\\/:*?"<>|\r\n\t]')


def clean_title(text, limit=None):
    """去 HTML 标签、反转义实体、压缩空白。"""
    s = html.unescape(_TAG.sub("", str(text or "")))
    s = _WS.sub(" ", s).strip()
    return s[:limit] if limit else s


def safe_name(text, limit=80):
    """转成可用作文件/目录名的字符串。"""
    s = _UNSAFE.sub("_", clean_title(text))
    s = _WS.sub("_", s).strip("._")
    return s[:limit] or "untitled"


def is_cjk(s):
    return any("\u4e00" <= ch <= "\u9fff" for ch in s or "")


def year_of(text):
    """从任意文本里取第一个 18xx/19xx/20xx 年份，取不到返回 ""。"""
    m = re.search(r"\b(1[89]\d{2}|20[0-2]\d)\b", str(text or ""))
    return m.group(1) if m else ""
