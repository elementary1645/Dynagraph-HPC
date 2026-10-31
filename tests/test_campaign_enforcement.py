"""Bounded Linux affinity barriers, native syscalls and adversarial evidence controls."""
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'benchmarks/python'))
from campaign_enforcement import (Barrier, POLICY, binding, preflight, permitted, receipt,
                                  seal, verify, observe, validate_ack)
from campaign_process import capture, termination_as_interrupt, LaunchDeadlineExpired
from campaign_provenance import reconcile_cgroups, mounts_for
from workloads import canonical_json, sha256


def groups(cpus, quota='max 100000'):
    g=dict(membership='0::/',mountinfo='11 1 0:9 / /sys/fs/cgroup rw - cgroup2 cgroup rw',
           views=[],effective_cpuset=None,quota_pairs=None,memory_headroom_bytes=None,visibility=None)
    v=mounts_for(g['membership'],g['mountinfo'])[0]
    v['ancestors']=[dict(path='/sys/fs/cgroup',cgroup_path='/',**{'cpu.max':quota,
        'cpuset.cpus.effective':','.join(map(str,cpus)),'memory.max':'max','memory.current':'0'})]
    g['views']=[v];return reconcile_cgroups(g)


@unittest.skipUnless(sys.platform=='linux' and hasattr(os,'sched_getaffinity'),'Linux affinity required')
class EnforcementTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.base=Path(tmp.name)
        self.cpus=[min(os.sched_getaffinity(0))];self.g=groups(self.cpus)
        self.target=self.base/'runner'
        self.target.write_text('#!/usr/bin/python3\nimport os,pathlib\npathlib.Path("marker").write_text(str(sorted(os.sched_getaffinity(0))))\nprint("ok")\n')
        self.target.chmod(0o700)
        self.command=['./runner']
        self.b=dict(attempt_id='d'*64,execution_id='a'*64,trial_id='b'*64,journal_binding_sha256='c'*64,
                    process_index=0,origin=dict(kind='original',attempt_id=None),command=self.command,
                    executable_sha256=sha256(self.target.read_bytes()),workers=1)
        self.request=dict(cpus=self.cpus,binding=self.b)
        # Native affinity and /proc identity stay real; synthetic cgroup hierarchy
        # avoids dependence on CI container topology/quota and remains validated.
        p=patch('campaign_enforcement.cgroup_ancestry',return_value=self.g);p.start();self.addCleanup(p.stop)

    def run_capture(self, **kwargs):
        return capture(self.command,self.base,dict(os.environ),3,4096,
                       enforcement=self.request,**kwargs)

    def good(self):
        p,streams=self.run_capture();self.assertEqual(p['reason'],'exited',streams)
        v=p['_enforcement'];verify(v,self.b,self.cpus,p)
        self.assertEqual((self.base/'marker').read_text(),str(self.cpus))
        return v,p

    def test_native_self_affinity_barrier(self):
        before=sorted(os.sched_getaffinity(0));v,p=self.good()
        self.assertEqual(v['lifecycle'],['requested','validated','application_pending','applied','verified'])
        self.assertEqual(v['acknowledgement']['applied_cpus'],self.cpus)
        self.assertEqual(v['observation']['affinity'],self.cpus)
        self.assertEqual(sorted(os.sched_getaffinity(0)),before)
        for k in ('measurement_eligible','scientific_performance_allowed','execution_authorized'):
            self.assertIs(v[k],False)

    def test_resume_opt_in_requires_exact_boolean_before_io(self):
        from campaign_resume import resume_pilot
        for invalid in (1,0,'no',None,[],{}):
            with patch('campaign_resume.directory_lock',side_effect=AssertionError('touched original')):
                with self.assertRaisesRegex(ValueError,'must be boolean'):
                    resume_pilot(self.base/'absent',execute=True,authorize=True,enforce_affinity=invalid)

    def test_default_launch_is_unchanged(self):
        p,streams=capture(self.command,self.base,dict(os.environ),3,4096)
        self.assertEqual(p['reason'],'exited',streams);self.assertNotIn('_enforcement',p)

    def test_invalid_empty_duplicate_boolean_cpus_before_launch(self):
        for cpus in ([],[True],[-1],[2,2],[2,1],[1048576]):
            self.request['cpus']=cpus
            with patch('campaign_enforcement.subprocess.Popen',side_effect=AssertionError('launched')):
                p,_=self.run_capture()
            self.assertEqual(p['reason'],'launch-error');self.assertFalse((self.base/'marker').exists())

    def test_cpuset_quota_and_online_prelaunch(self):
        for affinity,online,g in (([0],[0],groups([1])),([0],[1],groups([0])),
                                  ([0],[0],groups([0],'99999 100000'))):
            with self.assertRaises(ValueError):permitted([0],1,affinity,online,g)
        with patch('campaign_enforcement.preflight',side_effect=ValueError('CPU became unavailable')):
            with patch('campaign_enforcement.subprocess.Popen',side_effect=AssertionError('launched')):
                p,_=self.run_capture()
        self.assertEqual(p['reason'],'launch-error')

    def test_os_affinity_rejection_ack(self):
        # Parent preflight deliberately accepts a non-existent CPU; actual child
        # syscall must fail and no workload may be released.
        self.request['cpus']=[1048575]
        with patch('campaign_enforcement.preflight'):
            p,_=self.run_capture()
        self.assertEqual(p['reason'],'capture-error');v=p['_enforcement']
        self.assertFalse(v['released']);self.assertNotEqual(v['acknowledgement']['errno'],0)
        verify(v,self.b,[1048575],p);self.assertFalse((self.base/'marker').exists())

    def test_executable_mismatch_no_release(self):
        self.request['binding']['executable_sha256']='f'*64
        with patch('campaign_enforcement.subprocess.Popen',side_effect=AssertionError('launched')):
            p,_=self.run_capture()
        self.assertEqual(p['reason'],'launch-error')
        self.assertFalse(p['_enforcement']['released']);self.assertFalse((self.base/'marker').exists())

    def test_process_identity_pid_start_and_affinity_mismatch(self):
        original=observe
        for key in ('pid','process_start_ticks','affinity'):
            def bad(pid):
                o=original(pid);o[key]=[1048575] if key=='affinity' else o[key]+1;return o
            with patch('campaign_enforcement.observe',side_effect=bad):p,_=self.run_capture()
            self.assertEqual(p['reason'],'capture-error');self.assertFalse(p['_enforcement']['released'])
            self.assertFalse((self.base/'marker').exists())

    def test_cpu_unavailable_or_cgroup_change_during_verification(self):
        original=observe
        for mode in ('online','cpuset','quota'):
            def bad(pid):
                o=original(pid)
                if mode=='online':o['online_cpus']=[1048575]
                elif mode=='cpuset':o['cgroups']=groups([1048575])
                else:o['cgroups']=groups(self.cpus,'1 100000')
                return o
            with patch('campaign_enforcement.observe',side_effect=bad):p,_=self.run_capture()
            self.assertFalse(p['_enforcement']['released']);self.assertFalse((self.base/'marker').exists())

    def test_parent_crash_before_release_eof(self):
        script="""import os,sys,time,select,json
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
from campaign_enforcement import Barrier
with patch('campaign_enforcement.preflight'):
 b=Barrier(json.loads(sys.argv[3]),['./runner'],sys.argv[2],dict(os.environ),time.monotonic()+3)
 b.spawn()
 if not select.select([b.ack],[],[],2)[0]:os._exit(1)
 os.read(b.ack,65536)
 os._exit(0)
"""
        parent=subprocess.run([sys.executable,'-B','-c',script,str(ROOT/'benchmarks/python'),
                               str(self.base),json.dumps(self.request)],capture_output=True,timeout=4)
        self.assertEqual(parent.returncode,0,parent.stderr)
        self.assertFalse((self.base/'marker').exists())

    def test_child_exit_before_ack(self):
        original=subprocess.Popen
        def exit_child(argv,**kwargs):return original([sys.executable,'-I','-c','pass'],**kwargs)
        with patch('campaign_enforcement.subprocess.Popen',side_effect=exit_child):p,_=self.run_capture()
        self.assertEqual(p['reason'],'capture-error');self.assertFalse(p['_enforcement']['released'])
        self.assertFalse((self.base/'marker').exists())

    def test_child_exit_before_verification(self):
        def exited(pid):
            os.kill(pid,signal.SIGKILL);raise ValueError('child exited')
        with patch('campaign_enforcement.observe',side_effect=exited):p,_=self.run_capture()
        self.assertEqual(p['reason'],'capture-error');self.assertFalse((self.base/'marker').exists())

    def test_deadline_before_launch_no_process(self):
        with patch('subprocess.Popen',side_effect=AssertionError('launched')):
            with self.assertRaises(LaunchDeadlineExpired):self.run_capture(deadline=time.monotonic()-1)

    def test_deadlines_at_each_barrier_boundary(self):
        original=Barrier.boundary
        for stage in ('requested','validated','application_pending','applied','verified'):
            def expiry(barrier):
                original(barrier)
                if barrier.value['lifecycle'][-1]==stage:
                    if stage=='application_pending' and barrier.process is None:return
                    raise TimeoutError('controlled boundary expiry')
            with patch.object(Barrier,'boundary',expiry):
                if stage in ('requested','validated'):
                    with self.assertRaises(LaunchDeadlineExpired):self.run_capture()
                    self.assertFalse((self.base/'marker').exists());continue
                p,_=self.run_capture()
            self.assertFalse(p['_enforcement']['released']);self.assertFalse((self.base/'marker').exists())
            self.assertEqual(p['_enforcement']['state'],'indeterminate')
            verify(p['_enforcement'],self.b,self.cpus,p)

    def test_sigterm_during_enforcement(self):
        def terminate(pid):os.kill(os.getpid(),signal.SIGTERM)
        with termination_as_interrupt(),patch('campaign_enforcement.observe',side_effect=terminate):
            p,_=self.run_capture()
        self.assertEqual(p['reason'],'interrupted');self.assertEqual(p['_enforcement']['state'],'interrupted')
        self.assertFalse((self.base/'marker').exists());verify(p['_enforcement'],self.b,self.cpus,p)

    def test_forged_success_without_child_receipt(self):
        v,p=self.good();p['returncode']=None;p['reason']='launch-error'
        with self.assertRaises(ValueError):verify(v,self.b,self.cpus,p)

    def test_native_cgroup_preflight_smoke(self):
        from campaign_hardware import cgroup_ancestry
        with patch('campaign_enforcement.cgroup_ancestry',side_effect=cgroup_ancestry):
            try:preflight(self.cpus,1)
            except (ValueError,OSError,TypeError) as error:self.skipTest('host evidence unavailable: '+str(error))
            self.good()

    def test_executable_changes_before_release(self):
        original=observe
        def changed(pid):
            o=original(pid);self.target.write_text('#!/bin/sh\nexit 0\n');return o
        with patch('campaign_enforcement.observe',side_effect=changed):p,_=self.run_capture()
        self.assertEqual(p['reason'],'capture-error');self.assertFalse(p['_enforcement']['released'])
        self.assertFalse((self.base/'marker').exists())

    def test_rehashed_failure_missing_requested_transition(self):
        with patch('campaign_enforcement.preflight',side_effect=ValueError('controlled rejection')):
            p,_=self.run_capture()
        v=copy.deepcopy(p['_enforcement']);v['lifecycle']=['rejected'];v=seal(v)
        with self.assertRaises(ValueError):verify(v,self.b,self.cpus,p)

    def test_runtime_receipt_identity_cross_binding(self):
        v,p=self.good()
        for snap in (dict(pid=v['acknowledgement']['pid']+1,process_start_ticks=None),
                     dict(pid=v['acknowledgement']['pid'],process_start_ticks=1)):
            with self.assertRaises(ValueError):verify(v,self.b,self.cpus,p,snap)

    def test_fd_cleanup_for_failed_and_successful_barriers(self):
        before=len(list(Path('/proc/self/fd').iterdir()))
        self.good()
        with patch('campaign_enforcement.observe',side_effect=ValueError('controlled failure')):
            self.run_capture()
        self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)

    def test_corrupted_ack_never_releases(self):
        with patch('campaign_enforcement.load_bytes',side_effect=ValueError('corrupted ack')):
            p,_=self.run_capture()
        self.assertEqual(p['reason'],'capture-error');self.assertFalse((self.base/'marker').exists())

    def test_rehashed_contradictions_versions_and_bindings(self):
        v,p=self.good()
        changes=[lambda x:x.update(schema_version=True),lambda x:x.update(schema_version=2),
                 lambda x:x.update(measurement_eligible=True),lambda x:x.update(released=False),
                 lambda x:x['binding'].update(trial_id='f'*64),
                 lambda x:x['binding'].update(execution_id='f'*64),
                 lambda x:x['binding'].update(attempt_id='f'*64),
                 lambda x:x['binding']['origin'].update(attempt_id='f'*64),
                 lambda x:x['observation'].update(pid=x['observation']['pid']+1),
                 lambda x:x['observation'].update(process_start_ticks=1),
                 lambda x:x['observation'].update(affinity=[1048575]),
                 lambda x:x['acknowledgement'].update(executable_sha256='f'*64),
                 lambda x:x.update(acknowledgement=None),lambda x:x.update(observation=None),
                 lambda x:x.update(lifecycle=['requested','verified']),
                 lambda x:x.update(release_timestamp='2000-01-01T00:00:00+00:00')]
        for change in changes:
            x=copy.deepcopy(v);change(x);x=seal(x)
            with self.assertRaises((ValueError,TypeError,KeyError)):verify(x,self.b,self.cpus,p)
        x=copy.deepcopy(v);x['evidence_sha256']='f'*64
        with self.assertRaises(ValueError):verify(x,self.b,self.cpus,p)


