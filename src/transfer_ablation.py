"""消融整座车站的换乘边，比较全线网的可达性和分钟代价。"""

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.stats import spearmanr

from .build_network import GRAPH_FILE, ROOT

OUTPUT = ROOT / "results/transfer_ablation"
SENSITIVITY_MINUTES = (3.0, 7.0)
STRATEGIES = {"random": "随机", "betweenness": "介数顺序", "single_loss": "单站损失顺序"}
CURVE_METRICS = {
    "unreachable_share": "不可达 OD 比例",
    "mean_added_min_reachable": "仍可达 OD 平均额外分钟",
    "efficiency_ratio": "相对出行效率",
}


class MetroAblation:
    def __init__(self, graph):
        if graph.is_directed() or graph.is_multigraph() or graph.graph.get("weight_unit") != "minutes":
            raise ValueError("实验要求无向、非多重的分钟图")
        station_of = nx.get_node_attributes(graph, "station")
        nodes = sorted(graph, key=lambda node: (station_of[node], node))
        indices = {node: i for i, node in enumerate(nodes)}
        stops = [station_of[node] for node in nodes]
        self.stations = sorted(set(stops))
        self.starts = [i for i, name in enumerate(stops) if i == 0 or stops[i - 1] != name]
        self.od = np.triu_indices(len(self.stations), k=1)
        self.running = np.zeros((len(nodes), len(nodes)))
        self.transfer_edges = defaultdict(list)
        self.lines = defaultdict(set)
        self.physical = nx.Graph()
        self.physical.add_nodes_from(self.stations)
        penalties = set()
        for u, v, edge in graph.edges(data=True):
            i, j, minutes = indices[u], indices[v], float(edge["weight"])
            if not 0 < minutes < float("inf"):
                raise ValueError(f"边权重必须为正分钟数：{u}—{v}")
            line_u, line_v = graph.nodes[u]["line"], graph.nodes[v]["line"]
            kind = edge["edge_type"]
            if kind == "running" and line_u == line_v and station_of[u] != station_of[v]:
                self.running[i, j] = self.running[j, i] = minutes
                self.physical.add_edge(station_of[u], station_of[v])
            elif kind == "transfer" and line_u != line_v and station_of[u] == station_of[v]:
                station = station_of[u]
                self.transfer_edges[station].append((i, j))
                self.lines[station].update((line_u, line_v))
                penalties.add(minutes)
            else:
                raise ValueError(f"非预期的边类型或端点：{u}—{v}")
        if len(penalties) != 1 or not nx.is_connected(graph):
            raise ValueError("基准图必须连通，且所有换乘边使用同一权重")
        self.transfer_minutes = penalties.pop()

    def distances(self, closed=(), transfer_minutes=None):
        """依次返回所有无序物理 OD 的最短分钟数；不可达为无穷。"""
        closed = set(closed)
        unknown = closed - self.transfer_edges.keys()
        if unknown:
            raise ValueError(f"不是换乘站：{unknown}")
        minutes = self.transfer_minutes if transfer_minutes is None else transfer_minutes
        if not 0 < minutes < float("inf"):
            raise ValueError("换乘分钟必须为正")
        weights = self.running.copy()
        for station, edges in self.transfer_edges.items():
            if station not in closed:
                for i, j in edges:
                    weights[i, j] = weights[j, i] = minutes
        weighted = dijkstra(csr_matrix(weights), directed=False)
        # 每个物理 OD 取起点和终点的所有线路副本组合的最小值；不串联不同 OD。
        physical = np.minimum.reduceat(weighted, self.starts, axis=0)
        physical = np.minimum.reduceat(physical, self.starts, axis=1)
        return physical[self.od]


@dataclass(frozen=True)
class Outcome:
    unreachable_od: int
    unreachable_share: float
    slower_od: int
    mean_added_min_reachable: float | None
    mean_added_min_slower: float | None
    max_added_min: float | None
    efficiency_ratio: float


def measure(base, after, base_efficiency):
    reachable = np.isfinite(after)
    extra = after[reachable] - base[reachable]
    if (extra < -1e-9).any():
        raise ValueError("删除换乘边后最短路代价不应降低")
    slower = extra[extra > 1e-9]
    lost = int((~reachable).sum())
    return Outcome(lost, lost / len(base), len(slower),
                   float(extra.mean()) if len(extra) else None,
                   float(slower.mean()) if len(slower) else None,
                   float(extra.max()) if len(extra) else None,
                   float((1 / after[reachable]).sum()) / (len(base) * base_efficiency))


