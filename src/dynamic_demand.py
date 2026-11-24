"""九线日客流预测、204 站分时 OD 分配与熵权 TOPSIS 关键站排名。"""
import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.optimize import root
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.stats import rankdata

from .build_network import ROOT, build_directed_network
from .prepare_dynamic_inputs import EARTH_M, OUT as INPUT, on_sphere, save_rows

OUT = ROOT / "results/dynamic_demand"
TARGET = date(2026, 11, 25)
ANCHOR = date(2026, 11, 23)   # 公告在 11-24 08:43 发布，早于预测日所有时段
HOLDOUT_ANCHOR = date(2026, 11, 20)
LINES = (*map(str, range(1, 9)), "S1")
REPORT_HOURS = ("08:00", "12:00", "18:00")
CRITERIA = ("degree", "betweenness", "closeness", "ppi")
EPS = 1e-10


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_history(path, lines):
    table = {}
    for r in read_rows(path):
        d = date.fromisoformat(r["service_date"])
        if not all(r.get(line) for line in lines):
            continue
        q = np.array([float(r[line]) for line in lines]) * 10000
        if np.all(q > 0) and abs(q.sum() - float(r["network_10k"]) * 10000) <= 500:
            table[d] = q
    return table


def seasonal_forecast(history, anchor, target, volumes):
    """用相同星期组合的历史比例中位数，转换最近可用工作日实报。S1 沿用实报。"""
    lag = target - anchor
    if lag <= timedelta(0) or target.weekday() > 4 or anchor.weekday() > 4:
        raise ValueError("预测须从较早工作日到较晚工作日")

    def eligible(d):
        # 9 月下旬至国庆调休不参与普通工作日校准。
        return d.weekday() < 5 and not date(2026, 9, 23) <= d <= date(2026, 10, 11)

    pairs = [(d, d + lag) for d in sorted(history)
             if d.weekday() == anchor.weekday() and eligible(d) and eligible(d + lag)
             and d + lag < anchor and d + lag in history]
    if len(pairs) < 4:
        raise ValueError("同星期历史样本不足")
    ratios = np.r_[np.median([history[b] / history[a] for a, b in pairs], axis=0), 1.]
    return volumes * ratios, pairs, ratios


@dataclass
class Routes:
    cost: np.ndarray
    od: tuple
    boardings: np.ndarray
    rides: csr_matrix
    changes: csr_matrix
    edges: list
    structural: np.ndarray


