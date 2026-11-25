"""把实验三的分时客流结果做成可拖动时间的离线 HTML（不联网、无外部依赖）。

    python -m src.visualize_flow

读 results/dynamic_demand 的节点、有向区间、区间负荷与站点名次，以及
data/metro_layout.csv 的示意坐标，写 results/flow_map.html。
"""

import argparse
import csv
import json
from html import escape
from pathlib import Path

from .build_network import ROOT
from .visualize_network import BOUNDS, COLORS, LABELS, line_name

FLOW = ROOT / "results/dynamic_demand"
LAYOUT_FILE = ROOT / "data/metro_layout.csv"
OUTPUT = ROOT / "results/flow_map.html"
METRICS = {"ppi": "关键性份额 PPI", "departures": "进站人次", "arrivals": "出站人次",
           "transfers": "换线次数"}
TOP_EDGES = 10


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load(flow_dir=FLOW, layout_path=LAYOUT_FILE):
    positions = {r["station"]: (int(r["x"]), int(r["y"])) for r in rows(layout_path)}
    nodes = rows(flow_dir / "nodes.csv")
    names = [r["station"] for r in nodes]
    if set(names) != set(positions) or len(names) != len(positions):
        raise ValueError("布局须与分时结果的物理站一一对应")

    ranks = {}
    hours, station_hours = [], {}
    for r in rows(flow_dir / "station_ranks.csv"):
        if r["hour"] not in hours:
            hours.append(r["hour"])
        station_hours.setdefault(r["station"], {})[r["hour"]] = r
    hours = sorted(hours)
    if set(station_hours) != set(names):
        raise ValueError("station_ranks.csv 与 nodes.csv 的站名不一致")
    for name in names:
        if set(station_hours[name]) != set(hours):
            raise ValueError(f"{name} 的小时不全")

    edges = rows(flow_dir / "edges.csv")
    loads = {}
    for r in rows(flow_dir / "edge_load.csv"):
        loads[(r["start_hour"], r["edge_id"])] = float(r["estimated_load"])
    if len(loads) != len(edges) * len(hours):
        raise ValueError("区间负荷未覆盖全部区间与小时")

    payload = {
        "hours": hours,
        "forecast": rows(flow_dir / "line_forecast.csv")[0]["target"],
        "stations": [dict(name=r["station"], id=r["station_id"], lines=r["lines"],
                          x=positions[r["station"]][0], y=positions[r["station"]][1]) for r in nodes],
        "edges": [dict(id=r["edge_id"], line=r["line"], a=r["from_station"], b=r["to_station"],
                       minutes=int(r["minutes"])) for r in edges],
        "fanout": [[round(float(station_hours[n][h]["departures"]), 1) for h in hours] for n in names],
        "alight": [[round(float(station_hours[n][h]["arrivals"]), 1) for h in hours] for n in names],
        "change": [[round(float(station_hours[n][h]["transfers"]), 1) for h in hours] for n in names],
        "ppi": [[round(float(station_hours[n][h]["ppi"]), 6) for h in hours] for n in names],
        "rank": [[int(station_hours[n][h]["rank"]) for h in hours] for n in names],
        "topo": [int(station_hours[n][hours[0]]["topology_rank"]) for n in names],
        "load": [[round(loads[(h, r["edge_id"])], 1) for h in hours] for r in edges],
        "layout": dict(bounds=BOUNDS, colors=COLORS,
                       labels={k: list(v) for k, v in LABELS.items()},
                       line_names={k: line_name(k) for k in COLORS}),
    }
    return payload


