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
                               observation, reconcile_cgroups)
from campaign_provenance import validate_runtime, validate_cgroups, topology_ids
from experiment_records import POLICIES
from workloads import canonical_json
from campaign_runtime_support import (elf_bytes, elf_evidence, patch_hex,
                                      harden_case, modified_runtime_file, add_load)
from campaign_elf import collect_elf, parse_elf, add


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


def runtime_fixture():
    numbers=[0]*49
    numbers[0]=1;numbers[1]=123;numbers[2]=123;numbers[18]=100000
    return dict(path='/usr/lib/libgomp.so.1.0.0',sha256='c'*64,soname='libgomp.so.1',
        linkage='observed-process-mapping',executable_sha256='a'*64,pid=123,
        evidence_version=3,page_size=4096,elf=elf_evidence(),executable_elf=elf_evidence(True),
        process_stat='123 (synthetic worker) S '+' '.join(map(str,numbers)),process_start_ticks=100000,
        mappings=['7f000000-7f002000 r-xp 00000000 08:01 7 /usr/lib/libgomp.so.1.0.0',
                  '7f005000-7f006000 r--p 00002000 08:01 7 /usr/lib/libgomp.so.1.0.0',
                  '7f006000-7f007000 rw-p 00003000 08:01 7 /usr/lib/libgomp.so.1.0.0'],
        file_identity=dict(device_major=8,device_minor=1,inode=7,size=0x3800,mtime_ns=1793284000000000000))


def cgroup_fixture():
    data={'/proc/self/cgroup':'0::/leaf','/proc/self/mountinfo':'1 0 0:1 / /cg rw - cgroup2 cgroup rw'}
    for path in ('/cg/leaf','/cg'):
        data.update({path+'/cpu.max':'200000 100000' if path.endswith('leaf') else 'max 100000',
                     path+'/cpuset.cpus.effective':'0-3',path+'/memory.max':'16384' if path.endswith('leaf') else 'max',
                     path+'/memory.current':'1024'})
    return cgroup_ancestry(data.get)


