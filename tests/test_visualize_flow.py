"""分时客流 HTML 的数据装配与已存实验结果一致。"""

import unittest

import numpy as np

from src.visualize_flow import FLOW, load, render

HOURS = 18
STATIONS = 204
EDGES = 432


class FlowMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()

    def test_shapes_cover_every_station_edge_and_hour(self):
        d = self.data
        self.assertEqual(len(d["hours"]), HOURS)
        self.assertEqual(len(d["stations"]), STATIONS)
        self.assertEqual(len(d["edges"]), EDGES)
        for key in ("fanout", "alight", "change", "ppi", "rank"):
            self.assertEqual(np.array(d[key]).shape, (STATIONS, HOURS), key)
        self.assertEqual(np.array(d["load"]).shape, (EDGES, HOURS))
        self.assertEqual(np.array(d["topo"]).shape, (STATIONS,))

    def test_ppi_is_a_share_and_load_is_ordered(self):
        ppi = np.array(self.data["ppi"])
        np.testing.assert_allclose(ppi.sum(axis=0), np.ones(HOURS), atol=2e-4)
        self.assertTrue((ppi >= 0).all())
        rank = np.array(self.data["rank"])
        for hour in range(HOURS):
            self.assertEqual(sorted(rank[:, hour]), list(range(1, STATIONS + 1)))
        self.assertTrue((np.array(self.data["load"]) >= 0).all())

    def test_figures_are_self_contained_and_escaped(self):
        html = render(self.data)
        self.assertIn("<!doctype html>", html)
        self.assertNotIn("http://", html.split("<script>")[0])
        self.assertNotIn("{{", html)
        self.assertIn("合肥南站", html)


if __name__ == "__main__":
    unittest.main()
