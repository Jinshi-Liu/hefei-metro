"""用布局坐标可视化已保存的分钟图，输出汇报 PNG 和离线交互图。"""

import argparse
import csv
from html import escape
import json
from pathlib import Path

import networkx as nx

from .build_network import GRAPH_FILE, ROOT

LAYOUT_FILE = ROOT / "data/metro_layout.csv"
SOURCE_URL = "https://www.metroman.cn/en/maps/hefei"
INK, DIM, PALE = "#122d43", "#4c6476", "#e3ebf2"
COLORS = {"1": "#d14149", "2": "#325fc6", "3": "#177b54", "4": "#cb681d",
          "5": "#729524", "6": "#984b9e", "7": "#a57c13", "8": "#0993b3", "S1": "#78634e"}
# 只在总览上标主要站与两端站；其余站名可在交互版查看。
LABELS = {
    "新桥2号航站楼": (-35, -58), "省中医院西区": (54, -12),
    "北城高铁站": (0, -64), "一里井": (-35, 68),
    "张洼": (36, -27), "九联圩": (32, 48), "南岗": (-34, -52), "撮镇": (0, 62),
    "相城路": (10, -55), "省儿童医院新区": (-12, 58),
    "综保区": (10, -55), "烧脉岗": (0, 67),
    "汲桥路": (0, -56), "贵阳路": (-32, 24),
    "青龙岗": (10, 62), "龙塘": (25, -55),
    "翡翠公园": (-30, -50), "省文化和非遗馆": (37, 29),
    "合肥西站": (-34, -47), "合肥南站": (27, 67), "合肥火车站": (40, -18),
    "繁华大道": (37, -39), "紫庐": (-38, 56), "中国科大东区": (-34, 57),
    "洪岗": (-34, -42), "西七里塘": (-30, 66), "方庙": (58, -102),
}
FOCUS = {"合肥西站", "合肥南站", "合肥火车站", "中国科大东区", "紫庐", "繁华大道"}
BOUNDS = (-65, -5, 2880, 2785)  # xmin, ymin, xmax, ymax


def load_map(graph_path, layout_path=LAYOUT_FILE):
    graph = nx.read_graphml(graph_path)
    with layout_path.open(encoding="utf-8-sig", newline="") as f:
        positions = {r["station"]: (int(r["x"]), int(r["y"])) for r in csv.DictReader(f)}
    names = {d["station"] for _, d in graph.nodes(data=True)}
    if positions.keys() != names or len(set(positions.values())) != len(positions):
        raise ValueError("布局须与 GraphML 的物理站一一对应")
    stations = {name: dict(lines=[], rides=[], transfers=[]) for name in sorted(names)}
    running = {line: [] for line in COLORS}
    for _, node in graph.nodes(data=True):
        stations[node["station"]]["lines"].append(node["line"])
    for u, v, edge in graph.edges(data=True):
        a, b = graph.nodes[u], graph.nodes[v]
        sa, sb = a["station"], b["station"]
        weight = float(edge["weight"])
        if edge["edge_type"] == "running" and a["line"] == b["line"]:
            line = a["line"]
            running[line].append((sa, sb, weight))
            for station, neighbor in ((sa, sb), (sb, sa)):
                stations[station]["rides"].append((line, neighbor, weight))
        elif edge["edge_type"] == "transfer" and sa == sb:
            l1, l2 = sorted((a["line"], b["line"]))
            stations[sa]["transfers"].append((l1, l2, weight))
        else:
            raise ValueError(f"不可识别的网络边：{u}—{v}")
    return positions, stations, running


def map_counts(stations, running):
    return len(stations), sum(len(s["lines"]) for s in stations.values()), sum(map(len, running.values())), sum(len(s["transfers"]) for s in stations.values())


def line_name(line):
    return f"{line} 线" if line == "S1" else f"{line} 号线"


def label_position(name, positions):
    x, y = positions[name]
    dx, dy = LABELS[name]
    return x + dx, y + dy, "end" if dx < -20 else "start" if dx > 20 else "middle"


