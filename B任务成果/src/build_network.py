# -*- coding: utf-8 -*-
"""A：构建物理站点网络和站点—线路网络。

本模块是 B 项（中心性 / 路径评价 / 单站换乘中断）的数据入口。
它直接读取 ``Hefei_Metro_Project/data/`` 下的线路站序 CSV，
按项目 README 约定的口径重建两种网络，并与 A 项已保存的
GraphML 结果做一致性校验，避免 B 项基于过期或误读的拓扑做实验。

口径（与 README、data_sources.md 一致）
------------------------------------
物理车站网络
    节点 = 物理车站；边 = 相邻车站之间的线路连接。
    同名候选换乘站在主网络中合并为单个节点。
    用于：度、介数等结构指标。

站点—线路网络
    节点 = （车站, 线路）副本，如 ``合肥南站_L1``。
    ``running`` 边 = 同线相邻车站的运行边。
    ``candidate_transfer`` 边 = 同名车站的不同线路层节点连接，
    带有 ``traversable="false"`` 属性。

重要说明
--------
1. NetworkX 不会根据 ``traversable="false"`` 自动禁止通行。
   本模块只负责建图；是否把候选换乘边当作可通行，
   由调用方（routing 模块）通过 ``include_transfers`` 等参数显式决定，
   并在结果中记录所用假设。
2. 主实验（1—8 号线）不含 S1；S1 仅作为独立试乘情景。
3. 图中不写入任何编造的运行分钟数或换乘分钟数。
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx

# ==============================
# 路径设置
# ==============================

SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent


def _resolve_data_dir() -> Path:
    """定位 Hefei_Metro_Project/data。

    优先级：
    1. 环境变量 ``HEFEI_DATA_DIR``（便于把代码复制到别处单独运行）；
    2. ``<代码上级目录>/Hefei_Metro_Project/data``（项目内正常运行）；
    3. 常见兜底：原始项目目录 ``hefei-metro-main/hefei-metro-main/...``。
    """
    env = os.environ.get("HEFEI_DATA_DIR")
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p
        raise FileNotFoundError(f"HEFEI_DATA_DIR 指向的目录不存在：{p}")

    for candidate in (
        PROJECT_ROOT / "Hefei_Metro_Project" / "data",
        Path(r"D:\实验课\复杂系统\hefei-metro-main\hefei-metro-main")
        / "Hefei_Metro_Project" / "data",
    ):
        if candidate.is_dir():
            return candidate

    raise FileNotFoundError(
        "未找到 Hefei_Metro_Project/data；请设置环境变量 HEFEI_DATA_DIR 指向该目录。"
    )


DATA_DIR = _resolve_data_dir()
METRO_DIR = DATA_DIR.parent
GRAPHML_DIR = METRO_DIR / "results"

#: 主实验线路编号（S1 不进入主实验）
MAIN_LINES: Tuple[str, ...] = tuple(str(i) for i in range(1, 9))

#: 主实验多层网络 GraphML（由 18_export_main_network.py 生成）
MAIN_MULTILAYER_GRAPHML = GRAPHML_DIR / "multilayer_network_main.graphml"

#: A 项保存的不含属性的物理网络
PHYSICAL_GRAPHML = GRAPHML_DIR / "physical_network.graphml"


# ==============================
# 读取工具
# ==============================

def _read_csv(path: Path) -> List[Dict[str, str]]:
    """读取 UTF-8（含 BOM）CSV，去除首尾空白。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        for row in rows
    ]


def read_line_stations(line: str, include_s1: bool = False):
    """读取一条线路的站序表，返回 [(station, status), ...]。"""
    if line == "S1":
        if not include_s1:
            return []
        path = DATA_DIR / "s1_stations.csv"
    else:
        path = DATA_DIR / f"line{line}_stations.csv"

    rows = _read_csv(path)
    rows.sort(key=lambda r: int(r["sequence"]))
    return [(r["station"], r.get("status", "")) for r in rows]


def station_id(station: str, line: str) -> str:
    """站点—线路节点 ID，例如 合肥南站_L1。"""
    return f"{station}_L{line}"


