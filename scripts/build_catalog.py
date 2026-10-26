"""生成交互式目录页：多维筛选 + 排序 + 阅读器（缩放、缩略图、键盘、手势）。

模板用占位符替换而非 f-string，避免 CSS/JS 里的大量花括号转义出错。
"""

import json
import os
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")
recs = json.load(open(os.path.join(IMG, "索引.json"), encoding="utf-8"))

book = [r for r in recs if r.get("kind") == "小册子"]
single = [r for r in recs if r.get("kind") != "小册子"]

ORDER = ["中国", "美国", "英国", "法国", "德国", "俄国", "意大利", "西班牙",
         "葡萄牙", "荷兰", "奥地利", "捷克", "波兰", "匈牙利", "瑞典", "丹麦", "比利时"]

data = []
for r in book:
    data.append({
        "k": "book", "c": r["country"], "y": str(r.get("year") or ""),
        "t": r["title"], "n": int(r.get("pages") or 1),
        "d": r["dir"], "cv": r["cover"], "st": r.get("stance") or "",
        "pdf": r["pdf"] if r.get("pdf") else "", "u": r.get("url") or "",
    })
for r in single:
    data.append({
        "k": "single", "c": r["country"], "y": str(r.get("year") or ""),
        "t": r["title"], "n": 1,
        "d": r["dir"], "cv": r["cover"], "st": "", "pdf": "", "u": r.get("url") or "",
    })
for i, d in enumerate(data):
    d["i"] = i

countries = [c for c in ORDER if any(d["c"] == c for d in data)]
countries += [c for c in sorted({d["c"] for d in data}) if c not in countries]
stances = [s for s, _ in Counter(d["st"] for d in data if d.get("st")).most_common()]

country_opts = "".join(
    f'<option value="{c}">{c}（{sum(1 for d in data if d["c"] == c)}）</option>' for c in countries)
stance_opts = "".join(
    f'<option value="{s}">{s}（{sum(1 for d in data if d["st"] == s)}）</option>' for s in stances)

TEMPLATE = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>政党宣传小册子 · 目录与阅读器</title>
<style>
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#f7f6f3;color:#1d1d1b;
  font:15px/1.6 -apple-system,"Segoe UI","Noto Sans SC",sans-serif;
  padding:0 0 80px}

