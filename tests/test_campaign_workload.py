"""Actual workload regions, rehashed semantic forgeries, pilot/offline/recovery gates."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'benchmarks/python'), str(ROOT/'tests')]
FIXTURE = Path(sys.argv.pop(1)).resolve() if __name__=='__main__' and len(sys.argv)>1 else Path(os.environ.get('DYNAGRAPH_WORKLOAD_TEST_FIXTURE',ROOT/'build/debug/tests/workload_fixture'))
BENCH = Path(sys.argv.pop(1)).resolve() if __name__=='__main__' and len(sys.argv)>1 else Path(os.environ.get('DYNAGRAPH_PILOT_TEST_RUNNER',ROOT/'build/debug/dynagraph_bench'))
from campaign_workload import (NATIVE, BOUND, bind, verify, validate_native, classification, expected_regions)
from campaign_enforcement import binding, seal
from campaign_process import capture
from campaign_pilot import run_pilot, verify_pilot, read_json
from campaign_journal import inspect_recovery, entry
from campaign_contract import expand
from artifacts import write_bundle
from workloads import canonical_json, sha256
from test_campaign_enforcement import groups
from test_campaign import hardware


class WorkloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.cpus = sorted(os.sched_getaffinity(0))[:2]
        cls.samples = {}
        for mode in ('one','two','dynamic','repeated','active','serialized','serialized-zero','joined','serial'):
            directory = cls.root/mode;directory.mkdir()
            shutil.copyfile(FIXTURE, directory/'runner');(directory/'runner').chmod(0o700)
            command = ['./runner',mode,NATIVE]
            b = dict(execution_id='a'*64,trial_id='b'*64,attempt_id='c'*64,journal_binding_sha256='d'*64,
                     process_index=0,origin=dict(kind='original',attempt_id=None),command=command,
                     executable_sha256=sha256(FIXTURE.read_bytes()),workers=1 if mode=='one' else 2)
            env = {k:v for k,v in os.environ.items() if not k.startswith(('OMP_','GOMP_','KMP_','LD_'))}
            env.update(OMP_NUM_THREADS='2', OMP_THREAD_LIMIT='1' if mode=='dynamic' else '4', OMP_DYNAMIC='FALSE')
            # Actual Linux affinity/identity/barrier; cgroup visibility is synthetic
            # and explicitly limited to fixtures (container hierarchy may be hidden).
            with patch('campaign_enforcement.cgroup_ancestry',return_value=groups(cls.cpus)):
                process, streams = capture(command,directory,env,10,1048576,
                    enforcement=dict(cpus=cls.cpus,binding=b))
            if process['reason'] != 'exited': raise AssertionError((mode,process,streams))
            if json.loads(streams['stdout']) != dict(oracle_passed=True): raise AssertionError('oracle failed')
            cls.samples[mode] = (read_json(directory/NATIVE),process['_enforcement'],b)
            for name,value in (('affinity.json',process['_enforcement']),('process.json',process),('binding.json',b)):
                (directory/name).write_bytes(canonical_json(value))
            for name,raw in streams.items():(directory/name).write_bytes(raw)

    @classmethod
    def tearDownClass(cls):
        retained=os.environ.get('DYNAGRAPH_WORKLOAD_EVIDENCE_DIR')
        if retained:
            shutil.copytree(cls.root,retained)
            Path(retained,'limitations.txt').write_text('Development fixtures; actual Linux affinity, process identities and workload threads. Synthetic visible cgroup hierarchy. No performance, isolation or scientific eligibility claims.\n')
        cls.tmp.cleanup()

    def test_actual_native_modes_and_nonleader_primary(self):
        for mode,(native,receipt,b) in self.samples.items():
            count = 0 if mode=='serial' else 3 if mode=='repeated' else 1
            validate_native(native,receipt,b['workers'],count)
            bound = bind(native,receipt,'e'*64,count)
            self.assertEqual(verify(bound,native,receipt,b,'e'*64,count,True),'observed_consistent')
        native, receipt, _ = self.samples['joined']
        self.assertNotEqual(native['regions'][0]['threads'][0]['entry']['tid'],receipt['observation']['pid'])
        self.assertEqual(len(self.samples['two'][0]['regions'][0]['threads']),2)
        self.assertEqual(len(self.samples['dynamic'][0]['regions'][0]['threads']),1)
        self.assertEqual(self.samples['active'][0]['regions'][0]['threads'][0]['active_level'],2)
        self.assertEqual(self.samples['serialized'][0]['regions'][0]['threads'][0]['active_level'],1)
        serialized_zero=self.samples['serialized-zero'][0]['regions'][0]['threads'][0]
        self.assertEqual((serialized_zero['team'],serialized_zero['active_level'],serialized_zero['max_active_levels']),(1,1,0))

    @staticmethod
    def mutations():
        def sample_change(n,key,delta=1,both=False,worker=0):
            t=n['regions'][0]['threads'][worker]
            for k in ('entry','exit') if both else ('entry',): t[k][key]+=delta
        mutations = {
            'leader-entry':lambda n:sample_change(n,'leader_start_ticks'),
            'leader-both':lambda n:sample_change(n,'leader_start_ticks',both=True),
            'leader-availability':lambda n:n['regions'][0]['threads'][0]['entry'].update(leader_available=False),
            'foreign-worker':lambda n:sample_change(n,'tgid',both=True,worker=1),
            'foreign-primary':lambda n:sample_change(n,'task_tgid',both=True),
            'pid-tid':lambda n:sample_change(n,'task_pid'),
            'generation':lambda n:sample_change(n,'start_ticks'),
            'leader-own-generation-both':lambda n:sample_change(n,'start_ticks',both=True),
            'process-group':lambda n:sample_change(n,'pgrp',both=True),
            'session':lambda n:sample_change(n,'session',both=True),
            'max-zero':lambda n:n['regions'][0]['threads'][0].update(max_active_levels=0),
            'active-level':lambda n:n['regions'][0]['threads'][0].update(active_level=0),
            'ancestor-team':lambda n:n['regions'][0]['threads'][0]['ancestor_sizes'].__setitem__(0,2),
            'missing-membership':lambda n:n['regions'][0]['threads'][0]['entry'].pop('task_tgid'),
            'duplicate-tid':lambda n:n['regions'][0]['threads'][1].update(entry=copy.deepcopy(n['regions'][0]['threads'][0]['entry']),exit=copy.deepcopy(n['regions'][0]['threads'][0]['exit'])),
            'missing-region':lambda n:n['regions'].clear(),
            'extra-region':lambda n:n['regions'].append(copy.deepcopy(n['regions'][0])),
            'outside-cpu':lambda n:n['regions'][0]['threads'][0]['entry'].update(cpu=8191),
            'legacy-downgrade':lambda n:n.update(schema_version=1),
        }
        return mutations

    def test_rehashed_adversarial_native_matrix(self):
        native,receipt,b = self.samples['two']
        for name,mutate in self.mutations().items():
            with self.subTest(name=name):
                forged=copy.deepcopy(native);mutate(forged)
                bound=bind(forged,receipt,'e'*64,1)  # Recompute every applicable evidence digest.
                with self.assertRaises(ValueError):verify(bound,forged,receipt,b,'e'*64,1,True)
        for key in ('attempt_id','trial_id','execution_id'):
            other=copy.deepcopy(b);other[key]='f'*64
            with self.assertRaises(ValueError):verify(bind(native,receipt,'e'*64,1),native,receipt,other,'e'*64,1,True)
        unknown=copy.deepcopy(receipt);unknown['release']['state']='indeterminate';unknown['released']=None
        unknown=seal(unknown)
        with self.assertRaises(ValueError):validate_native(native,unknown,2,1)

    def test_known_contradictions_precede_missing_task_evidence(self):
        native,receipt,b=self.samples['two']
        for missing_worker,bad_worker in ((0,0),(0,1),(1,0)):
            for field in ('leader_start_ticks','tgid','task_tgid','cpu'):
                with self.subTest(missing_worker=missing_worker,bad_worker=bad_worker,field=field):
                    forged=copy.deepcopy(native)
                    forged['regions'][0]['threads'][missing_worker]['entry'].pop('task_pid')
                    sample=forged['regions'][0]['threads'][bad_worker]['entry']
                    sample[field]=8191 if field=='cpu' else sample[field]+1
                    status,_=classification(forged,receipt,2,1)
                    self.assertEqual(status,'observed_contradictory')
        missing=copy.deepcopy(native)
        missing['regions'][0]['threads'][0]['entry'].pop('task_pid')
        self.assertEqual(classification(missing,receipt,2,1)[0],'insufficient_evidence')
        missing['regions'][0]['threads'][0]['entry']=None
        self.assertEqual(classification(missing,receipt,2,1)[0],'insufficient_evidence')
        missing['regions'][0]['threads'][0].pop('entry')
        self.assertEqual(classification(missing,receipt,2,1)[0],'insufficient_evidence')
        # The missing fact and known contradiction can be in different regions.
        repeated,repeated_receipt,_=self.samples['repeated']
        forged=copy.deepcopy(repeated)
        forged['regions'][0]['threads'][0]['entry'].pop('task_pid')
        forged['regions'][-1]['threads'][1]['exit']['leader_start_ticks']+=1
        self.assertEqual(classification(forged,repeated_receipt,2,3)[0],'observed_contradictory')
        missing['regions'][0]['threads'][1]['max_active_levels']=0
        self.assertEqual(classification(missing,receipt,2,1)[0],'observed_contradictory')

    def pilot(self, directory, observe=True, cut=False, fail=False, policy='delta-stepping'):
        root=directory/'inputs';root.mkdir();(root/'bin').mkdir()
        shutil.copyfile(BENCH,root/'bin/dynagraph_bench');(root/'bin/dynagraph_bench').chmod(0o700)
        plan=json.loads((ROOT/'benchmarks/configs/campaign-development-v1.json').read_bytes())
        plan['build']['executable_sha256']=sha256(BENCH.read_bytes())
        plan['hardware']['allocated_cpus']=self.cpus
        write_bundle(plan['workloads'][0]['recipe'],root/'workloads/chain')
        manifest=expand(plan)
        trials=[t for t in manifest['trials'] if t['phase']=='diagnostic' and t['policy']==policy][:2]
        output=directory/'out'
        from campaign_journal import Journal
        from campaign_pilot import put
        from contextlib import ExitStack
        finish = Journal.finish
        def interrupted(journal, record):
            finish(journal, record)
            raise RuntimeError('bounded interruption between trials')
        def publish(directory, name, value):
            if name == BOUND: raise OSError('injected diagnostic publication failure')
            return put(directory, name, value)
        with ExitStack() as stack:
            stack.enter_context(patch('campaign_pilot.inspect',return_value=hardware()))
            stack.enter_context(patch('campaign_enforcement.cgroup_ancestry',return_value=groups(self.cpus)))
            if cut: stack.enter_context(patch.object(Journal,'finish',interrupted))
            if fail: stack.enter_context(patch('campaign_pilot.put',side_effect=publish))
            if cut: stack.enter_context(self.assertRaisesRegex(RuntimeError,'bounded interruption'))
            result=run_pilot(plan,manifest,root,output,[t['trial_id'] for t in trials],execute=True,
                max_trials=2,enforce_affinity=True,observe_workload=observe,wall_seconds=60,timeout=20)
        if not cut:
            self.assertEqual(result['status'],'failed' if fail else 'complete', [read_json(output/t['trial_id']/'record.json') for t in trials])
        return output,trials

    def rehash(self, output):
        # Independently refresh trial indexes, record hashes, terminal references,
        # the entire journal chain and global inventory after an adversarial edit.
        for record_path in output.glob('*/record.json'):
            record=json.loads(record_path.read_bytes())
            record['artifacts']={p.relative_to(record_path.parent).as_posix():sha256(p.read_bytes())
                for p in record_path.parent.rglob('*') if p.is_file() and p!=record_path}
            record_path.write_bytes(canonical_json(record))
        previous=None
        for path in sorted((output/'recovery-journal').glob('*.json')):
            old=json.loads(path.read_bytes());payload=old['payload']
            if old['kind']=='transition' and payload['evidence']:
                payload['evidence']['sha256']=sha256((output/payload['evidence']['path']).read_bytes())
            value=entry(old['sequence'],previous,old['kind'],payload);previous=value['entry_id']
            path.write_bytes(canonical_json(value))
        inventory={p.relative_to(output).as_posix():sha256(p.read_bytes())
                   for p in output.rglob('*') if p.is_file() and p!=output/'sha256.json'}
        (output/'sha256.json').write_bytes(canonical_json(inventory))

    def test_pilot_offline_and_recovery_rehashed_forgeries(self):
        with tempfile.TemporaryDirectory() as tmp:
            output,trials=self.pilot(Path(tmp))
            self.assertEqual(verify_pilot(output)['execution_status'],'complete')
            self.assertTrue(all(t['classification']=='verified-complete' for t in inspect_recovery(output)['trials']))
            tid=next(t['trial_id'] for t in trials if t['workers']==2);base=output/tid
            original={p:p.read_bytes() for p in output.rglob('*') if p.is_file()}
            for case, mutate in self.mutations().items():
                for p,raw in original.items():p.write_bytes(raw)
                n=read_json(base/NATIVE);mutate(n);(base/NATIVE).write_bytes(canonical_json(n))
                receipt=read_json(base/'0-verify.affinity.json')
                old=read_json(base/BOUND)
                (base/BOUND).write_bytes(canonical_json(bind(n,receipt,old['hardware_sha256'],old['expected_regions'])))
                self.rehash(output)
                with self.assertRaises(ValueError):verify_pilot(output)
                try: report=inspect_recovery(output)
                except ValueError: pass
                else:self.assertNotEqual(next(t['classification'] for t in report['trials'] if t['trial_id']==tid),'verified-complete')
            for raw in (b'{', b'{}', b'{"regions":null}\n'):
                for p,data in original.items():p.write_bytes(data)
                (base/NATIVE).write_bytes(raw);self.rehash(output)
                with self.assertRaises(ValueError):verify_pilot(output)
                try: report=inspect_recovery(output)
                except ValueError: pass
                else:self.assertNotEqual(next(t['classification'] for t in report['trials'] if t['trial_id']==tid),'verified-complete')
            for key in ('trial_id', 'attempt_id'):
                for p,data in original.items():p.write_bytes(data)
                value=read_json(base/BOUND);value['binding'][key]='f'*64
                from campaign_workload import seal as seal_workload
                (base/BOUND).write_bytes(canonical_json(seal_workload(value)));self.rehash(output)
                with self.assertRaises(ValueError):verify_pilot(output)
                try: report=inspect_recovery(output)
                except ValueError: pass
                else:self.assertNotEqual(next(t['classification'] for t in report['trials'] if t['trial_id']==tid),'verified-complete')

    def test_rehashed_false_consistency_claims_fail_offline_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            output,trials=self.pilot(Path(tmp))
            tid=next(t['trial_id'] for t in trials if t['workers']==2);base=output/tid
            original={p:p.read_bytes() for p in output.rglob('*') if p.is_file()}
            for case in ('leader-both','foreign-worker','foreign-primary','max-zero','missing-membership'):
                with self.subTest(case=case):
                    for p,raw in original.items():p.write_bytes(raw)
                    native=read_json(base/NATIVE);self.mutations()[case](native)
                    (base/NATIVE).write_bytes(canonical_json(native))
                    # Attacker retains a success claim and independently rehashes
                    # every changed object, rather than calling the verifier's bind.
                    bound=read_json(base/BOUND)
                    bound['native_sha256']=hashlib.sha256(canonical_json(native)).hexdigest()
                    bound['classification']='observed_consistent';bound['issue']=None
                    bound.pop('evidence_sha256')
                    bound['evidence_sha256']=hashlib.sha256(canonical_json(bound)).hexdigest()
                    (base/BOUND).write_bytes(canonical_json(bound));self.rehash(output)
                    with self.assertRaises(ValueError):verify_pilot(output)
                    with self.assertRaises(ValueError):inspect_recovery(output)
                    # Exercise per-trial recovery directly, without the full-index
                    # shortcut into verify_pilot. No archived executable is run.
                    sidecar=(output/'sha256.json').read_bytes();(output/'sha256.json').unlink()
                    with self.assertRaises(ValueError):inspect_recovery(output)
                    (output/'sha256.json').write_bytes(sidecar)

    def test_serial_pilot_has_no_workload_teams(self):
        with tempfile.TemporaryDirectory() as tmp:
            output,trials=self.pilot(Path(tmp),policy='dijkstra')
            self.assertEqual(verify_pilot(output)['execution_status'],'complete')
            for trial in trials:self.assertEqual(read_json(output/trial['trial_id']/NATIVE)['regions'],[])
            self.assertTrue(all(t['classification']=='verified-complete' for t in inspect_recovery(output)['trials']))

    def test_opt_in_rejected_before_output_or_launch(self):
        plan=json.loads((ROOT/'benchmarks/configs/campaign-development-v1.json').read_bytes())
        manifest=expand(plan)
        diagnostic=next(t['trial_id'] for t in manifest['trials'] if t['phase']=='diagnostic')
        measured=next(t['trial_id'] for t in manifest['trials'] if t['phase']=='measured')
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'absent'
            for trial,options in ((diagnostic,dict(observe_workload=True)),
                    (measured,dict(observe_workload=True,enforce_affinity=True)),
                    (diagnostic,dict(observe_workload=1,enforce_affinity=True))):
                with self.assertRaises(ValueError):
                    run_pilot(plan,manifest,Path(tmp),output,[trial],execute=True,**options)
                self.assertFalse(output.exists())

    def test_unknown_GO_offline_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            output,trials=self.pilot(Path(tmp))
            tid=trials[0]['trial_id'];base=output/tid
            receipt=read_json(base/'0-verify.affinity.json')
            receipt['released']=None;receipt['release']['state']='indeterminate'
            receipt['release']['bytes_written']=None;receipt['release']['confirmed_at']=None
            receipt['release_timestamp']=None;receipt=seal(receipt)
            (base/'0-verify.affinity.json').write_bytes(canonical_json(receipt))
            native=read_json(base/NATIVE);old=read_json(base/BOUND)
            (base/BOUND).write_bytes(canonical_json(bind(native,receipt,old['hardware_sha256'],old['expected_regions'])))
            self.rehash(output)
            with self.assertRaises(ValueError):verify_pilot(output)
            try: report=inspect_recovery(output)
            except ValueError: pass
            else:self.assertNotEqual(next(t['classification'] for t in report['trials'] if t['trial_id']==tid),'verified-complete')

    def test_legacy_affinity_downgrade_cannot_reuse_workload_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            output,trials=self.pilot(Path(tmp))
            tid=trials[0]['trial_id'];base=output/tid
            receipt=read_json(base/'0-verify.affinity.json')
            receipt['schema_version']=1;receipt.pop('release');receipt=seal(receipt)
            (base/'0-verify.affinity.json').write_bytes(canonical_json(receipt))
            native=read_json(base/NATIVE);old=read_json(base/BOUND)
            (base/BOUND).write_bytes(canonical_json(bind(native,receipt,old['hardware_sha256'],old['expected_regions'])))
            self.rehash(output)
            with self.assertRaises(ValueError):verify_pilot(output)
            try: report=inspect_recovery(output)
            except ValueError: pass
            else:self.assertNotEqual(next(t['classification'] for t in report['trials'] if t['trial_id']==tid),'verified-complete')

    def test_resume_renewed_authorization_and_immutable_reuse(self):
        from campaign_resume import resume_pilot, inspect_resume, transaction_path
        with tempfile.TemporaryDirectory() as tmp:
            output,trials=self.pilot(Path(tmp),cut=True)
            before={p:p.read_bytes() for p in output.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(ValueError,'observe-workload'):
                resume_pilot(output,execute=True,authorize=True,enforce_affinity=True)
            with patch('campaign_pilot.inspect',return_value=hardware()), patch('campaign_enforcement.cgroup_ancestry',return_value=groups(self.cpus)):
                report=resume_pilot(output,execute=True,authorize=True,enforce_affinity=True,observe_workload=True)
            self.assertEqual(report['execution_status'],'complete')
            self.assertEqual([t['disposition'] for t in report['trials']],['reused','new'])
            self.assertEqual(before,{p:p.read_bytes() for p in output.rglob('*') if p.is_file()})
            self.assertEqual(inspect_resume(transaction_path(output)),report)
            with self.assertRaises(FileExistsError):
                resume_pilot(output,execute=True,authorize=True,enforce_affinity=True,observe_workload=True)

    def test_resume_cannot_upgrade_legacy_completed_evidence(self):
        from campaign_resume import resume_pilot, transaction_path
        with tempfile.TemporaryDirectory() as tmp:
            output,trials=self.pilot(Path(tmp),observe=False,cut=True)
            with self.assertRaisesRegex(ValueError,'cannot upgrade legacy'):
                resume_pilot(output,execute=True,authorize=True,enforce_affinity=True,observe_workload=True)
            self.assertFalse(transaction_path(output).exists())

    def test_diagnostic_publication_failure_blocks_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            output,trials=self.pilot(Path(tmp),fail=True)
            self.assertEqual(verify_pilot(output)['execution_status'],'failed')
            self.assertTrue(all(t['classification']!='verified-complete' for t in inspect_recovery(output)['trials']))

    def test_migration_and_legacy_receipt(self):
        native,receipt,b=self.samples['two']
        n=copy.deepcopy(native)
        for t in n['regions'][0]['threads']:
            t['entry']['cpu']=self.cpus[0];t['exit']['cpu']=self.cpus[-1]
        validate_native(n,receipt,2,1)
        legacy=copy.deepcopy(receipt);legacy.pop('release');legacy['schema_version']=1;legacy=seal(legacy)
        validate_native(n,legacy,2,1)
        self.assertEqual(classification(n,legacy,2,1)[0],'insufficient_evidence')
        with self.assertRaises(ValueError):verify(bind(n,legacy,'e'*64,1),n,legacy,b,'e'*64,1,True)

    def test_native_publication_failure(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'existing';path.write_text('immutable')
            result=subprocess.run([str(FIXTURE),'one',str(path)],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,2);self.assertEqual(path.read_text(),'immutable')


if __name__=='__main__':unittest.main()
