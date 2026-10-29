"""Sequential fresh-checkout full verification; disjoint new outputs, no installs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from check_execution import validate_report
from check_registration import compare, expected_names, registration_names, strict_loads
from command_receipts import Runner
from snapshot import compare_inventory, copy_inventory, inventory, inventory_hash, validate_paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--revision', required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--include-working-tree', action='store_true',
                        help='explicit precommit overlay; records dirty source identity')
    args = parser.parse_args()
    source, output = validate_paths(args.source, args.output)
    # Preserve the venv path; resolving its executable symlink loses pyvenv.cfg.
    python = args.python.absolute()
    output.mkdir(parents=True, exist_ok=False)
    runner = Runner(output)
    run = runner.run

    def git(label, root, *arguments):
        return run(label, ['git', '-C', str(root), *arguments], root)

    def files(label, root):
        raw = git(label, root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z')
        return [n for n in raw.decode('utf-8').split('\0') if n]

    revision = git('base-revision', source, 'rev-parse', '--verify', '--end-of-options',
                   args.revision + '^{commit}').decode().strip()
    status = git('source-status', source, 'status', '--porcelain', '--untracked-files=all').decode()
    if status and not args.include_working_tree:
        raise ValueError('source is dirty; use explicit --include-working-tree for precommit evidence')
    source_inventory = inventory(source, files('source-files', source)) if args.include_working_tree else None
    checkout = output / 'checkout'
    run('clone', ['git', 'clone', '--no-hardlinks', '--no-checkout', '--', str(source), str(checkout)])
    git('checkout', checkout, 'checkout', '--detach', revision)
    actual = git('checkout-revision', checkout, 'rev-parse', 'HEAD').decode().strip()
    clean = git('checkout-status', checkout, 'status', '--porcelain').decode()
    if actual != revision or clean:
        raise ValueError('initial isolated checkout identity/cleanliness mismatch')
    identity = dict(base_revision=actual, initial_checkout_clean=True, overlay=False)
    if args.include_working_tree:
        patch = git('source-diff', source, 'diff', '--binary', '--no-ext-diff', '--no-textconv', revision, '--')
        (output / 'source.patch').write_bytes(patch)
        if patch:
            run('apply-overlay', ['git', 'apply', str(output / 'source.patch')], checkout)
        copy_inventory(source, checkout, source_inventory)
        compare_inventory(source_inventory, inventory(source, files('source-files-recheck', source)))
        identity.update(overlay=True, patch_sha256=hashlib.sha256(patch).hexdigest(), original_status=status)
    copied = inventory(checkout, files('checkout-files', checkout))
    if source_inventory is not None:
        compare_inventory(source_inventory, copied)
    identity.update(inventory=copied, inventory_sha256=inventory_hash(copied),
                    source_destination_match=source_inventory is not None)
    (output / 'source-identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    run('environment', [python, '-B', checkout/'tools/validation/check_environment.py'], checkout)
    for tool in ('cmake', 'g++'):
        run(tool+'-version', [tool, '--version'])
    expected = expected_names()
    outcomes = {}
    for mode in ('debug', 'release', 'sanitize'):
        build = output / ('build-' + mode)
        if build.exists():
            raise ValueError('build directory must be new: ' + str(build))
        command = ['cmake', '-S', str(checkout), '-B', str(build), '-G', 'Unix Makefiles',
                   '-DCMAKE_CXX_COMPILER=g++', '-DCMAKE_BUILD_TYPE=' + ('Release' if mode=='release' else 'Debug'),
                   '-DBUILD_TESTING=ON', '-DDYNAGRAPH_WARNINGS_AS_ERRORS=ON',
                   '-DDYNAGRAPH_FULL_VALIDATION=ON', '-DDYNAGRAPH_ANALYSIS_PYTHON='+str(python)]
        if mode == 'sanitize':
            command += ['-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer',
                        '-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined']
        run(mode+'-configure', command, checkout)
        raw = run(mode+'-registration', ['ctest', '--test-dir', build, '--show-only=json-v1'], checkout)
        names = registration_names(strict_loads(raw))
        compare(names, expected)
        run(mode+'-build', ['cmake', '--build', build, '--parallel', '2'], checkout)
        report = output / (mode + '-execution.xml')
        extra = {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'} if mode=='sanitize' else {}
        # Runner rejects any nonzero exit before report acceptance. Fresh output
        # prevents a report from a prior invocation from satisfying this run.
        run(mode+'-ctest', ['ctest', '--test-dir', build, '--output-on-failure', '--parallel', '1',
                           '--output-junit', report], checkout, extra)
        outcomes[mode] = dict(registered=len(names), **validate_report(report, runner.records[-1]['exit_code'], expected))
        (output / 'acceptance.json').write_text(json.dumps(outcomes, indent=2) + '\n')
        print(mode, 'accepted', outcomes[mode]['passed'], 'executed passes', flush=True)
    # Detect changes to either snapshot while running. Build products are outside
    # checkout; source-inventory checks intentionally exclude ignored artifacts.
    compare_inventory(copied, inventory(checkout, files('checkout-files-final', checkout)))
    if source_inventory is not None:
        compare_inventory(source_inventory, inventory(source, files('source-files-final', source)))
    evidence = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    (output / 'evidence-sha256.json').write_text(json.dumps(evidence, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError) as error:
        print('Clean-checkout verification failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