def hardware():
    report = {k:observation(None, 'synthetic unavailable') for k in
              ('cpu_model logical_cpus topology numa affinity cgroups available_memory_bytes os kernel '
               'virtualization compiler openmp executable_sha256 placement frequency').split()}
    report.update(schema='dynagraph-hardware',schema_version=2,limitations=['SYNTHETIC'])
    values = dict(cpu_model='synthetic CPU',logical_cpus=4,
        topology=[dict(cpu=i,package=0,core=i//2,siblings=[i//2*2,i//2*2+1]) for i in range(4)],
        numa=[dict(node=0,cpus=[0,1,2,3])],affinity=[0,2],
        cgroups=cgroup_fixture(),
        available_memory_bytes=8192,os='fixture',kernel='fixture',
        virtualization=dict(hypervisor=False,container=False,product='fixture'),
        compiler=dict(path='/usr/bin/g++',version='g++ synthetic 13.3.0',sha256='b'*64),
        openmp=runtime_fixture(),
        executable_sha256='a'*64,placement=dict(taskset='/usr/bin/taskset'),
        frequency=[dict(cpu=i,governor='performance',driver='synthetic',current_khz='2000000',
                        min_khz='1000000',max_khz='3000000') for i in (0,2)])
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
        r=hardware();r['cgroups']['value']['views'][0]['ancestors'][0]['cpuset.cpus.effective']='0-1'
        r['cgroups']['value']=reconcile_cgroups(r['cgroups']['value'])
        self.assertIn('allocation outside effective cgroup cpuset',admit(self.p,r)['failures'])

    def test_ancestor_quota_and_memory(self):
        r=hardware();r['cgroups']['value']['views'][0]['ancestors'][1]['cpu.max']='100000 100000'
        r['cgroups']['value']=reconcile_cgroups(r['cgroups']['value'])
        self.assertIn('ancestor CPU quota below requested workers',admit(self.p,r)['failures'])
        r=hardware();r['available_memory_bytes']['value']=1024
        self.assertFalse(admit(self.p,r)['admitted'])

    def test_contradictory_reports(self):
        r=hardware();r['topology']['value'][0]['siblings']=[0]
        self.assertIn('missing or contradictory physical topology',admit(self.p,r)['failures'])
        r=hardware();r['cgroups']['value']['quota_pairs']=[]
        self.assertIn('missing or malformed cgroup ancestry',admit(self.p,r)['failures'])
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
        r=hardware();r['openmp']['value']={k:v for k,v in r['openmp']['value'].items() if k in ('path','sha256','soname')}
        r['openmp']['value']['linkage']='candidate-library'
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
        self.assertEqual([r['path'] for r in result['views'][0]['ancestors']],['/cg/job','/cg'])
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
        sample=runtime_fixture();maps='\n'.join(sample['mappings']);stat=sample['process_stat']
        def read(path):return maps if path.endswith('/maps') else stat
        info=SimpleNamespace(st_dev=os.makedev(8,1),st_ino=7,st_size=0x3800,st_mtime_ns=1793284000000000000,st_ctime_ns=1793284000000000000)
        snapshots=[(elf_evidence(True),'a'*64,info),(elf_evidence(),'c'*64,info)]
        with patch('campaign_hardware.elf_file',side_effect=snapshots),patch('campaign_hardware.file_hash',return_value='a'*64),patch('pathlib.Path.stat',return_value=info):
            value=mapped_runtime(123,'fixture',read)
            self.assertEqual(value['linkage'],'observed-process-mapping')
        bad=SimpleNamespace(st_dev=os.makedev(8,1),st_ino=8,st_size=0x3800,st_mtime_ns=1793284000000000000,st_ctime_ns=1793284000000000000)
        with patch('campaign_hardware.elf_file',side_effect=[snapshots[0],(elf_evidence(),'c'*64,bad)]),patch('campaign_hardware.file_hash',return_value='a'*64),patch('pathlib.Path.stat',return_value=bad):
            self.assertIsNone(mapped_runtime(123,'fixture',read))
        with patch('campaign_hardware.elf_file',return_value=snapshots[0]),patch('campaign_hardware.file_hash',return_value='b'*64):
            self.assertIsNone(mapped_runtime(123,'fixture',read))

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

    def audit_mounts(self):
        d={'/proc/self/cgroup':'0::/tenant/job', '/proc/self/mountinfo':
           '1 0 0:1 / /full rw - cgroup2 cgroup rw\n2 0 0:1 /tenant /sub rw - cgroup2 cgroup rw'}
        for path in ('/full','/full/tenant','/full/tenant/job','/sub','/sub/job'):
            d.update({path+'/cpu.max':'100000 100000' if path=='/full' else 'max 100000',
                      path+'/cpuset.cpus.effective':'0-3',path+'/memory.max':'max',path+'/memory.current':'0'})
        return d

    def admission_cli(self, report, plan=None):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'plan.json';r=Path(tmp)/'hardware.json'
            p.write_bytes(canonical_json(self.p if plan is None else plan));r.write_bytes(canonical_json(report))
            return subprocess.run([sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'admit',
                                   '--plan',str(p),'--hardware',str(r)],capture_output=True,text=True)

    def test_audit_f1_overlapping_mounts_api(self):
        r=hardware();r['cgroups']=observation(cgroup_ancestry(self.audit_mounts().get),'synthetic overlap')
        self.assertFalse(admit(self.p,r)['scientific_performance_allowed'])

    def test_audit_f1_overlapping_mounts_cli(self):
        r=hardware();r['cgroups']=observation(cgroup_ancestry(self.audit_mounts().get),'synthetic overlap')
        self.assertNotEqual(self.admission_cli(r).returncode,0)

    def test_audit_f2_runtime_api(self):
        r=hardware();r['openmp']['value'].update(pid=-1,path=False,soname='libwrong.so',process_stat='')
        try: result=admit(self.p,r)
        except ValueError: return
        self.assertFalse(result['scientific_performance_allowed'])

    def test_audit_f2_runtime_cli(self):
        r=hardware();r['openmp']['value'].update(pid=-1,path=False,soname='libwrong.so',process_stat='')
        result=self.admission_cli(r);self.assertNotEqual(result.returncode,0)
        self.assertNotIn('Traceback',result.stderr)

    def test_audit_f3_nonallocated_sibling_api(self):
        r=hardware();r['topology']['value'][1]['siblings']=[1]
        try: result=admit(self.p,r)
        except ValueError: return
        self.assertFalse(result['scientific_performance_allowed'])

    def test_audit_f3_nonallocated_sibling_cli(self):
        r=hardware();r['topology']['value'][1]['siblings']=[1]
        self.assertNotEqual(self.admission_cli(r).returncode,0)

    def test_audit_f4_unicode_api(self):
        p=copy.deepcopy(self.p);p['build']['executable']='bin/'+chr(0xd800)
        with self.assertRaises(ValueError): validate_plan(p)

    def test_audit_f4_unicode_cli(self):
        p=copy.deepcopy(self.p);p['build']['executable']='bin/'+chr(0xd800)
        result=self.admission_cli(hardware(),p)
        self.assertNotEqual(result.returncode,0);self.assertNotIn('Traceback',result.stderr)

    def assert_not_scientific(self, report, cli=False):
        try:self.assertFalse(admit(self.p,report)['scientific_performance_allowed'])
        except ValueError:pass
        if cli:
            result=self.admission_cli(report)
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn('Traceback',result.stderr)

    def test_f1_anchored_truncation_and_metadata(self):
        for mutate in (
            lambda g:g['views'][0]['ancestors'].pop(),
            lambda g:g['views'][0]['ancestors'].pop(0),
            lambda g:g['views'][0].update(endpoint='/other'),
            lambda g:g['views'][0].update(root='/other'),
            lambda g:g['views'][0].update(mount_id=True),
            lambda g:g['views'][0]['ancestors'][0].update(cgroup_path='/wrong'),
            lambda g:g.update(membership='0::/other'),
            lambda g:g.update(mountinfo=g['mountinfo']+'\n2 0 0:1 / /alias rw - cgroup2 cgroup rw'),
        ):
            r=hardware();mutate(r['cgroups']['value']);self.assert_not_scientific(r,cli=True)

    def test_f1_missing_or_ambiguous_mounts(self):
        for change in (
            lambda d:d.pop('/full/cpu.max'),
            lambda d:d.update({'/proc/self/mountinfo':d['/proc/self/mountinfo']+'\n3 0 0:2 / /other rw - cgroup2 cgroup rw'}),
            lambda d:d.update({'/proc/self/mountinfo':d['/proc/self/mountinfo']+'\n2 0 0:1 / /another rw - cgroup2 cgroup rw'}),
            lambda d:d.update({'/sub/cpu.max':'200000 100000'}),
            lambda d:d.update({'/sub/cpuset.cpus.effective':'0-1'}),
        ):
            d=self.audit_mounts();change(d)
            with self.assertRaises(ValueError):cgroup_ancestry(d.get)

    def test_f1_restrictive_parent_cpuset_memory(self):
        d=self.audit_mounts();d['/full/cpuset.cpus.effective']='0-1'
        r=hardware();r['cgroups']=observation(cgroup_ancestry(d.get),'fixture')
        self.assert_not_scientific(r,cli=True)
        self.assertEqual(r['cgroups']['value']['effective_cpuset'],[0,1])
        d=self.audit_mounts();d['/full/memory.max']='2048'
        r['cgroups']=observation(cgroup_ancestry(d.get),'fixture')
        self.assertEqual(r['cgroups']['value']['memory_headroom_bytes'],2048)
        self.assert_not_scientific(r,cli=True)

    def test_f1_malformed_quota_and_memory(self):
        for key,text in [('cpu.max','max 0'),('cpu.max','0 100000'),('cpu.max','1.5 100000'),
                         ('cpu.max','100  100000'),('cpu.max','-1 100000'),('memory.max','unknown'),
                         ('memory.current',True)]:
            d=self.audit_mounts();d['/full/'+key]=text
            with self.subTest(key=key,text=text),self.assertRaises(ValueError):cgroup_ancestry(d.get)

    def test_f1_gauge_changes_and_determinism(self):
        d=self.audit_mounts();d['/sub/memory.current']='64'
        a=cgroup_ancestry(d.get);b=cgroup_ancestry(d.get)
        self.assertEqual(a,b)
        self.assertEqual([v['root'] for v in a['views']],['/','/tenant'])
        self.assertIn([100000,100000],a['quota_pairs'])
        with self.assertRaises(ValueError):validate_cgroups(dict(ancestors=[]))

    def test_f2_missing_and_unknown_mapping_fields(self):
        for key in runtime_fixture():
            r=hardware();r['openmp']['value'].pop(key);self.assert_not_scientific(r,cli=True)
        r=hardware();r['openmp']['value']['unexpected']=True;self.assert_not_scientific(r,cli=True)
        r=hardware();r['compiler']['value']['unexpected']=True;self.assert_not_scientific(r,cli=True)

    def test_f2_mapping_numeric_types_and_cross_checks(self):
        changes=[lambda v:v.update(pid=True),lambda v:v.update(pid=0),
                 lambda v:v.update(process_stat=''),lambda v:v.update(process_start_ticks=99999),
                 lambda v:v.update(path='../libgomp.so.1'),lambda v:v.update(soname='libgomp.so.2'),
                 lambda v:v.update(executable_sha256='d'*64),lambda v:v.update(sha256='d'*64),
                 lambda v:v['file_identity'].update(inode=8),lambda v:v['file_identity'].update(device_minor=2),
                 lambda v:v['file_identity'].update(size=0),lambda v:v['file_identity'].update(mtime_ns=True),
                 lambda v:v.update(mappings=[]),lambda v:v['mappings'].append(v['mappings'][0]),
                 lambda v:v.update(mappings=[v['mappings'][0].replace('08:01','08:02')]),
                 lambda v:v.update(mappings=[v['mappings'][0].replace('r-xp','nope')]),
                 lambda v:v.update(mappings=[v['mappings'][0].replace('7f002000','7f000000')]+v['mappings'][1:])]
        for change in changes:
            r=hardware();change(r['openmp']['value']);self.assert_not_scientific(r,cli=True)

    def test_f2_candidate_and_complete_positive_cli(self):
        r=hardware();self.assertEqual(self.admission_cli(r).returncode,0)
        candidate={k:v for k,v in r['openmp']['value'].items() if k in ('path','sha256','soname')}
        candidate['linkage']='candidate-library';validate_runtime(candidate)
        r['openmp']['value']=candidate;self.assert_not_scientific(r,cli=True)
        candidate['pid']=123
        with self.assertRaises(ValueError):validate_runtime(candidate)

    def test_f3_complete_topology_and_numa(self):
        changes=[lambda r:r['topology']['value'][3].update(siblings=[3]),
                 lambda r:r['topology']['value'][1].update(core=5),
                 lambda r:r['topology']['value'][1].update(siblings=[0,1,2]),
                 lambda r:r['topology']['value'][1].update(cpu=0),
                 lambda r:r['topology']['value'][1].update(siblings=[0,True]),
                 lambda r:r['topology']['value'][1].update(extra=1),
                 lambda r:r['numa'].update(value='bad'),
                 lambda r:r['numa'].update(value=[dict(node=0,cpus=[0,1])]),
                 lambda r:r['numa'].update(value=[dict(node=0,cpus=[0,1,2,3,4])]),
                 lambda r:r['numa'].update(value=[dict(node=0,cpus=[0,1]),dict(node=0,cpus=[2,3])]),
                 lambda r:r['numa'].update(value=[dict(node=0,cpus=[0,2]),dict(node=1,cpus=[1,3])]),
                 lambda r:r['numa'].update(value=[dict(node=0,cpus=[0,1,2]),dict(node=1,cpus=[2,3])])]
        for change in changes:
            r=hardware();change(r);self.assert_not_scientific(r,cli=True)

    def test_f3_optional_absent_and_valid_multinode(self):
        r=hardware();r['numa']=observation(None,'genuinely unavailable')
        self.assertTrue(admit(self.p,r)['scientific_performance_allowed'])
        r['numa']=observation([dict(node=0,cpus=[0,1]),dict(node=1,cpus=[2,3])],'synthetic two-node')
        self.assertTrue(admit(self.p,r)['scientific_performance_allowed'])
        for key in ('virtualization','placement','frequency'):
            r=hardware()
            if key=='frequency':r[key]['value'][0]['unknown']=1
            else:r[key]['value']['unknown']=1
            self.assert_not_scientific(r)

    def test_f4_unicode_encoding_and_legitimate_paths(self):
        for path in ('bin/'+chr(0xd800),'bin/'+chr(0xdc80),'work/'+chr(0xdfff)):
            for kind in ('build','workload'):
                p=copy.deepcopy(self.p)
                if kind=='build':p['build']['executable']=path
                else:p['workloads'][0]['bundle']=path
                with self.assertRaisesRegex(ValueError,'encoding'):validate_plan(p)
                result=self.admission_cli(hardware(),p)
                self.assertEqual(result.returncode,2);self.assertNotIn('Traceback',result.stderr)
        hashes=[]
        for path in ('bin/caf\u00e9','bin/cafe\u0301','bin/\u56fe worker'):
            p=copy.deepcopy(self.p);p['build']['executable']=path
            validate_plan(p);hashes.append(plan_hash(p))
            self.assertEqual(self.admission_cli(hardware(),p).returncode,0)
        self.assertEqual(len(set(hashes)),3)

    def test_hardware_v1_not_silently_upgraded(self):
        r=hardware();r['schema_version']=1
        with self.assertRaisesRegex(ValueError,'unsupported hardware'):admit(self.p,r)
        result=self.admission_cli(r);self.assertEqual(result.returncode,2)

    def test_f2_process_and_mapping_nearby_cases(self):
        for change in (lambda v:v.update(process_stat=v['process_stat'].replace('123 (','124 (',1)),
                       lambda v:v.update(process_stat='123 (worker) S '+' '.join(['0']*19)),
                       lambda v:v['file_identity'].update(inode=True),
                       lambda v:v.update(mappings=[v['mappings'][0].replace('libgomp.so.1.0.0','libgomp.so.2')])):
            r=hardware();change(r['openmp']['value']);self.assert_not_scientific(r,cli=True)
        sample=runtime_fixture();maps='\n'.join(sample['mappings']);stat=sample['process_stat']
        def read(path):
            if path.endswith('/maps'):return maps
            read.calls+=1
            return stat if read.calls==1 else stat.replace('100000','100001')
        read.calls=0
        info=SimpleNamespace(st_dev=os.makedev(8,1),st_ino=7,st_size=0x3800,st_mtime_ns=1793284000000000000,st_ctime_ns=1793284000000000000)
        with patch('campaign_hardware.elf_file',side_effect=[(elf_evidence(True),'a'*64,info),(elf_evidence(),'c'*64,info)]),patch('campaign_hardware.file_hash',return_value='a'*64),patch('pathlib.Path.stat',return_value=info):
            self.assertIsNone(mapped_runtime(123,'fixture',read))

    def test_f3_memory_only_numa_node(self):
        r=hardware();r['numa']['value'].append(dict(node=1,cpus=[]))
        self.assertTrue(admit(self.p,r)['scientific_performance_allowed'])

    def test_collector_missing_cgroup_is_explicit(self):
        d=self.audit_mounts();d.pop('/full/cpu.max')
        r=inspect(read=d.get,affinity=[0,2],binaries=False)
        self.assertIsNone(r['cgroups']['value'])
        self.assertEqual(r['cgroups']['origin'],'unavailable')
        self.assertTrue(any('Cgroup evidence unavailable:' in v for v in r['limitations']))
        self.assert_not_scientific(r)

    def test_f4_validate_cli_and_filesystem_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=copy.deepcopy(self.p);p['build']['executable']='bin/'+chr(0xd800)
            path=Path(tmp)/'plan.json';path.write_bytes(canonical_json(p))
            result=subprocess.run([sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),
                                   'validate','--plan',str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2);self.assertIn('encoding',result.stderr)
            self.assertNotIn('Traceback',result.stderr)
            for name in ('caf\u00e9','cafe\u0301','\u56fe'):
                target=Path(tmp)/name;target.write_text('legitimate Unicode',encoding='utf-8')
                self.assertEqual(os.fsdecode(os.fsencode(str(target))),str(target))

    def test_r2_plain_text_mapping_is_not_runtime(self):
        import mmap
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'libgomp.so.1';path.write_bytes(b'not an ELF runtime\n'+b'X'*8192)
            with path.open('rb') as stream, mmap.mmap(stream.fileno(),4096,
                    flags=mmap.MAP_PRIVATE,prot=mmap.PROT_READ):
                self.assertIsNone(mapped_runtime(os.getpid(),sys.executable))

    def test_r2_genuine_runtime_data_mapping_is_not_linkage(self):
        import mmap
        path=Path(subprocess.check_output(['g++','-print-file-name=libgomp.so.1'],text=True).strip()).resolve()
        with path.open('rb') as stream, mmap.mmap(stream.fileno(),4096,
                flags=mmap.MAP_PRIVATE,prot=mmap.PROT_READ):
            self.assertIsNone(mapped_runtime(os.getpid(),sys.executable))

    def test_r2_unaligned_mappings_rejected_api_cli(self):
        for start,offset in [('7f000001-7f002001','00000000'),('7f000000-7f002000','00000001')]:
            r=hardware();r['openmp']['value']['mappings'][0]=(
                start+' r-xp '+offset+' 08:01 7 /usr/lib/libgomp.so.1.0.0')
            with self.subTest(start=start,offset=offset):self.assert_not_scientific(r,cli=True)

    def test_r2_out_of_bounds_mapping_rejected_api_cli(self):
        for offset in ('00010000','ffffffffffffffff'):
            r=hardware();r['openmp']['value']['mappings'][0]=(
                '7f000000-7f002000 r-xp '+offset+' 08:01 7 /usr/lib/libgomp.so.1.0.0')
            with self.subTest(offset=offset):self.assert_not_scientific(r,cli=True)

    def test_r2_elf_header_adversaries_api_cli(self):
        changes=[('magic',0,'<I',0),('class',4,'<B',1),('encoding',5,'<B',2),
                 ('architecture',18,'<H',183),('type',16,'<H',1),('version',20,'<I',2),
                 ('header-size',52,'<H',63),('ph-size',54,'<H',55),('ph-count',56,'<H',129),
                 ('ph-bounds',32,'<Q',0x3800),('section-bounds',40,'<Q',0x3800)]
        for name,offset,fmt,value in changes:
            r=hardware();patch_hex(r['openmp']['value']['elf'],'header',offset,fmt,value)
            with self.subTest(name=name):self.assert_not_scientific(r,cli=True)

    def test_r2_elf_segments_and_dynamic_adversaries_api_cli(self):
        changes=[('no-exec','program_headers',4,'<I',4),
                 ('file-range','program_headers',56+8,'<Q',0xfffffffffffff000),
                 ('virtual-overflow','program_headers',56+16,'<Q',0xfffffffffffff000),
                 ('filesz-memsz','program_headers',56+32,'<Q',0x3000),
                 ('segment-align','program_headers',56+48,'<Q',24),
                 ('no-soname','dynamic',32,'<q',1),('bad-soname-offset','dynamic',40,'<Q',9999),
                 ('no-null','dynamic',48,'<q',1),('bad-strtab','dynamic',8,'<Q',0x9000),
                 ('no-strsize','dynamic',16,'<q',1)]
        for name,key,offset,fmt,value in changes:
            r=hardware();patch_hex(r['openmp']['value']['elf'],key,offset,fmt,value)
            with self.subTest(name=name):self.assert_not_scientific(r,cli=True)
        for key in ('program_headers','dynamic','strings'):
            r=hardware();r['openmp']['value']['elf'][key]=r['openmp']['value']['elf'][key][:-2]
            with self.subTest(truncated=key):self.assert_not_scientific(r,cli=True)
        r=hardware();r['openmp']['value']['elf']['strings']=b'\0libgomp.so.2\0'.hex()
        self.assert_not_scientific(r,cli=True)

    def test_r2_mapping_permissions_and_completeness_api_cli(self):
        for change in (lambda v:v['mappings'].pop(0),lambda v:v['mappings'].pop(),
                       lambda v:v.update(mappings=[v['mappings'][0].replace('r-xp','r--p')]+v['mappings'][1:]),
                       lambda v:v.update(mappings=[v['mappings'][0].replace('r-xp','rwxp')]+v['mappings'][1:]),
                       lambda v:v.update(mappings=[v['mappings'][0].replace('r-xp','r-xs')]+v['mappings'][1:]),
                       lambda v:v.update(mappings=[v['mappings'][0].replace('7f002000','7f001000')]+v['mappings'][1:]),
                       lambda v:v.update(mappings=[v['mappings'][0]]+[v['mappings'][1].replace('00002000','00001000')]+v['mappings'][2:]),
                       lambda v:v.update(mappings=[v['mappings'][0].replace('7f002000','fffffffffffff000')]+v['mappings'][1:])):
            r=hardware();change(r['openmp']['value']);self.assert_not_scientific(r,cli=True)
        with self.assertRaisesRegex(ValueError,'overflow'):add((1<<64)-1,1)

    def test_r2_version_page_and_linkage_api_cli(self):
        for key in ('evidence_version','page_size','elf','executable_elf'):
            r=hardware();r['openmp']['value'].pop(key);self.assert_not_scientific(r,cli=True)
        for key,value in [('evidence_version',2),('evidence_version',True),('page_size',8192),('page_size',True)]:
            r=hardware();r['openmp']['value'][key]=value;self.assert_not_scientific(r,cli=True)
        r=hardware();patch_hex(r['openmp']['value']['executable_elf'],'dynamic',32,'<q',14)
        self.assert_not_scientific(r,cli=True)
        r=hardware();r['openmp']['value']['executable_elf']['interpreter']=b'/lib64/xx-linux-x86-64.so.2\0'.hex()
        self.assert_not_scientific(r,cli=True)
        r=hardware();r['openmp']['value']['elf']['unknown']=1;self.assert_not_scientific(r,cli=True)

    def test_r2_padding_relocation_and_alternate_layout(self):
        import io
        self.assertEqual(collect_elf(io.BytesIO(elf_bytes())),elf_evidence())
        # Final file page is padded; writable segment's vaddr differs from offset.
        r=hardware();validate_runtime(r['openmp']['value'])
        # Split executable VMA and remove RELRO splitting: both are valid layouts.
        v=r['openmp']['value'];first=v['mappings'][0]
        v['mappings']=[first.replace('7f002000','7f001000'),
            first.replace('7f000000-7f002000','7f001000-7f002000').replace('00000000','00001000')]+v['mappings'][1:]
        validate_runtime(v);self.assertEqual(self.admission_cli(r).returncode,0)
        v['mappings']=v['mappings'][:2]+['7f005000-7f007000 rw-p 00002000 08:01 7 /usr/lib/libgomp.so.1.0.0']
        validate_runtime(v)
        patch_hex(v['executable_elf'],'header',16,'<H',2)
        patch_hex(v['executable_elf'],'header',24,'<Q',0x401000)
        for index,address in enumerate((0x300,0,0x5000,0x400,0x5000)):
            patch_hex(v['executable_elf'],'program_headers',index*56+16,'<Q',0x400000+address)
        patch_hex(v['executable_elf'],'dynamic',8,'<Q',0x400800)
        validate_runtime(v)

    def test_r2_relro_and_metadata_consistency(self):
        r=hardware();patch_hex(r['openmp']['value']['elf'],'program_headers',3*56+16,'<Q',0x1000)
        self.assert_not_scientific(r,cli=True)
        r=hardware();r['openmp']['value']['file_identity']['size']+=1
        self.assert_not_scientific(r,cli=True)
        r=hardware();patch_hex(r['openmp']['value']['executable_elf'],'header',24,'<Q',0)
        self.assert_not_scientific(r,cli=True)
        # An RX load cannot silently become writable, and a non-RELRO data page
        # cannot silently lose write permission under this explicitly narrow scope.
        r=hardware();r['openmp']['value']['mappings'][2]=r['openmp']['value']['mappings'][2].replace('rw-p','r--p')
        self.assert_not_scientific(r,cli=True)

    def test_r2_collected_bytes_and_bounds(self):
        import io
        from campaign_hardware import elf_file
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'libgomp.so.1';path.write_bytes(elf_bytes())
            evidence,digest,info=elf_file(path)
            self.assertEqual(evidence,elf_evidence())
            self.assertEqual(digest,hashlib.sha256(elf_bytes()).hexdigest())
            self.assertEqual(info.st_size,len(elf_bytes()))
        evidence=elf_evidence();evidence['strings']='00'*(65536+1)
        with self.assertRaises(ValueError):parse_elf(evidence)
        raw=bytearray(elf_bytes());raw[18:20]=b'\xb7\0'
        with self.assertRaises(ValueError):collect_elf(io.BytesIO(raw))

    def test_r2_collect_invalid_elf_bytes(self):
        import io
        for raw in (b'not ELF'*100,elf_bytes()[:100],b'\0'*0x3800):
            with self.subTest(prefix=raw[:8]),self.assertRaises(ValueError):collect_elf(io.BytesIO(raw))

    def test_r2_real_direct_linked_runtime(self):
        import select
        from campaign_hardware import read_text
        # Compile and run only this trusted idle test helper, never a candidate or benchmark.
        source='#include <omp.h>\n#include <unistd.h>\nint main(){if(omp_get_max_threads()<1)return 1; if(write(1,"ready\\n",6)!=6)return 2; char c; return read(0,&c,1)==1?0:3;}\n'
        with tempfile.TemporaryDirectory() as tmp:
            cpp=Path(tmp)/'idle.cpp';exe=Path(tmp)/'idle';cpp.write_text(source)
            subprocess.run(['g++','-fopenmp',str(cpp),'-o',str(exe)],check=True,capture_output=True,timeout=30)
            with subprocess.Popen([str(exe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as child:
                try:
                    self.assertTrue(select.select([child.stdout],[],[],5)[0])
                    self.assertEqual(child.stdout.readline(),b'ready\n')
                    value=mapped_runtime(child.pid,exe)
                    self.assertIsNotNone(value);validate_runtime(value)
                    r=hardware();r['openmp']['value']=value
                    p=copy.deepcopy(self.p)
                    p['build'].update(executable_sha256=value['executable_sha256'],openmp_sha256=value['sha256'])
                    r['executable_sha256']['value']=value['executable_sha256']
                    self.assertTrue(admit(p,r)['scientific_performance_allowed'])
                    self.assertEqual(self.admission_cli(r,p).returncode,0)
                    # Public inspector produces the same valid runtime form.
                    cli=subprocess.run([sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),
                        'inspect','--executable',str(exe),'--pid',str(child.pid)],capture_output=True,text=True,timeout=10)
                    self.assertEqual(cli.returncode,0,cli.stderr)
                    validate_runtime(json.loads(cli.stdout)['openmp']['value'])
                    maps=read_text(f'/proc/{child.pid}/maps')
                    extra='10000000-10001000 r-xp 00000000 08:01 99 /other/libgomp.so.1'
                    def multiple(path):return maps+'\n'+extra if path.endswith('/maps') else read_text(path)
                    self.assertIsNone(mapped_runtime(child.pid,exe,multiple))
                    def deleted(path):return maps+'\n'+extra+' (deleted)' if path.endswith('/maps') else read_text(path)
                    self.assertIsNone(mapped_runtime(child.pid,exe,deleted))
                    incomplete='\n'.join(line for line in maps.splitlines() if not ('libgomp' in line and 'r-xp' in line))
                    def missing(path):return incomplete if path.endswith('/maps') else read_text(path)
                    self.assertIsNone(mapped_runtime(child.pid,exe,missing))
                finally:
                    child.communicate(b'x',timeout=5)

    def assert_r3_rejected(self, report, plan=None, reason=None):
        p=self.p if plan is None else plan
        result=admit(p,report);cli=self.admission_cli(report,p)
        self.assertFalse(result['scientific_performance_allowed'],f'API allowed; CLI exit={cli.returncode}')
        self.assertEqual(cli.returncode,1,cli.stderr)
        self.assertNotIn('Traceback',cli.stderr)
        if reason is not None:
            with self.assertRaisesRegex(ValueError,reason):validate_runtime(report['openmp']['value'])

    def test_r3_n3_synthetic_alignment_api_cli(self):
        r=hardware();harden_case(r['openmp']['value']['elf'],'alignment')
        self.assert_r3_rejected(r,reason='unsupported ELF PT_LOAD alignment')

    def test_r3_n4_synthetic_zero_fill_api_cli(self):
        r=hardware();harden_case(r['openmp']['value']['elf'],'zero-fill')
        self.assert_r3_rejected(r,reason='overlapping ELF load memory pages')

    def test_r3_actual_modified_genuine_elf_api_cli(self):
        import select
        from campaign_hardware import elf_file
        source='#include <omp.h>\n#include <unistd.h>\nint main(){if(omp_get_max_threads()<1)return 1;char c=1;if(write(1,&c,1)!=1)return 2;return read(0,&c,1)==1?0:3;}\n'
        with tempfile.TemporaryDirectory() as tmp:
            cpp=Path(tmp)/'idle.cpp';exe=Path(tmp)/'idle';cpp.write_text(source)
            subprocess.run(['g++','-fopenmp',str(cpp),'-o',str(exe)],check=True,capture_output=True,timeout=30)
            with subprocess.Popen([str(exe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as child:
                try:
                    self.assertTrue(select.select([child.stdout],[],[],5)[0]);self.assertEqual(child.stdout.read(1),b'\1')
                    value=mapped_runtime(child.pid,exe);self.assertIsNotNone(value)
                    # The genuine baseline must qualify before either mutation.
                    p=copy.deepcopy(self.p);p['build'].update(executable_sha256=value['executable_sha256'],openmp_sha256=value['sha256'])
                    r=hardware();r['openmp']['value']=value;r['executable_sha256']['value']=value['executable_sha256']
                    self.assertTrue(admit(p,r)['scientific_performance_allowed'])
                    self.assertEqual(self.admission_cli(r,p).returncode,0)
                    for case in ('alignment','zero-fill'):
                        with self.subTest(case=case):
                            folder=Path(tmp)/case;folder.mkdir()
                            mutated,path=modified_runtime_file(value,case,folder)
                            pp=copy.deepcopy(p);pp['build']['openmp_sha256']=mutated['sha256']
                            rr=copy.deepcopy(r);rr['openmp']['value']=mutated
                            self.assertEqual(mutated['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
                            self.assertEqual(mutated['file_identity']['inode'],path.stat().st_ino)
                            reason='unsupported ELF PT_LOAD alignment' if case=='alignment' else 'overlapping ELF load memory pages'
                            self.assert_r3_rejected(rr,pp,reason)
                            with self.assertRaisesRegex(ValueError,reason):elf_file(path)
                finally:child.communicate(b'x',timeout=5)

    def test_r3_supported_alignment_values(self):
        for align in (0,1,2,8,2048,4096):
            with self.subTest(align=align):
                r=hardware()
                for index in (0,1):patch_hex(r['openmp']['value']['elf'],'program_headers',index*56+48,'<Q',align)
                validate_runtime(r['openmp']['value'])
                self.assertTrue(admit(self.p,r)['scientific_performance_allowed'])
                self.assertEqual(self.admission_cli(r).returncode,0)

    def test_r3_unsupported_and_invalid_alignment(self):
        for align in (3,24,4095,8192,1<<63):
            r=hardware();patch_hex(r['openmp']['value']['elf'],'program_headers',48,'<Q',align)
            with self.subTest(align=align):self.assert_r3_rejected(r)
        r=hardware();harden_case(r['openmp']['value']['elf'],'alignment')
        # Larger alignment remains deliberately unsupported even at a 2 MiB bias.
        r['openmp']['value']['mappings']=[line.replace('7f00','8000') for line in r['openmp']['value']['mappings']]
        self.assert_r3_rejected(r,reason='unsupported ELF PT_LOAD alignment')
        r=hardware();patch_hex(r['openmp']['value']['elf'],'program_headers',56+8,'<Q',0x1001)
        self.assert_r3_rejected(r,reason='invalid or unsupported ELF PT_LOAD')

    def test_r3_zero_fill_writable_and_padding_overlap(self):
        for address,offset in ((0x6000,0),(0x7800,0x800)):
            r=hardware();add_load(r['openmp']['value']['elf'],address,0x1000,offset=offset)
            with self.subTest(address=address):self.assert_r3_rejected(r,reason='overlapping ELF load memory pages')

    def test_r3_nonoverlapping_anonymous_and_empty_loads(self):
        for address,size in ((0x8000,0x1000),(0x1000,0)):
            r=hardware();add_load(r['openmp']['value']['elf'],address,size)
            # No file-backed VMA is added for anonymous or empty loads.
            validate_runtime(r['openmp']['value'])
            self.assertTrue(admit(self.p,r)['scientific_performance_allowed'])
            self.assertEqual(self.admission_cli(r).returncode,0)
        # The unchanged ordinary RW PT_LOAD includes a BSS tail and final-page padding.
        value=runtime_fixture();loads=[s for s in parse_elf(value['elf'])['segments'] if s['kind']==1]
        self.assertGreater(loads[1]['memsz'],loads[1]['filesz']);validate_runtime(value)

    def test_r3_file_load_overlap_and_adjacency(self):
        r=hardware();add_load(r['openmp']['value']['elf'],0x1000,0x1000,filesz=0x1000,offset=0x1000,flags=4)
        self.assert_r3_rejected(r,reason='overlapping ELF load memory pages')
        r=hardware();add_load(r['openmp']['value']['elf'],0x2000,0x1000,filesz=0x1000,flags=4)
        r['openmp']['value']['mappings'].insert(1,'7f002000-7f003000 r--p 00000000 08:01 7 /usr/lib/libgomp.so.1.0.0')
        validate_runtime(r['openmp']['value'])
        self.assertTrue(admit(self.p,r)['scientific_performance_allowed'])
        self.assertEqual(self.admission_cli(r).returncode,0)

    def test_r3_memory_endpoint_and_page_rounding_overflow(self):
        for address,size in ((0x8000,(1<<64)-1),((1<<64)-4096,4096),((1<<64)-4096,4095)):
            r=hardware();add_load(r['openmp']['value']['elf'],address,size)
            with self.subTest(address=address,size=size):self.assert_r3_rejected(r,reason='overflow')

    def test_r3_anonymous_relocation_overflow(self):
        r=hardware();add_load(r['openmp']['value']['elf'],(1<<64)-8192,4096)
        parse_elf(r['openmp']['value']['elf']) # Unrelocated endpoints fit uint64.
        self.assert_r3_rejected(r,reason='overflow')

    def test_cli_validate_and_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'plan.json';path.write_bytes(canonical_json(self.p))
            cmd=[sys.executable,'-B',str(ROOT/'benchmarks/python/campaign.py'),'validate','--plan',str(path)]
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            path.write_text('{"schema_version":99}')
            result=subprocess.run(cmd,capture_output=True)
            self.assertEqual(result.returncode,2);self.assertNotIn(b'Traceback',result.stderr)


if __name__=='__main__': unittest.main(verbosity=2)
