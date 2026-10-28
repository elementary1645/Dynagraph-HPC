"""Bound each failure profile in a fresh process; retain last started epoch on failure."""
import os
import subprocess
import sys

binary, profile = sys.argv[1:]
limit = {'fast': 30, 'stress': 120, 'extended': 300}[profile]
env = dict(os.environ, OMP_NUM_THREADS='2', OMP_THREAD_LIMIT='2',
           OMP_DYNAMIC='FALSE', OMP_MAX_ACTIVE_LEVELS='1')
command = [binary, profile]
print(f'command={command!r} timeout={limit} environment=threads:2,limit:2,dynamic:FALSE,levels:1', flush=True)
try:
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=limit)
except subprocess.TimeoutExpired as error:
    print(f'TIMEOUT profile={profile} stdout={error.stdout!r} stderr={error.stderr!r}', flush=True)
    raise SystemExit(1)
print(result.stdout, end='')
print(result.stderr, end='', file=sys.stderr)
expected = {'fast': 4, 'stress': 20, 'extended': 100}[profile]
receipt = f'COMPLETE profile={profile} epochs_per_stage_and_metrics={expected} stages=3 faulted_calls={expected * 18}'
if result.returncode or receipt not in result.stdout:
    print(f'FAIL profile={profile} exit={result.returncode} expected_receipt={receipt!r}', file=sys.stderr)
    raise SystemExit(1)
