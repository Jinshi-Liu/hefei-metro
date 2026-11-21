# -*- coding: utf-8 -*-
"""B：统一路径评价，分开统计不可达、绕行与额外换乘。

设计要点（对应计划书“指标口径与可靠性”）
------------------------------------
1. **同一组起终点**：所有情景共用同一组物理站点两两组合（195 座站、
   18915 个无序 OD 对，每对等权一次），不把“站点—线路”副本重复计为需求。
2. **统一代价规则**：站点—线路多层网络上的无向加权最短路。
   路径代价 = 站数（运行边，每条权重 1） + 换乘次数 × 换乘惩罚。
   换乘惩罚用“等效站数”表示，**不是真实分钟数**。
3. **分开报告**：
   - 不可达比例（基线可达但中断后不可达的 OD 占比）；
   - 仍可达行程的绕行代价（额外站数与额外换乘次数）；
   - 网络效率作为辅证。
   不把不可达行程混进“平均出行时间”里，避免只统计幸存路径造成误判。
4. **固定并列处理**：最短路以 ``(代价, 换乘次数, 乘车区间数)``
   比较状态，堆按节点名稳定处理并列；相同输入及顺序可复现。

三种计价口径
------------
- ``stations``：换乘惩罚 = 0（纯粹站数，即“站数模型”）。
- ``transfers_x1``：换乘惩罚 = 1 站（1 次换乘 ≈ 多坐 1 站）。
- ``transfers_x2``：换乘惩罚 = 2 站（更偏向少换乘的出行习惯）。

为什么需要“换乘边计数”而不是只读边权重
--------------------------------------
起终点可选该物理站的线路副本，上下车不额外收费。为了只统计
**真正的跨线换乘**，路径分析中额外记录换乘边条数 ``k``，
于是：换乘次数 = k，乘车区间数 = L - k（L 为路径边数）。

权重展开：运行边权重 1、换乘边权重 p，则路径代价
``cost = (L - k)·1 + k·p = L + (p-1)·k``。

- ``p = 0``（``stations``）：``cost = L - k``，即**纯站数**，
  换乘不额外计价，相当于“站数模型”。
- ``p = 1``（``transfers_x1``）：``cost = L``，即乘车区间数 + 换乘次数。
- ``p = 2``（``transfers_x2``，基准）：``cost = L + k``，
  即乘车区间数 + 换乘次数 × 2，一次换乘等效多坐 2 个区间。

因此 ``stations`` 与 ``transfers_x1`` **并不等价**；只有把换乘惩罚
设为 1 时才与“站数 + 换乘次数”展开式一致。三者都保留，便于 C 项
做参数敏感性分析。
"""

from __future__ import annotations

import csv
import heapq
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import networkx as nx

from build_network import build_multilayer_network

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
TABLES_DIR = RESULTS_DIR / "tables"

#: 计划书要求保存的参数：换乘惩罚按“等效站数”计
COST_MODELS: Dict[str, int] = {
    "stations": 0,        # 纯站数
    "transfers_x1": 1,    # 1 次换乘 ≈ 1 站
    "transfers_x2": 2,    # 1 次换乘 ≈ 2 站（基准）
}

DEFAULT_MODEL = "transfers_x2"


# ==============================
# 基础数据结构
# ==============================

@dataclass
class PathResult:
    """一次最短出行路径的评价结果。"""

    reachable: bool = False
    cost: Optional[float] = None          # 加权代价（等效站数）
    edges: Optional[int] = None           # 路径边数 L（= 运行边数 + 换乘边数）
    transfers: Optional[int] = None       # 换乘次数 k
    rides: Optional[int] = None           # 乘车区间数 = L - k
    stations: Optional[int] = None        # 途经线路副本节点数 = L + 1
    nodes: Tuple[str, ...] = ()           # 站点—线路节点序列
    physical_stations: Optional[int] = None  # 途经不同物理站点数
    network_distance: Optional[int] = None  # 物理站点网络上的站数最短路（对照）


@dataclass
class ODRecord:
    """一个 OD 对在基线与中断情景下的对照。"""

    origin: str
    destination: str
    baseline: PathResult
    disrupted: PathResult


