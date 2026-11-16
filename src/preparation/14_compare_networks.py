
import networkx as nx
import csv
from pathlib import Path

# ==============================
# 1. 路径设置
# ==============================

BASE_DIR = Path(__file__).resolve().parents[2]
RESULT_DIR = BASE_DIR / "results" / "networks"

physical_path = (
    RESULT_DIR / "physical_network_with_s1_trial.graphml"
)

multilayer_path = (
    RESULT_DIR / "multilayer_network_with_s1_trial.graphml"
)

output_path = BASE_DIR / "results" / "tables" / "network_comparison.csv"
output_path.parent.mkdir(parents=True, exist_ok=True)


# ==============================
# 2. 读取网络
# ==============================

physical = nx.read_graphml(physical_path)
multilayer = nx.read_graphml(multilayer_path)


# ==============================
# 3. 计算网络指标
# ==============================

def calculate_metrics(G, network_name):

    n = G.number_of_nodes()
    m = G.number_of_edges()

    average_degree = 2 * m / n if n > 0 else 0

    density = nx.density(G)

    components = list(nx.connected_components(G))

    component_count = len(components)

    largest_component = (
        max(len(c) for c in components)
        if components else 0
    )

    return {
        "network": network_name,
        "nodes": n,
        "edges": m,
        "average_degree": round(average_degree, 4),
        "density": round(density, 6),
        "components": component_count,
        "largest_component": largest_component
    }


# ==============================
# 4. 计算两种网络
# ==============================

results = []

results.append(
    calculate_metrics(physical, "Physical Network")
)

results.append(
    calculate_metrics(multilayer, "Multilayer Network")
)


# ==============================
# 5. 输出统计结果
# ==============================

print("=" * 55)
print("          两种地铁网络结构对比")
print("=" * 55)

for result in results:

    print("\n网络类型：", result["network"])
    print("节点数：", result["nodes"])
    print("边数：", result["edges"])
    print("平均度：", result["average_degree"])
    print("网络密度：", result["density"])
    print("连通分量数：", result["components"])
    print("最大连通分量节点数：", result["largest_component"])


# ==============================
# 6. 保存CSV
# ==============================

fields = [
    "network",
    "nodes",
    "edges",
    "average_degree",
    "density",
    "components",
    "largest_component"
]

with open(
    output_path,
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(f, fieldnames=fields)

    writer.writeheader()
    writer.writerows(results)


print("\n" + "=" * 55)
print("网络对比统计表保存成功！")
print(output_path)
print("=" * 55)
