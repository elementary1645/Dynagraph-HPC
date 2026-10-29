"""Campaign foundation regressions; synthetic hardware, no timed execution."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'benchmarks/python'))
from artifacts import generate
from campaign_contract import EVIDENCE, expand, load_bytes, plan_hash, validate_plan
from campaign_hardware import (admit, cgroup_ancestry, cpu_list, inspect, mapped_runtime,
                               observation, summarize_cgroups)
from experiment_records import POLICIES
from workloads import canonical_json


def fixture():
    recipe = json.loads((ROOT/'benchmarks/configs/chain-v1.json').read_bytes())
    manifest, graph, trace = generate(recipe)
    return dict(schema_version=1, campaign_id='foundation-fixture', panel='service-control',
        measurement_level='engine-update-service-v1', timing_mode='full-trace',
        workloads=[dict(id=recipe['workload_id'], recipe=recipe,
            recipe_sha256=hashlib.sha256(canonical_json(recipe)).hexdigest(),
            graph_sha256=hashlib.sha256(graph).hexdigest(), trace_sha256=hashlib.sha256(trace).hexdigest(),
            bundle='workloads/chain')],
        configurations=[dict(id='one',workers=1,delta=16),dict(id='two',workers=2,delta=16)],
        policies=list(POLICIES), no_effect='shared_fast_path',
        heuristic=dict(small_graph_edges=4096,repair_max_degree=32,parallel_min_edges=65536),
        sessions=['session-a','session-b'], blocks=4,warmups=2,diagnostics=1,order_seed=7,
        order_version='campaign-balanced-four-v1',
        build=dict(revision='a'*40,build_type='Release',executable='bin/dynagraph_bench',
                   executable_sha256='a'*64,compiler_sha256='b'*64,openmp_sha256='c'*64,
                   flags_sha256='d'*64,uninstrumented=True),
        hardware=dict(mode='scientific',allocated_cpus=[0,2],min_physical_cores=2,allow_smt=False,
            allow_virtualization=False,min_available_memory_bytes=4096,require_frequency_evidence=True,
            exclusive=True,reservation='Synthetic exclusive host fixture; never real hardware evidence'),
        limits=dict(max_trials=1000,timeout_seconds=60,max_memory_bytes=4096,max_output_bytes=1048576),
        expected_evidence=list(EVIDENCE),
        comparisons=[dict(kind='worker-scaling',numerator='two',baseline='one')])


def hardware():
    report = {k:observation(None, 'synthetic unavailable') for k in
              ('cpu_model logical_cpus topology numa affinity cgroups available_memory_bytes os kernel '
               'virtualization compiler openmp executable_sha256 placement frequency').split()}
    report.update(schema='dynagraph-hardware',schema_version=1,limitations=['SYNTHETIC'])
    values = dict(cpu_model='synthetic CPU',logical_cpus=4,
        topology=[dict(cpu=i,package=0,core=i//2,siblings=[i//2*2,i//2*2+1]) for i in range(4)],
        numa=[dict(node=0,cpus=[0,1,2,3])],affinity=[0,2],
        cgroups=summarize_cgroups([{'path':'/cg/leaf','cpu.max':'200000 100000','cpuset.cpus.effective':'0-3',
                                    'memory.max':'16384','memory.current':'1024'},
                                  {'path':'/cg','cpu.max':'max 100000','cpuset.cpus.effective':'0-3',
                                    'memory.max':'max','memory.current':'1024'}]),
        available_memory_bytes=8192,os='fixture',kernel='fixture',
        virtualization=dict(hypervisor=False,container=False,product='fixture'),
        compiler=dict(sha256='b'*64),
        openmp=dict(sha256='c'*64,linkage='observed-process-mapping',executable_sha256='a'*64),
        executable_sha256='a'*64,placement=dict(taskset='/usr/bin/taskset'),
        frequency=[dict(cpu=i,governor='performance') for i in (0,2)])
    for k,v in values.items(): report[k]=observation(v,'SYNTHETIC fixture')
    return report


class CampaignTests(unittest.TestCase):
    def setUp(self): self.p=fixture()

    def reject(self, change, diagnostic):
        p=copy.deepcopy(self.p); change(p)
        with self.assertRaisesRegex(ValueError,diagnostic): validate_plan(p)

    def test_canonical_hash_order_and_roundtrip(self):
        reversed_plan=dict(reversed(list(self.p.items())))
        self.assertEqual(plan_hash(self.p),plan_hash(reversed_plan))
        self.assertEqual(validate_plan(load_bytes(canonical_json(self.p))),self.p)
        self.p['order_seed']+=1
        self.assertNotEqual(plan_hash(self.p),plan_hash(fixture()))

    def test_expansion_stable_unique_and_coverage(self):
        a=expand(self.p);b=expand(copy.deepcopy(self.p))
        self.assertEqual(canonical_json(a),canonical_json(b))
        trials=a['trials'];self.assertEqual(len(trials),208)
        self.assertEqual(len({t['trial_id'] for t in trials}),len(trials))
        self.assertEqual([t['sequence'] for t in trials],list(range(len(trials))))
        self.assertEqual({t['phase'] for t in trials},{'warmup','diagnostic','measured'})
        for c in self.p['configurations']:
            for s in self.p['sessions']:
                rows=[t for t in trials if t['configuration_id']==c['id'] and t['session']==s and t['phase']=='measured']
                for policy in POLICIES:
                    self.assertEqual(sorted(t['policy_position'] for t in rows if t['policy']==policy),[0,1,2,3])
                adjacent=[]
                for block in range(4):
                    ordered=sorted([t for t in rows if t['block']==block],key=lambda t:t['policy_position'])
                    adjacent.extend((a['policy'],b['policy']) for a,b in zip(ordered,ordered[1:]))
                self.assertEqual(len(set(adjacent)),12)

    def test_seeds_change_order_preserve_coverage(self):
        a=expand(self.p);self.p['order_seed']=8;b=expand(self.p)
        key=lambda t:(t['session'],t['workload_id'],t['configuration_id'],t['policy'],t['phase'],t['block'])
        self.assertEqual(sorted(map(key,a['trials'])),sorted(map(key,b['trials'])))
        self.assertNotEqual([key(t) for t in a['trials']],[key(t) for t in b['trials']])

    def test_hash_randomization_independence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'plan.json';path.write_bytes(canonical_json(self.p))
            command=[sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'expand','--plan',str(path)]
            outputs=[subprocess.check_output(command,env=dict(os.environ,PYTHONHASHSEED=seed)) for seed in ('1','42')]
            self.assertEqual(*outputs)

    def test_versions_unknown_and_missing(self):
        for value in (0,2,True,'1'):
            self.reject(lambda p:p.update(schema_version=value),'schema version')
        self.reject(lambda p:p.update(extra=1),'exactly')
        self.reject(lambda p:p['limits'].update(extra=1),'exactly')
        self.reject(lambda p:p.pop('warmups'),'exactly')

    def test_json_adversaries(self):
        for raw in (b'{"x":1,"x":2}',b'NaN',b'Infinity',b'1.5',b'\xff',b'['*1000+b']'*1000):
            with self.subTest(raw=raw[:20]),self.assertRaises(ValueError): load_bytes(raw)
        with self.assertRaisesRegex(ValueError,'size limit'): load_bytes(b' '*1048577)

    def test_paths(self):
        for value in ('../x','/x','a//b','a/./b','a/../b','a\\b','C:x','x\n',''):
            self.reject(lambda p:p['workloads'][0].update(bundle=value),'unsafe')
            self.reject(lambda p:p['build'].update(executable=value),'unsafe')

    def test_resources_and_excessive_expansion(self):
        self.reject(lambda p:p['limits'].update(max_trials=207),'trial limit')
        self.reject(lambda p:p.update(blocks=3),'blocks')
        self.reject(lambda p:p.update(warmups=101),'warmups')
        self.reject(lambda p:p['limits'].update(timeout_seconds=3601),'timeout')
        self.reject(lambda p:p['limits'].update(max_memory_bytes=8192),'memory minimum')
        self.reject(lambda p:p['configurations'][0].update(workers=0),'workers')
        self.reject(lambda p:p['configurations'][0].update(workers=3),'incompatible')

    def test_identity_and_recipe_guards(self):
        self.reject(lambda p:p['workloads'][0].update(recipe_sha256='f'*64),'recipe hash')
        self.reject(lambda p:p['build'].update(executable_sha256='x'),'SHA-256')
        self.reject(lambda p:p['workloads'].append(copy.deepcopy(p['workloads'][0])),'duplicate workload')
        self.reject(lambda p:p['sessions'].append(p['sessions'][0]),'duplicate session')
        self.reject(lambda p:p['configurations'].append(copy.deepcopy(p['configurations'][0])),'duplicate configuration')

    def test_comparison_guards(self):
        self.reject(lambda p:p['configurations'][1].update(delta=32),'incompatible cross')
        self.reject(lambda p:p['comparisons'][0].update(baseline='unknown'),'unknown')
        self.reject(lambda p:p['comparisons'][0].update(kind='anything'),'incompatible cross')
        self.reject(lambda p:p['comparisons'].append(copy.deepcopy(p['comparisons'][0])),'duplicate comparison')

    def test_no_unsupported_scientific_changes(self):
        self.reject(lambda p:p.update(measurement_level='kernel'),'unsupported')
        self.reject(lambda p:p.update(policies=['dijkstra']),'four canonical')
        self.reject(lambda p:p['heuristic'].update(small_graph_edges=1),'unchanged heuristic')
        self.reject(lambda p:p['build'].update(build_type='Debug'),'Release')
        self.reject(lambda p:p['build'].update(uninstrumented=False),'uninstrumented')

    def test_declaration_conflicts(self):
        self.reject(lambda p:p['hardware'].update(min_physical_cores=3),'exceeds allocated')
        self.reject(lambda p:p['hardware'].update(exclusive=False),'exclusive reservation')
        self.reject(lambda p:p['hardware'].update(mode='development'),'development declarations')

    def test_positive_scientific_fixture(self):
        result=admit(self.p,hardware())
        self.assertEqual(result['plan_sha256'],plan_hash(self.p))
        self.assertEqual(result['hardware_sha256'],hashlib.sha256(canonical_json(hardware())).hexdigest())
        self.assertTrue(result['admitted']);self.assertTrue(result['scientific_performance_allowed'])
        self.assertFalse(result['multicore_scaling_claims_allowed'])
        self.assertEqual(result['declarations']['origin'],'user_declared')

    def test_missing_provenance_fails_closed(self):
        for key in ('affinity','topology','cgroups','available_memory_bytes','compiler','openmp','executable_sha256','virtualization','frequency'):
            r=hardware();r[key]=observation(None,'missing fixture')
            with self.subTest(key=key): self.assertFalse(admit(self.p,r)['admitted'])

    def test_smt_and_insufficient_core_rejection(self):
        r=hardware();r['affinity']['value']=[0,1];self.p['hardware']['allocated_cpus']=[0,1]
        result=admit(self.p,r);self.assertIn('insufficient physical cores',result['failures'])
        self.assertIn('SMT siblings disallowed',result['failures'])

    def test_affinity_and_cpuset_rejection(self):
        r=hardware();r['affinity']['value']=[0,1,2]
        self.assertFalse(admit(self.p,r)['admitted'])
        r=hardware();r['cgroups']['value']['ancestors'][0]['cpuset.cpus.effective']='0-1'
        r['cgroups']['value']=summarize_cgroups(r['cgroups']['value']['ancestors'])
        self.assertIn('allocation outside effective cgroup cpuset',admit(self.p,r)['failures'])

    def test_ancestor_quota_and_memory(self):
        r=hardware();r['cgroups']['value']['ancestors'][1]['cpu.max']='100000 100000'
        r['cgroups']['value']=summarize_cgroups(r['cgroups']['value']['ancestors'])
        self.assertIn('ancestor CPU quota below requested workers',admit(self.p,r)['failures'])
        r=hardware();r['available_memory_bytes']['value']=1024
        self.assertFalse(admit(self.p,r)['admitted'])

    def test_contradictory_reports(self):
        r=hardware();r['topology']['value'][0]['siblings']=[0]
        self.assertIn('missing or contradictory physical topology',admit(self.p,r)['failures'])
        r=hardware();r['cgroups']['value']['quota_pairs']=[]
        self.assertIn('contradictory cgroup summaries',admit(self.p,r)['failures'])
        r=hardware();r['affinity']['origin']='unavailable'
        with self.assertRaisesRegex(ValueError,'contradictory'): admit(self.p,r)

    def test_nested_boolean_numeric_aliases(self):
        r=hardware();r['affinity']['value']=[False,2]
        self.assertFalse(admit(self.p,r)['admitted'])
        r=hardware();r['topology']['value'][0]['siblings']=[False,True]
        self.assertFalse(admit(self.p,r)['admitted'])
        r=hardware();r['cgroups']['value']['effective_cpuset']=[False,1,2,3]
        self.assertFalse(admit(self.p,r)['admitted'])
        r=hardware();r['frequency']['value'][0]['governor']=True
        self.assertFalse(admit(self.p,r)['admitted'])

    def test_unresolved_runtime_rejected(self):
        r=hardware();r['openmp']['value']['linkage']='DT_NEEDED candidate'
        self.assertIn('actual linked OpenMP runtime resolution is unverified',admit(self.p,r)['failures'])
        r=hardware();r['openmp']['value']['sha256']='e'*64
        self.assertIn('missing or mismatched openmp identity',admit(self.p,r)['failures'])

    def test_virtualized_host(self):
        r=hardware();r['virtualization']['value']['hypervisor']=True
        self.assertFalse(admit(self.p,r)['admitted'])
        self.p['hardware']['allow_virtualization']=True
        self.assertTrue(admit(self.p,r)['admitted'])

    def test_development_only(self):
        self.p['hardware'].update(mode='development',exclusive=False,reservation='')
        r=hardware()
        for k in ('topology','openmp','affinity'): r[k]=observation(None,'unavailable')
        result=admit(self.p,r)
        self.assertTrue(result['admitted']);self.assertFalse(result['scientific_performance_allowed'])
        self.assertTrue(result['failures']);self.assertEqual(result['qualification'],'development-only')

    def test_cpu_list_limits(self):
        self.assertEqual(cpu_list('0-2,4'),[0,1,2,4])
        for value in ('0-999999999','a','-1','2-1','',None):
            with self.assertRaises(ValueError): cpu_list(value)

    def cgroup_files(self):
        d={'/proc/self/cgroup':'0::/tenant/job',
           '/proc/self/mountinfo':'1 0 0:1 /tenant /cg rw - cgroup2 cgroup rw'}
        for path,quota in [('/cg/job','max 100000'),('/cg','150000 100000')]:
            d.update({path+'/cpu.max':quota,path+'/cpuset.cpus.effective':'0-3',
                      path+'/memory.max':'8192',path+'/memory.current':'1024'})
        return d

    def test_cgroup_mount_root_and_ancestors(self):
        result=cgroup_ancestry(self.cgroup_files().get)
        self.assertEqual([r['path'] for r in result['ancestors']],['/cg/job','/cg'])
        self.assertEqual(result['quota_pairs'],[[150000,100000]])
        self.assertEqual(result['memory_headroom_bytes'],7168)

    def test_cgroup_missing_and_malformed(self):
        d=self.cgroup_files();d.pop('/cg/cpu.max')
        with self.assertRaisesRegex(ValueError,'missing'): cgroup_ancestry(d.get)
        d=self.cgroup_files();d['/proc/self/cgroup']='0::/elsewhere'
        with self.assertRaisesRegex(ValueError,'does not resolve'): cgroup_ancestry(d.get)
        d=self.cgroup_files();d['/cg/cpu.max']='100 0'
        with self.assertRaisesRegex(ValueError,'quota'): cgroup_ancestry(d.get)

    def test_missing_inspection_never_infers_cores(self):
        report=inspect(read=lambda p:None,affinity=[0,1],binaries=False)
        self.assertIsNone(report['topology']['value'])
        self.assertIsNone(report['logical_cpus']['value'])
        self.assertFalse(admit(self.p,report)['admitted'])

    def test_inspection_fixture(self):
        d=self.cgroup_files()
        d.update({'/sys/devices/system/cpu/online':'0-3','/sys/devices/system/node/online':'0',
                  '/sys/devices/system/node/node0/cpulist':'0-3','/proc/cpuinfo':'model name : fixture\nflags : hypervisor',
                  '/proc/meminfo':'MemAvailable: 64 kB','/etc/os-release':'fixture',
                  '/proc/sys/kernel/osrelease':'fixture'})
        for cpu in range(4):
            prefix=f'/sys/devices/system/cpu/cpu{cpu}/topology/'
            d.update({prefix+'physical_package_id':'0',prefix+'core_id':str(cpu//2),
                      prefix+'thread_siblings_list':f'{cpu//2*2}-{cpu//2*2+1}'})
        r=inspect(read=d.get,affinity=[0,2],binaries=False)
        self.assertEqual(r['logical_cpus']['value'],4)
        self.assertEqual(r['available_memory_bytes']['value'],7168)
        self.assertTrue(r['virtualization']['value']['hypervisor'])

    def test_mapped_runtime_missing_and_pid_reuse(self):
        self.assertIsNone(mapped_runtime(1,None))
        self.assertIsNone(mapped_runtime(1,'/missing',read=lambda p:None))

    def test_planning_never_launches_process(self):
        with patch('subprocess.run',side_effect=AssertionError('no execution')), patch('subprocess.Popen',side_effect=AssertionError('no execution')):
            validate_plan(self.p);expand(self.p)

    def test_legacy_goldens_unchanged(self):
        p=self.p['workloads'][0]
        manifest,graph,trace=generate(p['recipe'])
        self.assertEqual(hashlib.sha256(graph).hexdigest(),p['graph_sha256'])
        self.assertEqual(hashlib.sha256(trace).hexdigest(),p['trace_sha256'])
        from experiment_records import configuration
        legacy=json.loads((ROOT/'benchmarks/configs/timing-smoke-v1.json').read_bytes())
        self.assertEqual(configuration(legacy)['timing_mode'],'full-trace')

    def test_all_missing_required_fields(self):
        for key in self.p:
            self.reject(lambda p:p.pop(key),'exactly')
        for key in hardware():
            r=hardware();r.pop(key)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'exactly'): admit(self.p,r)

    def test_malformed_top_level_values_controlled(self):
        for key in self.p:
            for bad in (None,[],{},True):
                if key == 'comparisons' and bad == []: continue
                p=copy.deepcopy(self.p);p[key]=bad
                with self.subTest(key=key,bad=bad),self.assertRaises(ValueError): validate_plan(p)

    def test_cgroup_memory_contradiction_and_count(self):
        r=hardware();r['available_memory_bytes']['value']=20000
        self.assertIn('available memory contradicts cgroup headroom',admit(self.p,r)['failures'])
        r=hardware();r['logical_cpus']['value']=128
        self.assertIn('contradictory logical CPU count',admit(self.p,r)['failures'])

    def test_malformed_hardware_values_controlled(self):
        for key in ('topology','affinity','cgroups','available_memory_bytes','virtualization','compiler','openmp','frequency'):
            for bad in ([],{},True,'invalid'):
                r=hardware();r[key]=observation(bad,'synthetic malformed')
                with self.subTest(key=key,bad=bad): self.assertFalse(admit(self.p,r)['admitted'])

    def test_single_worker_and_no_warmup(self):
        self.p['configurations']=self.p['configurations'][:1];self.p['comparisons']=[]
        self.p.update(warmups=0,diagnostics=0)
        rows=expand(self.p)['trials']
        self.assertEqual(len(rows),32)
        self.assertEqual({r['phase'] for r in rows},{'measured'})

    def test_mapped_runtime_observed_and_changed(self):
        # No process is launched: synthetic /proc maps and file digests.
        maps='1-2 r-xp 0 00:00 1 /lib/libgomp.so.1.0.0'
        stat='1 (fixture name) '+' '.join(['0']*30)
        def read(path): return maps if path.endswith('/maps') else stat
        info=SimpleNamespace(st_dev=os.makedev(0,0),st_ino=1,st_size=100,st_mtime_ns=1)
        with patch('campaign_hardware.file_hash',return_value='a'*64), patch('pathlib.Path.stat',return_value=info):
            value=mapped_runtime(1,'fixture',read)
            self.assertEqual(value['linkage'],'observed-process-mapping')
        with patch('campaign_hardware.file_hash',return_value='a'*64), patch('pathlib.Path.stat',return_value=SimpleNamespace(st_dev=0,st_ino=2)):
            self.assertIsNone(mapped_runtime(1,'fixture',read))
        with patch('campaign_hardware.file_hash',side_effect=['a'*64,'b'*64]):
            self.assertIsNone(mapped_runtime(1,'fixture',read))

    def test_cli_admission_exit_and_no_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan=Path(tmp)/'plan.json';report=Path(tmp)/'hardware.json'
            plan.write_bytes(canonical_json(self.p));r=hardware();r['openmp']=observation(None,'missing')
            report.write_bytes(canonical_json(r))
            cmd=[sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'admit',
                 '--plan',str(plan),'--hardware',str(report)]
            result=subprocess.run(cmd,capture_output=True)
            self.assertEqual(result.returncode,1);self.assertFalse(json.loads(result.stdout)['admitted'])
            self.p['hardware'].update(mode='development',exclusive=False,reservation='')
            plan.write_bytes(canonical_json(self.p));result=subprocess.run(cmd,capture_output=True)
            self.assertEqual(result.returncode,0)
            self.assertFalse(json.loads(result.stdout)['scientific_performance_allowed'])

    def test_cli_validate_and_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'plan.json';path.write_bytes(canonical_json(self.p))
            cmd=[sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'validate','--plan',str(path)]
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            path.write_text('{"schema_version":99}')
            result=subprocess.run(cmd,capture_output=True)
            self.assertEqual(result.returncode,2);self.assertNotIn(b'Traceback',result.stderr)


if __name__=='__main__': unittest.main(verbosity=2)
