"""Actual orchestrator -> complete importer -> analysis CLI, without timing claims."""
import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from analysis_test_support import ROOT, plan_for
from analysis_import import inventory
from artifacts import write_bundle
from experiment_records import loads, validate_dataset
from test_workloads import specification
from workloads import canonical_json, sha256

RUNNER=os.environ.get('DYNAGRAPH_BENCH')
if __name__=='__main__':RUNNER=str(Path(sys.argv.pop(1)).resolve())

@unittest.skipUnless(RUNNER,'pass the benchmark executable or set DYNAGRAPH_BENCH')
class IntegrationTests(unittest.TestCase):
    def test_completed_experiments_cli_pairing_and_readonly_regeneration(self):
        keep=os.environ.get('DYNAGRAPH_ANALYSIS_SMOKE_ROOT')
        if keep:
            root=Path(keep).resolve();root.mkdir(parents=True,exist_ok=False)
        else:
            temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
            root=Path(temporary.name)
        write_bundle(specification(),root/'bundle')
        inputs=[]
        for mode in ('full-trace','per-update'):
            config=dict(schema_version=1,manifest='bundle/manifest.json',timing_mode=mode,blocks='4',
                        order_seed='0',delta='16',threads='2',no_effect='shared_fast_path',timeout_seconds='20',warmups='1')
            path=root/(mode+'.json');path.write_bytes(canonical_json(config))
            evidence=root/mode
            result=subprocess.run([sys.executable,str(ROOT/'benchmarks/python/run.py'),'run',
                                   '--config',str(path),'--runner',RUNNER,'--output',str(evidence)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            self.assertEqual(validate_dataset(evidence/'records.jsonl')['status'],'complete')
            inputs.append(evidence)
        plan=plan_for(inputs);plan['figures']=[]
        for item in plan['inputs']:item.update(synthetic=False,evidence_intent='harness')
        for config in plan['compatible_configurations']:config['build_type']=None
        path=root/'analysis-plan.json';path.write_bytes(canonical_json(plan))
        before=[inventory(p) for p in inputs]
        command=[sys.executable,str(ROOT/'benchmarks/python/analyze.py'),'--plan',str(path)]
        for name in ('analysis-one','analysis-two'):
            result=subprocess.run([*command,'--output',str(root/name)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            self.assertEqual(loads(result.stdout)['accepted_inputs'],'2')
        self.assertEqual(inventory(root/'analysis-one'),inventory(root/'analysis-two'))
        self.assertEqual([inventory(p) for p in inputs],before)
        with (root/'analysis-one/paired-ratios.csv').open(newline='') as stream:pairs=list(csv.DictReader(stream))
        self.assertEqual(len(pairs),16)
        for pair in pairs:
            self.assertEqual(int(pair['numerator_trial_id'])//4,int(pair['block_id']))
            self.assertEqual(int(pair['baseline_trial_id'])//4,int(pair['block_id']))
        manifest=loads((root/'analysis-one/analysis-manifest.json').read_bytes())
        for name,digest in manifest['output_sha256'].items():
            self.assertEqual(sha256((root/'analysis-one'/name).read_bytes()),digest)
        repeated=subprocess.run([*command,'--output',str(root/'analysis-one')],capture_output=True)
        self.assertEqual(repeated.returncode,2)
        # Keep the raw evidence unchanged; a plan identity mismatch must reject the whole analysis.
        plan['inputs'][0]['expected_identities']['executable_sha256']='0'*64
        path=root/'bad-plan.json';path.write_bytes(canonical_json(plan))
        rejected=subprocess.run([sys.executable,str(ROOT/'benchmarks/python/analyze.py'),'--plan',str(path),
                                 '--output',str(root/'rejected')],capture_output=True)
        self.assertEqual(rejected.returncode,2)
        self.assertEqual(loads((root/'rejected/analysis-manifest.json').read_bytes())['status'],'failed')
        self.assertEqual([inventory(p) for p in inputs],before)


if __name__=='__main__':
    unittest.main()
