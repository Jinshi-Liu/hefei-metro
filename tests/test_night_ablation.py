import unittest
from collections import defaultdict

import networkx as nx
import numpy as np

from src import night_ablation as night


class NightAblationTests(unittest.TestCase):
    def test_matches_explicit_time_graph(self):
        trips = [
            night.Trip("1", ("A", "B", "C"), (1324, 1331, 1334)),
            night.Trip("1", ("A", "B", "C"), (1332, 1338, 1341)),
            night.Trip("1", ("C", "B", "A"), (1334, 1337, 1343)),
            night.Trip("2", ("B", "D"), (1336, 1342)),
            night.Trip("2", ("D", "B"), (1338, 1342)),
        ]
        stations = list("ABCD")
        changes = {("B", "1"): {"2"}, ("B", "2"): {"1"}}
        # 独立对照：显式连出同车续坐、到站和所有满足时刻的换车边。
        graph = nx.DiGraph()
        departures = defaultdict(list)
        for ti, t in enumerate(trips):
            for pos, (station, minute) in enumerate(zip(t.stops[:-1], t.times[:-1])):
                event = (ti, pos)
                graph.add_node(event)
                departures[station].append((minute, t.line, event))
        for ti, t in enumerate(trips):
            for pos, (station, minute) in enumerate(zip(t.stops[1:], t.times[1:])):
                event = (ti, pos)
                graph.add_edge(event, station)
                if pos + 2 < len(t.stops):
                    graph.add_edge(event, (ti, pos + 1))
                for depart, line, target in departures[station]:
                    if ((line == t.line and depart >= minute + night.SAME_LINE_CHANGE)
                            or (line in changes.get((station, t.line), ()) and depart >= minute + 5)):
                        graph.add_edge(event, target)
        result = night.latest_boarding(trips, stations, changes, 5)
        for i, o in enumerate(stations):
            for j, d in enumerate(stations):
                if o != d:
                    expected = max((depart for depart, _, event in departures[o] if nx.has_path(graph, event, d)), default=-1)
                    self.assertEqual(result[i, j], expected)
        self.assertEqual(result[0, 3], 1324)  # 赶末班接驳，不能搭最后一班 1 线
        self.assertEqual(result[0, 2], 1332)  # 不换车，原班次继续驶到 C
        self.assertEqual(result[3, 0], -1)   # 反方向不一定同样可达

    def test_holding_changes_departure_but_not_arrival_at_hold_station(self):
        original = night.Trip("1", ("A", "B", "C"), (1310, 1320, 1330))
        held = night.hold_at(original, "B", 5)
        self.assertEqual(held.times, (1310, 1320, 1335))
        self.assertEqual(held.departures, (1310, 1325, 1335))
        trips = [held, night.Trip("2", ("B", "D"), (1325, 1330))]
        changes = {("B", "1"): {"2"}, ("B", "2"): {"1"}}
        result = night.latest_boarding(trips, list("ABCD"), changes, 5)
        self.assertEqual(result[0, 3], 1310)  # 车在 B 到得早，已经可以下车换乘
        self.assertEqual(result[1, 2], 1325)  # 在 B 等本车，等候后才发车

    def test_snapshot_and_saved_results(self):
        g = nx.read_graphml(night.GRAPH_FILE)
        day, trips = night.load_timetable(g)
        self.assertEqual((day, len(trips)), ("2026-11-23", 449))
        self.assertEqual(len(night.read_rows(night.LAST_DEPARTURES_FILE)), 432)
        stations, changes = night.network_stations(g)
        base = night.latest_boarding(trips, stations, changes)
        extension = night.extra_trips(trips, "3")
        self.assertEqual(len(extension), 2)
        after = night.latest_boarding(trips + extension, stations, changes)
        self.assertTrue(np.all(after >= base))
        o, d = map(stations.index, ("新桥2号航站楼", "繁华大道"))
        self.assertEqual((night.clock(base[o,d]), night.clock(after[o,d])), ("22:15", "22:30"))
        actual = night.read_rows(night.OUTPUT / "line_gain.csv")
        _, ranking, curve = night.analyze(g, trips)
        self.assertEqual(len(actual), 9)
        self.assertEqual(actual[0]["line"], "3")
        for row, expected in zip(actual, ranking):
            self.assertEqual(row["line"], expected["line"])
            self.assertEqual(int(row["total_window_gain_od_min"]), expected["total_window_gain_od_min"])
        self.assertEqual(curve[0]["baseline"], 41412)
        self.assertEqual(curve[-1]["baseline"], 0)
        for key in ("baseline", *(f"plus_{row['line']}" for row in ranking)):
            self.assertTrue(all(a[key] >= b[key] for a, b in zip(curve, curve[1:])))
            if key != "baseline":
                line = key.removeprefix("plus_")
                total = next(r["total_window_gain_od_min"] for r in ranking if r["line"] == line)
                self.assertEqual(sum(row[key] - row["baseline"] for row in curve), total)

    def test_three_line_combination(self):
        graph = nx.read_graphml(night.GRAPH_FILE)
        _, trips = night.load_timetable(graph)
        saved = night.read_rows(night.OUTPUT / "three_line_reachability.csv")
        actual = list(night.three_line_comparison(graph, trips))
        self.assertEqual(saved, [{k: str(v) for k, v in r.items()} for r in actual])
        for r in actual:
            self.assertLessEqual(r["baseline"], min(r["plus_2"], r["plus_3"], r["plus_6"]))
            self.assertLessEqual(max(r["plus_2"], r["plus_3"], r["plus_6"]), r["union_of_singles"])
            self.assertEqual(r["plus_2_3_6"] - r["union_of_singles"], r["only_joint"])
        row = next(r for r in actual if r["time"] == "22:30")
        self.assertEqual(row["plus_2_3_6"] - row["baseline"], 4236)
        self.assertEqual(row["only_joint"], 281)

    def test_west_hold_comparison(self):
        rows = {(int(r["west_s1_to_3_min"]), r["scenario"]): r
                for r in night.read_rows(night.OUTPUT / "west_station_hold.csv")}
        self.assertEqual(len(rows), 30)
        graph = nx.read_graphml(night.GRAPH_FILE)
        _, trips = night.load_timetable(graph)
        for row in night.west_station_comparison(graph, trips):
            key = (row["west_s1_to_3_min"], row["scenario"])
            self.assertEqual(rows[key], {k: str(v) for k, v in row.items()})
        self.assertEqual(rows[5, "baseline"]["airport_to_fanhua_latest"], "22:15")
        self.assertEqual(rows[5, "hold_2"]["airport_to_fanhua_latest"], "22:30")
        self.assertEqual(rows[6, "hold_2"]["airport_to_fanhua_latest"], "22:15")
        for transfer in (3, 4, 5, 6, 7):
            self.assertEqual(rows[transfer, "hold_5"]["airport_to_fanhua_latest"], "22:30")
            self.assertIn("西七里塘", rows[transfer, "hold_10"]["missed_downstream_last_connections"])
        self.assertEqual(int(rows[5, "hold_10"]["earlier_od"]), 207)
        self.assertEqual(int(rows[5, "hold_10"]["lost_2300"]), 36)
        self.assertEqual(int(rows[5, "add_same_direction_15"]["earlier_od"]), 0)
        self.assertEqual(int(rows[5, "add_both_directions_15"]["net_window_od_min"]), 83085)


if __name__ == "__main__":
    unittest.main()
