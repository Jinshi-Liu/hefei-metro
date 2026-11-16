# -*- coding: utf-8 -*-
"""B：生成 B 项图表（结构排名、逐站损失、排名对照、代表案例）。

图表口径与表格一致：代价单位为“等效站数”，不是真实分钟数。
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

import networkx as nx

from build_network import build_multilayer_network, build_physical_network
import routing as rt

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
TABLES_DIR = RESULTS_DIR / "tables"
FIG_DIR = RESULTS_DIR / "figures"

BASELINE_MODEL = "transfers_x2"


# ---------- 中文字体 ----------

def setup_chinese_font() -> None:
    """选择一个可用的中文字体，避免乱码。"""
    candidates = [
        "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC",
        "PingFang SC", "WenQuanYi Zen Hei", "SimSun", "DengXian",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False
            return
    plt.rcParams["axes.unicode_minus"] = False


def read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------- 图 1：物理网络 + 关键站点 ----------

def fig_physical_network_with_key_stations() -> Path:
    G = build_physical_network()
    rows = read_csv(TABLES_DIR / "B01_physical_centrality_ranking.csv")
    bt = {r["station"]: float(r["betweenness_centrality"]) for r in rows}
    is_transfer = {r["station"]: int(r["line_count"]) > 1 for r in rows}

    pos = nx.spring_layout(G, seed=42, k=0.28, iterations=260)

    sizes = [60 + 9_000 * bt[n] for n in G.nodes()]
    colors = ["#e45756" if is_transfer[n] else "#8fb8de" for n in G.nodes()]

    fig, ax = plt.subplots(figsize=(15, 12))
    nx.draw_networkx_edges(G, pos, ax=ax, width=0.7, edge_color="#b9b9b9", alpha=0.75)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=sizes, node_color=colors,
                           linewidths=0.4, edgecolors="white")

    top = sorted(G.nodes(), key=lambda n: -bt[n])[:12]
    labels = {n: n for n in top}
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax, font_size=10, font_weight="bold")

    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], marker="o", ls="", markerfacecolor="#e45756",
               markersize=11, label="换乘站"),
        Line2D([], [], marker="o", ls="", markerfacecolor="#8fb8de",
               markersize=8, label="普通站"),
        Line2D([], [], marker="o", ls="", markerfacecolor="#999999",
               markersize=5, label="节点面积∝介数中心性（物理站网络）"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=10, frameon=True)
    ax.set_title("Physical station network with key stations (1-8) - node size ~ betweenness",
                 fontsize=13)
    ax.axis("off")
    fig.tight_layout()
    out = FIG_DIR / "B_fig1_physical_network_key_stations.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------- 图 2：逐站出行损失 ----------

def fig_station_loss_bar() -> Path:
    rows = read_csv(TABLES_DIR / "B04_single_transfer_disruption.csv")
    rows.sort(key=lambda r: -float(r["loss_index"]))
    names = [r["station"] for r in rows]
    loss = [float(r["loss_index"]) for r in rows]
    detour_od = [int(r["detour_od"]) for r in rows]

    fig, axes = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [1.25, 1]})

    ax = axes[0]
    bars = ax.barh(names[::-1], loss[::-1], color="#4c78a8", height=0.68)
    ax.set_xlabel("loss index = mean incremental cost / mean baseline cost")
    ax.set_title("Single transfer disruption: loss index by station\n"
                 "(cost model: stations + 2 x transfers)", fontsize=12)
    ax.grid(axis="x", alpha=0.3)
    for bar, v in zip(bars, loss[::-1]):
        ax.text(v, bar.get_y() + bar.get_height() / 2, f" {v:.4f}",
                va="center", fontsize=8)

    ax = axes[1]
    ax.barh(names[::-1], detour_od[::-1], color="#f58518", height=0.68)
    ax.set_xlabel("number of OD pairs with increased cost")
    ax.set_title("OD pairs affected (detour)", fontsize=12)
    ax.grid(axis="x", alpha=0.3)

    fig.tight_layout()
    out = FIG_DIR / "B_fig2_single_station_loss.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------- 图 3：结构排名 vs 出行损失排名 ----------

def fig_centrality_vs_loss() -> Path:
    rows = read_csv(TABLES_DIR / "B08_centrality_vs_loss.csv")
    xs = [float(r["betweenness_rank_among_transfers"]) for r in rows]
    ys = [float(r["loss_rank"]) for r in rows]
    labels = [r["station"] for r in rows]

    fig, ax = plt.subplots(figsize=(9, 9))
    ax.scatter(xs, ys, s=110, color="#4c78a8", zorder=3)
    lim = max(max(xs), max(ys)) + 1
    ax.plot([1, lim], [1, lim], ls="--", color="#999999", lw=1.2,
            label="identical ranking")
    for x, y, s in zip(xs, ys, labels):
        ax.annotate(s, (x, y), textcoords="offset points", xytext=(6, 5), fontsize=9)

    ax.set_xlabel("betweenness rank among 19 transfer stations (1 = highest)")
    ax.set_ylabel("travel-loss rank under single-station transfer closure (1 = largest loss)")
    ax.set_title("Structure ranking vs travel-loss ranking\n"
                 "(Spearman rho = 0.461; top-5 overlap = 2)", fontsize=12)
    ax.set_xlim(0.5, lim)
    ax.set_ylim(0.5, lim)
    ax.invert_yaxis()
    ax.invert_xaxis()
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()

    out = FIG_DIR / "B_fig3_centrality_vs_loss_rank.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------- 图 4：换乘惩罚敏感性 ----------

def fig_cost_model_sensitivity() -> Path:
    rows = read_csv(TABLES_DIR / "B07_cost_model_sensitivity.csv")
    models = ["stations", "transfers_x1", "transfers_x2"]
    by_model: Dict[str, Dict[str, float]] = {m: {} for m in models}
    for r in rows:
        by_model.setdefault(r["cost_model"], {})[r["station"]] = float(r["loss_index"])

    stations = sorted(
        {r["station"] for r in rows},
        key=lambda s: -by_model["transfers_x2"].get(s, 0),
    )

    fig, ax = plt.subplots(figsize=(13, 6))
    width = 0.26
    x = range(len(stations))
    colors = {"stations": "#72b7b2", "transfers_x1": "#4c78a8", "transfers_x2": "#e45756"}
    for i, m in enumerate(models):
        vals = [by_model[m].get(s, 0) for s in stations]
        ax.bar([xi + (i - 1) * width for xi in x], vals, width=width,
               label=m, color=colors.get(m, "#888888"))

    ax.set_xticks(list(x))
    ax.set_xticklabels(stations, rotation=45, ha="right")
    ax.set_ylabel("loss index")
    ax.set_title("Sensitivity to transfer penalty (Spearman rho >= 0.92 across models)", fontsize=12)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    out = FIG_DIR / "B_fig4_cost_model_sensitivity.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------- 图 5：代表站替代路径案例 ----------

def fig_case_alternatives(case_station: str = "紫庐") -> Path:
    """画出代表站在换乘中断前后的替代路径示意。"""
    G_multi = build_multilayer_network()
    station_index = rt.station_index(G_multi)
    stations = sorted(station_index)
    pairs = rt.all_od_pairs(stations)

    network_distance = rt.compute_network_distance_matrix(build_physical_network())
    ev = rt.ODEvaluator(G_multi, model=BASELINE_MODEL, network_distance=network_distance)

    # 找该站关闭后绕行增加最大、且起终点都不是该站的 OD 对
    C_closed, _ = rt.build_cost_graph(
        G_multi, model=BASELINE_MODEL, closed_transfer_stations=[case_station]
    )
    ev_closed = rt.ODEvaluator(G_multi, model=BASELINE_MODEL,
                              network_distance=network_distance)
    ev_closed.set_graph(C_closed)

    best = None
    second = None
    for o, d in pairs:
        if case_station in (o, d):
            continue
        b = ev.evaluate_pair(o, d)
        if not b.reachable:
            continue
        a = ev_closed.evaluate_pair(o, d)
        if not a.reachable:
            continue
        delta = a.cost - b.cost
        if delta <= 0:
            continue
        if best is None or delta > best[0]:
            second = best
            best = (delta, o, d, b, a)
        elif second is None or delta > second[0]:
            second = (delta, o, d, b, a)

    fig, axes = plt.subplots(1, 2, figsize=(17, 8))
    fig.suptitle(f"Representative detour case: transfer closure at {case_station}",
                 fontsize=14)

    for ax, item, tag in zip(axes, [best, second], ["A", "B"]):
        if item is None:
            ax.axis("off")
            continue
        delta, o, d, b, a = item

        # 按各线路真实站序布置：每条线路一行，站序为 x
        pos = {}
        line_order = {}
        for line in sorted({G_multi.nodes[n]["line"] for n in G_multi.nodes()},
                           key=lambda x: int(x) if x.isdigit() else 99):
            nodes = [n for n in G_multi.nodes() if G_multi.nodes[n]["line"] == line]
            head = [n for n in nodes if sum(1 for m in G_multi.neighbors(n)
                                            if G_multi.nodes[m]["line"] == line) <= 1]
            seq = [head[0]] if head else [nodes[0]]
            seen = {seq[0]}
            while True:
                nxt = [m for m in G_multi.neighbors(seq[-1])
                       if G_multi.nodes[m]["line"] == line and m not in seen]
                if not nxt:
                    break
                seq.append(nxt[0])
                seen.add(nxt[0])
            line_order[line] = seq
            for i, n in enumerate(seq):
                pos[n] = (i, -int(line) if line.isdigit() else -9)

        nx.draw_networkx_edges(G_multi, pos, ax=ax, width=0.3,
                               edge_color="#dddddd", alpha=0.6)

        def draw_path(path, color, width, ls="-"):
            if not path:
                return
            seg = [(path[i], path[i + 1]) for i in range(len(path) - 1)
                   if G_multi.has_edge(path[i], path[i + 1])]
            # 高亮路径涉及的节点
            for n in path:
                if n in pos:
                    ax.plot(*pos[n], marker="o", ms=6, color=color, zorder=5)
            nx.draw_networkx_edges(
                G_multi, pos, edgelist=seg, ax=ax, width=width,
                edge_color=color, alpha=0.95, style=ls,
            )
            # 起点、终点单独标注
            for n, mk in ((path[0], "s"), (path[-1], "*")):
                if n in pos:
                    ax.plot(*pos[n], marker=mk, ms=14, mfc=color, mec="black",
                            zorder=6)

        draw_path(b.nodes, "#2ca02c", 2.6, "-")
        draw_path(a.nodes, "#d62728", 2.6, "--")

        # 只标注起终点，避免全站名拥挤
        def annotate(path, color, o_text, d_text):
            for i, txt in ((0, o_text), (-1, d_text)):
                n = path[i]
                if n in pos:
                    ax.annotate(txt, pos[n], textcoords="offset points",
                                xytext=(0, 9), ha="center", fontsize=9,
                                color=color, fontweight="bold")

        annotate(b.nodes, "#2ca02c", f"起点 {o}", f"终点 {d}")
        annotate(a.nodes, "#d62728", "", "")

        ax.set_title(
            f"{tag}: {o} -> {d}\n"
            f"cost {b.cost:.1f} -> {a.cost:.1f}  (+{delta:.1f}), "
            f"transfers {b.transfers} -> {a.transfers}",
            fontsize=11,
        )
        ax.set_ylim(-9.6, -0.4)
        ax.axis("off")

    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], color="#2ca02c", lw=3, label="baseline shortest path"),
        Line2D([], [], color="#d62728", lw=3, ls="--", label=f"after closing {case_station}"),
    ]
    axes[0].legend(handles=handles, loc="lower right", fontsize=9)

    fig.tight_layout()
    out = FIG_DIR / "B_fig5_detour_case.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    setup_chinese_font()
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    made = []
    made.append(fig_physical_network_with_key_stations())
    made.append(fig_station_loss_bar())
    made.append(fig_centrality_vs_loss())
    made.append(fig_cost_model_sensitivity())
    made.append(fig_case_alternatives("紫庐"))

    print("已生成图表：")
    for p in made:
        print("  ", p)


if __name__ == "__main__":
    main()
