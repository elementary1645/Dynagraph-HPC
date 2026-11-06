"""Real bounded Linux sampling plus independently rehashed resource-evidence attacks."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'benchmarks/python'),str(ROOT/'tests')]
BENCH = Path(sys.argv.pop(1)).resolve() if __name__=='__main__' and len(sys.argv)>1 else Path(os.environ.get('DYNAGRAPH_PILOT_TEST_RUNNER',ROOT/'build/debug/dynagraph_bench'))
from artifacts import write_bundle
from campaign_contract import expand
from campaign_pilot import run_pilot, verify_pilot, read_json, put
from campaign_journal import inspect_recovery, Journal
from campaign_interference import NATIVE, BOUND, CONFIG, bind, complete, verify
from campaign_resume import resume_pilot
from campaign_workload import NATIVE as WN, BOUND as WB
from workloads import sha256, canonical_json
from test_campaign_workload import WorkloadTests

# Do not import its TestCase into discovery: only reuse the independent rehash utility.
rehash = WorkloadTests.rehash
del WorkloadTests


class ResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.base = Path(cls.tmp.name)
        cls.cpus = sorted(os.sched_getaffinity(0))[:2]
        cls.output, cls.trials = cls.pilot(cls.base/'baseline')
        cls.directory = cls.output/cls.trials[0]['trial_id']
        cls.native = read_json(cls.directory/NATIVE)
        cls.workload = read_json(cls.directory/WN)
        cls.workload_bound = read_json(cls.directory/WB)
        cls.receipt = read_json(cls.directory/'0-verify.affinity.json')
        cls.raw_config = (cls.directory/CONFIG).read_bytes()
        cls.bound = read_json(cls.directory/BOUND)
        cls.record = read_json(cls.directory/'record.json')
        # Stable synthetic control uses actual native identities and boundaries,
        # freezing only shared counters, never presented as an original measurement.
        cls.stable = copy.deepcopy(cls.native)
        for sample in cls.stable['samples'][1:]:
            for group, initial in zip(sample['groups'], cls.stable['samples'][0]['groups']):
                for key in ('cpu.stat','cpu.pressure'): group[key]=copy.deepcopy(initial[key])

    @classmethod
    def tearDownClass(cls):
        retained = os.environ.get('DYNAGRAPH_RESOURCE_EVIDENCE_DIR')
        if retained: shutil.copytree(cls.base,retained)
        cls.tmp.cleanup()

    @classmethod
    def pilot(cls,directory,cut=False,fail=False,interrupt=False):
        directory.mkdir(); root=directory/'inputs';root.mkdir();(root/'bin').mkdir()
        shutil.copyfile(BENCH,root/'bin/dynagraph_bench');(root/'bin/dynagraph_bench').chmod(0o700)
        plan=json.loads((ROOT/'benchmarks/configs/campaign-development-v1.json').read_bytes())
        plan['build']['executable_sha256']=sha256(BENCH.read_bytes());plan['hardware']['allocated_cpus']=cls.cpus
        write_bundle(plan['workloads'][0]['recipe'],root/'workloads/chain')
        manifest=expand(plan)
        trials=[t for t in manifest['trials'] if t['phase']=='diagnostic' and t['policy']=='delta-stepping'][:2]
        output=directory/'out'
        finish=Journal.finish
        def stop(journal,record):
            finish(journal,record);raise RuntimeError('between trials')
        def publish(directory,name,value):
            if name == BOUND: raise OSError('resource publication failure')
            return put(directory,name,value)
        from contextlib import ExitStack
        with ExitStack() as stack:
            if cut: stack.enter_context(patch.object(Journal,'finish',stop))
            if fail: stack.enter_context(patch('campaign_pilot.put',side_effect=publish))
            if interrupt: stack.enter_context(patch('campaign_runtime.collect',side_effect=KeyboardInterrupt))
            try:
                result=run_pilot(plan,manifest,root,output,[t['trial_id'] for t in trials],execute=True,
                    max_trials=2,enforce_affinity=True,observe_workload=True,observe_resources=True,wall_seconds=60,timeout=20)
            except RuntimeError:
                if not cut: raise
            else:
                if result['status'] != ('failed' if fail or interrupt else 'complete'):
                    raise AssertionError([read_json(output/t['trial_id']/'record.json') for t in trials])
        return output,trials

    def rebound(self,native=None,**kw):
        return bind(self.stable if native is None else native,kw.get('workload',self.workload),self.workload_bound,
            kw.get('receipt',self.receipt),self.raw_config,self.bound['sampling']['finished_ns'],
            self.record['hardware_sha256'],self.record['openmp_environment'])

    def test_real_native_pilot_offline_recovery(self):
        self.assertEqual(verify_pilot(self.output)['execution_status'],'complete')
        self.assertTrue(complete(self.bound),self.bound)
        self.assertEqual(len(self.native['samples']),4)
        self.assertEqual(self.workload['schema_version'],3)
        self.assertTrue(all(t['classification']=='verified-complete' for t in inspect_recovery(self.output)['trials']))
        self.assertFalse(self.bound['measurement_eligible'])

    def test_stable_control(self):
        self.assertEqual(self.rebound()['classification'],'observed_stable')
        self.assertTrue(complete(self.rebound()))

    def test_throttle_and_pressure_increases(self):
        for key,name in (('cpu.stat','nr_throttled'),('cpu.stat','throttled_usec'),('cpu.pressure','some'),('cpu.pressure','full')):
            n=copy.deepcopy(self.stable)
            for sample in n['samples'][1:]:
                raw=sample['groups'][0][key]['value']
                if key=='cpu.stat':
                    lines=raw.splitlines();raw='\n'.join(line.split()[0]+' '+str(int(line.split()[1])+1) if line.startswith(name+' ') else line for line in lines)+'\n'
                else:
                    lines=raw.splitlines();raw='\n'.join(line.rsplit('=',1)[0]+'='+str(int(line.rsplit('=',1)[1])+1) if line.startswith(name+' ') else line for line in lines)+'\n'
                sample['groups'][0][key]['value']=raw
            result=self.rebound(n)
            self.assertEqual(result['classification'],'observed_interference',result)
            self.assertTrue(complete(result))

    def test_configuration_changes(self):
        for name in ('quota','cpuset','online','inode','topology','pre-go-quota'):
            n=copy.deepcopy(self.stable);s=n['samples'][-1]
            if name=='quota': s['groups'][0]['cpu.max']['value']='100000 100000\n'
            if name=='pre-go-quota':
                for sample in n['samples']:sample['groups'][0]['cpu.max']['value']='100000 100000\n'
            if name=='cpuset': s['groups'][0]['cpuset.cpus.effective']['value']=str(self.cpus[0])+'\n'
            if name=='online':
                s['online']['value']=s['online_after']['value']=str(self.cpus[0])+'\n'
            if name=='inode':s['groups'][0]['identity']['inode']+=1
            if name=='topology': s['topology'][0]['core_id']['value']=str(int(s['topology'][0]['core_id']['value'])+1)+'\n'
            result=self.rebound(n)
            self.assertEqual(result['classification'],'observed_configuration_change',(name,result))

    def test_unavailable_unsupported_and_counter_reset(self):
        for mode in ('missing','v1','reset','gap'):
            n=copy.deepcopy(self.stable)
            if mode=='missing':n['samples'][0]['groups'][0]['cpu.pressure']=dict(value=None,errno=2)
            if mode=='v1':
                for s in n['samples']:s['membership']=s['membership_after']=dict(value='2:cpu:/\n',errno=0)
            if mode=='reset':
                n['samples'][-1]['groups'][0]['cpu.stat']['value']=n['samples'][-1]['groups'][0]['cpu.stat']['value'].replace('usage_usec '+n['samples'][-1]['groups'][0]['cpu.stat']['value'].splitlines()[0].split()[1],'usage_usec 0')
            if mode=='gap':
                # Rehash a publication interval outside the bounded policy.
                result=bind(n,self.workload,self.workload_bound,self.receipt,self.raw_config,
                    self.bound['sampling']['finished_ns']+3_000_000_000,self.record['hardware_sha256'],self.record['openmp_environment'])
            else:result=self.rebound(n)
            self.assertEqual(result['classification'],'insufficient_evidence',(mode,result))
            self.assertFalse(complete(result))
        n['samples'][0]['pid']+=1
        self.assertEqual(self.rebound(n)['classification'],'contradictory_evidence')

    def test_semantic_contradiction_matrix(self):
        def generation(n):
            s=n['samples'][0];raw=s['process_stat']['value'];i=raw.rfind(') ');tokens=raw[i+2:].split();tokens[19]=str(int(tokens[19])+1);s['process_stat']['value']=raw[:i+2]+' '.join(tokens)+'\n'
        def session(n):
            s=n['samples'][0];raw=s['process_stat']['value'];i=raw.rfind(') ');tokens=raw[i+2:].split();tokens[3]=str(int(tokens[3])+1);s['process_stat']['value']=raw[:i+2]+' '.join(tokens)+'\n'
        mutations = {
            'boolean-region':lambda n:n['samples'][1].update(region_id=False),
            'boolean-topology':lambda n:n['samples'][0]['topology'][0].update(cpu=False),
            'numeric':lambda n:n['samples'][0]['groups'][0]['cpu.stat'].update(value='usage_usec NaN\n'),
            'truncated':lambda n:n['samples'].pop(),
            'generation':generation,
            'wrong-boundary':lambda n:n['samples'][1].update(boundary='post'),
            'outside-workload':lambda n:n['samples'][1].update(start_ns=n['samples'][0]['end_ns']),
            'foreign-task':lambda n:n['samples'][1].update(tid=n['samples'][1]['tid']+1),
            'errno':lambda n:n['samples'][0]['groups'][0]['cpu.max'].update(errno=2),
            'missing-ancestry':lambda n:n['samples'][0]['groups'].pop(),
            'leader-session':session,
            'boot':lambda n:n['samples'][0]['boot_id'].update(value='f'*36),
        }
        for name,mutate in mutations.items():
            n=copy.deepcopy(self.stable);mutate(n)
            b=self.rebound(n)
            self.assertEqual(b['classification'],'contradictory_evidence',(name,b))
            with self.assertRaises(ValueError): verify(b,n,self.workload,self.workload_bound,self.receipt,self.raw_config,
                self.record['hardware_sha256'],self.record['openmp_environment'],True)
        receipt=copy.deepcopy(self.receipt);receipt['release']['state']='indeterminate';receipt['released']=None
        self.assertEqual(self.rebound(receipt=receipt)['classification'],'contradictory_evidence')

    def test_rehashed_pipeline_forgeries(self):
        for attack in ('native','classification','cross-trial','workload','config','missing','truncated-json','optout'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as tmp:
                output=Path(tmp)/'copy';shutil.copytree(self.output,output);base=output/self.trials[0]['trial_id']
                if attack=='native':
                    n=read_json(base/NATIVE);n['samples'][0]['pid']+=1;(base/NATIVE).write_bytes(canonical_json(n))
                    b=self.rebound(n);b['classification']='observed_stable';b['coverage_complete']=True
                    b=__import__('campaign_workload').seal(b);(base/BOUND).write_bytes(canonical_json(b))
                if attack=='classification':
                    b=read_json(base/BOUND);b['classification']='observed_stable' if b['classification']!='observed_stable' else 'observed_interference'
                    (base/BOUND).write_bytes(canonical_json(__import__('campaign_workload').seal(b)))
                if attack=='cross-trial':shutil.copyfile(output/self.trials[1]['trial_id']/BOUND,base/BOUND)
                if attack=='workload':
                    b=read_json(base/BOUND);b['workload_sha256']='a'*64;(base/BOUND).write_bytes(canonical_json(__import__('campaign_workload').seal(b)))
                if attack=='config':(base/CONFIG).write_bytes((base/CONFIG).read_bytes().replace(b'/sys/fs/cgroup/init',b'/sys/fs/cgroup/else'))
                if attack=='missing':(base/NATIVE).unlink()
                if attack=='truncated-json':(base/NATIVE).write_bytes((base/NATIVE).read_bytes()[:-5])
                if attack=='optout':
                    e=read_json(output/'execution-manifest.json');del e['resource_policy'];(output/'execution-manifest.json').write_bytes(canonical_json(e))
                rehash(self,output)
                with self.assertRaises(ValueError):verify_pilot(output)
                with self.assertRaises(ValueError):inspect_recovery(output)

    def test_incomplete_publication_and_interruption(self):
        for mode in ('fail','interrupt'):
            with tempfile.TemporaryDirectory() as tmp:
                output,trials=self.pilot(Path(tmp)/mode,**{mode:True})
                self.assertEqual(verify_pilot(output)['execution_status'],'failed')
                if mode=='interrupt':
                    record=read_json(output/trials[0]['trial_id']/'record.json')
                    self.assertEqual(record['reason'],'interrupted')
                    self.assertEqual(len(record['processes']),1)
                    self.assertTrue(read_json(output/trials[0]['trial_id']/'0-verify.affinity.json')['released'])
                self.assertTrue(all(t['classification']!='verified-complete' for t in inspect_recovery(output)['trials']))
                with self.assertRaises(ValueError):resume_pilot(output,execute=True,authorize=True,enforce_affinity=True,observe_workload=True,observe_resources=True)

    def test_explicit_opt_in_and_time_rejection(self):
        from campaign_pilot import command
        from campaign_resume import header
        from campaign_interference import configuration
        import subprocess
        with self.assertRaises(ValueError):resume_pilot(self.output,execute=True,authorize=True,observe_resources=1)
        plan=read_json(self.output/'plan.json');manifest=read_json(self.output/'trial-manifest.json')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):run_pilot(plan,manifest,self.base/'baseline/inputs',Path(tmp)/'out',
                [self.trials[0]['trial_id']],execute=True,observe_resources=True)
            proc=subprocess.run([str(BENCH),'time','--resource-observations',str(Path(tmp)/'resource.json')],capture_output=True,timeout=5)
            self.assertNotEqual(proc.returncode,0);self.assertFalse((Path(tmp)/'resource.json').exists())
        for raw in (b'',self.raw_config[:-1],self.raw_config.replace(b'DYNAGRAPH_RESOURCE_PATHS 1',b'DYNAGRAPH_RESOURCE_PATHS 2')):
            with self.assertRaises(ValueError):configuration(raw)

    def test_bound_shape_policy_and_identity_tampering(self):
        for key in ('binding','process_generation','enforcement_sha256','workload_sha256','openmp_environment_sha256','sampling'):
            bound=copy.deepcopy(self.bound);bound.pop(key)
            with self.assertRaises(ValueError):verify(bound,self.native,self.workload,self.workload_bound,self.receipt,
                self.raw_config,self.record['hardware_sha256'],self.record['openmp_environment'],True)
        for key in ('max_gap_ns','max_span_ns','max_samples','max_paths'):
            bound=copy.deepcopy(self.bound);bound['sampling'][key]*=2
            bound=__import__('campaign_workload').seal(bound)
            with self.assertRaises(ValueError):verify(bound,self.native,self.workload,self.workload_bound,self.receipt,
                self.raw_config,self.record['hardware_sha256'],self.record['openmp_environment'],True)

    def test_safe_resume_renewal_and_immutable_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            output,trials=self.pilot(Path(tmp)/'cut',cut=True)
            original={str(p.relative_to(output)):sha256(p.read_bytes()) for p in output.rglob('*') if p.is_file()}
            with self.assertRaises(ValueError):resume_pilot(output,execute=True,authorize=True,enforce_affinity=True,observe_workload=True)
            result=resume_pilot(output,execute=True,authorize=True,enforce_affinity=True,observe_workload=True,observe_resources=True)
            self.assertEqual(result['execution_status'],'complete',result)
            self.assertEqual([t['disposition'] for t in result['trials']],['reused','new'])
            self.assertEqual(original,{str(p.relative_to(output)):sha256(p.read_bytes()) for p in output.rglob('*') if p.is_file()})
            with self.assertRaises(FileExistsError):resume_pilot(output,execute=True,authorize=True,enforce_affinity=True,observe_workload=True,observe_resources=True)


if __name__=='__main__':unittest.main()
