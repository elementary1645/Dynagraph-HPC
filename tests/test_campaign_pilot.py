"""Bounded development pilot contracts and failure evidence; no performance claims."""
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'benchmarks/python'))
from artifacts import write_bundle
from campaign_contract import expand, plan_hash
from campaign_process import timestamp
from campaign_pilot import (OracleUnavailable, atomic_bytes, capture, run_pilot, select,
                            validate_trial, verify_pilot)
from workloads import canonical_json, sha256
from test_campaign import hardware


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan = json.loads((ROOT/'benchmarks/configs/campaign-development-v1.json').read_bytes())
        (self.root/'bin').mkdir()
        self.runner = self.root/'bin/dynagraph_bench'
        self.runner.write_text('#!/usr/bin/env python3\nraise SystemExit(7)\n');self.runner.chmod(0o700)
        self.plan['build']['executable_sha256'] = sha256(self.runner.read_bytes())
        write_bundle(self.plan['workloads'][0]['recipe'],self.root/'workloads/chain')
        self.manifest = expand(self.plan)
        self.ids = [t['trial_id'] for t in self.manifest['trials']]
        self.probe = patch('campaign_pilot.inspect',return_value=hardware());self.probe.start();self.addCleanup(self.probe.stop)

    def run_case(self, ids=None, **kwargs):
        return run_pilot(self.plan,self.manifest,self.root,self.root/'out',ids or [self.ids[0]],
                         execute=True,**kwargs)

    def record(self):
        index = json.loads((self.root/'out/result-index.json').read_bytes())
        return json.loads((self.root/'out'/index['records'][0]).read_bytes())

    def test_selection_order_and_identity(self):
        a = select(self.plan,self.manifest,[self.ids[4],self.ids[0]],2)
        self.assertEqual(a,[self.manifest['trials'][0],self.manifest['trials'][4]])
        self.assertEqual(a,select(copy.deepcopy(self.plan),copy.deepcopy(self.manifest),[self.ids[0],self.ids[4]],2))

    def test_duplicate_unknown_and_empty_ids(self):
        for ids in ([self.ids[0]]*2,['f'*64],[],[False]):
            with self.subTest(ids=ids),self.assertRaises(ValueError):select(self.plan,self.manifest,ids,2)

    def test_invalid_manifests(self):
        for change in (lambda m:m['trials'].reverse(),lambda m:m['trials'].append(m['trials'][0]),
                       lambda m:m.update(schema_version=True),lambda m:m['trials'][0].update(sequence=True)):
            m=copy.deepcopy(self.manifest);change(m)
            with self.assertRaises(ValueError):select(self.plan,m,[self.ids[0]])

    def test_opt_in_and_scientific_rejection(self):
        with self.assertRaisesRegex(ValueError,'execute-development'):
            run_pilot(self.plan,self.manifest,self.root,self.root/'out',[self.ids[0]])
        self.plan['hardware'].update(mode='scientific',exclusive=True,reservation='test')
        with self.assertRaisesRegex(ValueError,'development'):
            self.run_case()
        self.assertFalse((self.root/'out').exists())

    def test_limits(self):
        for option,value in [('max_trials',9),('wall_seconds',121),('timeout',31),('output_limit',1048577)]:
            with self.subTest(option=option),self.assertRaises(ValueError):self.run_case(**{option:value})
        self.assertFalse((self.root/'out').exists())

    def test_nonzero_and_no_retry(self):
        result=self.run_case([self.ids[1],self.ids[0]],max_trials=2)
        self.assertEqual(result['status'],'failed');r=self.record()
        self.assertEqual(r['reason'],'nonzero-exit');self.assertEqual(r['processes'][0]['returncode'],7)
        second=json.loads((self.root/'out'/result['records'][1]).read_bytes())
        self.assertEqual(second['reason'],'not-run');self.assertEqual(second['processes'],[])
        self.assertFalse(r['measurement_eligible']);self.assertIsNone(r['observed_team_size'])
        self.assertEqual(verify_pilot(self.root/'out')['execution_status'],'failed')

    def test_missing_executable(self):
        self.runner.unlink();self.run_case();self.assertEqual(self.record()['reason'],'input-error')
        self.assertEqual(self.record()['processes'],[])

    def test_missing_input(self):
        (self.root/'workloads/chain/trace.txt').unlink();self.run_case()
        self.assertEqual(self.record()['reason'],'input-error')

    def test_modified_input_hashes(self):
        with (self.root/'workloads/chain/graph.txt').open('ab') as s:s.write(b'changed')
        self.run_case();self.assertEqual(self.record()['reason'],'input-error')

    def test_wrong_executable_hash(self):
        self.plan['build']['executable_sha256']='f'*64;self.manifest=expand(self.plan)
        self.ids=[t['trial_id'] for t in self.manifest['trials']]
        self.run_case();self.assertIn('SHA-256',self.record()['message'])

    def test_input_symlink_and_escape(self):
        self.runner.unlink();self.runner.symlink_to(sys.executable)
        self.run_case();self.assertIn('symlink',self.record()['message'])

    def response(self, raw=b'{}\n', reason='exited'):
        return dict(command=['runner','verify'],start=timestamp(),end=timestamp(),returncode=0,
                    signal=None,reason=reason,truncated=False),dict(stdout=raw,stderr=b'')

    def test_malformed_and_partial_result_json(self):
        for raw in (b'{',b'not JSON',b'{}'):
            with self.subTest(raw=raw),tempfile.TemporaryDirectory() as temp:
                with patch('campaign_pilot.capture',return_value=self.response(raw)):
                    run_pilot(self.plan,self.manifest,self.root,Path(temp)/'out',[self.ids[0]],execute=True)
                r=json.loads((Path(temp)/'out'/self.ids[0]/'record.json').read_bytes())
                self.assertEqual(r['reason'],'correctness-failed');self.assertFalse(r['measurement_eligible'])

    def test_failed_correctness_gate(self):
        with patch('campaign_pilot.capture',return_value=self.response()),patch('campaign_pilot.verify_preflight',side_effect=ValueError('oracle mismatch')):
            self.run_case()
        self.assertEqual(self.record()['correctness']['outcome'],'failed')

    def test_unavailable_correctness_oracle(self):
        with patch('campaign_pilot.stage_inputs',side_effect=OracleUnavailable('unavailable')):
            self.run_case()
        r=self.record();self.assertEqual(r['status'],'unverified');self.assertFalse(r['correctness']['checked'])
        self.assertFalse(r['measurement_eligible'])

    def test_keyboard_interruption_record(self):
        with patch('campaign_pilot.capture',side_effect=KeyboardInterrupt):self.run_case()
        self.assertEqual(self.record()['reason'],'interrupted')
        self.assertEqual(verify_pilot(self.root/'out')['execution_status'],'failed')

    def test_atomic_write_failure_and_collision(self):
        f=self.root/'atomic'
        with patch('campaign_pilot.os.link',side_effect=OSError('disk')):
            with self.assertRaises(OSError):atomic_bytes(f,b'partial')
        self.assertFalse(f.exists());self.assertEqual(list(self.root.glob('.pending-*')),[])
        atomic_bytes(f,b'original')
        with self.assertRaises(FileExistsError):atomic_bytes(f,b'overwrite')
        self.assertEqual(f.read_bytes(),b'original')

    def test_existing_output_collision(self):
        (self.root/'out').mkdir()
        with self.assertRaises(FileExistsError):self.run_case()
        self.assertEqual(list((self.root/'out').iterdir()),[])

    def test_atomic_record_failure_leaves_incomplete(self):
        from campaign_pilot import put
        def fail(directory,name,value):
            if name=='record.json':raise OSError('disk full')
            return put(directory,name,value)
        with patch('campaign_pilot.put',side_effect=fail):
            with self.assertRaises(OSError):self.run_case()
        self.assertFalse((self.root/'out/result-index.json').exists())
        with self.assertRaises(OSError):verify_pilot(self.root/'out')

    def test_inventory_tamper(self):
        self.run_case();(self.root/'out'/self.ids[0]/'0-verify.stdout').write_bytes(b'tamper')
        with self.assertRaisesRegex(ValueError,'digest mismatch'):verify_pilot(self.root/'out')

    def test_success_cannot_be_inferred(self):
        self.run_case();r=self.record();r.update(status='success',reason='success')
        with self.assertRaises(ValueError):validate_trial(r)

    def test_cli_requires_optin(self):
        p=self.root/'p.json';m=self.root/'m.json';p.write_bytes(canonical_json(self.plan));m.write_bytes(canonical_json(self.manifest))
        c=subprocess.run([sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'pilot','--plan',str(p),'--manifest',str(m),
                          '--root',str(self.root),'--output',str(self.root/'out'),'--trial-id',self.ids[0]],capture_output=True)
        self.assertEqual(c.returncode,2);self.assertIn(b'execute-development',c.stderr)

    def process(self, code, timeout=1, limit=1024):
        return capture([sys.executable,'-B','-c',code],self.root,dict(os.environ),timeout,limit)

    def test_process_timeout(self):
        r,_=self.process('import time;time.sleep(10)',timeout=0.1)
        self.assertEqual(r['reason'],'timeout');self.assertEqual(r['signal'],signal.SIGKILL)

    def test_output_cap_and_partial_capture(self):
        r,b=self.process('import os;os.write(1,b"x"*100000)')
        self.assertEqual(r['reason'],'output-limit');self.assertTrue(r['truncated']);self.assertEqual(len(b['stdout']),1024)

    def test_launch_failure_and_signal(self):
        r,_=capture(['/does/not/exist'],self.root,dict(os.environ),1,1024)
        self.assertEqual(r['reason'],'launch-error');self.assertIsNone(r['returncode'])
        r,_=self.process('import os,signal;os.kill(os.getpid(),signal.SIGTERM)')
        self.assertEqual(r['reason'],'signal');self.assertEqual(r['signal'],signal.SIGTERM)

    def test_process_interrupt_cleanup(self):
        import selectors
        with patch.object(selectors.EpollSelector,'select',side_effect=KeyboardInterrupt):
            r,_=self.process('import time;time.sleep(10)')
        self.assertEqual(r['reason'],'interrupted');self.assertIsNotNone(r['returncode'])

    def test_descendant_pipe_timeout(self):
        r,_=self.process('import os,time\nif os.fork()==0:time.sleep(10)',timeout=0.1)
        self.assertEqual(r['reason'],'timeout')

    def test_wall_budget_no_launch(self):
        with patch('campaign_pilot.time.monotonic',side_effect=[0,0,61]),patch('campaign_pilot.capture') as launch:
            self.run_case()
        self.assertEqual(self.record()['reason'],'budget-exhausted');launch.assert_not_called()

    def test_environment_and_requested_workers(self):
        from campaign_pilot import environment
        with patch.dict(os.environ,{'OMP_PLACES':'bad','GOMP_CPU_AFFINITY':'bad','LD_PRELOAD':'bad'}):
            env=environment(2)
        self.assertNotIn('LD_PRELOAD',env);self.assertNotIn('OMP_PLACES',env)
        self.assertNotIn('GOMP_CPU_AFFINITY',env);self.assertEqual(env['OMP_NUM_THREADS'],'2')

    def test_shared_per_trial_deadline(self):
        with patch('campaign_pilot.capture',return_value=self.response()),patch('campaign_pilot.verify_preflight'),patch('campaign_pilot.time.monotonic',side_effect=[0,0,0,0,11,11]):
            self.run_case([self.ids[4]])
        self.assertEqual(self.record()['reason'],'timeout')

    def test_truncated_stream_records_failure(self):
        response=self.response(b'x'*16,'output-limit');response[0]['truncated']=True
        with patch('campaign_pilot.capture',return_value=response):self.run_case()
        self.assertEqual(self.record()['reason'],'output-limit')
        self.assertEqual(verify_pilot(self.root/'out')['execution_status'],'failed')

    def test_manifest_compatibility(self):
        p=json.loads((ROOT/'benchmarks/configs/campaign-development-v1.json').read_bytes())
        self.assertEqual(plan_hash(p),'f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24')
        self.assertEqual(sha256(canonical_json(expand(p))),'f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a')

    def test_real_worker_all_phases(self):
        executable=Path(os.environ.get('DYNAGRAPH_PILOT_TEST_RUNNER',ROOT/'build/release/dynagraph_bench'))
        if not executable.is_file():self.skipTest('built benchmark unavailable')
        self.runner.write_bytes(executable.read_bytes());self.runner.chmod(0o700)
        self.plan['build']['executable_sha256']=sha256(self.runner.read_bytes());self.manifest=expand(self.plan)
        ids=[next(t['trial_id'] for t in self.manifest['trials'] if t['phase']==phase) for phase in ('diagnostic','warmup','measured')]
        result=self.run_case(ids,max_trials=3)
        self.assertEqual(result['status'],'complete',self.record())
        self.assertEqual(verify_pilot(self.root/'out')['execution_status'],'complete')
        for name in result['records']:
            r=json.loads((self.root/'out'/name).read_bytes());self.assertFalse(r['measurement_eligible']);self.assertTrue(r['correctness']['checked'])


if __name__=='__main__':unittest.main(verbosity=2)
