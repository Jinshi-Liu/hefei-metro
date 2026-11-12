
from pathlib import Path
import networkx as nx

BASE_DIR = Path(__file__).resolve().parent.parent
RESULT_DIR = BASE_DIR / "results"

# 1. 读取之前建立的完整多层网络
G = nx.read_graphml(
    RESULT_DIR / "multilayer_network_with_s1_trial.graphml"
)

# 2. 复制网络，移除S1试乘线路
G_main = G.copy()

s1_nodes = [
    node for node in G_main.nodes()
    if node.endswith("_LS1")
]

G_main.remove_nodes_from(s1_nodes)

# 3. 区分运行边和候选换乘边
running_edges = [
    (u, v)
    for u, v, data in G_main.edges(data=True)
    if data.get("edge_type") == "running"
]

transfer_edges = [
    (u, v)
    for u, v, data in G_main.edges(data=True)
    if data.get("edge_type") == "candidate_transfer"
]

# 4. 保存主实验多层网络
output = RESULT_DIR / "multilayer_network_main.graphml"

nx.write_graphml(G_main, output)

# 5. 计算连通性
G_running = G_main.edge_subgraph(running_edges).copy()
G_running.add_nodes_from(G_main.nodes())

print("=== 1—8号线主实验网络 ===")
print("节点数：", G_main.number_of_nodes())
print("运行边数：", len(running_edges))
print("候选换乘边数：", len(transfer_edges))
print("总边数：", G_main.number_of_edges())
print("包含候选换乘边时的连通分量数：",
      nx.number_connected_components(G_main))
print("仅保留运行边时的连通分量数：",
      nx.number_connected_components(G_running))
print("已保存：", output)
