"""仓库路径常量与安全搬移。

所有脚本统一从这里取路径，避免各自 `os.path.dirname(...)` 重复推导。
"""

import os
import shutil

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.dirname(SCRIPTS)

DATA = os.path.join(BASE, "data")
METADATA = os.path.join(BASE, "metadata")
DOCS = os.path.join(BASE, "docs")
IMAGES = os.path.join(BASE, "images")
NOTES = os.path.join(BASE, "notes")
INBOX = os.path.join(BASE, "inbox")

#: 权威文献目录（受版本控制）；images/ 只放二进制
CATALOG = os.path.join(DATA, "catalog.json")
SOURCES = os.path.join(DATA, "sources.json")
MANIFEST = os.path.join(DATA, "manifest.json")
INDEX_CSV = os.path.join(DATA, "index.csv")

#: 发布产物
SITE = os.path.join(DOCS, "index.html")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def move(src, dst):
    """把 src 搬到 dst，必要时建父目录。

    用 shutil.move 而非 os.rename：后者在跨卷时会抛 OSError。
    目标已存在时拒绝执行，避免静默覆盖。
    """
    if os.path.exists(dst):
        raise FileExistsError(f"目标已存在，拒绝覆盖：{dst}")
    ensure_dir(os.path.dirname(dst))
    shutil.move(src, dst)
    return dst
