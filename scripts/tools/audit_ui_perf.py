# -*- coding: utf-8 -*-
"""UI 性能实测：docs/index.html 在 file:// 下的首屏 / 网格 / 列表 / 筛选 / 阅读器 / 内存 / 长任务。

只读：不修改 docs/index.html、模板、images/。脚本前后各记一次 docs/index.html 的
sha256 + 页面内 BUILD 指纹，写进 JSON，便于核对数字属于哪一次构建
（本仓库的 docs/index.html 由 scripts/build_catalog.py 生成，采集期间可能被重建）。

用法：
    python scripts/tools/audit_ui_perf.py
    python scripts/tools/audit_ui_perf.py --headed
    python scripts/tools/audit_ui_perf.py --out ui-perf-report.json
    python scripts/tools/audit_ui_perf.py --only boot,reader
    python scripts/tools/audit_ui_perf.py --repeat 5

口径（把"估算"和"实测"分开）：
- 耗时全部取自页面内 performance.now() 或 CDP Performance 计数器，不用外部计时器。
- DOM 稳定 = 动作同步执行完 + 连续两次 requestAnimationFrame；每个测点 3s 兜底。
  两次 rAF 本身要 1–2 帧，所以先测一条"空动作"基线（measureFloorMs），
  筛选延迟的净值 = 实测中位数 − 基线中位数，两个数都写进报告。
- 图片字节取自磁盘文件长度（file:// 的真实字节），不用 CDP encodedDataLength
  （后者含协议分帧开销：HTML 实测 292648 而文件 274530）。
- JS 堆一律在 HeapProfiler.collectGarbage 之后读，否则 GC 抖动会读出"开阅读器后堆变小"。
- 无 CPU 节流、无网络模拟：本机双击打开的真实情形（文件已在 OS 页缓存里）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from playwright.sync_api import Error as PWError
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import paths  # noqa: E402

SITE = Path(paths.SITE)
IMAGES = Path(paths.IMAGES)
OUT_DEFAULT = Path(paths.BASE) / "ui-perf-report.json"
VIEWPORT = {"width": 1440, "height": 900}

#: 阅读器负载上限：页数最大的那本（buildThumbs/buildScroll/paintPages 的最坏情况）
BIG_BOOK = 353          # 匈牙利 89 页
SMALL_BOOK = 338        # 拉美 14 页，用来隔离"缩略图条数"这个变量


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_bytes(url: str):
    """file:// URL -> 磁盘字节数；映射不到（http/data 等）返回 None。"""
    try:
        u = urlparse(url)
        if u.scheme != "file":
            return None
        p = unquote(u.path)
        if p.startswith("/") and len(p) > 2 and p[2] == ":":
            p = p[1:]                       # Windows: /C:/... -> C:/...
        return Path(p).stat().st_size
    except OSError:
        return None


def ms(x, nd=1):
    return None if x is None else round(float(x), nd)


def median(xs):
    xs = [x for x in xs if x is not None]
    return round(float(statistics.median(xs)), 1) if xs else None


def short_path(url: str) -> str:
    """images/ 之后的部分，便于阅读与归类。"""
    mark = "/images/"
    i = url.find(mark)
    s = unquote(url[i + len(mark):]) if i >= 0 else unquote(url)[-90:]
    return s


INIT_SCRIPT = r"""
(() => {
  window.__nav = {};
  window.__lt = [];
  window.__loaf = [];
  window.__lcp = null;
  window.__obsErrors = [];
  document.addEventListener("DOMContentLoaded", () => {
    window.__nav.dcl = performance.now();
    window.__nav.domElements = document.getElementsByTagName("*").length;
  });
  window.addEventListener("load", () => { window.__nav.load = performance.now(); });
  try {
    new PerformanceObserver(list => {
      for (const e of list.getEntries())
        window.__lt.push({ start: +e.startTime.toFixed(1), dur: +e.duration.toFixed(1), name: e.name });
    }).observe({ type: "longtask", buffered: true });
  } catch (e) { window.__obsErrors.push("longtask: " + e); }
  /* LoAF 把长帧拆成 脚本 / 样式与布局 / 渲染 三段，用来判断"卡"到底卡在哪 */
  try {
    new PerformanceObserver(list => {
      for (const e of list.getEntries()) {
        const sl = e.styleAndLayoutStart
          ? +(e.startTime + e.duration - e.styleAndLayoutStart).toFixed(1) : 0;
        window.__loaf.push({
          start: +e.startTime.toFixed(1),
          dur: +e.duration.toFixed(1),
          blocking: +e.blockingDuration.toFixed(1),
          styleLayoutMs: sl,
          renderMs: e.renderStart ? +(e.startTime + e.duration - e.renderStart).toFixed(1) : 0,
          scriptMs: +e.scripts.reduce((a, s) => a + s.duration, 0).toFixed(1),
          scripts: e.scripts.map(s => ({ src: (s.sourceURL || "").slice(-40),
                                         fn: s.sourceFunctionName,
                                         dur: +s.duration.toFixed(1) })),
        });
      }
    }).observe({ type: "long-animation-frame", buffered: true });
  } catch (e) { window.__obsErrors.push("loaf: " + e); }
  try {
    new PerformanceObserver(list => {
      const es = list.getEntries();
      const e = es[es.length - 1];
      window.__lcp = { t: +e.startTime.toFixed(1), size: e.size,
                       tag: (e.element && e.element.tagName) || null };
    }).observe({ type: "largest-contentful-paint", buffered: true });
  } catch (e) { window.__obsErrors.push("lcp: " + e); }

  window.__settle = () => new Promise(resolve => {
    const t0 = performance.now();
    let done = false;
    const fin = () => { if (!done) { done = true; resolve(performance.now() - t0); } };
    requestAnimationFrame(() => requestAnimationFrame(fin));
    setTimeout(fin, 3000);
  });

  /* 动作 -> DOM 稳定 的端到端耗时 + 该窗口内新增长任务 */
  window.__measure = async fn => {
    const lt0 = window.__lt.length;
    const t0 = performance.now();
    let err = null;
    try { fn(); } catch (e) { err = String(e); }
    await window.__settle();
    const lt = window.__lt.slice(lt0);
    return { ms: +(performance.now() - t0).toFixed(1), err,
             ltCount: lt.length, ltDur: +lt.reduce((a, e) => a + e.dur, 0).toFixed(1) };
  };

  /* 只量同步 JS 成本，不含帧等待 */
  window.__sync = fn => {
    const t0 = performance.now();
    let err = null;
    try { fn(); } catch (e) { err = String(e); }
    return { ms: +(performance.now() - t0).toFixed(1), err };
  };
})();
"""

