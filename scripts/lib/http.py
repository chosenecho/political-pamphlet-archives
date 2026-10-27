"""HTTP 抓取：统一 UA、重试与限速。

README 里"UA 不合规会持续 429"的踩坑经验原本散落在十几个脚本的
`safe()` / `fetch()` 副本里，改一处漏十一处。集中到这里。
"""

import gzip
import io
import ssl
import time
import urllib.error
import urllib.request

#: Wikimedia 要求 UA 采用 ToolName/1.0 (URL; mail) 形式，否则 429。
DEFAULT_UA = (
    "PoliticalPamphletArchives/1.0 "
    "(https://github.com/chosenecho/political-pamphlet-archives; "
    "research-only) Python-urllib"
)

DEFAULT_DELAY = 1.0
DEFAULT_RETRIES = 4
BACKOFF = (1, 2, 4, 8)

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


class FetchError(RuntimeError):
    pass


def _decode(resp):
    raw = resp.read()
    enc = (resp.headers.get("Content-Encoding") or "").lower()
    if enc == "gzip":
        raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    charset = resp.headers.get_content_charset() or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def fetch(url, *, ua=DEFAULT_UA, retries=DEFAULT_RETRIES, timeout=45,
          headers=None, delay=DEFAULT_DELAY):
    """GET 一个 URL 并返回文本。

    429/5xx 与网络错误按 BACKOFF 退避重试；其余 4xx 立即失败，
    重试也不会通过。
    """
    hdrs = {"User-Agent": ua, "Accept-Encoding": "gzip"}
    if headers:
        hdrs.update(headers)

    last = None
    for attempt in range(retries):
        if attempt and delay:
            time.sleep(BACKOFF[min(attempt - 1, len(BACKOFF) - 1)])
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
                body = _decode(resp)
            return body
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429 or 500 <= e.code < 600:
                continue
            raise FetchError(f"HTTP {e.code} {url}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            continue
    raise FetchError(f"重试 {retries} 次仍失败：{url}（{last}）")


def fetch_json(url, **kw):
    import json

    return json.loads(fetch(url, **kw))
