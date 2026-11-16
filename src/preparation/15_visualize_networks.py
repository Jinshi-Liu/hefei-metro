
import networkx as nx
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict
import matplotlib.font_manager as fm

# =================================
# 1. 路径设置
# =================================

BASE_DIR = Path(__file__).resolve().parents[2]
RESULT_DIR = BASE_DIR / "results" / "networks"
FIGURE_DIR = BASE_DIR / "results" / "figures" / "a"
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

physical_path = RESULT_DIR / "physical_network_with_s1_trial.graphml"
multilayer_path = RESULT_DIR / "multilayer_network_with_s1_trial.graphml"

# =================================
# 2. 中文字体设置
# =================================

available_fonts = {f.name for f in fm.fontManager.ttflist}

for font in ["Microsoft YaHei", "SimHei", "SimSun"]:
    if font in available_fonts:
        plt.rcParams["font.sans-serif"] = [font]
        break

plt.rcParams["axes.unicode_minus"] = False

# =================================
# 3. 线路颜色
# =================================

line_colors = {
    "1": "#E53935",
    "2": "#1976D2",
    "3": "#43A047",
    "4": "#8E24AA",
    "5": "#FB8C00",
    "6": "#00897B",
    "7": "#6D4C41",
    "8": "#3949AB",
    "S1": "#F06292"
}

# =================================
# 4. 绘制物理车站网络
# =================================

G1 = nx.read_graphml(physical_path)

# 固定随机种子，保证布局可复现
pos1 = nx.spring_layout(
    G1,
    seed=42,
    k=1.1,
    iterations=200
)

plt.figure(figsize=(18, 14))

ordinary_nodes = []
transfer_nodes = []
s1_nodes = []

for node, data in G1.nodes(data=True):

    if data.get("line") == "S1" or node.endswith("_LS1"):
        s1_nodes.append(node)

    elif ";" in data.get("lines", ""):
        transfer_nodes.append(node)

    else:
        ordinary_nodes.append(node)

# 普通车站
nx.draw_networkx_nodes(
    G1, pos1,
    nodelist=ordinary_nodes,
    node_color="#90CAF9",
    node_size=35,
    alpha=0.85
)

# 候选换乘站
nx.draw_networkx_nodes(
    G1, pos1,
    nodelist=transfer_nodes,
    node_color="#FFD54F",
    node_size=100,
    node_shape="s"
)

# S1试乘线路
nx.draw_networkx_nodes(
    G1, pos1,
    nodelist=s1_nodes,
    node_color=line_colors["S1"],
    node_size=55,
    node_shape="D"
)

# 绘制运行边
nx.draw_networkx_edges(
    G1, pos1,
    width=0.8,
    alpha=0.45,
    edge_color="#78909C"
)

# 仅标注候选换乘站
nx.draw_networkx_labels(
    G1, pos1,
    labels={
        n: G1.nodes[n].get("station", n)
        for n in transfer_nodes
    },
    font_size=8
)

plt.title(
    "Hefei Metro Physical Station Network",
    fontsize=17,
    pad=20
)

plt.axis("off")
plt.tight_layout()

plt.savefig(
    FIGURE_DIR / "physical_network_visualization.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()

# =================================
# 5. 绘制站点—线路多层网络
# =================================

G2 = nx.read_graphml(multilayer_path)

pos2 = nx.spring_layout(
    G2,
    seed=42,
    k=1.0,
    iterations=200
)

plt.figure(figsize=(20, 15))

# 按线路分类节点
line_nodes = defaultdict(list)

for node, data in G2.nodes(data=True):

    line = data.get("line", "Unknown")
    line_nodes[line].append(node)

# 绘制各线路节点
for line, nodes in line_nodes.items():

    nx.draw_networkx_nodes(
        G2, pos2,
        nodelist=nodes,
        node_color=line_colors.get(line, "#9E9E9E"),
        node_size=35,
        alpha=0.85,
        label=f"{line}号线" if line != "S1" else "S1试乘线路"
    )

# 分别提取运行边和候选换乘边
running_edges = []
candidate_edges = []

for u, v, data in G2.edges(data=True):

    if data.get("edge_type") == "running":
        running_edges.append((u, v))

    elif data.get("edge_type") == "candidate_transfer":
        candidate_edges.append((u, v))

# 绘制运行边
nx.draw_networkx_edges(
    G2, pos2,
    edgelist=running_edges,
    width=0.9,
    alpha=0.5,
    edge_color="#78909C"
)

# 绘制候选换乘边
nx.draw_networkx_edges(
    G2, pos2,
    edgelist=candidate_edges,
    width=1.5,
    alpha=0.8,
    edge_color="#E53935",
    style="dashed"
)

# 标注候选换乘站
transfer_labels = {}

for u, v in candidate_edges:
    for node in [u, v]:
        transfer_labels[node] = G2.nodes[node].get("station", node)

nx.draw_networkx_labels(
    G2, pos2,
    labels=transfer_labels,
    font_size=7
)

plt.title(
    "Hefei Metro Station-Line Multilayer Network",
    fontsize=17,
    pad=20
)

plt.legend(
    loc="upper left",
    fontsize=9,
    ncol=3
)

plt.axis("off")
plt.tight_layout()

plt.savefig(
    FIGURE_DIR / "multilayer_network_visualization.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()

# =================================
# 6. 输出结果
# =================================

print("=" * 45)
print("地铁网络可视化完成！")
print("=" * 45)

print("物理车站网络图：")
print(FIGURE_DIR / "physical_network_visualization.png")

print("\n站点—线路多层网络图：")
print(FIGURE_DIR / "multilayer_network_visualization.png")

print("\n图片分辨率：300 DPI")
print("图片保存在 results 文件夹。")
