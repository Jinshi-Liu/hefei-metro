"""检查 C 的正式交付与 A/B 输入一致，不重跑全量随机实验。"""

import hashlib
import json
import sys
import unittest
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import build_network as bn
import routing as rt
from run_c_step2 import read_csv, verify_shared_inputs

TABLES = ROOT / 'results' / 'tables' / 'c'
STEP2 = TABLES / 'step2'
STEP3 = TABLES / 'step3'


def scenario_id(row):
    return row['strategy'], row['trial'], row['k']


class CResultsTests(unittest.TestCase):
    def test_published_inputs_match_shared_files(self):
        base = json.loads((STEP2 / 'C05_run_parameters.json').read_text(encoding='utf-8-sig'))
        verify_shared_inputs(base['hashes'])

        sensitivity = json.loads((STEP3 / 'C12_run_parameters.json').read_text(encoding='utf-8-sig'))
        sensitivity_hashes = dict(sensitivity['hashes'])
        # C12 v1.0 只引用 C05，未再次记录其中的 B09 摘要指纹。
        for key, digest in base['hashes'].items():
            if key.endswith('B09_run_parameters.json'):
                sensitivity_hashes.setdefault(key, digest)
        verify_shared_inputs(sensitivity_hashes)
        by_filename = {
            Path(key.replace('\\', '/')).name: digest
            for key, digest in sensitivity['hashes'].items()
        }
        for name in ('C01_disruption_orders.csv', 'C02_multi_disruption_detail.csv', 'C05_run_parameters.json'):
            with self.subTest(file=name):
                lf = (STEP2 / name).read_bytes().replace(b'\r\n', b'\n')
                digests = {hashlib.sha256(data).hexdigest() for data in (lf, lf.replace(b'\n', b'\r\n'))}
                self.assertIn(by_filename[name], digests)

    def test_sensitivity_reuses_baseline_penalty(self):
        base = {scenario_id(row): row for row in read_csv(STEP2 / 'C02_multi_disruption_detail.csv')}
        sensitivity = read_csv(STEP3 / 'C08_sensitivity_detail.csv')
        baseline_rows = [r for r in sensitivity if r['penalty'] == '2']
        self.assertEqual(len(base), 2040)
        self.assertEqual(len(sensitivity), 5 * len(base))
        self.assertEqual(len(baseline_rows), len(base))
        self.assertEqual({scenario_id(row) for row in baseline_rows}, base.keys())
        for row in baseline_rows:
            expected = base[scenario_id(row)]
            for col in ('unreachable_ratio', 'efficiency_ratio', 'mean_delta_survivors', 'mean_delta_affected'):
                self.assertEqual(row[col], expected[col], (scenario_id(row), col))

    def test_rerouting_mean_with_fixed_cohort(self):
        orders = read_csv(STEP2 / 'C01_disruption_orders.csv')
        order = [r['station'] for r in sorted(
            (r for r in orders if r['strategy'] == 'centrality'),
            key=lambda r: int(r['position']),
        )]
        network = bn.build_multilayer_network()
        evaluator = rt.ODEvaluator(network)
        pairs = rt.all_od_pairs(evaluator.stations)

        def reachable_costs(k):
            graph, _ = rt.build_cost_graph(network, closed_transfer_stations=order[:k])
            evaluator.set_graph(graph)
            return {pair: result.cost for pair in pairs
                    if (result := evaluator.evaluate_pair(*pair)).reachable}

        baseline, first, second = (reachable_costs(k) for k in (0, 10, 11))
        self.assertTrue(second.keys() <= first.keys())
        lost = first.keys() - second.keys()
        common = second.keys()

        self.assertEqual(len(common), 10763)
        self.assertEqual(len(lost), 5980)
        self.assertEqual(round(mean(first[p] - baseline[p] for p in first), 2), 8.66)
        self.assertEqual(round(mean(first[p] - baseline[p] for p in common), 2), 2.65)
        self.assertEqual(round(mean(second[p] - baseline[p] for p in common), 2), 2.69)
        self.assertEqual(round(mean(first[p] - baseline[p] for p in lost), 2), 19.49)
