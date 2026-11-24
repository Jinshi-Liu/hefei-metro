"""按夜间班次反推各 OD 的最晚上车时间，并比较逐线加开晚班。"""

import argparse
import csv
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import numpy as np

from .build_network import GRAPH_FILE, ROOT, TRANSFER_MINUTES

TRIPS_FILE = ROOT / "data/night_trips.csv"
LAST_DEPARTURES_FILE = ROOT / "data/night_last_departures.csv"
OUTPUT = ROOT / "results/night_ablation"
EXTENSION = 15
SAME_LINE_CHANGE = 1  # 换一趟同线列车；留在同一趟车上无需等待
SNAPSHOTS = (22 * 60 + 30, 23 * 60)
WEST = "合肥西站"
AIRPORT = "新桥2号航站楼"
SOUTH_TERMINAL = "省儿童医院新区"
EXAMPLE_DESTINATION = "繁华大道"


@dataclass(frozen=True)
class Trip:
    line: str
    stops: tuple[str, ...]
    times: tuple[int, ...]  # 到站；无单独发车记录时也用作计划发车
    departures: tuple[int, ...] | None = None

    def depart_at(self, position: int) -> int:
        return (self.times if self.departures is None else self.departures)[position]


def minutes(clock: str) -> int:
    h, m = map(int, clock.split(":"))
    if not (0 <= h < 28 and 0 <= m < 60):
        raise ValueError(f"无效运营日时刻：{clock}")
    return 60 * h + m


def clock(minute: int) -> str:
    """次日凌晨沿用同一运营日，例如 24:06。"""
    return f"{minute // 60:02d}:{minute % 60:02d}" if minute >= 0 else ""


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_timetable(graph, trips_path=TRIPS_FILE, last_path=LAST_DEPARTURES_FILE):
    by_line = defaultdict(list)
    for _, attrs in graph.nodes(data=True):
        by_line[attrs["line"]].append((attrs["sequence"], attrs["station"]))
    orders = {line: tuple(station for _, station in sorted(stations)) for line, stations in by_line.items()}
    trips, dates, observed = [], set(), {}
    for row in read_rows(trips_path):
        line, origin, terminus = row["line"], row["origin"], row["terminus"]
        order = orders[line]
        if terminus == order[0]:
            order = order[::-1]
        if terminus != order[-1] or not row["source_url"]:
            raise ValueError(f"未知运行方向或缺少来源：{row}")
        stops = order[order.index(origin):]
        times = tuple(map(minutes, row["stop_times"].split(";")))
        if len(times) < 2 or len(times) != len(stops) or any(x >= y for x, y in zip(times, times[1:])):
            raise ValueError(f"逐站时刻不完整或未严格递增：{row}")
        dates.add(row["service_date"])
        trips.append(Trip(line, stops, times))
        for s, t in zip(stops[:-1], times[:-1]):
            key = (line, terminus, s)
            observed[key] = max(observed.get(key, -1), t)
    if len(dates) != 1 or len(trips) != len(set(trips)):
        raise ValueError("时刻表须为同一个运营日，且不含重复班次")
    service_date = dates.pop()
    reference = {}
    for row in read_rows(last_path):
        key = (row["line"], row["direction_terminal"], row["station"])
        if row["service_date"] != service_date or key in reference or not row["source_url"]:
            raise ValueError(f"末班发车表日期、行或来源无效：{row}")
        reference[key] = minutes(row["last_departure"])
    expected_keys = {(line, terminal, s) for line, stops in orders.items()
                     for terminal in (stops[0], stops[-1]) for s in stops if s != terminal}
    if reference.keys() != expected_keys or observed != reference:
        raise ValueError("班次重建未覆盖全线网或与逐站末班发车表不一致")
    return service_date, trips


def network_stations(graph):
    stations = sorted({d["station"] for _, d in graph.nodes(data=True)})
    changes = defaultdict(set)
    for u, v, e in graph.edges(data=True):
        if e["edge_type"] != "transfer":
            continue
        a, b = graph.nodes[u], graph.nodes[v]
        s = a["station"]
        if s != b["station"] or a["line"] == b["line"]:
            raise ValueError("换乘边须连接同一物理站的不同线路")
        changes[s, a["line"]].add(b["line"])
        changes[s, b["line"]].add(a["line"])
    return stations, changes


