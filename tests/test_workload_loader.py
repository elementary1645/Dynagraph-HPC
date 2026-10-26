"""Cross-check all generated families with the unchanged C++ loader/Dijkstra."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_workloads import FAMILIES, generate, parse_graph, parse_trace, replay, specification, graph_bytes


def bellman_ford(graph, source):
    distances = [None] * graph.vertices
    distances[source] = 0
    for _ in range(graph.vertices - 1):
        changed = distances.copy()
        for u, v, weight in graph.edges:
            if distances[u] is not None:
                candidate = distances[u] + weight
                if changed[v] is None or candidate < changed[v]:
                    changed[v] = candidate
        if changed == distances:
            break
        distances = changed
    return distances


class LoaderTests(unittest.TestCase):
    def test_families_distributions_and_final_states(self):
        distributions = [
            {"kind": "positive_uniform", "min": 8, "max": 32},
            {"kind": "zero_inclusive", "max": 32, "zero_numerator": 1, "denominator": 2},
            {"kind": "bimodal", "low_min": 0, "low_max": 2, "high_min": 4294967293,
             "high_max": 4294967295, "high_numerator": 1, "denominator": 2}]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "generated graph.txt"
            for family in FAMILIES:
                for weights in distributions:
                    spec = specification(family)
                    spec["weights"] = weights
                    spec["trace"].update(count=3, schedule=["equal", "strict", "equal"])
                    manifest, data, trace_data = generate(spec)
                    graph, trace = parse_graph(data), parse_trace(trace_data)
                    for current in (graph, replay(graph, trace)):
                        with self.subTest(family=family, weights=weights["kind"], final=current != graph):
                            path.write_bytes(graph_bytes(current))
                            process = subprocess.run([CLI, "sssp", "--input", str(path), "--source",
                                                      str(manifest["source"]), "--algorithm", "dijkstra"],
                                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                            self.assertEqual((process.returncode, process.stderr), (0, b""))
                            response = json.loads(process.stdout)
                            self.assertEqual(response["distances"], bellman_ford(current, manifest["source"]))


if __name__ == "__main__":
    CLI = sys.argv.pop(1)
    unittest.main()