@dataclass
class EvaluationSummary:
    """一组 OD 对照的汇总指标。"""

    model: str
    n_pairs: int = 0
    n_reachable_before: int = 0
    n_reachable_after: int = 0
    n_lost: int = 0                 # 基线可达、中断后不可达
    n_detour: int = 0               # 仍可达但代价增加
    n_same: int = 0                 # 仍可达且代价不变
    unreachable_ratio: float = 0.0
    detour_ratio: float = 0.0
    mean_cost_before: float = 0.0
    mean_cost_after: float = 0.0
    mean_detour_among_survivors: float = 0.0   # 仅幸存行程
    mean_detour_all: float = 0.0               # 幸存行程 + 不可达记为缺失
    extra_stations_total: float = 0.0
    extra_transfers_total: float = 0.0
    total_baseline_cost: float = 0.0
    total_after_cost: float = 0.0
    efficiency_before: float = 0.0
    efficiency_after: float = 0.0
    extra: Dict[str, object] = field(default_factory=dict)


# ==============================
# 代价模型与图构建
# ==============================

def transfer_penalty(model: str) -> int:
    """取计价口径对应的换乘惩罚（等效站数）。"""
    if model not in COST_MODELS:
        raise ValueError(f"未知计价口径 {model}；可选：{sorted(COST_MODELS)}")
    return COST_MODELS[model]


def build_cost_graph(
    G_multilayer: nx.Graph,
    model: str = DEFAULT_MODEL,
    include_transfers: bool = True,
    closed_transfer_stations: Iterable[str] = (),
) -> Tuple[nx.Graph, dict]:
    """按计价口径生成带权多重图（保留运行边与换乘边两类）。

    参数
    ----
    G_multilayer
        站点—线路多层网络。
    model
        计价口径，见 ``COST_MODELS``。
    include_transfers
        是否把候选换乘边视为可通行。
        ``True`` 表示“在明确说明假设后建立单独的实验情景网络”
        （README 给 B 项的授权）；``False`` 表示只保留运行边，
        此时 8 条线路互不相连，跨线 OD 全部不可达。
    closed_transfer_stations
        换乘中断的物理站名集合：只删除该站的换乘边，
        保留该站各线路副本节点与列车运行边（列车通过、正常上下车）。

    返回
    ----
    (cost_graph, info)
    """
    penalty = transfer_penalty(model)
    closed = set(closed_transfer_stations)

    C = nx.MultiGraph()
    C.add_nodes_from(G_multilayer.nodes(data=True))

    running = [(u, v) for u, v, d in G_multilayer.edges(data=True)
               if d["edge_type"] == "running"]

    # 运行边：权重 1（一个乘车区间 = 1 站）
    for u, v in running:
        C.add_edge(u, v, key="running", weight=1.0, edge_type="running")

    # 换乘边：权重 penalty，且必须被显式选择才会计入
    n_transfer_used = 0
    if include_transfers:
        for u, v, d in G_multilayer.edges(data=True):
            if d["edge_type"] == "running":
                continue
            station = d.get("station") or G_multilayer.nodes[u]["station"]
            if station in closed:
                continue
            # 即使 penalty=0 也给一个极小的正值占位，真正的换乘计数靠边类型
            weight = float(penalty) if penalty > 0 else 0.0
            C.add_edge(
                u, v,
                key="transfer",
                weight=weight,
                edge_type="transfer",
                station=station,
            )
            n_transfer_used += 1

    info = {
        "model": model,
        "transfer_penalty": penalty,
        "include_transfers": include_transfers,
        "closed_transfer_stations": sorted(closed),
        "running_edges": len(running),
        "transfer_edges": n_transfer_used,
    }
    return C, info


def station_index(G_multilayer: nx.Graph) -> Dict[str, List[str]]:
    """物理站名 -> 线路副本节点列表（已排序，保证可复现）。"""
    index: Dict[str, List[str]] = {}
    for node, data in G_multilayer.nodes(data=True):
        index.setdefault(data["station"], []).append(node)
    for station in index:
        index[station].sort(
            key=lambda n: (0, int(G_multilayer.nodes[n]["line"]))
            if str(G_multilayer.nodes[n]["line"]).isdigit()
            else (1, str(G_multilayer.nodes[n]["line"]))
        )
    return index


# ==============================
# 单源最短路（带换乘计数与确定性并列处理）
# ==============================

def _edge_options(C: nx.MultiGraph, u: str, v: str):
    """返回 u—v 之间可用的 (edge_type, weight) 选项，运行边优先枚举。"""
    options = []
    for key, data in C[u][v].items():
        options.append((data.get("edge_type", "running"), float(data["weight"])))
    # 稳定排序：运行边在前，再按权重升序
    options.sort(key=lambda t: (t[0] != "running", t[1]))
    return options