def latest_boarding(trips, stations, changes, transfer_minutes=TRANSFER_MINUTES, transfer_overrides=None):
    """反向扫描有时刻的乘车事件；结果为各有向 OD 的最晚首程发车。"""
    transfer_overrides = transfer_overrides or {}
    if any(t <= 0 or int(t) != t for t in (transfer_minutes, *transfer_overrides.values())):
        raise ValueError("换乘缓冲须为正整数分钟")
    index = {station: i for i, station in enumerate(stations)}
    events, platforms = [], defaultdict(list)
    for trip in trips:
        for k, (a, b) in enumerate(zip(trip.stops, trip.stops[1:])):
            depart, arrival = trip.depart_at(k), trip.times[k + 1]
            event = len(events)
            continuation = event + 1 if k + 2 < len(trip.stops) else -1
            events.append((trip.line, a, b, depart, arrival, continuation))
            platforms[a, trip.line].append((depart, event))

    suffix = [0] * len(events)
    destinations = [0] * len(events)
    next_departure = [-1] * len(events)
    for queue in platforms.values():
        queue.sort()
        for (_, event), (_, next_event) in zip(queue, queue[1:]):
            next_departure[event] = next_event

    latest = np.full((len(stations), len(stations)), -1, dtype=int)
    seen = [1 << i for i in range(len(stations))]  # 不把回到本站算成 OD
    # 每个事件的位集合表示「上这班车能到哪些目的站」，suffix 并入同站同线更晚的班次。
    for e in sorted(range(len(events)), key=lambda i: (events[i][3], i), reverse=True):
        line, a, b, depart, arrival, continuation = events[e]
        reached = 1 << index[b]
        if continuation != -1:
            reached |= destinations[continuation]  # 原车继续，不收换乘时间
        targets = [(line, SAME_LINE_CHANGE)]
        targets.extend((other, transfer_overrides.get((b, line, other), transfer_minutes))
                       for other in changes.get((b, line), ()))
        for other, buffer in targets:
            queue = platforms.get((b, other), ())
            i = bisect_left(queue, (arrival + buffer, -1))
            if i < len(queue):
                reached |= suffix[queue[i][1]]
        destinations[e] = reached
        next_e = next_departure[e]
        suffix[e] = reached | (suffix[next_e] if next_e != -1 else 0)
        origin = index[a]
        new = reached & ~seen[origin]
        seen[origin] |= reached
        while new:
            bit = new & -new
            latest[origin, bit.bit_length() - 1] = depart
            new ^= bit
    return latest


def last_by_direction(trips, line):
    tails = {}
    for trip in trips:
        if trip.line == line:
            terminal = trip.stops[-1]
            if terminal not in tails or trip.depart_at(-2) > tails[terminal].depart_at(-2):
                tails[terminal] = trip
    if len(tails) != 2:
        raise ValueError(f"线路 {line} 未找到两个方向")
    return tails


def shift_trip(trip, delay):
    arrivals = tuple(t + delay for t in trip.times)
    departures = None if trip.departures is None else tuple(t + delay for t in trip.departures)
    return Trip(trip.line, trip.stops, arrivals, departures)


def extra_trips(trips, line, delay=EXTENSION):
    return [shift_trip(trip, delay) for trip in last_by_direction(trips, line).values()]


def hold_at(trip, station, hold):
    """本车原时刻到达等候站；仅发车及下游到发推迟。"""
    k = trip.stops.index(station)
    if not 0 < k < len(trip.stops) - 1 or hold <= 0:
        raise ValueError("须在中途站延长正分钟数")
    return Trip(trip.line, trip.stops,
                tuple(t + (hold if i > k else 0) for i, t in enumerate(trip.times)),
                tuple(trip.depart_at(i) + (hold if i >= k else 0) for i in range(len(trip.times))))


