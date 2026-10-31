"""Resource contracts: deterministic synthetic facts, no resource manipulation."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'benchmarks/python'))
from campaign_resources import controls, assess, bundle, verify_bundle, resource_context, fact
from campaign_provenance import reconcile_cgroups, cpu_list
from workloads import canonical_json, sha256
from test_campaign import hardware


def fixture():
    h=hardware();tid='b'*64
    obs={k:fact(None,'independent fixture unavailable','not established','record') for k in
         ('affinity','online_cpus','cgroups','topology','numa','openmp_team','exclusivity','uncontended','isolation')}
    for k,v in dict(affinity=[0,2],online_cpus=[0,1,2,3],cgroups=h['cgroups']['value']).items():
        obs[k]=fact(v,'synthetic child fixture','child leader / visible namespace','runtime',
                    '2026-01-01T00:00:01+00:00','2026-01-01T00:00:02+00:00')
    for k in ('topology','numa'):obs[k]=fact(h[k]['value'],'synthetic hardware','earlier observer context','hardware')
    paths=dict(plan='plan.json',manifest='trial-manifest.json',execution='execution-manifest.json',
               hardware='hardware.json',record=tid+'/record.json',runtime=tid+'/0-verify.runtime.json')
    return dict(binding=dict(execution_id='a'*64,trial_id=tid,journal_binding_sha256='c'*64,
                    process_index=0,executable_sha256='d'*64,pid=123,process_start_ticks=100000),
                references={k:dict(path=v,sha256='e'*64) for k,v in paths.items()},
                request=dict(affinity=[0,2],workers=2,openmp=dict(OMP_NUM_THREADS='2',OMP_DYNAMIC='FALSE',OMP_THREAD_LIMIT='2'),
                             min_physical_cores=2,allow_smt=False),observations=obs,
                process_interval=dict(start='2026-01-01T00:00:00+00:00',end='2026-01-01T00:00:03+00:00'),
                trial_success=True)


def application(value, state='applied'):
    cpus=value['request']['affinity'] if state=='applied' else None
    value['application']=dict(state=state,cpus=cpus,receipt=dict(
        schema='dynagraph-affinity-application',schema_version=1,binding=copy.deepcopy(value['binding']),
        requested_cpus=value['request']['affinity'],applied_cpus=cpus,
        outcome='success' if state=='applied' else 'failure',errno=0 if state=='applied' else 1,
        mechanism='sched_setaffinity',timestamp='2026-01-01T00:00:00+00:00',
        source='supplied application receipt',scope='child leader only'))


class ContractTests(unittest.TestCase):
    def setUp(self):self.context=fixture()
    def decision(self,context=None,**requirements):
        context=context or self.context;value=controls(context);value['requirements'].update(requirements)
        return assess(value,context)

    def test_development_only_and_no_execution_authority(self):
        value=bundle(self.context);d=verify_bundle(value,self.context)
        self.assertEqual(d['state'],'development_only')
        self.assertFalse(d['measurement_eligible']);self.assertFalse(d['execution_authorized'])
        self.assertFalse(d['scientific_performance_allowed'])
        self.assertEqual(value['controls']['application'],dict(state='not_attempted',cpus=None,receipt=None))

    def test_scientific_is_indeterminate_never_eligible(self):
        value=bundle(self.context,'scientific');self.assertEqual(value['decision']['state'],'indeterminate')
        codes={r['code'] for r in value['decision']['reasons']}
        self.assertTrue({'EXCLUSIVITY_UNAVAILABLE','OPENMP_TEAM_UNAVAILABLE','ISOLATION_UNAVAILABLE'}<=codes)
        application(value['controls']);d=assess(value['controls'],self.context)
        self.assertEqual(d['state'],'indeterminate');self.assertFalse(d['measurement_eligible'])

    def test_requested_is_not_applied_or_observed(self):
        self.assertEqual(self.decision(applied_affinity=True)['state'],'indeterminate')
        c=copy.deepcopy(self.context);c['observations']['affinity']['value']=None;c['observations']['affinity']['status']='unavailable'
        self.assertEqual(self.decision(c,observed_affinity=True)['state'],'indeterminate')

    def test_requested_observed_mismatch_is_known_failure(self):
        c=copy.deepcopy(self.context);c['observations']['affinity']['value']=[0,1]
        d=self.decision(c,observed_affinity=True);self.assertEqual(d['state'],'rejected')
        self.assertIn('AFFINITY_MATCH_FAILED',{r['code'] for r in d['reasons']})

    def test_cpu_sets_ranges_and_encoding(self):
        self.assertEqual(cpu_list('0-2,5,9-10'),[0,1,2,5,9,10])
        for bad in ('','-1','2-1','0-4096','1048576','1,,2'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):cpu_list(bad)
        for bad in ([],[True],[-1],[1,1],[2,0],[1048576]):
            for key in ('request','observations'):
                c=copy.deepcopy(self.context)
                if key=='request':c['request']['affinity']=bad
                else:c['observations']['affinity']['value']=bad
                with self.subTest(bad=bad,key=key),self.assertRaises(ValueError):assess(controls(c),c)

    def test_insufficient_quota_and_max(self):
        c=copy.deepcopy(self.context);g=c['observations']['cgroups']['value']
        g['views'][0]['ancestors'][0]['cpu.max']='100000 100000';g.update(reconcile_cgroups(g))
        self.assertEqual(self.decision(c,quota=True)['state'],'rejected')
        for row in g['views'][0]['ancestors']:row['cpu.max']='max 100000'
        g.update(reconcile_cgroups(g));self.assertEqual(self.decision(c,quota=True)['state'],'development_only')

    def test_invalid_quotas_and_contradictory_summary(self):
        for bad in ('0 100','max 0','-1 100','1  100','max 100 extra'):
            c=copy.deepcopy(self.context);c['observations']['cgroups']['value']['views'][0]['ancestors'][0]['cpu.max']=bad
            with self.subTest(bad=bad),self.assertRaises(ValueError):self.decision(c,quota=True)
        c=copy.deepcopy(self.context);c['observations']['cgroups']['value']['quota_pairs']=[]
        with self.assertRaises(ValueError):self.decision(c)

    def test_cpuset_restriction_and_online_cpus(self):
        c=copy.deepcopy(self.context);g=c['observations']['cgroups']['value']
        g['views'][0]['ancestors'][0]['cpuset.cpus.effective']='0-1';g.update(reconcile_cgroups(g))
        self.assertEqual(self.decision(c,cpuset=True)['state'],'rejected')
        c=copy.deepcopy(self.context);c['observations']['online_cpus']['value']=[0,1]
        self.assertEqual(self.decision(c,online_cpus=True)['state'],'rejected')

    def test_missing_required_topology_is_indeterminate(self):
        c=copy.deepcopy(self.context);c['observations']['topology'].update(value=None,status='unavailable')
        self.assertEqual(self.decision(c,topology=True)['state'],'indeterminate')

    def test_smt_core_count_and_ambiguity(self):
        c=copy.deepcopy(self.context);c['request']['affinity']=[0,1]
        self.assertEqual(self.decision(c,topology=True)['state'],'rejected')
        for change in (lambda rows:rows.append(copy.deepcopy(rows[0])),
                       lambda rows:rows[1].update(siblings=[1]),
                       lambda rows:rows[1].update(core=2)):
            c=copy.deepcopy(self.context);change(c['observations']['topology']['value'])
            with self.assertRaises(ValueError):self.decision(c)

    def test_numa_missing_and_cross_node(self):
        c=copy.deepcopy(self.context);c['observations']['numa'].update(value=None,status='unavailable')
        self.assertEqual(self.decision(c,numa=True)['state'],'indeterminate')
        self.assertEqual(self.decision(c,topology=True)['state'],'development_only')
        c=copy.deepcopy(self.context);c['observations']['numa']['value']=[dict(node=0,cpus=[0,1]),dict(node=1,cpus=[2,3])]
        self.assertEqual(self.decision(c,numa=True)['state'],'rejected')

    def test_missing_required_cgroups_is_unknown_not_unlimited(self):
        c=copy.deepcopy(self.context);c['observations']['cgroups'].update(value=None,status='unavailable')
        self.assertEqual(self.decision(c,quota=True,cpuset=True)['state'],'indeterminate')

    def test_known_failure_precedes_missing_evidence(self):
        c=copy.deepcopy(self.context);c['observations']['affinity']['value']=[0,1]
        self.assertEqual(self.decision(c,observed_affinity=True,exclusivity=True)['state'],'rejected')

    def test_applied_and_failed_receipts(self):
        value=controls(self.context);value['requirements']['applied_affinity']=True
        application(value);self.assertEqual(assess(value,self.context)['state'],'development_only')
        application(value,'failed');self.assertEqual(assess(value,self.context)['state'],'rejected')

    def test_contradictory_application_receipts(self):
        for change in (lambda a:a.update(cpus=[0]),lambda a:a['receipt'].update(errno=1),
                       lambda a:a['receipt']['binding'].update(pid=124),
                       lambda a:a['receipt'].update(applied_cpus=[0]),
                       lambda a:a['receipt'].update(timestamp='2026-01-01T00:00:04+00:00'),
                       lambda a:a['receipt'].update(mechanism='taskset'),
                       lambda a:a['receipt'].update(schema_version=True)):
            value=controls(self.context);application(value);change(value['application'])
            with self.assertRaises(ValueError):assess(value,self.context)
        value=controls(self.context);value['application']['cpus']=[0,2]
        with self.assertRaises(ValueError):assess(value,self.context)

    def test_no_fabricated_team_exclusivity_or_isolation(self):
        for key in ('openmp_team','exclusivity','uncontended','isolation'):
            for claim in (True,False,2):
                c=copy.deepcopy(self.context);c['observations'][key].update(value=claim,status='observed')
                with self.subTest(key=key,claim=claim),self.assertRaises(ValueError):self.decision(c)

    def test_unsupported_versions_missing_and_extra_fields(self):
        for version in (True,0,2):
            value=bundle(self.context);value['controls']['schema_version']=version
            with self.assertRaises(ValueError):verify_bundle(value,self.context)
        for key in ('requirements','observations','references'):
            value=bundle(self.context);del value['controls'][key]
            with self.assertRaises(ValueError):verify_bundle(value,self.context)
        value=bundle(self.context);value['controls']['guaranteed']=True
        with self.assertRaises(ValueError):verify_bundle(value,self.context)

    def test_incorrect_binding_and_rehashed_observation(self):
        for key in ('trial_id','execution_id','executable_sha256','journal_binding_sha256'):
            value=bundle(self.context);value['controls']['binding'][key]='f'*64
            with self.assertRaises(ValueError):verify_bundle(value,self.context)
        value=bundle(self.context);value['controls']['observations']['affinity']['value']=[0]
        value['decision']['controls_sha256']=sha256(canonical_json(value['controls']))
        value['decision'].pop('assessment_id');value['decision']['assessment_id']=sha256(canonical_json(value['decision']))
        with self.assertRaisesRegex(ValueError,'context mismatch'):verify_bundle(value,self.context)

    def test_eligible_and_other_invalid_decisions(self):
        for key,claim in (('state','eligible'),('state','indeterminate'),('measurement_eligible',True),
                          ('scientific_performance_allowed',True),('execution_authorized',True),('schema_version',2)):
            value=bundle(self.context);value['decision'][key]=claim
            with self.subTest(key=key),self.assertRaises(ValueError):verify_bundle(value,self.context)
        value=bundle(self.context,'scientific');value['controls']['requirements']['exclusivity']=False
        with self.assertRaises(ValueError):verify_bundle(value,self.context)

    def test_reason_codes_references_and_immutable_transitions(self):
        previous=bundle(self.context);verify_bundle(previous,self.context,copy.deepcopy(previous))
        changed=copy.deepcopy(previous);changed['controls']['requirements']['applied_affinity']=True
        changed['decision']=assess(changed['controls'],self.context)
        self.assertEqual(changed['decision']['state'],'indeterminate')
        with self.assertRaisesRegex(ValueError,'transition'):verify_bundle(changed,self.context,previous)
        for reason in changed['decision']['reasons']:
            self.assertTrue(reason['evidence'][0]['reference'].startswith('controls#/'))
            self.assertEqual(len(reason['evidence'][0]['sha256']),64)
        changed['decision']['reasons'][0]['code']='INVENTED'
        with self.assertRaises(ValueError):verify_bundle(changed,self.context)

    def test_malformed_optional_facts_and_timestamps(self):
        for change in (lambda c:c['observations']['affinity'].update(status='unavailable'),
                       lambda c:c['observations']['affinity'].update(end='2020-01-01T00:00:00+00:00'),
                       lambda c:c['observations']['affinity'].update(scope=''),
                       lambda c:c['observations']['affinity'].update(reference='unknown'),
                       lambda c:c['references']['plan'].update(path='../outside'),
                       lambda c:c['observations']['numa']['value'].append(dict(node=0,cpus=[0]))):
            c=copy.deepcopy(self.context);change(c)
            with self.assertRaises(ValueError):self.decision(c)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        from test_campaign_resume import ResumeTests
        self.f=ResumeTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.initial()

    def test_read_only_verified_completion_and_cli(self):
        f=self.f;before=f.snapshot();marks=f.marks()
        with patch('subprocess.Popen',side_effect=AssertionError('inspection executed')):
            ctx=resource_context(f.out,f.ids[0]);value=bundle(ctx);verify_bundle(value,ctx)
        self.assertEqual(value['decision']['state'],'development_only')
        evidence=f.base/'resources.json';evidence.write_bytes(canonical_json(value))
        p=f.cli('verify-resources','--output',str(f.out),'--trial-id',f.ids[0],'--evidence',str(evidence))
        self.assertEqual(p.returncode,0,p.stderr);self.assertFalse(json.loads(p.stdout)['measurement_eligible'])
        p=f.cli('inspect-resources','--output',str(f.out),'--trial-id',f.ids[0],'--purpose','scientific')
        self.assertEqual(p.returncode,0,p.stderr);self.assertNotEqual(json.loads(p.stdout)['decision']['state'],'eligible')
        self.assertEqual(f.snapshot(),before);self.assertEqual(f.marks(),marks)

    def test_rehashed_wrong_context_fails_offline(self):
        f=self.f;ctx=resource_context(f.out,f.ids[0]);value=bundle(ctx)
        value['controls']['observations']['online_cpus']['value']=[99]
        value['controls']['observations']['online_cpus']['status']='observed'
        value['decision']['controls_sha256']=sha256(canonical_json(value['controls']))
        value['decision'].pop('assessment_id');value['decision']['assessment_id']=sha256(canonical_json(value['decision']))
        path=f.base/'rehashed.json';path.write_bytes(canonical_json(value))
        result=f.cli('verify-resources','--output',str(f.out),'--trial-id',f.ids[0],'--evidence',str(path))
        self.assertEqual(result.returncode,2)

    def test_pending_wrong_trial_process_and_tampered_runtime(self):
        f=self.f
        for tid,index in ((f.ids[1],0),('f'*64,0),(f.ids[0],1)):
            with self.subTest(tid=tid,index=index),self.assertRaises((ValueError,OSError)):
                resource_context(f.out,tid,index)
        path=f.out/f.ids[0]/'0-verify.runtime.json';path.write_bytes(b'{}')
        with self.assertRaises(ValueError):resource_context(f.out,f.ids[0])

    def test_evidence_changes_during_inspection_reject(self):
        from campaign_journal import inspect_recovery
        f=self.f
        def changed(directory):
            result=inspect_recovery(directory)
            path=directory/f.ids[0]/'record.json';record=json.loads(path.read_bytes())
            record['message']='changed after verification';path.write_bytes(canonical_json(record))
            return result
        with patch('campaign_journal.inspect_recovery',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'changed during inspection'):
                resource_context(f.out,f.ids[0])

    def test_success_record_without_terminal_remains_indeterminate(self):
        f=self.f
        # Fully verified successful output is not a committed completion.
        (f.out/'recovery-journal/00000002.json').unlink()
        before=f.snapshot();marks=f.marks()
        context=resource_context(f.out,f.ids[0])
        self.assertIsNone(context['trial_success'])
        value=bundle(context);verify_bundle(value,context)
        self.assertEqual(value['decision']['state'],'indeterminate')
        self.assertIn('TRIAL_COMPLETION_UNAVAILABLE',{r['code'] for r in value['decision']['reasons']})
        self.assertEqual(f.snapshot(),before);self.assertEqual(f.marks(),marks)

    def test_resume_origin_and_legacy_compatibility(self):
        f=self.f;before=f.snapshot();f.resume();self.assertEqual(before,f.snapshot())
        child=f.attempt/'pilot';tid=f.ids[1];ctx=resource_context(child,tid)
        verify_bundle(bundle(ctx),ctx)
        legacy=f.base/'legacy';shutil.copytree(child,legacy)
        shutil.rmtree(legacy/'recovery-journal');(legacy/'runtime-contract.json').unlink()
        for record_path in legacy.glob('*/record.json'):
            record=json.loads(record_path.read_bytes());record['execution_observations']='legacy observations unavailable'
            for name in list(record['artifacts']):
                if name.endswith('.runtime.json'):
                    (record_path.parent/name).unlink();del record['artifacts'][name]
            record_path.write_bytes(canonical_json(record))
        (legacy/'sha256.json').write_bytes(canonical_json({p.relative_to(legacy).as_posix():sha256(p.read_bytes())
                    for p in legacy.rglob('*') if p.is_file() and p!=legacy/'sha256.json'}))
        from campaign_pilot import verify_pilot
        verify_pilot(legacy);ctx=resource_context(legacy,tid)
        self.assertIsNone(ctx['references']['runtime']);self.assertIsNone(ctx['observations']['affinity']['value'])
        self.assertEqual(bundle(ctx)['decision']['state'],'development_only')

    def test_bounded_and_nonregular_sidecars(self):
        f=self.f;path=f.base/'evidence';os.mkfifo(path)
        result=f.cli('verify-resources','--output',str(f.out),'--trial-id',f.ids[0],'--evidence',str(path))
        self.assertEqual(result.returncode,2)
        path.unlink();path.write_bytes(b'x'*1048577)
        result=f.cli('verify-resources','--output',str(f.out),'--trial-id',f.ids[0],'--evidence',str(path))
        self.assertEqual(result.returncode,2)


if __name__=='__main__':unittest.main(verbosity=2)
