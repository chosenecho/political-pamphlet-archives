"""生成目录页：默认只列小册子，整本翻页，可下 PDF；单页宣传品另设开关。"""

import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")
recs = json.load(open(os.path.join(IMG, "索引.json"), encoding="utf-8"))

book = [r for r in recs if r["kind"] == "小册子"]
single = [r for r in recs if r["kind"] != "小册子"]

ORDER = ["中国", "美国", "英国", "法国", "德国"]

data = []
for r in sorted(book, key=lambda x: (ORDER.index(x["country"]) if x["country"] in ORDER else 99, str(x["year"]))):
    data.append({"kind": "book", "c": r["country"], "y": r["year"], "t": r["title"],
                 "n": int(r["pages"]), "d": r["dir"], "cv": r["cover"],
                 "pdf": r.get("pdf") or "", "u": r["url"]})
for r in single:
    data.append({"kind": "single", "c": r["country"], "y": r["year"], "t": r["title"],
                 "n": 1, "d": r["dir"], "cv": r["cover"], "pdf": "", "u": r["url"]})
for i, d in enumerate(data):
    d["i"] = i

groups = {}
for d in data:
    if d["kind"] == "book":
        groups.setdefault(d["c"], []).append(d)

sections = []
for c in ORDER:
    if c not in groups:
        continue
    items = sorted(groups[c], key=lambda x: x["y"])
    cards = []
    for d in items:
        cards.append(
            f'<figure class="c" data-i="{d["i"]}">'
            f'<img loading="lazy" src="{d["d"]}/pages/p-00001.jpg" alt="">'
            f'<figcaption><b>{d["y"]}</b> {d["t"][:44]} '
            f'<span class="pg">{d["n"]}p</span></figcaption></figure>')
    sections.append(f'<section data-c="{c}"><h2>{c} <small>{len(items)} 本</small></h2>'
                    f'<div class="grid">{"".join(cards)}</div></section>')

payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

html = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>政党宣传小册子 · 目录与阅读器</title>
<style>
:root{{color-scheme:light}}*{{box-sizing:border-box}}
body{{margin:0;padding:24px 28px 60px;background:#f7f6f3;color:#1d1d1b;
font:15px/1.6 -apple-system,"Segoe UI","Noto Sans SC",sans-serif}}
h1{{font-size:24px;margin:0 0 4px}}
h2{{font-size:15px;margin:28px 0 0;padding-top:18px;border-top:1px solid #e3e1db}}
h2 small{{color:#9a958c;font-weight:400;font-size:12.5px}}
.lede{{color:#666;margin:0 0 8px;font-size:13.5px}}
.tools{{display:flex;gap:12px;align-items:center;margin-top:12px;flex-wrap:wrap}}
#q{{width:240px;padding:7px 11px;border:1px solid #d8d5cd;border-radius:8px;font-size:14px;background:#fff}}
.tab{{padding:6px 14px;border:1px solid #d8d5cd;border-radius:999px;background:#fff;cursor:pointer;font-size:13.5px}}
.tab.on{{background:#1d1d1b;color:#fff;border-color:#1d1d1b}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(176px,1fr));gap:14px;margin-top:14px}}
.c{{margin:0;background:#fff;border:1px solid #e3e1db;border-radius:10px;overflow:hidden;cursor:pointer;
transition:box-shadow .15s,border-color .15s}}
.c:hover{{border-color:#b9b4a8;box-shadow:0 2px 10px rgba(0,0,0,.07)}}
.c img{{width:100%;display:block;aspect-ratio:2/3;object-fit:cover;background:#eee}}
figcaption{{padding:8px 10px 10px;font-size:12.5px;line-height:1.45;color:#333}}
figcaption b{{color:#981722}}
.pg{{display:inline-block;background:#eef2f7;color:#40618c;border-radius:4px;padding:0 5px;font-size:11px}}
#v{{position:fixed;inset:0;background:rgba(20,20,18,.94);display:none;z-index:50;
align-items:center;justify-content:center;flex-direction:column;padding:44px 76px 70px}}
#v.on{{display:flex}}
#v img{{max-width:100%;max-height:calc(100vh - 150px);object-fit:contain;background:#fff;
box-shadow:0 8px 40px rgba(0,0,0,.5)}}
#bar{{position:absolute;top:0;left:0;right:0;height:44px;display:flex;align-items:center;
justify-content:space-between;padding:0 16px;color:#e8e4da;font-size:13px;gap:16px}}
#bar .t{{max-width:52%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
#bar .r a{{color:#9db4d4;text-decoration:none;margin-left:14px}}
#foot{{position:absolute;bottom:0;left:0;right:0;height:56px;display:flex;align-items:center;
justify-content:center;gap:16px;color:#e8e4da;font-size:13px}}
button.nav{{background:rgba(255,255,255,.12);color:#f2efe6;border:0;border-radius:8px;
padding:7px 15px;font-size:14px;cursor:pointer}}
button.nav:hover{{background:rgba(255,255,255,.22)}}
button.nav:disabled{{opacity:.3;cursor:default}}
.zone{{position:absolute;top:44px;bottom:56px;width:26%;cursor:pointer;z-index:2}}
.zone.l{{left:0}} .zone.r{{right:0}}
#cnt{{min-width:86px;text-align:center;font-variant-numeric:tabular-nums}}
</style></head><body>
<h1>政党宣传小册子 · 目录与阅读器</h1>
<p class="lede"><b>{len(book)} 本多页小册子</b>（中国 {sum(1 for r in book if r['country']=='中国')}、美国 {sum(1 for r in book if r['country']=='美国')}、英国 {sum(1 for r in book if r['country']=='英国')}、法国 {sum(1 for r in book if r['country']=='法国')}、德国 {sum(1 for r in book if r['country']=='德国')}）。
点开即可整本翻阅，<b>← / →</b> 或点击画面两侧翻页，翻到末尾自动接下一本，<b>Esc</b> 退出。</p>
<div class="tools">
  <input id="q" placeholder="搜索标题 / 国别 / 年份">
  <span class="tab on" data-k="book">小册子 {len(book)}</span>
  <span class="tab" data-k="single">单页传单/海报 {len(single)}</span>
</div>
<div id="books">{''.join(sections)}</div>
<div id="singles" style="display:none"><p class="lede" style="margin-top:18px">单页宣传品共 {len(single)} 件，不在小册子统计内。</p></div>

<div id="v">
  <div id="bar"><span class="t"></span><span class="r"><a class="pdf" target="_blank" rel="noopener">下载 PDF</a><a class="src" target="_blank" rel="noopener">来源 ↗</a></span></div>
  <div class="zone l" data-step="-1"></div><div class="zone r" data-step="1"></div>
  <img alt="">
  <div id="foot">
    <button class="nav" data-step="-1">← 上一页</button>
    <span id="cnt"></span>
    <button class="nav" data-step="1">下一页 →</button>
  </div>
</div>

<script>
const D = {payload};
const BOOKS = D.filter(d => d.kind === 'book');
const v = document.getElementById('v');
const img = v.querySelector('img');
const cnt = document.getElementById('cnt');
const barT = v.querySelector('#bar .t');
const srcA = v.querySelector('#bar .src');
const pdfA = v.querySelector('#bar .pdf');
const prevB = v.querySelector('#foot button[data-step="-1"]');
const nextB = v.querySelector('#foot button[data-step="1"]');
const seq = BOOKS;
let cur = null, page = 1;

function path(d, p) {{
  if (d.kind !== 'book') return d.cv;
  return d.d + '/pages/p-' + String(p).padStart(5, '0') + '.jpg';
}}
function show() {{
  img.src = path(cur, page);
  barT.textContent = cur.c + ' · ' + cur.y + ' · ' + cur.t;
  srcA.href = cur.u || '#';
  if (cur.pdf) {{ pdfA.href = cur.pdf; pdfA.style.display = ''; }}
  else {{ pdfA.style.display = 'none'; }}
  cnt.textContent = page + ' / ' + cur.n;
  prevB.disabled = page <= 1 && cur.i === seq[0].i;
  nextB.disabled = page >= cur.n && cur.i === seq[seq.length - 1].i;
  if (page < cur.n) {{ const p = new Image(); p.src = path(cur, page + 1); }}
}}
function open(i) {{
  const idx = seq.findIndex(x => x.i === i);
  if (idx < 0) return;
  cur = seq[idx]; page = 1; v.classList.add('on'); show();
}}
function close() {{ v.classList.remove('on'); }}
function step(s) {{
  if (!cur) return;
  const k = seq.findIndex(x => x.i === cur.i);
  if (s > 0) {{
    if (page < cur.n) page++;
    else if (k < seq.length - 1) {{ cur = seq[k + 1]; page = 1; }}
    else return;
  }} else {{
    if (page > 1) page--;
    else if (k > 0) {{ cur = seq[k - 1]; page = cur.n; }}
    else return;
  }}
  show();
}}
document.querySelectorAll('.c').forEach(el => el.addEventListener('click', () => open(+el.dataset.i)));
document.querySelectorAll('[data-step]').forEach(el =>
  el.addEventListener('click', e => {{ e.stopPropagation(); step(+el.dataset.step); }}));
v.addEventListener('click', e => {{ if (e.target === v) close(); }});
document.addEventListener('keydown', e => {{
  if (!v.classList.contains('on')) return;
  if (e.key === 'Escape') close();
  else if (e.key === 'ArrowLeft') {{ e.preventDefault(); step(-1); }}
  else if (e.key === 'ArrowRight') {{ e.preventDefault(); step(1); }}
}});
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {{
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'));
  t.classList.add('on');
  const k = t.dataset.k;
  document.getElementById('books').style.display = k === 'book' ? '' : 'none';
  document.getElementById('singles').style.display = k === 'single' ? '' : 'none';
}}));
const q = document.getElementById('q');
q.addEventListener('input', () => {{
  const s = q.value.trim().toLowerCase();
  document.querySelectorAll('section').forEach(sec => {{
    let n = 0;
    sec.querySelectorAll('.c').forEach(c => {{
      const d = D.find(x => x.i === +c.dataset.i);
      const hit = !s || (d.c + ' ' + d.y + ' ' + d.t).toLowerCase().includes(s);
      c.style.display = hit ? '' : 'none';
      if (hit) n++;
    }});
    sec.style.display = n ? '' : 'none';
  }});
}});
</script>
</body></html>"""

open(os.path.join(IMG, "目录.html"), "w", encoding="utf-8").write(html)
print(f"目录.html：小册子 {len(book)} 本，单页 {len(single)} 件")
print("页数范围:", min(r["pages"] for r in book), "-", max(r["pages"] for r in book))