def compile_routes(graph, features):
    """求有向最短路，首末站任选线路；按物理站聚合区间、换乘事件和结构指标。"""
    names = [r["station"] for r in features]
    index = {s: i for i, s in enumerate(names)}
    nodes = sorted(graph, key=lambda u: (graph.nodes[u]["station"], graph.nodes[u]["line"]))
    members = defaultdict(list)
    platforms = {}
    tracks = defaultdict(set)
    for i, u in enumerate(nodes):
        s, line = graph.nodes[u]["station"], graph.nodes[u]["line"]
        members[index[s]].append(i)
        tracks[s].add(line)
        platforms[u] = i
    if len(names) != len(index) or any(tracks[r["station"]] != set(r["lines"].split(";")) for r in features):
        raise ValueError("地理站点与线网的站名/线路不一致")
    line_id = {line: i for i, line in enumerate(LINES)}
    n = len(names)
    station_of = {u: index[graph.nodes[u]["station"]] for u in nodes}
    xyz = on_sphere(np.array([float(r["wgs84_lon"]) for r in features]),
                    np.array([float(r["wgs84_lat"]) for r in features]))
    physical_edges = []
    edges = []
    edge_lookup = {}
    geom = nx.Graph()
    geom.add_nodes_from(range(n))
    arcs = np.zeros((len(nodes), len(nodes)))
    for u, v, attrs in sorted(graph.edges(data=True)):
        i, j = platforms[u], platforms[v]
        minutes = int(attrs["weight"])
        if minutes <= 0 or minutes != attrs["weight"]:
            raise ValueError("区间和换乘分钟须为正整数")
        if attrs["edge_type"] == "transfer":
            arcs[i, j] = 1000*minutes + 1
            continue
        a, b = station_of[u], station_of[v]
        la = attrs["line"]
        arcs[i, j] = 1000*minutes  # 同分钟优先少换乘，次级编码不进入时间矩阵
        d = 2 * EARTH_M * np.arcsin(np.linalg.norm(xyz[a]-xyz[b])/(2*EARTH_M)) / 1000
        edge_lookup[(i, j)] = (len(edges), line_id[la])
        edges.append(dict(edge_id=f"E{len(edges)+1:03d}", line=la,
                          from_id=features[a]["station_id"], to_id=features[b]["station_id"],
                          from_station=names[a], to_station=names[b], minutes=minutes,
                          straight_km=round(d, 4)))
        physical_edges.append((a, b))
    geom.add_edges_from(physical_edges)
    distances, previous = dijkstra(csr_matrix(arcs), directed=True, return_predecessors=True)
    if not np.isfinite(distances).all():
        raise ValueError("正常分钟线网不应失联")
    cost = np.zeros((n, n), dtype=int)
    od = np.nonzero(~np.eye(n, dtype=bool))
    m = len(od[0])
    boardings = np.zeros((m, len(LINES)), dtype=np.int8)
    route_edge, route_trip, transfer_at, transfer_trip = [], [], [], []
    for k, (a, b) in enumerate(zip(*od)):
        aa, bb = members[a], members[b]
        local = distances[np.ix_(aa, bb)]
        x, y = np.unravel_index(local.argmin(), local.shape)
        origin, curr = aa[x], bb[y]
        cost[a, b] = int(local[x, y]) // 1000
        last_line, n_transfers = None, 0
        while curr != origin:
            prev = int(previous[origin, curr])
            if (prev, curr) in edge_lookup:
                e, line = edge_lookup[prev, curr]
                route_trip.append(k)
                route_edge.append(e)
                if line != last_line:
                    boardings[k, line] += 1
                last_line = line
            else:
                transfer_trip.append(k)
                transfer_at.append(station_of[nodes[curr]])
                n_transfers += 1
            curr = prev
        if boardings[k].sum() != 1 + n_transfers:
            raise ValueError(f"异常路径：{names[a]} → {names[b]}")
    degree = nx.degree_centrality(geom)
    betweenness = nx.betweenness_centrality(geom)
    # Directed outward closeness, not the distance-to reduction used by some DiGraph libraries.
    structural = np.column_stack(([degree[i] for i in range(n)],
                                  [betweenness[i] for i in range(n)], (n-1)/cost.sum(axis=1)))

    def incidence(trips, items, cols):
        return csr_matrix((np.ones(len(trips)), (trips, items)), shape=(m, cols))

    return Routes(cost, od, boardings, incidence(route_trip, route_edge, len(edges)),
                  incidence(transfer_trip, transfer_at, n), edges, structural)


def ipf(kernel, origin, destination):
    """固定起终点份额的熵最大化重力分配。kernel 对角线为零。"""
    v = np.ones(len(destination))
    for _ in range(600):
        u = origin / (kernel @ v)
        v = destination / (kernel.T @ u)
        if np.max(np.abs(u * (kernel @ v) - origin)) < EPS:
            return u[:, None] * kernel * v[None, :]
    raise ValueError("起终点份额迭代未收敛")


def normalized(x):
    return x / x.sum(axis=-1, keepdims=True)


