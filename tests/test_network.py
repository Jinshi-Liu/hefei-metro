"""整理后的基础回归测试；不写入数据或结果。"""
import sys
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build_network as bn
import routing as rt


class NetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = bn.build_multilayer_network()

    def test_saved_network_matches(self):
        self.assertTrue(bn.compare_with_saved_graphml()['consistent'])
        self.assertEqual(len(bn.build_physical_network()), 195)
        self.assertEqual(len(self.graph), 215)

    def test_disruption_keeps_running_edges(self):
        original, _ = rt.build_cost_graph(self.graph)
        closed, info = rt.build_cost_graph(self.graph, closed_transfer_stations=['合肥南站'])
        self.assertEqual(set(original), set(closed))
        def running(g):
            return {frozenset((u, v)) for u, v, d in g.edges(data=True) if d['edge_type'] == 'running'}
        self.assertEqual(running(original), running(closed))
        self.assertEqual(info['running_edges'], 207)
        self.assertEqual(info['transfer_edges'], 18)

    def test_paths_against_networkx(self):
        for model, penalty in rt.COST_MODELS.items():
            evaluator = rt.ODEvaluator(self.graph, model=model)
            for stations in [[], ['紫庐'], bn.transfer_station_names(self.graph)]:
                graph, _ = rt.build_cost_graph(self.graph, model=model, closed_transfer_stations=stations)
                evaluator.set_graph(graph)
                for origin in ['万年埠', '合肥南站', '洪岗']:
                    distances = nx.multi_source_dijkstra_path_length(graph, evaluator.index[origin], weight='weight')
                    for destination in evaluator.stations:
                        result = evaluator.evaluate_pair(origin, destination)
                        expected = min((distances.get(n, float('inf')) for n in evaluator.index[destination]))
                        self.assertEqual(result.reachable, expected != float('inf'))
                        if result.reachable:
                            self.assertAlmostEqual(result.cost, expected)
                            self.assertAlmostEqual(result.cost, result.rides + penalty * result.transfers)


if __name__ == '__main__':
    unittest.main()
