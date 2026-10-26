"""修正编码：优先严格 UTF-8，失败再回退到声明编码。只处理 raw/ 里存在的文件。"""

import json
import os
import re

from lxml import html as LH

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
TXT = os.path.join(BASE, "txt")

MANUAL_SKIP = {"kas-archiv-bibliothek", "francearchives-tracts", "pares-carteles",
               "loc-printed-ephemera", "modernhistory-cn", "ndl-digital-collections"}

META = re.compile(rb'<meta[^>]+charset=["\']?([\w\-]+)', re.I)

manifest = {r["slug"]: r for r in json.load(open(os.path.join(BASE, "data", "manifest.json"), encoding="utf-8"))}


def decode_best(raw):
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    for m in META.finditer(raw[:8000]):
        enc = m.group(1).decode("ascii", "ignore").lower()
        if not enc:
            continue
        enc = "utf-8" if enc in ("utf-8", "utf8") else enc
        try:
            return raw.decode(enc, errors="replace"), enc
        except LookupError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


for slug in sorted(os.listdir(RAW)):
    if not slug.endswith(".html"):
        continue
    key = slug[:-5]
    if key in MANUAL_SKIP:
        continue
    raw = open(os.path.join(RAW, slug), "rb").read()
    s, enc = decode_best(raw)
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
    text = "\n".join(out)
    open(os.path.join(TXT, key + ".txt"), "w", encoding="utf-8").write(text)
    if key in manifest:
        manifest[key]["chars"] = len(text)
        manifest[key]["encoding"] = enc
    print(f"{key:32s} enc={enc:12s} chars={len(text)}")

json.dump(list(manifest.values()), open(os.path.join(BASE, "data", "manifest.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