def single_source_shortest_paths(
    C: nx.MultiGraph,
    source: str,
) -> Tuple[Dict[str, Optional[float]], Dict[str, float], Dict[str, float], Dict[str, str]]:
    """从线路副本节点 ``source`` 出发的最短路。

    状态 = (累计代价, 累计换乘边条数, 累计运行边条数)。
    主键为代价；代价相同时取换乘次数更少者（计划书“固定并列处理方式”），
    再按节点名做最终确定性破并列。

    返回 (cost, transfers, rides, parent)，其中不可达节点 cost 为 None。
    """
    best_cost: Dict[str, Optional[float]] = {n: None for n in C.nodes()}
    best_tr: Dict[str, float] = {n: float("inf") for n in C.nodes()}
    best_rd: Dict[str, float] = {n: float("inf") for n in C.nodes()}
    parent: Dict[str, str] = {}

    best_cost[source] = 0.0
    best_tr[source] = 0.0
    best_rd[source] = 0.0

    # 堆元素：(代价, 换乘次数, 运行边数, 节点)
    heap: List[Tuple[float, float, float, str]] = [(0.0, 0.0, 0.0, source)]

    while heap:
        cost, tr, rd, u = heapq.heappop(heap)

        # 过期条目检查
        if best_cost.get(u) is None or cost > best_cost[u] + 1e-12:
            continue
        if abs(cost - best_cost[u]) <= 1e-12:
            if (tr, rd) > (best_tr[u], best_rd[u]):
                continue

        for v in C.neighbors(u):
            if v == u:
                continue
            for edge_type, weight in _edge_options(C, u, v):
                new_cost = cost + weight
                new_tr = tr + (1.0 if edge_type == "transfer" else 0.0)
                new_rd = rd + (1.0 if edge_type != "transfer" else 0.0)

                old_cost = best_cost.get(v)
                improved = (
                    old_cost is None
                    or new_cost < old_cost - 1e-12
                    or (
                        abs(new_cost - old_cost) <= 1e-12
                        and (new_tr, new_rd) < (best_tr[v], best_rd[v])
                    )
                )
                if improved:
                    best_cost[v] = new_cost
                    best_tr[v] = new_tr
                    best_rd[v] = new_rd
                    parent[v] = u
                    heapq.heappush(heap, (new_cost, new_tr, new_rd, v))

    return best_cost, best_tr, best_rd, parent


def _reconstruct(parent: Dict[str, str], source: str, target: str) -> Tuple[str, ...]:
    path = [target]
    node = target
    while node != source:
        node = parent[node]
        path.append(node)
    return tuple(reversed(path))


# ==============================
# OD 评价器
# ==============================

