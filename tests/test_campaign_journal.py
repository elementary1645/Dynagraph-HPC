"""Bounded recovery state/evidence/crash contracts; never resumes a campaign."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'benchmarks/python'))
from artifacts import write_bundle
from campaign_contract import expand
from campaign_journal import (DIRECTORY, Journal, apply, entry, inspect_recovery, MAX_ENTRY)
from campaign_pilot import run_pilot, verify_pilot
from workloads import canonical_json, sha256
from test_campaign import hardware


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.inputs=self.root/'inputs';(self.inputs/'bin').mkdir(parents=True)
        self.plan=json.loads((ROOT/'benchmarks/configs/campaign-development-v1.json').read_bytes())
        self.binary=self.inputs/'bin/bench'
        source=Path(os.environ.get('DYNAGRAPH_PILOT_TEST_RUNNER',ROOT/'build/release/dynagraph_bench'))
        if not source.is_file():self.fail('build benchmark before journal tests')
        self.binary.write_bytes(source.read_bytes())
        write_bundle(self.plan['workloads'][0]['recipe'],self.inputs/'workloads/chain')
        self.output=self.root/'output';self.refresh()
        self.probe=patch('campaign_pilot.inspect',return_value=hardware());self.probe.start();self.addCleanup(self.probe.stop)

    def refresh(self):
        self.plan['build'].update(executable='bin/bench',executable_sha256=sha256(self.binary.read_bytes()))
        self.manifest=expand(self.plan);self.tid=self.manifest['trials'][0]['trial_id']

    def run_pilot(self,**options):
        return run_pilot(self.plan,self.manifest,self.inputs,self.output,[self.tid],execute=True,**options)

    def partial(self):
        for name in ('sha256.json','result-index.json'):
            (self.output/name).unlink(missing_ok=True)

    def entries(self):return sorted((self.output/DIRECTORY).glob('*.json'))

    def alter(self,index,change):
        files=self.entries();value=json.loads(files[index].read_bytes());change(value)
        files[index].write_bytes(canonical_json(value))
        previous=None
        for f in files:
            v=json.loads(f.read_bytes());v=entry(v['sequence'],previous,v['kind'],v['payload'])
            f.write_bytes(canonical_json(v));previous=v['entry_id']

    def cli(self):
        return subprocess.run([sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'inspect-recovery','--output',str(self.output)],capture_output=True,timeout=3)

    def reject(self):
        with self.assertRaises((ValueError,OSError)):inspect_recovery(self.output)
        c=self.cli();self.assertEqual(c.returncode,2,c.stdout);self.assertNotIn(b'Traceback',c.stderr)
        self.assertEqual(json.loads(c.stdout)['status'],'rejected')

    def test_complete_lifecycle_and_controlled_cli(self):
        self.run_pilot();r=inspect_recovery(self.output)
        self.assertEqual(r['status'],'settled');self.assertEqual(r['trials'][0]['classification'],'verified-complete')
        self.assertFalse(r['measurement_eligible']);self.assertEqual(r['committed_entries'],3)
        c=self.cli();self.assertEqual(c.returncode,0,c.stderr);self.assertEqual(json.loads(c.stdout)['schema_version'],1)
        self.assertEqual(verify_pilot(self.output)['execution_status'],'complete')

    def test_order_and_pending_after_failure(self):
        self.binary.write_text('#!/usr/bin/python3\nraise SystemExit(7)\n');self.refresh()
        ids=[t['trial_id'] for t in self.manifest['trials'][:2]]
        run_pilot(self.plan,self.manifest,self.inputs,self.output,ids[::-1],execute=True,max_trials=2)
        r=inspect_recovery(self.output)
        self.assertEqual([t['trial_id'] for t in r['trials']],ids)
        self.assertEqual([t['classification'] for t in r['trials']],['failed','pending'])
        self.assertEqual(r['status'],'settled')

    def test_header_bindings(self):
        self.run_pilot();self.partial()
        original=[p.read_bytes() for p in self.entries()]
        for key,value in [('plan_sha256','0'*64),('manifest_sha256','0'*64),('pilot_execution_id','0'*64),
                          ('hardware_sha256','0'*64),('environment_sha256','0'*64),('admission','scientific'),
                          ('measurement_eligible',True),('evidence_schema_version',1)]:
            with self.subTest(key=key):
                for p,raw in zip(self.entries(),original):p.write_bytes(raw)
                self.alter(0,lambda v:v['payload'].update({key:value}));self.reject()

    def test_wrong_trial_and_external_evidence(self):
        self.run_pilot();self.partial();original=[p.read_bytes() for p in self.entries()]
        for change in (lambda v:v['payload'].update(trial_id='0'*64),
                       lambda v:v['payload']['evidence'].update(path='../outside'),
                       lambda v:v['payload']['evidence'].update(path='/tmp/outside'),
                       lambda v:v['payload']['evidence'].update(sha256='0'*64)):
            for p,raw in zip(self.entries(),original):p.write_bytes(raw)
            self.alter(2,change);self.reject()

    def test_invalid_transition(self):
        self.run_pilot();self.partial()
        self.alter(1,lambda v:v['payload'].update(to_state='completed'))
        self.reject()

    def test_duplicate_entry(self):
        self.run_pilot();self.partial();shutil.copy2(self.entries()[2],self.output/DIRECTORY/'00000003.json');self.reject()

    def test_missing_sequence(self):
        self.run_pilot();self.partial();self.entries()[1].unlink();self.reject()

    def test_out_of_order(self):
        self.run_pilot();self.partial();a,b=self.entries()[1:];x=a.read_bytes();a.write_bytes(b.read_bytes());b.write_bytes(x);self.reject()

    def test_duplicate_transition_identity(self):
        self.run_pilot();self.partial();v=json.loads(self.entries()[2].read_bytes());v['entry_id']=json.loads(self.entries()[1].read_bytes())['entry_id'];self.entries()[2].write_bytes(canonical_json(v));self.reject()

    def test_corrupt_or_torn_committed_entry(self):
        self.run_pilot();self.partial();self.entries()[2].write_bytes(b'{"schema":');self.reject()

    def test_unpublished_torn_write_is_not_committed(self):
        self.run_pilot();self.partial();self.entries()[2].unlink()
        (self.output/DIRECTORY/'.pending-torn').write_bytes(b'{"to_state":"completed"')
        r=inspect_recovery(self.output)
        self.assertEqual(r['committed_entries'],2);self.assertEqual(r['status'],'incomplete')
        self.assertEqual(r['trials'][0]['classification'],'indeterminate');self.assertEqual(self.cli().returncode,1)

    def test_evidence_complete_journal_incomplete(self):
        self.run_pilot();self.partial();self.entries()[2].unlink()
        r=inspect_recovery(self.output);self.assertEqual(r['trials'][0]['evidence_status'],'verified-complete')
        self.assertEqual(r['trials'][0]['classification'],'indeterminate')

    def test_prior_completed_trial_survives_missing_final_index(self):
        self.run_pilot();self.partial();r=inspect_recovery(self.output)
        self.assertEqual(r['status'],'incomplete');self.assertEqual(r['trials'][0]['classification'],'verified-complete')
        self.assertFalse(r['final_evidence_verified'])

    def test_missing_stream(self):
        self.run_pilot();self.partial();record=json.loads((self.output/self.tid/'record.json').read_bytes())
        (self.output/self.tid/record['processes'][0]['stderr']).unlink();self.reject()

    def test_modified_record(self):
        self.run_pilot();self.partial();f=self.output/self.tid/'record.json';v=json.loads(f.read_bytes());v['message']='modified';f.write_bytes(canonical_json(v));self.reject()

    def test_journal_cannot_promote_failed_evidence(self):
        self.binary.write_text('#!/usr/bin/python3\nraise SystemExit(7)\n');self.refresh();self.run_pilot();self.partial()
        self.alter(2,lambda v:v['payload'].update(to_state='completed',reason='success'));self.reject()

    def test_interrupted(self):
        with patch('campaign_pilot.capture',side_effect=KeyboardInterrupt):self.run_pilot()
        r=inspect_recovery(self.output);self.assertEqual(r['trials'][0]['classification'],'interrupted')

    def test_timeout_and_overall_deadline(self):
        self.binary.write_text('#!/usr/bin/python3\nimport time\ntime.sleep(10)\n');self.refresh()
        self.run_pilot(timeout=5,wall_seconds=1)
        r=inspect_recovery(self.output);self.assertEqual(r['trials'][0]['classification'],'failed')
        self.assertEqual(r['trials'][0]['evidence_status'],'timeout')

    def test_launch_failure(self):
        self.binary.write_bytes(b'invalid executable');self.refresh();self.run_pilot()
        r=inspect_recovery(self.output);self.assertEqual(r['trials'][0]['evidence_status'],'launch-error')

    def test_capture_failure(self):
        real=__import__('campaign_process').capture
        def fail(command,cwd,env,timeout,limit):
            result,streams=real(['/does/not/exist'],cwd,env,timeout,limit)
            result.update(command=command,reason='capture-error',returncode=-9,signal=9)
            return result,streams
        with patch('campaign_pilot.capture',side_effect=fail):self.run_pilot()
        self.assertEqual(inspect_recovery(self.output)['trials'][0]['evidence_status'],'capture-error')

    def test_concurrent_creator_collision(self):
        self.run_pilot();other=self.root/'context';other.mkdir()
        for name in ('plan.json','trial-manifest.json','execution-manifest.json','hardware.json','admission.json'):shutil.copy2(self.output/name,other/name)
        def create():
            try:Journal.create(other);return 'created'
            except FileExistsError:return 'collision'
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:create(),range(2)))
        self.assertEqual(sorted(results),['collision','created'])

    def test_journal_write_failure_prevents_launch(self):
        original=Journal._publish
        def fail(journal,kind,payload):
            if kind=='transition':raise Journal.Error('injected disk error')
            return original(journal,kind,payload)
        with patch.object(Journal,'_publish',fail),patch('campaign_pilot.capture') as child:
            with self.assertRaises(Journal.Error):self.run_pilot()
            child.assert_not_called()
        self.assertFalse((self.output/'result-index.json').exists())
        self.assertEqual(inspect_recovery(self.output)['status'],'incomplete')

    def test_terminal_write_failure_does_not_certify(self):
        original=Journal._publish
        def fail(journal,kind,payload):
            if kind=='transition' and payload['to_state']=='completed':raise Journal.Error('injected terminal disk error')
            return original(journal,kind,payload)
        with patch.object(Journal,'_publish',fail):
            with self.assertRaises(Journal.Error):self.run_pilot()
        r=inspect_recovery(self.output);self.assertEqual(r['trials'][0]['classification'],'indeterminate')

    def test_readonly_inspection_does_not_execute_or_write(self):
        self.run_pilot();before={str(p):p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
        with patch('subprocess.Popen',side_effect=AssertionError('inspection executed a command')),patch.object(Journal,'_publish',side_effect=AssertionError('inspection wrote journal')):
            inspect_recovery(self.output)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.output.rglob('*') if p.is_file()})

    def test_v2_legacy_without_journal_still_verifies(self):
        self.run_pilot();shutil.rmtree(self.output/DIRECTORY)
        f=self.output/'sha256.json';v=json.loads(f.read_bytes());v={k:h for k,h in v.items() if not k.startswith(DIRECTORY+'/')} ;f.write_bytes(canonical_json(v))
        self.assertEqual(verify_pilot(self.output)['execution_status'],'complete')
        self.assertEqual(self.cli().returncode,2)  # No inferred/migrated recovery journal.

    def test_metadata_bounds_and_types(self):
        self.run_pilot();self.partial();target=self.entries()[2];old=target.read_bytes()
        for mode in ('fifo','link','directory','oversize','schema'):
            with self.subTest(mode=mode):
                if target.is_dir():target.rmdir()
                elif target.exists() or target.is_symlink():target.unlink()
                if mode=='fifo':os.mkfifo(target)
                elif mode=='link':target.symlink_to(self.entries()[0])
                elif mode=='directory':target.mkdir()
                elif mode=='oversize':target.write_bytes(b' '*(MAX_ENTRY+1))
                else:
                    v=json.loads(old);v['schema_version']=2;target.write_bytes(canonical_json(v))
                self.reject()

    def test_pending_initial_state(self):
        self.run_pilot();context=self.root/'pending';context.mkdir()
        for name in ('plan.json','trial-manifest.json','execution-manifest.json','hardware.json','admission.json'):shutil.copy2(self.output/name,context/name)
        Journal.create(context);r=inspect_recovery(context)
        self.assertEqual(r['status'],'incomplete');self.assertEqual(r['trials'][0]['classification'],'pending')

    def test_missing_sequence_field_and_noncanonical_commit(self):
        self.run_pilot();self.partial();f=self.entries()[2];raw=f.read_bytes();v=json.loads(raw);v.pop('sequence');f.write_bytes(canonical_json(v));self.reject()
        f.write_bytes(raw.rstrip(b'\n'));self.reject()

    def test_invalid_repeated_transition_does_not_publish(self):
        self.run_pilot();context=self.root/'writer';context.mkdir()
        for name in ('plan.json','trial-manifest.json','execution-manifest.json','hardware.json','admission.json'):shutil.copy2(self.output/name,context/name)
        writer=Journal.create(context);writer.transition(self.tid,'launched')
        before=list((context/DIRECTORY).iterdir())
        with self.assertRaises(ValueError):writer.transition(self.tid,'launched')
        self.assertEqual(before,list((context/DIRECTORY).iterdir()))

    def test_socket_journal_entry(self):
        import socket
        self.run_pilot();self.partial();f=self.entries()[2];f.unlink()
        with socket.socket(socket.AF_UNIX) as sock:
            sock.bind(str(f));self.reject()

    def test_missing_header(self):
        self.run_pilot();self.partial();self.entries()[0].unlink();self.reject()

    def test_sigterm_and_abrupt_parent_death(self):
        for name,signum in [('term',signal.SIGTERM),('kill',signal.SIGKILL)]:
            with self.subTest(name=name):
                pidfile=self.root/(name+'.pid')
                self.binary.write_text('#!/usr/bin/python3\nimport os,time\nopen('+repr(str(pidfile))+',"w").write(str(os.getpid()))\ntime.sleep(10)\n');self.refresh()
                pf=self.root/(name+'-plan.json');mf=self.root/(name+'-manifest.json');pf.write_bytes(canonical_json(self.plan));mf.write_bytes(canonical_json(self.manifest));out=self.root/name
                command=[sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'pilot','--plan',str(pf),'--manifest',str(mf),'--root',str(self.inputs),'--output',str(out),'--trial-id',self.tid,'--timeout','5','--execute-development']
                child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);pid=None
                try:
                    deadline=time.monotonic()+3
                    while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.01)
                    self.assertTrue(pidfile.exists());pid=int(pidfile.read_text());child.send_signal(signum);child.communicate(timeout=3)
                    r=inspect_recovery(out)
                    expected='interrupted' if signum==signal.SIGTERM else 'indeterminate'
                    self.assertEqual(r['trials'][0]['classification'],expected)
                    self.assertFalse(r['measurement_eligible'])
                finally:
                    if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.communicate(timeout=2)
                    if pid is not None:
                        try:os.killpg(pid,signal.SIGKILL)
                        except ProcessLookupError:pass


if __name__=='__main__':unittest.main(verbosity=2)
