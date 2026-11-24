"""用分钟代价摆放站点—线路节点，渲染网络图，而不是地理线路图。"""

import argparse
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.stats import spearmanr

from .build_network import GRAPH_FILE, ROOT
from .visualize_network import COLORS, DIM, INK, line_name

OUTPUT = ROOT / "results/metro_weighted_layout.png"
TRANSFER_COLOR = "#657583"
LABELS = {
    "新桥2号航站楼_LS1": (1, 12, "新桥 T2"), "北城高铁站_L8": (-9, 13, "北城高铁站"),
    "相城路_L3": (8, 6, "相城路"), "省儿童医院新区_L3": (-8, 10, "省儿童医院新区"),
    "九联圩_L1": (10, 0, "九联圩"), "撮镇_L2": (-9, -9, "撮镇"),
    "合肥西站_LS1": (26, 43, "合肥西站"), "中国科大东区_L5": (-32, 15, "中国科大东区"),
    "合肥南站_L5": (8, -14, "合肥南站"), "省文化和非遗馆_L7": (11, 2, "省文化和非遗馆"),
}


def fit_minutes(graph):
    """使用 NetworkX 的 Kamada–Kawai 布局，分钟用于计算最短路距离。"""
    if graph.is_directed() or graph.is_multigraph() or len(graph) < 3 or not nx.is_connected(graph):
        raise ValueError("需要至少三个节点的连通无向简单图")
    if any(not 0 < float(e["weight"]) < float("inf") for _, _, e in graph.edges(data=True)):
        raise ValueError("分钟权重须为正数")
    layout = nx.kamada_kawai_layout(graph, weight="weight")
    nodes = list(layout)
    index = {name: i for i, name in enumerate(nodes)}
    xy = np.array(list(layout.values()))
    xy = xy @ np.linalg.svd(xy, full_matrices=False)[2].T
    # 只旋转和翻转朝向以便读图；不读取示意坐标，也不改变相对距离。
    if {"新桥2号航站楼_LS1", "合肥西站_LS1"} <= index.keys():
        if xy[index["新桥2号航站楼_LS1"], 0] > xy[index["合肥西站_LS1"], 0]:
            xy[:, 0] *= -1
    if {"北城高铁站_L8", "合肥南站_L1"} <= index.keys():
        if xy[index["北城高铁站_L8"], 1] < xy[index["合肥南站_L1"], 1]:
            xy[:, 1] *= -1
    return dict(zip(nodes, xy))