class ODEvaluator:
    """统一路径评价器：对同一组物理站点 OD 对做多次评价。"""

    def __init__(
        self,
        G_multilayer: nx.Graph,
        model: str = DEFAULT_MODEL,
        include_transfers: bool = True,
        network_distance: Optional[Dict[Tuple[str, str], Optional[int]]] = None,
    ):
        self.G = G_multilayer
        self.model = model
        self.include_transfers = include_transfers
        self.index = station_index(G_multilayer)
        self.stations: List[str] = sorted(self.index)
        self.network_distance = network_distance or {}
        # 基线计价图；中断情景通过 set_graph 切换
        self._baseline_graph, self.graph_info = build_cost_graph(
            G_multilayer, model=model, include_transfers=include_transfers
        )
        self._graph = self._baseline_graph
        self._cache: Dict[str, object] = {}

    # -------- 单源解析 --------

    def _line_copy_distances(self, station: str):
        """物理站 ``station`` 到全部线路副本节点的最短路（多源超源）。"""
        if station in self._cache:
            return self._cache[station]

        sources = self.index[station]
        best_cost: Dict[str, Optional[float]] = {n: None for n in self.G.nodes()}
        best_tr: Dict[str, float] = {n: float("inf") for n in self.G.nodes()}
        best_rd: Dict[str, float] = {n: float("inf") for n in self.G.nodes()}
        parent: Dict[str, str] = {}

        heap: List[Tuple[float, float, float, str]] = []
        for s in sources:
            best_cost[s] = 0.0
            best_tr[s] = 0.0
            best_rd[s] = 0.0
            heap.append((0.0, 0.0, 0.0, s))
        heapq.heapify(heap)

        C = self._graph
        while heap:
            cost, tr, rd, u = heapq.heappop(heap)
            if best_cost.get(u) is None or cost > best_cost[u] + 1e-12:
                continue
            if abs(cost - best_cost[u]) <= 1e-12 and (tr, rd) > (best_tr[u], best_rd[u]):
                continue

            for v in C.neighbors(u):
                if v == u:
                    continue
                for edge_type, weight in _edge_options(C, u, v):
                    new_cost = cost + weight
                    new_tr = tr + (1.0 if edge_type == "transfer" else 0.0)
                    new_rd = rd + (1.0 if edge_type != "transfer" else 0.0)
                    old = best_cost.get(v)
                    if (
                        old is None
                        or new_cost < old - 1e-12
                        or (abs(new_cost - old) <= 1e-12
                            and (new_tr, new_rd) < (best_tr[v], best_rd[v]))
                    ):
                        best_cost[v] = new_cost
                        best_tr[v] = new_tr
                        best_rd[v] = new_rd
                        parent[v] = u
                        heapq.heappush(heap, (new_cost, new_tr, new_rd, v))

        self._cache[station] = (best_cost, best_tr, best_rd, parent)
        return self._cache[station]

    def set_graph(self, C: nx.MultiGraph) -> None:
        """切换当前计价图并清空缓存（用于中断情景）。"""
        self._graph = C
        self._cache.clear()

    # -------- 单 OD 评价 --------

    def evaluate_pair(self, origin: str, destination: str) -> PathResult:
        if origin == destination:
            return PathResult(
                reachable=True, cost=0.0, edges=0, transfers=0, rides=0,
                stations=1, physical_stations=1, nodes=(self.index[origin][0],),
                network_distance=0,
            )

        best_cost, best_tr, best_rd, parent = self._line_copy_distances(origin)

        # 目标站：在所有线路副本中取最优
        candidates = []
        for node in self.index[destination]:
            c = best_cost.get(node)
            if c is None:
                continue
            candidates.append((c, best_tr[node], best_rd[node], node))
        if not candidates:
            return PathResult(
                reachable=False,
                network_distance=self.network_distance.get((origin, destination)),
            )

        candidates.sort()
        cost, tr, rd, target = candidates[0]
        actual_source = _walk_to_source(parent, target)
        nodes = _reconstruct(parent, actual_source, target)

        return PathResult(
            reachable=True,
            cost=cost,
            edges=len(nodes) - 1,
            transfers=int(round(tr)),
            rides=int(round(rd)),
            stations=len(nodes),
            physical_stations=len({self.G.nodes[n]["station"] for n in nodes}),
            nodes=nodes,
            network_distance=self.network_distance.get((origin, destination)),
        )

    def reset_to_baseline(self) -> None:
        """回到基线计价图。"""
        self.set_graph(self._baseline_graph)

    def summary_of(self, records: Sequence["ODRecord"]) -> "EvaluationSummary":
        """汇总一组 OD 对照。"""
        return summarize(records, self.model)


def _walk_to_source(parent: Dict[str, str], target: str) -> str:
    """沿父指针回溯到源节点（多源超源情景下返回真实起点副本）。"""
    node = target
    while node in parent:
        node = parent[node]
    return node


# ==============================
# OD 对照与汇总
# ==============================

def all_od_pairs(stations: Sequence[str]) -> List[Tuple[str, str]]:
    """无序物理站点 OD 对（i<j），每对等权一次。"""
    ordered = sorted(stations)
    return [(a, b) for i, a in enumerate(ordered) for b in ordered[i + 1:]]


def compute_network_distance_matrix(G_phys: nx.Graph) -> Dict[Tuple[str, str], Optional[int]]:
    """物理车站网络上的站数最短距离，仅作对照（不参与补偿计算）。"""
    dist: Dict[Tuple[str, str], Optional[int]] = {}
    for source, lengths in nx.all_pairs_shortest_path_length(G_phys):
        for target, d in lengths.items():
            if source < target:
                dist[(source, target)] = d
            elif target < source:
                dist[(target, source)] = d
    return dist


def global_efficiency(G: nx.Graph, weight: Optional[str] = None) -> float:
    """网络效率：全部无序节点对的 1/最短路 平均（不可达记为 0）。

    与计划书“辅以网络效率”一致，便于跨情景比较整体性能。
    """
    n = G.number_of_nodes()
    if n < 2:
        return 0.0
    total = 0.0
    for source, lengths in nx.all_pairs_dijkstra_path_length(G, weight=weight):
        for target, d in lengths.items():
            if source != target and d > 0:
                total += 1.0 / d
    return total / (n * (n - 1))


