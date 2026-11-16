
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path

# 1. 路径
BASE_DIR = Path(__file__).resolve().parents[2]
RESULT_DIR = BASE_DIR / "results" / "networks"
FIGURE_DIR = BASE_DIR / "results" / "figures" / "a"
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

G = nx.read_graphml(
    RESULT_DIR / "physical_network_with_s1_trial.graphml"
)

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei", "DejaVu Sans"
]
plt.rcParams["axes.unicode_minus"] = False

# 2. 分类节点
ordinary = []
transfers = []
s1_nodes = []

for node, data in G.nodes(data=True):
    if data.get("line") == "S1":
        s1_nodes.append(node)
    elif ";" in data.get("lines", ""):
        transfers.append(node)
    else:
        ordinary.append(node)

# 3. 力导向布局
pos = nx.spring_layout(
    G,
    seed=42,
    k=0.25,
    iterations=500
)

# 4. 绘图
fig, ax = plt.subplots(figsize=(18, 13))

nx.draw_networkx_edges(
    G, pos,
    edge_color="#9CA3AF",
    width=0.8,
    alpha=0.45,
    ax=ax
)

nx.draw_networkx_nodes(
    G, pos,
    nodelist=ordinary,
    node_color="#60A5FA",
    node_size=24,
    alpha=0.9,
    ax=ax
)

nx.draw_networkx_nodes(
    G, pos,
    nodelist=transfers,
    node_color="#FBBF24",
    node_size=115,
    edgecolors="#92400E",
    linewidths=0.8,
    ax=ax
)

nx.draw_networkx_nodes(
    G, pos,
    nodelist=s1_nodes,
    node_color="#EC4899",
    node_size=52,
    node_shape="D",
    ax=ax
)

# 5. 标注换乘站
labels = {n: G.nodes[n].get("station", n) for n in transfers}

nx.draw_networkx_labels(
    G, pos,
    labels=labels,
    font_size=8,
    font_family="Microsoft YaHei",
    verticalalignment="bottom",
    ax=ax
)

# 6. 图例
legend_items = [
    Line2D([0], [0], marker="o", linestyle="None",
           color="#60A5FA", markersize=7, label="普通车站"),
    Line2D([0], [0], marker="o", linestyle="None",
           markerfacecolor="#FBBF24",
           markeredgecolor="#92400E",
           markersize=9, label="候选换乘站"),
    Line2D([0], [0], marker="D", linestyle="None",
           color="#EC4899", markersize=7, label="S1试乘站点")
]

ax.legend(handles=legend_items, loc="upper right", fontsize=11)

ax.set_title(
    "合肥轨道交通物理车站网络拓扑图",
    fontsize=19,
    pad=20
)

ax.text(
    0.5, -0.03,
    "注：力导向布局，不代表真实地理位置；"
    "候选换乘关系尚未全部核验；S1为独立试乘线路。",
    transform=ax.transAxes,
    ha="center",
    fontsize=10,
    color="#666666"
)

ax.axis("off")
fig.tight_layout()

# 7. 保存，不自动打开
output = FIGURE_DIR / "physical_network_optimized.png"

fig.savefig(output, dpi=300, bbox_inches="tight")
plt.close(fig)

print("=== 物理车站网络绘图成功 ===")
print("节点数：", G.number_of_nodes())
print("边数：", G.number_of_edges())
print("候选换乘站：", len(transfers))
print("S1试乘站点：", len(s1_nodes))
print("图片已保存：", output)
