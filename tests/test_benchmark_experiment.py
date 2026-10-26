"""Raw timing contracts and experiment validity; never compares runtimes."""
from collections import Counter
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_workloads import specification, generate, parse_graph, parse_trace, graph_bytes
from workloads import Graph, Trace, trace_bytes, sha256, canonical_json
from artifacts import write_bundle
from experiment_records import (POLICIES, configuration, loads, schedule, read_jsonl, validate_worker,
                                validate_dataset, uint, IDENTITIES)
from run import run_experiment, execute, ExperimentError
import run as orchestration


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = write_bundle(specification(), self.root / 'bundle')
        self.config = dict(schema_version=1, manifest='bundle/manifest.json', timing_mode='full-trace',
                           blocks='4', order_seed='18446744073709551615', delta='16', threads='2',
                           no_effect='shared_fast_path', timeout_seconds='20', warmups='1')
        self.config_path = self.root / 'config.json'
        self.config_path.write_bytes(canonical_json(self.config))

    def experiment(self, name='output'):
        self.config_path.write_bytes(canonical_json(self.config))
        directory = self.root / name
        result = run_experiment(self.config_path, CLI, directory)
        self.assertEqual(result, {'schema_version':1,'status':'complete','trials':'16'})
        return directory

    def test_schedule_reproducible_balanced_and_pinned(self):
        for seed in (0, 1, 18446744073709551615):
            orders = schedule(8, seed)
            self.assertEqual(orders, schedule(8, seed))
            for group in (orders[:4], orders[4:]):
                for policy in POLICIES:
                    self.assertEqual(sorted(row.index(policy) for row in group), [0,1,2,3])
                pairs = Counter((a,b) for row in group for a,b in zip(row,row[1:]))
                self.assertEqual(pairs, Counter({(a,b):1 for a in POLICIES for b in POLICIES if a != b}))
        self.assertEqual(schedule(4,0), [['incremental','delta-stepping','heuristic','dijkstra'],
                                       ['delta-stepping','dijkstra','incremental','heuristic'],
                                       ['dijkstra','heuristic','delta-stepping','incremental'],
                                       ['heuristic','incremental','dijkstra','delta-stepping']])
        for blocks in (0,1,3,5,404):
            with self.assertRaises(ValueError):
                schedule(blocks,0)

    def test_two_end_to_end_modes_and_completion_evidence(self):
        for mode in ('full-trace','per-update'):
            self.config['timing_mode'] = mode
            directory = self.experiment(mode)
            self.assertEqual(validate_dataset(directory/'records.jsonl')['status'], 'complete')
            records = read_jsonl((directory/'records.jsonl').read_bytes())
            self.assertEqual(sum(item['record_type'] == 'trial_end' for item in records),16)
            self.assertEqual(sum(item['record_type'] == 'warmup_end' for item in records),16)
            self.assertEqual(sum(item['record_type'] == 'update_latency' for item in records),16*9 if mode == 'per-update' else 0)
            self.assertEqual(sum(item['record_type'] == 'trial_measurement' for item in records),16 if mode == 'full-trace' else 0)
            original = (directory/'records.jsonl').read_bytes()
            for invalid in (original[:-1], b'\n'.join(original.splitlines()[:-1])+b'\n', original.replace(b'"elapsed_ns":"', b'"elapsed_ns":"0',1)):
                (directory/'records.jsonl').write_bytes(invalid)
                with self.assertRaises((ValueError,IndexError,KeyError)):
                    validate_dataset(directory/'records.jsonl')
            (directory/'records.jsonl').write_bytes(original)
            for file in ('runner','workload/graph.txt','workload/trace.txt','trial-0.exit.json','preflight-dijkstra.stdout'):
                path = directory/file
                saved = path.read_bytes()
                path.write_bytes(b'{}' if file.endswith('.exit.json') else saved + b'\n')
                with self.assertRaises(ValueError):
                    validate_dataset(directory/'records.jsonl')
                path.write_bytes(saved)
            with self.assertRaises(FileExistsError):
                self.experiment(mode)

    def test_direct_worker_all_policies_modes_no_effect_and_verify_regression(self):
        graph = Graph(5, ((0,1,8),(1,0,0),(2,3,7),(3,2,0)))
        trace = Trace(sha256(graph_bytes(graph)), ('0',)*4, 0,
                      ((0,0,1,8,7),(1,0,1,7,7),(2,0,1,7,0),(3,2,3,7,0)))
        (self.root/'graph.txt').write_bytes(graph_bytes(graph))
        (self.root/'trace.txt').write_bytes(trace_bytes(trace))
        base = ['--graph',str(self.root/'graph.txt'),'--trace',str(self.root/'trace.txt'),
                '--source','0','--delta','16','--threads','2']
        for policy in POLICIES:
            for no_effect in ('shared_fast_path','execute_selected'):
                args = [*base,'--policy',policy,'--no-effect',no_effect]
                before = subprocess.run([CLI,'verify',*args],capture_output=True,check=True).stdout
                response = loads(before)
                self.assertEqual(response['updates_verified'],4)
                self.assertEqual(response['reference_recomputations'],5)
                self.assertEqual(response['final_weights'],[0,0,0,0])
                for mode in ('full-trace','per-update'):
                    process = subprocess.run([CLI,'time',*args,'--timing-mode',mode,'--warmups','2',
                                              *sum((['--'+key.replace('_','-'),'a'*64] for key in IDENTITIES),[])],
                                             capture_output=True,check=True)
                    records = read_jsonl(process.stdout)
                    config = dict(self.config,timing_mode=mode,no_effect=no_effect,warmups='2')
                    expected = dict(records[0],source='0')
                    validate_worker(records,expected,config,4,5,4)
                    self.assertEqual(records[0]['external_integrity'],'unconfirmed')
                    changed_config = dict(config,delta='17')
                    with self.assertRaisesRegex(ValueError,'configuration'):
                        validate_worker(records,expected,changed_config,4,5,4)
                    changed = [dict(item) for item in records]
                    changed[-1]['configuration_sha256'] = 'b'*64
                    with self.assertRaisesRegex(ValueError,'identity'):
                        validate_worker(changed,expected,config,4,5,4)
                self.assertEqual(subprocess.run([CLI,'verify',*args],capture_output=True,check=True).stdout,before)
        # Ledger failure is found before any warmup or measurement.
        changed = replace(trace,updates=((0,0,1,9,7),)+trace.updates[1:])
        (self.root/'trace.txt').write_bytes(trace_bytes(changed))
        failure = subprocess.run([CLI,'time',*args,'--timing-mode','full-trace'],capture_output=True)
        self.assertEqual(failure.returncode,2)
        self.assertNotIn(b'trial_measurement',failure.stdout)
        self.assertIn(b'"success":false',failure.stdout)
        empty = replace(trace,updates=())
        (self.root/'trace.txt').write_bytes(trace_bytes(empty))
        self.assertEqual(subprocess.run([CLI,'time',*args,'--timing-mode','per-update'],capture_output=True).returncode,2)

    def test_failure_stop_no_retry_and_integrity_change(self):
        real_execute = orchestration.execute
        for category in ('worker_failure','timeout','interrupted','artifact_changed','protocol_failure','preflight_verification_failure'):
            calls = []
            def injected(command, stem, timeout):
                calls.append(command[1])
                if category == 'preflight_verification_failure':
                    raise ExperimentError(category,'injected preflight')
                if command[1] == 'time':
                    if category == 'artifact_changed':
                        result = real_execute(command,stem,timeout)
                        graph = stem.parent/'workload/graph.txt'
                        graph.write_bytes(graph.read_bytes()+b'\n')
                        return result
                    if category == 'protocol_failure':
                        return b'{"schema":'
                    raise ExperimentError(category,'injected trial')
                return real_execute(command,stem,timeout)
            output = self.root/category
            with patch('run.execute',injected):
                with self.assertRaises(ExperimentError):
                    run_experiment(self.config_path,CLI,output)
            records = read_jsonl((output/'records.jsonl').read_bytes())
            self.assertEqual(records[-1]['record_type'],'run_end')
            self.assertFalse(records[-1]['success'])
            self.assertLessEqual(calls.count('time'),1)
            with self.assertRaises((ValueError,IndexError)):
                validate_dataset(output/'records.jsonl')

    def test_real_worker_exit_and_timeout_evidence(self):
        for name, command, timeout in (('exit',[sys.executable,'-c','raise SystemExit(7)'],2),
                                        ('timeout',[sys.executable,'-c','import time; time.sleep(2)'],0.02)):
            with self.assertRaises(ExperimentError):
                execute(command,self.root/name,timeout)
            evidence=loads((self.root/(name+'.exit.json')).read_bytes())
            self.assertNotEqual(evidence['returncode'],0)
            self.assertTrue((self.root/(name+'.stderr')).exists())

    def test_strict_configuration_json_and_record_rejections(self):
        for key,value in (('delta','0'),('threads','65'),('warmups','101'),('blocks','3'),('order_seed','18446744073709551616'),
                          ('delta','01'),('threads',2),('timing_mode','other'),('no_effect','other'),('schema_version',True)):
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                configuration(dict(self.config,**{key:value}))
        for data in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{} garbage'):
            with self.assertRaises(ValueError):
                loads(data)
        for data in (b'', b'{}', b'{}\n', b'{}\n\n'):
            with self.assertRaises(ValueError):
                read_jsonl(data)
        self.config.pop('warmups')
        self.assertEqual(configuration(self.config)['warmups'],'1')
        (self.root/'bundle/graph.txt').write_bytes(b'bad\n')
        with self.assertRaises(ExperimentError):
            run_experiment(self.config_path,CLI,self.root/'bad-artifacts')


if __name__ == '__main__':
    CLI = str(Path(sys.argv.pop(1)).resolve())
    unittest.main()