def cohort_check(metro, base, transfer_minutes, candidate):
    if candidate is None:
        return None
    _, strategy, k, order = candidate
    before = metro.distances(order[:k - 1], transfer_minutes)
    after = metro.distances(order[:k], transfer_minutes)
    reachable_before, common = np.isfinite(before), np.isfinite(after)
    if (~reachable_before & common).any():
        raise ValueError("中断集合扩大后，不可达行程不应恢复")
    dropped = reachable_before & ~common
    return dict(strategy=strategy, before_k=k - 1, after_k=k, newly_closed=order[k - 1],
                reachable_before=int(reachable_before.sum()), reachable_after=int(common.sum()),
                mean_added_before=float((before - base)[reachable_before].mean()),
                mean_added_after=float((after - base)[common].mean()),
                shared_od_mean_before=float((before - base)[common].mean()),
                shared_od_mean_after=float((after - base)[common].mean()),
                newly_unreachable_od=int(dropped.sum()),
                newly_unreachable_prior_mean_added=float((before - base)[dropped].mean()))


def analyze(graph, repeats, seed):
    if repeats < 1:
        raise ValueError("随机序列数必须为正")
    metro = MetroAblation(graph)
    stations = sorted(metro.transfer_edges)
    cent = nx.betweenness_centrality(metro.physical, weight=None)
    by_cent = sorted(stations, key=lambda s: (-cent[s], s))
    cent_rank = {station: i for i, station in enumerate(by_cent, 1)}
    rng = random.Random(seed)
    trials = [("random", rng.sample(stations, len(stations))) for _ in range(repeats)]
    baseline = metro.transfer_minutes
    single_rows, curve_rows = [], []
    summary = dict(weight_unit="minutes", baseline_transfer_minutes=baseline,
                   random_repeats=repeats, random_seed=seed, od_pairs=len(metro.od[0]),
                   physical_stations=len(metro.stations), station_line_nodes=len(graph),
                   lines=sorted({attrs["line"] for _, attrs in graph.nodes(data=True)}),
                   running_edges=graph.number_of_edges() - sum(map(len, metro.transfer_edges.values())),
                   transfer_edges=sum(map(len, metro.transfer_edges.values())),
                   transfer_stations=len(stations), settings=[])

    for penalty in [baseline, *[p for p in SENSITIVITY_MINUTES if p != baseline]]:
        base = metro.distances(transfer_minutes=penalty)
        if not np.isfinite(base).all():
            raise ValueError("基线存在不可达 OD")
        base_efficiency = float((1 / base).mean())
        cache = {}

        def outcome(closed):
            key = frozenset(closed)
            if key not in cache:
                cache[key] = measure(base, metro.distances(key, penalty), base_efficiency)
            return cache[key]

        singles = {station: outcome([station]) for station in stations}
        by_loss = sorted(stations, key=lambda s: (-singles[s].unreachable_od,
                         -(singles[s].mean_added_min_reachable or 0), s))
        if penalty == baseline:
            single_rows = [dict(station=station, lines=";".join(sorted(metro.lines[station])),
                                removed_transfer_edges=len(metro.transfer_edges[station]),
                                betweenness=cent[station], betweenness_rank=cent_rank[station],
                                loss_rank=rank, **asdict(singles[station]))
                           for rank, station in enumerate(by_loss, 1)]
            # 多站对照的站序固定，调换乘时间时不重排。
            summary["fixed_orders"] = {"betweenness": by_cent, "single_loss": by_loss}
            schedules = [*trials, ("betweenness", by_cent), ("single_loss", by_loss)]
        areas, groups = defaultdict(list), defaultdict(list)
        candidate = None
        for strategy, order in schedules:
            previous = None
            area = 0.0
            for k in range(len(order) + 1):
                state = outcome(order[:k])
                if penalty == baseline:
                    groups[strategy, k].append(state)
                if previous:
                    if (state.unreachable_od < previous.unreachable_od
                            or state.efficiency_ratio > previous.efficiency_ratio + 1e-9):
                        raise ValueError("嵌套消融的可达性或效率违反单调性")
                    area += (previous.efficiency_ratio + state.efficiency_ratio) / (2 * len(order))
                    if (penalty == baseline and strategy != "random"
                            and state.unreachable_od > previous.unreachable_od
                            and state.mean_added_min_reachable is not None):
                        drop = previous.mean_added_min_reachable - state.mean_added_min_reachable
                        if drop > (candidate[0] if candidate else 1e-9):
                            candidate = (drop, strategy, k, order)
                previous = state
            areas[strategy].append(area)

        for (strategy, k), group in sorted(groups.items()):
            row = dict(strategy=strategy, k=k, samples=len(group))
            for metric in (*CURVE_METRICS, "unreachable_od", "slower_od", "mean_added_min_slower"):
                values = [v for state in group if (v := getattr(state, metric)) is not None]
                row[f"{metric}_mean"] = float(np.mean(values)) if values else None
                if metric in CURVE_METRICS:
                    for name, q in (("p025", .025), ("p975", .975)):
                        row[f"{metric}_{name}"] = float(np.quantile(values, q)) if values else None
            curve_rows.append(row)
        summary["settings"].append(dict(transfer_minutes=penalty, mean_baseline_minutes=float(base.mean()),
                                        structural_vs_loss_spearman=float(spearmanr(
                                            range(1, len(stations) + 1), [cent_rank[s] for s in by_loss]).statistic)
                                        if len(stations) > 1 else None,
                                        top_five_overlap=len(set(by_cent[:5]) & set(by_loss[:5])),
                                        top_five_single_loss=by_loss[:5],
                                        efficiency_auc={s: float(np.mean(v)) for s, v in areas.items()}))
        if penalty == baseline:
            summary["fixed_cohort"] = cohort_check(metro, base, penalty, candidate)
    return single_rows, curve_rows, summary