def station_physical_efficiency(
    C: nx.MultiGraph,
    stations: Sequence[str],
    index: Dict[str, List[str]],
) -> float:
    """物理站点口径的网络效率（1/加权代价，跨全部无序站点对平均）。

    换乘边权重为 0 时（``stations`` 口径）多起点等价使用最短路，
    因此统一采用“逐站多源最短路 + 站点层取最优”的方式，读取站点
    副本间的最小代价，不可达记 0。
    """
    ordered = sorted(stations)
    n = len(ordered)
    if n < 2:
        return 0.0

    total = 0.0
    for source in ordered:
        sources = index[source]
        # 多源 Dijkstra
        best: Dict[str, float] = {s: 0.0 for s in sources}
        heap: List[Tuple[float, str]] = [(0.0, s) for s in sources]
        heapq.heapify(heap)
        while heap:
            cost, u = heapq.heappop(heap)
            if cost > best.get(u, float("inf")) + 1e-12:
                continue
            for v in C.neighbors(u):
                if v == u:
                    continue
                w = min(float(data["weight"]) for data in C[u][v].values())
                nc = cost + w
                if nc < best.get(v, float("inf")) - 1e-12:
                    best[v] = nc
                    heapq.heappush(heap, (nc, v))

        for target in ordered:
            if target == source:
                continue
            d = min((best.get(t, float("inf")) for t in index[target]), default=float("inf"))
            if d < float("inf") and d > 0:
                total += 1.0 / d

    return total / (n * (n - 1))


def summarize(records: Sequence[ODRecord], model: str) -> EvaluationSummary:
    """把一组 OD 对照汇总成可直接进表的指标。"""
    s = EvaluationSummary(model=model, n_pairs=len(records))

    cost_before_total = 0.0
    cost_after_total = 0.0
    detour_surv = 0.0
    extra_st_total = 0.0
    extra_tr_total = 0.0

    for rec in records:
        b, d = rec.baseline, rec.disrupted
        if b.reachable:
            s.n_reachable_before += 1
            cost_before_total += b.cost
        if d.reachable:
            s.n_reachable_after += 1

        if b.reachable and not d.reachable:
            s.n_lost += 1
        elif b.reachable and d.reachable:
            delta_cost = d.cost - b.cost
            if delta_cost > 1e-9:
                s.n_detour += 1
                detour_surv += delta_cost
                if d.network_distance is not None and b.network_distance is not None:
                    extra_st_total += max(d.network_distance - b.network_distance, 0)
                extra_tr_total += max(d.transfers - b.transfers, 0)
                cost_after_total += d.cost
            else:
                s.n_same += 1
                cost_after_total += d.cost
        elif d.reachable:
            # 基线不可达但中断后可达（理论上不应出现，记录以防异常）
            cost_after_total += d.cost

    n = max(s.n_pairs, 1)
    s.unreachable_ratio = s.n_lost / n
    s.detour_ratio = s.n_detour / n
    s.mean_cost_before = cost_before_total / max(s.n_reachable_before, 1)
    s.mean_cost_after = cost_after_total / max(s.n_reachable_after, 1)
    s.mean_detour_among_survivors = detour_surv / max(s.n_detour, 1)
    # 全 OD 平均增量：不可达行程不并入，另以不可达比例单列
    s.mean_detour_all = detour_surv / n
    s.extra_stations_total = extra_st_total
    s.extra_transfers_total = extra_tr_total
    s.total_baseline_cost = cost_before_total
    s.total_after_cost = cost_after_total
    return s


def transfer_loss_index(summary: EvaluationSummary) -> float:
    """单站中断的出行损失指数（用于排序，口径固定）。

    定义：``损失指数 = 全 OD 平均增量代价 / 全 OD 基线平均代价``。
    分子只含仍可达行程的增量（幸存行程绕行），因此它**不含**不可达
    行程；不可达行程由 ``unreachable_ratio`` 单独报告。二者必须并列
    解读，不合并成单一的“真实时间损失”。取值越大表示换乘中断对该
    站的影响越大。
    """
    baseline_mean = summary.mean_cost_before
    if baseline_mean <= 0:
        return 0.0
    return summary.mean_detour_all / baseline_mean


# ==============================
# CSV 输出
# ==============================

def write_csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})
