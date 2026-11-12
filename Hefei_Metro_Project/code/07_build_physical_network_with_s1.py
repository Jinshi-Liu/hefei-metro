
import csv
import networkx as nx
from pathlib import Path
from collections import defaultdict

# ==============================
# 1. 路径设置
# ==============================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RESULT_DIR = BASE_DIR / "results"

RESULT_DIR.mkdir(parents=True, exist_ok=True)

G = nx.Graph()

# 记录每个物理站点所属线路
station_lines = defaultdict(list)

# ==============================
# 2. 读取1—8号线
# ==============================

operating_edges = 0

for line in range(1, 9):

    file_path = DATA_DIR / f"line{line}_stations.csv"

    with open(file_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    stations = [row["station"].strip() for row in rows]

    # 创建物理车站节点
    for row in rows:

        station = row["station"].strip()

        station_lines[station].append(str(line))

        G.add_node(
            station,
            station=station,
            node_type="physical_station",
            status=row["status"]
        )

    # 添加相邻车站运行边
    for i in range(len(stations) - 1):

        u = stations[i]
        v = stations[i + 1]

        G.add_edge(
            u,
            v,
            line=str(line),
            edge_type="running",
            status="operating"
        )

        operating_edges += 1


# ==============================
# 3. 补充车站所属线路信息
# ==============================

for station, lines in station_lines.items():

    G.nodes[station]["lines"] = ";".join(lines)

    if len(lines) > 1:
        G.nodes[station]["interchange_status"] = (
            "candidate_pending_verification"
        )
    else:
        G.nodes[station]["interchange_status"] = "ordinary_station"


# ==============================
# 4. 加入S1试乘线路
# ==============================

file_path = DATA_DIR / "s1_stations.csv"

with open(file_path, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

s1_stations = [row["station"].strip() for row in rows]

# 使用独立节点ID，避免同名站点合并
for row in rows:

    station = row["station"].strip()
    node_id = f"{station}_LS1"

    G.add_node(
        node_id,
        station=station,
        line="S1",
        node_type="physical_station",
        status=row["status"]
    )

# 添加S1内部运行边
s1_edges = 0

for i in range(len(s1_stations) - 1):

    u = f"{s1_stations[i]}_LS1"
    v = f"{s1_stations[i + 1]}_LS1"

    G.add_edge(
        u,
        v,
        line="S1",
        edge_type="running",
        status="trial"
    )

    s1_edges += 1


# ==============================
# 5. 网络统计
# ==============================

total_edges = G.number_of_edges()

components = nx.number_connected_components(G)

print("=" * 40)
print("       物理车站网络统计")
print("=" * 40)

print("节点数：", G.number_of_nodes())
print("1—8号线运行边：", operating_edges)
print("S1试乘线路运行边：", s1_edges)
print("总边数：", total_edges)
print("连通分量数：", components)

print("-" * 40)

print("普通及候选换乘站数量：", len(station_lines))
print("S1试乘站点数量：", len(s1_stations))

print("注意：同名站点合并形成的连接仍属于候选换乘关系。")

print("=" * 40)


# ==============================
# 6. 保存网络
# ==============================

output_path = (
    RESULT_DIR / "physical_network_with_s1_trial.graphml"
)

nx.write_graphml(G, output_path)

print("\n网络文件保存成功：")
print(output_path)