def write_table(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def plot_results(out, single, curves, baseline):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    plt.rcParams.update({"font.family": "sans-serif", "axes.unicode_minus": False,
                         "font.sans-serif": ["Microsoft YaHei", "Noto Sans CJK SC", "SimHei", "DejaVu Sans"]})
    single = single[::-1]
    fig, axes = plt.subplots(1, 3, sharey=True, figsize=(11, 7), layout="constrained")
    names = [r["station"] for r in single]
    measures = [
        ("unreachable_share", "不可达 OD 比例", "#a64b35"),
        ("mean_added_min_reachable", "仍可达组平均额外分钟", "#245679"),
        ("mean_added_min_slower", "仅变慢组平均额外分钟", "#bc6c25"),
    ]
    for ax, (field, label, color) in zip(axes, measures):
        ax.barh(names, [r[field] or 0 for r in single], color=color)
        ax.set_xlabel(label)
        ax.set_axisbelow(True)
        ax.set_xlim(left=0)
        ax.grid(axis="x", alpha=.22)
    axes[0].xaxis.set_major_formatter(PercentFormatter(1))
    fig.suptitle(f"单站换乘消融｜换乘 {baseline:g} 分钟")
    fig.savefig(out / "single_station.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(9, 8), layout="constrained")
    for ax, (metric, label) in zip(axes, CURVE_METRICS.items()):
        for (strategy, name), color in zip(STRATEGIES.items(), ("#377a71", "#245679", "#bc6c25")):
            rows = [r for r in curves if r["strategy"] == strategy]
            k = [r["k"] for r in rows]
            ax.plot(k, [r[f"{metric}_mean"] for r in rows], label=name, color=color)
            if strategy == "random":
                ax.fill_between(k, [r[f"{metric}_p025"] for r in rows],
                                [r[f"{metric}_p975"] for r in rows], color=color, alpha=.18,
                                label="随机序列经验分位区间" if metric == "unreachable_share" else None)
        ax.set_ylabel(label)
        ax.grid(alpha=.22)
        if metric != "mean_added_min_reachable":
            ax.yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].legend(loc="upper left", ncols=2)
    axes[-1].set_xlabel("不能换乘的物理站数量")
    axes[-1].set_xticks(range(0, max(k) + 1, 2))
    fig.suptitle(f"多站换乘消融｜换乘 {baseline:g} 分钟")
    fig.savefig(out / "multi_station.png", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=GRAPH_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261116)
    args = parser.parse_args()
    graph = nx.read_graphml(args.graph)
    single, curves, summary = analyze(graph, args.repeats, args.seed)
    summary.update(graph_file=args.graph.name, source_sha256=graph.graph.get("source_sha256"),
                   graph_sha256=hashlib.sha256(args.graph.read_bytes().replace(b"\r\n", b"\n")).hexdigest())
    args.output.mkdir(parents=True, exist_ok=True)
    write_table(args.output / "single_station.csv", single)
    write_table(args.output / "multi_station.csv", curves)
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")
    plot_results(args.output, single, curves, summary["baseline_transfer_minutes"])
    print(f"{args.output}: {len(single)} single-station results, {len(curves)} multi-station summaries")


if __name__ == "__main__":
    main()
