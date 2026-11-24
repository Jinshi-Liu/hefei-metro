import unittest

import numpy as np

from src import dynamic_demand as model


class DynamicDemandTests(unittest.TestCase):
    def test_ipf_keeps_both_margins(self):
        cost = np.array([[0, 2, 4], [3, 0, 7], [5, 5, 0]])
        seed = np.exp(-cost / 3)
        np.fill_diagonal(seed, 0)
        origin = np.array([.2, .4, .4])
        destination = np.array([.3, .2, .5])
        trips = model.ipf(seed, origin, destination)
        np.testing.assert_allclose(trips.diagonal(), 0)
        np.testing.assert_allclose(trips.sum(axis=1), origin, atol=1e-9, rtol=0)
        np.testing.assert_allclose(trips.sum(axis=0), destination, atol=1e-9, rtol=0)

    def test_aggregate_calibration_preserves_temporal_multiplier(self):
        prior = np.array([[.14, .20, .03, .05], [.19, .15, .14, .10]])
        use = np.array([[1, 0], [0, 1], [1, 1], [1, 1]])
        target = np.array([1000., 480.])
        out = model.fit_boardings(prior, use, target)
        np.testing.assert_allclose(out.sum(axis=0) @ use, target)
        np.testing.assert_allclose(out[0]/out[1], prior[0]/prior[1])

    def test_forecast_uses_past_same_weekdays(self):
        hist = model.read_history(model.INPUT / "ridership_history.csv", model.LINES[:-1])
        official = model.read_history(model.ROOT / "data/line_ridership.csv", model.LINES)
        q, _, held, pairs = model.summarize_forecast(official, hist)
        self.assertEqual(len(pairs), 6)
        self.assertTrue(all(a.weekday() == 0 and b.weekday() == 2 and b < model.ANCHOR for a, b in pairs))
        self.assertEqual(q[-1], official[model.ANCHOR][-1])
        self.assertEqual(held["actual_boardings"], 2084200.)
        self.assertLess(abs(held["error_total_pct"]), abs(held["carry_error_total_pct"]))

    def test_export_preserves_all_stations_and_directional_flows(self):
        with np.load(model.OUT / "time_network.npz") as file:
            od, cost, loads = file["od_trips"], file["cost_minutes"], file["edge_load"]
            ids, names, hours = list(file["station_ids"]), list(file["stations"]), list(file["departure_hours"])
        self.assertEqual(od.shape, (18, 204, 204))
        self.assertEqual(loads.shape, (18, 432))
        self.assertEqual(len(set(names)), 204)
        x, y = names.index("紫庐"), names.index("嵩山路")
        self.assertEqual((cost[x, y], cost[y, x]), (3, 2))
        self.assertEqual(np.count_nonzero(od), 18*204*203)
        idx = {sid: i for i, sid in enumerate(ids)}
        divergence = np.zeros(od.shape[:2])
        for k, edge in enumerate(model.read_rows(model.OUT / "edges.csv")):
            divergence[:, idx[edge["from_id"]]] += loads[:, k]
            divergence[:, idx[edge["to_id"]]] -= loads[:, k]
        np.testing.assert_allclose(divergence, od.sum(axis=2)-od.sum(axis=1), atol=.01, rtol=0)
        rows = model.read_rows(model.OUT / "station_ranks.csv")
        self.assertEqual({(r["hour"], r["station_id"]) for r in rows}, {(h, i) for h in hours for i in ids})
        boarding = sum(float(r["forecast_boardings"]) for r in model.read_rows(model.OUT / "line_forecast.csv"))
        np.testing.assert_allclose(od.astype(float).sum() + sum(float(r["transfers"]) for r in rows),
                                   boarding, atol=.35, rtol=0)


if __name__ == "__main__":
    unittest.main()
