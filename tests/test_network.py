import hashlib
import unittest

import networkx as nx
import numpy as np
from scipy.stats import spearmanr

from src.build_network import DATA_FILE, GRAPH_FILE, build_weighted_network, station_id
from src.visualize_network import load_map, map_counts
from src.visualize_weighted_network import fit_minutes


class NetworkTests(unittest.TestCase):
    def test_graphml_matches_source(self):
        expected = build_weighted_network()
        saved = nx.read_graphml(GRAPH_FILE)
        self.assertFalse(saved.is_directed())
        self.assertTrue(nx.is_connected(saved))
        self.assertEqual(dict(expected.nodes(data=True)), dict(saved.nodes(data=True)))
        edges = lambda graph: {frozenset((u, v)): attrs for u, v, attrs in graph.edges(data=True)}
        self.assertEqual(edges(expected), edges(saved))
        self.assertEqual(saved.graph["source_sha256"],
                         hashlib.sha256(DATA_FILE.read_bytes().replace(b"\r\n", b"\n")).hexdigest())

    def test_scope_and_minute_weights(self):
        graph = build_weighted_network()
        self.assertEqual({d["line"] for _, d in graph.nodes(data=True)}, {*"12345678", "S1"})
        self.assertEqual(len({d["station"] for _, d in graph.nodes(data=True)}), 204)
        self.assertEqual(len(graph), 225)
        running = [d for _, _, d in graph.edges(data=True) if d["edge_type"] == "running"]
        transfers = [d for _, _, d in graph.edges(data=True) if d["edge_type"] == "transfer"]
        self.assertEqual((len(running), len(transfers)), (216, 22))
        self.assertEqual(len({d["station"] for d in transfers}), 20)
        self.assertEqual({d["weight"] for d in transfers}, {5.0})
        self.assertEqual(graph["紫庐_L7"]["嵩山路_L7"]["weight"], 2.5)
        self.assertEqual(graph[station_id("合肥西站", "3")][station_id("合肥西站", "S1")]["weight"], 5)

    def test_three_transfer_links_at_south_station(self):
        graph = build_weighted_network()
        south = {frozenset((graph.nodes[u]["line"], graph.nodes[v]["line"]))
                 for u, v, d in graph.edges(data=True) if d.get("station") == "合肥南站"}
        self.assertEqual(south, {frozenset(pair) for pair in ("14", "15", "45")})

    def test_map_keeps_all_edges_and_weights(self):
        positions, stations, running = load_map(GRAPH_FILE)
        self.assertEqual(positions.keys(), stations.keys())
        self.assertEqual(map_counts(stations, running), (204, 225, 216, 22))
        self.assertEqual(set(stations["合肥南站"]["transfers"]),
                         {("1", "4", 5), ("1", "5", 5), ("4", "5", 5)})
        self.assertIn(("7", "嵩山路", 2.5), stations["紫庐"]["rides"])

    def test_weighted_layout_follows_minute_costs(self):
        graph = nx.read_graphml(GRAPH_FILE)
        positions = fit_minutes(graph)
        self.assertEqual(positions.keys(), graph.nodes.keys())
        weights, lengths = zip(*[(d["weight"], np.linalg.norm(positions[u] - positions[v]))
                                 for u, v, d in graph.edges(data=True)])
        self.assertGreater(spearmanr(weights, lengths).statistic, .8)


if __name__ == "__main__":
    unittest.main()
