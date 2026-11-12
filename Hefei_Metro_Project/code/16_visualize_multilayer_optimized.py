
import csv
from pathlib import Path

import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# ============================
# 1. 路径设置
# ============================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RESULT_DIR = BASE_DIR / "results"

G = nx.read_graphml(
    RESULT_DIR / "multilayer_network_with_s1_trial.graphml"
)

# 中文字体
plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei", "DejaVu Sans"
]
plt.rcParams["axes.unicode_minus"] = False

# 线路颜色（示意配色，不代表官方标准色）
colors = {
    "1": "#E53935",
    "2": "#1976D2",
    "3": "#43A047",
    "4": "#8E24AA",
    "5": "#FB8C00",
    "6": "#00897B",
    "7": "#795548",
    "8": "#3949AB",
    "S1": "#EC407A"
}

lines = [str(i) for i in range(1, 9)] + ["S1"]

pos = {}
line_nodes = {}

# ============================
# 2. 按线路顺序排列节点
# ============================

for row_index, line in enumerate(lines):

    filename = (
        "s1_stations.csv"
        if line == "S1"
        else f"line{line}_stations.csv"
    )

    with open(
        DATA_DIR / filename,
        encoding="utf-8-sig"
    ) as f:
        rows = list(csv.DictReader(f))

    rows.sort(key=lambda r: int(r["sequence"]))

    stations = [r["station"].strip() for r in rows]

    y = 8 - row_index
    line_nodes[line] = []

    for i, station in enumerate(stations):

        node = f"{station}_L{line}"

        if node not in G:
            raise ValueError(f"网络缺少节点：{node}")

        # 每条线路按站点顺序水平排列
        x = i * 1.0

        pos[node] = (x, y)
        line_nodes[line].append(node)

# ============================
# 3. 绘图
# ============================

fig, ax = plt.subplots(figsize=(22, 11))

# 绘制各线路运行边及节点
for line in lines:

    nodes = line_nodes[line]

    running_edges = [
        (u, v)
        for u, v in zip(nodes[:-1], nodes[1:])
        if G.has_edge(u, v)
        and G.edges[u, v].get("edge_type") == "running"
    ]

    nx.draw_networkx_edges(
        G, pos,
        edgelist=running_edges,
        edge_color=colors[line],
        width=2.5,
        alpha=0.85,
        ax=ax
    )

    nx.draw_networkx_nodes(
        G, pos,
        nodelist=nodes,
        node_color=colors[line],
        node_size=42,
        ax=ax
    )

    # 在每一行左侧标明线路
    first_x, first_y = pos[nodes[0]]

    label = (
        "S1（试乘）"
        if line == "S1"
        else f"{line}号线"
    )

    ax.text(
        -1.5, first_y,
        label,
        fontsize=11,
        fontweight="bold",
        color=colors[line],
        ha="right",
        va="center"
    )

# ============================
# 4. 绘制候选换乘边
# ============================

candidate_edges = [
    (u, v)
    for u, v, d in G.edges(data=True)
    if d.get("edge_type") == "candidate_transfer"
]

nx.draw_networkx_edges(
    G, pos,
    edgelist=candidate_edges,
    edge_color="#777777",
    style="dashed",
    width=0.8,
    alpha=0.4,
    ax=ax
)

# ============================
# 5. 标记候选换乘节点
# ============================

transfer_nodes = set()

for u, v in candidate_edges:
    transfer_nodes.add(u)
    transfer_nodes.add(v)

nx.draw_networkx_nodes(
    G, pos,
    nodelist=list(transfer_nodes),
    node_color="#FFD54F",
    edgecolors="#333333",
    linewidths=0.8,
    node_size=105,
    ax=ax
)

# 减少文字重叠：
# 不标注全部车站，只标注部分重要节点
# 详细名称仍保存在GraphML和CSV中

label_names = {
    "合肥南站",
    "合肥火车站",
    "大东门",
    "西七里塘",
    "三孝口",
    "图书馆",
    "海棠",
    "合肥西站"
}

# 每个名称仅选一个线路层节点显示
labels = {}

for name in label_names:
    if name == "合肥西站":
        node = "合肥西站_L3"
        if node in G:
            labels[node] = name
    else:
        matches = [
            node for node in transfer_nodes
            if G.nodes[node].get("station") == name
        ]
        if matches:
            labels[sorted(matches)[0]] = name

nx.draw_networkx_labels(
    G, pos,
    labels=labels,
    font_size=8,
    verticalalignment="bottom",
    ax=ax
)

# ============================
# 6. 标题和图例
# ============================

ax.set_title(
    "合肥轨道交通站点—线路多层网络拓扑示意图",
    fontsize=18,
    pad=22
)

legend_items = [
    Line2D(
        [0], [0],
        color="#777777",
        linestyle="--",
        label="候选换乘边（待核验）"
    ),
    Line2D(
        [0], [0],
        marker="o",
        linestyle="None",
        markerfacecolor="#FFD54F",
        markeredgecolor="#333333",
        markersize=8,
        label="候选换乘节点"
    )
]

ax.legend(
    handles=legend_items,
    loc="upper right",
    fontsize=10
)

ax.text(
    0.5, -0.05,
    "注：水平位置为线路站点序号，不代表地理距离；"
    "灰色虚线为候选换乘关系，尚未全部核验。",
    transform=ax.transAxes,
    ha="center",
    fontsize=10,
    color="#555555"
)

ax.set_axis_off()
fig.tight_layout()

# ============================
# 7. 保存，不自动打开
# ============================

output = (
    RESULT_DIR / "multilayer_network_optimized.png"
)

fig.savefig(
    output,
    dpi=300,
    bbox_inches="tight"
)

plt.close(fig)

print("=== 多层网络优化绘图完成 ===")
print("线路数量：", len(lines))
print("节点数量：", G.number_of_nodes())
print("候选换乘边：", len(candidate_edges))
print("图片保存至：", output)