@unittest.skipUnless(sys.platform=='linux' and hasattr(os,'sched_getaffinity'),'Linux required')
class PilotIntegrationTests(unittest.TestCase):
    def setUp(self):
        from test_campaign_resume import ResumeTests
        from campaign_contract import expand
        self.f=ResumeTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.cpus=sorted(os.sched_getaffinity(0))[:2]
        if len(self.cpus)<2:self.skipTest('two permitted CPUs required by bounded pilot fixture')
        self.f.plan['hardware']['allocated_cpus']=self.cpus
        self.f.manifest=expand(self.f.plan);self.f.ids=[t['trial_id'] for t in self.f.manifest['trials'][:3]]
        p=patch('campaign_enforcement.cgroup_ancestry',return_value=groups(self.cpus));p.start();self.addCleanup(p.stop)

    def start(self):
        from campaign_pilot import run_pilot
        f=self.f
        return run_pilot(f.plan,f.manifest,f.root,f.out,f.ids,execute=True,max_trials=3,enforce_affinity=True)

    def test_enforced_pilot_and_offline_verification(self):
        from campaign_pilot import verify_pilot
        self.assertEqual(self.start()['status'],'complete');f=self.f
        self.assertEqual(verify_pilot(f.out)['execution_status'],'complete')
        self.assertEqual(len(f.marks()),3)
        for path in f.out.glob('*/*.affinity.json'):
            v=json.loads(path.read_bytes());self.assertTrue(v['released']);self.assertFalse(v['measurement_eligible'])

    def test_no_output_or_child_on_prevalidation_failure(self):
        with patch('campaign_enforcement.preflight',side_effect=ValueError('outside cpuset')):
            with self.assertRaises(ValueError):self.start()
        self.assertFalse(self.f.out.exists());self.assertEqual(self.f.marks(),[])

    def test_failed_enforcement_never_successful_trial(self):
        from campaign_pilot import verify_pilot
        with patch('campaign_enforcement.observe',side_effect=ValueError('identity contradiction')):
            result=self.start()
        self.assertEqual(result['status'],'failed');self.assertEqual(self.f.marks(),[])
        self.assertEqual(verify_pilot(self.f.out)['execution_status'],'failed')

    def test_enforced_resume_is_explicit_single_use_and_original_immutable(self):
        from campaign_journal import Journal
        from campaign_resume import resume_pilot, inspect_resume
        from campaign_pilot import verify_pilot
        f=self.f;original=Journal.finish;count=[0]
        def cut(j,r):
            original(j,r);count[0]+=1
            if count[0]==1:raise RuntimeError('bounded crash')
        with patch.object(Journal,'finish',cut):
            with self.assertRaises(RuntimeError):self.start()
        before=f.snapshot()
        with self.assertRaises(ValueError):resume_pilot(f.out,execute=True,authorize=True)
        result=resume_pilot(f.out,execute=True,authorize=True,enforce_affinity=True)
        self.assertEqual(result['execution_status'],'complete');self.assertEqual(f.snapshot(),before)
        self.assertEqual(len(f.marks()),3);self.assertEqual(inspect_resume(f.attempt),result)
        self.assertEqual(verify_pilot(f.attempt/'pilot')['trials'],2)
        with self.assertRaises(FileExistsError):resume_pilot(f.out,execute=True,authorize=True,enforce_affinity=True)
        self.assertEqual(len(f.marks()),3);self.assertEqual(f.snapshot(),before)
        paths=list((f.attempt/'pilot').glob('*/*.affinity.json'));self.assertTrue(paths)
        for p in paths:self.assertEqual(json.loads(p.read_bytes())['binding']['origin']['attempt_id'],result['attempt_id'])

    def test_rehashed_receipt_trial_and_journal_reject(self):
        from campaign_pilot import verify_pilot
        self.start();f=self.f;p=next(f.out.glob('*/*.affinity.json'));v=json.loads(p.read_bytes())
        v['observation']['affinity']=[1048575];p.write_bytes(canonical_json(seal(v)))
        # Rehash all containing indexes: semantic verification remains decisive.
        record_path=p.parent/'record.json';record=json.loads(record_path.read_bytes());record['artifacts'][p.name]=sha256(p.read_bytes());record_path.write_bytes(canonical_json(record))
        inventory={p.relative_to(f.out).as_posix():sha256(p.read_bytes()) for p in f.out.rglob('*') if p.is_file() and p!=f.out/'sha256.json'}
        (f.out/'sha256.json').write_bytes(canonical_json(inventory))
        with self.assertRaises(ValueError):verify_pilot(f.out)


if __name__=='__main__':unittest.main(verbosity=2)
