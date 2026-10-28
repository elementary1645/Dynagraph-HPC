"""Isolated 5C-2A command recorder; never registered in CTest or CI.

Run from the repository root. All generated evidence is outside tracked source.
Stages are separate so a failed build cannot silently fall back to old binaries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tests/tsan_controls'
BUILD = ROOT / 'build/tsan-5c2a'
OUTPUT = ROOT / 'results/validation/phase5c2a'
FLAGS = ['-std=c++17', '-g', '-O1', '-fsanitize=thread', '-fno-omit-frame-pointer',
         '-fPIE', '-pie', '-fopenmp', '-pthread', '-Wall', '-Wextra', '-Wpedantic',
         '-Wconversion', '-Wshadow', '-Werror']
TSAN = 'halt_on_error=1:exitcode=66'
COMPILE_LAYOUT = '-fPIE'
LINK_LAYOUT = '-pie'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(name, args, settings=None, timeout=60):
    env = dict(os.environ)
    for key in ('TSAN_OPTIONS', 'ASAN_OPTIONS', 'UBSAN_OPTIONS', 'OMP_TOOL_LIBRARIES',
                'OMP_DYNAMIC', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'OMP_SCHEDULE'):
        env.pop(key, None)
    env.update(settings or {})
    start = time.monotonic()
    timed_out = False
    with (OUTPUT / (name + '.stdout')).open('xb') as stdout, (OUTPUT / (name + '.stderr')).open('xb') as stderr:
        process = subprocess.Popen(list(map(str, args)), cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            code = process.wait()
    raw = (OUTPUT / (name + '.stderr')).read_text(errors='replace')
    record = dict(command=list(map(str, args)), cwd=str(ROOT), exit_code=code, timed_out=timed_out,
                  seconds=round(time.monotonic() - start, 3),
                  environment={k: env.get(k) for k in ('TSAN_OPTIONS', 'ASAN_OPTIONS', 'UBSAN_OPTIONS',
                      'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'OMP_DYNAMIC', 'OMP_TOOL_LIBRARIES')},
                  warnings=re.findall(r'WARNING: ThreadSanitizer: ([^\n]+)', raw),
                  fatal=re.findall(r'FATAL: ThreadSanitizer: ([^\n]+)', raw),
                  stdout_sha256=digest(OUTPUT / (name + '.stdout')),
                  stderr_sha256=digest(OUTPUT / (name + '.stderr')))
    (OUTPUT / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    print(name, 'exit=' + str(code), 'timeout=' + str(timed_out),
          'warnings=' + str(len(record['warnings'])), 'fatal=' + str(len(record['fatal'])), flush=True)
    return record


def successful(record):
    if record['exit_code'] != 0 or record['timed_out']:
        raise RuntimeError('build/compile path failed; do not use stale binaries: ' + ' '.join(record['command']))


def build():
    if BUILD.exists():
        raise RuntimeError('fresh instrumented build directory must not exist')
    successful(command('configure', ['cmake', '-S', '.', '-B', BUILD, '-DCMAKE_CXX_COMPILER=g++',
        '-DCMAKE_BUILD_TYPE=Debug', '-DBUILD_TESTING=ON', '-DDYNAGRAPH_WARNINGS_AS_ERRORS=ON',
        '-DCMAKE_CXX_FLAGS=-O1 -fsanitize=thread -fno-omit-frame-pointer ' + COMPILE_LAYOUT,
        '-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=thread ' + LINK_LAYOUT]))
    successful(command('build', ['cmake', '--build', BUILD, '--parallel', '2', '--target',
        'test_delta_stepping', 'test_system_correctness', 'test_system_adversarial'], timeout=180))
    for name in ('ordinary_race', 'openmp_race', 'barrier_publication', 'atomic_publication'):
        successful(command('compile-' + name, ['g++', *FLAGS, SOURCE / (name + '.cpp'), '-o', OUTPUT / name]))
    successful(command('compile-project_work_probe', ['g++', *FLAGS, '-I', ROOT / 'include', '-I', ROOT / 'tests',
        SOURCE / 'project_work_probe.cpp', BUILD / 'libdynagraph.a', '-o', OUTPUT / 'project_work_probe']))
    bins = [OUTPUT / n for n in ('ordinary_race', 'openmp_race', 'barrier_publication', 'atomic_publication', 'project_work_probe')]
    bins += [BUILD / 'tests' / n for n in ('test_delta_stepping', 'test_system_correctness', 'test_system_adversarial')]
    for binary in bins:
        successful(command('ldd-' + binary.name, ['ldd', binary]))
    value = dict(source_sha256={str(p.relative_to(ROOT)): digest(p) for p in sorted(SOURCE.glob('*.cpp'))},
                 production_sha256=digest(ROOT / 'src/algorithms/delta_stepping.cpp'),
                 binary_sha256={str(p.relative_to(ROOT)): digest(p) for p in bins})
    (OUTPUT / 'fresh-build.json').write_text(json.dumps(value, indent=2) + '\n')


def verify_build():
    data = json.loads((OUTPUT / 'fresh-build.json').read_text())
    for key in ('source_sha256', 'binary_sha256'):
        if any(digest(ROOT / p) != value for p, value in data[key].items()):
            raise RuntimeError('source or fresh binary changed; stop this path')
    if digest(ROOT / 'src/algorithms/delta_stepping.cpp') != data['production_sha256']:
        raise RuntimeError('production source changed')


def run(label):
    verify_build()
    for repeat in range(3):
        for variant, threads, limit in (('one', '1', '1'), ('env1-team2', '1', '2'), ('two', '2', '2')):
            env = dict(TSAN_OPTIONS=TSAN, OMP_NUM_THREADS=threads, OMP_THREAD_LIMIT=limit, OMP_DYNAMIC='FALSE')
            base = f'{label}-{variant}-r{repeat}'
            for name, arguments in (('ordinary_race', []), ('openmp_race', []),
                    ('barrier_publication', ['implicit']), ('barrier_publication', ['explicit']), ('atomic_publication', [])):
                suffix = '-' + arguments[0] if arguments else ''
                command(base + '-' + name + suffix, [OUTPUT / name, *arguments], env, timeout=15)
            command(base + '-delta-tests', [BUILD / 'tests/test_delta_stepping'], env, timeout=30)
            for workers in ('1', '2'):
                command(base + '-work-probe-w' + workers, [OUTPUT / 'project_work_probe', workers], env, timeout=15)
            command(base + '-system-case', [BUILD / 'tests/test_system_correctness', '--case', '3', '--source', '0',
                '--workers', '1' if limit == '1' else '2'], env, timeout=30)


def optional_tools():
    # This path stops at compiler failure; it never substitutes GCC headers/libgomp.
    command('clang-openmp-attempt', ['clang++', *FLAGS, SOURCE / 'barrier_publication.cpp', '-o', OUTPUT / 'clang_barrier'])
    native_flags = [flag for flag in FLAGS if flag != '-fsanitize=thread']
    for name in ('ordinary_race', 'openmp_race', 'barrier_publication', 'atomic_publication'):
        successful(command('native-compile-' + name, ['g++', *native_flags, SOURCE / (name + '.cpp'), '-o', OUTPUT / ('native-' + name)]))
        arguments = ['implicit'] if name == 'barrier_publication' else []
        env = dict(OMP_NUM_THREADS='2', OMP_THREAD_LIMIT='2', OMP_DYNAMIC='FALSE')
        command('native-' + name, [OUTPUT / ('native-' + name), *arguments], env)
        command('helgrind-' + name, ['valgrind', '--tool=helgrind', '--error-exitcode=67', '--history-level=full',
            '--fair-sched=yes', OUTPUT / ('native-' + name), *arguments], env, timeout=30)


def followup():
    verify_build()
    successful(command('build-delta-failure', ['cmake', '--build', BUILD, '--parallel', '2',
        '--target', 'test_delta_failure'], timeout=180))
    binary = BUILD / 'tests/test_delta_failure'
    (OUTPUT / 'failure-build.json').write_text(json.dumps(
        dict(binary=str(binary), sha256=digest(binary)), indent=2) + '\n')
    for repeat in range(3):
        for threads in ('1', '2'):
            env = dict(TSAN_OPTIONS=TSAN, OMP_NUM_THREADS=threads, OMP_THREAD_LIMIT='2', OMP_DYNAMIC='FALSE')
            command(f'followup-env{threads}-r{repeat}-delta-failure', [binary], env, timeout=30)
        # Retain all reports until program exit, bounded by the same timeout.
        # This is not a suppression or a clean-run attempt.
        env = dict(TSAN_OPTIONS='halt_on_error=0:exitcode=66', OMP_NUM_THREADS='2',
                   OMP_THREAD_LIMIT='2', OMP_DYNAMIC='FALSE')
        command(f'followup-r{repeat}-work-probe-all-reports', [OUTPUT / 'project_work_probe', '2'], env, timeout=30)
        for kind in ('implicit', 'explicit'):
            command(f'followup-r{repeat}-barrier-all-reports-{kind}',
                    [OUTPUT / 'barrier_publication', kind], env, timeout=15)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('stage', choices=('build', 'run', 'optional', 'followup'))
    parser.add_argument('--label', default='sandbox')
    parser.add_argument('--layout', choices=('pie', 'fixed'), default='pie',
                        help='fixed is a separate GCC-only address-layout calibration experiment')
    args = parser.parse_args()
    if args.layout == 'fixed':
        BUILD = ROOT / 'build/tsan-5c2a-fixed'
        OUTPUT = ROOT / 'results/validation/phase5c2a-fixed'
        COMPILE_LAYOUT, LINK_LAYOUT = '-fno-pie', '-no-pie'
        FLAGS = [COMPILE_LAYOUT if f == '-fPIE' else LINK_LAYOUT if f == '-pie' else f for f in FLAGS]
    if args.stage == 'build':
        OUTPUT.mkdir(exist_ok=args.layout == 'pie')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.label):
        parser.error('simple label required')
    if args.stage == 'build': build()
    elif args.stage == 'run': run(args.label)
    elif args.stage == 'optional': optional_tools()
    else: followup()
