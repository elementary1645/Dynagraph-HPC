"""Bounded explicit resume contracts; marker children and existing v2 verifier."""
import copy
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'benchmarks/python'))
from artifacts import write_bundle
from campaign_contract import expand
from campaign_journal import Journal, inspect_recovery
from campaign_ownership import directory_lock, OWNER
from campaign_pilot import run_pilot, verify_pilot
from campaign_resume import resume_pilot, inspect_resume, transaction_path, event
from workloads import canonical_json, sha256
from test_campaign import hardware


class ResumeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.base=Path(tmp.name)
        self.root=self.base/'inputs';(self.root/'bin').mkdir(parents=True)
        self.plan=json.loads((ROOT/'benchmarks/configs/campaign-development-v1.json').read_bytes())
        binary=Path(os.environ.get('DYNAGRAPH_PILOT_TEST_RUNNER',ROOT/'build/release/dynagraph_bench'))
        reference=self.root/'bin/reference';reference.write_bytes(binary.read_bytes());reference.chmod(0o700)
        self.marker=self.base/'markers';runner=self.root/'bin/bench'
        runner.write_text('#!/usr/bin/python3\nimport os,sys\nwith open('+repr(str(self.marker))+',"a") as f:f.write(" ".join(sys.argv[1:])+"\\n")\nos.execv('+repr(str(reference))+',['+repr(str(reference))+',*sys.argv[1:]])\n')
        self.plan['build'].update(executable='bin/bench',executable_sha256=sha256(runner.read_bytes()))
        write_bundle(self.plan['workloads'][0]['recipe'],self.root/'workloads/chain')
        self.manifest=expand(self.plan);self.ids=[t['trial_id'] for t in self.manifest['trials'][:3]]
        self.out=self.base/'original';self.attempt=transaction_path(self.out)
        probe=patch('campaign_pilot.inspect',return_value=hardware());probe.start();self.addCleanup(probe.stop)

    def initial(self,completed=1):
        finish=Journal.finish;count=[0]
        def cut(j,r):
            finish(j,r);count[0]+=1
            if count[0]==completed:raise RuntimeError('bounded parent crash between trials')
        with patch.object(Journal,'finish',cut):
            with self.assertRaises(RuntimeError):
                run_pilot(self.plan,self.manifest,self.root,self.out,self.ids,execute=True,max_trials=3,wall_seconds=5,timeout=2)

    def resume(self,**kwargs):return resume_pilot(self.out,execute=True,authorize=True,**kwargs)
    def snapshot(self):return {str(p.relative_to(self.out)):p.read_bytes() for p in self.out.rglob('*') if p.is_file()}
    def marks(self):return self.marker.read_text().splitlines() if self.marker.exists() else []
    def rejected(self):
        before=self.marks()
        with self.assertRaises((ValueError,OSError,KeyError,TypeError)):self.resume()
        self.assertEqual(before,self.marks())
    def cli(self,*args):return subprocess.run([sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),*args],capture_output=True,timeout=10)

    def test_explicit_authorizations(self):
        for execute,authorize in [(False,False),(True,False),(False,True)]:
            with self.assertRaises(ValueError):resume_pilot(self.out,execute=execute,authorize=authorize)
        self.assertFalse(self.out.exists());self.assertEqual(self.marks(),[])

    def test_completed_reuse_and_pending_order(self):
        self.initial();before=self.snapshot();r=self.resume()
        self.assertEqual(r['execution_status'],'complete');self.assertFalse(r['measurement_eligible'])
        self.assertEqual([x['disposition'] for x in r['trials']],['reused','new','new'])
        self.assertEqual(len(self.marks()),3);self.assertEqual(before,self.snapshot())
        self.assertEqual(verify_pilot(self.attempt/'pilot')['trials'],2)
        self.assertEqual(inspect_resume(self.attempt),r)
        self.assertEqual([t['trial_id'] for t in json.loads((self.attempt/'pilot/execution-manifest.json').read_text())['selected_trials']],self.ids[1:])

    def test_cli_authorization_and_inspection(self):
        self.initial()
        self.assertEqual(self.cli('resume-pilot','--output',str(self.out),'--execute-development').returncode,2)
        c=self.cli('resume-pilot','--output',str(self.out),'--execute-development','--authorize-resume');self.assertEqual(c.returncode,0,c.stderr)
        c=self.cli('inspect-resume','--output',str(self.attempt));self.assertEqual(c.returncode,0,c.stderr)

    def test_ordinary_verify_inspect_and_pilot_never_resume(self):
        self.initial();before=self.snapshot()
        with patch('subprocess.Popen',side_effect=AssertionError('inspection executed')):
            inspect_recovery(self.out)
            with self.assertRaises(FileNotFoundError):verify_pilot(self.out)
        with self.assertRaises(FileExistsError):run_pilot(self.plan,self.manifest,self.root,self.out,self.ids,execute=True,max_trials=3)
        self.assertEqual(before,self.snapshot());self.assertEqual(len(self.marks()),1)

    def test_legacy_without_ownership_rejected(self):
        self.initial();(self.out/OWNER).unlink();self.rejected()

    def test_copied_original_cannot_bypass_writer_ownership(self):
        self.initial();copy=self.base/'copied-original';shutil.copytree(self.out,copy)
        with directory_lock(self.out):
            with self.assertRaises(ValueError):resume_pilot(copy,execute=True,authorize=True)
        self.assertEqual(len(self.marks()),1)

    def test_active_original_writer_rejected(self):
        self.initial()
        with directory_lock(self.out):self.rejected()

    def test_single_use_attempt_blocks_second_resume(self):
        self.initial();self.resume();self.rejected();self.assertEqual(len(self.marks()),3)

    def test_failed_and_interrupted_not_retried(self):
        for reason in ['nonzero-exit','interrupted']:
            with self.subTest(reason=reason):
                target=self.base/reason;self.out=target
                from campaign_process import capture
                def fail(command,cwd,env,timeout,limit,**kw):
                    p,s=capture(['/does/not/exist'],cwd,env,timeout,limit,**kw);p.update(command=command,reason=reason,returncode=7 if reason=='nonzero-exit' else None);return p,s
                with patch('campaign_pilot.capture',side_effect=fail):
                    run_pilot(self.plan,self.manifest,self.root,target,self.ids,execute=True,max_trials=3)
                self.rejected()

    def test_unresolved_launch_possible_orphan_rejected(self):
        original=Journal.transition
        def cut(j,tid,state,*a,**kw):
            original(j,tid,state,*a,**kw)
            if state=='launched':raise Journal.Error('parent died after intent')
        with patch.object(Journal,'transition',cut):
            with self.assertRaises(Journal.Error):run_pilot(self.plan,self.manifest,self.root,self.out,self.ids,execute=True,max_trials=3)
        self.assertEqual(inspect_recovery(self.out)['trials'][0]['classification'],'indeterminate');self.rejected()
        self.assertEqual(self.marks(),[])

    def test_stale_pid_metadata_cannot_authorize_recovery(self):
        self.test_unresolved_launch_possible_orphan_rejected()
        (self.out/'stale-pid.json').write_text(json.dumps({'pid':os.getpid(),'dead':True}));self.rejected()

    def test_wrong_completed_record_hash(self):
        self.initial();p=self.out/self.ids[0]/'record.json';p.write_bytes(p.read_bytes()+b' ');self.rejected()

    def test_wrong_manifest(self):
        self.initial();p=self.out/'trial-manifest.json';m=json.loads(p.read_text());m['trials'].reverse();p.write_bytes(canonical_json(m));self.rejected()

    def test_wrong_execution_identity(self):
        self.initial();p=self.out/'execution-manifest.json';v=json.loads(p.read_text());v['plan_sha256']='0'*64;p.write_bytes(canonical_json(v));self.rejected()

    def test_changed_input_binary(self):
        self.initial();(self.root/'bin/bench').write_text('untrusted replacement');self.rejected();self.assertFalse(self.attempt.exists())

    def test_all_inputs_validated_before_launch(self):
        self.initial();(self.root/'workloads/chain/trace.txt').write_text('bad');self.rejected();self.assertFalse(self.attempt.exists())

    def test_terminal_publication_failure_keeps_verified_new_completions(self):
        self.initial();from campaign_resume import put
        def fail(d,n,v):
            if n=='00000001.json':raise OSError('terminal failure')
            return put(d,n,v)
        with patch('campaign_resume.put',side_effect=fail):
            with self.assertRaises(OSError):self.resume()
        r=inspect_resume(self.attempt);self.assertEqual(r['status'],'incomplete')
        self.assertTrue(all(t['classification']=='verified-complete' for t in r['trials']))
        self.rejected();self.assertEqual(len(self.marks()),3)

    def test_crash_before_authorization_publication_reserves_attempt(self):
        self.initial()
        with patch('campaign_resume.put',side_effect=OSError('crash')):
            with self.assertRaises(OSError):self.resume()
        self.rejected();self.assertEqual(len(self.marks()),1)
        with self.assertRaises(FileNotFoundError):inspect_resume(self.attempt)

    def test_crash_after_authorization_before_child(self):
        self.initial()
        with patch('campaign_resume.run_pilot',side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):self.resume()
        r=inspect_resume(self.attempt);self.assertEqual(r['status'],'incomplete');self.rejected()

    def test_repeated_interruption_after_new_completion(self):
        self.initial();finish=Journal.finish
        def cut(j,r):finish(j,r);raise RuntimeError('crash after new completion')
        with patch.object(Journal,'finish',cut):
            with self.assertRaises(RuntimeError):self.resume()
        r=inspect_resume(self.attempt)
        self.assertEqual([t['classification'] for t in r['trials']],['verified-complete','verified-complete','pending'])
        self.assertEqual(r['status'],'incomplete');self.rejected();self.assertEqual(len(self.marks()),2)

    def test_resume_unresolved_launch_blocks_second_attempt(self):
        self.initial();original=Journal.transition
        def cut(j,t,s,*a,**kw):
            original(j,t,s,*a,**kw)
            if s=='launched':raise Journal.Error('crash')
        with patch.object(Journal,'transition',cut):
            with self.assertRaises(Journal.Error):self.resume()
        r=inspect_resume(self.attempt);self.assertEqual(r['trials'][1]['classification'],'indeterminate');self.rejected()

    def test_slow_authorization_publication_uses_attempt_deadline(self):
        self.initial();clock=[0.];from campaign_resume import put
        def delay(d,n,v):
            put(d,n,v)
            if n=='00000000.json':clock[0]=5
        with patch('time.monotonic',side_effect=lambda:clock[0]),patch('campaign_resume.put',side_effect=delay):r=self.resume()
        self.assertEqual(r['execution_status'],'failed');self.assertEqual(len(self.marks()),1)
        self.assertEqual(r['trials'][1]['classification'],'failed')

    def test_expiry_after_child_launch_intent(self):
        self.initial();clock=[0.];original=Journal.transition
        def delay(j,t,s,*a,**kw):
            original(j,t,s,*a,**kw)
            if s=='launched':clock[0]=5
        with patch('time.monotonic',side_effect=lambda:clock[0]),patch.object(Journal,'transition',delay):r=self.resume()
        self.assertEqual(r['execution_status'],'failed');self.assertEqual(len(self.marks()),1)

    def test_resume_metadata_mutations(self):
        self.initial();self.resume();p=self.attempt/'00000000.json';raw=p.read_bytes();v=json.loads(raw)
        changes={'original_chain_head':'0'*64,'attempt_sequence':2,'attempt_id':'0'*64,'measurement_eligible':True,'limits':{},'pending':self.ids,'schema_version':2,'original':'../outside','authorization':{}}
        for key,value in changes.items():
            with self.subTest(key=key):
                altered=copy.deepcopy(v['payload']);altered[key]=value;p.write_bytes(canonical_json(event(0,None,'authorized',altered)))
                with self.assertRaises((ValueError,OSError,KeyError)):inspect_resume(self.attempt)
        p.write_bytes(raw)

    def test_torn_missing_reordered_duplicate_events(self):
        self.initial();self.resume();a=self.attempt/'00000000.json';b=self.attempt/'00000001.json';x=a.read_bytes();y=b.read_bytes()
        for first,last in [(b'{',y),(y,x),(x,x)]:
            a.write_bytes(first);b.write_bytes(last)
            with self.assertRaises((ValueError,KeyError)):inspect_resume(self.attempt)
        a.write_bytes(x);b.write_bytes(y);(self.attempt/'00000002.json').write_bytes(y)
        with self.assertRaises(ValueError):inspect_resume(self.attempt)

    def test_metadata_special_files_and_oversize(self):
        self.initial();p=self.out/OWNER;raw=p.read_bytes()
        for kind in ['fifo','symlink','directory','oversize','version']:
            p.unlink()
            if kind=='fifo':os.mkfifo(p)
            elif kind=='symlink':p.symlink_to(self.out/'plan.json')
            elif kind=='directory':p.mkdir()
            elif kind=='oversize':p.write_bytes(b' '*(1048576+1))
            else:
                v=json.loads(raw);v['schema_version']=2;p.write_bytes(canonical_json(v))
            self.rejected()
            if p.is_dir():p.rmdir()
            else:p.unlink()
            p.write_bytes(raw)

    def test_rehashed_wrong_distances_and_command_rejected(self):
        self.initial();base=self.out/self.ids[0];record=base/'record.json'
        r=json.loads(record.read_bytes());stream=base/r['processes'][0]['stdout']
        value=json.loads(stream.read_bytes());value['final_distances'][1]=123456789
        stream.write_bytes(canonical_json(value));r['processes'][0].update(stdout_size=stream.stat().st_size,stdout_sha256=sha256(stream.read_bytes()))
        r['artifacts'][stream.name]=sha256(stream.read_bytes());record.write_bytes(canonical_json(r))
        # Rehash every committed journal reference: the independent oracle must
        # still reject even when all integrity-only checks are consistent.
        previous=None
        from campaign_journal import entry
        for p in sorted((self.out/'recovery-journal').glob('*.json')):
            v=json.loads(p.read_bytes())
            if v['kind']=='transition' and v['payload']['to_state']=='completed':v['payload']['evidence']['sha256']=sha256(record.read_bytes())
            v=entry(v['sequence'],previous,v['kind'],v['payload']);p.write_bytes(canonical_json(v));previous=v['entry_id']
        self.rejected()

    def test_concurrent_resume_reservation(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        self.initial();ready=Event();release=Event()
        from campaign_resume import header
        def held(original):
            result=header(original);ready.set()
            if not release.wait(5):raise RuntimeError('bounded coordination timeout')
            return result
        with ThreadPoolExecutor(max_workers=1) as pool, patch('campaign_resume.header',side_effect=held):
            task=pool.submit(self.resume)
            try:
                self.assertTrue(ready.wait(5));self.rejected()
            finally:release.set()
            self.assertEqual(task.result(timeout=10)['execution_status'],'complete')
        self.assertEqual(len(self.marks()),3)

    def test_resume_file_fsync_expiry(self):
        self.initial();clock=[0.];fsync=os.fsync;delayed=[False]
        def slow(fd):
            import stat
            path=Path(os.readlink('/proc/self/fd/'+str(fd)))
            if path.parent==self.attempt and stat.S_ISREG(os.fstat(fd).st_mode):
                delayed[0]=True;clock[0]=5
            return fsync(fd)
        with patch('time.monotonic',side_effect=lambda:clock[0]),patch('os.fsync',side_effect=slow):r=self.resume()
        self.assertTrue(delayed[0]);self.assertEqual(r['execution_status'],'failed');self.assertEqual(len(self.marks()),1)

    def test_original_per_trial_cap_not_extended(self):
        self.initial();clock=[0.];transition=Journal.transition
        def delay(j,t,state,*a,**kw):
            transition(j,t,state,*a,**kw)
            if state=='launched':clock[0]=2
        with patch('time.monotonic',side_effect=lambda:clock[0]),patch.object(Journal,'transition',delay):r=self.resume()
        self.assertEqual(r['execution_status'],'failed');self.assertEqual(len(self.marks()),1)
        rec=json.loads((self.attempt/'pilot'/self.ids[1]/'record.json').read_bytes())
        self.assertEqual(rec['reason'],'timeout');self.assertEqual(rec['processes'],[])

    def test_invalid_command_binding_even_with_rehashed_journal(self):
        self.initial();p=self.out/self.ids[0]/'record.json';v=json.loads(p.read_bytes())
        v['processes'][0]['command'][0]='/bin/true';p.write_bytes(canonical_json(v))
        from campaign_journal import entry
        previous=None
        for f in sorted((self.out/'recovery-journal').glob('*.json')):
            e=json.loads(f.read_bytes())
            if e['kind']=='transition' and e['payload']['to_state']=='completed':e['payload']['evidence']['sha256']=sha256(p.read_bytes())
            e=entry(e['sequence'],previous,e['kind'],e['payload']);f.write_bytes(canonical_json(e));previous=e['entry_id']
        self.rejected()

    def test_sigterm_resume_cleanup_and_inspection(self):
        import signal
        import time
        runner=self.root/'bin/bench';text=runner.read_text()
        pidfile=self.base/'resume-child.pid'
        text=text.replace('os.execv(', 'if len(open('+repr(str(self.marker))+').readlines())>1:\n import time\n open('+repr(str(pidfile))+',"w").write(str(os.getpid()))\n time.sleep(10)\nos.execv(')
        runner.write_text(text);self.plan['build']['executable_sha256']=sha256(runner.read_bytes());self.manifest=expand(self.plan);self.ids=[t['trial_id'] for t in self.manifest['trials'][:3]]
        self.initial()
        child=subprocess.Popen([sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'resume-pilot','--output',str(self.out),'--execute-development','--authorize-resume'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+4
            while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(pidfile.exists());pid=int(pidfile.read_text())
            child.send_signal(signal.SIGTERM);child.communicate(timeout=4)
            r=inspect_resume(self.attempt);self.assertEqual(r['trials'][1]['classification'],'interrupted');self.rejected()
            with self.assertRaises(ProcessLookupError):os.kill(pid,0)
        finally:
            if child.poll() is None:child.kill();child.communicate(timeout=2)
            if pidfile.exists():
                try:os.killpg(int(pidfile.read_text()),signal.SIGKILL)
                except ProcessLookupError:pass

    def test_socket_rejected(self):
        self.initial();p=self.out/OWNER;p.unlink()
        with socket.socket(socket.AF_UNIX) as s:s.bind(str(p));self.rejected()

    def test_symlink_original_directory_rejected(self):
        self.initial();link=self.base/'alias';link.symlink_to(self.out,target_is_directory=True)
        with self.assertRaises(OSError):resume_pilot(link,execute=True,authorize=True)

    def test_inspection_is_read_only(self):
        self.initial();self.resume();before={str(p):p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        with patch('subprocess.Popen',side_effect=AssertionError('executed')),patch('campaign_resume.put',side_effect=AssertionError('write')):inspect_resume(self.attempt)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.base.rglob('*') if p.is_file()})

    def test_runtime_origin_reuse_and_new_attempt(self):
        self.initial();before=self.snapshot()
        original_record=json.loads((self.out/self.ids[0]/'record.json').read_bytes())
        original_observation=json.loads((self.out/self.ids[0]/'0-verify.runtime.json').read_bytes())
        result=self.resume()
        self.assertEqual(before,self.snapshot())
        self.assertEqual(original_observation['origin'],dict(kind='original',attempt_id=None))
        self.assertFalse(original_record['measurement_eligible'])
        for tid in self.ids[1:]:
            observation=json.loads((self.attempt/'pilot'/tid/'0-verify.runtime.json').read_bytes())
            self.assertEqual(observation['origin'],dict(kind='resume',attempt_id=result['attempt_id']))
            self.assertNotEqual(observation['execution_id'],original_observation['execution_id'])
            self.assertFalse(observation['measurement_eligible'])
        target=self.attempt/'pilot'/self.ids[1]/'0-verify.runtime.json'
        observation['schema_version']=99;target.write_bytes(canonical_json(observation))
        with self.assertRaises(ValueError):inspect_resume(self.attempt)


if __name__=='__main__':unittest.main(verbosity=2)