def seed_od(cost, features, profile, decay=30., tide_scale=1., poi_share=.70):
    residents = normalized(np.sqrt(np.array([float(r["population_worldpop"]) for r in features]) + 500))
    # OSM 计数是活动机会代理，不是就业或进站人数。底数防止漏标导致站点被删掉。
    categories = {key: np.array([int(r[f"poi_{key}"]) for r in features])
                  for key in ("office", "education", "hospital", "retail", "hub")}
    visits = normalized(np.sqrt(1 + categories["office"] + 2*categories["education"] +
                                2*categories["hospital"] + 2*categories["retail"] + 5*categories["hub"]))
    activity = poi_share*visits + (1-poi_share)*residents
    kernel = np.exp(-cost / decay)
    np.fill_diagonal(kernel, 0)
    volume = normalized(np.array([float(r["volume_weight"]) for r in profile]))
    prior = []
    for q, r in zip(volume, profile):
        a = (1 + tide_scale * float(r["commute_tilt"])) / 2
        origin = a*residents + (1-a)*activity
        dest = (1-a)*residents + a*activity
        prior.append(q*ipf(kernel, origin, dest))
    return np.stack(prior)


def fit_boardings(od_prior, route_boardings, observed):
    """对初始 OD 最小化相对熵改动，同时匹配九条线的日上车量。

    每个 OD 的倍率对全天恒定；无实测站点边际，二次校准后不声称保留这些边际。
    """
    patterns, groups = np.unique(route_boardings, axis=0, return_inverse=True)
    masses = np.bincount(groups, weights=od_prior.sum(axis=0))
    total = observed.sum()
    target = observed / total

    def rate(x):
        return masses*np.exp(np.clip(patterns @ x, -60, 60))

    def fn(x):
        return rate(x) @ patterns - target

    def jac(x):
        return patterns.T @ (rate(x)[:, None] * patterns)

    fitted = root(fn, np.zeros(len(target)), jac=jac, tol=1e-10)
    if np.max(np.abs(fn(fitted.x))) > 1e-8:
        raise ValueError("线路上车量校准未收敛")
    trips = od_prior * (total*np.exp(patterns[groups] @ fitted.x))
    if not np.allclose(trips.sum(axis=0) @ route_boardings, observed, atol=.05, rtol=0):
        raise ValueError("线路上车量校准未达到数值精度")
    return trips


def normalize_metrics(values):
    cloud = values.reshape(-1, values.shape[-1])
    low = cloud.min(axis=0)
    width = cloud.max(axis=0) - low
    return low, np.where(width > 0, width, 1)


def entropy_weights(scaled):
    cloud = scaled.reshape(-1, scaled.shape[-1])
    prob = cloud / np.maximum(cloud.sum(axis=0), EPS)
    spread = 1 + (prob*np.log(np.maximum(prob, EPS))).sum(axis=0) / np.log(len(cloud))
    return normalized(np.where(cloud.sum(axis=0) > EPS, np.maximum(spread, 0), 0))


def topsis(values, low, width, weights):
    scaled = np.clip((values - low) / width, 0, 1)
    x = scaled * weights
    worst = np.linalg.norm(x, axis=-1)
    best = np.linalg.norm(weights - x, axis=-1)
    return worst / (worst + best)


def predict_activity(routes, features, profile, volumes, **options):
    prior = seed_od(routes.cost, features, profile, **options)
    flat = fit_boardings(prior[:, routes.od[0], routes.od[1]], routes.boardings, volumes)
    trip = np.zeros_like(prior)
    trip[:, routes.od[0], routes.od[1]] = flat
    origins, exits = trip.sum(axis=2), trip.sum(axis=1)
    transfers = (routes.changes.T @ flat.T).T
    loads = (routes.rides.T @ flat.T).T
    metrics = np.concatenate((np.broadcast_to(routes.structural, (len(profile), *routes.structural.shape)),
                              normalized(origins + exits + transfers)[:, :, None]), axis=2)
    return trip, origins, exits, transfers, loads, metrics


