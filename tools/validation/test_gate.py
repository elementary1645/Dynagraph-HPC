"""Isolated full-mode configure failures; never alter the real Python environment."""
import argparse
import json
from pathlib import Path
import sys


from command_receipts import Runner
from snapshot import copy_inventory, inventory, validate_paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = validate_paths(args.source, args.output)
    output.mkdir(parents=True, exist_ok=False)
    args.output = output
    python = args.python.absolute()
    runner = Runner(output)
    raw = runner.run('source-files', ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], source)
    entries = inventory(source, [name for name in raw.decode().split('\0') if name])
    fixture = output / 'source-fixture'
    fixture.mkdir()
    copy_inventory(source, fixture, entries)
    records = []
    cases = [('absent', 'working DYNAGRAPH_ANALYSIS_PYTHON'),
             ('old', 'found 3.10.0 mock'), ('missing', 'missing pinned dependency matplotlib'),
             ('mismatch', 'pinned dependency mismatch: matplotlib'),
             ('agg', 'Matplotlib Agg initialization/render failed'),
             ('registration', "missing=['analysis_stats']")]
    for case, diagnostic in cases:
        interpreter = str(python)
        if case == 'absent':
            interpreter = str(args.output.resolve() / 'does-not-exist')
        elif case not in ('registration',):
            wrapper = args.output.resolve() / ('python-' + case)
            wrapper.write_text('#!' + str(python) + '\n' +
                'import sys, importlib.util, importlib.metadata\n' +
                'spec=importlib.util.spec_from_file_location("gate",sys.argv[1])\n' +
                'm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n' +
                ('sys.version_info=(3,10,0)\nsys.version="3.10.0 mock"\n' if case == 'old' else '') +
                ('def missing(name):\n raise importlib.metadata.PackageNotFoundError(name)\nimportlib.metadata.version=missing\n' if case == 'missing' else '') +
                ('importlib.metadata.version=lambda name: "0.0.mock"\n' if case == 'mismatch' else '') +
                ('def fail():\n raise RuntimeError("mock Agg failure")\nm.initialize_agg=fail\n' if case == 'agg' else '') +
                'sys.exit(m.main())\n')
            wrapper.chmod(0o755)
            interpreter = str(wrapper)
        if case == 'registration':
            cmake = fixture / 'tests/CMakeLists.txt'
            cmake.write_text(cmake.read_text().replace('IN ITEMS import stats)', 'IN ITEMS import)'))
        command = ['cmake', '-S', str(fixture), '-B', str(args.output.resolve() / case),
                   '-DDYNAGRAPH_FULL_VALIDATION=ON', '-DDYNAGRAPH_ANALYSIS_PYTHON=' + interpreter]
        try:
            runner.run(case, command, timeout=120)
        except RuntimeError:
            pass  # The classification, code and specific diagnostic are checked below.
        record = runner.records[-1]
        text = (output / (case + '.log')).read_text()
        passed = (record['classification'] == 'exited' and record['exit_code'] != 0 and
                  diagnostic in ' '.join(text.split()))
        records.append(dict(case=case, command=command, exit_code=record['exit_code'],
                            expected_diagnostic=diagnostic, passed=passed))
        print(case, 'PASS' if passed else 'FAIL', flush=True)
        (args.output / 'negative-results.json').write_text(json.dumps(records, indent=2)+'\n')
        if not passed:
            return 1
    # Algorithmic checker failures exercise extra and duplicate names too.
    sys.path.insert(0, str(source / 'tools/validation'))
    from check_registration import compare, expected_names
    names = expected_names()
    for label, actual in [('missing', names[1:]), ('extra', names + ['unexpected']),
                          ('duplicate', names + [names[0]])]:
        try:
            compare(actual, names)
        except ValueError as error:
            print(label, str(error), flush=True)
        else:
            raise AssertionError(label + ' was accepted')
    return 0


if __name__ == '__main__':
    sys.exit(main())