def analyze(graph, trips, transfer_minutes=TRANSFER_MINUTES):
    stations, changes = network_stations(graph)
    od_mask = ~np.eye(len(stations), dtype=bool)
    base = latest_boarding(trips, stations, changes, transfer_minutes)[od_mask]
    if (base < 0).any():
        raise ValueError(f"晚间样本不足，{int((base < 0).sum())} 对 OD 未找到路线；需补采更早班次后再排名")
    outcomes, ranking = {}, []
    for line in sorted({t.line for t in trips}):
        extra = extra_trips(trips, line)
        after = latest_boarding(trips + extra, stations, changes, transfer_minutes)[od_mask]
        gain = after - base
        if (gain < 0).any():
            raise ValueError("新增班次不应使可达窗口缩短")
        outcomes[line] = after
        ranking.append(dict(line=line, improved_od=int((gain > 0).sum()),
                            total_window_gain_od_min=int(gain.sum()), mean_gain_min_all_od=float(gain.mean()),
                            max_gain_min=int(gain.max()),
                            added_reachable_2230=int(((after >= SNAPSHOTS[0]) & (base < SNAPSHOTS[0])).sum()),
                            added_reachable_2300=int(((after >= SNAPSHOTS[1]) & (base < SNAPSHOTS[1])).sum()),
                            added_departures=";".join(f"{t.stops[0]}→{t.stops[-1]} {clock(t.times[0])}" for t in extra)))
    ranking.sort(key=lambda r: (-r["total_window_gain_od_min"], r["line"]))
    start = int(base.min()) // 30 * 30
    final = int(max(after.max() for after in outcomes.values())) + 1
    curve = [dict(time=clock(t), baseline=int((base >= t).sum()),
                  **{f"plus_{l}": int((m >= t).sum()) for l, m in outcomes.items()})
             for t in range(start, final + 1)]
    i, j = np.nonzero(od_mask)
    rows = (dict(origin=stations[a], destination=stations[b], latest_boarding=clock(base[k]),
                 **{f"plus_{l}": clock(m[k]) for l, m in outcomes.items()})
            for k, (a, b) in enumerate(zip(i, j)))
    return rows, ranking, curve


def three_line_comparison(graph, trips, transfer_minutes=TRANSFER_MINUTES):
    """2/3/6 号线分别加开，以及同时加开；按 OD 集合计算互补，不加总柱高。"""
    stations, changes = network_stations(graph)
    mask = ~np.eye(len(stations), dtype=bool)
    base = latest_boarding(trips, stations, changes, transfer_minutes)[mask]
    additions = {line: extra_trips(trips, line) for line in ("2", "3", "6")}
    single = {line: latest_boarding(trips + extra, stations, changes, transfer_minutes)[mask]
              for line, extra in additions.items()}
    joint = latest_boarding(trips + sum(additions.values(), []), stations, changes, transfer_minutes)[mask]
    union = np.maximum.reduce(list(single.values()))
    if (union < base).any() or (joint < union).any():
        raise ValueError("加开更多车不应缩短可达窗口")
    for t in range(22 * 60, 24 * 60 + 1):
        yield dict(time=clock(t), baseline=int((base >= t).sum()),
                   **{f"plus_{line}": int((x >= t).sum()) for line, x in single.items()},
                   union_of_singles=int((union >= t).sum()), plus_2_3_6=int((joint >= t).sum()),
                   only_joint=int(((joint >= t) & (union < t)).sum()))


def missed_last_connections(trips, before, after, station, changes, transfer_minutes):
    """核对原来能从这趟车换上的下游跨线末班（按目标线路方向），不是 OD 数。"""
    cutoffs = {}
    for trip in trips:
        if trip.line == before.line:
            continue
        for i, stop in enumerate(trip.stops[:-1]):
            key = (stop, trip.line, trip.stops[-1])
            cutoffs[key] = max(cutoffs.get(key, -1), trip.depart_at(i))
    missed = []
    for i in range(before.stops.index(station) + 1, len(before.stops)):
        stop = before.stops[i]
        available = changes.get((stop, before.line), ())
        for (s, line, terminal), departure in sorted(cutoffs.items()):
            if (s == stop and line in available
                    and before.times[i] + transfer_minutes <= departure < after.times[i] + transfer_minutes):
                missed.append(f"{s}：{line}→{terminal} {clock(departure)}")
    return missed


