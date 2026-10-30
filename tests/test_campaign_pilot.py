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
                            validate_trial, verify_pilot, command)
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
        return dict(command=command(self.plan,self.manifest['trials'][0],0,'verify'),start=timestamp(),end=timestamp(),returncode=0,
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
        with patch('campaign_pilot.capture',return_value=self.response()),patch('campaign_pilot.check_preflight'),patch('campaign_pilot.time.monotonic',side_effect=[0,0,0,0,0,11,11]):
            self.run_case([self.ids[4]])
        self.assertEqual(self.record()['reason'],'timeout')

    def test_truncated_stream_records_failure(self):
        response=self.response(b'x'*16,'output-limit');response[0]['truncated']=True
        def fresh(*args,**kwargs):
            response[0].update(start=timestamp(),end=timestamp());return response
        with patch('campaign_pilot.capture',side_effect=fresh):self.run_case(output_limit=16)
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


class R1Tests(unittest.TestCase):
    """Red acceptance probes added before remediation; no historical fixture edits."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.plan=json.loads((ROOT/'benchmarks/configs/campaign-development-v1.json').read_bytes())
        (self.root/'bin').mkdir();self.runner=self.root/'bin/bench'
        executable=Path(os.environ.get('DYNAGRAPH_PILOT_TEST_RUNNER',ROOT/'build/release/dynagraph_bench'))
        if not executable.is_file():self.fail('build benchmark before running pilot regressions')
        self.runner.write_bytes(executable.read_bytes());self.runner.chmod(0o700)
        self.plan['build'].update(executable='bin/bench',executable_sha256=sha256(self.runner.read_bytes()))
        write_bundle(self.plan['workloads'][0]['recipe'],self.root/'workloads/chain')
        self.manifest=expand(self.plan)
        self.patch=patch('campaign_pilot.inspect',return_value=hardware());self.patch.start();self.addCleanup(self.patch.stop)

    def pilot(self,name='out',phase='diagnostic'):
        tid=next(t['trial_id'] for t in self.manifest['trials'] if t['phase']==phase)
        d=self.root/name
        index=run_pilot(self.plan,self.manifest,self.root,d,[tid],execute=True)
        ref=Path(index['records'][0]);r=json.loads((d/ref).read_bytes())
        return d,ref,r

    def rehash(self,d,ref,r):
        (d/ref).write_bytes(canonical_json(r))
        (d/'sha256.json').write_bytes(canonical_json({p.relative_to(d).as_posix():sha256(p.read_bytes())
            for p in d.rglob('*') if p.is_file() and p.name!='sha256.json'}))

    def test_r1_live_corrupt_distance_all_phases(self):
        real=capture
        def faulty(command,*args,**kwargs):
            process,streams=real(command,*args,**kwargs)
            if command[1]=='verify':
                report=json.loads(streams['stdout']);report['final_distances'][1]=123456789
                streams['stdout']=canonical_json(report)
            return process,streams
        for phase in ('diagnostic','warmup','measured'):
            with self.subTest(phase=phase),patch('campaign_pilot.capture',side_effect=faulty):
                d,ref,r=self.pilot(phase,phase)
            self.assertEqual(r['reason'],'correctness-failed',r)
            self.assertNotEqual(r['status'],'success')

    def test_r1_rehashed_contradictory_evidence(self):
        for case in ('executable','argv','extra-flag','missing-flag','stdout','stderr','affinity','stream-cap','exit','correctness','eligibility','inventory','size','hash','duplicate-stream','environment','schema'):
            with self.subTest(case=case):
                d,ref,r=self.pilot(case)
                if case=='executable':r['processes'][0]['command'][0]='/bin/false'
                if case=='argv':r['processes'][0]['command']=['/bin/false','verify','--policy','invalid']
                if case=='extra-flag':r['processes'][0]['command'].append('--extra')
                if case=='missing-flag':r['processes'][0]['command'].pop()
                if case in ('stdout','stderr'):
                    n=r['processes'][0][case];(d/ref.parent/n).unlink();r['artifacts'].pop(n)
                if case=='affinity':r['requested_affinity']=[999]
                if case=='stream-cap':
                    f=d/'execution-manifest.json';v=json.loads(f.read_bytes());v['limits']['stream_bytes']=1
                    f.write_bytes(canonical_json(v));idx=json.loads((d/'result-index.json').read_bytes())
                    idx['execution_manifest_sha256']=sha256(f.read_bytes());(d/'result-index.json').write_bytes(canonical_json(idx))
                if case=='exit':r['processes'][0]['returncode']=7
                if case=='correctness':r['correctness']=dict(checked=False,outcome='unavailable',oracle=None)
                if case=='eligibility':r['measurement_eligible']=True
                if case=='size':r['processes'][0]['stdout_size']+=1
                if case=='hash':r['processes'][0]['stderr_sha256']='0'*64
                if case=='duplicate-stream':r['processes'][0]['stderr']=r['processes'][0]['stdout']
                if case=='environment':r['openmp_environment']['OMP_NUM_THREADS']='999'
                if case=='schema':r['schema_version']=1
                self.rehash(d,ref,r)
                if case=='inventory':
                    f=d/'sha256.json';v=json.loads(f.read_bytes());v.pop((ref.parent/r['processes'][0]['stderr']).as_posix());f.write_bytes(canonical_json(v))
                with self.assertRaises((ValueError,OSError)):verify_pilot(d)

    def test_r1_offline_distances_and_output_protocol(self):
        for case in ('distance','length','source','weights','policy','incomplete'):
            with self.subTest(case=case):
                d,ref,r=self.pilot(case)
                f=d/ref.parent/r['processes'][0]['stdout'];v=json.loads(f.read_bytes())
                if case=='distance':v['final_distances'][1]=123456789
                if case=='length':v['final_distances'].pop()
                if case=='source':v['source']=1
                if case=='weights':v['final_weights'][0]+=1
                if case=='policy':v['policy']='invalid'
                if case=='incomplete':v['updates_verified']-=1
                raw=canonical_json(v);f.write_bytes(raw)
                r['processes'][0].update(stdout_size=len(raw),stdout_sha256=sha256(raw))
                r['artifacts'][f.name]=sha256(raw);self.rehash(d,ref,r)
                with self.assertRaises(ValueError):verify_pilot(d)

    def test_r1_relocated_evidence_and_cli_positive(self):
        d,ref,r=self.pilot(phase='measured')
        import shutil
        moved=self.root/'relocated';shutil.copytree(d,moved)
        self.assertEqual(verify_pilot(moved)['execution_status'],'complete')
        c=subprocess.run([sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'verify-pilot','--output',str(moved)],capture_output=True,timeout=2)
        self.assertEqual(c.returncode,0,c.stderr)
        self.assertIn(b'"measurement_eligible":false',c.stdout)

    def test_r1_failed_receipt_and_halt_reconciliation(self):
        self.runner.write_text('#!/usr/bin/python3\nraise SystemExit(7)\n')
        self.plan['build']['executable_sha256']=sha256(self.runner.read_bytes());self.manifest=expand(self.plan)
        d,ref,r=self.pilot()
        self.assertEqual(verify_pilot(d)['execution_status'],'failed')
        r['processes'][0]['returncode']=0;self.rehash(d,ref,r)
        with self.assertRaises(ValueError):verify_pilot(d)

    def test_r1_error_diagnostic_stays_bounded(self):
        from campaign_process import capture as run
        original=os.read
        seen=False
        def broken(fd,n):
            nonlocal seen
            if seen:raise OSError('x'*1000)
            data=original(fd,n)
            if data:seen=True
            return data
        with patch('campaign_process.os.read',side_effect=broken):
            result,streams=run([sys.executable,'-B','-c','import os,time;os.write(2,b"x"*64);time.sleep(.05);os.write(2,b"y");time.sleep(5)'],self.root,dict(os.environ),1,128)
        self.assertEqual(result['reason'],'capture-error')
        self.assertLessEqual(len(streams['stderr']),128)
        self.assertTrue(result['truncated'])

    def test_r1_fifo_metadata_cli_is_bounded(self):
        d=self.root/'fifo';d.mkdir();os.mkfifo(d/'sha256.json')
        c=subprocess.run([sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'verify-pilot','--output',str(d)],capture_output=True,timeout=1)
        self.assertEqual(c.returncode,2);self.assertNotIn(b'Traceback',c.stderr)


class OracleTests(unittest.TestCase):
    def setUp(self):
        from workloads import Graph, Trace, graph_bytes, trace_bytes
        from campaign_oracle import reconcile
        self.reconcile=reconcile
        self.graph=graph_bytes(Graph(3,((0,1,10),)))
        self.trace=Trace(sha256(self.graph),('1','2','3','4'),0,((0,0,1,10,7),(1,0,1,7,5)))
        self.trace_bytes=trace_bytes
        self.data=trace_bytes(self.trace)
        self.manifest=dict(source=0,artifacts={'graph':{'sha256':sha256(self.graph)},'trace':{'sha256':sha256(self.data)}},
                           final_graph_sha256=sha256(graph_bytes(Graph(3,((0,1,5),)))))
        self.result=dict(source=0,final_weights=[5],final_distances=[0,5,None])

    def test_reference_positive_and_zero_cycles(self):
        from campaign_oracle import METHOD
        self.assertEqual(self.reconcile(self.graph,self.data,self.manifest,self.result),METHOD)
        from workloads import Graph, Trace, graph_bytes, trace_bytes
        graph=graph_bytes(Graph(3,((0,1,0),(1,0,0),(1,2,0))))
        trace=trace_bytes(Trace(sha256(graph),('1','2','3','4'),0,()))
        manifest=dict(source=0,artifacts={'graph':{'sha256':sha256(graph)},'trace':{'sha256':sha256(trace)}},final_graph_sha256=sha256(graph))
        self.reconcile(graph,trace,manifest,dict(source=0,final_weights=[0,0,0],final_distances=[0,0,0]))

    def test_reference_distance_source_length_and_weights(self):
        for change in (dict(final_distances=[0,6,None]),dict(final_distances=[0,5,0]),
                       dict(source=1),dict(source=False),dict(final_distances=[0,5]),
                       dict(final_distances=[False,5,None]),dict(final_weights=[7])):
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.reconcile(self.graph,self.data,self.manifest,dict(self.result,**change))

    def test_ordered_updates_and_final_graph(self):
        from dataclasses import replace
        trace=replace(self.trace,updates=((0,0,1,7,5),(1,0,1,10,7)))
        data=self.trace_bytes(trace);m=copy.deepcopy(self.manifest);m['artifacts']['trace']['sha256']=sha256(data)
        with self.assertRaisesRegex(ValueError,'old weight'):self.reconcile(self.graph,data,m,self.result)
        m=copy.deepcopy(self.manifest);m['final_graph_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'final graph'):self.reconcile(self.graph,self.data,m,self.result)

    def test_missing_or_tampered_reference(self):
        with self.assertRaises(ValueError):self.reconcile(b'',self.data,self.manifest,self.result)
        with self.assertRaises(ValueError):self.reconcile(self.graph,self.data+b'x',self.manifest,self.result)


class CaptureAndMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_capture_diagnostics_at_all_caps(self):
        original=os.read
        for cap in (0,1,64,128,1048576):
            for saturated in (False,True):
                with self.subTest(cap=cap,saturated=saturated):
                    seen=False
                    amount=cap if saturated else min(64,cap//2)
                    def broken(fd,n):
                        nonlocal seen
                        if n!=65536:return original(fd,n)
                        if seen:raise OSError('x'*(cap+1))
                        seen=True
                        return b'x'*amount
                    # cap=0 has no positive read before error: inject on select.
                    if amount==0:
                        import selectors
                        with patch.object(selectors.EpollSelector,'select',side_effect=OSError('x'*(cap+1))):
                            r,b=capture([sys.executable,'-c','import time;time.sleep(5)'],self.root,dict(os.environ),1,cap)
                    else:
                        with patch('campaign_process.os.read',side_effect=broken):
                            r,b=capture([sys.executable,'-c','import os,time;os.write(2,b"x");time.sleep(5)'],self.root,dict(os.environ),1,cap)
                    self.assertEqual(r['reason'],'capture-error');self.assertTrue(r['truncated'])
                    self.assertLessEqual(len(b['stderr']),cap);self.assertLessEqual(len(b['stdout']),cap)

    def test_simultaneous_streams_with_read_error(self):
        original=os.read;seen=False
        def broken(fd,n):
            nonlocal seen
            if n!=65536:return original(fd,n)
            if seen:raise OSError('injected read failure'*20)
            seen=True;return original(fd,min(n,64))
        code='import os,threading\ndef flood(fd):\n while True:os.write(fd,b"x"*32)\nthreading.Thread(target=flood,args=(2,)).start();flood(1)'
        with patch('campaign_process.os.read',side_effect=broken):
            r,b=capture([sys.executable,'-c',code],self.root,dict(os.environ),1,128)
        self.assertEqual(r['reason'],'capture-error');self.assertTrue(all(len(v)<=128 for v in b.values()))

    def test_nonregular_and_oversized_metadata(self):
        from campaign_pilot import read_json
        import socket
        fifo=self.root/'fifo';os.mkfifo(fifo)
        link=self.root/'link';link.symlink_to(fifo)
        directory=self.root/'directory';directory.mkdir()
        sock=socket.socket(socket.AF_UNIX);self.addCleanup(sock.close);sock.bind(str(self.root/'socket'))
        huge=self.root/'huge';huge.write_bytes(b' '*1048577)
        for path in (fifo,link,directory,self.root/'socket',Path('/dev/null'),huge):
            with self.subTest(path=path),self.assertRaises((ValueError,OSError)):read_json(path)
        regular=self.root/'valid';regular.write_bytes(b'{"value":1}\n');self.assertEqual(read_json(regular),{'value':1})

    def test_nonregular_metadata_cli(self):
        for name in ('sha256.json','plan.json','execution-manifest.json','result-index.json'):
            d=self.root/name.replace('.','-');d.mkdir()
            if name=='sha256.json':os.mkfifo(d/name)
            else:
                os.mkfifo(d/name)
                (d/'sha256.json').write_bytes(canonical_json({name:'0'*64}))
            c=subprocess.run([sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'verify-pilot','--output',str(d)],capture_output=True,timeout=1)
            self.assertEqual(c.returncode,2);self.assertNotIn(b'Traceback',c.stderr)


if __name__=='__main__':unittest.main(verbosity=2)
