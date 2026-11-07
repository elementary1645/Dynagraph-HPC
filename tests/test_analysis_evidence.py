"""Numerical fixtures and fail-closed diagnostic import; no benchmark execution."""
import copy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'benchmarks/python'))
from analysis_inference import numerical_summary, paired_numerical_summary, unavailable_performance
from analysis_evidence import anchored_inventory, original_rows, reconcile_exports, load_phase_d
from campaign_contract import expand
from workloads import canonical_json


class NumericalEvidenceTests(unittest.TestCase):
    def test_exact_descriptives(self):
        result=numerical_summary([1,2,3,4,5])
        self.assertEqual((result['mean'],result['median'],result['minimum'],result['maximum']),('3/1','3/1','1/1','5/1'))
        self.assertEqual((result['p90'],result['p95']),('5/1','5/1'))
        self.assertAlmostEqual(float(result['sample_standard_deviation']),2.5**0.5)
        result=numerical_summary([Fraction(1,10),Fraction(3,10)])
        self.assertEqual(result['mean'],'1/5')

    def test_empty_one_zero_and_constant(self):
        empty=numerical_summary([]);self.assertEqual(empty['count'],0);self.assertIsNone(empty['mean'])
        for values in ([0],[1],[1,2,3,4],[0]*8,[5]*8):
            result=numerical_summary(values);self.assertIsNone(result['confidence_interval']);self.assertIsNotNone(result['confidence_interval_reason'])
        self.assertIsNone(numerical_summary([1])['sample_standard_deviation'])
        self.assertEqual(numerical_summary([0,2])['mean'],'1/1')

    def test_invalid_numbers_and_bounds(self):
        for value in (None,True,-1,float('nan'),float('inf'),float('-inf'),1.0,'2/1'):
            with self.subTest(value=repr(value)),self.assertRaises(ValueError):numerical_summary([value])
        for kwargs in ({'seed':True},{'seed':-1},{'resamples':99},{'resamples':True},{'resamples':10001}):
            with self.assertRaises(ValueError):numerical_summary([1,2],**kwargs)
        with self.assertRaises(ValueError):numerical_summary([1]*10001)
        with self.assertRaises(ValueError):numerical_summary([1]*10000,resamples=2000)

    def test_bootstrap_determinism_and_support(self):
        values=list(range(1,11));a=numerical_summary(values,seed=42,resamples=500)
        self.assertEqual(a,numerical_summary(values,seed=42,resamples=500))
        lo,hi=map(Fraction,a['confidence_interval']);self.assertLessEqual(lo,hi)
        self.assertGreaterEqual(lo,min(values));self.assertLessEqual(hi,max(values))
        self.assertNotEqual(a,numerical_summary(values,seed=43,resamples=500))
        self.assertIsNone(a['confidence_interval_reason'])

    def test_paired_units_and_insufficiency(self):
        a={str(i):Fraction(i+2) for i in range(6)};b={str(i):Fraction(i+1) for i in range(6)}
        result=paired_numerical_summary(a,b)
        self.assertEqual(result,paired_numerical_summary(dict(reversed(list(a.items()))),b))
        self.assertEqual(result['ratio_direction'],'candidate/baseline')
        with self.assertRaises(ValueError):paired_numerical_summary({'a':1},{'b':1})
        with self.assertRaises(ValueError):paired_numerical_summary({True:1},{True:1})
        self.assertIsNone(paired_numerical_summary({'a':1},{'a':2})['runtime_ratio']['confidence_interval'])
        self.assertIsNone(paired_numerical_summary({'a':0},{'a':2})['runtime_ratio'])
        self.assertIsNone(paired_numerical_summary({'a':2},{'a':0})['runtime_ratio'])
        with self.assertRaises(ValueError):paired_numerical_summary({'a':-1},{'a':2})
        self.assertEqual(paired_numerical_summary({}, {})['count'],0)

    def test_unavailable_is_not_zero_performance(self):
        result=unavailable_performance();self.assertEqual(result['sample_count'],0)
        for name in ('mean','median','sample_standard_deviation','percentiles','confidence_interval','paired_comparison','speedup'):
            self.assertIsNone(result[name])


class EvidenceImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.plan=json.loads((ROOT/'benchmarks/configs/campaign-development-v1.json').read_text());self.manifest=expand(self.plan)

    def anchor(self):
        entries={str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file() and p.name!='audit-sha256.json'}
        raw=canonical_json(entries);(self.root/'audit-sha256.json').write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def test_anchor_and_missing_extra_tampered(self):
        (self.root/'file').write_bytes(b'fixed');anchor=self.anchor();self.assertEqual(len(anchored_inventory(self.root,anchor)),1)
        with self.assertRaises(ValueError):anchored_inventory(self.root,'0'*64)
        (self.root/'extra').write_bytes(b'extra')
        with self.assertRaises(ValueError):anchored_inventory(self.root,anchor)
        (self.root/'extra').unlink();(self.root/'file').write_bytes(b'changed')
        with self.assertRaises(ValueError):anchored_inventory(self.root,anchor)
        (self.root/'file').unlink()
        with self.assertRaises(ValueError):anchored_inventory(self.root,anchor)

    def test_symlinks_traversal_and_fifo(self):
        (self.root/'file').write_bytes(b'fixed');anchor=self.anchor()
        (self.root/'link').symlink_to(self.root/'file')
        with self.assertRaises((ValueError,OSError)):anchored_inventory(self.root,anchor)
        (self.root/'link').unlink()
        raw=canonical_json({'../file':'0'*64});(self.root/'audit-sha256.json').write_bytes(raw)
        with self.assertRaises(ValueError):anchored_inventory(self.root,hashlib.sha256(raw).hexdigest())
        (self.root/'file').unlink();os.mkfifo(self.root/'fifo')
        raw=canonical_json({'fifo':'0'*64});(self.root/'audit-sha256.json').write_bytes(raw)
        with self.assertRaises(ValueError):anchored_inventory(self.root,hashlib.sha256(raw).hexdigest())

    def test_actual_raw_verifier_mandatory(self):
        with patch('analysis_evidence.anchored_inventory',return_value={}),patch('analysis_evidence.read_json',side_effect=[self.plan,self.manifest]),patch('analysis_evidence.verify_pilot',side_effect=ValueError('raw verifier rejected')) as verify:
            with self.assertRaisesRegex(ValueError,'raw verifier rejected'):load_phase_d(self.root,'0'*64)
            verify.assert_called_once_with(self.root/'execution/pilot')

    def test_no_scientific_override_flag(self):
        import subprocess
        result=subprocess.run([sys.executable,'-B',str(ROOT/'benchmarks/python/analyze.py'),'--phase-d',str(self.root),'--output',str(self.root/'out'),'--scientific-eligible'],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,2);self.assertFalse((self.root/'out').exists())

    def test_original_accounting_and_every_export_field(self):
        rows=original_rows(self.manifest);self.assertEqual(len(rows),104)
        self.assertEqual(sum(r['eligibility']=='unexecuted' for r in rows),104)
        directory=self.root/'phase-e-preparation';directory.mkdir()
        expected=b''.join(canonical_json(row) for row in rows)
        (directory/'original-trials.jsonl').write_bytes(expected);(directory/'diagnostic-trials.jsonl').write_bytes(b'')
        reconcile_exports(self.root,rows,[])
        for key,value in (('scientific_eligibility',True),('timing_values',1),('timing_eligible',True),('trial_id','f'*64),('actual_workers',[2]),('environment_provenance',{}),('correctness_status','passed'),('evidence_verification','verified-complete')):
            altered=copy.deepcopy(rows);altered[0][key]=value
            (directory/'original-trials.jsonl').write_bytes(b''.join(canonical_json(row) for row in altered))
            with self.subTest(key=key),self.assertRaises(ValueError):reconcile_exports(self.root,rows,[])
        for raw in (expected+canonical_json(rows[0]),b'not json\n',expected[:-1],b''):
            (directory/'original-trials.jsonl').write_bytes(raw)
            with self.assertRaises(ValueError):reconcile_exports(self.root,rows,[])


