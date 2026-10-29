"""Actual CMake configurations: quoting, minimal mode and optional registration."""
import argparse
import json
from pathlib import Path
import sys

from check_registration import compare, expected_names, registration_names, strict_loads
from command_receipts import Runner
from snapshot import copy_inventory, inventory, validate_paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    source, output = validate_paths(Path(__file__).resolve().parents[2], args.output)
    output.mkdir(parents=True, exist_ok=False)
    runner = Runner(output)
    raw = runner.run('source-files', ['git','ls-files','--cached','--others','--exclude-standard','-z'], source)
    entries = inventory(source, [n for n in raw.decode().split('\0') if n])
    fixture = output/"source with spaces apostrophe' Unicode-λ"
    fixture.mkdir()
    copy_inventory(source, fixture, entries)
    python = str(args.python.absolute())
    optional = ['concurrency-stress','concurrency-extended','system-stress','system-extended']
    cases = [
        ('quoted-full', ['-DDYNAGRAPH_FULL_VALIDATION=ON','-DDYNAGRAPH_ANALYSIS_PYTHON='+python],expected_names()),
        ('minimal', ['-DDYNAGRAPH_FULL_VALIDATION=OFF','-DDYNAGRAPH_ANALYSIS_PYTHON=/nonexistent/analysis-python'],
         [n for n in expected_names() if not n.startswith('analysis_')]),
        ('library', ['-DBUILD_TESTING=OFF'], []),
        ('optional', ['-DDYNAGRAPH_FULL_VALIDATION=ON','-DDYNAGRAPH_ANALYSIS_PYTHON='+python] +
         ['-DDYNAGRAPH_ENABLE_'+tier+'=ON' for tier in ('CONCURRENCY_STRESS','CONCURRENCY_EXTENDED','VALIDATION_STRESS','VALIDATION_EXTENDED')],
         expected_names(optional))]
    outcomes = []
    for name, flags, expected in cases:
        build = output/('build-'+name)
        runner.run(name+'-configure', ['cmake','-S',fixture,'-B',build,*flags])
        raw = runner.run(name+'-registration', ['ctest','--test-dir',build,'--show-only=json-v1'])
        actual = registration_names(strict_loads(raw))
        compare(actual, expected)
        outcomes.append(dict(case=name, count=len(actual), passed=True))
    try:
        runner.run('full-without-tests', ['cmake','-S',fixture,'-B',output/'build-invalid',
                                        '-DBUILD_TESTING=OFF','-DDYNAGRAPH_FULL_VALIDATION=ON'])
    except RuntimeError:
        record = runner.records[-1]
        diagnostic = (output/'full-without-tests.log').read_text()
        if record['classification'] != 'exited' or record['exit_code'] == 0 or 'requires BUILD_TESTING=ON' not in diagnostic:
            raise
    else:
        raise ValueError('full mode incorrectly accepted BUILD_TESTING=OFF')
    (output/'outcomes.json').write_text(json.dumps(outcomes, indent=2)+'\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
