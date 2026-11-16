# -*- coding: utf-8 -*-
"""Render dark-theme variants of the B figures for the PPT deck.

The white-background originals stay untouched (they are used in the report);
these variants match the deck theme (background 0E1B31, card 172943).
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
import routing as rt                      # noqa: E402
from build_network import build_multilayer_network, build_physical_network  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

TABLES = ROOT / "results" / "tables"
OUT = ROOT / "results" / "figures" / "deck"
OUT.mkdir(parents=True, exist_ok=True)

# ---- deck palette ----
BG = "#0E1B31"
CARD = "#172943"
TEAL = "#14B8A6"
GOLD = "#F6C453"
BLUE = "#4F9CF7"
MUTED = "#AFC0D4"
WHITE = "#FFFFFF"
GRID = "#27405F"


def setup():
    for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DengXian"):
        if name in {f.name for f in font_manager.fontManager.ttflist}:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def dark_axes(ax):
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(WHITE)
    ax.grid(color=GRID, alpha=0.55, linewidth=0.7)


def read(name):
    with open(TABLES / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------------- 1. loss bar ----------------
def fig_loss():
    rows = read("B04_single_transfer_disruption.csv")
    rows.sort(key=lambda r: -float(r["loss_index"]))
    names = [r["station"] for r in rows]
    loss = [float(r["loss_index"]) for r in rows]
    detour = [int(r["detour_od"]) for r in rows]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6.4),
                             gridspec_kw={"width_ratios": [1.15, 1]})
    fig.patch.set_facecolor(BG)

    ax = axes[0]
    dark_axes(ax)
    colors = [GOLD if i < 3 else TEAL for i in range(len(names))]
    ax.barh(names[::-1], loss[::-1], color=colors[::-1], height=0.66)
    ax.set_title("单站换乘中断：损失指数", fontsize=15, fontweight="bold", pad=12)
    for y, v in enumerate(loss[::-1]):
        ax.text(v + 0.0006, y, f"{v:.4f}", va="center", fontsize=8.5, color=MUTED)
    ax.set_xlim(0, max(loss) * 1.16)

    ax = axes[1]
    dark_axes(ax)
    ax.barh(names[::-1], detour[::-1], color=BLUE, height=0.66)
    ax.set_title("受影响 OD 对数（绕行）", fontsize=15, fontweight="bold", pad=12)
    ax.set_xlim(0, max(detour) * 1.1)

    fig.tight_layout()
    p = OUT / "deck_loss.png"
    fig.savefig(p, dpi=200, facecolor=BG)
    plt.close(fig)
    return p


# ---------------- 2. rank scatter ----------------
def fig_rank():
    rows = read("B08_centrality_vs_loss.csv")
    xs = [float(r["betweenness_rank_among_transfers"]) for r in rows]
    ys = [float(r["loss_rank"]) for r in rows]
    labels = [r["station"] for r in rows]

    fig, ax = plt.subplots(figsize=(8.4, 7.4))
    fig.patch.set_facecolor(BG)
    dark_axes(ax)
    ax.scatter(xs, ys, s=150, color=TEAL, edgecolors=WHITE, linewidths=0.8, zorder=3)

    lim = 20.4
    ax.plot([1, lim], [1, lim], ls="--", color=MUTED, lw=1.3, alpha=0.75,
            label="排名完全一致")
    for x, y, s in zip(xs, ys, labels):
        ax.annotate(s, (x, y), textcoords="offset points", xytext=(8, 6),
                    fontsize=10, color=WHITE)

    ax.set_xlabel("介数中心性排名（19 座换乘站，1=最高）", fontsize=11)
    ax.set_ylabel("换乘中断损失排名（1=损失最大）", fontsize=11)
    ax.set_title("结构排名 ≠ 出行损失排名（Spearman ρ = 0.461）",
                 fontsize=15, fontweight="bold", pad=12)
    ax.set_xlim(0.4, lim)
    ax.set_ylim(0.4, lim)
    ax.invert_xaxis()
    ax.invert_yaxis()
    leg = ax.legend(loc="lower right", facecolor=CARD, edgecolor=GRID, fontsize=10)
    for t in leg.get_texts():
        t.set_color(WHITE)

    fig.tight_layout()
    p = OUT / "deck_rank.png"
    fig.savefig(p, dpi=200, facecolor=BG)
    plt.close(fig)
    return p


# ---------------- 3. detour case ----------------
def fig_case(case_station="紫庐"):
    G = build_multilayer_network()
    idx = rt.station_index(G)
    stations = sorted(idx)
    pairs = rt.all_od_pairs(stations)
    nd = rt.compute_network_distance_matrix(build_physical_network())

    ev = rt.ODEvaluator(G, model="transfers_x2", network_distance=nd)
    C_closed, _ = rt.build_cost_graph(G, model="transfers_x2",
                                      closed_transfer_stations=[case_station])
    ev_c = rt.ODEvaluator(G, model="transfers_x2", network_distance=nd)
    ev_c.set_graph(C_closed)

    best = None
    for o, d in pairs:
        if case_station in (o, d):
            continue
        b = ev.evaluate_pair(o, d)
        if not b.reachable:
            continue
        a = ev_c.evaluate_pair(o, d)
        if not a.reachable:
            continue
        delta = a.cost - b.cost
        if delta > 0 and (best is None or delta > best[0]):
            best = (delta, o, d, b, a)

    delta, o, d, b, a = best

    pos = {}
    for line in sorted({G.nodes[n]["line"] for n in G.nodes()},
                       key=lambda x: int(x) if x.isdigit() else 99):
        nodes = [n for n in G.nodes() if G.nodes[n]["line"] == line]
        head = [n for n in nodes
                if sum(1 for m in G.neighbors(n) if G.nodes[m]["line"] == line) <= 1]
        seq = [head[0]] if head else [nodes[0]]
        seen = {seq[0]}
        while True:
            nxt = [m for m in G.neighbors(seq[-1])
                   if G.nodes[m]["line"] == line and m not in seen]
            if not nxt:
                break
            seq.append(nxt[0])
            seen.add(nxt[0])
        for i, n in enumerate(seq):
            pos[n] = (i, -int(line) if line.isdigit() else -9)

    fig, ax = plt.subplots(figsize=(13, 6.6))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    nx.draw_networkx_edges(G, pos, ax=ax, width=0.35, edge_color=GRID, alpha=0.85)

    def draw_path(path, color, width, ls):
        seg = [(path[i], path[i + 1]) for i in range(len(path) - 1)
               if G.has_edge(path[i], path[i + 1])]
        for n in path:
            if n in pos:
                ax.plot(*pos[n], marker="o", ms=5.5, color=color, zorder=5)
        nx.draw_networkx_edges(G, pos, edgelist=seg, ax=ax, width=width,
                               edge_color=color, alpha=0.98, style=ls)

    draw_path(b.nodes, TEAL, 4.4, "-")
    draw_path(a.nodes, GOLD, 3.0, "--")

    def lab(path, text, color, off):
        for i in (0, -1):
            n = path[i]
            if n in pos:
                ax.annotate(text[i], pos[n], textcoords="offset points",
                            xytext=(0, off), ha="center", fontsize=11,
                            color=color, fontweight="bold")

    lab(b.nodes, (f"起点 {o}", f"终点 {d}"), TEAL, 11)

    ax.set_title(f"代表案例：关闭「{case_station}」换乘以后的绕行",
                 fontsize=15, fontweight="bold", color=WHITE, pad=10)
    ax.text(0.5, -0.06,
            f"{o} → {d}   代价 {b.cost:.1f} → {a.cost:.1f}（+{delta:.1f}）   "
            f"换乘 {b.transfers} → {a.transfers} 次",
            transform=ax.transAxes, ha="center", fontsize=12, color=GOLD,
            fontweight="bold")
    ax.set_ylim(-9.7, -0.3)
    ax.axis("off")

    fig.tight_layout()
    p = OUT / "deck_case.png"
    fig.savefig(p, dpi=200, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return p


# ---------------- 4. centrality bar ----------------
def fig_centrality():
    rows = read("B02_transfer_station_ranking.csv")
    rows.sort(key=lambda r: -float(r["betweenness_centrality"]))
    names = [r["station"] for r in rows]
    bt = [float(r["betweenness_centrality"]) for r in rows]

    fig, ax = plt.subplots(figsize=(12, 4.6))
    fig.patch.set_facecolor(BG)
    dark_axes(ax)
    colors = [GOLD if i < 5 else TEAL for i in range(len(names))]
    ax.bar(range(len(names)), bt, color=colors, width=0.66)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=40, ha="right", fontsize=10)
    for i, v in enumerate(bt):
        ax.text(i, v + 0.004, f"{v:.3f}", ha="center", fontsize=8, color=MUTED)
    ax.set_ylabel("介数中心性", fontsize=11)
    ax.set_title("19 座换乘站的结构排名（前 5 标金）", fontsize=14,
                 fontweight="bold", pad=10)
    ax.set_ylim(0, max(bt) * 1.16)
    fig.tight_layout()
    p = OUT / "deck_centrality.png"
    fig.savefig(p, dpi=200, facecolor=BG)
    plt.close(fig)
    return p


# ---------------- 5. sensitivity ----------------
def fig_sens():
    rows = read("B07_cost_model_sensitivity.csv")
    models = ["stations", "transfers_x1", "transfers_x2"]
    by = {m: {} for m in models}
    for r in rows:
        by.setdefault(r["cost_model"], {})[r["station"]] = float(r["loss_index"])
    stations = sorted({r["station"] for r in rows},
                      key=lambda s: -by["transfers_x2"].get(s, 0))[:8]

    fig, ax = plt.subplots(figsize=(12, 4.8))
    fig.patch.set_facecolor(BG)
    dark_axes(ax)
    width = 0.26
    colors = {"stations": TEAL, "transfers_x1": BLUE, "transfers_x2": GOLD}
    for i, m in enumerate(models):
        vals = [by[m].get(s, 0) for s in stations]
        ax.bar([x + (i - 1) * width for x in range(len(stations))], vals,
               width=width, label=m, color=colors[m])
    ax.set_xticks(range(len(stations)))
    ax.set_xticklabels(stations, fontsize=11)
    ax.set_ylabel("损失指数", fontsize=11)
    ax.set_title("换乘惩罚 0/1/2 站：前三名完全一致（秩相关 ≥ 0.918）",
                 fontsize=14, fontweight="bold", pad=10)
    leg = ax.legend(facecolor=CARD, edgecolor=GRID, fontsize=10)
    for t in leg.get_texts():
        t.set_color(WHITE)
    fig.tight_layout()
    p = OUT / "deck_sens.png"
    fig.savefig(p, dpi=200, facecolor=BG)
    plt.close(fig)
    return p


# ---------------- 6. physical network ----------------
def fig_network():
    G = build_physical_network()
    rows = read("B01_physical_centrality_ranking.csv")
    bt = {r["station"]: float(r["betweenness_centrality"]) for r in rows}
    is_tr = {r["station"]: int(r["line_count"]) > 1 for r in rows}

    pos = nx.spring_layout(G, seed=42, k=0.28, iterations=260)
    fig, ax = plt.subplots(figsize=(11, 8.2))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    nx.draw_networkx_edges(G, pos, ax=ax, width=0.55, edge_color=GRID, alpha=0.9)
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_size=[50 + 7000 * bt[n] for n in G.nodes()],
        node_color=[GOLD if is_tr[n] else BLUE for n in G.nodes()],
        linewidths=0.3, edgecolors=BG,
    )
    top = sorted(G.nodes(), key=lambda n: -bt[n])[:8]
    nx.draw_networkx_labels(G, pos, labels={n: n for n in top}, ax=ax,
                            font_size=10, font_color=WHITE, font_weight="bold")
    ax.set_title("物理车站网络（195 站 / 207 边）｜金=换乘站，大小∝介数",
                 fontsize=14, fontweight="bold", color=WHITE, pad=8)
    ax.axis("off")
    fig.tight_layout()
    p = OUT / "deck_network.png"
    fig.savefig(p, dpi=190, facecolor=BG)
    plt.close(fig)
    return p


if __name__ == "__main__":
    setup()
    made = [fig_network(), fig_centrality(), fig_loss(), fig_rank(),
            fig_case(), fig_sens()]
    print("deck figures:")
    for p in made:
        print("  ", p)
