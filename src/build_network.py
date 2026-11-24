"""从唯一边表构建并导出无向分钟图。"""

import argparse
import csv
import hashlib
import io
from collections import defaultdict
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data/metro_edges.csv"
GRAPH_FILE = ROOT / "results/metro.graphml"
TRANSFER_MINUTES = 5.0


def station_id(station: str, line: str) -> str:
    return f"{station}_L{line}"


def clock_minutes(clock: str) -> int:
    hour, minute = map(int, clock.split(":"))
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError(f"无效时刻：{clock}")
    return hour * 60 + minute


def ride_minutes(row: dict) -> float:
    ab = (clock_minutes(row["ab_time_at_b"]) - clock_minutes(row["ab_time_at_a"])) % 1440
    ba = (clock_minutes(row["ba_time_at_a"]) - clock_minutes(row["ba_time_at_b"])) % 1440
    if min(ab, ba) == 0 or not (row["source_ab"] and row["source_ba"]):
        raise ValueError(f"缺少有效的同车区间时刻或来源：{row}")
    return (ab + ba) / 2


def build_weighted_network(path: Path = DATA_FILE) -> nx.Graph:
    """站点—线路节点保证跨线必须经过显式换乘边。"""
    content = path.read_bytes().replace(b"\r\n", b"\n")
    graph = nx.Graph(weight_unit="minutes", source_table=path.name,
                     source_sha256=hashlib.sha256(content).hexdigest())
    running = defaultdict(list)
    transfers = []
    for row in csv.DictReader(io.StringIO(content.decode("utf-8-sig"))):
        if row["edge_type"] == "running":
            running[row["line_a"]].append(row)
        elif row["edge_type"] == "transfer":
            transfers.append(row)
        else:
            raise ValueError(f"未知边类型：{row['edge_type']}")

    for line, rows in sorted(running.items()):
        rows.sort(key=lambda row: int(row["sequence"]))
        for i, row in enumerate(rows, start=1):
            a, b = row["station_a"], row["station_b"]
            if (not (line and a and b) or a == b or row["line_b"] != line
                    or int(row["sequence"]) != i or (i > 1 and rows[i - 2]["station_b"] != a)):
                raise ValueError(f"线路 {line} 的站序不连续或端点错误：{row}")
            u, v = station_id(a, line), station_id(b, line)
            if v in graph:
                raise ValueError(f"重复站点或运行边：{v}")
            minutes = float(row["minutes"])
            if minutes != ride_minutes(row):
                raise ValueError(f"区间权重与双向时刻不符：{a}—{b}")
            if i == 1:
                graph.add_node(u, station=a, line=line, sequence=i)
            graph.add_node(v, station=b, line=line, sequence=i + 1)
            graph.add_edge(u, v, edge_type="running", line=line, weight=minutes)

    for row in transfers:
        station, a, b = row["station_a"], row["line_a"], row["line_b"]
        u, v = station_id(station, a), station_id(row["station_b"], b)
        if (station != row["station_b"] or a == b or u not in graph or v not in graph
                or graph.has_edge(u, v)):
            raise ValueError(f"无效或重复的换乘边：{row}")
        minutes = float(row["minutes"])
        if minutes != TRANSFER_MINUTES:
            raise ValueError(f"基准换乘权重须为 {TRANSFER_MINUTES:g} 分钟：{row}")
        graph.add_edge(u, v, edge_type="transfer", station=station,
                       weight=minutes, transfer_status=row["transfer_status"])
    if not graph or not transfers or not nx.is_connected(graph):
        raise ValueError("基准线网不连通")
    return graph


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DATA_FILE)
    parser.add_argument("--output", type=Path, default=GRAPH_FILE)
    args = parser.parse_args()
    graph = build_weighted_network(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(graph, args.output)
    print(f"{args.output}: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")


if __name__ == "__main__":
    main()
