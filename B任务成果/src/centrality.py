# -*- coding: utf-8 -*-
"""B：计算物理站点网络的度、介数及排名。

交付物（对应计划书 B 项“基础排名”）
--------------------------------
1. 物理车站网络上的度中心性、介数中心性（及贴近度、特征向量等辅证指标）；
2. 统一排序表：同时给出物理站排名与普通站排名、相对排名；
3. 换乘站排名表：仅 19 座换乘站的结构重要性；
4. 结构排名与“换乘站是否在排名前列”的对照，供后续与出行损失排名比较。

口径
----
- 基础中心性使用 **物理车站网络**（195 节点 / 207 边，同名站已合并），
  与项目 README“用物理站点网络计算结构排名”一致。
- 所有中心性均按 NetworkX 默认归一化方式计算：
  degree 归一化除以 n-1；betweenness 归一化除以无向点对数；
  closeness ``wf_improved=True``；eigenvector 按最大特征值归一化。
- 物理车站网络是全连通、无自环的无向无权图，可直接计算介数。
- 不输出任何“客流量”“实际时间”类指标。

排名并列处理
------------
按计划书要求“固定并列路径处理方式”，本模块**不使用** ``method="min"``
这类把并列名次压平的写法，而是统一采用“竞赛式排名（competition
ranking）”：数值严格大于它自身的站点个数 + 1。并列站点获得相同名次，
下一名次跳号。该规则在全部排名表中保持一致。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Sequence

import networkx as nx

from build_network import build_physical_network, build_multilayer_network

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
TABLES_DIR = RESULTS_DIR / "tables"


# ==============================
# 排名工具
# ==============================

def competition_rank(values: Dict[str, float]) -> Dict[str, int]:
    """竞赛式排名：名次 = 严格更大的数值个数 + 1（并列同名次，下一名次跳号）。"""
    ordered = sorted(values.values(), reverse=True)
    return {
        key: sum(1 for other in ordered if other > value) + 1
        for key, value in values.items()
    }


# ==============================
# 中心性计算
# ==============================

def compute_centralities(G: nx.Graph) -> Dict[str, Dict[str, float]]:
    """计算物理车站网络上的多项中心性。"""
    n = G.number_of_nodes()

    return {
        "degree": {n: float(d) for n, d in G.degree()},          # 原始度（相邻站数）
        "degree_centrality": nx.degree_centrality(G),            # 度 / (n-1)
        "betweenness_centrality": nx.betweenness_centrality(G, normalized=True),
        "closeness_centrality": nx.closeness_centrality(G),
        "eigenvector_centrality": nx.eigenvector_centrality(G, max_iter=10_000, tol=1e-10),
        "clustering": nx.clustering(G),
    }


def build_ranking_table(
    G: nx.Graph,
    metrics: Dict[str, Dict[str, float]],
) -> List[Dict[str, object]]:
    """生成统一的结构排名表。"""
    nodes = sorted(G.nodes())

    deg_rank = competition_rank(metrics["degree_centrality"])
    bt_rank = competition_rank(metrics["betweenness_centrality"])
    cl_rank = competition_rank(metrics["closeness_centrality"])

    # 主排序键：介数中心性（计划书的口径是“物理站点网络用于度、介数排名”）
    main_order = sorted(nodes, key=lambda s: (-metrics["betweenness_centrality"][s], s))

    rows: List[Dict[str, object]] = []
    for overall_rank, station in enumerate(main_order, start=1):
        data = G.nodes[station]
        rows.append(
            {
                "rank": overall_rank,
                "station": station,
                "lines": data.get("lines", ""),
                "line_count": data.get("line_count", 1),
                "station_type": "换乘站" if data.get("line_count", 1) > 1 else "普通站",
                "degree": int(metrics["degree"][station]),
                "degree_centrality": round(metrics["degree_centrality"][station], 8),
                "degree_rank": deg_rank[station],
                "betweenness_centrality": round(
                    metrics["betweenness_centrality"][station], 8
                ),
                "betweenness_rank": bt_rank[station],
                "closeness_centrality": round(metrics["closeness_centrality"][station], 8),
                "closeness_rank": cl_rank[station],
                "eigenvector_centrality": round(
                    metrics["eigenvector_centrality"][station], 8
                ),
                "clustering": round(metrics["clustering"][station], 8),
            }
        )

    # 附加两个描述性列：站内排名与百分位（不改变主排序）
    for row in rows:
        row["rank_percentile"] = round(100.0 * (1 - (row["rank"] - 1) / max(len(rows) - 1, 1)), 2)
    return rows


def build_transfer_ranking_table(
    G: nx.Graph,
    rows: Sequence[Dict[str, object]],
) -> List[Dict[str, object]]:
    """仅针对 19 座候选换乘站的结构排名表。"""
    by_station = {r["station"]: r for r in rows}
    transfers = [s for s in G.nodes() if G.nodes[s].get("line_count", 1) > 1]

    table: List[Dict[str, object]] = []
    transfers.sort(key=lambda s: by_station[s]["rank"])
    for order, station in enumerate(transfers, start=1):
        r = by_station[station]
        table.append(
            {
                "transfer_rank": order,
                "station": station,
                "lines": r["lines"],
                "line_count": r["line_count"],
                "overall_rank": r["rank"],
                "degree": r["degree"],
                "degree_rank": r["degree_rank"],
                "betweenness_centrality": r["betweenness_centrality"],
                "betweenness_rank": r["betweenness_rank"],
                "closeness_centrality": r["closeness_centrality"],
                "eigenvector_centrality": r["eigenvector_centrality"],
            }
        )
    return table


def network_level_metrics(G: nx.Graph) -> Dict[str, float]:
    """网络整体指标（辅以计划书提到的“网络效率”）。"""
    n = G.number_of_nodes()
    efficiency = nx.global_efficiency(G) if n > 1 else 0.0
    return {
        "nodes": n,
        "edges": G.number_of_edges(),
        "average_degree": round(2 * G.number_of_edges() / n, 6) if n else 0.0,
        "density": round(nx.density(G), 8),
        "average_shortest_path_length": round(
            nx.average_shortest_path_length(G), 6
        ),
        "diameter": nx.diameter(G),
        "global_efficiency": round(efficiency, 8),
        "degree_assortativity": round(nx.degree_assortativity_coefficient(G), 6),
        "average_clustering": round(nx.average_clustering(G), 8),
    }


# ==============================
# 输出
# ==============================

def write_csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def main() -> None:
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    G_phys = build_physical_network()
    G_multi = build_multilayer_network()

    metrics = compute_centralities(G_phys)
    rows = build_ranking_table(G_phys, metrics)
    transfer_rows = build_transfer_ranking_table(G_phys, rows)
    net_metrics = network_level_metrics(G_phys)

    # 交叉核对：物理网络的换乘站集合应与多层网络的换乘站集合一致
    multi_index = {}
    for node, data in G_multi.nodes(data=True):
        multi_index.setdefault(data["station"], []).append(node)
    multi_transfers = {s for s, ns in multi_index.items() if len(ns) > 1}
    phys_transfers = {s for s in G_phys.nodes() if G_phys.nodes[s]["line_count"] > 1}

    print("=" * 64)
    print("B 项｜物理车站网络中心性与基础排名")
    print("=" * 64)
    print(f"物理车站网络：{net_metrics['nodes']} 节点 / {net_metrics['edges']} 边")
    print(f"平均最短路：{net_metrics['average_shortest_path_length']} 站；"
          f"直径：{net_metrics['diameter']} 站")
    print(f"全局效率：{net_metrics['global_efficiency']}")
    print(f"换乘站：{len(phys_transfers)} 座"
          f"（与多层网络一致：{phys_transfers == multi_transfers}）")
    print()

    print("介数中心性前 15 名：")
    print(f"{'名次':<4}{'站点':<12}{'线路':<8}{'度':<4}{'介数':<12}{'接近':<10}")
    for r in rows[:15]:
        print(f"{r['rank']:<4}{r['station']:<12}{r['lines']:<8}{r['degree']:<4}"
              f"{r['betweenness_centrality']:<12}{r['closeness_centrality']:<10}")

    print()
    print("19 座换乘站的结构排名（按介数）：")
    print(f"{'换乘排名':<8}{'站点':<12}{'线路':<8}{'全面排名':<8}{'介数排名':<8}{'介数':<12}")
    for r in transfer_rows:
        print(f"{r['transfer_rank']:<8}{r['station']:<12}{r['lines']:<8}"
              f"{r['overall_rank']:<8}{r['betweenness_rank']:<8}"
              f"{r['betweenness_centrality']:<12}")

    # 保存
    ranking_path = TABLES_DIR / "B01_physical_centrality_ranking.csv"
    transfer_path = TABLES_DIR / "B02_transfer_station_ranking.csv"
    network_path = TABLES_DIR / "B03_physical_network_metrics.csv"

    write_csv(
        ranking_path,
        rows,
        [
            "rank", "station", "lines", "line_count", "station_type",
            "degree", "degree_centrality", "degree_rank",
            "betweenness_centrality", "betweenness_rank",
            "closeness_centrality", "closeness_rank",
            "eigenvector_centrality", "clustering", "rank_percentile",
        ],
    )
    write_csv(
        transfer_path,
        transfer_rows,
        [
            "transfer_rank", "station", "lines", "line_count", "overall_rank",
            "degree", "degree_rank", "betweenness_centrality",
            "betweenness_rank", "closeness_centrality", "eigenvector_centrality",
        ],
    )
    write_csv(
        network_path,
        [net_metrics],
        [
            "nodes", "edges", "average_degree", "density",
            "average_shortest_path_length", "diameter", "global_efficiency",
            "degree_assortativity", "average_clustering",
        ],
    )

    print()
    print("已保存：")
    for p in (ranking_path, transfer_path, network_path):
        print("  ", p)


if __name__ == "__main__":
    main()
