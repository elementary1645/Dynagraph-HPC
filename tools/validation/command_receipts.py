"""Bounded sequential process runner with allowlisted provenance and launch receipts."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


REMOVED = {'CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS', 'MPLCONFIGDIR',
           'MPLBACKEND', 'ASAN_OPTIONS', 'UBSAN_OPTIONS', 'LSAN_OPTIONS', 'TSAN_OPTIONS',
           'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LIBRARY_PATH', 'CPATH', 'CPLUS_INCLUDE_PATH',
           'TMPDIR', 'TMP', 'TEMP', 'MAKEFLAGS', 'MFLAGS', 'BASH_ENV', 'ENV'}
PREFIXES = ('PYTHON', 'OMP_', 'GOMP_', 'KMP_', 'CMAKE_', 'CTEST_', 'GIT_')


def controlled_environment(output):
    env = dict(os.environ)
    removed = sorted(k for k in env if k in REMOVED or k.startswith(PREFIXES))
    for key in removed:
        del env[key]
    overrides = dict(PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0', PYTHONNOUSERSITE='1',
                     MPLCONFIGDIR=str(output / 'mpl-cache'), MPLBACKEND='Agg',
                     TMPDIR=str(output / 'tmp'), LC_ALL='C.UTF-8', TZ='UTC', GIT_OPTIONAL_LOCKS='0')
    env.update(overrides)
    return env, dict(removed_variable_names=removed, overrides=overrides,
                     policy='remove listed build/Python/OpenMP/sanitizer controls; inherit other OS variables; '
                            'record hashes only for PATH and HOME; never dump full environment',
                     inherited_sha256={k: hashlib.sha256(env.get(k, '').encode()).hexdigest()
                                       for k in ('PATH', 'HOME')})


class Runner:
    def __init__(self, output):
        self.output = output
        (output / 'tmp').mkdir()
        self.environment, policy = controlled_environment(output)
        (output / 'environment-policy.json').write_text(json.dumps(policy, indent=2) + '\n')
        self.records = []

    def run(self, name, command, cwd=None, extra=None, timeout=1800):
        settings = dict(self.environment, **(extra or {}))
        command = [str(arg) for arg in command]
        log_path = self.output / (name + '.log')
        start, tick = time.time(), time.monotonic()
        code, classification, error = None, 'launch-error', None
        with log_path.open('wb') as log:
            try:
                process = subprocess.Popen(command, cwd=cwd, env=settings, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    code = process.wait(timeout=timeout)
                    classification = 'exited'
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    code, classification = 124, 'timeout'
                    error = f'command exceeded {timeout} seconds; process group terminated'
            except OSError as failure:
                error = f'{type(failure).__name__}: {failure}'
            if error:
                log.write(('\n' + error + '\n').encode())
        relevant = {k: v for k, v in settings.items()
                    if k in REMOVED or k.startswith(PREFIXES) or k in ('LC_ALL', 'TZ')}
        receipt = dict(name=name, command=command, cwd=str(cwd or Path.cwd()),
                       start_unix=start, end_unix=time.time(), wall_seconds=time.monotonic()-tick,
                       exit_code=code, classification=classification, error=error,
                       environment=relevant, log=log_path.name,
                       log_sha256=hashlib.sha256(log_path.read_bytes()).hexdigest())
        self.records.append(receipt)
        (self.output / 'commands.json').write_text(json.dumps(self.records, indent=2) + '\n')
        print(name, classification, code, flush=True)
        if classification != 'exited' or code != 0:
            raise RuntimeError(f'{name}: {classification}, exit={code}; see {log_path}')
        return log_path.read_bytes()
