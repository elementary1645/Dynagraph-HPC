"""Bounded Linux affinity barriers, native syscalls and adversarial evidence controls."""
import copy
import errno
from contextlib import contextmanager
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
from campaign_process import (capture, termination_as_interrupt, LaunchDeadlineExpired,
                              defer_cleanup_signals, OwnedProcessTeardown, CaptureSignals)
from campaign_provenance import reconcile_cgroups, mounts_for
from workloads import canonical_json, sha256


def groups(cpus, quota='max 100000'):
    g=dict(membership='0::/',mountinfo='11 1 0:9 / /sys/fs/cgroup rw - cgroup2 cgroup rw',
           views=[],effective_cpuset=None,quota_pairs=None,memory_headroom_bytes=None,visibility=None)
    v=mounts_for(g['membership'],g['mountinfo'])[0]
    v['ancestors']=[dict(path='/sys/fs/cgroup',cgroup_path='/',**{'cpu.max':quota,
        'cpuset.cpus.effective':','.join(map(str,cpus)),'memory.max':'max','memory.current':'0'})]
    g['views']=[v];return reconcile_cgroups(g)


INVALID_STREAMS=('coalesced','split','delayed_failure','whitespace','trailing',
                 'held_writer','inherited_writer','partial','oversized','malformed',
                 'exit_after_ack','broken_ack','broken_gate')


def launcher_source(mode):
    source=(ROOT/'benchmarks/python/campaign_affinity_child.py').read_text()
    anchor="    raw = (json.dumps(message, sort_keys=True, separators=(',', ':'))+'\\n').encode()"
    additions={'coalesced':"raw=raw+raw", 'split':"raw=raw+raw",
               'whitespace':"raw+=b' '", 'trailing':"raw+=b'x'",
               'partial':"raw=raw[:len(raw)//2]", 'oversized':"raw=b'x'*65537",
               'malformed':"raw=b'{bad}\\n'", 'broken_ack':"raw=b''"}
    if mode in additions:source=source.replace(anchor,anchor+'\n    '+additions[mode])
    if mode in ('split','partial_writes'):source=source.replace('os.write(ack, raw)','os.write(ack, raw[:1])')
    if mode=='delayed_failure':
        source=source.replace('    while raw:', '    saved=raw\n    while raw:')
        source=source.replace('    os.close(ack)', "    time.sleep(.03)\n    bad=json.loads(saved)\n    bad['error']='second failure'\n    bad['errno']=22\n    os.write(ack,(json.dumps(bad)+'\\n').encode())\n    os.close(ack)")
    if mode=='held_writer':source=source.replace('    os.close(ack)','    time.sleep(2)\n    os.close(ack)')
    if mode=='inherited_writer':
        source=source.replace('    os.close(ack)', "    if os.fork()==0:\n        time.sleep(2)\n        os._exit(0)\n    os.close(ack)")
    if mode=='broken_gate':
        source=source.replace(anchor,'    os.close(gate)\n'+anchor)
        source=source.replace("    try:\n        if os.read(gate, 1)","    time.sleep(2)\n    try:\n        if os.read(gate, 1)")
    if mode=='exit_after_ack':source=source.replace('    os.close(ack)','    os.close(ack)\n    os._exit(125)')
    return source


def wait_exited_without_reaping(child, timeout=2):
    stop=time.monotonic()+timeout
    while os.waitid(os.P_PID,child.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT) is None:
        if time.monotonic()>=stop:raise subprocess.TimeoutExpired(child.args,timeout)
        time.sleep(.005)


@contextmanager
def faulty_launcher(directory, mode):
    helper=directory/(mode+'-launcher.py');helper.write_text(launcher_source(mode))
    popen=subprocess.Popen;children=[]
    def spawn(argv,**kwargs):
        argv=list(argv)
        if len(argv)>4 and argv[4].endswith('campaign_affinity_child.py'):argv[4]=str(helper)
        child=popen(argv,**kwargs);children.append(child)
        if mode=='exit_after_ack':wait_exited_without_reaping(child)  # Dead, still owned.
        return child
    try:
        with patch('campaign_enforcement.subprocess.Popen',side_effect=spawn):yield children
    finally:
        for child in children:
            if child.poll() is None:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait(timeout=2)
            for stream in (child.stdout,child.stderr):
                if stream is not None:stream.close()


