"""Correctness-only integration of canonical Python artifacts and C++ replay."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_workloads import (FAMILIES, generate, parse_graph, parse_trace, replay,
                            specification, graph_bytes, ROOT)
from test_workload_loader import bellman_ford
from artifacts import verify, write_bundle, verify_bundle
from workloads import Graph, Trace, sha256, trace_bytes

POLICIES = ("dijkstra", "delta-stepping", "incremental", "heuristic")
MODES = ("shared_fast_path", "execute_selected")


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.graph_path = self.directory / 'graph with spaces.txt'
        self.trace_path = self.directory / 'trace with spaces.txt'
        self.manifest, self.graph, self.trace = generate(specification())
        self.write(self.graph, self.trace)

    def write(self, graph, trace):
        self.graph_path.write_bytes(graph)
        self.trace_path.write_bytes(trace)

    def arguments(self, source=0, policy='incremental', mode='shared_fast_path'):
        return ['verify', '--graph', str(self.graph_path), '--trace', str(self.trace_path),
                '--source', str(source), '--policy', policy, '--delta', '16', '--threads', '2',
                '--no-effect', mode, '--verification', 'full']

    def invoke(self, arguments):
        return subprocess.run([CLI, *arguments], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=False, timeout=15)

    def success(self, graph_data, trace_data, source=0):
        self.write(graph_data, trace_data)
        original = (self.graph_path.read_bytes(), self.trace_path.read_bytes())
        final = replay(parse_graph(graph_data), parse_trace(trace_data))
        expected_weights = [weight for _, _, weight in final.edges]
        expected_distances = bellman_ford(final, source)
        count = len(parse_trace(trace_data).updates)
        for policy in POLICIES:
            for mode in MODES:
                with self.subTest(policy=policy, mode=mode):
                    arguments = self.arguments(source, policy, mode)
                    process = self.invoke(arguments)
                    self.assertEqual((process.returncode, process.stderr), (0, b''))
                    record = json.loads(process.stdout)
                    self.assertTrue(record['success'])
                    self.assertEqual(record['failure_category'], 'none')
                    self.assertIsNone(record['failing_update_index'])
                    for key in ('trace_entries', 'updates_executed', 'updates_verified'):
                        self.assertEqual(record[key], count)
                    self.assertEqual(record['reference_recomputations'], count + 1)
                    self.assertEqual(record['bellman_ford_checks'],
                                     count + 1 if final.vertices <= 128 and len(final.edges) <= 4096 else 0)
                    self.assertTrue(record['final_graph_verified'])
                    self.assertTrue(record['final_distances_verified'])
                    self.assertEqual(record['final_weights'], expected_weights)
                    self.assertEqual(record['final_distances'], expected_distances)
                    self.assertEqual(record['identity_origin'], 'unverified_artifact_metadata')
                    self.assertEqual(record['integrity'], 'external_python_verifier_required')
                    self.assertEqual(record['declared_graph_sha256'], sha256(graph_data))
                    # Canonical final weights agree with independent Python replay hash.
                    reconstructed = Graph(final.vertices, tuple((u, v, weight) for (u, v, _), weight
                                                               in zip(final.edges, record['final_weights'])))
                    self.assertEqual(sha256(graph_bytes(reconstructed)), sha256(graph_bytes(final)))
                    self.assertEqual(self.invoke(arguments).stdout, process.stdout)
        self.assertEqual((self.graph_path.read_bytes(), self.trace_path.read_bytes()), original)

    def failure(self, arguments=None, category=None, index=None, executed=None):
        process = self.invoke(self.arguments() if arguments is None else arguments)
        self.assertEqual(process.returncode, 2)
        self.assertTrue(process.stderr)
        record = json.loads(process.stdout)
        self.assertFalse(record['success'])
        self.assertFalse(record['final_graph_verified'])
        self.assertFalse(record['final_distances_verified'])
        self.assertNotIn('final_weights', record)
        self.assertNotIn('final_distances', record)
        if category is not None:
            self.assertEqual(record['failure_category'], category)
        self.assertEqual(record['failing_update_index'], index)
        if executed is not None:
            self.assertEqual(record['updates_executed'], executed)
        return record

    def test_generated_families_distributions_all_policies(self):
        distributions = [
            {'kind': 'positive_uniform', 'min': 8, 'max': 32},
            {'kind': 'zero_inclusive', 'max': 32, 'zero_numerator': 1, 'denominator': 2},
            {'kind': 'bimodal', 'low_min': 0, 'low_max': 2, 'high_min': 4294967293,
             'high_max': 4294967295, 'high_numerator': 1, 'denominator': 2}]
        for family in FAMILIES:
            for weights in distributions:
                spec = specification(family)
                spec['weights'] = weights
                spec['trace'].update(count=3, schedule=['equal', 'strict', 'equal'])
                manifest, graph, trace = generate(spec)
                self.assertEqual(verify(manifest, graph, trace)['status'], 'verified')
                self.success(graph, trace, manifest['source'])

    def test_repeated_equal_zero_cycles_unreachable_no_effect(self):
        graph = Graph(7, ((0, 1, 9), (0, 2, 1), (1, 2, 0), (2, 1, 0),
                          (3, 4, 8), (4, 3, 0), (5, 5, 0)))
        trace = Trace(sha256(graph_bytes(graph)), ('0', '18446744073709551615', '2', '3'), 0,
                      ((0, 3, 4, 8, 7), (1, 0, 1, 9, 8), (2, 0, 1, 8, 8),
                       (3, 0, 1, 8, 0), (4, 0, 1, 0, 0), (5, 4, 3, 0, 0)))
        self.success(graph_bytes(graph), trace_bytes(trace))
        self.success(graph_bytes(graph), trace_bytes(replace(trace, source=6)), 6)

    def test_every_trace_prefix_against_python_oracle(self):
        # Independent Python integers/None sentinel, original endpoint records and
        # synchronous Bellman-Ford. Every prefix is a fresh public verify call.
        initial = Graph(8, ((0, 1, 30), (0, 2, 3), (1, 2, 0), (1, 3, 4294967295),
                            (2, 1, 0), (3, 0, 0), (4, 5, 9), (5, 4, 0), (6, 6, 10)))
        updates = ((0, 0, 1, 30, 29), (1, 0, 1, 29, 29), (2, 4, 5, 9, 0),
                   (3, 0, 1, 29, 2), (4, 1, 3, 4294967295, 0), (5, 0, 1, 2, 0))
        graph_data = graph_bytes(initial)
        for source in (0, 7):
            ledger = {(u, v): weight for u, v, weight in initial.edges}
            for length in range(len(updates) + 1):
                if length:
                    _, u, v, old, new = updates[length - 1]
                    self.assertEqual(ledger[u, v], old); ledger[u, v] = new
                expected = Graph(initial.vertices, tuple((u, v, weight) for (u, v), weight in sorted(ledger.items())))
                trace = Trace(sha256(graph_data), ('0',) * 4, source, updates[:length])
                self.write(graph_data, trace_bytes(trace))
                for policy in POLICIES:
                    for mode in MODES:
                        with self.subTest(source=source, prefix=length, policy=policy, mode=mode):
                            process = self.invoke(self.arguments(source, policy, mode))
                            self.assertEqual((process.returncode, process.stderr), (0, b''))
                            result = json.loads(process.stdout)
                            self.assertEqual(result['final_weights'], list(ledger.values()))
                            self.assertEqual(result['final_distances'], bellman_ford(expected, source))
                            self.assertEqual(result['updates_verified'], length)
                            self.assertEqual(result['bellman_ford_checks'], length + 1)

    def test_empty_trace_edgeless_and_bellman_ford_boundary(self):
        for vertices in (1, 128, 129):
            graph = Graph(vertices, ())
            trace = Trace(sha256(graph_bytes(graph)), ('0',) * 4, vertices - 1, ())
            self.success(graph_bytes(graph), trace_bytes(trace), vertices - 1)

    def test_generator_verifier_cli_cross_language(self):
        spec_path = self.directory / 'spec.json'
        spec_path.write_text(json.dumps(specification('layered')), encoding='ascii')
        bundle = self.directory / 'bundle'
        generator = ROOT / 'benchmarks/python/generate.py'
        for args in (['generate', '--spec', str(spec_path), '--output', str(bundle)],
                     ['verify', '--manifest', str(bundle / 'manifest.json')]):
            process = subprocess.run([sys.executable, str(generator), *args], capture_output=True, check=False)
            self.assertEqual((process.returncode, process.stderr), (0, b''))
        self.success((bundle / 'graph.txt').read_bytes(), (bundle / 'trace.txt').read_bytes())

    def test_invalid_graph_syntax_counts_and_quotas(self):
        for graph in (b'', b'2 0', b'2 0\n\n', b'2 0\r\n', b'02 0\n', b'2  0\n',
                      b'2 1\n', b'2 0\n0 1 1\n', b'2 1\n0 2 1\n', b'2 1\n0 1 -1\n',
                      b'2 1\n0 1 +1\n', b'2 1\n0 1 1.0\n', b'2 1\n0 1 4294967296\n',
                      b'2 2\n0 1 2\n0 1 1\n', b'2 2\n1 0 2\n0 1 1\n',
                      b'100001 0\n', b'1 500001\n', b'18446744073709551616 0\n',
                      b'2 1\n0 1 1\x00\n', b'\xff\n', b'2 1\n0\t1 1\n'):
            with self.subTest(graph=graph):
                self.write(graph, self.trace)
                self.failure(category='artifact_validation', executed=0)
        self.write(b' ' * (32 * 1024 * 1024 + 1), self.trace)
        self.failure(category='artifact_validation', executed=0)

    def test_invalid_trace_headers_records_and_limits(self):
        mutations = [self.trace.replace(b'TRACE 1', b'TRACE 2'), self.trace[:-1], self.trace + b'\n',
                     self.trace.replace(b'trace-v1', b'trace-v2'), self.trace.replace(b'graph-v1', b'graph-v2'),
                     self.trace.replace(b'splitmix64-v1', b'other'), self.trace.replace(b'graph_seed 1', b'graph_seed 01'),
                     self.trace.replace(b'graph_seed 1', b'graph_seed 18446744073709551616'),
                     self.trace.replace(b'source 0', b'source 1'), self.trace.replace(b'updates 9', b'updates 100001'),
                     self.trace.replace(b'graph_sha256 ', b'unknown '),
                     self.trace.replace(parse_trace(self.trace).graph_sha256.encode(), b'G' * 64),
                     self.trace.replace(b'updates 9', b'updates 8'), b' ' * (16 * 1024 * 1024 + 1)]
        for trace in mutations:
            with self.subTest(trace=trace[:100]):
                self.write(self.graph, trace)
                # Truncated final record identifies the parsing update index.
                index = 8 if trace == self.trace[:-1] else None
                self.failure(category='artifact_validation', index=index, executed=0)
        lines = self.trace.splitlines(keepends=True)
        for record in (b'1 0 1 18 17\n', b'0 100000 1 18 17\n', b'0 0 1 4294967296 17\n',
                       b'0 0 1 18\n', b'0 0 1 18 17 extra\n', b'0 0 1 18 1e0\n'):
            changed = lines.copy()
            changed[11] = record
            self.write(self.graph, b''.join(changed))
            self.failure(category='artifact_validation', index=0, executed=0)

    def test_invalid_ledger_transitions_stop_at_update(self):
        trace = parse_trace(self.trace)
        for bad in ((0, 0, 1, 19, 17), (0, 0, 1, 18, 19), (0, 0, 5, 18, 17), (0, 6, 1, 18, 17)):
            self.write(self.graph, trace_bytes(replace(trace, updates=(bad,) + trace.updates[1:])))
            self.failure(category='trace_validation', index=0, executed=0)
        changed = list(trace.updates)
        i, u, v, old, new = changed[1]
        changed[1] = (i, u, v, old + 1, new)
        self.write(self.graph, trace_bytes(replace(trace, updates=tuple(changed))))
        record = self.failure(category='trace_validation', index=1, executed=1)
        self.assertEqual(record['updates_verified'], 1)

    def test_cli_strictness_help_and_sources(self):
        process = self.invoke(['--help'])
        self.assertEqual(process.returncode, 0)
        self.assertIn(b'Usage: dynagraph_bench', process.stdout)
        for key, value in (('--source', '6'), ('--source', '-1'), ('--policy', 'other'),
                           ('--delta', '0'), ('--delta', '18446744073709551616'), ('--delta', '01'),
                           ('--threads', '-1'), ('--threads', '65'), ('--threads', '1.0'),
                           ('--no-effect', 'other'), ('--verification', 'bounded')):
            args = self.arguments()
            args[args.index(key) + 1] = value
            self.failure(args)
        for args in ([], ['--help', 'extra'], ['run'], self.arguments() + ['--unknown', '1'],
                     self.arguments() + ['--delta', '1'], self.arguments() + ['--graph'],
                     self.arguments()[:-2], ['verify', '--graph', '']):
            # Removing optional --verification is valid; omit required delta instead.
            if args == self.arguments()[:-2]:
                position = args.index('--delta')
                del args[position:position + 2]
            self.failure(args, category='cli_validation')
        for delta in ('1', '18446744073709551615'):
            for workers in ('0', '1', '2', '64'):
                args = self.arguments(policy='delta-stepping')
                args[args.index('--delta') + 1] = delta
                args[args.index('--threads') + 1] = workers
                self.assertEqual(self.invoke(args).returncode, 0)
        self.graph_path.unlink()
        self.failure(category='artifact_validation', executed=0)

    def test_external_integrity_boundary_rejects_wrong_identities(self):
        # C++ deliberately does not implement cryptography: the documented Python
        # prerequisite rejects graph/trace identities and inconsistent provenance.
        manifest_path = write_bundle(specification(), self.directory / 'bundle')
        self.assertEqual(verify_bundle(manifest_path)['status'], 'verified')
        graph_path = manifest_path.parent / 'graph.txt'
        original_graph = graph_path.read_bytes()
        graph_path.write_bytes(original_graph.replace(b'0 1 18', b'0 1 17'))
        with self.assertRaisesRegex(ValueError, 'graph SHA-256 mismatch'):
            verify_bundle(manifest_path)
        graph_path.write_bytes(original_graph)
        trace_path = manifest_path.parent / 'trace.txt'
        original_trace = trace_path.read_bytes()
        trace_path.write_bytes(original_trace + b'\n')
        with self.assertRaisesRegex(ValueError, 'trace SHA-256 mismatch'):
            verify_bundle(manifest_path)
        changed = replace(parse_trace(original_trace), graph_sha256='0' * 64)
        changed_bytes = trace_bytes(changed)
        changed_manifest = json.loads(manifest_path.read_bytes())
        changed_manifest['artifacts']['trace']['sha256'] = sha256(changed_bytes)
        with self.assertRaisesRegex(ValueError, 'graph fingerprint mismatch'):
            verify(changed_manifest, original_graph, changed_bytes)
        self.write(original_graph, changed_bytes)
        process = self.invoke(self.arguments())
        self.assertEqual(process.returncode, 0)
        self.assertEqual(json.loads(process.stdout)['identity_origin'], 'unverified_artifact_metadata')


if __name__ == '__main__':
    CLI = sys.argv.pop(1)
    unittest.main()
