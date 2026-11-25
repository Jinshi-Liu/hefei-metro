"""现场演示脚本与已存单站表的一致性。"""

import csv
import unittest

import networkx as nx
import numpy as np

from src.build_network import GRAPH_FILE
from src.demo import pair_names, station_report
from src.transfer_ablation import OUTPUT, MetroAblation


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metro = MetroAblation(nx.read_graphml(GRAPH_FILE))
        cls.base = cls.metro.distances()

    def test_pair_names_cover_all_unordered_od(self):
        names = pair_names(self.metro)
        self.assertEqual(len(names), 20706)
        self.assertEqual(len(set(map(frozenset, names))), 20706)
        self.assertTrue(all(a != b for a, b in names))

    def test_demo_counts_match_saved_single_station_table(self):
        with (OUTPUT / "single_station.csv").open(encoding="utf-8-sig", newline="") as file:
            saved = {r["station"]: r for r in csv.DictReader(file)}
        for station in ("合肥西站", "西七里塘", "合肥南站"):
            with self.subTest(station=station):
                after = self.metro.distances([station])
                reachable = np.isfinite(after)
                extra = after[reachable] - self.base[reachable]
                self.assertEqual(int((~reachable).sum()), int(saved[station]["unreachable_od"]))
                self.assertEqual(int((extra > 1e-9).sum()), int(saved[station]["slower_od"]))
                self.assertAlmostEqual(float(extra.mean()), float(saved[station]["mean_added_min_reachable"] or 0))

    def test_report_runs_without_side_effects(self):
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            station_report(self.metro, ["合肥西站"], self.metro.transfer_minutes, 2)
        text = buffer.getvalue()
        self.assertIn("失联 1746 对", text)
        self.assertIn("无路可走", text)


if __name__ == "__main__":
    unittest.main()