def draw(path, graph, positions):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.collections import LineCollection

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "Noto Sans CJK SC", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    rides, transfers = [], []
    for u, v, attrs in graph.edges(data=True):
        (rides if attrs["edge_type"] == "running" else transfers).append((u, v, attrs["weight"]))
    transfer_nodes = {n for u, v, _ in transfers for n in (u, v)}
    fig = plt.figure(figsize=(15.2, 8.55), facecolor="white")
    fig.text(.044, .965, "合肥地铁｜按出行时间排列的加权网络", color=INK,
             weight="bold", fontsize=25, va="top")
    fig.text(.046, .904, "耗时短的连接通常更短；这不是地理地图。", color=DIM, fontsize=12, va="top")
    ax = fig.add_axes([.035, .074, .665, .793])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_collection(LineCollection([(positions[u], positions[v]) for u, v, _ in transfers],
                                     colors=TRANSFER_COLOR, linewidths=1.15, linestyles=(0, (3, 2.6)), zorder=2))
    ax.add_collection(LineCollection([(positions[u], positions[v]) for u, v, _ in rides],
                                     colors=[COLORS[graph.nodes[u]["line"]] for u, _, _ in rides],
                                     linewidths=1.45, capstyle="round", zorder=3))
    for line, color in COLORS.items():
        nodes = [n for n, d in graph.nodes(data=True) if d["line"] == line]
        for swap in (False, True):
            coords = [positions[n] for n in nodes if (n in transfer_nodes) == swap]
            if coords:
                x, y = np.array(coords).T
                ax.scatter(x, y, color="white" if swap else color, s=24 if swap else 10,
                           edgecolors=color if swap else "white", linewidths=1.3 if swap else .34, zorder=4)
    for node, (dx, dy, name) in LABELS.items():
        if node in positions:
            leader = dict(arrowstyle="-", color=DIM, lw=.7) if name in {"合肥西站", "中国科大东区"} else None
            ax.annotate(name, positions[node], xytext=(dx, dy), textcoords="offset points", color=INK,
                        arrowprops=leader,
                        ha="left" if dx > 1 else "right" if dx < -1 else "center", va="center",
                        weight="bold" if node in transfer_nodes or name.startswith("中国科大") else "normal",
                        fontsize=10, path_effects=[pe.withStroke(linewidth=3.2, foreground="white")], zorder=6)
    if rides:
        u, v, longest = max(rides, key=lambda e: e[2])
        if longest >= 8:
            midpoint = (positions[u] + positions[v]) / 2
            ax.annotate(f"{longest:g} 分钟", midpoint, xytext=(17, 4), textcoords="offset points",
                        arrowprops=dict(arrowstyle="-", color=DIM, lw=.75), color=DIM, fontsize=10,
                        va="center", path_effects=[pe.withStroke(linewidth=2.5, foreground="white")], zorder=6)
    ax.autoscale()
    ax.margins(.11)

    side = fig.add_axes([.713, .094, .249, .77], facecolor="#f3f7fa")
    side.set(xlim=(0, 1), ylim=(0, 1), xticks=[], yticks=[])
    for spine in side.spines.values():
        spine.set_visible(False)
    def text(x, y, value, size=11, *, color=INK, bold=False):
        side.text(x, y, value, fontsize=size, va="center", color=color, weight="bold" if bold else "normal")
    text(.080, .930, f"{len(graph)} 个站点—线路节点", 16, bold=True)
    text(.080, .865, f"{len(rides)} 条运行边    {len(transfers)} 条换乘边", color=DIM)
    for i, (line, color) in enumerate(COLORS.items()):
        row, column = divmod(i, 3)
        x, y = .084 + column*.281, .774-row*.067
        side.plot([x, x+.067], [y, y], color=color, lw=2.7, solid_capstyle="round")
        text(x+.084, y, line_name(line), 10)
    side.plot([.083, .154], [.549, .549], color=TRANSFER_COLOR, lw=1.7, ls="--")
    transfer_weights = {w for _, _, w in transfers}
    caption = (f"跨线换乘（{next(iter(transfer_weights)):g} 分钟）"
               if len(transfer_weights) == 1 else "跨线换乘（本站线路节点之间）")
    text(.175, .549, caption, 9.5)
    text(.081, .451, "边长是否跟着分钟变化？", 11.0, bold=True)
    mini = fig.add_axes([.768, .225, .170, .163], facecolor="#f3f7fa")
    weights = np.array([w for _, _, w in rides + transfers])
    lengths = np.linalg.norm([positions[u] - positions[v] for u, v, _ in rides + transfers], axis=1)
    lengths *= np.median(weights) / np.median(lengths)  # 对齐中位数，只作图形核对
    top = max(lengths.max(), weights.max()) + .7
    mini.plot([0, top], [0, top], color="#a5b4c0", lw=.9, ls="--", zorder=0)
    mini.scatter(weights[:len(rides)], lengths[:len(rides)], s=11, alpha=.42, color="#2b7297", edgecolors="none")
    mini.scatter(weights[len(rides):], lengths[len(rides):], s=13, alpha=.65, color=TRANSFER_COLOR, marker="x", linewidths=.9)
    mini.set(xlim=(0, top), ylim=(0, top), xticks=[2, 5, 9], yticks=[2, 5, 9])
    mini.set_xlabel("边权（分钟）", fontsize=8.5, color=DIM)
    mini.set_ylabel("相对边长", fontsize=8.5, color=DIM, labelpad=1)
    mini.tick_params(labelsize=8, colors=DIM, length=2)
    for spine in mini.spines.values():
        spine.set_color("#d6e2ec")
    rho = float(spearmanr(weights, lengths).statistic)
    text(.081, .100, f"边权与图中边长的秩相关：{rho:.2f}", 10, color=DIM)
    text(.081, .047, "两维近似，不用尺子读分钟。", 9.5, color=DIM)
    fig.text(.046, .032, "来源：metro.graphml  ｜  NetworkX Kamada–Kawai 布局：拟合各节点间的最短出行时间  ｜  不改变实验边权", fontsize=9, color=DIM)
    fig.savefig(path, dpi=170, facecolor="white")
    plt.close(fig)
    return rho


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    graph = nx.read_graphml(GRAPH_FILE)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rho = draw(args.output, graph, fit_minutes(graph))
    print(f"{args.output} · 边权和布局边长的秩相关：{rho:.3f}")


if __name__ == "__main__":
    main()
