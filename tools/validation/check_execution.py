"""Strict acceptance of CTest --output-junit (CTest 3.28 schema demonstrated)."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from check_registration import compare, expected_names


def duration(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{label}: missing or invalid time') from error
    if not math.isfinite(number) or number < 0:
        raise ValueError(f'{label}: invalid time {value!r}')
    return number


def validate_report(path, exit_code, expected):
    if exit_code != 0:
        raise ValueError(f'CTest process exit {exit_code}; cannot accept execution')
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ValueError(f'missing/unreadable execution report {path}: {error}') from error
    # CTest emits UTF-8 XML without declarations/entities. Restrict that format
    # before ElementTree parsing; never process DTDs or external/internal entities.
    if b'\x00' in raw or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('execution report contains forbidden XML DTD/entity or non-UTF-8 encoding')
    try:
        root = ET.fromstring(raw.decode('utf-8'))
    except (ET.ParseError, UnicodeError) as error:
        raise ValueError(f'malformed execution XML: {error}') from error
    if root.tag != 'testsuite':
        raise ValueError('expected a CTest testsuite root')
    counts = {}
    for key in ('tests', 'failures', 'disabled', 'skipped'):
        value = root.get(key)
        if value is None or not value.isascii() or not value.isdecimal():
            raise ValueError(f'execution report missing/invalid {key} count')
        counts[key] = int(value)
    if root.get('errors', '0') != '0' or any(counts[k] for k in ('failures', 'disabled', 'skipped')):
        raise ValueError(f'execution report has failures/errors/disabled/skipped: {counts}')
    duration(root.get('time'), 'suite')
    if not root.get('name') or not root.get('timestamp'):
        raise ValueError('execution report missing suite name/timestamp')
    results = []
    for case in root:
        if case.tag != 'testcase':
            raise ValueError(f'unexpected execution element: {case.tag}')
        name = case.get('name')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('execution testcase missing nonempty name')
        if case.get('status') != 'run':
            raise ValueError(f'{name}: expected executed status run, found {case.get("status")!r}')
        tags = [child.tag for child in case]
        if any(tag not in ('properties', 'system-out') for tag in tags):
            raise ValueError(f'{name}: failure/error/skipped or unknown testcase element {tags}')
        if tags.count('system-out') != 1 or tags.count('properties') > 1:
            raise ValueError(f'{name}: incomplete/duplicate testcase output metadata')
        results.append({'name': name, 'seconds': duration(case.get('time'), name), 'status': 'passed'})
    compare([r['name'] for r in results], expected)
    if counts['tests'] != len(results):
        raise ValueError('execution tests count disagrees with testcase records')
    return {'passed': len(results), 'results': results, 'report_sha256': hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--exit-code', required=True, type=int)
    parser.add_argument('--optional', action='append', default=[], choices=[
        'concurrency-stress', 'concurrency-extended', 'system-stress', 'system-extended'])
    args = parser.parse_args()
    try:
        print(json.dumps(validate_report(args.report, args.exit_code, expected_names(args.optional))))
    except ValueError as error:
        print(f'CTest execution acceptance failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