def summarize_forecast(base, history):
    q, pairs, ratio = seasonal_forecast(history, ANCHOR, TARGET, base[ANCHOR])
    pred, held_pairs, _ = seasonal_forecast(history, HOLDOUT_ANCHOR, ANCHOR, base[HOLDOUT_ANCHOR])
    actual = base[ANCHOR]
    holdout = dict(anchor=str(HOLDOUT_ANCHOR), target=str(ANCHOR),
                   actual_boardings=float(actual.sum()), predicted_boardings=float(pred.sum()),
                   carry_boardings=float(base[HOLDOUT_ANCHOR].sum()),
                   error_total_pct=float(100 * (pred.sum() - actual.sum()) / actual.sum()),
                   carry_error_total_pct=float(100 * (base[HOLDOUT_ANCHOR].sum() - actual.sum()) / actual.sum()),
                   mae_pct_8_lines=float(100*np.mean(np.abs(pred[:-1] / actual[:-1] - 1))),
                   training_pairs=[[str(a), str(b)] for a, b in held_pairs])
    forecast = [dict(line=line, anchor=str(ANCHOR), anchor_boardings=base[ANCHOR][i],
                     target=str(TARGET), weekday_ratio=ratio[i], forecast_boardings=q[i],
                     holdout_predicted=pred[i], holdout_observed=actual[i]) for i, line in enumerate(LINES)]
    return q, forecast, holdout, pairs