def read_transfer_edges():
    """读取候选换乘边表。

    返回 [(station, line_a, line_b, edge_type, status), ...]。
    """
    rows = _read_csv(DATA_DIR / "transfer_edges.csv")
    out = []
    for r in rows:
        out.append(
            (
                r["station"],
                r["line_a"],
                r["line_b"],
                r.get("edge_type", "candidate_transfer"),
                r.get("status", "pending_verification"),
            )
        )
    return out


# ==============================
# 建网
# ==============================

def build_multilayer_network(
    lines: Tuple[str, ...] = MAIN_LINES,
    add_transfers: bool = True,
) -> nx.Graph:
    """构建站点—线路多层网络。

    参数
    ----
    lines
        参与建网的线路编号，默认 1—8 号线（主实验）。
    add_transfers
        是否加入候选换乘边。``True`` 时加入但不改 ``traversable`` 属性；
        ``False`` 时只保留运行边，得到各线互不相连的 8 个分量。
    """
    G = nx.Graph()

    for line in lines:
        stations = read_line_stations(line)
        if not stations:
            continue
        for station, status in stations:
            G.add_node(
                station_id(station, line),
                station=station,
                line=line,
                node_type="station",
                status=status,
            )
        for (s_a, _), (s_b, _) in zip(stations, stations[1:]):
            G.add_edge(
                station_id(s_a, line),
                station_id(s_b, line),
                edge_type="running",
                line=line,
            )

    if add_transfers:
        for station, line_a, line_b, edge_type, status in read_transfer_edges():
            u = station_id(station, line_a)
            v = station_id(station, line_b)
            if u not in G or v not in G:
                # 例如合肥西站 (3;S1)：S1 不在主实验，跳过而不报错
                continue
            G.add_edge(
                u,
                v,
                edge_type=edge_type,
                station=station,
                line_a=line_a,
                line_b=line_b,
                verification_status=status,
                traversable="false",
            )

    return G


def build_physical_network(
    lines: Tuple[str, ...] = MAIN_LINES,
) -> nx.Graph:
    """构建物理车站网络：同名站合并为单个节点。"""
    G = nx.Graph()

    # 先记录每个物理站由哪些线路服务
    station_lines: Dict[str, List[str]] = {}
    for line in lines:
        for station, status in read_line_stations(line):
            station_lines.setdefault(station, []).append(line)
            G.add_node(
                station,
                station=station,
                node_type="physical_station",
                status=status,
            )

    for station, served in station_lines.items():
        G.nodes[station]["lines"] = ";".join(sorted(served, key=_line_sort_key))
        G.nodes[station]["line_count"] = len(served)
        G.nodes[station]["interchange_status"] = (
            "transfer_station" if len(served) > 1 else "ordinary_station"
        )

    for line in lines:
        stations = [s for s, _ in read_line_stations(line)]
        for s_a, s_b in zip(stations, stations[1:]):
            if s_a == s_b:
                continue
            if G.has_edge(s_a, s_b):
                # 同一对物理站在多条线路上相邻时记录线路来源
                old = G[s_a][s_b]["line"]
                G[s_a][s_b]["line"] = f"{old};{line}"
            else:
                G.add_edge(s_a, s_b, line=line, edge_type="running", status="operating")

    return G


def _line_sort_key(line: str):
    return (0, int(line)) if line.isdigit() else (1, line)


# ==============================
# 站点—线路映射与校验
# ==============================

def build_station_line_index(G: nx.Graph) -> Dict[str, List[str]]:
    """物理站名 -> 该站在多层网络中的线路副本节点列表。"""
    index: Dict[str, List[str]] = {}
    for node, data in G.nodes(data=True):
        index.setdefault(data["station"], []).append(node)
    for station in index:
        index[station].sort(key=lambda n: _line_sort_key(G.nodes[n]["line"]))
    return index


def transfer_station_names(G: nx.Graph) -> List[str]:
    """多层网络中拥有跨线副本的换乘站名（按出现顺序排序）。"""
    index = build_station_line_index(G)
    names = [s for s, nodes in index.items() if len(nodes) > 1]
    return sorted(names)


