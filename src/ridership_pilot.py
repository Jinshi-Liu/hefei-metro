"""线路客流加权的换乘试算；结果是每千条模拟行程的影响，不是受影响人数。"""
import csv
from collections import defaultdict

import networkx as nx
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from .build_network import ROOT, build_directed_network

COUNTS = ROOT / "data/line_ridership.csv"
OUT = ROOT / "results/ridership_pilot/stations.csv"
DELAY = 10  # “明显绕行”：还能到，但最短时间比正常多至少 10 分钟


def compare_stations(g):
    """起点固定在线路站台；目的站只计一次，两种选终点规则共用同一套最短路。"""
    nodes = sorted(g, key=lambda n: (g.nodes[n]["station"], n))
    names = np.array([g.nodes[n]["station"] for n in nodes])
    lines = np.array([g.nodes[n]["line"] for n in nodes])
    stations, first = np.unique(names, return_index=True)
    test = names[:, None] != stations[None, :]  # 不算出发站自身
    arcs = nx.to_numpy_array(g, nodelist=nodes, weight="weight")
    index = {n: i for i, n in enumerate(nodes)}
    at = defaultdict(list)
    for u, v, edge in g.edges(data=True):
        if edge["edge_type"] == "transfer":
            at[edge["station"]].append((index[u], index[v]))

    def times(weights):
        return np.minimum.reduceat(dijkstra(csr_matrix(weights), directed=True), first, axis=1)

    base = times(arcs)
    if not np.isfinite(base).all():
        raise ValueError("正常网络应全部可达")
    # 先抽起始线路，再等概率抽该线的一个站台。用比例直接算期望，不随机抽样。
    by_line, counts = np.unique(lines, return_counts=True)
    sizes = dict(zip(by_line, counts))
    cases = []
    for day, volumes in line_weights(by_line):
        origin = np.array([volumes[line] / sizes[line] for line in lines])
        origin /= origin.sum()
        for rule, dest in [("各站等可能", np.ones(len(stations))),
                           ("热门线路目的地也多", np.add.reduceat(origin, first))]:
            # 第二种规则把同一物理站所属各线分到的份额合并；两个版本都排除原站。
            destinations = dest * test
            shares = origin[:, None] * destinations / destinations.sum(axis=1)[:, None]
            cases.append((day, rule, shares))

    rows = []
    for station, edges in sorted(at.items()):
        after_arcs = arcs.copy()
        for i, j in edges:
            after_arcs[i, j] = 0
        after = times(after_arcs)
        if np.any(after < base):
            raise ValueError("移除换乘边不应缩短时间")
        lost = ~np.isfinite(after)
        delayed = ~lost & (after - base >= DELAY)
        for day, rule, shares in cases:
            a, b = shares[lost].sum() * 1000, shares[delayed].sum() * 1000
            rows.append(dict(scenario=day, destinations=rule, station=station,
                             lost=a, delay_10plus=b, lost_or_delay_10plus=a+b))
    return sorted(rows, key=lambda r: (r["scenario"], r["destinations"], -r["lost_or_delay_10plus"], r["station"]))


def line_weights(lines):
    yield "各线同等", {line: 1 for line in lines}
    with COUNTS.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            volumes = {line: float(row[line]) for line in lines}
            # 日报按 0.01 万人次取整，分项之和可能和公布总数差一个末位。
            if min(volumes.values()) <= 0 or abs(sum(volumes.values()) - float(row["network_10k"])) > .05:
                raise ValueError(f"线路客流不完整或与全网总数不符：{row['service_date']}")
            yield row["service_date"], volumes


def main():
    rows = compare_stations(build_directed_network())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0])
        writer.writeheader()
        for r in rows:
            writer.writerow({k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()})
    print(OUT)


if __name__ == "__main__":
    main()
