"""One full-validation CI leg, with the same local and hosted acceptance gate."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from check_execution import validate_report
from check_registration import compare, expected_names, registration_names, strict_loads
from command_receipts import Runner
from snapshot import compare_inventory, inventory, inventory_hash, validate_paths


def source_identity(runner, source):
    revision = runner.run('revision', ['git', 'rev-parse', 'HEAD'], source).decode().strip()
    status = runner.run('status', ['git', 'status', '--porcelain', '--untracked-files=all'], source).decode()
    raw = runner.run('source-files', ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], source)
    entries = inventory(source, [n for n in raw.decode().split('\0') if n])
    result = dict(git_revision=revision, dirty=bool(status), git_status=status,
                  inventory=entries, inventory_sha256=inventory_hash(entries))
    (runner.output/'source-identity.json').write_text(json.dumps(result, indent=2)+'\n')
    return entries


def hashes(output):
    entries = {}
    for path in sorted(output.rglob('*')):
        if path.is_symlink():
            raise ValueError('symlink in evidence: ' + str(path))
        if path.is_file() and path != output/'evidence-sha256.json':
            entries[path.relative_to(output).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output/'evidence-sha256.json').write_text(json.dumps(entries, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--mode', choices=('debug', 'release', 'sanitize'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.mode == 'release' and not args.smoke:
        parser.error('release validation requires --smoke for release-smoke-v1')
    if args.smoke and args.mode != 'release':
        parser.error('--smoke is supported only for Release')
    source, output = validate_paths(args.source, args.output)
    python = args.python.absolute()
    output.mkdir(parents=True, exist_ok=False)
    runner = Runner(output)
    validation_error = None
    try:
        before = source_identity(runner, source)
        runner.run('environment', [python, '-B', source/'tools/validation/check_environment.py'], source)
        for tool in ('cmake', 'ctest', 'g++'):
            runner.run(tool+'-version', [tool, '--version'], source)
        build = output/'build'
        command = ['cmake', '-S', source, '-B', build, '-G', 'Unix Makefiles',
                   '-DCMAKE_CXX_COMPILER=g++', '-DCMAKE_BUILD_TYPE='+('Release' if args.mode=='release' else 'Debug'),
                   '-DBUILD_TESTING=ON', '-DDYNAGRAPH_WARNINGS_AS_ERRORS=ON',
                   '-DDYNAGRAPH_FULL_VALIDATION=ON', '-DDYNAGRAPH_ANALYSIS_PYTHON='+str(python)]
        if args.mode == 'sanitize':
            command += ['-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer',
                        '-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined']
        runner.run('configure', command, source)
        raw = runner.run('registration', ['ctest', '--test-dir', build, '--show-only=json-v1'], source)
        compare(registration_names(strict_loads(raw)), expected_names())
        runner.run('build', ['cmake', '--build', build, '--parallel', '2'], source)
        options = dict(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1') if args.mode=='sanitize' else {}
        report = output/'execution.xml'
        runner.run('ctest', ['ctest', '--test-dir', build, '--output-on-failure', '--parallel', '1',
                            '--output-junit', report], source, options)
        accepted = validate_report(report, runner.records[-1]['exit_code'], expected_names())
        (output/'acceptance.json').write_text(json.dumps(accepted, indent=2)+'\n')
        if args.smoke:
            runner.run('pipeline', [python, '-B', source/'tools/validation/smoke_pipeline.py',
                                   '--source', source, '--runner', build/'dynagraph_bench',
                                   '--output', output/'pipeline'], source)
            runner.run('pipeline-negative', [python, '-B', source/'tools/validation/test_smoke.py',
                                            '--pipeline', output/'pipeline', '--output', output/'pipeline-negative'], source)
        raw = runner.run('source-files-final', ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], source)
        compare_inventory(before, inventory(source, [n for n in raw.decode().split('\0') if n]))
        (output/'result.json').write_text(json.dumps(dict(status='complete', mode=args.mode, passed=accepted['passed'],
                                                       source_unchanged=True, smoke=args.smoke))+'\n')
    except (ValueError, RuntimeError, OSError) as error:
        validation_error = error
        classification = ('command-failed' if runner.records and
                          (runner.records[-1]['classification'] != 'exited' or runner.records[-1]['exit_code'] != 0)
                          else 'validation-rejected')
        (output/'failure.json').write_text(json.dumps(dict(status='failed', classification=classification, error=str(error)))+'\n')
    finally:
        # Build products are intentionally not uploaded; preserve raw test evidence.
        entries = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()
                   and p.name != 'evidence-sha256.json'}
        (output/'evidence-sha256.json').write_text(json.dumps(entries, indent=2)+'\n')
    # A completed leg always produces and independently reopens a portable archive.
    from evidence_archive import create
    if validation_error is not None:
        # Preserve raw evidence even if the captured source is unavailable/changed.
        try:
            create(output, source, output.with_name(output.name + '.failed.tar.gz'), profile='failed-run-v1')
        except (ValueError, OSError) as archive_error:
            print('Failed-run archive unavailable: ' + str(archive_error), file=sys.stderr)
        raise validation_error
    create(output, source, output.with_name(output.name + '.tar.gz'))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError) as error:
        print('CI verification failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