JS_STATE = r"""() => {
  const q = s => document.querySelectorAll(s);
  const imgs = [...q(".mat img")];
  let px = 0;
  for (const i of imgs) if (i.naturalWidth) px += i.naturalWidth * i.naturalHeight;
  return {
    elements: document.getElementsByTagName("*").length,
    cards: q(".card").length,
    rows: q(".row").length,
    matImgs: imgs.length,
    matImgsLoaded: imgs.filter(i => i.naturalWidth > 0).length,
    matImgsHidden: imgs.filter(i => i.hidden).length,
    coverPixels: px,
    coverDecodedMB: +(px * 4 / 1048576).toFixed(1),
    gridChildren: document.getElementById("grid").children.length,
    gridHeight: Math.round(document.getElementById("grid").getBoundingClientRect().height),
    scrollHeight: document.documentElement.scrollHeight,
    thumbs: q("#rdThumbs button").length,
    thumbsImgs: q("#rdThumbs img").length,
    scrollPages: q("#rdScroll .sc-page").length,
    fopts: q("#rail .fopt").length,
    histBars: q("#histBars button").length,
    countText: (document.getElementById("count") || {}).textContent || "",
    rdCnt: (document.getElementById("rdCnt") || {}).textContent || "",
    rdOpen: !!document.querySelector("#rd.on"),
    rdMode: (() => { const b = document.querySelector("#rdModes button.on");
                     return b ? b.dataset.mode : null; })(),
    rdImgSrc: (document.getElementById("rdImgA") || {}).src || "",
  };
}"""


class NetLog:
    """图片请求统计。

    file:// 下 performance.getEntriesByType('resource') 返回空数组（实测 0 条），
    所以只能走 CDP Network 域。
    """

    def __init__(self, cdp):
        self.cdp = cdp
        self.reqs = {}
        self.finished = {}
        self.failed = []
        cdp.on("Network.requestWillBeSent", self._on_req)
        cdp.on("Network.loadingFinished", self._on_fin)
        cdp.on("Network.loadingFailed", self._on_fail)
        cdp.send("Network.enable")

    def _on_req(self, e):
        # wallTime 是 Unix 秒，可与 time.time() 直接比；timestamp 是 CDP 单调时钟，不可混用
        self.reqs[e["requestId"]] = {"url": e["request"]["url"],
                                     "type": e.get("type"),
                                     "ts": e.get("wallTime", 0)}

    def _on_fin(self, e):
        self.finished[e["requestId"]] = e.get("encodedDataLength")

    def _on_fail(self, e):
        self.failed.append({"url": (self.reqs.get(e["requestId"]) or {}).get("url", ""),
                            "error": e.get("errorText")})

    def images(self, since=None):
        out = [{"id": k, **v} for k, v in self.reqs.items() if v["type"] == "Image"]
        if since is not None:
            out = [i for i in out if (i["ts"] or 0) >= since]
        return out

    def summary(self, since=None):
        imgs = self.images(since)
        total = 0
        unresolved = 0
        entries = []
        for i in imgs:
            b = file_bytes(i["url"])
            if b is None:
                unresolved += 1
            else:
                total += b
            entries.append({"path": short_path(i["url"]), "bytes": b})
        return {"images": len(imgs), "bytes": total,
                "bytesMB": round(total / 1048576, 2),
                "unresolved": unresolved,
                "paths": [e["path"] for e in entries],
                "entries": entries}

    def mark(self):
        """当前时刻（Unix 秒），与 CDP wallTime 同域，用于 since 过滤。"""
        return time.time()


class Perf:
    """CDP Performance 计数器：快照、差值、强制 GC 后的堆读数。"""

    KEYS = ("LayoutCount", "RecalcStyleCount", "LayoutDuration", "RecalcStyleDuration",
            "ScriptDuration", "TaskDuration", "JSHeapUsedSize", "Nodes")

    def __init__(self, cdp):
        self.cdp = cdp
        cdp.send("Performance.enable")

    def snap(self, gc=False):
        if gc:
            try:
                self.cdp.send("HeapProfiler.collectGarbage")
            except PWError:
                pass
        return {m["name"]: m["value"] for m in self.cdp.send("Performance.getMetrics")["metrics"]}

    @classmethod
    def diff(cls, a, b):
        out = {}
        for k in cls.KEYS:
            if k in a and k in b:
                d = b[k] - a[k]
                out[k] = round(d, 4) if k.endswith("Duration") else int(round(d))
        return out

    @staticmethod
    def heap(m):
        return {"heapMB": round(m["JSHeapUsedSize"] / 1048576, 2), "nodes": int(m["Nodes"])}


def open_page(browser, query=""):
    ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)[:400]))
    page.add_init_script(INIT_SCRIPT)
    cdp = ctx.new_cdp_session(page)
    net = NetLog(cdp)
    perf = Perf(cdp)
    url = SITE.as_uri() + query
    return {"ctx": ctx, "page": page, "cdp": cdp, "net": net, "perf": perf,
            "errors": errors, "url": url}


def settle(page):
    try:
        page.evaluate("() => window.__settle()")
    except PWError:
        page.wait_for_timeout(300)


def goto(page, url):
    page.goto(url, wait_until="load", timeout=120000)
    settle(page)
    page.wait_for_timeout(400)


