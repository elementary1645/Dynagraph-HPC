"""Pinned rendering and deterministic synthetic end-to-end output."""
from pathlib import Path
import tempfile
import unittest
from analysis_test_support import fixture,plan_for
from analyze import analyze
from analysis_import import inventory
from analysis_figures import pinned_versions
from workloads import canonical_json
from experiment_records import loads

class FigureTests(unittest.TestCase):
    def test_seven_types_deterministic_tables_figures_and_provenance(self):
        pinned_versions()  # Failure is explicit if the optional rendering environment is absent.
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            full=fixture(root/'full');latency=fixture(root/'latency',mode='per-update',run_id='2')
            plan=plan_for([full,latency]);path=root/'plan.json';path.write_bytes(canonical_json(plan))
            before={str(p):inventory(p) for p in (full,latency)}
            results=[]
            for name in ('one','two'):
                results.append(analyze(path,root/name))
            self.assertEqual(results[0],results[1])
            self.assertEqual(results[0]['figures'],'14')
            self.assertEqual(inventory(root/'one'),inventory(root/'two'))
            for p in (full,latency):self.assertEqual(inventory(p),before[str(p)])
            manifest=loads((root/'one/analysis-manifest.json').read_bytes())
            self.assertEqual(manifest['numerical_conventions']['inference'],'not_implemented')
            self.assertTrue(manifest['input_evidence'])
            for p in (root/'one/figures').glob('*.svg'):
                self.assertIn('SYNTHETIC FIXTURE',p.read_text())
            self.assertIn('SYNTHETIC FIXTURE', (root/'one/report.md').read_text())

if __name__=='__main__':unittest.main()
