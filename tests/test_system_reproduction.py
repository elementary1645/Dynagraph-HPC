"""Actual deterministic test CLI, malformed arguments and worker-count equivalence."""
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest


class ReproductionTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([CLI, *args], capture_output=True, timeout=60,
                              env=dict(os.environ, OMP_NUM_THREADS='2', OMP_THREAD_LIMIT='2', OMP_DYNAMIC='FALSE'))

    def test_repeat_seed_case_source_and_workers(self):
        for profile, case in (('fast', '31'), ('stress', '95'), ('extended', '383')):
            args = ('--profile', profile, '--seed', '4294967295', '--case', case, '--source', '0')
            outputs = []
            for workers in ('1', '2', '2', '4'):
                result = self.invoke(*args, '--workers', workers)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                outputs.append(re.search(rb'generation_fingerprint=\d+ state_fingerprint=\d+', result.stdout).group())
            self.assertEqual(len(set(outputs)), 1)
            if profile == 'fast':
                self.assertEqual(outputs[0], b'generation_fingerprint=6423381795917974648 state_fingerprint=618799244384374341')
            # Worker-dependent heuristic choices are allowed; state is invariant.

    def test_invalid_options(self):
        for args in (('--profile', 'unknown'), ('--workers', '0'), ('--workers', '5'),
                     ('--case', '48'), ('--case', '-1'), ('--source', '0'),
                     ('--seed', '4294967296'), ('--seed', '01'), ('--seed', '-1'),
                     ('--seed', '1', '--seed', '2'), ('--unknown', '1'), ('--case',),
                     ('--case', '0', '--source', '127')):
            with self.subTest(args=args):
                self.assertEqual(self.invoke(*args).returncode, 2)


if __name__ == '__main__':
    CLI = str(Path(sys.argv.pop(1)).resolve())
    unittest.main()
