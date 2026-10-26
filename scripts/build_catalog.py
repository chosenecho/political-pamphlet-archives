"""生成带翻页阅读器的目录页：点开条目后可左右翻页，支持键盘。"""

import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "images")
recs = json.load(open(os.path.join(IMG, "索引.json"), encoding="utf-8"))

ORDER = ["中国", "俄国", "德国", "法国", "英国", "美国", "意大利", "西班牙",
         "葡萄牙", "荷兰", "奥地利", "捷克", "波兰", "日本", "印度", "拉美"]

data = []
for i, r in enumerate(recs):
    n = int(r.get("pages") or 1)
    item = {
        "i": i,
        "c": r["country"],
        "y": str(r["year"]),
        "t": r["title"],
        "n": n,
        "d": r["dir"],
        "cv": r["cover"],
        "u": r["url"],
        "s": (r.get("publisher") or r.get("license") or r.get("credit") or "")[:60],
    }
    data.append(item)

payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

groups = {}
for d in data:
    groups.setdefault(d["c"], []).append(d)

sections = []
for c in ORDER:
    if c not in groups:
        continue
    items = sorted(groups[c], key=lambda x: x["y"])
    cards = []
    for d in items:
        cover = d["cv"]
        badge = f'<span class="pg">{d["n"]}p</span>' if d["n"] > 1 else ""
        cards.append(
            f'<figure class="c" data-i="{d["i"]}">'
            f'<img loading="lazy" src="{cover}" alt="">'
            f'<figcaption><b>{d["y"]}</b> {d["t"][:46]} {badge}<br>'
            f'<span>{d["s"]}</span></figcaption></figure>')
    sections.append(
        f'<section data-c="{c}"><h2>{c} <small>{len(items)} 件</small></h2>'
        f'<div class="grid">{"".join(cards)}</div></section>')

html = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>政党宣传品 · 目录与阅读器</title>
<style>
:root{{color-scheme:light}}
*{{box-sizing:border-box}}
body{{margin:0;padding:24px 28px 60px;background:#f7f6f3;color:#1d1d1b;
font:15px/1.6 -apple-system,"Segoe UI","Noto Sans SC",sans-serif}}
h1{{font-size:24px;margin:0 0 4px}}
h2{{font-size:15px;margin:30px 0 0;padding-top:18px;border-top:1px solid #e3e1db}}
h2 small{{color:#9a958c;font-weight:400;font-size:12.5px}}
.lede{{color:#666;margin:0 0 6px;font-size:13.5px}}
#q{{margin-top:14px;width:260px;padding:7px 11px;border:1px solid #d8d5cd;border-radius:8px;
font-size:14px;background:#fff}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(176px,1fr));gap:14px;margin-top:14px}}
.c{{margin:0;background:#fff;border:1px solid #e3e1db;border-radius:10px;overflow:hidden;cursor:pointer;
transition:box-shadow .15s,border-color .15s}}
.c:hover{{border-color:#b9b4a8;box-shadow:0 2px 10px rgba(0,0,0,.07)}}
.c img{{width:100%;display:block;aspect-ratio:2/3;object-fit:cover;background:#eee}}
figcaption{{padding:8px 10px 10px;font-size:12.5px;line-height:1.45;color:#333}}
figcaption b{{color:#981722}}
figcaption span{{color:#777}}
.pg{{display:inline-block;background:#eef2f7;color:#40618c;border-radius:4px;padding:0 5px;font-size:11px}}
/* 阅读器 */
#v{{position:fixed;inset:0;background:rgba(20,20,18,.94);display:none;z-index:50;
align-items:center;justify-content:center;flex-direction:column;padding:44px 76px 70px}}
#v.on{{display:flex}}
#v img{{max-width:100%;max-height:calc(100vh - 150px);object-fit:contain;background:#fff;
box-shadow:0 8px 40px rgba(0,0,0,.5)}}
#bar{{position:absolute;top:0;left:0;right:0;height:44px;display:flex;align-items:center;
justify-content:space-between;padding:0 16px;color:#e8e4da;font-size:13px}}
#bar .t{{max-width:60%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
#bar a{{color:#9db4d4;text-decoration:none}}
#foot{{position:absolute;bottom:0;left:0;right:0;height:56px;display:flex;align-items:center;
justify-content:center;gap:16px;color:#e8e4da;font-size:13px}}
button.nav{{background:rgba(255,255,255,.12);color:#f2efe6;border:0;border-radius:8px;
padding:7px 15px;font-size:14px;cursor:pointer}}
button.nav:hover{{background:rgba(255,255,255,.22)}}
button.nav:disabled{{opacity:.3;cursor:default}}
.zone{{position:absolute;top:44px;bottom:56px;width:26%;cursor:pointer;z-index:2}}
.zone.l{{left:0}} .zone.r{{right:0}}
#cnt{{min-width:86px;text-align:center;font-variant-numeric:tabular-nums}}
.hint{{color:#8d887d;font-size:12px}}
</style></head><body>
<h1>政党宣传品 · 目录与阅读器</h1>
<p class="lede">{len(data)} 件，{len(groups)} 个国别/地区。点击任一条目打开；多页条目用左右方向键或点击画面两侧翻页，Esc 退出。</p>
<input id="q" placeholder="搜索标题 / 国别 / 年份">

{"".join(sections)}

<div id="v">
  <div id="bar"><span class="t"></span><a target="_blank" rel="noopener">来源 ↗</a></div>
  <div class="zone l" data-step="-1"></div>
  <div class="zone r" data-step="1"></div>
  <img alt="">
  <div id="foot">
    <button class="nav" data-step="-1">← 上一页</button>
    <span id="cnt"></span>
    <button class="nav" data-step="1">下一页 →</button>
  </div>
</div>

<script>
const D = {payload};
const v = document.getElementById('v');
const img = v.querySelector('img');
const cnt = document.getElementById('cnt');
const bar = v.querySelector('#bar .t');
const srcLink = v.querySelector('#bar a');
const prevB = v.querySelector('#foot button[data-step="-1"]');
const nextB = v.querySelector('#foot button[data-step="1"]');
let cur = null, page = 1;

function path(d, p) {{
  if (d.n === 1) return d.cv;
  return d.d + '/pages/p-' + String(p).padStart(5, '0') + '.jpg';
}}

function show() {{
  img.src = path(cur, page);
  bar.textContent = cur.c + ' · ' + cur.y + ' · ' + cur.t;
  srcLink.href = cur.u || '#';
  cnt.textContent = cur.n > 1 ? (page + ' / ' + cur.n) : '单页';
  prevB.disabled = cur.n === 1 || page <= 1;
  nextB.disabled = cur.n === 1 || page >= cur.n;
  // 预载
  if (cur.n > 1 && page < cur.n) {{ const p = new Image(); p.src = path(cur, page + 1); }}
}}

function open(i) {{
  cur = D.find(x => x.i === i);
  if (!cur) return;
  page = 1;
  v.classList.add('on');
  show();
}}

function close() {{ v.classList.remove('on'); }}

function step(s) {{
  if (!cur || cur.n === 1) return;
  const p = page + s;
  if (p < 1 || p > cur.n) return;
  page = p;
  show();
}}

document.querySelectorAll('.c').forEach(el => {{
  el.addEventListener('click', () => open(+el.dataset.i));
}});

document.querySelectorAll('[data-step]').forEach(el => {{
  el.addEventListener('click', e => {{ e.stopPropagation(); step(+el.dataset.step); }});
}});

v.addEventListener('click', e => {{ if (e.target === v) close(); }});

document.addEventListener('keydown', e => {{
  if (!v.classList.contains('on')) return;
  if (e.key === 'Escape') close();
  else if (e.key === 'ArrowLeft') {{ e.preventDefault(); step(-1); }}
  else if (e.key === 'ArrowRight') {{ e.preventDefault(); step(1); }}
}});

// 搜索过滤
const q = document.getElementById('q');
q.addEventListener('input', () => {{
  const s = q.value.trim().toLowerCase();
  document.querySelectorAll('section').forEach(sec => {{
    let shown = 0;
    sec.querySelectorAll('.c').forEach(card => {{
      const d = D.find(x => x.i === +card.dataset.i);
      const hay = (d.c + ' ' + d.y + ' ' + d.t + ' ' + d.s).toLowerCase();
      const hit = !s || hay.includes(s);
      card.style.display = hit ? '' : 'none';
      if (hit) shown++;
    }});
    sec.style.display = shown ? '' : 'none';
  }});
}});
</script>
</body></html>"""

open(os.path.join(IMG, "目录.html"), "w", encoding="utf-8").write(html)

multi = sum(1 for d in data if d["n"] > 1)
print(f"目录.html：{len(data)} 件（多页 {multi} 件，单页 {len(data)-multi} 件）")
print(f"最大页数 {max(d['n'] for d in data)}")