def draw_png(path, positions, stations, running):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.collections import LineCollection

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "Noto Sans CJK SC", "SimHei", "DejaVu Sans"]
    fig = plt.figure(figsize=(14.4, 8.1), facecolor="white")
    fig.text(.049, .947, "合肥地铁｜全线网示意图", fontsize=27, weight="bold", color=INK, va="top")
    fig.text(.050, .895, "1–8 号线及 S1  ·  2026-11-23 研究快照", fontsize=11.5, color=DIM, va="top")
    ax = fig.add_axes([.027, .074, .682, .785])
    x0, y0, x1, y1 = BOUNDS
    ax.set(xlim=(x0, x1), ylim=(y1, y0), aspect="equal")
    ax.axis("off")
    for line, edges in running.items():
        segments = [(positions[a], positions[b]) for a, b, _ in edges]
        ax.add_collection(LineCollection(segments, colors="white", linewidths=4.6, capstyle="round", zorder=2))
        ax.add_collection(LineCollection(segments, colors=COLORS[line], linewidths=2.72, capstyle="round", zorder=2.2))
    for name, d in stations.items():
        x, y = positions[name]
        swap = bool(d["transfers"])
        ax.scatter(x, y, s=30 if swap else 8.5, facecolor="white",
                   edgecolor=INK if swap else COLORS[d["lines"][0]], lw=1.02 if swap else .7, zorder=4)
    for name in LABELS:
        if name not in positions:
            continue
        x, y, anchor = label_position(name, positions)
        text = ax.text(x, y, name, ha={"start": "left", "end": "right", "middle": "center"}[anchor],
                       va="center", color=INK if name in FOCUS else DIM, fontsize=9.5 if name in FOCUS else 8.1,
                       weight="bold" if name in FOCUS else "normal", zorder=5)
        text.set_path_effects([pe.withStroke(linewidth=3.0, foreground="white")])

    sidebar = fig.add_axes([.715, .098, .244, .768])
    sidebar.set(xlim=(0, 1), ylim=(0, 1), facecolor="#f4f8fb", xticks=[], yticks=[])
    for spine in sidebar.spines.values():
        spine.set_visible(False)
    def text(y, value, size=11, bold=False, x=.085, color=INK, **kw):
        sidebar.text(x, y, value, fontsize=size, weight="bold" if bold else "normal", color=color, va="center", **kw)
    count, nodes, ride, change = map_counts(stations, running)
    text(.923, f"{len(running)} 条线  /  {count} 座车站", 16, True)
    text(.859, f"{nodes} 个站点—线路节点", color=DIM)
    text(.810, f"{ride} 条乘车边    {change} 条换乘边", color=DIM)
    sidebar.plot([.085, .915], [.762, .762], lw=1, color=PALE)
    text(.710, "线路", 11.5, True)
    for i, (line, color) in enumerate(COLORS.items()):
        row, col = divmod(i, 3)
        x, y = .088 + col * .281, .638 - row * .066
        sidebar.plot([x, x+.061], [y, y], lw=3, color=color, solid_capstyle="round")
        text(y, line_name(line), 10, x=x+.08)
    sidebar.plot([.085, .915], [.455, .455], lw=1, color=PALE)
    sidebar.plot(.105, .394, marker="o", ms=4, mfc="white", mec=INK)
    text(.394, "普通站", x=.169)
    sidebar.plot(.510, .394, marker="o", ms=6.7, mfc="white", mec=INK)
    text(.394, f"换乘站（{sum(bool(v['transfers']) for v in stations.values())} 座）", x=.581)
    text(.302, "换乘处画在一起，算路时仍区分线路。", 9.6, color=DIM)
    text(.250, "有颜色的线是乘车边；线条交叉不等于可换乘。", 9.3, color=DIM)
    text(.146, "乘车边：规划区间耗时的双向均值", 9.6, color=DIM)
    weights = {weight for s in stations.values() for _, _, weight in s["transfers"]}
    note = (f"换乘边：每次按 {next(iter(weights)):g} 分钟（模型设定）"
            if len(weights) == 1 else "换乘边：逐条查阅交互版的分钟数")
    text(.093, note, 9.6, color=DIM)
    fig.text(.048, .036, "网络：metro.graphml  ｜  版式坐标：MetroMan 合肥线网示意图  ｜  线段长度不表示距离或分钟数", fontsize=9, color=DIM)
    fig.savefig(path, dpi=170, facecolor="white")
    plt.close(fig)


