"""验证词表闸门的四条行为，以及「绕开 save 直改 json」能被 validate_catalog 抓到。

这是 P0 的验收脚本，不进 CI（CI 用的是真实数据的 validate + audit）。
跑法：python scripts/test_vocab.py
"""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import index as catalog
from lib import paths
from lib import vocab

fails = []


def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + (("  " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


def main():
    recs = catalog.load()
    if not recs:
        print("目录为空")
        return 1
    tmpdir = tempfile.mkdtemp(prefix="pamphlet-vocab-")
    tmp = os.path.join(tmpdir, "catalog.json")

    print("\n[词表完整性]")
    check("STANCE 无重复", len(vocab.STANCE) == len(set(vocab.STANCE)))
    check("STANCE 与 RESERVED 不重叠", not (set(vocab.STANCE) & set(vocab.RESERVED)))
    live = {r["stance"] for r in recs if r["stance"]}
    check("数据中的取值全部已登记", not (live - set(vocab.ALL)),
          sorted(live - set(vocab.ALL))[:5])
    check("空串是合法状态", vocab.is_stance(""))

    print("\n[闸门：写入未登记值]")
    bad = [dict(recs[0], stance="这是一个未登记的值")]
    raised = None
    try:
        catalog.save(bad, path=tmp)
    except catalog.VocabularyError as e:
        raised = e
    check("save() 抛出 VocabularyError", raised is not None)
    check("错误信息指向 vocab.py", "vocab.py" in str(raised or ""))
    check("拒绝时未写出文件", not os.path.exists(tmp))

    print("\n[闸门：正常写入]")
    try:
        catalog.save(recs, path=tmp)
        ok = True
    except Exception as e:                                  # noqa: BLE001
        ok = False
        print("   ", type(e).__name__, e)
    check("60 个已登记值可写回", ok)
    check("写回后条目数不变", ok and len(catalog.load(tmp)) == len(recs))
    check("写回后可被再次校验通过", ok and not vocab.validate(catalog.load(tmp)))

    print("\n[闸门：空值合法]")
    try:
        catalog.save([dict(recs[0], stance="")], path=tmp)
        ok = True
    except Exception:                                       # noqa: BLE001
        ok = False
    check("未标注 = 空串，放行", ok)

    print("\n[绕过 save 直接改 json：由 validate_catalog 兜住]")
    # 造一份含未登记值的目录，指向临时 CATALOG，再跑校验脚本
    dirty = [dict(r) for r in recs]
    dirty[0]["stance"] = "偷偷加的值"
    os.makedirs(tmpdir, exist_ok=True)
    dirty_path = os.path.join(tmpdir, "dirty.json")
    with open(dirty_path, "w", encoding="utf-8") as f:
        json.dump([catalog.normalize(r) for r in dirty], f, ensure_ascii=False, indent=1)

    env = dict(os.environ, DSH_PAMPHLET_CATALOG=dirty_path, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, os.path.join(paths.SCRIPTS, "validate_catalog.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    check("validate_catalog 以非 0 退出", r.returncode != 0, r.returncode)
    check("指出是词表问题", "未登记" in (r.stdout or "") + (r.stderr or ""),
          (r.stdout or r.stderr or "").strip().splitlines()[-1:] or "")

    print("\n[audit_stance]")
    r = subprocess.run([sys.executable,
                        os.path.join(paths.SCRIPTS, "tools", "audit_stance.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    check("真实数据审计通过", r.returncode == 0, r.returncode)
    check("审计报告未登记项为 0", "全部取值已登记" in (r.stdout or ""))

    print("\n" + ("全部通过" if not fails else "失败：" + "、".join(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
