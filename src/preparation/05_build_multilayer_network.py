
import csv
import networkx as nx
from pathlib import Path

# ==============================
# 1. 路径设置
# ==============================

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "processed"
RESULT_DIR = BASE_DIR / "results" / "networks"

RESULT_DIR.mkdir(parents=True, exist_ok=True)

# 创建站点—线路多层网络
G = nx.Graph()

# ==============================
# 2. 读取1—8号线，建立线路层节点
# ==============================

running_count = 0

for line in range(1, 9):

    file_path = DATA_DIR / f"line{line}_stations.csv"

    with open(file_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    stations = [row["station"].strip() for row in rows]

    # 创建线路层节点
    for row in rows:

        station = row["station"].strip()
        node_id = f"{station}_L{line}"

        G.add_node(
            node_id,
            station=station,
            line=str(line),
            node_type="station",
            status=row["status"]
        )

    # 添加相邻车站之间的运行边
    for i in range(len(stations) - 1):

        u = f"{stations[i]}_L{line}"
        v = f"{stations[i + 1]}_L{line}"

        G.add_edge(
            u, v,
            edge_type="running",
            line=str(line)
        )

        running_count += 1


# ==============================
# 3. 读取候选换乘边
# ==============================

transfer_file = DATA_DIR / "transfer_edges.csv"

candidate_count = 0

with open(transfer_file, encoding="utf-8-sig") as f:

    reader = csv.DictReader(f)

    for row in reader:

        station = row["station"].strip()
        line_a = row["line_a"].strip()
        line_b = row["line_b"].strip()

        u = f"{station}_L{line_a}"
        v = f"{station}_L{line_b}"

        # 检查两个线路层节点是否存在
        if u not in G or v not in G:

            print(
                "警告：换乘节点不存在：",
                station, line_a, line_b
            )

            continue

        # 添加候选换乘边
        G.add_edge(
            u, v,
            edge_type="candidate_transfer",
            verification_status="pending_verification",
            traversable="false"
        )

        candidate_count += 1


# ==============================
# 4. 加入S1试乘线路
# ==============================

file_path = DATA_DIR / "s1_stations.csv"

with open(file_path, encoding="utf-8-sig") as f:

    rows = list(csv.DictReader(f))

s1_stations = [row["station"].strip() for row in rows]

# 创建S1独立线路层节点
for row in rows:

    station = row["station"].strip()
    node_id = f"{station}_LS1"

    G.add_node(
        node_id,
        station=station,
        line="S1",
        node_type="station",
        status=row["status"]
    )

# 添加S1内部相邻车站运行边
s1_running_count = 0

for i in range(len(s1_stations) - 1):

    u = f"{s1_stations[i]}_LS1"
    v = f"{s1_stations[i + 1]}_LS1"

    G.add_edge(
        u, v,
        edge_type="running",
        line="S1",
        status="trial"
    )

    s1_running_count += 1


# ==============================
# 5. 统计网络数据
# ==============================

running_edges = sum(
    1 for u, v, d in G.edges(data=True)
    if d["edge_type"] == "running"
)

candidate_edges = sum(
    1 for u, v, d in G.edges(data=True)
    if d["edge_type"] == "candidate_transfer"
)

# ==============================
# 6. 分别计算两种连通分量
# ==============================

# 只包含运行边的网络
running_graph = nx.Graph()

running_graph.add_nodes_from(G.nodes(data=True))

running_graph.add_edges_from(
    (u, v)
    for u, v, d in G.edges(data=True)
    if d["edge_type"] == "running"
)

running_components = nx.number_connected_components(
    running_graph
)

# 包含候选换乘边的网络
all_components = nx.number_connected_components(G)


# ==============================
# 7. 输出统计结果
# ==============================

print("=" * 40)
print("       站点—线路多层网络统计")
print("=" * 40)

print("节点数：", G.number_of_nodes())
print("1—8号线运行边：", running_count)
print("S1试乘线路运行边：", s1_running_count)
print("运行边总数：", running_edges)
print("候选换乘边数：", candidate_edges)
print("总边数：", G.number_of_edges())

print("-" * 40)

print("仅运行边的连通分量数：", running_components)
print("包含候选换乘边的连通分量数：", all_components)

print("-" * 40)

print("候选换乘边状态：待核验")
print("S1线路状态：试乘")
print("=" * 40)


# ==============================
# 8. 保存网络文件
# ==============================

output_path = (
    RESULT_DIR / "multilayer_network_with_s1_trial.graphml"
)

nx.write_graphml(G, output_path)

print("\n网络文件保存成功：")
print(output_path)
