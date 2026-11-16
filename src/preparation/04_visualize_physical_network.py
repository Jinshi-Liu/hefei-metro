
import networkx as nx
import matplotlib.pyplot as plt
import csv
from pathlib import Path
from collections import defaultdict

# 路径设置
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "processed"
RESULT_DIR = BASE_DIR / "results" / "networks"
FIGURE_DIR = BASE_DIR / "results" / "figures" / "a"
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

# 读取之前构建的物理网络
G = nx.read_graphml(RESULT_DIR / "physical_network.graphml")

# 识别疑似换乘站
station_lines = defaultdict(set)

for line in range(1, 9):
    file_path = DATA_DIR / f"line{line}_stations.csv"

    with open(file_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            station_lines[row["station"].strip()].add(line)

transfer_nodes = [
    station for station, lines in station_lines.items()
    if len(lines) > 1 and station in G
]

# 设置中文字体
plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei", "DejaVu Sans"
]
plt.rcParams["axes.unicode_minus"] = False

# 计算节点度数
degrees = dict(G.degree())

# 生成网络布局
pos = nx.spring_layout(G, seed=42, k=0.35, iterations=150)

# 绘图
plt.figure(figsize=(16, 12))

# 普通车站
ordinary_nodes = [
    node for node in G.nodes()
    if node not in transfer_nodes
]

nx.draw_networkx_edges(
    G, pos,
    edge_color="gray",
    alpha=0.3,
    width=0.7
)

nx.draw_networkx_nodes(
    G, pos,
    nodelist=ordinary_nodes,
    node_color="steelblue",
    node_size=25,
    alpha=0.8
)

# 疑似换乘站
nx.draw_networkx_nodes(
    G, pos,
    nodelist=transfer_nodes,
    node_color="orange",
    node_size=90,
    edgecolors="black",
    linewidths=0.7
)

# 只标注疑似换乘站，避免标签重叠
nx.draw_networkx_labels(
    G, pos,
    labels={n: n for n in transfer_nodes},
    font_size=8,
    font_family="Microsoft YaHei"
)

plt.title(
    "合肥轨道交通物理车站网络结构图",
    fontsize=18
)

plt.text(
    0.02, 0.02,
    f"节点数：{G.number_of_nodes()}  "
    f"边数：{G.number_of_edges()}  "
    f"疑似换乘站：{len(transfer_nodes)}",
    transform=plt.gca().transAxes,
    fontsize=11
)

plt.axis("off")
plt.tight_layout()

# 保存图片
output_path = FIGURE_DIR / "physical_network.png"

plt.savefig(
    output_path,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print("网络图保存成功：", output_path)