def measure_floor(page, n=5):
    """空动作的 rAF 基线：筛选延迟里有多少只是"等两帧"。"""
    vals = []
    for _ in range(n):
        r = page.evaluate("() => window.__measure(() => {})")
        vals.append(r["ms"])
    return {"samples": vals, "median": median(vals)}


# ---------------------------------------------------------------------------
# 1. 首屏
# ---------------------------------------------------------------------------

def scenario_boot(browser):
    h = open_page(browser)
    page, perf, net, errors = h["page"], h["perf"], h["net"], h["errors"]
    t0 = time.perf_counter()
    page.goto(h["url"], wait_until="load", timeout=120000)
    wall_load = (time.perf_counter() - t0) * 1000
    settle(page)
    page.wait_for_timeout(800)

    nav = page.evaluate("() => window.__nav")
    paint = page.evaluate(
        "() => Object.fromEntries(performance.getEntriesByType('paint').map(e => [e.name, e.startTime]))")
    lcp = page.evaluate("() => window.__lcp")
    lt = page.evaluate("() => window.__lt")
    loaf = page.evaluate("() => window.__loaf")
    navtiming = page.evaluate("""() => {
      const n = performance.getEntriesByType('navigation')[0];
      if (!n) return null;
      return {responseEnd: +n.responseEnd.toFixed(1),
              domInteractive: +n.domInteractive.toFixed(1),
              domContentLoaded: +n.domContentLoadedEventEnd.toFixed(1),
              loadEventEnd: +n.loadEventEnd.toFixed(1),
              transferSize: n.transferSize, decodedBodySize: n.decodedBodySize};
    }""")
    floor = measure_floor(page)
    state = page.evaluate(JS_STATE)
    m = perf.snap(gc=True)

    # 强制布局成本：把整张网格的样式重算 + 布局单独称一次重量
    forced = page.evaluate("""() => {
      const grid = document.getElementById('grid');
      const force = () => { document.body.getBoundingClientRect(); };
      const out = {};
      grid.style.display = 'none'; document.body.getBoundingClientRect();
      let t0 = performance.now();
      grid.style.display = ''; document.body.getBoundingClientRect();
      out.relayoutAllCardsMs = +(performance.now() - t0).toFixed(1);
      const kids = [...grid.children];
      grid.replaceChildren(); force();
      t0 = performance.now();
      grid.append(...kids); force();
      out.reinsertAllCardsMs = +(performance.now() - t0).toFixed(1);

      // 逐步剥掉卡片的昂贵部分，看样式/布局成本落在哪
      const med = arr => { arr.sort((a, b) => a - b); return +arr[Math.floor(arr.length / 2)].toFixed(1); };
      const spin = (n) => {
        const t = [];
        for (let i = 0; i < n; i++) {
          const a = performance.now();
          grid.style.display = 'none'; force();
          grid.style.display = ''; force();
          t.push(performance.now() - a);
        }
        return med(t);
      };
      out.withAll = spin(5);
      const plates = [...grid.querySelectorAll('.plate')];
      plates.forEach(p => { p.style.backgroundImage = 'none'; });
      grid.querySelectorAll('.plate .frame').forEach(f => {
        f.style.boxShadow = 'none'; f.style.outline = 'none';
      });
      out.noPlateDecoration = spin(5);
      plates.forEach(p => p.remove());
      out.noPlateAtAll = spin(5);
      grid.querySelectorAll('.mat img').forEach(i => i.remove());
      out.noImages = spin(5);
      return out;
    }""")

    # 冷渲染：清掉卡片缓存后跑一次 apply()，等于 boot 首次渲染的工作量
    cold = page.evaluate("""() => {
      gcache.clear();
      const lt0 = window.__lt.length;
      const t = window.__sync(() => apply({ keepScroll: true }));
      const st = document.getElementsByTagName('*').length;
      return { ms: t.ms, elementsAfter: st, cards: document.querySelectorAll('.card').length,
               ltDur: +window.__lt.slice(lt0).reduce((a, e) => a + e.dur, 0).toFixed(1) };
    }""")
    warm = page.evaluate("() => window.__sync(() => apply({ keepScroll: true }))")

    req = net.summary()
    facts = page.evaluate("""() => ({
      records: DATA.length,
      build: (typeof BUILD === 'string' ? BUILD : null),
      stats: STATS,
      maxPages: Math.max(...DATA.map(d => d.n || 1)),
      lazyImgs: document.querySelectorAll('.mat img[loading=lazy]').length,
      cardsInDom: document.querySelectorAll('.card').length,
      observers: window.__obsErrors,
      resourceTimingEntries: performance.getEntriesByType('resource').length,
    })""")

    h["ctx"].close()
    return {
        "url": h["url"],
        "htmlBytesOnDisk": SITE.stat().st_size,
        "dcl": ms(nav.get("dcl")),
        "load": ms(nav.get("load")),
        "loadWall": ms(wall_load),
        "firstPaint": ms(paint.get("first-paint")),
        "firstContentfulPaint": ms(paint.get("first-contentful-paint")),
        "lcp": {"ms": ms(lcp["t"]) if lcp else None,
                "size": lcp["size"] if lcp else None,
                "tag": lcp["tag"] if lcp else None},
        "domElementsAtDCL": nav.get("domElements"),
        "domElements": state["elements"],
        "cards": state["cards"],
        "gridChildren": state["gridChildren"],
        "gridHeight": state["gridHeight"],
        "scrollHeight": state["scrollHeight"],
        "matImgElements": state["matImgs"],
        "matImgsLoaded": state["matImgsLoaded"],
        "coverDecodedMB": state["coverDecodedMB"],
        "railOptions": state["fopts"],
        "histBars": state["histBars"],
        "initialImageRequests": req["images"],
        "initialImageBytes": req["bytes"],
        "initialImageMB": req["bytesMB"],
        "initialImageUnresolved": req["unresolved"],
        "coldApplyMs": cold["ms"],
        "coldApplyLongTaskMs": cold["ltDur"],
        "warmApplyMs": warm["ms"],
        "measureFloorMs": floor["median"],
        "measureFloorSamples": floor["samples"],
        "navigationTiming": navtiming,
        "forcedLayout": forced,
        "longTasks": {"count": len(lt), "totalMs": ms(sum(e["dur"] for e in lt)), "entries": lt},
        "loaf": loaf,
        "perf": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k in Perf.KEYS},
        "dataFacts": facts,
        "errors": errors,
    }