def compare_with_saved_graphml(lines: Tuple[str, ...] = MAIN_LINES) -> Dict[str, object]:
    """把重新构建的多层网络与 A 项保存的 GraphML 做一致性对比。

    仅用于校验，不修改任何文件；结果写入日志和报告。
    """
    report: Dict[str, object] = {}

    G_new = build_multilayer_network(lines=lines, add_transfers=True)
    report["rebuilt_nodes"] = G_new.number_of_nodes()
    report["rebuilt_edges"] = G_new.number_of_edges()

    if not MAIN_MULTILAYER_GRAPHML.exists():
        report["saved_graphml"] = "missing"
        report["consistent"] = "unknown"
        return report

    G_saved = nx.read_graphml(str(MAIN_MULTILAYER_GRAPHML))
    report["saved_nodes"] = G_saved.number_of_nodes()
    report["saved_edges"] = G_saved.number_of_edges()

    same_nodes = set(G_new.nodes()) == set(G_saved.nodes())
    same_edges = {(u, v) for u, v in G_new.edges()} == {(u, v) for u, v in G_saved.edges()}
    report["same_nodes"] = same_nodes
    report["same_edges"] = same_edges

    # 节点属性（站点名、线路）一致性
    attr_ok = True
    for node in G_new.nodes():
        if node in G_saved:
            for key in ("station", "line"):
                if G_new.nodes[node].get(key) != G_saved.nodes[node].get(key):
                    attr_ok = False
    report["same_node_attrs"] = attr_ok

    # 边类型一致性
    etype_ok = True
    for u, v in G_new.edges():
        if G_saved.has_edge(u, v):
            if G_new[u][v].get("edge_type") != G_saved[u][v].get("edge_type"):
                etype_ok = False
    report["same_edge_types"] = etype_ok

    report["consistent"] = bool(
        same_nodes and same_edges and attr_ok and etype_ok
        and report["rebuilt_nodes"] == report["saved_nodes"]
        and report["rebuilt_edges"] == report["saved_edges"]
    )
    return report


def network_summary(G: nx.Graph) -> Dict[str, object]:
    """多层网络的规模与结构摘要。"""
    n_running = sum(1 for _, _, d in G.edges(data=True) if d["edge_type"] == "running")
    n_transfer = sum(1 for _, _, d in G.edges(data=True) if d["edge_type"] != "running")

    G_running = nx.Graph()
    G_running.add_nodes_from(G.nodes())
    G_running.add_edges_from(
        (u, v) for u, v, d in G.edges(data=True) if d["edge_type"] == "running"
    )

    return {
        "nodes": G.number_of_nodes(),
        "running_edges": n_running,
        "candidate_transfer_edges": n_transfer,
        "total_edges": G.number_of_edges(),
        "physical_stations": len(build_station_line_index(G)),
        "transfer_stations": len(transfer_station_names(G)),
        "components_running_only": nx.number_connected_components(G_running),
        "components_with_transfers": nx.number_connected_components(G),
    }


def build_all() -> Tuple[nx.Graph, nx.Graph]:
    """返回 (物理车站网络, 站点—线路多层网络)。"""
    return build_physical_network(), build_multilayer_network()


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    G_phys, G_multi = build_all()

    print("=" * 56)
    print("A 项网络重建校验（B 项入口）")
    print("=" * 56)
    print(f"物理车站网络：节点 {G_phys.number_of_nodes()}，"
          f"边 {G_phys.number_of_edges()}，"
          f"连通分量 {nx.number_connected_components(G_phys)}")

    summary = network_summary(G_multi)
    put = lambda k, v: print(f"  {k:<26}{v}")
    print("站点—线路多层网络：")
    for k, v in summary.items():
        put(k, v)

    print("-" * 56)
    print("与 A 项 GraphML 的一致性校验：")
    cmp = compare_with_saved_graphml()
    for k, v in cmp.items():
        put(k, v)

    print("-" * 56)
    if cmp.get("consistent") is True:
        print("结论：重建网络与 A 项保存结果一致，B 项可直接使用。")
    elif cmp.get("consistent") == "unknown":
        print("结论：未找到 A 项 GraphML，仅使用重建结果。")
    else:
        print("结论：重建结果与 A 项 GraphML 不一致，请先核对数据版本！")