def map_svg(positions, stations, running):
    xmin, ymin, xmax, ymax = BOUNDS
    svg = [f'<svg id="map" viewBox="{xmin} {ymin} {xmax-xmin} {ymax-ymin}" aria-label="合肥地铁全线网示意图">']
    for line, edges in running.items():
        svg.append(f'<g class="rail" data-line="{line}" stroke="{COLORS[line]}">')
        for a, b, weight in edges:
            x, y = positions[a]
            dx, dy = positions[b]
            info = escape(f"{line_name(line)} · {a}—{b}：{weight:g} 分钟")
            svg.append(f'<line x1="{x}" y1="{y}" x2="{dx}" y2="{dy}"><title>{info}</title></line>')
        svg.append('</g>')
    for name, d in stations.items():
        x, y = positions[name]
        swap = bool(d["transfers"])
        stroke = INK if swap else COLORS[d["lines"][0]]
        safe = escape(name, quote=True)
        svg.append(f'<g class="place" data-station="{safe}" tabindex="0" role="button" aria-label="{safe}"><title>{safe}</title>')
        svg.append(f'<circle class="dot" cx="{x}" cy="{y}" r="{11 if swap else 7}" stroke="{stroke}"/>')
        svg.append(f'<circle class="target" cx="{x}" cy="{y}" r="20"/>')
        if name in LABELS:
            lx, ly, anchor = label_position(name, positions)
            label_class = "focus-label" if name in FOCUS else ""
            svg.append(f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" class="{label_class}">{safe}</text>')
        svg.append('</g>')
    return "".join(svg) + "</svg>"


def draw_html(path, positions, stations, running):
    html = (HTML.replace("{{MAP}}", map_svg(positions, stations, running))
            .replace("{{DATA}}", json.dumps(stations, ensure_ascii=False).replace("<", "\\u003c"))
            .replace("{{LINES}}", "".join(f'<option value="{line}">{line_name(line)}</option>' for line in COLORS))
            .replace("{{SOURCE}}", SOURCE_URL))
    path.write_text(html, encoding="utf-8")


HTML = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>合肥地铁｜全线网示意图</title>
<style>
:root{color-scheme:light;--ink:#122d43;--dim:#4c6476;--paper:#f3f7fa;--line:#d6e2ec;--accent:#235e78}
*{box-sizing:border-box}body{margin:0;font:15px/1.55 system-ui,"Microsoft YaHei",sans-serif;color:var(--ink);background:var(--paper)}
main{max-width:1450px;margin:auto;padding:22px clamp(16px,3vw,40px)}h1,h2,p{margin:0}h1{font-size:clamp(25px,4vw,39px)}h2{font-size:25px}.quiet,footer{color:var(--dim)}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(245px,300px);gap:16px;margin:14px 0}.view,aside{background:#fff;border:1px solid var(--line);border-radius:13px}
.view{display:flex;flex-direction:column;overflow:hidden}.tools{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:12px;border-bottom:1px solid var(--line)}form{display:flex;gap:8px;margin-right:auto}
button,input,select{font:inherit;color:inherit;padding:5px 9px;border:1px solid var(--line);border-radius:6px;background:#fff}input{width:clamp(138px,21vw,220px)}button{cursor:pointer}button:hover{background:#e8f2f8}
aside{padding:16px}aside section{margin-top:16px}h3{font-size:14px;color:var(--accent);margin:0 0 6px}ul{padding-left:17px;margin:0}li{margin:.16em 0}.meta{font-size:13px;margin-top:4px}footer{font-size:13px}footer a{color:var(--accent)}
#map{display:block;width:100%;height:clamp(430px,75vh,940px);touch-action:none;cursor:grab;background:#fff}#map.dragging{cursor:grabbing}#map .dim{opacity:.14}
.rail{fill:none;stroke-width:8;stroke-linecap:round}.rail line{vector-effect:non-scaling-stroke;stroke-width:2.3}.place{cursor:pointer}.dot{fill:white;stroke-width:4.4}.target{fill:transparent}
.place:hover .dot,.place:focus .dot,.place.active .dot{fill:#f8bd45;stroke:#122d43;stroke-width:7}.place.active{opacity:1!important}.place text{font-size:33px;fill:#4c6476;paint-order:stroke;stroke:#fff;stroke-width:14px;stroke-linejoin:round;dominant-baseline:middle;pointer-events:none}.place .focus-label{font-weight:700;font-size:38px;fill:#122d43}
@media(max-width:760px){.grid{grid-template-columns:1fr}#map{height:65vh;min-height:360px}}
</style></head>
<body><main><h1>合肥地铁｜全线网示意图</h1><p class="quiet">按现有分钟图绘制。可搜索或点击车站；拖动平移，滚轮放大。</p>
<div class="grid"><section class="view" aria-label="线网地图"><div class="tools"><form id="search"><input id="station" list="names" placeholder="输入站名，例如合肥南站" aria-label="站名" required><datalist id="names"></datalist><button type="submit">找车站</button></form>
<select id="filter" aria-label="突出显示线路"><option value="">所有线路</option>{{LINES}}</select><button type="button" id="plus" aria-label="放大">＋</button><button type="button" id="minus" aria-label="缩小">−</button><button type="button" id="reset">全图</button></div>
{{MAP}}
</section><aside><p class="quiet meta" id="scope"></p><h2 id="name"></h2><p id="serves" class="quiet" aria-live="polite"></p>
<section><h3>相邻车站与乘车时间</h3><ul id="rides"></ul></section><section><h3>本站的换乘边</h3><ul id="transfers"></ul></section>
<section class="meta quiet">站名集中在示意坐标上，但同一站的不同线路仍是不同节点。黑色圈标出可以换乘的站；线路相交不等于相通。</section></aside></div>
<footer>站序、连接及权重来自 metro.graphml。布局来自 <a href="{{SOURCE}}">MetroMan 合肥示意图</a>，线段长度不表示距离或耗时；分钟值与换乘条件为模型假设，不作乘车指引。</footer></main>
<script>
const data = {{DATA}}, byId = id => document.getElementById(id), svg = byId('map');
const places = new Map([...svg.querySelectorAll('.place')].map(el => [el.dataset.station, el]));
const full = svg.getAttribute('viewBox').split(' ').map(Number); let box = [...full], active;
const pretty = l => l === 'S1' ? 'S1 线' : `${l} 号线`;
const show = () => svg.setAttribute('viewBox', box.join(' '));
function list(id, text) { byId(id).replaceChildren(...text.map(value => {const el = document.createElement('li'); el.textContent = value; return el;})); }
function pick(name, move=false) {
  const node = places.get(name); if (!node) return;
  if (active) active.classList.remove('active'); node.classList.add('active'); active = node;
  const s = data[name]; byId('name').textContent = name; byId('serves').textContent = s.lines.map(pretty).join(' · ');
  list('rides', s.rides.map(([l,d,m]) => `${pretty(l)} → ${d} · ${m} 分钟`));
  list('transfers', s.transfers.length ? s.transfers.map(([a,b,m]) => `${pretty(a)} ↔ ${pretty(b)} · ${m} 分钟`) : ['本站无跨线换乘边']);
  if (move) { const dot=node.querySelector('.dot'); const w=full[2]*.46, h=full[3]*.46; box=[+dot.getAttribute('cx')-w/2,+dot.getAttribute('cy')-h/2,w,h]; show(); }
}
for (const [name, node] of places) {
  const option=document.createElement('option'); option.value=name; byId('names').append(option);
  node.addEventListener('click', () => pick(name));
  node.addEventListener('keydown', e => {if(e.key==='Enter'||e.key===' '){e.preventDefault();pick(name);}});
}
byId('station').addEventListener('input', e=>e.target.setCustomValidity(''));
byId('search').addEventListener('submit', e=>{
  e.preventDefault(); const input=byId('station'), name=input.value.trim();
  if (!places.has(name)) {input.setCustomValidity('请从列表选择一座车站');input.reportValidity();return;}
  pick(name,true);
});
byId('filter').addEventListener('change', e=>{
  const line=e.target.value; for (const g of svg.querySelectorAll('.rail')) g.classList.toggle('dim', !!line && g.dataset.line!==line);
  for (const [name,el] of places) el.classList.toggle('dim', !!line && !data[name].lines.includes(line));
});
function zoom(f, x=box[0]+box[2]/2, y=box[1]+box[3]/2){
  const w=Math.min(full[2],Math.max(full[2]/12,box[2]*f)); const scale=w/box[2];
  box=[x-(x-box[0])*scale,y-(y-box[1])*scale,w,box[3]*scale];show();
}
byId('plus').onclick=()=>zoom(.78);byId('minus').onclick=()=>zoom(1/.78);
byId('reset').onclick=()=>{box=[...full];show();};
svg.addEventListener('wheel',e=>{e.preventDefault();const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());zoom(e.deltaY<0?.85:1/.85,p.x,p.y);},{passive:false});
let drag;
svg.addEventListener('pointerdown',e=>{if(e.button!==0||e.target.closest('.place'))return;const m=svg.getScreenCTM();drag=[e.clientX,e.clientY,box[0],box[1],m.a,m.d];svg.setPointerCapture(e.pointerId);svg.classList.add('dragging');});
svg.addEventListener('pointermove',e=>{if(drag){box[0]=drag[2]-(e.clientX-drag[0])/drag[4];box[1]=drag[3]-(e.clientY-drag[1])/drag[5];show();}});
for(const type of ['pointerup','pointercancel','lostpointercapture']) svg.addEventListener(type,()=>{drag=null;svg.classList.remove('dragging');});
byId('scope').textContent = `${places.size} 座物理站 · ${Object.keys(data).filter(n=>data[n].transfers.length).length} 座换乘站`;
pick(places.has('合肥西站')?'合肥西站':places.keys().next().value);
</script></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=GRAPH_FILE)
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    map_data = load_map(args.graph)
    draw_png(args.output / "metro_map.png", *map_data)
    draw_html(args.output / "metro_map.html", *map_data)
    print(f"线网示意图与离线交互版已保存至 {args.output}")


if __name__ == "__main__":
    main()