def save_network(output, features, hours, routes, trips, loads):
    save_rows(output / "nodes.csv", features)
    save_rows(output / "edges.csv", routes.edges)
    ids = [r["station_id"] for r in features]
    with (output / "cost_matrix.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["origin_id", *ids])
        writer.writerows([o, *r] for o, r in zip(ids, routes.cost))
    np.savez_compressed(output / "time_network.npz", stations=[r["station"] for r in features], station_ids=ids,
                        forecast_date=str(TARGET), departure_hours=hours, cost_minutes=routes.cost,
                        od_trips=trips.astype(np.float32), edge_ids=[r["edge_id"] for r in routes.edges],
                        edge_load=loads.astype(np.float32))
    edge_rows = [dict(date=str(TARGET), start_hour=h, **e, estimated_load=round(float(loads[t, k]), 3))
                 for t, h in enumerate(hours) for k, e in enumerate(routes.edges)]
    save_rows(output / "edge_load.csv", edge_rows)
    top_od = []
    for label, matrix in [("day", trips.sum(axis=0)), *zip(hours, trips)]:
        indices = np.argsort(-matrix.ravel(), kind="stable")[:10]
        for rank, (o, d) in enumerate(zip(*np.unravel_index(indices, matrix.shape)), 1):
            top_od.append(dict(date=str(TARGET), start_hour=label, rank=rank, origin_id=ids[o],
                               origin=features[o]["station"], destination_id=ids[d],
                               destination=features[d]["station"], estimated_trips=round(float(matrix[o, d]), 3),
                               minutes=routes.cost[o, d]))
    save_rows(output / "top_od.csv", top_od)


def run(inputs, output):
    features = read_rows(inputs / "station_features.csv")
    profile = read_rows(inputs / "hour_profile.csv")
    hours = [r["hour"] for r in profile]
    if any(float(r["volume_weight"]) <= 0 or abs(float(r["commute_tilt"])) > 1 for r in profile):
        raise ValueError("时间剖面范围错误")
    history = read_history(inputs / "ridership_history.csv", LINES[:-1])
    base = read_history(ROOT / "data/line_ridership.csv", LINES)
    q, forecast, holdout, pairs = summarize_forecast(base, history)
    routes = compile_routes(build_directed_network(), features)
    trip, origins, exits, transfers, loads, metrics = predict_activity(routes, features, profile, q)
    low, width = normalize_metrics(metrics)
    weights = entropy_weights((metrics - low) / width)
    scores = topsis(metrics, low, width, weights)
    ranks = rankdata(-scores, method="min", axis=1)
    static = topsis(routes.structural, low[:-1], width[:-1], normalized(weights[:-1]))
    static_ranks = rankdata(-static, method="min")
    day_entries = origins.sum(axis=0)
    day_events = (origins + exits + transfers).sum(axis=0)
    day_share = np.column_stack((routes.structural, normalized(day_events)))
    day_ranks = rankdata(-topsis(day_share, low, width, weights), method="min")
    output.mkdir(parents=True, exist_ok=True)
    full = []
    for t, hour in enumerate(hours):
        for i in np.argsort(ranks[t], kind="stable"):
            f = features[i]
            full.append(dict(date=str(TARGET), hour=hour, rank=int(ranks[t, i]), station_id=f["station_id"],
                             station=f["station"], lines=f["lines"], topology_rank=int(static_ranks[i]),
                             daily_flow_rank=int(day_ranks[i]), arrivals=round(float(exits[t, i]), 4),
                             departures=round(float(origins[t, i]), 4), transfers=round(float(transfers[t, i]), 4),
                             score=round(float(scores[t, i]), 7),
                             **{k: round(float(metrics[t, i, j]), 8) for j, k in enumerate(CRITERIA)}))
    save_rows(output / "line_forecast.csv", forecast)
    save_rows(output / "station_ranks.csv", full)
    save_network(output, features, hours, routes, trip, loads)

    sensitivity = []
    focus = [hours.index(h) for h in REPORT_HOURS]
    for label, settings in [("base", {}), ("shorter_trips", {"decay": 20}), ("longer_trips", {"decay": 40}),
                            ("half_commute_tilt", {"tide_scale": .50}), ("weaker_poi", {"poi_share": .35})]:
        new_metrics = metrics if not settings else predict_activity(routes, features, profile, q, **settings)[-1]
        score = topsis(new_metrics, low, width, weights)
        alt = rankdata(-score, method="min", axis=1)
        for t in focus:
            ref_top = set(np.flatnonzero(ranks[t] <= 5))
            top = np.argsort(alt[t], kind="stable")[:5]
            for i in range(len(features)):
                sensitivity.append(dict(scenario=label, hour=hours[t], station=features[i]["station"],
                                        rank=int(alt[t, i]), top5_overlap=len(ref_top.intersection(top))))
    save_rows(output / "sensitivity.csv", sensitivity)
    booking_station = {r["station"]: i for i, r in enumerate(features)}
    ext = read_rows(inputs / "association_2025.csv")[0]
    entry_rank = rankdata(-day_entries, method="min")
    comparison = [dict(station=r["station"], holiday_entries=int(r["mean_daily_entries"]),
                       forecast_workday_entry_rank=int(entry_rank[booking_station[r["station"]]]))
                  for r in read_rows(inputs / "holiday_station_sample.csv")]
    by_hour = {}
    for t in focus:
        e = int(loads[t].argmax())
        by_hour[hours[t]] = dict(top5=[r["station"] for r in full if r["hour"] == hours[t] and r["rank"] <= 5],
                                 strongest_edge={**routes.edges[e], "estimated_load": float(loads[t, e])},
                                 trip_count=float(trip[t].sum()))
    report = dict(forecast_date=str(TARGET), last_observed_service_date=str(ANCHOR),
                  hours=hours, physical_stations=len(features), directed_running_edges=len(routes.edges),
                  ordered_od_per_hour=len(routes.od[0]), forecast_line_boardings=float(q.sum()),
                  estimated_unique_trips=float(trip.sum()),
                  estimated_entries_to_boardings=float(trip.sum()/q.sum()),
                  year_2025_entries_to_boardings=float(ext["entries_10k"])/float(ext["network_boardings_10k"]),
                  forecast_training_pairs=[[str(a), str(b)] for a, b in pairs], holdout=holdout,
                  criterion_weights=dict(zip(CRITERIA, map(float, weights))),
                  reference_holiday=comparison, report_hours=by_hour)
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"{TARGET}: {len(features)} stations × {len(hours)} hours; {trip.sum():,.0f} estimated trips; {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    run(args.input, args.output)


if __name__ == "__main__":
    main()