def reap_fixture_child(child):
    if child.poll() is None:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait(timeout=2)
    for stream in (child.stdout,child.stderr):
        if stream is not None:stream.close()


def track_fixture_children(test):
    spawn=Barrier.spawn
    def tracked(barrier):
        try:return spawn(barrier)
        finally:
            if barrier.process is not None:test.addCleanup(reap_fixture_child,barrier.process)
    tracker=patch.object(Barrier,'spawn',tracked);tracker.start();test.addCleanup(tracker.stop)


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
        track_fixture_children(self)

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
        changes=[lambda x:x.update(schema_version=True),lambda x:x.update(schema_version=3),
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

    def test_acknowledgement_stream_framing_before_GO(self):
        for mode in INVALID_STREAMS:
            with self.subTest(mode=mode),faulty_launcher(self.base,mode) as children:
                p,_=capture(self.command,self.base,dict(os.environ),.15,4096,enforcement=self.request)
                self.assertNotEqual(p['reason'],'exited')
                if mode in ('held_writer','inherited_writer'):
                    self.assertEqual(p['reason'],'timeout');self.assertEqual(p['_enforcement']['state'],'indeterminate')
                self.assertFalse(p['_enforcement']['released']);self.assertNotEqual(p['_enforcement']['state'],'verified')
                self.assertFalse((self.base/'marker').exists());verify(p['_enforcement'],self.b,self.cpus,p)
                for child in children:
                    self.assertIsNotNone(child.returncode)
                    with self.assertRaises(ChildProcessError):os.waitpid(child.pid,os.WNOHANG)

    def test_partial_writes_with_single_EOF_acknowledgement(self):
        with faulty_launcher(self.base,'partial_writes'):
            self.good()

    def test_close_idempotent_already_closed_and_reused_descriptor(self):
        b=Barrier(self.request,self.command,self.base,dict(os.environ),time.monotonic()+1)
        fd=os.open(self.target,os.O_RDONLY);b.own(fd);os.close(fd);b.close();b.close()
        fd=os.open(self.target,os.O_RDONLY);b.own(fd);os.close(fd)
        other=self.base/'other';other.write_text('different inode')
        replacement=os.open(other,os.O_RDONLY)
        try:
            self.assertEqual(replacement,fd)
            with self.assertRaises(OSError) as error:b.close()
            self.assertEqual(error.exception.errno,errno.ESTALE)
            b.close();os.fstat(replacement)
        finally:os.close(replacement)

    def test_close_failure_reported_once_and_remaining_fds_closed(self):
        b=Barrier(self.request,self.command,self.base,dict(os.environ),time.monotonic()+1)
        first=os.open(self.target,os.O_RDONLY);second=os.open(self.target,os.O_RDONLY)
        b.own(first);b.own(second);close=os.close;calls=[]
        def failure(fd):
            calls.append(fd);close(fd)
            if fd==first:raise OSError(errno.EIO,'injected close failure after kernel release')
        with patch('os.close',side_effect=failure):
            with self.assertRaisesRegex(OSError,'injected close failure'):b.close()
            b.close()
        self.assertEqual(calls.count(first),1);self.assertEqual(calls.count(second),1)
        self.assertEqual(b.fds,[])
        for fd in (first,second):
            with self.assertRaises(OSError):os.fstat(fd)

    def test_SIGTERM_at_release_close_ownership_boundary(self):
        self.target.write_text('#!/usr/bin/python3\nimport time,pathlib\ntime.sleep(5)\npathlib.Path("late").write_text("ran")\ntime.sleep(2)\n')
        self.b['executable_sha256']=sha256(self.target.read_bytes());close=os.close;original=Barrier.verify_and_release;state={}
        def armed(b,child):state.update(barrier=b,child=child);return original(b,child)
        def terminate(fd):
            close(fd);b=state.get('barrier')
            if b is not None and fd==b.gate and b.value['released'] and not state.get('sent'):
                state['sent']=True;os.kill(os.getpid(),signal.SIGTERM)
        with termination_as_interrupt(),patch.object(Barrier,'verify_and_release',armed),patch('os.close',side_effect=terminate):
            p,_=self.run_capture()
        self.assertTrue(state['sent']);self.assertEqual(p['reason'],'interrupted')
        self.assertIsNotNone(state['child'].returncode)
        with self.assertRaises(ChildProcessError):os.waitpid(state['child'].pid,os.WNOHANG)
        time.sleep(.3);self.assertFalse((self.base/'late').exists())
        # GO was genuinely sent before interruption; retain that fact without
        # turning interrupted process execution into a successful completion.
        self.assertTrue(p['_enforcement']['released']);verify(p['_enforcement'],self.b,self.cpus,p)

    def test_cleanup_failures_cannot_skip_kill_or_reap(self):
        original=Barrier.verify_and_release;state={}
        def failed(b,child):state.update(barrier=b,child=child);raise RuntimeError('original failure')
        with patch.object(Barrier,'verify_and_release',failed),patch.object(Barrier,'close',side_effect=OSError(errno.EIO,'cleanup failure')):
            try:
                with self.assertRaisesRegex(RuntimeError,'original failure') as caught:self.run_capture()
                self.assertIsInstance(caught.exception.__cause__,OSError)
                self.assertIsNotNone(state['child'].returncode)
                with self.assertRaises(ChildProcessError):os.waitpid(state['child'].pid,os.WNOHANG)
                self.assertFalse((self.base/'marker').exists())
            finally:
                # Bypass the patched class method using the real owned-fd API.
                for fd in tuple(state['barrier'].fds):state['barrier'].close_fd(fd)

    def test_unrelated_cleanup_error_reported_after_reaping(self):
        self.target.write_text('#!/usr/bin/python3\nimport time,pathlib\ntime.sleep(5)\npathlib.Path("late").write_text("ran")\ntime.sleep(2)\n')
        self.b['executable_sha256']=sha256(self.target.read_bytes())
        state={};spawn=Barrier.spawn;close=Barrier.close
        def spawned(b):
            child=spawn(b);state.update(child=child,barrier=b);return child
        def failure(b):close(b);raise OSError(errno.EIO,'visible cleanup failure')
        with patch.object(Barrier,'spawn',spawned),patch.object(Barrier,'close',failure):
            with self.assertRaisesRegex(OSError,'visible cleanup failure'):
                capture(self.command,self.base,dict(os.environ),.1,4096,enforcement=self.request)
        self.assertIsNotNone(state['child'].returncode)
        with self.assertRaises(ChildProcessError):os.waitpid(state['child'].pid,os.WNOHANG)

    def test_parent_pipe_close_failure_is_a_launched_process_failure(self):
        original=Barrier.close_fd;state={}
        def failed(b,fd):
            original(b,fd)
            if b.process is not None and not b.value['released'] and not state.get('failed'):
                state.update(failed=True,child=b.process)
                raise OSError(errno.EIO,'parent writer close failure')
        with patch.object(Barrier,'close_fd',failed):p,_=self.run_capture()
        self.assertTrue(state['failed']);self.assertEqual(p['reason'],'capture-error')
        self.assertIsNotNone(p['returncode']);self.assertIsNotNone(state['child'].returncode)
        self.assertFalse(p['_enforcement']['released']);self.assertFalse((self.base/'marker').exists())
        verify(p['_enforcement'],self.b,self.cpus,p)
        with self.assertRaises(ChildProcessError):os.waitpid(state['child'].pid,os.WNOHANG)

    def test_child_inherits_original_signal_mask(self):
        expected=sorted(int(s) for s in signal.pthread_sigmask(signal.SIG_BLOCK,[]))
        self.target.write_text('#!/usr/bin/python3\nimport signal,json\nprint(json.dumps(sorted(int(s) for s in signal.pthread_sigmask(signal.SIG_BLOCK,[]))))\n')
        self.b['executable_sha256']=sha256(self.target.read_bytes())
        p,streams=self.run_capture()
        self.assertEqual(p['reason'],'exited');self.assertEqual(json.loads(streams['stdout']),expected)
        self.assertEqual(sorted(int(s) for s in signal.pthread_sigmask(signal.SIG_BLOCK,[])),expected)

    def test_cleanup_wait_is_explicitly_bounded(self):
        original=Barrier.spawn;calls=[]
        def spawned(b):
            child=original(b);wait=child.wait
            def bounded_wait(*args,**kwargs):
                calls.append(kwargs);return wait(*args,**kwargs)
            child.wait=bounded_wait;return child
        with patch.object(Barrier,'spawn',spawned):self.good()
        self.assertEqual(len(calls),1);self.assertGreater(calls[0]['timeout'],0);self.assertLessEqual(calls[0]['timeout'],2)

    def test_interruption_preserved_with_secondary_cleanup_error(self):
        original_close=Barrier.close;state={};spawn=Barrier.spawn
        def spawned(b):
            child=spawn(b);state['child']=child;return child
        def interrupted(pid):os.kill(os.getpid(),signal.SIGTERM)
        def failed(b):original_close(b);raise OSError(errno.EIO,'secondary cleanup failure')
        with termination_as_interrupt(),patch.object(Barrier,'spawn',spawned),patch.object(Barrier,'close',failed):
            with self.assertRaises(KeyboardInterrupt) as caught:self.run_capture(runtime_observer=interrupted)
        self.assertIsInstance(caught.exception.__cause__,OSError)
        self.assertIsNotNone(state['child'].returncode)
        with self.assertRaises(ChildProcessError):os.waitpid(state['child'].pid,os.WNOHANG)

    def test_signal_handler_reused_gate_fd_remains_open(self):
        target=self.base/'unrelated';target.write_text('owned by caller')
        original=Barrier.verify_and_release;close=os.close;state={}
        def armed(b,child):state.update(barrier=b,child=child);return original(b,child)
        def handler(signum,frame):
            fd=os.open(target,os.O_RDONLY);gate=state['barrier'].gate
            if fd!=gate:os.dup2(fd,gate);close(fd)
            state['replacement']=gate
            raise KeyboardInterrupt('controlled SIGTERM')
        def closed(fd):
            close(fd);b=state.get('barrier')
            if b is not None and fd==b.gate and b.value['released'] and not state.get('sent'):
                state['sent']=True;os.kill(os.getpid(),signal.SIGTERM)
        previous=signal.signal(signal.SIGTERM,handler)
        try:
            with patch.object(Barrier,'verify_and_release',armed),patch('os.close',side_effect=closed):p,_=self.run_capture()
            self.assertEqual(p['reason'],'interrupted');self.assertTrue(state['sent'])
            os.fstat(state['replacement']);self.assertIsNotNone(state['child'].returncode)
        finally:
            signal.signal(signal.SIGTERM,previous)
            if 'replacement' in state:close(state['replacement'])

    def test_receipt_sealing_failure_cannot_skip_reap(self):
        state={};original=Barrier.spawn
        def spawned(b):
            child=original(b);state['child']=child;return child
        with patch.object(Barrier,'spawn',spawned),patch('campaign_enforcement.seal',side_effect=ValueError('seal failure')):
            with self.assertRaisesRegex(ValueError,'seal failure'):self.run_capture()
        self.assertIsNotNone(state['child'].returncode)
        with self.assertRaises(ChildProcessError):os.waitpid(state['child'].pid,os.WNOHANG)
        self.assertFalse((self.base/'marker').exists())

    def test_SIGTERM_during_ack_verification_and_before_release(self):
        original=Barrier.boundary
        for stage in ('application_pending','applied','verified'):
            sent=[False]
            def terminate(b):
                original(b)
                if b.process is not None and b.value['lifecycle'][-1]==stage and not sent[0]:
                    sent[0]=True;os.kill(os.getpid(),signal.SIGTERM)
            with termination_as_interrupt(),patch.object(Barrier,'boundary',terminate):p,_=self.run_capture()
            self.assertTrue(sent[0]);self.assertEqual(p['reason'],'interrupted')
            self.assertFalse(p['_enforcement']['released']);self.assertNotEqual(p['_enforcement']['state'],'verified')
            self.assertFalse((self.base/'marker').exists());verify(p['_enforcement'],self.b,self.cpus,p)

    def test_SIGTERM_during_execution_and_during_cleanup(self):
        self.target.write_text('#!/usr/bin/python3\nimport time,pathlib\ntime.sleep(5)\npathlib.Path("late").write_text("ran")\ntime.sleep(2)\n')
        self.b['executable_sha256']=sha256(self.target.read_bytes())
        for stage in ('execution','cleanup'):
            state={};original_spawn=Barrier.spawn;original_close=Barrier.close
            def spawned(b):
                child=original_spawn(b);state['child']=child;return child
            def closed(b):
                original_close(b)
                if stage=='cleanup':os.kill(os.getpid(),signal.SIGTERM)
            def observer(pid):
                if stage=='execution':os.kill(os.getpid(),signal.SIGTERM)
                else:raise ValueError('controlled transition into cleanup')
            with termination_as_interrupt(),patch.object(Barrier,'spawn',spawned),patch.object(Barrier,'close',closed):
                p,_=self.run_capture(runtime_observer=observer)
            self.assertEqual(p['reason'],'interrupted');self.assertIsNotNone(state['child'].returncode)
            with self.assertRaises(ChildProcessError):os.waitpid(state['child'].pid,os.WNOHANG)
        time.sleep(.3);self.assertFalse((self.base/'late').exists())

    def delayed_target(self):
        self.target.write_text('#!/usr/bin/python3\nimport time,pathlib\ntime.sleep(.3)\npathlib.Path("late").write_text("ran")\ntime.sleep(2)\n')
        self.b['executable_sha256']=sha256(self.target.read_bytes())

    def test_R2_exact_cleanup_entry_signals_and_mask_boundaries(self):
        self.delayed_target()
        code=defer_cleanup_signals.__wrapped__.__code__
        for sig in (signal.SIGINT,signal.SIGTERM):
            for boundary in ('entry','before_mask','after_mask'):
                state={};old_trace=sys.gettrace()
                old_mask=signal.pthread_sigmask(signal.SIG_BLOCK,[])
                old_handlers={s:signal.getsignal(s) for s in (signal.SIGINT,signal.SIGTERM)}
                def trace(frame,event,arg):
                    caller=frame.f_back.f_back if frame.f_back else None
                    if frame.f_code is code and event=='line' and caller is not None and caller.f_code is capture.__code__:
                        masked=bool(signal.pthread_sigmask(signal.SIG_BLOCK,[]) & {sig})
                        if not state.get('sent') and (boundary=='entry' or
                                (boundary=='before_mask' and frame.f_locals.get('previous','absent') is None) or
                                (boundary=='after_mask' and masked)):
                            state['sent']=True
                            os.kill(os.getpid(),sig);os.kill(os.getpid(),sig)
                    return trace
                try:
                    sys.settrace(trace)
                    p,_=self.run_capture(runtime_observer=lambda pid:(_ for _ in ()).throw(ValueError('cleanup')))
                finally:sys.settrace(old_trace)
                self.assertTrue(state.get('sent'),boundary);self.assertEqual(p['reason'],'interrupted')
                self.assertIsNotNone(p['returncode']);verify(p['_enforcement'],self.b,self.cpus,p)
                self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK,[]),old_mask)
                self.assertEqual({s:signal.getsignal(s) for s in old_handlers},old_handlers)
        time.sleep(.35);self.assertFalse((self.base/'late').exists())

    def test_cleanup_context_entry_exception_runs_fallback(self):
        self.delayed_target();original=defer_cleanup_signals;state={}
        @contextmanager
        def interrupted_entry():
            if not state.get('sent') and sys._getframe(2).f_code is capture.__code__:
                state['sent']=True
                raise KeyboardInterrupt('before mask')
            with original():yield
        with patch('campaign_process.defer_cleanup_signals',interrupted_entry):
            p,_=self.run_capture(runtime_observer=lambda pid:(_ for _ in ()).throw(ValueError('cleanup')))
        self.assertTrue(state.get('sent'));self.assertEqual(p['reason'],'interrupted');self.assertIsNotNone(p['returncode'])
        time.sleep(.35);self.assertFalse((self.base/'late').exists())

    def test_repeated_signals_during_kill_and_wait(self):
        self.delayed_target()
        for sig in (signal.SIGINT,signal.SIGTERM):
            for stage in ('kill','wait'):
                kill=os.killpg;spawn=Barrier.spawn;sent=[]
                def requested():
                    sent.append(True)
                    for _ in range(3):os.kill(os.getpid(),sig)
                def killed(pid,signum):
                    if stage=='kill':requested()
                    return kill(pid,signum)
                def spawned(b):
                    child=spawn(b);wait=child.wait
                    def waited(*args,**kwargs):
                        if stage=='wait':requested()
                        return wait(*args,**kwargs)
                    child.wait=waited;return child
                with patch('os.killpg',side_effect=killed),patch.object(Barrier,'spawn',spawned):
                    p,_=self.run_capture(runtime_observer=lambda pid:(_ for _ in ()).throw(ValueError('cleanup')))
                self.assertTrue(sent);self.assertEqual(p['reason'],'interrupted');self.assertIsNotNone(p['returncode'])
        time.sleep(.35);self.assertFalse((self.base/'late').exists())

    def test_teardown_twice_and_concurrent_exit_keep_pid_until_signal(self):
        child=subprocess.Popen([sys.executable,'-c','pass'],start_new_session=True)
        self.addCleanup(reap_fixture_child,child)
        wait_exited_without_reaping(child)
        teardown=OwnedProcessTeardown(child);kill=os.killpg
        with patch('os.killpg',wraps=kill) as calls:
            teardown.run();teardown.run()
        self.assertEqual(calls.call_count,1);self.assertTrue(teardown.finished);self.assertTrue(teardown.reaped)
        with self.assertRaises(ChildProcessError):os.waitpid(child.pid,os.WNOHANG)

    def test_teardown_already_reaped_never_signals_group(self):
        for external in (False,True):
            child=subprocess.Popen([sys.executable,'-c','pass'],start_new_session=True)
            self.addCleanup(reap_fixture_child,child)
            if external:
                wait_exited_without_reaping(child);os.waitpid(child.pid,os.WNOHANG)
            else:child.wait(timeout=2)
            teardown=OwnedProcessTeardown(child)
            with patch('os.killpg',side_effect=AssertionError('lost ownership')):
                with self.assertRaises(ChildProcessError):teardown.run()
                teardown.run()
            self.assertTrue(teardown.failed)

    def test_changed_group_identity_never_signals(self):
        child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(2)'],start_new_session=True)
        self.addCleanup(reap_fixture_child,child)
        with patch('os.getpgid',return_value=child.pid+1),patch('os.killpg',side_effect=AssertionError('wrong group')):
            with self.assertRaises(ChildProcessError):OwnedProcessTeardown(child).run()

    def test_R2_signals_during_GO_and_after_success_before_ledger(self):
        for sig in (signal.SIGINT,signal.SIGTERM):
            for stage in ('during','after'):
                state={};original=Barrier.verify_and_release;write=os.write
                def armed(b,child):state['barrier']=b;return original(b,child)
                def sending(fd,data):
                    b=state.get('barrier')
                    if b is None or fd!=b.gate:return write(fd,data)
                    if stage=='during':os.kill(os.getpid(),sig)
                    n=write(fd,data)
                    if stage=='after':os.kill(os.getpid(),sig)
                    return n
                with patch.object(Barrier,'verify_and_release',armed),patch('os.write',side_effect=sending):p,_=self.run_capture()
                v=p['_enforcement'];self.assertEqual(p['reason'],'interrupted');self.assertIs(v['released'],True)
                self.assertEqual(v['release']['state'],'confirmed_sent');verify(v,self.b,self.cpus,p)

    def test_signal_immediately_before_GO_prevents_write(self):
        for sig in (signal.SIGINT,signal.SIGTERM):
            boundary=Barrier.boundary;sent=[];write=os.write
            def requested(b):
                boundary(b)
                if b.value['lifecycle'][-1]=='verified' and not sent:
                    sent.append(True);os.kill(os.getpid(),sig)
            with patch.object(Barrier,'boundary',requested),patch('os.write',wraps=write) as writes:p,_=self.run_capture()
            self.assertTrue(sent);self.assertEqual(p['reason'],'interrupted');self.assertFalse(writes.called)
            self.assertEqual(p['_enforcement']['release']['state'],'not_attempted');verify(p['_enforcement'],self.b,self.cpus,p)
            self.assertFalse((self.base/'marker').exists())

    def test_GO_known_failed_and_uncertain_IO_no_retry(self):
        for mode in ('EPIPE','EBADF','EAGAIN','EINTR','EIO','short','unknown','delivered_then_EIO'):
            state={};original=Barrier.verify_and_release;write=os.write;calls=[]
            def armed(b,child):state['barrier']=b;return original(b,child)
            def failed(fd,data):
                b=state.get('barrier')
                if b is None or fd!=b.gate:return write(fd,data)
                calls.append(True)
                if mode=='short':return 0
                if mode=='unknown':raise KeyboardInterrupt('unknown write outcome')
                if mode=='delivered_then_EIO':write(fd,data);raise OSError(errno.EIO,'after delivery')
                raise OSError(getattr(errno,mode),'injected GO failure')
            with patch.object(Barrier,'verify_and_release',armed),patch('os.write',side_effect=failed):p,_=self.run_capture()
            v=p['_enforcement'];uncertain=mode in ('EINTR','EIO','unknown','delivered_then_EIO')
            self.assertEqual(len(calls),1);self.assertIs(v['released'],None if uncertain else False)
            self.assertEqual(v['release']['state'],'indeterminate' if uncertain else 'not_sent')
            self.assertIsNone(v['release_timestamp']);self.assertNotEqual(p['reason'],'exited');verify(v,self.b,self.cpus,p)
            bad=copy.deepcopy(v);bad['release']['attempted_at']=bad['observation']['start']
            with self.assertRaises(ValueError):verify(seal(bad),self.b,self.cpus,p)
            self.assertFalse(v['measurement_eligible'])
            if mode!='delivered_then_EIO':self.assertFalse((self.base/'marker').exists())
            (self.base/'marker').unlink(missing_ok=True)

    def test_GO_child_exit_and_unexpected_closed_control_fd(self):
        for mode in ('child_exit','closed_gate'):
            original=Barrier.boundary;state={}
            def failed(b):
                original(b)
                if b.value['lifecycle'][-1]=='verified' and not state:
                    state['sent']=True
                    if mode=='child_exit':
                        os.kill(b.process.pid,signal.SIGKILL)
                        wait_exited_without_reaping(b.process)
                    else:os.close(b.gate)
            with patch.object(Barrier,'boundary',failed):p,_=self.run_capture()
            self.assertEqual(p['_enforcement']['release']['state'],'not_sent')
            self.assertIs(p['_enforcement']['released'],False);verify(p['_enforcement'],self.b,self.cpus,p)
            self.assertFalse((self.base/'marker').exists())

    def test_signal_during_handler_handoff_is_not_lost(self):
        original=CaptureSignals.restore
        for sig in (signal.SIGINT,signal.SIGTERM):
            handlers={s:signal.getsignal(s) for s in (signal.SIGINT,signal.SIGTERM)}
            mask=signal.pthread_sigmask(signal.SIG_BLOCK,[])
            def requested(guard):
                os.kill(os.getpid(),sig)
                return original(guard)
            with patch.object(CaptureSignals,'restore',requested):p,_=self.run_capture()
            self.assertEqual(p['reason'],'interrupted');self.assertIsNotNone(p['returncode'])
            self.assertEqual({s:signal.getsignal(s) for s in handlers},handlers)
            self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK,[]),mask)
            verify(p['_enforcement'],self.b,self.cpus,p)

    def test_legacy_v1_and_strict_v2_release_reconciliation(self):
        v,p=self.good();legacy=copy.deepcopy(v);legacy.pop('release');legacy['schema_version']=1
        verify(seal(legacy),self.b,self.cpus,p)
        for mutation in (lambda x:x['release'].update(attempted_at=x['observation']['start']),
                         lambda x:x['release'].update(state='attempted'),
                         lambda x:x['release'].update(bytes_written=True),
                         lambda x:x['release'].update(confirmed_at=None),
                         lambda x:x['release'].update(errno=errno.EPIPE),
                         lambda x:x.update(released=None),
                         lambda x:x['release'].update(state='not_sent')):
            bad=copy.deepcopy(v);mutation(bad)
            with self.assertRaises((ValueError,TypeError)):verify(seal(bad),self.b,self.cpus,p)

    def test_signal_during_final_serialization_keeps_release_and_reaps(self):
        import campaign_enforcement as ce
        sealing=ce.seal;state={}
        def signaled(value):
            if value['release']['state']=='confirmed_sent' and value['release_timestamp'] is not None and not state:
                state['sent']=True;os.kill(os.getpid(),signal.SIGTERM)
            return sealing(value)
        # Candidate sealing is pre-GO; inject only in capture's final serialization.
        def final(value):
            frame=sys._getframe(1)
            while frame is not None:
                if frame.f_code.co_name=='record_enforcement':return signaled(value)
                frame=frame.f_back
            return sealing(value)
        with patch('campaign_enforcement.seal',side_effect=final):p,_=self.run_capture()
        self.assertTrue(state);self.assertEqual(p['reason'],'interrupted');self.assertIsNotNone(p['returncode'])
        self.assertTrue(p['_enforcement']['released']);verify(p['_enforcement'],self.b,self.cpus,p)


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
        track_fixture_children(self)

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

    def test_invalid_acknowledgements_never_complete_or_resume(self):
        from campaign_pilot import verify_pilot
        from campaign_resume import resume_pilot,transaction_path
        from campaign_journal import inspect_recovery
        f=self.f
        for mode in INVALID_STREAMS:
            f.out=f.base/('pilot-'+mode);f.attempt=transaction_path(f.out)
            from campaign_pilot import run_pilot
            with self.subTest(mode=mode),faulty_launcher(f.base,mode):
                result=run_pilot(f.plan,f.manifest,f.root,f.out,f.ids,execute=True,max_trials=3,
                                 enforce_affinity=True,timeout=1)
            self.assertEqual(result['status'],'failed');self.assertEqual(f.marks(),[])
            self.assertEqual(verify_pilot(f.out)['execution_status'],'failed')
            recovery=inspect_recovery(f.out)
            self.assertNotIn('verified-complete',{t['classification'] for t in recovery['trials']})
            before=f.snapshot()
            with self.assertRaises(ValueError):resume_pilot(f.out,execute=True,authorize=True,enforce_affinity=True)
            self.assertEqual(f.snapshot(),before);self.assertEqual(f.marks(),[])

    def test_R2_post_GO_signal_keeps_release_without_completion(self):
        from campaign_pilot import verify_pilot
        original=Barrier.verify_and_release;write=os.write;state={}
        def armed(b,child):state['barrier']=b;return original(b,child)
        def sent(fd,data):
            n=write(fd,data);b=state.get('barrier')
            if b is not None and fd==b.gate and data==b'G' and not state.get('sent'):
                stop=time.monotonic()+.5
                while not self.f.marks() and time.monotonic()<stop:time.sleep(.002)
                state['executed']=bool(self.f.marks());state['sent']=True
                os.kill(os.getpid(),signal.SIGTERM)
            return n
        with patch.object(Barrier,'verify_and_release',armed),patch('os.write',side_effect=sent):index=self.start()
        self.assertTrue(state['executed']);self.assertEqual(index['status'],'failed')
        self.assertEqual(verify_pilot(self.f.out)['execution_status'],'failed')
        value=json.loads(next(self.f.out.glob('*/*.affinity.json')).read_bytes())
        self.assertIs(value['released'],True);self.assertEqual(value['release']['state'],'confirmed_sent')
        self.assertIsNotNone(value['release_timestamp']);self.assertFalse(value['measurement_eligible'])

    def test_close_boundary_SIGTERM_cannot_record_completed_trial(self):
        from campaign_journal import inspect_recovery
        from campaign_pilot import verify_pilot
        original=Barrier.verify_and_release;close=os.close;state={}
        def armed(b,child):state['barrier']=b;state['child']=child;return original(b,child)
        def terminated(fd):
            close(fd);b=state.get('barrier')
            if b is not None and fd==b.gate and b.value['released'] and not state.get('sent'):
                state['sent']=True;os.kill(os.getpid(),signal.SIGTERM)
        with termination_as_interrupt(),patch.object(Barrier,'verify_and_release',armed),patch('os.close',side_effect=terminated):result=self.start()
        self.assertTrue(state['sent']);self.assertEqual(result['status'],'failed')
        self.assertEqual(verify_pilot(self.f.out)['execution_status'],'failed')
        report=inspect_recovery(self.f.out)
        self.assertNotIn('verified-complete',{t['classification'] for t in report['trials']})
        self.assertIsNotNone(state['child'].returncode)


if __name__=='__main__':unittest.main(verbosity=2)