def scenario_boot_variance(browser, runs=6):
    """首屏 DCL 的方差 + 卡片数的缩放关系。

    同一份文件在不同次打开之间 DCL 会成倍跳动（首次打开 vs 之后），
    单次读数不能当结论，所以分开报 median / min / max；另外用 hash 预置
    筛选把卡片数压到 0 / 中 / 全量，看 DCL 随卡片数怎么长。
    """
    base = SITE.as_uri()
    cases = [("0 张卡", "#q=zzzzzz"), ("搜索「海报」", "#q=" + "海报"), ("全量", "")]

    def one(page):
        page.add_init_script("""window.__n = {};
          document.addEventListener('DOMContentLoaded', () => {
            window.__n.dcl = performance.now();
            window.__n.el = document.getElementsByTagName('*').length;
            window.__n.cards = document.querySelectorAll('.card').length;
          });""")

    out = {"fullLoadRuns": [], "byCardCount": []}
    for _ in range(runs):
        page = browser.new_page(viewport=VIEWPORT)
        one(page)
        page.goto(base, wait_until="load", timeout=120000)
        page.wait_for_timeout(180)
        out["fullLoadRuns"].append(round(page.evaluate("() => window.__n.dcl"), 1))
        page.close()

    for label, frag in cases:
        vals, el, cards = [], None, None
        for _ in range(4):
            page = browser.new_page(viewport=VIEWPORT)
            one(page)
            page.goto(base + frag, wait_until="load", timeout=120000)
            page.wait_for_timeout(180)
            n = page.evaluate("() => window.__n")
            vals.append(round(n["dcl"], 1))
            el, cards = n["el"], n["cards"]
            page.close()
        out["byCardCount"].append({"label": label, "cards": cards, "domElements": el,
                                   "dclMedian": median(vals), "samples": vals})

    d = out["fullLoadRuns"]
    out["fullLoadSummary"] = {"median": median(d), "min": min(d), "max": max(d), "runs": len(d)}
    return out


def scenario_ab_fix(browser, runs=4):
    """A/B：把候选修复套在临时副本上量 DCL，验证"首屏慢在哪"。

    只用 tempfile 里的副本，docs/index.html 一个字节都不改。
    这是把"根因"从相关性变成因果的那一步：同一节点数、只改渲染方式。
    """
    import tempfile

    src = SITE.read_text(encoding="utf-8")
    variants = {"A_baseline": src}

    b = src.replace("</style>", "#grid{display:none!important}</style>")
    variants["B_grid_not_laid_out"] = b          # 卡片仍在 DOM，但首屏不参与布局

    c = src.replace("</style>",
                    ".card{content-visibility:auto;"
                    "contain-intrinsic-size:auto 320px}</style>")
    variants["C_card_content_visibility"] = c    # 候选修复

    d = src.replace(
        'el.innerHTML =\n    `<span class="mat">${plate(d)}',
        'el.innerHTML =\n    `<span class="mat"><span class="plate-x"></span>')
    variants["D_simplified_card"] = d            # 少一层占位封面 DOM

    def run(uri):
        page = browser.new_page(viewport=VIEWPORT)
        page.add_init_script("""window.__n = {};
          document.addEventListener('DOMContentLoaded', () => {
            window.__n.dcl = performance.now();
            window.__n.el = document.getElementsByTagName('*').length;
            window.__n.cards = document.querySelectorAll('.card').length;
          });""")
        page.goto(uri, wait_until="load", timeout=120000)
        page.wait_for_timeout(150)
        n = page.evaluate("() => window.__n")
        page.close()
        return n

    results = {}
    with tempfile.TemporaryDirectory(prefix="ui-perf-ab-") as td:
        uris = {}
        for name, text in variants.items():
            p = Path(td) / (name + ".html")
            p.write_text(text, encoding="utf-8")
            uris[name] = p.resolve().as_uri()

        run(uris["A_baseline"])                  # 预热，去掉首次冷启动
        for name, uri in uris.items():
            vals, el, cards = [], None, None
            for _ in range(runs):
                n = run(uri)
                vals.append(round(n["dcl"], 1))
                el, cards = n["el"], n["cards"]
            results[name] = {"dclMedian": median(vals), "samples": vals,
                             "domElements": el, "cards": cards}

    base = results["A_baseline"]["dclMedian"]
    for k, v in results.items():
        if v["dclMedian"] and base:
            v["savingVsBaselineMs"] = round(base - v["dclMedian"], 1)
            v["savingVsBaselinePct"] = round((base - v["dclMedian"]) / base * 100, 1)
    return {"runsPerVariant": runs, "variants": results,
            "note": "临时副本实验，docs/index.html 未改动"}


# ---------------------------------------------------------------------------
# 2. 网格全量滚动
# ---------------------------------------------------------------------------

