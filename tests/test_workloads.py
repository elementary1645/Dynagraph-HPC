"""Small, deterministic Phase 5B-1 tests; no engine execution or measurements."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "python"))

from artifacts import generate, read_bounded, verify, verify_bundle, write_bundle
from deterministic import EligiblePool, MAX_DRAWS, SplitMix64, UINT64_MAX, sample_ranks
from workloads import (Graph, MAX_EDGES, MAX_UPDATES, MAX_VERTICES, Trace, UINT32_MAX,
                       canonical_json, generate_graph, graph_bytes, parse_graph, parse_json,
                       parse_trace, reachable_vertices, replay, sha256, trace_bytes, validate_spec)


FAMILIES = {
    "chain": ({"family": "chain", "vertices": 6}, 6, 5),
    "grid": ({"family": "grid", "rows": 2, "columns": 3, "bidirectional": True}, 6, 14),
    "sparse_random": ({"family": "sparse_random", "vertices": 8, "edges": 14}, 8, 14),
    "layered": ({"family": "layered", "layers": 3, "width": 3, "fanout": 2}, 9, 12),
    "disconnected": ({"family": "disconnected", "component_sizes": [3, 3], "isolated_vertices": 2}, 8, 4),
}


def specification(family="chain"):
    return {"schema_version": 1, "workload_id": "golden-" + family, "split": "development",
            "seeds": {"graph": "1", "weight": "2", "source": "3", "trace": "4"},
            "graph": deepcopy(FAMILIES[family][0]),
            "weights": {"kind": "positive_uniform", "min": 8, "max": 32},
            "source": {"kind": "explicit", "vertex": 0},
            "trace": {"count": 9, "schedule": ["strict", "repeat", "equal"], "max_decrement": 1}}


# V1 reference fingerprints: initial graph, trace, and replayed final graph.
GOLDEN = {
    "chain": ("ed3529f541bda61ef1f10f89fe4e7382cdb197645663f6c4b02fd32304701137",
              "f780296f560de1637e4100c1f7db4c6cdbd84e4ba58ace3315341e4caef3ffb7",
              "e3bb3352ca01d7291b3c8ba0cabbce20bea7f819a317a28947f2e1f631228d12"),
    "grid": ("f1ff55892d619cd19627f8d5ce16a62158f4d61786127fe8cb62b56511c41ff4",
             "4fc7c8028fe22ccb5e88d140676004507a78105dd6212accaab27e76811ffce6",
             "50bbb2b7b8945a548b407944c74238138420b84f719583f7050cae5127c0aeb6"),
    "sparse_random": ("2df72a8b17b45103d5cc6640f293aa9935a636378f184fd5f25461827fd6b7a8",
                      "30fc5c7d71f0b19c0634ea8c5b919e455c55b9ba8e556ae6bec914f3817d4bd5",
                      "8fe50121834b0fa7ad8bc88f698f503b2ddf0c13bd391ee51c4f7555a8594f21"),
    "layered": ("f49c70433cae314fca47dcd87f6a78d54d7c22b04946b2964eecca0a30c4e53a",
                "3fed9d4170e8a1b53015129afb9a235b89e866424bd1cb0d8ef4230cb15af215",
                "e3fbe06e8794936932cb439c7b777d91d47daaa987ca4a405d45a8ea303f0a2f"),
    "disconnected": ("daf366ef41d4fd6831564f3d2852f40fd8865e668f502d6f1614121330cd5992",
                     "df8dd0df06b8d21a7bd04bc8b9cecaaf26fd06bc5424a167938eb725fef862fa",
                     "7d184d1b94b1de73cce6f274c9214fffa7d8fd6503cab0b3491b17b61116e8ef"),
}


class RandomnessTests(unittest.TestCase):
    def test_splitmix_reference_vector(self):
        random = SplitMix64(0)
        self.assertEqual([random.next_u64() for _ in range(3)],
                         [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F])
        wrap = SplitMix64(UINT64_MAX)
        self.assertEqual(wrap.next_u64(), 0xE4D971771B652C20)
        for seed in (-1, UINT64_MAX + 1, True, "1", 1.0):
            with self.assertRaises(ValueError):
                SplitMix64(seed)

    def test_bounded_mapping_and_exhaustion(self):
        class Scripted(SplitMix64):
            def __init__(self, values):
                self.values = iter(values)
                self.calls = 0

            def next_u64(self):
                self.calls += 1
                return next(self.values)

        random = Scripted([0, 1, 2, 3, UINT64_MAX])
        self.assertEqual([random.below(3) for _ in range(3)], [1, 2, 0])
        self.assertEqual(random.below(1 << 64), UINT64_MAX)
        exhausted = Scripted([0] * MAX_DRAWS)
        with self.assertRaisesRegex(ValueError, "128 draws"):
            exhausted.below(3)
        self.assertEqual(exhausted.calls, MAX_DRAWS)
        for bound in (0, -1, (1 << 64) + 1, True, 1.0):
            with self.assertRaises(ValueError):
                SplitMix64(1).below(bound)

    def test_floyd_sampling_and_pool_order(self):
        for population in range(12):
            for count in range(population + 1):
                ranks = sample_ranks(SplitMix64(123), population, count)
                self.assertEqual(len(ranks), count)
                self.assertEqual(ranks, sorted(set(ranks)))
                self.assertTrue(all(0 <= rank < population for rank in ranks))
        self.assertEqual(sample_ranks(SplitMix64(0), 5, 5), list(range(5)))
        for population, count in ((3, 4), (-1, 0), (3, -1), (True, 1)):
            with self.assertRaises(ValueError):
                sample_ranks(SplitMix64(1), population, count)
        pool = EligiblePool([0, 2, 4, 6])
        pool.discard(2)
        self.assertEqual(pool.items, [0, 6, 4])
        pool.discard(2)
        pool.discard(4)
        pool.discard(0)
        self.assertEqual(pool.choose(SplitMix64(0)), 6)
        pool.discard(6)
        with self.assertRaisesRegex(ValueError, "exhausted"):
            pool.choose(SplitMix64(0))


class GenerationTests(unittest.TestCase):
    def test_byte_identical_regeneration_and_golden(self):
        self.assertEqual(set(GOLDEN), set(FAMILIES))
        for family in FAMILIES:
            with self.subTest(family=family):
                first = generate(specification(family))
                second = generate(specification(family))
                self.assertEqual(first, second)
                manifest, graph, trace = first
                self.assertEqual((sha256(graph), sha256(trace), manifest["final_graph_sha256"]), GOLDEN[family])
                self.assertEqual(canonical_json(manifest), canonical_json(second[0]))
                self.assertEqual(verify(*first)["status"], "verified")

    def test_family_invariants(self):
        for family, (_, vertices, edges) in FAMILIES.items():
            graph = generate_graph(specification(family))
            self.assertEqual((graph.vertices, len(graph.edges)), (vertices, edges))
            pairs = [(u, v) for u, v, _ in graph.edges]
            self.assertEqual(pairs, sorted(set(pairs)))
            self.assertTrue(all(0 <= u < vertices and 0 <= v < vertices and u != v for u, v in pairs))
            self.assertTrue(all(8 <= weight <= 32 for _, _, weight in graph.edges))
            self.assertEqual(parse_graph(graph_bytes(graph)), graph)
        spec = specification("grid")
        spec["graph"]["bidirectional"] = False
        self.assertEqual([(u, v) for u, v, _ in generate_graph(spec).edges],
                         [(0, 1), (0, 3), (1, 2), (1, 4), (2, 5), (3, 4), (4, 5)])
        layered = generate_graph(specification("layered"))
        self.assertTrue(all(v // 3 == u // 3 + 1 for u, v, _ in layered.edges))
        for u in range(6):
            self.assertEqual(sum(start == u for start, _, _ in layered.edges), 2)
        disconnected = generate_graph(specification("disconnected"))
        self.assertEqual(reachable_vertices(disconnected, 0), {0, 1, 2})
        self.assertTrue(all(6 not in (u, v) and 7 not in (u, v) for u, v, _ in disconnected.edges))

    def test_small_parameter_sweep(self):
        configs = []
        for vertices in range(1, 9):
            configs.append({"family": "chain", "vertices": vertices})
            for edges in sorted({0, vertices * (vertices - 1) // 2, vertices * (vertices - 1)}):
                configs.append({"family": "sparse_random", "vertices": vertices, "edges": edges})
        for rows in (1, 2, 3):
            for columns in (1, 2, 3):
                for bidirectional in (False, True):
                    configs.append({"family": "grid", "rows": rows, "columns": columns,
                                    "bidirectional": bidirectional})
        for layers in (1, 2, 3):
            for width in (1, 2, 3):
                for fanout in sorted({0, 1, width}):
                    configs.append({"family": "layered", "layers": layers, "width": width, "fanout": fanout})
        configs.append({"family": "disconnected", "component_sizes": [1, 1], "isolated_vertices": 1})
        for index, config in enumerate(configs):
            with self.subTest(config=config):
                spec = specification()
                spec["graph"] = config
                spec["weights"] = {"kind": "positive_uniform", "min": 16, "max": 16}
                spec["source"] = {"kind": "random"}
                spec["seeds"] = {name: str(index + offset) for offset, name in enumerate(spec["seeds"])}
                graph = generate_graph(spec)
                spec["trace"].update(count=6 if graph.edges else 0, schedule=["strict", "equal", "repeat"])
                manifest, data, trace = generate(spec)
                self.assertEqual(verify(manifest, data, trace)["status"], "verified")

    def test_separate_seed_streams(self):
        spec = specification("sparse_random")
        baseline = generate(spec)
        for name in ("graph", "weight", "trace"):
            changed = deepcopy(spec)
            changed["seeds"][name] = "12345"
            other = generate(changed)
            if name == "trace":
                self.assertEqual(baseline[1], other[1])
                self.assertNotEqual(parse_trace(baseline[2]).updates, parse_trace(other[2]).updates)
            else:
                self.assertNotEqual(baseline[1], other[1])
            if name == "weight":
                self.assertEqual([(u, v) for u, v, _ in parse_graph(baseline[1]).edges],
                                 [(u, v) for u, v, _ in parse_graph(other[1]).edges])
        spec["source"] = {"kind": "random"}
        a = generate(spec)
        spec["seeds"]["source"] = "99"
        b = generate(spec)
        self.assertEqual(a[1], b[1])
        self.assertNotEqual(a[0]["source"], b[0]["source"])
        for seed in ("0", str(UINT64_MAX)):
            spec["seeds"] = {name: seed for name in spec["seeds"]}
            self.assertEqual(verify(*generate(spec))["status"], "verified")

    def test_weight_distributions(self):
        spec = specification("sparse_random")
        spec["graph"].update(vertices=16, edges=100)
        spec["trace"]["count"] = 0
        configs = [
            {"kind": "positive_uniform", "min": UINT32_MAX, "max": UINT32_MAX},
            {"kind": "zero_inclusive", "max": 32, "zero_numerator": 1, "denominator": 2},
            {"kind": "zero_inclusive", "max": 1, "zero_numerator": 1, "denominator": 1},
            {"kind": "bimodal", "low_min": 0, "low_max": 2, "high_min": UINT32_MAX - 2,
             "high_max": UINT32_MAX, "high_numerator": 1, "denominator": 2}]
        for config in configs:
            spec["weights"] = config
            values = [weight for _, _, weight in generate_graph(spec).edges]
            self.assertTrue(all(type(value) is int and 0 <= value <= UINT32_MAX for value in values))
            if config["kind"] == "bimodal":
                self.assertTrue(any(value <= 2 for value in values))
                self.assertTrue(any(value >= UINT32_MAX - 2 for value in values))
                self.assertTrue(all(value <= 2 or value >= UINT32_MAX - 2 for value in values))
            elif config.get("zero_numerator") == config.get("denominator") == 1:
                self.assertEqual(set(values), {0})
                spec["trace"].update(count=3, schedule=["equal"])
            elif config["kind"] == "zero_inclusive":
                self.assertIn(0, values)
                self.assertTrue(any(value > 0 for value in values))
            else:
                self.assertEqual(set(values), {UINT32_MAX})
            self.assertEqual(verify(*generate(spec))["status"], "verified")
            spec["trace"]["count"] = 0

    def test_strict_equal_repeated_and_independent_final_state(self):
        manifest, data, trace_data = generate(specification())
        graph, trace = parse_graph(data), parse_trace(trace_data)
        self.assertEqual(data, b"6 5\n0 1 18\n1 2 9\n2 3 9\n3 4 19\n4 5 32\n")
        self.assertEqual(trace.updates, ((0, 3, 4, 19, 18), (1, 3, 4, 18, 17), (2, 2, 3, 9, 9),
                                         (3, 1, 2, 9, 8), (4, 1, 2, 8, 7), (5, 1, 2, 7, 7),
                                         (6, 4, 5, 32, 31), (7, 4, 5, 31, 30), (8, 0, 1, 18, 18)))
        weights = {(u, v): weight for u, v, weight in graph.edges}
        for index, u, v, old, new in trace.updates:
            self.assertEqual(old, weights[u, v])
            if index % 3 == 2:
                self.assertEqual(new, old)
            else:
                self.assertEqual(new, old - 1)
            if index % 3 == 1:
                self.assertEqual((u, v), trace.updates[index - 1][1:3])
            weights[u, v] = new
        expected = Graph(graph.vertices, tuple((u, v, weights[u, v]) for u, v, _ in graph.edges))
        self.assertEqual(replay(graph, trace), expected)
        self.assertEqual(sha256(graph_bytes(expected)), manifest["final_graph_sha256"])
        self.assertEqual(graph_bytes(graph), data)  # Generation/replay do not mutate input.
        manual = Graph(3, ((0, 1, 9), (2, 2, 0)))
        manual_trace = Trace(sha256(graph_bytes(manual)), ("0",) * 4, 0,
                             ((0, 0, 1, 9, 7), (1, 0, 1, 7, 7), (2, 0, 1, 7, 0)))
        self.assertEqual(graph_bytes(replay(manual, manual_trace)), b"3 2\n0 1 0\n2 2 0\n")

    def test_unreachable_updates(self):
        spec = specification("disconnected")
        spec["trace"].update(count=6, schedule=["unreachable", "repeat", "equal"])
        manifest, data, trace_data = generate(spec)
        reached = reachable_vertices(parse_graph(data), manifest["source"])
        for index, u, _, old, new in parse_trace(trace_data).updates:
            if index % 3 != 2:
                self.assertNotIn(u, reached)
                self.assertLess(new, old)
        self.assertEqual(verify(manifest, data, trace_data)["status"], "verified")
        spec = specification()
        spec["trace"].update(count=1, schedule=["unreachable"])
        with self.assertRaisesRegex(ValueError, "update 0.*exhausted"):
            generate(spec)

    def test_budget_exhaustion_and_empty_edges(self):
        spec = specification()
        spec["graph"]["vertices"] = 2
        spec["weights"] = {"kind": "positive_uniform", "min": 1, "max": 1}
        spec["trace"].update(count=1, schedule=["strict"])
        manifest, graph, trace = generate(spec)
        self.assertEqual(parse_trace(trace).updates, ((0, 0, 1, 1, 0),))
        self.assertEqual(manifest["final_graph_sha256"], sha256(b"2 1\n0 1 0\n"))
        spec["trace"]["count"] = 2
        with self.assertRaisesRegex(ValueError, "update 1.*exhausted"):
            generate(spec)
        spec["trace"]["schedule"] = ["strict", "repeat"]
        with self.assertRaisesRegex(ValueError, "update 1.*repeat requires"):
            generate(spec)
        spec["trace"].update(count=1, schedule=["repeat"])
        with self.assertRaisesRegex(ValueError, "previous edge"):
            generate(spec)
        spec["graph"]["vertices"] = 1
        for schedule in (["strict"], ["equal"], ["unreachable"]):
            spec["trace"]["schedule"] = schedule
            with self.assertRaises(ValueError):
                generate(spec)
        spec["trace"]["count"] = 0
        self.assertEqual(verify(*generate(spec))["counts"], {"vertices": 1, "edges": 0, "updates": 0})
        spec["graph"] = {"family": "sparse_random", "vertices": 1, "edges": 0}
        self.assertEqual(generate_graph(spec), Graph(1, ()))
        self.assertEqual(parse_graph(b"0 0\n"), Graph(0, ()))


class RejectionTests(unittest.TestCase):
    def test_invalid_specifications(self):
        mutations = [
            ("schema_version", 2), ("schema_version", True), ("schema_version", 1.0),
            ("workload_id", "../escape"), ("split", "unknown"), ("seeds", {}),
            ("source", {"kind": "explicit", "vertex": 6}), ("source", {"kind": "random", "extra": 0}),
            ("graph", {"family": "chain", "vertices": MAX_VERTICES + 1}),
            ("graph", {"family": "chain", "vertices": 0}),
            ("graph", {"family": "chain", "vertices": True}),
            ("graph", {"family": "chain", "vertices": 2.0}),
            ("graph", {"family": "chain", "vertices": 2, "edges": 1}),
            ("graph", {"family": "sparse_random", "vertices": 3, "edges": 7}),
            ("graph", {"family": "sparse_random", "vertices": 1000, "edges": MAX_EDGES + 1}),
            ("graph", {"family": "grid", "rows": MAX_VERTICES, "columns": MAX_VERTICES, "bidirectional": True}),
            ("graph", {"family": "grid", "rows": 2, "columns": 2, "bidirectional": 1}),
            ("graph", {"family": "layered", "layers": 2, "width": 3, "fanout": 4}),
            ("graph", {"family": "layered", "layers": 1000, "width": 1000, "fanout": 1000}),
            ("graph", {"family": "layered", "layers": 2, "width": 1000, "fanout": 1000}),
            ("graph", {"family": "disconnected", "component_sizes": [3], "isolated_vertices": 1}),
            ("graph", {"family": "disconnected", "component_sizes": [0, 3], "isolated_vertices": 1}),
            ("graph", {"family": "dense", "vertices": 3}),
            ("weights", {"kind": "positive_uniform", "min": 0, "max": 2}),
            ("weights", {"kind": "positive_uniform", "min": 2, "max": 1}),
            ("weights", {"kind": "positive_uniform", "min": 1, "max": UINT32_MAX + 1}),
            ("weights", {"kind": "zero_inclusive", "max": 1, "zero_numerator": 1, "denominator": 0}),
            ("weights", {"kind": "zero_inclusive", "max": 1, "zero_numerator": 3, "denominator": 2}),
            ("weights", {"kind": "bimodal", "low_min": 1, "low_max": 2, "high_min": 2,
                         "high_max": 3, "high_numerator": 1, "denominator": 2}),
            ("trace", {"count": MAX_UPDATES + 1, "schedule": ["equal"], "max_decrement": 1}),
            ("trace", {"count": 1, "schedule": [], "max_decrement": 1}),
            ("trace", {"count": 1, "schedule": ["broad"], "max_decrement": 1}),
            ("trace", {"count": 1, "schedule": ["strict"], "max_decrement": 0})]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                spec = specification()
                spec[key] = value
                with self.assertRaises(ValueError):
                    generate(spec)
        for seed in (-1, 1, "-1", "+1", "01", "1.0", str(UINT64_MAX + 1), "1" * 100):
            spec = specification()
            spec["seeds"]["graph"] = seed
            with self.assertRaises(ValueError):
                validate_spec(spec)

    def test_json_rejects_duplicates_constants_and_garbage(self):
        for data in (b'{"a":1,"a":2}', b'{"nested":{"a":1,"a":2}}', b'{"a":NaN}',
                     b'{"a":Infinity}', b'{} trailing', b'\xff', b'{}' + b' ' * 65536):
            with self.assertRaises(ValueError):
                parse_json(data)

    def test_malformed_canonical_graphs(self):
        for data in (b"", b"2 0", b"2 0\n\n", b"2 0\r\n", b"2 1\n0 1 2\nextra\n",
                     b"2 2\n0 1 1\n", b"2 2\n0 1 1\n0 1 2\n", b"2 2\n1 0 1\n0 1 2\n",
                     b"2 1\n0 2 1\n", b"2 1\n0 1 4294967296\n", b"2 1\n0 1 -1\n",
                     b"2 1\n0 1 +1\n", b"2 1\n0 1 1.0\n", b"02 0\n", b"2  0\n",
                     b"2 1\n0 1 1 extra\n", b"0 1\n0 0 0\n", b"100001 0\n",
                     b"1 500001\n", b"2 1\n0 1 1\x00\n", b"\xef\xbb\xbf2 0\n"):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    parse_graph(data)

    def test_malformed_trace_header_and_records(self):
        _, _, data = generate(specification())
        mutations = [
            data.replace(b"TRACE 1", b"TRACE 2"), data.replace(b"trace-v1", b"trace-v2"),
            data.replace(b"graph-v1", b"graph-v2"), data.replace(b"splitmix64-v1", b"other-v1"),
            data.replace(b"graph_seed 1", b"graph_seed 01"), data.replace(b"source 0", b"source -1"),
            data.replace(b"updates 9", b"updates 10"), data.replace(b"updates 9", b"updates 100001"),
            data + b"0 0 1 2 1\n", data + b"\n", data[:-1], data.replace(b"\n", b"\r\n"),
            b"DYNAGRAPH_TRACE 1\n", data.replace(b"graph_sha256 ", b"unknown ", 1)]
        lines = data.decode("ascii").splitlines()
        for record in ("1 0 1 9 8", "0 100000 1 9 8", "0 0 1 4294967296 8",
                       "0 0 1 9 8 extra", "0 0 1 9", "0 0 1 9 8.0"):
            changed = lines.copy()
            changed[11] = record
            mutations.append(("\n".join(changed) + "\n").encode("ascii"))
        for data in mutations:
            with self.subTest(data=data[:80]):
                with self.assertRaises(ValueError):
                    parse_trace(data)

    def test_replay_rejects_identity_endpoints_old_and_increases(self):
        _, data, trace_data = generate(specification())
        graph, trace = parse_graph(data), parse_trace(trace_data)
        old = graph.edges[0][2]
        for changed in (
                replace(trace, graph_sha256="0" * 64), replace(trace, source=graph.vertices),
                replace(trace, updates=((0, 0, 1, old + 1, old),)),
                replace(trace, updates=((0, 0, 1, old, old + 1),)),
                replace(trace, updates=((0, 0, 5, old, old - 1),)),
                replace(trace, updates=((0, 6, 1, old, old - 1),))):
            with self.assertRaises(ValueError):
                replay(graph, changed)

    def test_manifest_and_hash_mismatches(self):
        manifest, graph, trace = generate(specification())
        mutations = [
            ("schema_version", 2), ("schema_version", True), ("generator_versions", {}),
            ("source", 1), ("source", True), ("counts", {"vertices": 6, "edges": 5, "updates": 8}),
            ("counts", {"vertices": 6.0, "edges": 5, "updates": 9}),
            ("final_graph_sha256", "0" * 64), ("final_graph_sha256", "a" * 63),
            ("split", "test"), ("workload_id", "other"), ("configuration", {})]
        for key, value in mutations:
            changed = deepcopy(manifest)
            changed[key] = value
            with self.assertRaises(ValueError):
                verify(changed, graph, trace)
        for name in ("graph", "trace"):
            for path in ("../" + name + ".txt", "/tmp/" + name + ".txt", "other.txt"):
                changed = deepcopy(manifest)
                changed["artifacts"][name]["path"] = path
                with self.assertRaises(ValueError):
                    verify(changed, graph, trace)
        with self.assertRaisesRegex(ValueError, "graph SHA-256 mismatch"):
            verify(manifest, graph + b"\n", trace)
        with self.assertRaisesRegex(ValueError, "trace SHA-256 mismatch"):
            verify(manifest, graph, trace + b"\n")
        changed = deepcopy(manifest)
        changed["configuration"]["seeds"]["trace"] = "5"
        with self.assertRaisesRegex(ValueError, "seeds disagree"):
            verify(changed, graph, trace)
        changed = deepcopy(manifest)
        changed["configuration"]["graph"]["vertices"] = 7
        with self.assertRaisesRegex(ValueError, "do not reproduce"):
            verify(changed, graph, trace)

    def test_rehashed_invalid_trace_still_rejected(self):
        manifest, graph_data, trace_data = generate(specification())
        trace = parse_trace(trace_data)
        record = trace.updates[0]
        for bad in ((record[0], record[1], record[2], record[3] + 1, record[4]),
                    (record[0], record[1], record[2], record[3], record[3] + 1)):
            changed = deepcopy(manifest)
            data = trace_bytes(replace(trace, updates=(bad,) + trace.updates[1:]))
            changed["artifacts"]["trace"]["sha256"] = sha256(data)
            with self.assertRaisesRegex(ValueError, "old weight mismatch|weight increase"):
                verify(changed, graph_data, data)

    def test_rehashed_identity_mismatch_still_rejected(self):
        manifest, graph_data, trace_data = generate(specification())
        trace = replace(parse_trace(trace_data), graph_sha256="0" * 64)
        changed = deepcopy(manifest)
        data = trace_bytes(trace)
        changed["artifacts"]["trace"]["sha256"] = sha256(data)
        with self.assertRaisesRegex(ValueError, "graph fingerprint mismatch"):
            verify(changed, graph_data, data)
        changed = deepcopy(manifest)
        changed["counts"]["vertices"] = 7
        with self.assertRaisesRegex(ValueError, "counts disagree"):
            verify(changed, graph_data, trace_data)


class ArtifactCLITests(unittest.TestCase):
    def command(self, *args, hash_seed="0"):
        import os
        environment = dict(os.environ, PYTHONHASHSEED=hash_seed, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(ROOT / "benchmarks/python/generate.py"), *map(str, args)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment, check=False)

    def test_bundle_roundtrip_hash_seeds_paths_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec = root / "spec with spaces.json"
            spec.write_bytes(canonical_json(specification("layered")))
            outputs = []
            for seed in ("0", "1", "12345"):
                output = root / ("bundle " + seed)
                result = self.command("generate", "--spec", spec, "--output", output, hash_seed=seed)
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                outputs.append(tuple((output / name).read_bytes() for name in ("graph.txt", "trace.txt", "manifest.json")))
                result = self.command("verify", "--manifest", output / "manifest.json")
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                self.assertEqual(json.loads(result.stdout)["status"], "verified")
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[1], outputs[2])
            previous = outputs[0]
            result = self.command("generate", "--spec", spec, "--output", root / "bundle 0")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            self.assertTrue(result.stderr)
            self.assertEqual(previous, tuple((root / "bundle 0" / name).read_bytes()
                                            for name in ("graph.txt", "trace.txt", "manifest.json")))
            renamed = root / "bundle 1" / "manifest.json"
            self.assertEqual(verify_bundle(renamed)["status"], "verified")

    def test_cli_errors_are_nonzero_without_success_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = write_bundle(specification(), root / "bundle")
            for name in ("graph", "trace"):
                artifact = path.parent / (name + ".txt")
                original = artifact.read_bytes()
                artifact.write_bytes(original + b"\n")
                result = self.command("verify", "--manifest", path)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"SHA-256 mismatch", result.stderr)
                artifact.write_bytes(original)
            path.write_bytes(b'{"schema_version":2}')
            result = self.command("verify", "--manifest", path)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            invalid = specification()
            invalid["trace"]["schedule"] = ["repeat"]
            spec_path = root / "bad.json"
            spec_path.write_bytes(canonical_json(invalid))
            output = root / "never-created"
            result = self.command("generate", "--spec", spec_path, "--output", output)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertIn(b"update 0", result.stderr)
            spec_path.write_bytes(b"{" * 65537)
            result = self.command("generate", "--spec", spec_path, "--output", output)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"exceeds", result.stderr)
            with self.assertRaises(ValueError):
                read_bounded(spec_path, 10)

    def test_missing_artifact_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = write_bundle(specification(), root / "bundle")
            graph = manifest.parent / "graph.txt"
            moved = root / "saved.txt"
            graph.rename(moved)
            result = self.command("verify", "--manifest", manifest)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            graph.symlink_to(moved)
            result = self.command("verify", "--manifest", manifest)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"symlinks", result.stderr)


if __name__ == "__main__":
    unittest.main()
