"""Fresh-process runtime calibration and deterministic concurrency reproduction."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

OPTIONAL = '--optional' in sys.argv
if OPTIONAL:
    sys.argv.remove('--optional')


class ConcurrencyRuntimeTests(unittest.TestCase):
    def invoke(self, *args, limit='2', dynamic='FALSE', levels='1', expected=0):
        env = dict(os.environ)
        for key in ('OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'OMP_DYNAMIC', 'OMP_MAX_ACTIVE_LEVELS',
                    'OMP_NESTED', 'OMP_SCHEDULE', 'OMP_PROC_BIND', 'OMP_PLACES'):
            env.pop(key, None)
        env.update(OMP_NUM_THREADS='2', OMP_THREAD_LIMIT=limit, OMP_DYNAMIC=dynamic,
                   OMP_MAX_ACTIVE_LEVELS=levels)
        start = time.monotonic()
        launch = dict(command=[CLI, *args], timeout_seconds=30,
                      runtime=dict(limit=limit, dynamic=dynamic, levels=levels))
        print(json.dumps(dict(type='subprocess_start', **launch)), flush=True)
        # A timeout raises and fails the test. There are no retries.
        try:
            result = subprocess.run([CLI, *args], capture_output=True, text=True, timeout=30, env=env)
        except subprocess.TimeoutExpired as error:
            print(json.dumps(dict(type='subprocess_timeout', **launch,
                stdout=str(error.stdout), stderr=str(error.stderr),
                actual_workers='unavailable unless present in partial output')), flush=True)
            raise
        records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        observations = [r for r in records if r['type'] == 'observation']
        for observation in observations:
            print(json.dumps(observation, sort_keys=True), flush=True)
        print(json.dumps(dict(command=[CLI, *args], exit_code=result.returncode,
            seconds=round(time.monotonic() - start, 6), runtime=dict(limit=limit, dynamic=dynamic, levels=levels),
            observed_teams=sorted({r['actual_workers'] for r in observations if r['actual_workers'] is not None}),
            summaries=[r for r in records if r['type'] != 'observation'])), flush=True)
        self.assertEqual(result.returncode, expected, result.stderr + '\n' + result.stdout)
        for r in observations:
            self.assertEqual(r['version'], 'concurrency-validation-v1')
            self.assertEqual(r['environment']['OMP_THREAD_LIMIT'], limit)
            self.assertEqual(r['environment']['OMP_DYNAMIC'], dynamic)
            if not r['metrics']:
                self.assertIsNone(r['actual_workers'])
                self.assertIsNone(r['per_thread'])
                self.assertIsNone(r['cas_retries'])
            if r['actual_workers'] is not None:
                self.assertGreaterEqual(r['actual_workers'], 1)
                # Explicit requests override NUM_THREADS. Do not impose a
                # process-global team sum across independent host callers.
                if r['requested_workers']:
                    self.assertLessEqual(r['actual_workers'], r['requested_workers'])
            if r['per_thread'] is not None:
                self.assertEqual(len(r['per_thread']), r['actual_workers'])
                self.assertEqual(r['work_participants'], sum(t['edges'] > 0 for t in r['per_thread']))
                self.assertEqual(r['successes'], sum(t['successes'] for t in r['per_thread']))
                self.assertEqual(r['cas_retries'], sum(t['cas_retries'] for t in r['per_thread']))
        return records, observations

    def summary(self, records, kind):
        return next(r for r in records if r['type'] == kind)

    def test_reduced_matrix_and_observation_schema(self):
        records, observations = self.invoke('--suite', 'direct', '--case', '3')
        self.assertEqual(self.summary(records, 'direct_summary')['queries'], 36)
        self.assertEqual(self.summary(records, 'direct_summary')['generation_fingerprint'], 13210075048839355636)
        self.assertEqual(len(observations), 36)
        actual = {(r['delta'], r['requested_workers'], r['metrics'], r['repetition']) for r in observations}
        expected = {(d, w, m, r) for d in (1, 16, 2**64 - 1) for w in (1, 2, 4)
                    for m in (False, True) for r in (0, 1)}
        self.assertEqual(actual, expected)

    def test_exact_selected_case_reproduction(self):
        for profile, case, source in (('fast', '4', '0'), ('stress', '7', '0'), ('extended', '15', '17')):
            fingerprints = []
            for workers, measured in (('1', '0'), ('2', '1'), ('2', '1'), ('4', '0')):
                records, observations = self.invoke('--suite', 'direct', '--profile', profile,
                    '--seed', '4294967295', '--case', case, '--source', source, '--workers', workers,
                    '--metrics', measured, '--delta', '16', '--repeat', '1')
                summary = self.summary(records, 'direct_summary')
                self.assertEqual(summary['queries'], 1)
                self.assertEqual(len(observations), 1)
                self.assertEqual(observations[0]['source'], int(source))
                self.assertEqual(observations[0]['case'], int(case))
                fingerprints.append((summary['generation_fingerprint'], summary['state_fingerprint']))
            self.assertEqual(len(set(fingerprints)), 1)

    def test_fresh_runtime_configurations_and_default_request(self):
        for limit, dynamic in (('2', 'FALSE'), ('1', 'FALSE'), ('2', 'TRUE')):
            records, observations = self.invoke('--suite', 'runtime', limit=limit, dynamic=dynamic)
            self.assertEqual(self.summary(records, 'runtime_summary')['queries'], 6)
            self.assertEqual({r['requested_workers'] for r in observations}, {0, 2, 4})
            self.assertTrue(all(r['actual_workers'] <= int(limit) for r in observations))
            if limit == '1':
                self.assertTrue(all(r['actual_workers'] == 1 for r in observations))

    def test_nested_max_active_levels_one(self):
        records, observations = self.invoke('--suite', 'runtime', '--runtime', 'nested')
        summary = self.summary(records, 'runtime_summary')
        self.assertEqual(summary['queries'], summary['outer_team'])
        self.assertEqual(summary['max_active_levels'], 1)
        self.assertIn(summary['outer_team'], (1, 2))
        if summary['outer_team'] == 2:
            self.assertTrue(all(r['actual_workers'] == 1 for r in observations))

    def test_independent_and_serialized_clients(self):
        records, observations = self.invoke('--suite', 'clients')
        summary = self.summary(records, 'client_summary')
        self.assertEqual(summary['immutable_queries'], 8)
        self.assertEqual(summary['separate_engine_updates'], 32)
        self.assertEqual(summary['serialized_updates'], 8)
        self.assertEqual(summary['state_comparisons'], 51)
        for name, count in (('immutable_clients', 8), ('separate_engines', 32), ('serialized_engine', 8)):
            selected = [r for r in observations if r['policy'] == name]
            self.assertEqual(len(selected), count)
            self.assertEqual({r['client'] for r in selected}, {0, 1})

    def test_seeded_trace_reproduction(self):
        records, observations = self.invoke('--suite', 'traces', '--seed', '4294967295',
            '--case', '31', '--source', '0', '--workers', '4', '--delta', '16')
        self.assertEqual(self.summary(records, 'trace_summary'),
                         dict(type='trace_summary', traces=1, updates=16, state_comparisons=68))
        self.assertEqual(len(observations), 65)
        self.assertEqual({r['policy'] for r in observations},
                         {'always_delta', 'heuristic', 'rotating_override', 'standalone_delta'})

    def test_invalid_cli(self):
        for args in (('--suite', 'bad'), ('--suite', 'direct', '--case', '8'),
                     ('--suite', 'direct', '--profile', 'extended', '--case', '16'),
                     ('--suite', 'direct', '--workers', '3'), ('--suite', 'direct', '--repeat', '2'),
                     ('--suite', 'direct', '--delta', '0'), ('--suite', 'direct', '--delta', str(2**64)),
                     ('--suite', 'direct', '--metrics', '2'), ('--source', '0'),
                     ('--suite', 'direct', '--case', '0', '--source', '4095'),
                     ('--seed', '01'), ('--seed', '-1'), ('--seed', '4294967296'),
                     ('--seed', '1', '--seed', '2'), ('--unknown', '1'), ('--case',),
                     ('--suite', 'traces', '--case', '1'), ('--suite', 'traces', '--workers', '0'),
                     ('--suite', 'traces', '--metrics', '0'), ('--runtime', 'nested')):
            with self.subTest(args=args):
                self.invoke(*args, expected=2)

    @unittest.skipUnless(OPTIONAL, 'active nesting is opt-in')
    def test_optional_active_nesting(self):
        records, observations = self.invoke('--suite', 'runtime', '--runtime', 'nested', limit='4', levels='2')
        self.assertEqual(self.summary(records, 'runtime_summary')['max_active_levels'], 2)
        if not any(r['outer_team'] == 2 and r['actual_workers'] == 2 for r in observations):
            self.skipTest('active inner team was not achieved; observations retained')

    @unittest.skipUnless(OPTIONAL, 'genuine four-worker execution is opt-in')
    def test_optional_four_workers(self):
        _, observations = self.invoke('--suite', 'runtime', '--runtime', 'four', limit='4')
        self.assertEqual(len(observations), 2)
        if not all(r['actual_workers'] == 4 for r in observations):
            self.skipTest('four actual workers unavailable; correctness checked at observed team size')


if __name__ == '__main__':
    CLI = str(Path(sys.argv.pop(1)).resolve())
    unittest.main()