def scenario_grid_scroll(browser):
    h = open_page(browser)
    page, perf, net, errors = h["page"], h["perf"], h["net"], h["errors"]
    goto(page, h["url"])

    before = net.summary()
    m0 = perf.snap(gc=True)
    st0 = page.evaluate(JS_STATE)
    lt0 = page.evaluate("() => window.__lt.length")

    steps = page.evaluate("""async () => {
      const h = document.documentElement.scrollHeight;
      const vh = window.innerHeight;
      let n = 0;
      for (let y = 0; y < h; y += vh) {
        window.scrollTo(0, y);
        await new Promise(r => setTimeout(r, 90));
        n++;
      }
      window.scrollTo(0, h);
      await new Promise(r => setTimeout(r, 700));
      return { steps: n, atBottom: Math.round(window.scrollY), height: h };
    }""")
    settle(page)
    page.wait_for_timeout(400)

    m1 = perf.snap(gc=True)
    st1 = page.evaluate(JS_STATE)
    after = net.summary()
    lt = page.evaluate("() => window.__lt")

    page.evaluate("() => window.scrollTo(0, 0)")
    settle(page)
    page.wait_for_timeout(200)
    st2 = page.evaluate(JS_STATE)
    m2 = perf.snap()

    new_entries = after["entries"][len(before["entries"]):]
    new_bytes = sum(e["bytes"] or 0 for e in new_entries)
    long_tasks = lt[lt0:]
    h["ctx"].close()
    return {
        "steps": steps["steps"],
        "scrollHeight": steps["height"],
        "domElementsBefore": st0["elements"],
        "domElementsAfter": st1["elements"],
        "peakDomElements": max(st0["elements"], st1["elements"], st2["elements"]),
        "cards": st1["cards"],
        "gridChildren": st1["gridChildren"],
        "matImgElements": st1["matImgs"],
        "matImgsLoadedAfterScroll": st1["matImgsLoaded"],
        "coversDecodedMB_afterScroll": st1["coverDecodedMB"],
        "imgRequestsBeforeScroll": before["images"],
        "imgRequestsAfterScroll": after["images"],
        "imgRequestsAdded": after["images"] - before["images"],
        "imgBytesBeforeMB": before["bytesMB"],
        "imgBytesAddedMB": round(new_bytes / 1048576, 2),
        "imgBytesAfterMB": after["bytesMB"],
        "imgSampleAdded": [e["path"] for e in new_entries[:3]],
        "layoutCountDuringScroll": int(m1["LayoutCount"] - m0["LayoutCount"]),
        "recalcStyleCountDuringScroll": int(m1["RecalcStyleCount"] - m0["RecalcStyleCount"]),
        "layoutDurationDuringScroll": round(m1["LayoutDuration"] - m0["LayoutDuration"], 3),
        "taskDurationDuringScroll": round(m1["TaskDuration"] - m0["TaskDuration"], 3),
        "longTasksDuringScroll": {"count": len(long_tasks),
                                  "totalMs": ms(sum(e["dur"] for e in long_tasks)),
                                  "entries": long_tasks},
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 3. 列表视图
# ---------------------------------------------------------------------------

def scenario_list_view(browser):
    h = open_page(browser)
    page, perf, errors = h["page"], h["perf"], h["errors"]
    goto(page, h["url"])
    floor = measure_floor(page)

    m0 = perf.snap(gc=True)
    to_list = page.evaluate(
        """() => window.__measure(() => document.querySelector('#views button[data-view="list"]').click())""")
    st_list = page.evaluate(JS_STATE)
    m1 = perf.snap()

    to_grid = page.evaluate(
        """() => window.__measure(() => document.querySelector('#views button[data-view="grid"]').click())""")
    to_list2 = page.evaluate(
        """() => window.__measure(() => document.querySelector('#views button[data-view="list"]').click())""")

    # 列表 + 搜索高亮（hl() 每行编译一次正则）
    with_q = page.evaluate("""() => window.__measure(() => {
      const el = document.getElementById('q');
      el.value = '海报';
      el.dispatchEvent(new Event('input', { bubbles: true }));
      st.q = '海报'; st.terms = ['海报'];
      apply({ keepScroll: true });
    })""")
    st_q = page.evaluate(JS_STATE)

    # 纯 JS：同样切一次列表但不等帧
    sync_list = page.evaluate(
        """() => window.__sync(() => document.querySelector('#views button[data-view="list"]').click())""")
    lt = page.evaluate("() => window.__lt")
    h["ctx"].close()
    return {
        "measureFloorMs": floor["median"],
        "switchToGridTo_List_ms": to_list.get("ms"),
        "switchToListLongTaskMs": to_list.get("ltDur"),
        "rows": st_list["rows"],
        "domElementsInList": st_list["elements"],
        "listLayoutCount": int(m1["LayoutCount"] - m0["LayoutCount"]),
        "listRecalcStyleCount": int(m1["RecalcStyleCount"] - m0["RecalcStyleCount"]),
        "listLayoutDuration": round(m1["LayoutDuration"] - m0["LayoutDuration"], 3),
        "listScriptDuration": round(m1["ScriptDuration"] - m0["ScriptDuration"], 3),
        "switchBackToGridMs": to_grid.get("ms"),
        "switchToListAgainMs": to_list2.get("ms"),
        "syncRebuildMs": sync_list.get("ms"),
        "listWithQueryMs": with_q.get("ms"),
        "rowsWithQuery": st_q["rows"],
        "listQueryDeltaVsBase": (round(with_q["ms"] - floor["median"], 1)
                                 if with_q.get("ms") and floor["median"] is not None else None),
        "longTasks": {"count": len(lt), "totalMs": ms(sum(e["dur"] for e in lt))},
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 4. 筛选响应
# ---------------------------------------------------------------------------

FILTER_ACTIONS = [
    ("country", "法国", """() => document.querySelector('#fCountry .fopt[data-v="法国"]').click()"""),
    ("decade", "1930s", """() => [...document.querySelectorAll('#histBars button')].find(x => x.dataset.dec === '1930').click()"""),
    ("kind", "小册子", """() => document.querySelector('#fKind .fopt[data-v="book"]').click()"""),
    ("stance", "社会主义", """() => document.querySelector('#fStance .fopt[data-v="社会主义"]').click()"""),
    ("sort", "页数↓（439 全量重排）", """() => { const s = document.getElementById('sort'); s.value = 'n-'; s.dispatchEvent(new Event('change', { bubbles: true })); }"""),
    ("search", "海报", """() => { const el = document.getElementById('q'); el.value = '海报'; el.dispatchEvent(new Event('input', { bubbles: true })); }"""),
    ("reset", "清除筛选（回到 439）", """() => resetAll()"""),
]


def scenario_filter(browser, repeats=3):
    h = open_page(browser)
    page, errors = h["page"], h["errors"]
    goto(page, h["url"])
    floor = measure_floor(page, 7)

    pure = page.evaluate("""() => {
      const out = [];
      for (let i = 0; i < 5; i++) out.push(window.__sync(() => apply({ keepScroll: true })).ms);
      return out;
    }""")

    samples = {}
    for name, label, js in FILTER_ACTIONS:
        rows = []
        syncs = []
        for _ in range(repeats):
            page.evaluate("() => resetAll()")
            settle(page)
            page.wait_for_timeout(260)          # 让 resetAll 自己的长任务散掉，别污染下一样本
            # 先量纯 JS 成本（同一次动作，不含等帧）
            s = page.evaluate("(src) => { const f = eval('(' + src + ')'); return window.__sync(f); }", js)
            syncs.append(s["ms"])
            st_after_sync = page.evaluate(JS_STATE)
            page.evaluate("() => resetAll()")
            settle(page)
            page.wait_for_timeout(120)
            r = page.evaluate("(src) => window.__measure(eval('(' + src + ')'))", js)
            rows.append({"ms": r.get("ms"), "err": r.get("err"), "ltDur": r.get("ltDur", 0),
                         "cards": st_after_sync["cards"], "rows": st_after_sync["rows"],
                         "countText": st_after_sync["countText"].strip()})
            page.evaluate("() => resetAll()")
            settle(page)
        good = [r["ms"] for r in rows if r["ms"] is not None]
        samples[name] = {
            "label": label,
            "samples": good,
            "median": median(good),
            "syncJsMedian": median(syncs),
            "syncJsSamples": syncs,
            "netOfFrameFloor": (round(median(good) - floor["median"], 1)
                                if good and floor["median"] is not None else None),
            "min": min(good) if good else None,
            "max": max(good) if good else None,
            "longTaskMs": round(sum(r["ltDur"] for r in rows), 1),
            "resultCards": rows[0]["cards"],
            "resultRows": rows[0]["rows"],
            "countText": rows[0]["countText"],
            "errors": [r["err"] for r in rows if r["err"]],
        }
        page.evaluate("() => resetAll()")
        settle(page)

    all_ms = [v for s in samples.values() for v in s["samples"]]
    st = page.evaluate(JS_STATE)
    h["ctx"].close()
    return {
        "measureFloorMs": floor["median"],
        "measureFloorSamples": floor["samples"],
        "pureApplyMs": pure,
        "pureApplyMedian": median(pure),
        "byAction": samples,
        "overallMedianMs": median(all_ms),
        "railOptions": st["fopts"],
        "histBars": st["histBars"],
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 5+6. 阅读器与内存
# ---------------------------------------------------------------------------

def open_reader_by_card(page, i):
    return page.evaluate(
        "(i) => window.__measure(() => document.querySelector('.card[data-i=\"' + i + '\"]').click())", i)


def scenario_reader(browser):
    h = open_page(browser)
    page, perf, net, errors = h["page"], h["perf"], h["net"], h["errors"]
    goto(page, h["url"])

    m_before = perf.snap(gc=True)
    st_before = page.evaluate(JS_STATE)
    lt_before = page.evaluate("() => window.__lt.length")
    fails_before = len(net.failed)
    t_before = net.mark()
    req_before = net.summary()

    opened = open_reader_by_card(page, BIG_BOOK)
    settle(page)
    page.wait_for_timeout(1500)                 # 让缩略图/主图的请求与解码落地

    m_open = perf.snap(gc=True)
    st_open = page.evaluate(JS_STATE)
    req_open = net.summary(t_before)
    # 解码像素：缩略图网格单元只有 ~49×65 px，却按原图 1600×2500 解码
    decode = page.evaluate("""() => {
      const ts = [...document.querySelectorAll('#rdThumbs img')];
      let px = 0; ts.forEach(i => { if (i.naturalWidth) px += i.naturalWidth * i.naturalHeight; });
      const b0 = document.querySelector('#rdThumbs button');
      const r = b0 ? b0.getBoundingClientRect() : {width: 0, height: 0};
      const a = document.getElementById('rdImgA');
      return {
        thumbCount: ts.length,
        thumbsDecoded: ts.filter(i => i.naturalWidth > 0).length,
        thumbSourceMP: +(px / 1e6).toFixed(1),
        thumbDecodedMB: +(px * 4 / 1048576).toFixed(1),
        thumbSourceSample: ts.slice(0, 3).map(i => i.naturalWidth + 'x' + i.naturalHeight),
        cellW: Math.round(r.width), cellH: Math.round(r.height),
        mainNatural: a.naturalWidth + 'x' + a.naturalHeight,
        mainDecodedMB: +((a.naturalWidth * a.naturalHeight * 4) / 1048576).toFixed(1),
      };
    }""")

    # 归因：这次打开到底拉了哪些图
    paths = req_open["paths"]
    thumbs = [p for p in paths if "/pages/" in p or p.startswith("小册子/")]
    req_on_open = {"images": req_open["images"], "bytesMB": req_open["bytesMB"],
                   "thumbLike": len(thumbs), "sample": paths[:3]}

    # 单页翻页 × 5（每次换一张整页图）
    steps = []
    for _ in range(5):
        tb = net.mark()
        r = page.evaluate("() => window.__measure(() => document.getElementById('rdNextPage').click())")
        settle(page)
        page.wait_for_timeout(220)
        req = net.summary(tb)
        r["imgRequests"] = req["images"]
        r["imgBytesMB"] = req["bytesMB"]
        steps.append(r)
    m_steps = perf.snap()

    end = page.evaluate(
        """() => window.__measure(() => document.dispatchEvent(new KeyboardEvent('keydown', {key: 'End', bubbles: true})))""")
    settle(page)
    page.wait_for_timeout(500)
    st_end = page.evaluate(JS_STATE)
    m_end = perf.snap(gc=True)

    spread = page.evaluate(
        """() => window.__measure(() => document.querySelector('#rdModes button[data-mode="spread"]').click())""")
    settle(page)
    page.wait_for_timeout(600)
    st_spread = page.evaluate(JS_STATE)

    # 双页模式在末页会算到 n+1：spreadPair(d, si) 用 si*2 / si*2+1，siForPage(d, n) = ceil(n/2)
    # 89 页 -> si=45 -> a=90, b=91，两个都越界
    spread_edge = page.evaluate("""() => {
      const d = byId.get(rd.i);
      const si = siForPage(d, d.n);
      return {pages: d.n, siForLastPage: si, pairAtLastSpread: spreadPair(d, si),
              maxPairs: totalSpreads(d), overflow: spreadPair(d, si).filter(p => p > d.n)};
    }""")
    t_sp = net.mark()
    fails_before_spread = len(net.failed)
    page.evaluate("""() => {
      const d = byId.get(rd.i);
      rd.si = totalSpreads(d) - 1;
      rd.p = spreadPair(d, rd.si)[0];
      resetZoom(); paintPages(d); syncFoot();
    }""")
    settle(page)
    page.wait_for_timeout(700)
    st_spread_last = page.evaluate(JS_STATE)
    spread_reqs = net.summary(t_sp)
    spread_fail = net.failed[fails_before_spread:]
    spread_miss_visible = page.evaluate(
        "() => document.getElementById('rdMiss').classList.contains('on')")

    t_scroll = net.mark()
    scroll = page.evaluate(
        """() => window.__measure(() => document.querySelector('#rdModes button[data-mode="scroll"]').click())""")
    settle(page)
    page.wait_for_timeout(1000)
    st_scroll = page.evaluate(JS_STATE)
    req_scroll = net.summary(t_scroll)

    back = page.evaluate(
        """() => window.__measure(() => document.querySelector('#rdModes button[data-mode="page"]').click())""")
    settle(page)
    page.wait_for_timeout(300)
    m_after = perf.snap(gc=True)

    page.evaluate("() => document.getElementById('rdClose').click()")
    settle(page)
    page.wait_for_timeout(600)
    m_closed = perf.snap(gc=True)
    st_closed = page.evaluate(JS_STATE)

    # 对照：14 页那本，隔离"缩略图条数"变量
    small = open_reader_by_card(page, SMALL_BOOK)
    settle(page)
    page.wait_for_timeout(600)
    st_small = page.evaluate(JS_STATE)
    small_step = page.evaluate("() => window.__measure(() => document.getElementById('rdNextPage').click())")
    settle(page)
    lt = page.evaluate("() => window.__lt")
    lt_reader = lt[lt_before:]
    fails_total = net.failed[fails_before:]
    h["ctx"].close()

    steps_ms = [r["ms"] for r in steps if r.get("ms") is not None]
    return {
        "item": {"id": BIG_BOOK, "pages": 89},
        "open": {
            "ms": opened.get("ms"),
            "longTaskMs": opened.get("ltDur"),
            "domElementsBefore": st_before["elements"],
            "domElementsAfter": st_open["elements"],
            "domElementsDelta": st_open["elements"] - st_before["elements"],
            "thumbs": st_open["thumbs"],
            "thumbsImgs": st_open["thumbsImgs"],
            "requestsOnOpen": req_on_open,
            "thumbnailDecode": decode,
            "layoutCount": int(m_open["LayoutCount"] - m_before["LayoutCount"]),
            "recalcStyleCount": int(m_open["RecalcStyleCount"] - m_before["RecalcStyleCount"]),
            "layoutDuration": round(m_open["LayoutDuration"] - m_before["LayoutDuration"], 3),
            "scriptDuration": round(m_open["ScriptDuration"] - m_before["ScriptDuration"], 3),
            "taskDuration": round(m_open["TaskDuration"] - m_before["TaskDuration"], 3),
        },
        "pageStep": {
            "samples": steps_ms,
            "median": median(steps_ms),
            "longTaskMs": round(sum(r.get("ltDur", 0) for r in steps), 1),
            "imgRequestsPerStep": [r.get("imgRequests") for r in steps],
            "imgMBPerStep": [r.get("imgBytesMB") for r in steps],
            "layoutCount": int(m_steps["LayoutCount"] - m_open["LayoutCount"]),
            "recalcStyleCount": int(m_steps["RecalcStyleCount"] - m_open["RecalcStyleCount"]),
            "layoutDuration": round(m_steps["LayoutDuration"] - m_open["LayoutDuration"], 3),
        },
        "jumpToLastPage": {
            "ms": end.get("ms"),
            "counter": st_end["rdCnt"].strip(),
            "layoutCount": int(m_end["LayoutCount"] - m_steps["LayoutCount"]),
            "layoutDuration": round(m_end["LayoutDuration"] - m_steps["LayoutDuration"], 3),
        },
        "spreadMode": {
            "ms": spread.get("ms"),
            "counter": st_spread["rdCnt"].strip(),
            "counterAtLastSpread": st_spread_last["rdCnt"].strip(),
            "geometry": spread_edge,
            "requestsForLastSpread": {"images": spread_reqs["images"], "bytesMB": spread_reqs["bytesMB"]},
            "failedImageRequests": len(spread_fail),
            "missOverlayShown": spread_miss_visible,
        },
        "scrollMode": {
            "ms": scroll.get("ms"),
            "pageImgsCreated": st_scroll["scrollPages"],
            "imgRequests": req_scroll["images"],
            "imgMB": req_scroll["bytesMB"],
        },
        "backToPageMode": {"ms": back.get("ms")},
        "smallBookControl": {
            "id": SMALL_BOOK, "openMs": small.get("ms"),
            "thumbs": st_small["thumbs"], "pageStepMs": small_step.get("ms"),
        },
        "memory": {
            "before": {**perf.heap(m_before), "domElements": st_before["elements"]},
            "readerOpen": {**perf.heap(m_open), "domElements": st_open["elements"]},
            "afterScrollMode": {**perf.heap(m_after)},
            "afterClose": {**perf.heap(m_closed), "domElements": st_closed["elements"]},
            "retainedDomElementsAfterClose": st_closed["elements"] - st_before["elements"],
            "retainedThumbsAfterClose": st_closed["thumbs"],
            "retainedScrollPagesAfterClose": st_closed["scrollPages"],
            "heapDeltaOnOpenMB": round((m_open["JSHeapUsedSize"] - m_before["JSHeapUsedSize"]) / 1048576, 2),
            "heapDeltaAfterCloseMB": round((m_closed["JSHeapUsedSize"] - m_before["JSHeapUsedSize"]) / 1048576, 2),
            "gc": "每次读数前执行 HeapProfiler.collectGarbage",
        },
        "longTasks": {"count": len(lt_reader),
                      "totalMs": ms(sum(e["dur"] for e in lt_reader)),
                      "entries": lt_reader,
                      "window": "从打开阅读器到关闭后复位，含各模式切换"},
        "imageRequestFailures": {"count": len(fails_total),
                                 "sample": [short_path(f["url"]) for f in fails_total[:3]],
                                 "error": fails_total[0]["error"] if fails_total else None},
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 7. 图片缺失路径
# ---------------------------------------------------------------------------

def scenario_missing(browser, baseline_mb=None):
    h = open_page(browser, query="?assets=/nope/")
    page, perf, net, errors = h["page"], h["perf"], h["net"], h["errors"]
    page.goto(h["url"], wait_until="load", timeout=120000)
    settle(page)
    page.wait_for_timeout(1500)

    nav = page.evaluate("() => window.__nav")
    lt = page.evaluate("() => window.__lt")
    st = page.evaluate(JS_STATE)
    m = perf.snap(gc=True)
    failed = net.failed
    imgs = net.summary()
    h["ctx"].close()
    return {
        "url": h["url"],
        "dcl": ms(nav.get("dcl")),
        "load": ms(nav.get("load")),
        "domElements": st["elements"],
        "cards": st["cards"],
        "matImgElements": st["matImgs"],
        "imgsHiddenByError": st["matImgsHidden"],
        "imgRequests": imgs["images"],
        "failedRequests": len(failed),
        "failureMode": failed[0]["error"] if failed else None,
        "failedSample": [short_path(f["url"]) for f in failed[:3]],
        "longTasks": {"count": len(lt), "totalMs": ms(sum(e["dur"] for e in lt))},
        "perf": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k in Perf.KEYS},
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

SCENARIOS = {
    "boot": scenario_boot,
    "boot_variance": scenario_boot_variance,
    "ab_fix": scenario_ab_fix,
    "grid_scroll": scenario_grid_scroll,
    "list": scenario_list_view,
    "filter": scenario_filter,
    "reader": scenario_reader,
    "missing": scenario_missing,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT_DEFAULT), help="JSON 输出路径")
    ap.add_argument("--headed", action="store_true", help="显示窗口（默认 headless）")
    ap.add_argument("--only", default="", help="只跑指定场景，逗号分隔：" + ",".join(SCENARIOS))
    ap.add_argument("--repeat", type=int, default=3, help="筛选动作重复次数（取中位数）")
    args = ap.parse_args()

    wanted = [s.strip() for s in args.only.split(",") if s.strip()] or list(SCENARIOS)
    unknown = [s for s in wanted if s not in SCENARIOS]
    if unknown:
        print("未知场景：", unknown, "可选：", list(SCENARIOS))
        return 2

    before = {"sha256": sha256_file(SITE), "bytes": SITE.stat().st_size,
              "mtime": SITE.stat().st_mtime}
    report = {
        "generated": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "site": str(SITE),
        "siteBytes": before["bytes"],
        "viewport": VIEWPORT,
        "throttling": "none（本机 file://，无 CPU 降速、无网络模拟）",
        "phases": {},
        "notMeasured": [],
    }

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=not args.headed)
        except PWError as e:
            print("Chromium 启动失败：", e)
            print("请先运行：python -m playwright install chromium")
            return 2
        report["browser"] = f"Chromium {browser.version}"
        for name in wanted:
            print(f"[{name}] 测量中 …", flush=True)
            t0 = time.perf_counter()
            try:
                if name == "filter":
                    report["phases"][name] = scenario_filter(browser, repeats=args.repeat)
                elif name == "missing":
                    report["phases"][name] = scenario_missing(browser)
                else:
                    report["phases"][name] = SCENARIOS[name](browser)
            except Exception as e:      # 单项失败不中断整批，但必须如实记录
                report["phases"][name] = {"error": f"{type(e).__name__}: {e}"}
                report["notMeasured"].append({"phase": name, "reason": f"{type(e).__name__}: {e}"})
                print(f"  失败：{type(e).__name__}: {e}")
            print(f"  用时 {time.perf_counter() - t0:.1f}s", flush=True)
        browser.close()

    after = {"sha256": sha256_file(SITE), "bytes": SITE.stat().st_size,
             "mtime": SITE.stat().st_mtime}
    report["readOnly"] = {
        "sha256Before": before["sha256"],
        "sha256After": after["sha256"],
        "bytesBefore": before["bytes"],
        "bytesAfter": after["bytes"],
        "unchanged": before["sha256"] == after["sha256"],
    }
    if before["sha256"] != after["sha256"]:
        report["notMeasured"].append({
            "phase": "build-stability",
            "reason": "采集期间 docs/index.html 被重建（字节 %d -> %d）；本报告数字对应采集期间的构建"
                      % (before["bytes"], after["bytes"]),
        })

    out = Path(args.out)
    if not out.is_absolute():
        out = Path(paths.BASE) / out
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("=" * 70)
    print(f"JSON -> {out}")
    print(f"docs/index.html 采集前后一致：{report['readOnly']['unchanged']}")
    boot = report["phases"].get("boot") or {}
    if boot and "error" not in boot:
        print(f"  首屏 DCL {boot['dcl']} ms / load {boot['load']} ms / DOM {boot['domElements']} 节点")
    if report["notMeasured"]:
        print("未测到：", json.dumps(report["notMeasured"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