def render(payload):
    xmin, ymin, xmax, ymax = payload["layout"]["bounds"]
    return (HTML.replace("{{DATA}}", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                         .replace("<", "\\u003c"))
            .replace("{{VIEWBOX}}", f"{xmin} {ymin} {xmax - xmin} {ymax - ymin}")
            .replace("{{METRICS}}", "".join(
                f'<button type="button" data-metric="{key}"{" class=\'on\'" if key == "ppi" else ""}>'
                f"{label}</button>" for key, label in METRICS.items()))
            .replace("{{LEGEND}}", "".join(
                f'<span><i style="background:{color}"></i>{escape(line_name(line))}</span>'
                for line, color in COLORS.items())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flow", type=Path, default=FLOW)
    parser.add_argument("--layout", type=Path, default=LAYOUT_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    payload = load(args.flow, args.layout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(payload), encoding="utf-8")
    print(f"{args.output}: {len(payload['stations'])} 站 × {len(payload['hours'])} 小时, "
          f"{len(payload['edges'])} 条有向区间")


HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>合肥地铁｜分时客流与关键站（11 月 25 日情景）</title>
<style>
:root{color-scheme:light;--ink:#122d43;--dim:#51697b;--paper:#f4f8fb;--line:#d9e3ec;--accent:#004398;--warm:#a64b35}
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 system-ui,"Microsoft YaHei","Noto Sans CJK SC",sans-serif;color:var(--ink);background:var(--paper)}
header{padding:18px clamp(14px,3vw,34px) 10px}
h1{margin:0 0 4px;font-size:clamp(21px,2.6vw,30px);letter-spacing:.2px}
.sub{margin:0;color:var(--dim);font-size:13.5px}
.wrap{display:grid;grid-template-columns:minmax(0,1fr) 336px;gap:14px;padding:8px clamp(14px,3vw,34px) 26px;align-items:start}
.card{background:#fff;border:1px solid var(--line);border-radius:13px}
.stage{position:relative;overflow:hidden;padding:6px 6px 0}
svg#map{display:block;width:100%;height:auto}
.rail-base{fill:none;stroke-linecap:round}
.rail-load{fill:none;stroke-linecap:round;mix-blend-mode:multiply}
.bubble{fill:var(--warm);fill-opacity:.16;stroke:var(--warm);stroke-width:.9}
.bubble.hot{fill-opacity:.34}
.dot{fill:#fff;stroke:var(--ink);stroke-width:.9}
.dot.swap{stroke-width:1.6}
.stlabel{font-size:11px;fill:var(--ink);font-weight:600;paint-order:stroke;stroke:#fff;stroke-width:3;stroke-linejoin:round}
.stlabel.rank1{fill:#004398;font-size:13px}
.arrow{fill:var(--ink);opacity:.34}
.tip{position:absolute;pointer-events:none;opacity:0;transform:translate(-50%,-118%);background:#122d43f2;color:#fff;
  padding:9px 11px;border-radius:9px;font-size:12.5px;line-height:1.5;white-space:nowrap;transition:opacity .12s;z-index:5}
.tip b{font-size:13.5px}
.tip span{color:#b9cede}
aside{display:flex;flex-direction:column;gap:12px}
.panel{padding:12px 13px}
.panel h2{margin:0 0 9px;font-size:12.5px;letter-spacing:.09em;color:var(--dim);text-transform:uppercase;font-weight:700}
.clock{font-size:27px;font-weight:700;letter-spacing:.5px}
.clock small{font-size:12.5px;font-weight:500;color:var(--dim);margin-left:5px}
input[type=range]{width:100%;margin:9px 0 2px;accent-color:var(--accent)}
.row{display:flex;gap:7px;flex-wrap:wrap;margin-top:6px}
button{font:inherit;font-size:12.5px;padding:5px 10px;border-radius:8px;border:1px solid var(--line);
  background:#f7fafc;color:var(--ink);cursor:pointer}
button:hover{border-color:#b6c9d8}
button.on{background:var(--accent);border-color:var(--accent);color:#fff}
.totals{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:11px;font-size:12.5px}
.totals div{background:#f6f9fc;border-radius:9px;padding:7px 9px}
.totals b{display:block;font-size:16px;font-weight:700}
.totals span{color:var(--dim)}
ol{margin:0;padding:0;list-style:none;font-size:13px}
ol li{display:grid;grid-template-columns:20px 1fr auto;gap:7px;align-items:baseline;padding:4px 5px;border-radius:7px;cursor:default}
ol li:hover,ol li.sel{background:#eef5fb}
ol li em{font-style:normal;color:var(--dim);font-variant-numeric:tabular-nums;font-size:12px}
ol li strong{font-weight:600}
ol li i{font-style:normal;color:#8aa0b1;font-size:11.5px}
.legend{display:flex;flex-wrap:wrap;gap:8px 12px;font-size:12.5px;color:var(--dim)}
.legend span{display:flex;align-items:center;gap:5px}
.legend i{width:15px;height:4px;border-radius:2px;display:inline-block}
footer{padding:0 clamp(14px,3vw,34px) 30px;color:var(--dim);font-size:12.5px;line-height:1.7}
footer b{color:var(--ink)}
@media (max-width:1000px){.wrap{grid-template-columns:1fr}}
</style></head>
<body>
<header>
  <h1>合肥地铁｜分时客流与关键站</h1>
  <p class="sub">11 月 25 日（周三）估计情景 · 204 站 × 18 个出发小时 · 拖动时间看流向与名次如何变化</p>
</header>
<div class="wrap">
  <div class="card stage">
    <svg id="map" viewBox="{{VIEWBOX}}" role="img" aria-label="合肥地铁分时客流示意图"></svg>
    <div class="tip" id="tip"></div>
  </div>
  <aside>
    <div class="card panel">
      <h2>出发小时</h2>
      <div class="clock"><span id="clock">07:00</span><small id="hournote">早高峰</small></div>
      <input type="range" id="slider" min="0" max="17" step="1" value="1" aria-label="出发小时">
      <div class="row">
        <button type="button" id="play">播放</button>
        <button type="button" id="prev">上一小时</button>
        <button type="button" id="next">下一小时</button>
      </div>
      <div class="row" id="metrics">{{METRICS}}</div>
      <div class="totals">
        <div><b id="sum-fanout">–</b><span>进站合计</span></div>
        <div><b id="sum-alight">–</b><span>出站合计</span></div>
        <div><b id="sum-change">–</b><span>换线合计</span></div>
        <div><b id="peak">–</b><span id="peak-name">最重区间</span></div>
      </div>
    </div>
    <div class="card panel">
      <h2 id="list-title">关键站前 10</h2>
      <ol id="list"></ol>
    </div>
    <div class="card panel">
      <h2>线路</h2>
      <div class="legend">{{LEGEND}}</div>
    </div>
  </aside>
</div>
<footer>
  <b>怎么读：</b>气泡越大，该站这一小时的“<span id="metric-name">关键性份额 PPI</span>”越高；区间按该方向、该出发小时经过的估计行程数加粗，箭头标出本小时最重的十条。
  数字是<b>模型估计</b>：由公开线路日报、站周边人口与设施，以及 18 个小时的分时假设推出，不是刷卡或断面实测。
  <br><b>口径：</b>按出发小时归组，代表“这一小时出发、后来经过该区间或该站”的估计行程数，不是该小时车上的人数。
  来源：<code>results/dynamic_demand/</code>；坐标取自 MetroMan 合肥线网示意图，仅用于排版。
</footer>
<script>
const D = {{DATA}};
const H = D.hours.length, N = D.stations.length, E = D.edges.length;
const S = D.stations, names = S.map(s => s.name);
const idx = new Map(names.map((n, i) => [n, i]));
const color = D.layout.colors, lineName = D.layout.line_names;
const FIELDS = {ppi: D.ppi, departures: D.fanout, arrivals: D.alight, transfers: D.change};
const METRIC_LABEL = {ppi: "关键性份额 PPI", departures: "进站人次", arrivals: "出站人次", transfers: "换线次数"};
const NS = "http://www.w3.org/2000/svg";
let hour = 1, metric = "ppi", playing = null, peakIds = new Set();

const svg = document.getElementById("map");
const el = (tag, attrs) => { const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]); return n; };

// 全局量纲：跨 18 小时统一，拖动时气泡与线宽可比。
const metricMax = Object.fromEntries(Object.entries(FIELDS).map(([k, v]) =>
  [k, Math.max(...v.flat()) || 1]));
const loadMax = Math.max(...D.load.flat()) || 1;

const gRail = el("g", {}), gLoad = el("g", {}), gArrow = el("g", {}), gBubble = el("g", {}),
      gDot = el("g", {}), gLabel = el("g", {});
svg.append(gRail, gLoad, gArrow, gBubble, gDot, gLabel);

// 有向区间：反方向各偏 1.4 单位，避免两条线完全重叠。
const railEls = [], loadEls = [], arrowEls = [];
const offset = (a, b) => {
  const [x1, y1] = [S[a].x, S[a].y], [x2, y2] = [S[b].x, S[b].y];
  const len = Math.hypot(x2 - x1, y2 - y1) || 1;
  const side = (a < b ? 1 : -1) * 1.5;
  return { nx: -(y2 - y1) / len * side, ny: (x2 - x1) / len * side, x1, y1, x2, y2 };
};
D.edges.forEach((e, k) => {
  const a = idx.get(e.a), b = idx.get(e.b), o = offset(a, b);
  const geo = { x1: o.x1 + o.nx, y1: o.y1 + o.ny, x2: o.x2 + o.nx, y2: o.y2 + o.ny };
  const base = el("line", { ...geo, class: "rail-base", stroke: color[e.line], "stroke-width": 2.1,
                            opacity: .3, "stroke-linejoin": "round" });
  const load = el("line", { ...geo, class: "rail-load", stroke: color[e.line], "stroke-width": .4 });
  gRail.append(base); gLoad.append(load);
  railEls.push(base); loadEls.push(load);
  const arrow = el("polygon", { class: "arrow", points: "0,-4.6 9.6,0 0,4.6" });
  arrow.style.display = "none"; gArrow.append(arrow); arrowEls.push({ node: arrow, a, b });
});

const bubbles = [], dots = [], labels = [];
S.forEach((s, i) => {
  const bubble = el("circle", { cx: s.x, cy: s.y, r: 0, class: "bubble" });
  const swap = s.lines.includes(";");
  const dot = el("circle", { cx: s.x, cy: s.y, r: swap ? 4.6 : 2.7, class: swap ? "dot swap" : "dot" });
  gBubble.append(bubble); gDot.append(dot);
  bubbles.push(bubble); dots.push(dot);
  const text = el("text", { x: s.x, y: s.y - 12, "text-anchor": "middle", class: "stlabel" });
  text.textContent = s.name; text.style.display = "none"; gLabel.append(text); labels.push(text);
  bubble.addEventListener("mousemove", ev => showTip(ev, i));
  dot.addEventListener("mousemove", ev => showTip(ev, i));
  bubble.addEventListener("mouseleave", hideTip); dot.addEventListener("mouseleave", hideTip);
});

const fmt = v => v >= 1000 ? Math.round(v).toLocaleString("zh-CN") : (Math.round(v * 10) / 10).toString();
const $ = id => document.getElementById(id);

function hourNote(h) {
  if (h >= "07:00" && h <= "09:00") return "早高峰";
  if (h >= "17:00" && h <= "19:00") return "晚高峰";
  if (h >= "22:00") return "末班前";
  return "平峰";
}

function update() {
  const h = D.hours[hour], values = FIELDS[metric];
  $("clock").textContent = h;
  $("hournote").textContent = hourNote(h);
  $("metric-name").textContent = METRIC_LABEL[metric];
  const vmax = metricMax[metric];
  let best = -1, bestLoad = -1;
  const loads = [];
  for (let k = 0; k < E; k++) {
    const v = D.load[k][hour];
    loads.push(v);
    if (v > bestLoad) { bestLoad = v; best = k; }
    const rel = v / loadMax;
    loadEls[k].setAttribute("stroke-width", (0.35 + 7.4 * Math.sqrt(rel)).toFixed(2));
    loadEls[k].setAttribute("opacity", (0.16 + 0.84 * Math.min(1, rel * 2.6)).toFixed(2));
  }
  peakIds = new Set([...D.edges.keys()].sort((p, q) => loads[q] - loads[p]).slice(0, 10));
  arrowEls.forEach(({ node, a, b }, k) => {
    if (!peakIds.has(k)) { node.style.display = "none"; return; }
    const o = offset(a, b);
    node.style.display = "";
    node.setAttribute("transform",
      `translate(${(o.x1 + o.nx) * .38 + (o.x2 + o.nx) * .62},${(o.y1 + o.ny) * .38 + (o.y2 + o.ny) * .62}) ` +
      `rotate(${Math.atan2(o.y2 - o.y1, o.x2 - o.x1) * 180 / Math.PI})`);
  });
  for (let i = 0; i < N; i++) {
    const v = values[i][hour];
    bubbles[i].setAttribute("r", (2.2 + 17 * Math.sqrt(v / vmax)).toFixed(2));
    bubbles[i].setAttribute("class", v / vmax > .45 ? "bubble hot" : "bubble");
  }
  const order = metric === "ppi"
    ? [...Array(N).keys()].sort((p, q) => D.rank[p][hour] - D.rank[q][hour])
    : [...Array(N).keys()].sort((p, q) => values[q][hour] - values[p][hour]);
  labels.forEach(t => t.style.display = "none");
  order.slice(0, 8).forEach((i, r) => {
    labels[i].style.display = "";
    labels[i].setAttribute("class", "stlabel" + (r === 0 ? " rank1" : ""));
  });  $("list").innerHTML = order.slice(0, 10).map((i, r) => {
    const s = S[i], f = FIELDS[metric][i][hour];
    return `<li data-station="${s.name}"><em>${r + 1}</em><strong>${s.name}<br>` +
      `<i>拓扑第 ${D.topo[i]} 名 · 全网第 ${D.rank[i][hour]} 名</i></strong>` +
      `<em>${metric === "ppi" ? (f * 100).toFixed(2) + "%" : fmt(f)}</em></li>`;
  }).join("");
  $("list-title").textContent = metric === "ppi" ? "关键站前 10（PPI）" : `前 10（${METRIC_LABEL[metric]}）`;
  const sum = key => FIELDS[key].reduce((acc, row) => acc + row[hour], 0);
  $("sum-fanout").textContent = fmt(sum("departures"));
  $("sum-alight").textContent = fmt(sum("arrivals"));
  $("sum-change").textContent = fmt(sum("transfers"));
  const e = D.edges[best];
  $("peak").textContent = fmt(bestLoad);
  $("peak-name").textContent = `${lineName[e.line]} ${e.a}→${e.b}`;
  $("slider").value = hour;
}

function showTip(ev, i) {
  const h = D.hours[hour], tip = $("tip"), rect = svg.getBoundingClientRect();
  const scale = rect.width / svg.viewBox.baseVal.width;
  const x = S[i].x * scale + rect.left - svg.parentElement.getBoundingClientRect().left;
  const y = S[i].y * scale + rect.top - svg.parentElement.getBoundingClientRect().top;
  tip.innerHTML = `<b>${S[i].name}</b> <span>${S[i].lines.split(";").map(l => lineName[l]).join(" · ")}</span><br>` +
    `${h} 出发小时<br>进站 ${fmt(D.fanout[i][hour])}／出站 ${fmt(D.alight[i][hour])}／换线 ${fmt(D.change[i][hour])}<br>` +
    `PPI ${(D.ppi[i][hour] * 100).toFixed(2)}%　全网第 ${D.rank[i][hour]} 名（静态第 ${D.topo[i]} 名）`;
  tip.style.left = x + "px"; tip.style.top = y + "px"; tip.style.opacity = 1;
}
function hideTip() { $("tip").style.opacity = 0; }

$("slider").addEventListener("input", e => { hour = +e.target.value; update(); });
$("prev").addEventListener("click", () => { hour = (hour + H - 1) % H; update(); });
$("next").addEventListener("click", () => { hour = (hour + 1) % H; update(); });
$("play").addEventListener("click", e => {
  if (playing) { clearInterval(playing); playing = null; e.target.textContent = "播放"; e.target.classList.remove("on"); return; }
  playing = setInterval(() => { hour = (hour + 1) % H; update(); }, 900);
  e.target.textContent = "暂停"; e.target.classList.add("on");
});
$("metrics").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  metric = b.dataset.metric;
  [...$("metrics").children].forEach(x => x.classList.toggle("on", x === b));
  update();
});
document.addEventListener("keydown", e => {
  if (e.key === "ArrowRight") { hour = (hour + 1) % H; update(); }
  if (e.key === "ArrowLeft") { hour = (hour + H - 1) % H; update(); }
});
update();
</script>
</body></html>
'''


if __name__ == "__main__":
    main()