class RealPhaseDEvidenceTests(unittest.TestCase):
    """Explicit standalone tier uses retained originals, never required by CI."""
    source=None
    __test__=False
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.base=Path(cls.tmp.name)
        # Small independently rehashed transfer: raw pilot and relevant exports,
        # not a trusted substitute for the complete historical retention inventory.
        for name in ('original-plan.json','original-manifest.json','execution/inputs/plan.json','build-provenance/release/dynagraph_bench-flags.make'):
            p=cls.base/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(cls.source/name,p)
        shutil.copytree(cls.source/'execution/pilot',cls.base/'execution/pilot')
        shutil.copytree(cls.source/'phase-e-preparation',cls.base/'phase-e-preparation')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.tmpdir=tempfile.TemporaryDirectory();self.addCleanup(self.tmpdir.cleanup)
        self.root=Path(self.tmpdir.name)/'input';shutil.copytree(self.base,self.root)
    def anchor(self):
        entries={str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file() and p.name!='audit-sha256.json'}
        raw=canonical_json(entries);(self.root/'audit-sha256.json').write_bytes(raw);return hashlib.sha256(raw).hexdigest()
    def test_real_verified_counts_and_no_statistics(self):
        result=load_phase_d(self.root,self.anchor());self.assertEqual(result['original_campaign']['unexecuted'],104)
        self.assertEqual(result['derived_pilot']['verified_complete'],2)
        self.assertEqual(result['resource_classifications'],{'observed_interference':2})
        self.assertEqual(result['performance']['sample_count'],0)
    def test_rehashed_export_attacks(self):
        path=self.root/'phase-e-preparation/diagnostic-trials.jsonl';original=path.read_bytes()
        for key,value in (('scientific_eligibility',True),('scientific_eligibility',1),('timing_values',0),('timing_values',-1),('timing_values','NaN'),('timing_values',None),('timing_eligible',True),('correctness_status','failed'),('evidence_verification','unverified'),('actual_workers',[4]),('environment_provenance',{}),('attempt_id','f'*64),('algorithm','dijkstra'),('trial_id','0'*64)):
            if key=='timing_values' and value is None:continue
            rows=[json.loads(line) for line in original.splitlines()];rows[0][key]=value
            path.write_bytes(b''.join(canonical_json(row) for row in rows))
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):load_phase_d(self.root,self.anchor())
        path.write_bytes(original)
    def test_duplicate_and_substituted_rows(self):
        path=self.root/'phase-e-preparation/diagnostic-trials.jsonl';rows=path.read_bytes().splitlines(keepends=True)
        for raw in (rows[0]+rows[0],rows[1]+rows[0],b''.join(rows)+rows[0],b''):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):load_phase_d(self.root,self.anchor())
    def test_mixed_environment_and_configuration(self):
        path=self.root/'phase-e-preparation/diagnostic-trials.jsonl';original=path.read_bytes()
        for section,key,value in (('environment_provenance','hardware_sha256','f'*64),('trial','delta',32),('trial','workers',4),('trial','workload_id','foreign'),('trial','phase','measured')):
            rows=[json.loads(line) for line in original.splitlines()];rows[0][section][key]=value
            path.write_bytes(b''.join(canonical_json(row) for row in rows))
            with self.subTest(section=section,key=key),self.assertRaises(ValueError):load_phase_d(self.root,self.anchor())
        path.write_bytes(original)

    def test_raw_trial_corruption(self):
        file=next((self.root/'execution/pilot').glob('*/record.json'));value=json.loads(file.read_text());value['measurement_eligible']=True
        file.write_bytes(canonical_json(value))
        with self.assertRaises(ValueError):load_phase_d(self.root,self.anchor())
    def test_original_pilot_accounting_substitution(self):
        path=self.root/'phase-e-preparation/summary.json';value=json.loads(path.read_text());value['original_campaign']['completed']=2
        path.write_bytes(canonical_json(value))
        with self.assertRaises(ValueError):load_phase_d(self.root,self.anchor())


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(loader.loadTestsFromTestCase(cls) for cls in (NumericalEvidenceTests,EvidenceImportTests))


if __name__=='__main__':
    if len(sys.argv)>1:
        RealPhaseDEvidenceTests.source=Path(sys.argv.pop(1)).absolute()
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(RealPhaseDEvidenceTests)
        sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (NumericalEvidenceTests,EvidenceImportTests))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