def west_station_comparison(graph, trips, transfer_minutes=TRANSFER_MINUTES):
    stations, changes = network_stations(graph)
    mask = ~np.eye(len(stations), dtype=bool)
    o, d = (stations.index(s) for s in (AIRPORT, EXAMPLE_DESTINATION))
    last3 = last_by_direction(trips, "3")[SOUTH_TERMINAL]
    airport_last = next(trip for trip in last_by_direction(trips, "S1").values() if trip.stops[0] == AIRPORT)
    airport_arrival = airport_last.times[airport_last.stops.index(WEST)]
    west_position = last3.stops.index(WEST)
    held = [(m, hold_at(last3, WEST, m)) for m in (2, 5, 10)]
    misses = {m: missed_last_connections(trips, last3, variant, WEST, changes, transfer_minutes)
              for m, variant in held}
    scenarios = [("baseline", 0, [], last3, trips)]
    scenarios.extend((f"hold_{m}", m, [], variant, [variant if t == last3 else t for t in trips])
                     for m, variant in held)
    extra_same = shift_trip(last3, EXTENSION)
    extra_both = extra_trips(trips, "3")
    scenarios.extend([("add_same_direction_15", 0, [extra_same], extra_same, trips + [extra_same]),
                      ("add_both_directions_15", 0, extra_both, extra_same, trips + extra_both)])
    # 只改变 S1 → 3 在合肥西站的换乘耗时，其他换乘仍用原实验参数。
    for west_minutes in sorted({*range(3, 8), int(transfer_minutes)}):
        override = {(WEST, "S1", "3"): west_minutes}
        base = latest_boarding(trips, stations, changes, transfer_minutes, override)[mask]
        if (base < 0).any():
            raise ValueError("夜间班次不足，无法确定基线 OD")
        for name, hold, extras, late_train, timetable in scenarios:
            matrix = latest_boarding(timetable, stations, changes, transfer_minutes, override)
            after = matrix[mask]
            valid = after >= 0
            delta = after[valid] - base[valid]
            late_train_departure = late_train.depart_at(west_position)
            catch = airport_arrival + west_minutes <= late_train_departure
            row = dict(west_s1_to_3_min=west_minutes, scenario=name, hold_min=hold, added_trips=len(extras),
                       last_3_departure_at_west=clock(late_train_departure),
                       airport_last_can_transfer=int(catch), airport_to_fanhua_latest=clock(matrix[o, d]),
                       airport_last_arrival_at_fanhua=clock(late_train.times[late_train.stops.index(EXAMPLE_DESTINATION)]) if catch else "",
                       later_od=int((delta > 0).sum()), earlier_od=int((delta < 0).sum()),
                       no_route_od=int((~valid).sum()),
                       gained_window_od_min=int(delta[delta > 0].sum()), lost_window_od_min=int(-delta[delta < 0].sum()),
                       net_window_od_min=int(delta.sum()), missed_downstream_last_connections="；".join(misses.get(hold, ())))
            for t in SNAPSHOTS:
                tag = clock(t).replace(":", "")
                row[f"added_{tag}"] = int(((after >= t) & (base < t)).sum())
                row[f"lost_{tag}"] = int(((after < t) & (base >= t)).sum())
            yield row


def write_csv(path, rows):
    it = iter(rows)
    first = next(it)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(first), lineterminator="\n")
        writer.writeheader()
        writer.writerow(first)
        writer.writerows(it)


def plot(out, curve, ranking):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "Noto Sans CJK SC", "SimHei", "DejaVu Sans"],
                         "axes.unicode_minus": False})
    best = ranking[0]["line"]
    best_2230 = max(ranking, key=lambda r: r["added_reachable_2230"])["line"]
    fig, (ax, bars) = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained")
    times = [minutes(r["time"]) for r in curve]
    ax.step(times, [r["baseline"] for r in curve], where="post", label="基线", color="#354f5c")
    ax.step(times, [r[f"plus_{best}"] for r in curve], where="post", label=f"{best} 线加开（全局第一）", color="#c16a36")
    if best_2230 != best:
        ax.step(times, [r[f"plus_{best_2230}"] for r in curve], where="post",
                label=f"{best_2230} 线加开（22:30 第一）", color="#377a71")
    ax.set_xticks(range(times[0], times[-1] + 1, 30))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: clock(int(x))))
    ax.set(xlabel="在起点站台就绪时刻", ylabel="仍可完成的有向站点对", title="随末班车开走，可达机会逐步减少")
    ax.legend()
    ordered = ranking[::-1]
    bars.barh([r["line"] for r in ordered], [r["total_window_gain_od_min"] for r in ordered], color="#377a71")
    bars.set(xlabel="可出发窗口增量总和（OD·分钟）", title="各线双向各加开一班（相对末班 +15 分钟）")
    ax.grid(alpha=.2)
    bars.grid(axis="x", alpha=.2)
    fig.savefig(out / "night_ablation.png", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--transfer-minutes", type=int, default=int(TRANSFER_MINUTES))
    args = parser.parse_args()
    graph = nx.read_graphml(GRAPH_FILE)
    day, trips = load_timetable(graph)
    rows, ranking, curve = analyze(graph, trips, args.transfer_minutes)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "latest_boarding.csv", rows)
    write_csv(args.output / "line_gain.csv", ranking)
    write_csv(args.output / "reachability.csv", curve)
    write_csv(args.output / "three_line_reachability.csv", three_line_comparison(graph, trips, args.transfer_minutes))
    write_csv(args.output / "west_station_hold.csv", west_station_comparison(graph, trips, args.transfer_minutes))
    plot(args.output, curve, ranking)
    print(f"{day}: {len(trips)} trips; top line: {ranking[0]['line']}; results: {args.output}")


if __name__ == "__main__":
    main()