/* ---------- 顶栏 ---------- */
header{position:sticky;top:0;z-index:20;background:rgba(247,246,243,.94);
  backdrop-filter:blur(8px);border-bottom:1px solid #e3e1db;padding:14px 24px 12px}
h1{font-size:20px;margin:0 0 2px}
.lede{color:#6b675f;margin:0 0 10px;font-size:13px}
.lede b{color:#1d1d1b}
.tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
#q{flex:1 1 230px;min-width:170px;padding:8px 12px;border:1px solid #d8d5cd;border-radius:8px;
  font-size:14px;background:#fff;outline:none}
#q:focus{border-color:#9a958c;box-shadow:0 0 0 3px rgba(154,149,140,.12)}
select{padding:8px 10px;border:1px solid #d8d5cd;border-radius:8px;background:#fff;
  font-size:13.5px;cursor:pointer;max-width:190px}
.seg{display:flex;border:1px solid #d8d5cd;border-radius:8px;overflow:hidden;background:#fff}
.seg button{border:0;background:transparent;padding:8px 13px;font-size:13.5px;cursor:pointer;
  color:#5b564d;border-right:1px solid #ecebe6}
.seg button:last-child{border-right:0}
.seg button.on{background:#1d1d1b;color:#fff}
#reset{border:1px solid #d8d5cd;background:#fff;border-radius:8px;padding:8px 12px;
  font-size:13.5px;cursor:pointer;color:#5b564d}
#reset:hover{border-color:#b9b4a8}
.count{color:#8b867c;font-size:13px;margin-left:auto;white-space:nowrap}

/* ---------- 卡片 ---------- */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(178px,1fr));
  gap:16px;padding:20px 24px 0}
.card{margin:0;background:#fff;border:1px solid #e3e1db;border-radius:10px;overflow:hidden;
  cursor:pointer;transition:box-shadow .15s,border-color .15s,transform .15s;
  display:flex;flex-direction:column;position:relative}
.card:hover{border-color:#b9b4a8;box-shadow:0 4px 16px rgba(0,0,0,.09);transform:translateY(-1px)}
.card .thumb{position:relative;background:#eee}
.card img{width:100%;display:block;aspect-ratio:2/3;object-fit:cover}
.card .kind{position:absolute;top:7px;left:7px;background:rgba(29,29,27,.78);color:#fff;
  font-size:11px;padding:1px 7px;border-radius:999px;letter-spacing:.02em}
.card figcaption{padding:9px 11px 11px;font-size:12.5px;line-height:1.45;color:#333;flex:1}
.card .yr{color:#981722;font-weight:600}
.card .ti{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.chips{margin-top:6px;display:flex;gap:4px;flex-wrap:wrap}
.chip{font-size:11px;padding:0 6px;border-radius:4px;background:#f0eee9;color:#6b675f}
.chip.pages{background:#eef2f7;color:#40618c}
.chip.st{background:#f6ece6;color:#9c4a1e}
.empty{grid-column:1/-1;text-align:center;color:#9a958c;padding:70px 0;font-size:14px}

/* ---------- 阅读器 ---------- */
#viewer{position:fixed;inset:0;background:#141412;display:none;z-index:100;
  grid-template-rows:auto 1fr auto auto}
#viewer.on{display:grid}
#vtop{display:flex;align-items:center;gap:14px;padding:10px 16px;color:#e8e4da;font-size:13px}
#vtitle{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#vmeta{color:#a8a297;font-size:12.5px;white-space:nowrap}
#vtop a{color:#9db4d4;text-decoration:none;white-space:nowrap}
#vtop a:hover{text-decoration:underline}
#vclose{background:rgba(255,255,255,.1);border:0;color:#e8e4da;width:32px;height:32px;
  border-radius:8px;cursor:pointer;font-size:17px;line-height:1}
#vclose:hover{background:rgba(255,255,255,.2)}

#vstage{position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center;
  touch-action:none}
#vimg{max-width:100%;max-height:100%;object-fit:contain;background:#fff;
  box-shadow:0 8px 40px rgba(0,0,0,.55);transform-origin:center center;
  transition:transform .12s ease-out;user-select:none;-webkit-user-drag:none}
#vimg.dragging{transition:none}
.hit{position:absolute;top:0;bottom:0;width:22%;z-index:3;cursor:pointer}
.hit.l{left:0}.hit.r{right:0}
.hit:hover{background:linear-gradient(90deg,rgba(255,255,255,.05),transparent)}
.hit.r:hover{background:linear-gradient(270deg,rgba(255,255,255,.05),transparent)}

#vthumbs{display:flex;gap:6px;overflow-x:auto;padding:8px 16px;background:#1b1b19;
  scrollbar-width:thin}
#vthumbs img{height:58px;width:auto;border-radius:3px;cursor:pointer;opacity:.5;
  border:1px solid transparent;flex:0 0 auto}
#vthumbs img.on{opacity:1;border-color:#c8a06a}

#vfoot{display:flex;align-items:center;gap:12px;padding:10px 16px;color:#e8e4da;
  font-size:13px;background:#1b1b19;flex-wrap:wrap}
button.nb{background:rgba(255,255,255,.1);color:#f2efe6;border:0;border-radius:7px;
  padding:6px 11px;font-size:13px;cursor:pointer;white-space:nowrap}
button.nb:hover{background:rgba(255,255,255,.2)}
button.nb:disabled{opacity:.28;cursor:default}
#slider{flex:1;min-width:110px;accent-color:#c8a06a;cursor:pointer}
#cnt{font-variant-numeric:tabular-nums;min-width:74px;text-align:center}
#zoomctl{display:flex;gap:6px;align-items:center;margin-left:auto}
#zl{min-width:46px;text-align:right;color:#a8a297;font-size:12.5px}

@media (max-width:720px){
  body{padding-bottom:60px}
  header{padding:12px 14px 10px}
  .grid{padding:14px 14px 0;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px}
  h1{font-size:17px}
  #vmeta{display:none}
  #vthumbs img{height:44px}
  #vfoot{gap:8px;padding:8px 10px}
}
</style>
</head>
<body>

<header>
  <h1>政党宣传小册子 · 目录与阅读器</h1>
  <p class="lede"><b>__NBOOK__ 本多页小册子</b> · __NSINGLE__ 件单页宣传品 · __NSTANCE__ 种政治立场。
  点开整本翻阅：<b>←/→</b> 翻页、<b>↑/↓</b> 换本、<b>+/-</b> 缩放、双击放大、滚轮缩放、<b>Esc</b> 退出。</p>
  <div class="tools">
    <input id="q" placeholder="搜索标题 / 国别 / 年份 / 立场" autocomplete="off">
    <select id="fc"><option value="">全部国别</option>__COPTS__</select>
    <select id="fs"><option value="">全部立场</option>__SOPTS__</select>
    <div class="seg" id="fk">
      <button data-k="" class="on">全部</button>
      <button data-k="book">小册子</button>
      <button data-k="single">单页</button>
    </div>
    <select id="sort">
      <option value="i">默认顺序</option>
      <option value="y-">年份 ↓</option>
      <option value="y+">年份 ↑</option>
      <option value="c">按国别</option>
      <option value="n-">页数 ↓</option>
    </select>
    <button id="reset">重置</button>
    <span class="count" id="count"></span>
  </div>
</header>

<div class="grid" id="grid"></div>

<div id="viewer">
  <div id="vtop">
    <span id="vtitle"></span>
    <span id="vmeta"></span>
    <a id="vpdf" target="_blank" rel="noopener">下载 PDF</a>
    <a id="vsrc" target="_blank" rel="noopener">来源 ↗</a>
    <button id="vclose" title="关闭 (Esc)">✕</button>
  </div>
  <div id="vstage">
    <div class="hit l" data-step="-1"></div>
    <div class="hit r" data-step="1"></div>
    <img id="vimg" alt="">
  </div>
  <div id="vthumbs"></div>
  <div id="vfoot">
    <button class="nb" id="prevbook" title="上一本 (↑)">↤ 上一本</button>
    <button class="nb" id="prevpage" data-step="-1">← 上一页</button>
    <input type="range" id="slider" min="1" max="1" value="1">
    <span id="cnt"></span>
    <button class="nb" id="nextpage" data-step="1">下一页 →</button>
    <button class="nb" id="nextbook" title="下一本 (↓)">下一本 ↦</button>
    <div id="zoomctl">
      <button class="nb" id="zout">−</button>
      <span id="zl">100%</span>
      <button class="nb" id="zin">+</button>
      <button class="nb" id="zfit">适应</button>
    </div>
  </div>
</div>

<script>
const DATA = __DATA__;
const grid = document.getElementById('grid');
let visible = [];      // 当前筛选后的条目（DOM 顺序）
let vi = -1, vp = 1;   // 阅读器：条目下标、页码
let zoom = 1, panX = 0, panY = 0;

/* ---------- 渲染卡片 ---------- */
const cards = new Map();
for (const d of DATA) {
  const el = document.createElement('figure');
  el.className = 'card';
  el.dataset.i = d.i;
  const kindTxt = d.k === 'book' ? '小册子' : '单页';
  const chips = [];
  chips.push('<span class="chip">' + d.c + '</span>');
  if (d.k === 'book') chips.push('<span class="chip pages">' + d.n + 'p</span>');
  if (d.st) chips.push('<span class="chip st">' + d.st + '</span>');
  el.innerHTML =
    '<div class="thumb"><img loading="lazy" src="' + d.cv + '" alt="">' +
    '<span class="kind">' + kindTxt + '</span></div>' +
    '<figcaption><span class="yr">' + (d.y || '—') + '</span> ' +
    '<span class="ti">' + escapeHtml(d.t) + '</span>' +
    '<div class="chips">' + chips.join('') + '</div></figcaption>';
  el.addEventListener('click', () => open(d.i));
  cards.set(d.i, el);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

/* ---------- 筛选 / 排序 ---------- */
const q = document.getElementById('q');
const fc = document.getElementById('fc');
const fs = document.getElementById('fs');
const sortSel = document.getElementById('sort');
const countEl = document.getElementById('count');
let kindFilter = '';

function sortKey(a, b, mode) {
  if (mode === 'y-') return (b.y || '0').localeCompare(a.y || '0');
  if (mode === 'y+') return (a.y || '9999').localeCompare(b.y || '9999');
  if (mode === 'c') return a.c.localeCompare(b.c, 'zh') || (a.y||'').localeCompare(b.y||'');
  if (mode === 'n-') return b.n - a.n;
  return a.i - b.i;
}

function apply() {
  const s = q.value.trim().toLowerCase();
  const c = fc.value, st = fs.value, mode = sortSel.value;

  visible = DATA.filter(d => {
    if (kindFilter && d.k !== kindFilter) return false;
    if (c && d.c !== c) return false;
    if (st && d.st !== st) return false;
    if (s) {
      const hay = (d.t + ' ' + d.c + ' ' + d.y + ' ' + d.st).toLowerCase();
      if (!hay.includes(s)) return false;
    }
    return true;
  }).sort((a, b) => sortKey(a, b, mode));

  grid.innerHTML = '';
  if (!visible.length) {
    grid.innerHTML = '<div class="empty">没有匹配的条目</div>';
  } else {
    for (const d of visible) grid.appendChild(cards.get(d.i));
  }
  countEl.textContent = visible.length + ' / ' + DATA.length + ' 条';
  syncHash();
}

fc.addEventListener('change', apply);
fs.addEventListener('change', apply);
sortSel.addEventListener('change', apply);
q.addEventListener('input', apply);
document.getElementById('reset').addEventListener('click', () => {
  q.value = ''; fc.value = ''; fs.value = ''; sortSel.value = 'i';
  kindFilter = '';
  document.querySelectorAll('#fk button').forEach(b => b.classList.toggle('on', b.dataset.k === ''));
  apply();
});
document.querySelectorAll('#fk button').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('#fk button').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  kindFilter = btn.dataset.k;
  apply();
}));

/* ---------- URL 记忆 ---------- */
function syncHash() {
  const p = new URLSearchParams();
  if (q.value.trim()) p.set('q', q.value.trim());
  if (fc.value) p.set('c', fc.value);
  if (fs.value) p.set('s', fs.value);
  if (kindFilter) p.set('k', kindFilter);
  if (sortSel.value !== 'i') p.set('sort', sortSel.value);
  const h = p.toString();
  history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
}
function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (p.get('q')) q.value = p.get('q');
  if (p.get('c')) fc.value = p.get('c');
  if (p.get('s')) fs.value = p.get('s');
  if (p.get('k')) {
    kindFilter = p.get('k');
    document.querySelectorAll('#fk button').forEach(b =>
      b.classList.toggle('on', b.dataset.k === kindFilter));
  }
  if (p.get('sort')) sortSel.value = p.get('sort');
}

/* ---------- 阅读器 ---------- */
const viewer = document.getElementById('viewer');
const vimg = document.getElementById('vimg');
const vtitle = document.getElementById('vtitle');
const vmeta = document.getElementById('vmeta');
const vsrc = document.getElementById('vsrc');
const vpdf = document.getElementById('vpdf');
const vthumbs = document.getElementById('vthumbs');
const slider = document.getElementById('slider');
const cnt = document.getElementById('cnt');
const zl = document.getElementById('zl');
const prevpage = document.getElementById('prevpage');
const nextpage = document.getElementById('nextpage');
const prevbook = document.getElementById('prevbook');
const nextbook = document.getElementById('nextbook');

function pageSrc(d, p) {
  if (d.k !== 'book') return d.cv;
  return d.d + '/pages/p-' + String(p).padStart(5, '0') + '.jpg';
}

function buildThumbs(d) {
  vthumbs.innerHTML = '';
  if (d.k !== 'book' || d.n <= 1) return;
  for (let p = 1; p <= d.n; p++) {
    const im = document.createElement('img');
    im.loading = 'lazy';
    im.src = pageSrc(d, p);
    im.dataset.p = p;
    im.addEventListener('click', e => { e.stopPropagation(); vp = p; render(); });
    vthumbs.appendChild(im);
  }
}

function resetZoom() { zoom = 1; panX = 0; panY = 0; applyZoom(); }
function applyZoom() {
  vimg.style.transform = 'translate(' + panX + 'px,' + panY + 'px) scale(' + zoom + ')';
  zl.textContent = Math.round(zoom * 100) + '%';
  vimg.style.cursor = zoom > 1 ? 'grab' : 'zoom-in';
}
function setZoom(z) {
  zoom = Math.min(6, Math.max(1, +z.toFixed(2)));
  if (zoom === 1) { panX = 0; panY = 0; }
  applyZoom();
}

function render() {
  const d = visible[vi];
  if (!d) return;
  const src = pageSrc(d, vp);
  if (vimg.dataset.src !== src) {
    vimg.dataset.src = src;
    vimg.src = src;
    resetZoom();
  }
  vtitle.textContent = d.t;
  vmeta.textContent = [d.c, d.y, d.k === 'book' ? d.n + ' 页' : '单页', d.st]
    .filter(Boolean).join(' · ');
  vsrc.href = d.u || '#';
  vsrc.style.display = d.u ? '' : 'none';
  vpdf.style.display = d.pdf ? '' : 'none';
  if (d.pdf) vpdf.href = d.pdf;

  cnt.textContent = d.k === 'book' ? (vp + ' / ' + d.n) : '单页';
  slider.style.display = d.k === 'book' && d.n > 1 ? '' : 'none';
  slider.max = d.n; slider.value = vp;

  prevpage.disabled = d.k !== 'book' || vp <= 1;
  nextpage.disabled = d.k !== 'book' || vp >= d.n;
  prevbook.disabled = vi <= 0;
  nextbook.disabled = vi >= visible.length - 1;

  document.querySelectorAll('#vthumbs img').forEach(im =>
    im.classList.toggle('on', +im.dataset.p === vp));
  const act = vthumbs.querySelector('img.on');
  if (act) act.scrollIntoView({block: 'nearest', inline: 'center', behavior: 'smooth'});

  // 预载相邻页
  for (const p of [vp + 1, vp - 1]) {
    if (p >= 1 && p <= d.n) { const im = new Image(); im.src = pageSrc(d, p); }
  }
}

function open(i) {
  const idx = visible.findIndex(x => x.i === i);
  if (idx < 0) return;
  vi = idx; vp = 1;
  buildThumbs(visible[vi]);
  viewer.classList.add('on');
  document.body.style.overflow = 'hidden';
  render();
}
function closeViewer() {
  viewer.classList.remove('on');
  document.body.style.overflow = '';
}
function stepPage(s) {
  const d = visible[vi];
  if (!d) return;
  if (s > 0) { if (vp < d.n) { vp++; render(); } else gotoBook(1, 1); }
  else { if (vp > 1) { vp--; render(); } else gotoBook(-1, -1); }
}
function gotoBook(s, edge) {
  const t = vi + s;
  if (t < 0 || t >= visible.length) return;
  vi = t;
  const d = visible[vi];
  vp = edge < 0 ? d.n : 1;
  buildThumbs(d);
  render();
}

document.getElementById('vclose').addEventListener('click', closeViewer);
document.querySelectorAll('[data-step]').forEach(el =>
  el.addEventListener('click', e => { e.stopPropagation(); stepPage(+el.dataset.step); }));
prevbook.addEventListener('click', () => gotoBook(-1, -1));
nextbook.addEventListener('click', () => gotoBook(1, 1));
slider.addEventListener('input', () => { vp = +slider.value; render(); });
document.getElementById('zin').addEventListener('click', () => setZoom(zoom * 1.25));
document.getElementById('zout').addEventListener('click', () => setZoom(zoom / 1.25));
document.getElementById('zfit').addEventListener('click', resetZoom);

/* 滚轮缩放 */
document.getElementById('vstage').addEventListener('wheel', e => {
  if (!viewer.classList.contains('on')) return;
  e.preventDefault();
  setZoom(zoom * (e.deltaY < 0 ? 1.12 : 1 / 1.12));
}, {passive: false});

/* 双击缩放 */
vimg.addEventListener('dblclick', e => {
  e.stopPropagation();
  if (zoom > 1) resetZoom(); else setZoom(2.2);
});

/* 拖拽平移 */
let dragging = false, sx = 0, sy = 0;
vimg.addEventListener('pointerdown', e => {
  if (zoom <= 1) return;
  dragging = true; sx = e.clientX - panX; sy = e.clientY - panY;
  vimg.classList.add('dragging');
  vimg.setPointerCapture(e.pointerId);
});
vimg.addEventListener('pointermove', e => {
  if (!dragging) return;
  panX = e.clientX - sx; panY = e.clientY - sy;
  applyZoom();
});
vimg.addEventListener('pointerup', e => {
  dragging = false;
  vimg.classList.remove('dragging');
});
vimg.addEventListener('click', () => { if (zoom <= 1) stepPage(1); });

/* 触摸滑动翻页 */
let tx = 0, ty = 0;
const stage = document.getElementById('vstage');
stage.addEventListener('touchstart', e => {
  if (e.touches.length !== 1) return;
  tx = e.touches[0].clientX; ty = e.touches[0].clientY;
}, {passive: true});
stage.addEventListener('touchend', e => {
  if (zoom > 1 || !e.changedTouches.length) return;
  const dx = e.changedTouches[0].clientX - tx;
  const dy = e.changedTouches[0].clientY - ty;
  if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy)) stepPage(dx < 0 ? 1 : -1);
}, {passive: true});

/* 键盘 */
document.addEventListener('keydown', e => {
  if (!viewer.classList.contains('on')) {
    if (e.key === '/' && document.activeElement !== q) { e.preventDefault(); q.focus(); }
    return;
  }
  switch (e.key) {
    case 'Escape': closeViewer(); break;
    case 'ArrowLeft': e.preventDefault(); stepPage(-1); break;
    case 'ArrowRight': e.preventDefault(); stepPage(1); break;
    case 'ArrowUp': e.preventDefault(); gotoBook(-1, -1); break;
    case 'ArrowDown': e.preventDefault(); gotoBook(1, 1); break;
    case 'Home': e.preventDefault(); vp = 1; render(); break;
    case 'End': e.preventDefault(); vp = visible[vi].n; render(); break;
    case '+': case '=': e.preventDefault(); setZoom(zoom * 1.25); break;
    case '-': e.preventDefault(); setZoom(zoom / 1.25); break;
    case '0': e.preventDefault(); resetZoom(); break;
    case 'f': case 'F':
      e.preventDefault();
      if (document.fullscreenElement) document.exitFullscreen();
      else viewer.requestFullscreen && viewer.requestFullscreen();
      break;
  }
});

/* 启动 */
readHash();
apply();
</script>
</body>
</html>"""

html = (TEMPLATE
        .replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
        .replace("__COPTS__", country_opts)
        .replace("__SOPTS__", stance_opts)
        .replace("__NBOOK__", str(len(book)))
        .replace("__NSINGLE__", str(len(single)))
        .replace("__NSTANCE__", str(len(stances))))

out = os.path.join(IMG, "目录.html")
open(out, "w", encoding="utf-8").write(html)
print(f"目录.html：小册子 {len(book)} 本，单页 {len(single)} 件，立场 {len(stances)} 种")
print(f"体积 {os.path.getsize(out)/1024:.0f} KB")
