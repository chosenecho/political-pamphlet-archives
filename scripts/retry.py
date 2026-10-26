"""Retry pass for sources that failed in pass 1 (403 / 429 / JS redirect / empty body)."""

import gzip
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
import zlib

from lxml import html as LH

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
TXT = os.path.join(BASE, "txt")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

RETRIES = {
    "loc-printed-ephemera": [
        "https://www.loc.gov/collections/",
        "https://www.loc.gov/collections/an-american-time-capsule/about-this-collection/",
    ],
    "kas-archiv-bibliothek": [
        "https://www.kas.de/de/web/wissenschaftliche-dienste-archiv/bibliothek",
        "https://www.kas.de/en/archive-and-library",
    ],
    "pares-carteles": [
        "https://pares.cultura.gob.es/ParesBusquedas20/catalogo/search",
    ],
    "francearchives-tracts": [
        "https://francearchives.gouv.fr/fr/findingaid/1e48faec7165e984c693396f23969f5e00008e55",
    ],
    "ndl-digital-collections": [
        "https://www.ndl.go.jp/gallery/exhibitions/202507",
        "https://dl.ndl.go.jp/search/searchResult",
    ],
    "jstor-19c-british-pamphlets": [
        "https://about.jstor.org/products/journals-and-primary-sources/licensed-collections/19th-century-british-pamphlets/",
        "https://www.jstor.org/site/primary-sources/19th-century-british-pamphlets/",
    ],
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

META = re.compile(rb'<meta[^>]+charset=["\']?([\w\-]+)', re.I)


def decode(raw):
    enc = "utf-8"
    for m in META.finditer(raw[:4000]):
        e = m.group(1).decode("ascii", "ignore").lower()
        if e:
            enc = "utf-8" if e in ("utf-8", "utf8") else e
            break
    try:
        return raw.decode(enc, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def to_text(s):
    try:
        doc = LH.fromstring(s)
        for bad in doc.xpath("//script|//style|//noscript|//svg"):
            bad.getparent().remove(bad)
        s = doc.text_content()
    except Exception:
        pass
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in s.splitlines()]
    out = []
    for ln in lines:
        if ln:
            out.append(ln)
        elif out and out[-1] != "":
            out.append("")
    return "\n".join(out)


manifest = {r["slug"]: r for r in json.load(open(os.path.join(BASE, "data", "manifest.json"), encoding="utf-8"))}

for slug, urls in RETRIES.items():
    rec = manifest[slug]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,de;q=0.8,fr;q=0.7,ja;q=0.6,zh-CN;q=0.5",
                "Referer": "https://" + urllib.parse.urlsplit(url).netloc + "/",
            })
            with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
                body = r.read()
                if (r.headers.get("Content-Encoding") or "").lower() == "gzip" or body[:2] == b"\x1f\x8b":
                    try:
                        body = gzip.decompress(body)
                    except Exception:
                        pass
            s = decode(body)
            if len(s) < 500:
                raise ValueError(f"body too short ({len(s)} chars) - likely JS gate")
            open(os.path.join(RAW, slug + ".html"), "w", encoding="utf-8").write(s)
            txt = to_text(s)
            open(os.path.join(TXT, slug + ".txt"), "w", encoding="utf-8").write(txt)
            rec.update({"ok": True, "status": r.status, "final_url": url,
                        "bytes": len(body), "chars": len(txt), "via": "urllib-retry"})
            print(f"OK  {slug:30s} {r.status} chars={len(txt)} :: {url}")
            break
        except Exception as e:
            rec.update({"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"})
            print(f"ERR {slug:30s} {rec['error'][:90]} :: {url}")
        time.sleep(3)

json.dump(list(manifest.values()), open(os.path.join(BASE, "data", "manifest.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
