# -*- coding: utf-8 -*-
"""B/C：单站换乘中断、随机与针对性中断及参数敏感性。

本版本完成 B 项主体：**单站换乘中断实验**（逐站关闭换乘连接）。

实验设计（严格对应计划书“干扰模拟”“指标口径与可靠性”）
------------------------------------------------------
1. **关闭的是什么**：对每座候选换乘站，逐一关闭该站的换乘连接，
   保留各线路副本节点、列车运行边与正常上下车。
   —— 这不是“删除整座车站”，两者必须分开报告。
2. **同一组起终点**：所有情景共用同一组物理站点 OD 对
   （195 站、18915 个无序对，每对等权一次）。
3. **统一代价规则**：站点—线路网络上的加权最短路，
   代价 = 乘车区间数 + 换乘次数 × 换乘惩罚（基准惩罚 2 站）。
4. **分开报告**：不可达比例、仍可达行程的绕行代价（额外站数、
   额外换乘次数）、网络效率。不可达行程单列，不并入平均出行时间。
5. **可复现**：固定并列处理方式、保存参数与所依据的数据版本。

产出
----
- ``B04_single_transfer_disruption.csv``：逐站损失表（基准口径）
- ``B05_od_detail_<station>.csv``：代表站的 OD 级明细（可选）
- ``B06_baseline_od_stats.csv``：基线出行格局（换乘依赖度）
- ``B07_cost_model_sensitivity.csv``：换乘惩罚参数敏感性
- ``B08_centrality_vs_loss.csv``：结构排名与出行损失排名对照
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import networkx as nx

from build_network import (
    build_multilayer_network,
    build_physical_network,
    compare_with_saved_graphml,
    network_summary,
    transfer_station_names,
)
from centrality import (
    build_ranking_table,
    build_transfer_ranking_table,
    competition_rank,
    compute_centralities,
)
import routing as rt

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
TABLES_DIR = RESULTS_DIR / "tables"

#: 基准计价口径
BASELINE_MODEL = "transfers_x2"

#: 参数敏感性用的口径
SENSITIVITY_MODELS = ("stations", "transfers_x1", "transfers_x2")

#: 随机种子（本阶段单站实验不含随机过程，保留以便 C 项接手）
RANDOM_SEED = 20261116


# ==============================
# 工具
# ==============================

def write_csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman 秩相关（无 scipy 依赖，平均秩处理并列）。"""
    def ranks(vals: Sequence[float]) -> List[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        out = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and abs(vals[order[j + 1]] - vals[order[i]]) < 1e-12:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    n = len(rx)
    if n < 2:
        return float("nan")
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else float("nan")


# ==============================
# 基线出行格局
# ==============================

def baseline_od_statistics(
    evaluator: rt.ODEvaluator,
    pairs: Sequence[Tuple[str, str]],
) -> Tuple[List[Dict[str, object]], Dict[Tuple[str, str], rt.PathResult], "rt.EvaluationSummary"]:
    """评价全部 OD 对，返回 (逐 OD 明细, 结果字典, 汇总)。"""
    detail: List[Dict[str, object]] = []
    results: Dict[Tuple[str, str], rt.PathResult] = {}

    for origin, destination in pairs:
        r = evaluator.evaluate_pair(origin, destination)
        results[(origin, destination)] = r
        detail.append(
            {
                "origin": origin,
                "destination": destination,
                "reachable": int(r.reachable),
                "cost": r.cost if r.reachable else "",
                "rides": r.rides if r.reachable else "",
                "transfers": r.transfers if r.reachable else "",
                "physical_stations": r.physical_stations if r.reachable else "",
            }
        )

    records = [
        rt.ODRecord(o, d, results[(o, d)], results[(o, d)]) for o, d in pairs
    ]
    summary = rt.summarize(records, evaluator.model)
    return detail, results, summary


# ==============================
# 单站换乘中断
# ==============================

def run_single_transfer_disruption(
    G_multi: nx.Graph,
    stations_transfer: Sequence[str],
    pairs: Sequence[Tuple[str, str]],
    baseline: Dict[Tuple[str, str], rt.PathResult],
    model: str = BASELINE_MODEL,
    G_phys: nx.Graph | None = None,
    keep_od_detail: Sequence[str] = (),
) -> Tuple[List[Dict[str, object]], Dict[str, "rt.EvaluationSummary"], Dict[str, List[Dict[str, object]]]]:
    """逐站关闭换乘连接，计算对全部 OD 的出行影响。

    返回 (逐站汇总行, 各站汇总对象, 代表站 OD 明细)。
    """
    network_distance = rt.compute_network_distance_matrix(G_phys) if G_phys is not None else {}

    # 基线网络效率（供对比）
    G_base_running = nx.Graph()
    G_base_running.add_nodes_from(G_multi.nodes())
    G_base_running.add_edges_from(
        (u, v) for u, v, d in G_multi.edges(data=True) if d["edge_type"] == "running"
    )

    rows: List[Dict[str, object]] = []
    summaries: Dict[str, rt.EvaluationSummary] = {}
    od_details: Dict[str, List[Dict[str, object]]] = {}
    station_index = rt.station_index(G_multi)
    stations_all = sorted(station_index)

    for station in stations_transfer:
        C, info = rt.build_cost_graph(
            G_multi,
            model=model,
            include_transfers=True,
            closed_transfer_stations=[station],
        )
        ev = rt.ODEvaluator(G_multi, model=model, network_distance=network_distance)
        ev.set_graph(C)

        records: List[rt.ODRecord] = []
        lost_pairs = []
        for origin, destination in pairs:
            base = baseline[(origin, destination)]
            after = ev.evaluate_pair(origin, destination)
            records.append(rt.ODRecord(origin, destination, base, after))
            if base.reachable and not after.reachable:
                lost_pairs.append((origin, destination))

        summary = rt.summarize(records, model)

        # 中断后物理站点口径的网络效率
        eff_after = rt.station_physical_efficiency(C, stations_all, station_index)

        # 该站承担的基线换乘次数（全部 OD 最短路上经由该站换乘的次数）
        base_transfer_through = sum(
            1 for r in baseline.values()
            if r.reachable and r.transfers and _path_uses_transfer_at(r.nodes, station, G_multi)
        )

        # 仍可达行程的额外换乘次数
        extra_tr = 0
        extra_st = 0
        for rec in records:
            if rec.baseline.reachable and rec.disrupted.reachable:
                if rec.disrupted.cost > rec.baseline.cost + 1e-9:
                    extra_tr += max(rec.disrupted.transfers - rec.baseline.transfers, 0)
                    if rec.baseline.physical_stations is not None and \
                       rec.disrupted.physical_stations is not None:
                        extra_st += rec.disrupted.physical_stations - rec.baseline.physical_stations

        lost_cost = 0.0
        for origin, destination in lost_pairs:
            r = baseline[(origin, destination)]
            if r.cost is not None:
                lost_cost += r.cost

        summaries[station] = summary
        rows.append(
            {
                "station": station,
                "lines": ";".join(sorted({G_multi.nodes[n]["line"] for n in _copies(G_multi, station)})),
                "od_pairs": summary.n_pairs,
                "reachable_before": summary.n_reachable_before,
                "reachable_after": summary.n_reachable_after,
                "lost_od": summary.n_lost,
                "lost_od_ratio": round(summary.unreachable_ratio, 8),
                "detour_od": summary.n_detour,
                "detour_od_ratio": round(summary.detour_ratio, 8),
                "unchanged_od": summary.n_same,
                "mean_cost_before": round(summary.mean_cost_before, 6),
                "mean_cost_after": round(summary.mean_cost_after, 6),
                "mean_detour_among_survivors": round(summary.mean_detour_among_survivors, 6),
                "mean_detour_all_od": round(summary.mean_detour_all, 6),
                "extra_physical_stations_total": int(round(extra_st)),
                "extra_transfers_total": int(round(extra_tr)),
                "lost_baseline_cost_total": round(lost_cost, 4),
                "baseline_transfer_usage": base_transfer_through,
                "global_efficiency_after": round(eff_after, 8),
                "loss_index": round(rt.transfer_loss_index(summary), 8),
                "cost_model": model,
            }
        )

        if station in keep_od_detail:
            od_rows = []
            for rec in records:
                b, a = rec.baseline, rec.disrupted
                if not b.reachable:
                    continue
                delta = (a.cost - b.cost) if a.reachable else None
                od_rows.append(
                    {
                        "origin": rec.origin,
                        "destination": rec.destination,
                        "cost_before": b.cost,
                        "cost_after": a.cost if a.reachable else "",
                        "delta_cost": "" if delta is None else round(delta, 6),
                        "transfers_before": b.transfers,
                        "transfers_after": a.transfers if a.reachable else "",
                        "lost": int(not a.reachable),
                        "path_before": "->".join(b.nodes),
                        "path_after": "->".join(a.nodes) if a.reachable else "",
                    }
                )
            od_rows.sort(key=lambda r: (-(r["delta_cost"] if r["delta_cost"] != "" else 10**6),
                                        r["lost"], r["origin"]))
            od_details[station] = od_rows

    # 每个站点关闭了多少条换乘边
    closed_counts = {}
    for station in stations_transfer:
        n = sum(
            1 for u, v, d in G_multi.edges(data=True)
            if d["edge_type"] != "running"
            and (d.get("station") or G_multi.nodes[u]["station"]) == station
        )
        closed_counts[station] = n
    for row in rows:
        row["transfer_edges_closed"] = closed_counts[row["station"]]

    return rows, summaries, od_details


def _copies(G_multi: nx.Graph, station: str) -> List[str]:
    return [n for n, d in G_multi.nodes(data=True) if d["station"] == station]


def _path_uses_transfer_at(nodes: Tuple[str, ...], station: str, G_multi: nx.Graph) -> bool:
    """判断该路径是否在 ``station`` 处发生跨线换乘。"""
    for a, b in zip(nodes, nodes[1:]):
        if not G_multi.has_edge(a, b):
            continue
        if G_multi[a][b]["edge_type"] == "running":
            continue
        if G_multi.nodes[a]["station"] == station:
            return True
    return False


# ==============================
# 结构排名 vs 出行损失
# ==============================

def compare_rankings(
    transfer_ranking: Sequence[Dict[str, object]],
    loss_rows: Sequence[Dict[str, object]],
) -> Tuple[List[Dict[str, object]], Dict[str, float]]:
    """把换乘站的结构排名与出行损失排名对照。"""
    loss_by_station = {r["station"]: r for r in loss_rows}

    loss_values = {s: r["loss_index"] for s, r in loss_by_station.items()}
    unreach_values = {s: r["lost_od_ratio"] for s, r in loss_by_station.items()}
    loss_rank = competition_rank(loss_values)
    unreach_rank = competition_rank(unreach_values)

    rows: List[Dict[str, object]] = []
    for t in transfer_ranking:
        station = t["station"]
        loss = loss_by_station.get(station)
        if loss is None:
            continue
        rows.append(
            {
                "station": station,
                "lines": t["lines"],
                "betweenness_centrality": t["betweenness_centrality"],
                "betweenness_rank_all": t["betweenness_rank"],
                "betweenness_rank_among_transfers": t["transfer_rank"],
                "loss_index": loss["loss_index"],
                "loss_rank": loss_rank[station],
                "lost_od": loss["lost_od"],
                "lost_od_ratio": loss["lost_od_ratio"],
                "lost_rank": unreach_rank[station],
                "detour_od": loss["detour_od"],
                "mean_detour_among_survivors": loss["mean_detour_among_survivors"],
                "extra_transfers_total": loss["extra_transfers_total"],
                "baseline_transfer_usage": loss["baseline_transfer_usage"],
                "loss_minus_centrality_rank": loss_rank[station] - t["transfer_rank"],
            }
        )

    rows.sort(key=lambda r: r["loss_rank"])

    stats = {}
    bt = [r["betweenness_centrality"] for r in rows]
    li = [r["loss_index"] for r in rows]
    ur = [r["lost_od_ratio"] for r in rows]
    stats["spearman_centrality_vs_loss"] = round(spearman(bt, li), 6)

    # 不可达比例在各站之间无差异（全部为 0）时 Spearman 无定义，
    # 明确标注而不是输出 nan，避免被误读成“不相关”。
    if len(set(ur)) <= 1:
        stats["spearman_centrality_vs_unreachable"] = "undefined"
        stats["spearman_loss_vs_unreachable"] = "undefined"
        stats["unreachable_note"] = (
            "全部换乘站的不可达比例相同（均为0）：8条线路由19座换乘站相互连通，"
            "单站关闭不会切断线网，故不可达比例不构成区分指标"
        )
    else:
        stats["spearman_centrality_vs_unreachable"] = round(spearman(bt, ur), 6)
        stats["spearman_loss_vs_unreachable"] = round(spearman(li, ur), 6)
    top_k = min(5, len(rows))
    cen_top = {r["station"] for r in sorted(rows, key=lambda x: x["betweenness_rank_among_transfers"])[:top_k]}
    loss_top = {r["station"] for r in sorted(rows, key=lambda x: x["loss_rank"])[:top_k]}
    stats["top5_overlap_count"] = len(cen_top & loss_top)
    stats["top5_overlap_stations"] = ";".join(sorted(cen_top & loss_top))
    stats["centrality_top5"] = ";".join(sorted(cen_top, key=lambda s: [
        r["betweenness_rank_among_transfers"] for r in rows if r["station"] == s][0]))
    stats["loss_top5"] = ";".join(r["station"] for r in sorted(rows, key=lambda x: x["loss_rank"])[:top_k])
    return rows, stats


# ==============================
# 参数敏感性
# ==============================

def run_cost_model_sensitivity(
    G_multi: nx.Graph,
    stations_transfer: Sequence[str],
    pairs: Sequence[Tuple[str, str]],
    G_phys: nx.Graph,
) -> List[Dict[str, object]]:
    """改变换乘惩罚，检查逐站损失排名是否稳定（B 项先做基础版，C 项再扩展）。"""
    network_distance = rt.compute_network_distance_matrix(G_phys)
    out: List[Dict[str, object]] = []

    for model in SENSITIVITY_MODELS:
        ev = rt.ODEvaluator(G_multi, model=model, network_distance=network_distance)
        baseline = {p: ev.evaluate_pair(*p) for p in pairs}

        loss_values: Dict[str, float] = {}
        unreach_values: Dict[str, float] = {}
        for station in stations_transfer:
            C, _ = rt.build_cost_graph(
                G_multi, model=model, closed_transfer_stations=[station]
            )
            ev.set_graph(C)
            records = [
                rt.ODRecord(o, d, baseline[(o, d)], ev.evaluate_pair(o, d))
                for o, d in pairs
            ]
            s = rt.summarize(records, model)
            loss_values[station] = rt.transfer_loss_index(s)
            unreach_values[station] = s.unreachable_ratio

        loss_rank = competition_rank(loss_values)
        unreach_rank = competition_rank(unreach_values)
        for station in stations_transfer:
            out.append(
                {
                    "cost_model": model,
                    "transfer_penalty": rt.transfer_penalty(model),
                    "station": station,
                    "loss_index": round(loss_values[station], 8),
                    "loss_rank": loss_rank[station],
                    "lost_od_ratio": round(unreach_values[station], 8),
                    "lost_rank": unreach_rank[station],
                }
            )
    return out


def ranking_stability(
    station_order: Sequence[str],
    sensitivity_rows: Sequence[Dict[str, object]],
) -> Dict[str, float]:
    """不同口径下损失排名的相关性。"""
    by_model: Dict[str, Dict[str, float]] = {}
    for r in sensitivity_rows:
        by_model.setdefault(r["cost_model"], {})[r["station"]] = r["loss_index"]

    stats: Dict[str, float] = {}
    models = list(by_model)
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            a, b = models[i], models[j]
            xs = [by_model[a][s] for s in station_order]
            ys = [by_model[b][s] for s in station_order]
            stats[f"spearman_{a}_vs_{b}"] = round(spearman(xs, ys), 6)
    return stats


# ==============================
# 主流程
# ==============================

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 72)
    print("B 项｜中心性、路径评价与单站换乘中断实验")
    print("=" * 72)

    # ---------- 网络 ----------
    G_phys = build_physical_network()
    G_multi = build_multilayer_network()

    consistency = compare_with_saved_graphml()
    summary_net = network_summary(G_multi)

    print(f"物理车站网络：{G_phys.number_of_nodes()} 节点 / {G_phys.number_of_edges()} 边")
    print(f"站点—线路网络：{summary_net['nodes']} 节点 / "
          f"{summary_net['running_edges']} 运行边 / "
          f"{summary_net['candidate_transfer_edges']} 候选换乘边")
    print(f"与 A 项 GraphML 一致：{consistency.get('consistent')}")

    # ---------- 结构排名 ----------
    metrics = compute_centralities(G_phys)
    ranking_rows = build_ranking_table(G_phys, metrics)
    transfer_ranking = build_transfer_ranking_table(G_phys, ranking_rows)

    # ---------- OD 集合 ----------
    stations = sorted(G_phys.nodes())
    pairs = rt.all_od_pairs(stations)
    print(f"OD 对（物理站点无序组合，等权）：{len(pairs)}")

    # ---------- 基线 ----------
    network_distance = rt.compute_network_distance_matrix(G_phys)
    evaluator = rt.ODEvaluator(
        G_multi, model=BASELINE_MODEL, network_distance=network_distance
    )
    detail, baseline, base_summary = baseline_od_statistics(evaluator, pairs)

    station_index = rt.station_index(G_multi)
    eff_before = rt.station_physical_efficiency(
        evaluator._baseline_graph, stations, station_index
    )

    print(f"基准口径 {BASELINE_MODEL}（换乘惩罚 {rt.transfer_penalty(BASELINE_MODEL)} 站）：")
    print(f"  可达 OD：{base_summary.n_reachable_before}/{base_summary.n_pairs}")
    print(f"  平均代价：{base_summary.mean_cost_before:.3f} 等效站")
    print(f"  物理站点网络效率：{eff_before:.6f}")

    # ---------- 单站换乘中断 ----------
    transfer_stations = transfer_station_names(G_multi)
    print(f"\n换乘站：{len(transfer_stations)} 座，逐一关闭其换乘连接……")

    loss_rows, loss_summaries, od_details = run_single_transfer_disruption(
        G_multi, transfer_stations, pairs, baseline,
        model=BASELINE_MODEL, G_phys=G_phys,
        keep_od_detail=(),
    )

    loss_rows.sort(key=lambda r: (-r["loss_index"], -r["lost_od"], r["station"]))

    print(f"\n{'站点':<12}{'线路':<8}{'不可达OD':<10}{'不可达比例':<12}"
          f"{'绕行OD':<8}{'平均绕行':<10}{'损失指数':<12}")
    for r in loss_rows:
        print(f"{r['station']:<12}{r['lines']:<8}{r['lost_od']:<10}"
              f"{r['lost_od_ratio']:<12.5f}{r['detour_od']:<8}"
              f"{r['mean_detour_among_survivors']:<10.4f}{r['loss_index']:<12.6f}")

    # ---------- 排名对照 ----------
    rank_rows, rank_stats = compare_rankings(transfer_ranking, loss_rows)
    print("\n结构排名 vs 出行损失：")
    for k, v in rank_stats.items():
        print(f"  {k}: {v}")

    # ---------- 参数敏感性 ----------
    print("\n换乘惩罚参数敏感性……")
    sens_rows = run_cost_model_sensitivity(G_multi, transfer_stations, pairs, G_phys)
    stability = ranking_stability([r["station"] for r in loss_rows], sens_rows)
    for k, v in stability.items():
        print(f"  {k}: {v}")

    # ---------- 保存 ----------
    write_csv(
        TABLES_DIR / "B04_single_transfer_disruption.csv",
        loss_rows,
        [
            "station", "lines", "transfer_edges_closed", "od_pairs",
            "reachable_before", "reachable_after", "lost_od", "lost_od_ratio",
            "detour_od", "detour_od_ratio", "unchanged_od",
            "mean_cost_before", "mean_cost_after",
            "mean_detour_among_survivors", "mean_detour_all_od",
            "extra_physical_stations_total", "extra_transfers_total",
            "lost_baseline_cost_total", "baseline_transfer_usage",
            "global_efficiency_after", "loss_index", "cost_model",
        ],
    )
    write_csv(
        TABLES_DIR / "B06_baseline_od_stats.csv",
        detail,
        ["origin", "destination", "reachable", "cost", "rides", "transfers", "physical_stations"],
    )
    write_csv(
        TABLES_DIR / "B07_cost_model_sensitivity.csv",
        sens_rows,
        ["cost_model", "transfer_penalty", "station", "loss_index", "loss_rank",
         "lost_od_ratio", "lost_rank"],
    )
    write_csv(
        TABLES_DIR / "B08_centrality_vs_loss.csv",
        rank_rows,
        [
            "station", "lines", "betweenness_centrality", "betweenness_rank_all",
            "betweenness_rank_among_transfers", "loss_index", "loss_rank",
            "lost_od", "lost_od_ratio", "lost_rank", "detour_od",
            "mean_detour_among_survivors", "extra_transfers_total",
            "baseline_transfer_usage", "loss_minus_centrality_rank",
        ],
    )

    # 参数与元数据
    meta = {
        "data_version": {
            "multilayer_graphml": "results/networks/multilayer_network_main.graphml",
            "consistent_with_saved": consistency.get("consistent"),
        },
        "network": summary_net,
        "baseline_cost_model": BASELINE_MODEL,
        "baseline_transfer_penalty_stations": rt.transfer_penalty(BASELINE_MODEL),
        "cost_models": rt.COST_MODELS,
        "random_seed": RANDOM_SEED,
        "od_pairs": len(pairs),
        "od_weighting": "unique unordered physical-station pairs, equal weight",
        "transfer_station_count": len(transfer_stations),
        "baseline_summary": {
            "reachable_od": base_summary.n_reachable_before,
            "mean_cost": round(base_summary.mean_cost_before, 6),
            "mean_transfers": round(
                sum(r.transfers for r in baseline.values() if r.reachable)
                / max(sum(1 for r in baseline.values() if r.reachable), 1), 6
            ),
        },
        "ranking_comparison": rank_stats,
        "sensitivity_stability": stability,
        "baseline_efficiency": round(eff_before, 8),
        "notes": [
            "代价单位=等效站数：乘车区间=1，换乘次数×惩罚（基准2）。不是真实分钟数。",
            "换乘中断只删除目标站的换乘边，保留运行边、线路副本节点与正常上下车。",
            "不可达比例与仍可达行程绕行代价分开报告。",
            "候选换乘边均为待核验证状态，基准情景把其视为可通行属明确假设。",
        ],
    }
    meta_path = TABLES_DIR / "B09_run_parameters.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("\n已保存：")
    for p in (
        "B04_single_transfer_disruption.csv",
        "B06_baseline_od_stats.csv",
        "B07_cost_model_sensitivity.csv",
        "B08_centrality_vs_loss.csv",
        "B09_run_parameters.json",
    ):
        print("  ", TABLES_DIR / p)


if __name__ == "__main__":
    main()
