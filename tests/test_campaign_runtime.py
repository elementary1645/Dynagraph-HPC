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
from workloads import canonical_json, sha256


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


def process_state(raw, state):
    prefix, tail = raw.rsplit(') ', 1)
    return prefix + ') ' + state + tail[1:]


def replace_runtime(directory, tid, observation):
    """Refresh all consistency hashes so semantic checks must reject the fact."""
    from campaign_journal import entry
    path = directory/tid/'0-verify.runtime.json'
    path.write_bytes(canonical_json(observation))
    record_path = directory/tid/'record.json'
    record = json.loads(record_path.read_bytes())
    record['artifacts'][path.name] = sha256(path.read_bytes())
    record_path.write_bytes(canonical_json(record))
    previous = None
    for path in sorted((directory/'recovery-journal').glob('*.json')):
        value = json.loads(path.read_bytes())
        if value['kind'] == 'transition' and value['payload']['evidence'] is not None:
            evidence = value['payload']['evidence']
            evidence['sha256'] = sha256((directory/evidence['path']).read_bytes())
        value = entry(value['sequence'], previous, value['kind'], value['payload'])
        path.write_bytes(canonical_json(value))
        previous = value['entry_id']
    inventory = directory/'sha256.json'
    if inventory.exists():
        inventory.write_bytes(canonical_json({p.relative_to(directory).as_posix():sha256(p.read_bytes())
                                              for p in directory.rglob('*')
                                              if p.is_file() and p != inventory}))


def supplied_snapshot(record, process):
    """Synthetic mapping identity, explicitly supplied rather than collected."""
    value = snapshot()
    value['start'] = value['end'] = process['start']
    value['observed_executable_sha256'] = record['executable_sha256']
    value['openmp']['value']['executable_sha256'] = record['executable_sha256']
    return value


class MappingVerificationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = snapshot()
        self.bound = dict(pilot_execution_id='a'*64, environment={
            'b'*64:dict(OMP_NUM_THREADS='2', OMP_DYNAMIC='FALSE', OMP_THREAD_LIMIT='2')})
        self.trial = dict(trial_id='b'*64, workers=2)
        self.record = dict(trial=self.trial, executable_sha256=self.snapshot['observed_executable_sha256'])
        self.process = dict(command=['./runner','verify'], start='2026-01-01T00:00:00+00:00',
                            end='2026-01-01T00:00:03+00:00')
        self.origin = dict(kind='original', attempt_id=None)

    def check(self, value):
        observation = provenance(self.bound, self.trial, self.process, value, self.origin,
                                 self.record['executable_sha256'])
        verify(observation, self.bound, self.record, self.process, self.origin)

    def test_nested_exited_states_reject_top_level(self):
        for state in ('Z', 'X', 'x'):
            value = copy.deepcopy(self.snapshot)
            nested = value['openmp']['value']
            nested['process_stat'] = process_state(nested['process_stat'], state)
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'exited OpenMP mapping'):
                self.check(value)

    def test_distinct_live_states_remain_valid(self):
        for state in 'RSDTtKWPI':
            value = copy.deepcopy(self.snapshot)
            nested = value['openmp']['value']
            nested['process_stat'] = process_state(nested['process_stat'], state)
            with self.subTest(state=state):
                self.check(value)

    def test_missing_malformed_and_unsupported_nested_states(self):
        raw = self.snapshot['openmp']['value']['process_stat']
        for invalid in (None, '', process_state(raw, ''), process_state(raw, 'RR'), process_state(raw, '?')):
            value = copy.deepcopy(self.snapshot)
            value['openmp']['value']['process_stat'] = invalid
            with self.subTest(stat=invalid), self.assertRaises(ValueError):
                self.check(value)
        value = copy.deepcopy(self.snapshot)
        del value['openmp']['value']['process_stat']
        with self.assertRaises(ValueError):
            self.check(value)

    def test_nested_pid_start_and_executable_bindings(self):
        for key, invalid in (('pid',124), ('process_start_ticks',100001), ('executable_sha256','f'*64)):
            value = copy.deepcopy(self.snapshot)
            value['openmp']['value'][key] = invalid
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(value)
        # Internally consistent nested identities must still match the outer one.
        for raw in (self.snapshot['process_stat'].replace('123 (', '124 (', 1),
                    self.snapshot['process_stat'].replace('100000', '100001', 1)):
            value = copy.deepcopy(self.snapshot)
            nested = value['openmp']['value']
            nested['process_stat'] = raw
            nested['pid'] = int(raw.split(' ', 1)[0])
            nested['process_start_ticks'] = 100001 if '100001' in raw else 100000
            with self.subTest(stat=raw), self.assertRaises(ValueError):
                self.check(value)

    def test_outer_dead_with_live_mapping_rejects(self):
        for state in ('Z', 'X', 'x'):
            value = copy.deepcopy(self.snapshot)
            value['process_stat'] = process_state(value['process_stat'], state)
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.check(value)

    def test_unavailable_mapping_remains_valid(self):
        value = copy.deepcopy(self.snapshot)
        value['openmp'] = fact(None, 'fixture unavailable', 'child mapping snapshot')
        self.check(value)
        value = copy.deepcopy(self.snapshot)
        value['openmp']['status'] = 'unavailable'
        with self.assertRaises(ValueError):
            self.check(value)


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

    def test_rehashed_nested_dead_mapping_rejected_by_pilot(self):
        from campaign_pilot import verify_pilot
        from campaign_journal import inspect_recovery
        f = self.fixture; f.run_case()
        directory = f.root/'out'; record = f.record(); tid = record['trial']['trial_id']
        path = directory/tid/'0-verify.runtime.json'
        observation = json.loads(path.read_bytes())
        observation['snapshot'] = supplied_snapshot(record, record['processes'][0])
        replace_runtime(directory, tid, observation)
        verify_pilot(directory)  # Live supplied evidence passes the same hashes/schema.
        inspect_recovery(directory)
        for state in ('Z', 'X', 'x'):
            bad = copy.deepcopy(observation)
            nested = bad['snapshot']['openmp']['value']
            nested['process_stat'] = process_state(nested['process_stat'], state)
            replace_runtime(directory, tid, bad)
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, 'exited OpenMP mapping'):
                    verify_pilot(directory)
                with self.assertRaisesRegex(ValueError, 'exited OpenMP mapping'):
                    inspect_recovery(directory)

    def test_rehashed_nested_dead_mapping_blocks_resume_before_launch(self):
        from test_campaign_resume import ResumeTests
        from campaign_journal import inspect_recovery
        f = ResumeTests(); f.setUp(); self.addCleanup(f.doCleanups)
        f.initial()
        tid = f.ids[0]
        record = json.loads((f.out/tid/'record.json').read_bytes())
        observation = json.loads((f.out/tid/'0-verify.runtime.json').read_bytes())
        observation['snapshot'] = supplied_snapshot(record, record['processes'][0])
        replace_runtime(f.out, tid, observation)
        self.assertEqual(inspect_recovery(f.out)['trials'][0]['classification'], 'verified-complete')
        for state in ('Z', 'X', 'x'):
            bad = copy.deepcopy(observation)
            nested = bad['snapshot']['openmp']['value']
            nested['process_stat'] = process_state(nested['process_stat'], state)
            replace_runtime(f.out, tid, bad)
            before = f.snapshot(); marks = f.marks()
            with self.subTest(state=state), patch('campaign_resume.run_pilot') as launch:
                with self.assertRaisesRegex(ValueError, 'exited OpenMP mapping'):
                    f.resume()
                launch.assert_not_called()
                self.assertFalse(f.attempt.exists())
                self.assertEqual(f.snapshot(), before)
                self.assertEqual(f.marks(), marks)

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
