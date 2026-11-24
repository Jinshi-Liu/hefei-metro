import csv
import hashlib
import json
import unittest
from itertools import product

import networkx as nx
import numpy as np

from src.build_network import GRAPH_FILE
from src.transfer_ablation import OUTPUT, MetroAblation, analyze


class AblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = nx.read_graphml(GRAPH_FILE)
        cls.metro = MetroAblation(cls.graph)
        cls.base = cls.metro.distances()

    def od_minutes(self, vector, a, b):
        i, j = sorted(self.metro.stations.index(s) for s in (a, b))
        indexes = self.metro.od
        return vector[(indexes[0] == i) & (indexes[1] == j)].item()

    def test_routing_agrees_with_independent_networkx_reference(self):
        after = self.metro.distances(["合肥南站"])
        cut = self.graph.copy()
        cut.remove_edges_from([(u, v) for u, v, d in cut.edges(data=True) if d.get("station") == "合肥南站"])
        self.assertEqual(cut.number_of_nodes(), self.graph.number_of_nodes())
        self.assertEqual(cut.number_of_edges(), self.graph.number_of_edges() - 3)

        def copies(s):
            return [n for n, d in cut.nodes(data=True) if d["station"] == s]

        for a, b in [("义兴", "南屏路"), ("合肥南站", "嵩山路"), ("紫庐", "嵩山路")]:
            with self.subTest(origin=a, destination=b):
                expected = min(nx.shortest_path_length(cut, u, v, weight="weight")
                               for u, v in product(copies(a), copies(b)))
                self.assertEqual(self.od_minutes(after, a, b), expected)
        self.assertEqual(self.od_minutes(self.base, "义兴", "南屏路"), 19)
        self.assertEqual(self.od_minutes(after, "义兴", "南屏路"), 50)
        self.assertEqual(self.od_minutes(after, "合肥南站", "嵩山路"),
                         self.od_minutes(self.base, "合肥南站", "嵩山路"))

    def test_south_slower_west_unreachable(self):
        self.assertEqual(len(self.base), 20706)
        south = self.metro.distances(["合肥南站"])
        west = self.metro.distances(["合肥西站"])
        self.assertTrue(np.isfinite(south).all())
        self.assertEqual(np.count_nonzero(south > self.base), 3003)
        self.assertAlmostEqual((south - self.base)[south > self.base].mean(), 8.65168165168)
        reachable = np.isfinite(west)
        self.assertEqual((~reachable).sum(), 1746)
        np.testing.assert_array_equal(west[reachable], self.base[reachable])
        for minutes in (3, 7):
            other = self.metro.distances(["合肥西站"], minutes)
            np.testing.assert_array_equal(np.isfinite(other), reachable)

    def test_saved_results_match_small_recheck(self):
        saved = json.loads((OUTPUT / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["graph_sha256"],
                         hashlib.sha256(GRAPH_FILE.read_bytes().replace(b"\r\n", b"\n")).hexdigest())
        single, curves, summary = analyze(self.graph, repeats=3, seed=saved["random_seed"])
        self.assertEqual(single[0]["station"], "合肥西站")
        self.assertEqual(saved["fixed_orders"], summary["fixed_orders"])
        cohort = summary["fixed_cohort"]
        self.assertEqual(cohort, saved["fixed_cohort"])
        self.assertEqual(cohort["newly_unreachable_od"], 6394)
        self.assertGreater(cohort["mean_added_before"], cohort["mean_added_after"])
        self.assertLess(cohort["shared_od_mean_before"], cohort["shared_od_mean_after"])
        with (OUTPUT / "multi_station.csv").open(encoding="utf-8-sig", newline="") as file:
            rows = {(r["strategy"], int(r["k"])): r for r in csv.DictReader(file)}
        self.assertEqual(len(rows), 63)
        for row in curves:
            if row["strategy"] != "random":
                saved_row = rows[row["strategy"], row["k"]]
                self.assertEqual(row["unreachable_od_mean"], float(saved_row["unreachable_od_mean"]))
                self.assertAlmostEqual(row["efficiency_ratio_mean"], float(saved_row["efficiency_ratio_mean"]))
        self.assertEqual({int(r["samples"]) for r in rows.values() if r["strategy"] == "random"}, {100})


if __name__ == "__main__":
    unittest.main()
