
import csv
from pathlib import Path
import networkx as nx

# 设置路径
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "processed"
RESULT_DIR = BASE_DIR / "results" / "networks"

RESULT_DIR.mkdir(parents=True, exist_ok=True)

# 创建无向图
G = nx.Graph()

# 读取1—8号线数据
for line in range(1, 9):
    file_path = DATA_DIR / f"line{line}_stations.csv"

    with open(file_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    stations = [row["station"].strip() for row in rows]

    # 添加车站节点
    G.add_nodes_from(stations)

    # 相邻车站之间添加边
    for i in range(len(stations) - 1):
        G.add_edge(stations[i], stations[i + 1])

# 输出网络统计结果
print("=== 合肥地铁物理车站网络 ===")
print("节点数：", G.number_of_nodes())
print("边数：", G.number_of_edges())
print("连通分量数：", nx.number_connected_components(G))

# 保存网络文件
output_path = RESULT_DIR / "physical_network.graphml"
nx.write_graphml(G, output_path)

print("网络文件已保存：", output_path)
