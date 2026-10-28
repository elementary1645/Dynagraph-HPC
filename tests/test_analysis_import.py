"""Complete synthetic evidence import; no benchmark execution."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from analysis_test_support import fixture,plan_for
from analysis_import import validate_plan,import_input,trial_rows,inventory,classify,ImportRejected
from analyze import analyze,AnalysisFailure
from experiment_records import loads,validate_dataset
from workloads import canonical_json,sha256

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.evidence=fixture(self.root/'evidence')
        self.plan=validate_plan(plan_for([self.evidence]))

    def load(self,item=None,seen=None):
        return import_input(item or self.plan['inputs'][0],self.plan,self.root,seen if seen is not None else set())

    def test_complete_readonly_and_verified_feature_join(self):
        before=inventory(self.evidence)
        with patch('subprocess.Popen',side_effect=AssertionError('must not execute evidence')):
            dataset=self.load()
            self.assertEqual(dataset['evidence_class'],'valid_harness_only')
            self.assertEqual(len(trial_rows(dataset)),16)
        self.assertEqual(inventory(self.evidence),before)
        latency=fixture(self.root/'latency',mode='per-update')
        plan=validate_plan(plan_for([latency]));dataset=import_input(plan['inputs'][0],plan,self.root,set())
        rows=trial_rows(dataset)
        self.assertEqual(rows[0]['request_kind'],'strict_decrease')
        self.assertTrue(rows[1]['consecutive_repeated_endpoints'])
        self.assertEqual(rows[2]['request_kind'],'equal')
        self.assertEqual(rows[2]['decrease_magnitude'],'0')
        self.assertIsNone(rows[0]['actual_selected_backend']);self.assertIsNone(rows[0]['actual_workers'])

    def test_reject_missing_duplicate_incomplete_and_identity(self):
        path=self.evidence/'records.jsonl';original=path.read_bytes()
        lines=original.splitlines(keepends=True)
        for invalid in (original[:-1],b''.join(lines[:-1]),b''.join(lines[:8]+[lines[8]]+lines[8:]),original.replace(b'"success":true',b'"success":false',1)):
            path.write_bytes(invalid)
            with self.assertRaises((ValueError,IndexError,KeyError)):self.load()
        path.write_bytes(original)
        item=copy.deepcopy(self.plan['inputs'][0]);item['expected_identities']['executable_sha256']='0'*64
        with self.assertRaisesRegex(ImportRejected,'executable_sha256'):self.load(item)
        seen=set();self.load(seen=seen)
        clone=self.root/'clone';shutil.copytree(self.evidence,clone)
        item=copy.deepcopy(self.plan['inputs'][0]);item['path']=str(clone)
        with self.assertRaisesRegex(ImportRejected,'copied evidence'):self.load(item,seen)

    def test_strict_plan_modes_workloads_hardware_and_eligibility(self):
        for mutation in ('version','unknown','zero_weight','unsupported_comparison','numeric','mode'):
            plan=copy.deepcopy(self.plan)
            if mutation=='version':plan['schema_version']=2
            elif mutation=='unknown':plan['extra']=True
            elif mutation=='zero_weight':plan['workloads'][0]['weight']['numerator']='0'
            elif mutation=='unsupported_comparison':plan['comparisons'][0]['family']='inference'
            elif mutation=='numeric':plan['compatible_configurations'][0]['threads']=2
            else:plan['compatible_configurations'][0]['timing_mode']='other'
            with self.assertRaises(ValueError):validate_plan(plan)
        dataset=self.load();env=[r for r in dataset['records'] if r['record_type']=='environment' and r['trial_id'] is not None]
        item=dict(self.plan['inputs'][0],synthetic=False,evidence_intent='performance')
        self.assertEqual(classify(item,env,{})[0],'valid_performance_unconfirmed')
        evidence={'controlled_hardware_evidence':{},'instrumentation_evidence':{}}
        self.assertEqual(classify(item,env,evidence)[0],'performance_eligible')
        env=copy.deepcopy(env);env[0]['metadata']['flags']['value']='-O3 --coverage'
        self.assertEqual(classify(item,env,evidence)[0],'valid_harness_only')
        item=copy.deepcopy(self.plan['inputs'][0]);self.plan['compatible_configurations'][0]['timing_mode']='per-update'
        with self.assertRaisesRegex(ImportRejected,'configuration'):self.load(item)

    def test_pipeline_rejections_and_no_overwrite(self):
        path=self.root/'plan.json';plan=copy.deepcopy(self.plan);plan['figures']=[];path.write_bytes(canonical_json(plan))
        before=inventory(self.evidence)
        self.assertEqual(analyze(path,self.root/'output')['status'],'complete')
        self.assertEqual(inventory(self.evidence),before)
        with self.assertRaises(FileExistsError):analyze(path,self.root/'output')
        with self.assertRaisesRegex(AnalysisFailure,'raw evidence'):analyze(path,self.evidence/'analysis')
        (self.evidence/'trial-0.exit.json').write_bytes(b'{}')
        with self.assertRaises(AnalysisFailure):analyze(path,self.root/'invalid-output')
        acceptance=loads((self.root/'invalid-output/acceptance.jsonl').read_bytes().splitlines()[0])
        self.assertFalse(acceptance['accepted']);self.assertFalse(acceptance['structurally_valid'])
        self.assertEqual(loads((self.root/'invalid-output/analysis-manifest.json').read_bytes())['status'],'failed')

    def test_mixed_compatible_strata_and_declared_sessions(self):
        second=fixture(self.root/'second',run_id='2')
        latency=fixture(self.root/'latency',mode='per-update',run_id='3')
        other=fixture(self.root/'other-workload',seed='9',run_id='4')
        plan=plan_for([self.evidence,second,latency,other]);plan['figures']=[]
        plan['inputs'][1]['hardware_id']='other-hardware'
        plan['inputs'][1]['session_id']='session-1'
        path=self.root/'plan.json';path.write_bytes(canonical_json(plan))
        analyze(path,self.root/'mixed-output')
        summary=loads((self.root/'mixed-output/summaries.json').read_bytes())
        self.assertEqual(summary['declared_session_count'],'2')
        self.assertEqual(summary['declared_independent_session_count'],'0')
        self.assertEqual(len({r['stratum'] for r in summary['run_ratios']}),2)
        self.assertTrue(all(s['confidence_interval'] is None for s in summary['fixed_workload_panels']))

    def test_detect_input_change_after_validation(self):
        real_inventory=inventory;calls=0
        def changing(path):
            nonlocal calls
            result=real_inventory(path);calls+=1
            if calls==2:
                result=dict(result);result['records.jsonl']='0'*64
            return result
        with patch('analysis_import.inventory',changing):
            with self.assertRaisesRegex(ImportRejected,'changed'):self.load()

    def test_reused_run_id_and_symlink_directory_rejected(self):
        seen=set();self.load(seen=seen)
        second=fixture(self.root/'second',seed='9')
        plan=validate_plan(plan_for([second]))
        with self.assertRaisesRegex(ImportRejected,'replication'):
            import_input(plan['inputs'][0],plan,self.root,seen)
        link=self.root/'link';link.symlink_to(self.evidence,target_is_directory=True)
        item=dict(self.plan['inputs'][0],path=str(link))
        with self.assertRaisesRegex(ImportRejected,'symlink'):self.load(item)

    def test_public_complete_validator_and_explicit_exclusions(self):
        with patch('analysis_import.validate_dataset',side_effect=ValueError('strict acceptance')) as validator:
            with self.assertRaisesRegex(ValueError,'strict acceptance'):self.load()
            validator.assert_called_once_with(self.evidence/'records.jsonl')
        plan=copy.deepcopy(self.plan);plan['figures']=[]
        plan['allowed_evidence_classes']=['performance_eligible']
        path=self.root/'plan.json';path.write_bytes(canonical_json(plan))
        with self.assertRaises(AnalysisFailure):analyze(path,self.root/'disallowed')
        plan['exclusions']=[dict(input_id='input-0',reason='prespecified harness exclusion')]
        path.write_bytes(canonical_json(plan))
        self.assertEqual(analyze(path,self.root/'excluded')['accepted_inputs'],'0')

    def test_complete_dataset_evidence_tampering(self):
        for name in ('runner','workload/graph.txt','workload/trace.txt','workload/manifest.json',
                     'artifact-verification.json','preflight-dijkstra.stdout','trial-0.stdout','trial-0.stderr'):
            with self.subTest(name=name):
                path=self.evidence/name;saved=path.read_bytes()
                try:
                    path.write_bytes(saved+b'x')
                    with self.assertRaises((ValueError,IndexError,KeyError)):self.load()
                finally:path.write_bytes(saved)

if __name__=='__main__':unittest.main()
