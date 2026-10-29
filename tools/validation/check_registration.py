"""Check exact CTest names; standard library only, Python 3.8+."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import subprocess
import sys


def strict_loads(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result

    def invalid(value):
        raise ValueError('invalid JSON constant: ' + value)

    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('nonfinite JSON number: ' + value)
        return number

    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid, parse_float=finite)


def strings(value, label, nonempty=False):
    if (not isinstance(value, list) or (nonempty and not value) or
            any(not isinstance(v, str) or '\x00' in v for v in value)):
        raise ValueError(label + ': expected string array')


def metadata(document):
    graph = document.get('backtraceGraph')
    if 'backtraceGraph' not in document:
        return None
    if not isinstance(graph, dict):
        raise ValueError('backtraceGraph must be an object')
    for key in ('commands', 'files'):
        strings(graph.get(key), 'backtraceGraph.' + key)
    nodes = graph.get('nodes')
    if not isinstance(nodes, list):
        raise ValueError('backtraceGraph.nodes must be an array')
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError('backtrace node must be an object')
        for key, limit in (('command', len(graph['commands'])), ('file', len(graph['files'])),
                           ('parent', len(nodes))):
            if key in node and (type(node[key]) is not int or not 0 <= node[key] < limit):
                raise ValueError('invalid backtrace node ' + key)
        if 'line' in node and (type(node['line']) is not int or node['line'] < 1):
            raise ValueError('invalid backtrace node line')
    return len(nodes)


def property_metadata(key, value):
    if key in ('ENVIRONMENT', 'LABELS', 'PASS_REGULAR_EXPRESSION', 'FAIL_REGULAR_EXPRESSION',
               'SKIP_REGULAR_EXPRESSION', 'DEPENDS', 'FIXTURES_SETUP', 'FIXTURES_REQUIRED',
               'FIXTURES_CLEANUP', 'RESOURCE_LOCK', 'ENVIRONMENT_MODIFICATION'):
        strings(value, key)
    elif key in ('TIMEOUT', 'PROCESSORS', 'COST'):
        if (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError(key + ': expected finite nonnegative number')
    elif key in ('WORKING_DIRECTORY', 'REQUIRED_FILES', 'SKIP_RETURN_CODE'):
        if key == 'REQUIRED_FILES':
            strings(value, key)
        elif key == 'SKIP_RETURN_CODE':
            if type(value) is not int:
                raise ValueError(key + ': expected integer')
        elif not isinstance(value, str) or '\x00' in value:
            raise ValueError(key + ': expected string')
    elif key in ('WILL_FAIL', 'RUN_SERIAL', 'DISABLED'):
        enabled_value(value)


def compare(actual, expected):
    if not isinstance(actual, list) or any(not isinstance(n, str) or not n.strip() for n in actual):
        raise ValueError('test names must be a list of nonempty strings')
    counts = Counter(actual)
    missing = sorted(set(expected) - counts.keys())
    extra = sorted(counts.keys() - set(expected))
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    if missing or extra or duplicates:
        raise ValueError(f'registration mismatch: missing={missing}, extra={extra}, duplicates={duplicates}; '
                         'check BUILD_TESTING, full-validation dependencies and optional-tier flags')
    return len(actual)


def expected_names(optional=()):
    path = Path(__file__).with_name('default-tests.json')
    names = strict_loads(path.read_text())
    if len(names) != 31 or len(set(names)) != 31:
        raise ValueError('invalid checked-in default suite: expected 31 unique names')
    additions = {'concurrency-stress': ['concurrency_stress', 'parallel_failure_stress'],
                 'concurrency-extended': ['concurrency_extended', 'parallel_failure_extended'],
                 'system-stress': ['system_stress'], 'system-extended': ['system_extended']}
    for tier in optional:
        names.extend(additions[tier])
    return names


def enabled_value(value):
    """Fail closed on unknown CMake boolean encodings."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)) and value in (0, 1):
        return value == 0
    if isinstance(value, str):
        value = value.upper()
        if value in ('1', 'ON', 'YES', 'TRUE', 'Y'):
            return False
        if value in ('0', 'OFF', 'NO', 'FALSE', 'N', '', 'IGNORE', 'NOTFOUND') or value.endswith('-NOTFOUND'):
            return True
    raise ValueError(f'unsupported DISABLED value: {value!r}')


def registration_names(document):
    if not isinstance(document, dict) or document.get('kind') != 'ctestInfo':
        raise ValueError('expected CTest ctestInfo JSON envelope')
    version = document.get('version')
    if (not isinstance(version, dict) or type(version.get('major')) is not int or
            type(version.get('minor')) is not int or version != {'major': 1, 'minor': 0}):
        raise ValueError('expected CTest JSON version 1.0 metadata')
    tests = document.get('tests')
    if not isinstance(tests, list):
        raise ValueError('CTest tests collection must be a list')
    node_count = metadata(document)
    names = []
    for entry in tests:
        if not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not entry['name'].strip():
            raise ValueError('each CTest entry must be an object with a nonempty string name')
        name = entry['name']
        if 'command' in entry:
            strings(entry['command'], name + '.command', nonempty=True)
            if not entry['command'][0]:
                raise ValueError(name + ': empty command executable')
        if 'backtrace' in entry and (type(entry['backtrace']) is not int or entry['backtrace'] < 0 or
                                     (node_count is not None and entry['backtrace'] >= node_count)):
            raise ValueError(name + ': invalid backtrace index')
        properties = entry.get('properties')
        if not isinstance(properties, list):
            raise ValueError(f'{name}: missing or malformed CTest properties list')
        seen = set()
        for prop in properties:
            if (not isinstance(prop, dict) or not isinstance(prop.get('name'), str) or
                    not prop['name'] or 'value' not in prop):
                raise ValueError(f'{name}: malformed CTest property')
            key = prop['name']
            if key in seen:
                raise ValueError(f'{name}: duplicate property {key}')
            seen.add(key)
            property_metadata(key.upper(), prop['value'])
            if key.upper() == 'DISABLED' and not enabled_value(prop['value']):
                raise ValueError(f'{name}: required test is DISABLED')
        names.append(name)
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--build', type=Path)
    source.add_argument('--names-file', type=Path, help='CMake configure-time name array')
    parser.add_argument('--optional', action='append', default=[], choices=[
        'concurrency-stress', 'concurrency-extended', 'system-stress', 'system-extended'])
    args = parser.parse_args()
    try:
        if args.build:
            command = ['ctest', '--test-dir', str(args.build), '--show-only=json-v1']
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise ValueError(f'{command!r} exited {result.returncode}: {result.stderr}')
            names = registration_names(strict_loads(result.stdout))
        else:
            names = strict_loads(args.names_file.read_text())
        count = compare(names, expected_names(args.optional))
        print(json.dumps(dict(status='complete', count=count, names=sorted(names))))
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as error:
        print(f'CTest registration check failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
