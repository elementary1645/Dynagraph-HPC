"""Independent runtime fixtures and bounded real-process integrity checks."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'benchmarks/python'))
from campaign_runtime import (collect, fact, provenance, verify, validate_snapshot, read_metadata)
from campaign_process import capture
from campaign_provenance import cpu_list, validate_cgroups
from test_campaign import runtime_fixture, cgroup_fixture
from workloads import sha256


def snapshot():
    r = runtime_fixture()
    return dict(start='2026-01-01T00:00:01+00:00', end='2026-01-01T00:00:02+00:00',
                pid=123, process_stat=r['process_stat'], process_start_ticks=100000,
                executable_match=True, observed_executable_sha256=r['executable_sha256'],
                affinity=fact([0,1], 'independent fixture', 'child leader snapshot'),
                cgroups=fact(cgroup_fixture(), 'independent fixture', 'visible hierarchy'),
                openmp=fact(r, 'independent fixture', 'child mapping snapshot'),
                online_cpus=fact([0,1], 'fixture', 'observer namespace'),
                kernel=fact('fixture kernel', 'fixture', 'observer kernel'),
                os=fact('fixture OS', 'fixture', 'observer namespace'), limitations=[])


class RuntimeTests(unittest.TestCase):
    def test_independent_identity(self):
        s = snapshot()
        self.assertIs(validate_snapshot(s, s['observed_executable_sha256']), s)

    def test_missing_runtime_and_cgroups(self):
        s = snapshot()
        for key in ('openmp','cgroups'):
            s[key] = fact(None, 'fixture missing', 'child snapshot')
        validate_snapshot(s, s['observed_executable_sha256'])

    def test_conflicting_identity(self):
        for mutate in (lambda s:s.update(pid=124),
                       lambda s:s.update(process_start_ticks=2),
                       lambda s:s.update(observed_executable_sha256='f'*64),
                       lambda s:s['openmp']['value'].update(pid=124),
                       lambda s:s['openmp']['value'].update(executable_sha256='f'*64),
                       lambda s:s.update(executable_match=False)):
            s = snapshot(); wanted=s['observed_executable_sha256'];mutate(s)
            with self.assertRaises(ValueError): validate_snapshot(s, wanted)

    def test_affinity_encoding(self):
        self.assertEqual(cpu_list('0-2,5'), [0,1,2,5])
        for bad in ('', '1-', '-1', '2-1', '1,,2', '0-999999'):
            with self.assertRaises(ValueError): cpu_list(bad)
        for bad in ([1,0], [1,1], [True], [], [-1]):
            s=snapshot();s['affinity']['value']=bad
            with self.assertRaises(ValueError): validate_snapshot(s, s['observed_executable_sha256'])

    def test_exited_process_cannot_bind_observations(self):
        for state in ('Z', 'X', 'x'):
            s = snapshot()
            prefix, tail = s['process_stat'].rsplit(') ', 1)
            s['process_stat'] = prefix + ') ' + state + tail[1:]
            with self.subTest(state=state), self.assertRaises(ValueError):
                validate_snapshot(s, s['observed_executable_sha256'])
            # An exited process can retain identity evidence, with child facts
            # explicitly unavailable, just as the collector emits it.
            s['executable_match'] = False
            for key in ('affinity', 'cgroups', 'openmp'):
                s[key] = fact(None, 'exited fixture', 'child snapshot')
            validate_snapshot(s, s['observed_executable_sha256'])

    def test_quotas(self):
        validate_cgroups(cgroup_fixture())
        for bad in ('0 100', 'max 0', '-1 100', '1', 'max 100 extra', '1  100'):
            s=snapshot();s['cgroups']['value']['views'][0]['ancestors'][0]['cpu.max']=bad
            with self.assertRaises(ValueError): validate_snapshot(s, s['observed_executable_sha256'])

    def test_binding_teams_versions_and_admission(self):
        s=snapshot();wanted=s['observed_executable_sha256']
        bound={'pilot_execution_id':'a'*64,'environment':{'b'*64:{'OMP_NUM_THREADS':'2','OMP_DYNAMIC':'FALSE','OMP_THREAD_LIMIT':'2'}}};trial={'trial_id':'b'*64,'workers':2}
        process=dict(command=['./runner','time'],start='2026-01-01T00:00:00+00:00',end='2026-01-01T00:00:03+00:00')
        record=dict(trial=trial,executable_sha256=wanted)
        origin=dict(kind='resume',attempt_id='c'*64)
        p=provenance(bound,trial,process,s,origin,wanted)
        verify(p,bound,record,process,origin)
        for key, value in [('schema_version',2),('schema_version',True),('observed_team_size',2),
                           ('observed_team_size',0),('observed_team_size',-1),('observed_team_size',True),
                           ('relevant_parallel_regions',1),('intended_workload_observed',True),
                           ('measurement_eligible',True),('requested_workers',3),('execution_id','d'*64),
                           ('origin',dict(kind='original',attempt_id=None))]:
            q=copy.deepcopy(p);q[key]=value
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                verify(q,bound,record,process,origin)

    def test_timestamps_scopes_and_missing_contradiction(self):
        for mutate in (lambda s:s.update(start='yesterday'),
                       lambda s:s.update(end='2025-01-01T00:00:00+00:00'),
                       lambda s:s['affinity'].update(scope=''),
                       lambda s:s['openmp'].update(status='unavailable')):
            s=snapshot();mutate(s)
            with self.assertRaises(ValueError):validate_snapshot(s,s['observed_executable_sha256'])

    def test_bounded_regular_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'metadata';p.write_text('ok')
            self.assertEqual(read_metadata(p),'ok')
            p.write_bytes(b'x'*1048577)
            with self.assertRaises(ValueError):read_metadata(p)
            p.unlink();os.mkfifo(p)
            with self.assertRaises(ValueError):read_metadata(p)
            p.unlink();p.symlink_to('/etc/passwd')
            with self.assertRaises(OSError):read_metadata(p)
            self.assertIsNone(read_metadata(Path(tmp)/'missing'))

    def test_real_process_and_termination_during_observation(self):
        executable=Path(sys.executable).resolve();wanted=sha256(executable.read_bytes())
        observations=[]
        def observe(pid):
            s=collect(pid,executable,wanted);observations.append(s);return s
        result,_=capture([str(executable),'-c','import time;time.sleep(2)'],ROOT,dict(os.environ),1,1024,runtime_observer=observe)
        self.assertEqual(result['reason'],'timeout');self.assertEqual(len(observations),1)
        validate_snapshot(observations[0],wanted)
        def terminate(pid):
            os.kill(pid,9)
            return collect(pid,executable,wanted)
        result,_=capture([str(executable),'-c','import time;time.sleep(2)'],ROOT,dict(os.environ),1,1024,runtime_observer=terminate)
        self.assertEqual(result['reason'],'signal', result)
        validate_snapshot(result['_runtime_snapshot'],wanted)

    def test_rejected_observation_stops_process(self):
        def reject(pid):raise ValueError('contradictory fixture')
        result,_=capture([sys.executable,'-c','import time;time.sleep(2)'],ROOT,dict(os.environ),1,1024,runtime_observer=reject)
        self.assertEqual(result['reason'],'capture-error');self.assertIsNotNone(result['returncode'])


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        import test_campaign_pilot
        self.fixture=test_campaign_pilot.PilotTests()
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)

    def test_artifact_tamper_missing_and_unknown_version(self):
        f=self.fixture;f.run_case()
        directory=f.root/'out';record=f.record();tid=record['trial']['trial_id']
        path=directory/tid/'0-verify.runtime.json';original=path.read_bytes()
        from campaign_pilot import verify_pilot
        verify_pilot(directory)
        path.write_bytes(b'{}')
        with self.assertRaises(ValueError):verify_pilot(directory)
        path.write_bytes(original);value=json.loads(original);value['schema_version']=99
        path.write_bytes(__import__('workloads').canonical_json(value))
        # Even a refreshed inventory cannot turn an unsupported schema into v1.
        from campaign_runtime import verify
        with self.assertRaises(ValueError):verify(value,{},record,record['processes'][0],value['origin'])
        path.unlink()
        with self.assertRaises((ValueError,OSError)):verify_pilot(directory)


if __name__ == '__main__': unittest.main(verbosity=2)
