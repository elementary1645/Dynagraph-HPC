"""Focused infrastructure regressions. Retains fixtures; does not add CTest tests."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

from check_execution import validate_report
from check_registration import compare, expected_names, registration_names, strict_loads
from command_receipts import Runner, controlled_environment
from snapshot import compare_inventory, copy_inventory, inventory, validate_paths


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.work = OUTPUT / self.id().split('.')[-1]
        self.work.mkdir()
        self.names = expected_names()

    def registration(self):
        return dict(kind='ctestInfo', version=dict(major=1, minor=0),
                    tests=[dict(name=n, properties=[]) for n in self.names])

    def report(self):
        root = ET.Element('testsuite', name='fixture', tests='31', failures='0', disabled='0',
                          skipped='0', time='1', timestamp='2026-10-28T00:00:00')
        for name in self.names:
            case = ET.SubElement(root, 'testcase', name=name, status='run', time='0.01')
            ET.SubElement(case, 'system-out')
        return root

    def write_report(self, root, label='report'):
        path = self.work / (label + '.xml')
        ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
        return path

    def test_registration_valid_default_optional(self):
        compare(registration_names(self.registration()), self.names)
        optional = expected_names(['concurrency-stress', 'concurrency-extended', 'system-stress', 'system-extended'])
        self.assertEqual(len(optional), 37)
        compare(optional, optional)
        with self.assertRaisesRegex(ValueError, 'extra='):
            compare(optional, self.names)

    def test_registration_structural_rejections(self):
        base = self.registration()
        cases = [('array', [], 'envelope'), ('names-only', {'tests': base['tests']}, 'envelope'),
                 ('null-tests', dict(base, tests=None), 'collection'),
                 ('missing-tests', {k:v for k,v in base.items() if k != 'tests'}, 'collection'),
                 ('missing-version', {k:v for k,v in base.items() if k != 'version'}, 'version'),
                 ('bad-version', dict(base, version={'major':True,'minor':0}), 'version'),
                 ('null-entry', dict(base, tests=[None]), 'entry'),
                 ('empty-name', dict(base, tests=[dict(name='', properties=[])]), 'entry'),
                 ('numeric-name', dict(base, tests=[dict(name=42, properties=[])]), 'entry'),
                 ('missing-properties', dict(base, tests=[dict(name='x')]), 'properties'),
                 ('bad-property', dict(base, tests=[dict(name='x', properties=[{}])]), 'property')]
        for label, doc, error in cases:
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, error):
                registration_names(doc)
        for label, names in [('missing', self.names[:-1]), ('extra', self.names+['extra']),
                             ('duplicate', self.names+[self.names[0]])]:
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, label):
                compare(names, self.names)

    def test_registration_duplicate_json_keys(self):
        for raw in ('{"kind":"wrong","kind":"ctestInfo"}',
                    '{"version":{"major":0,"major":1,"minor":0}}',
                    '{"properties":[{"name":"DISABLED","value":true,"value":false}]}',
                    '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_loads(raw)

    def test_registration_supplied_metadata(self):
        for key, value in (('command', 17), ('command', [17]), ('command', []),
                           ('command', ['']), ('backtrace', True)):
            doc = self.registration()
            doc['tests'][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                registration_names(doc)
        for key, value in (('TIMEOUT', '10'), ('LABELS', 'fast'), ('ENVIRONMENT', [None]),
                           ('PROCESSORS', True), ('WORKING_DIRECTORY', 17)):
            doc = self.registration()
            doc['tests'][0]['properties'] = [dict(name=key, value=value)]
            with self.subTest(key=key), self.assertRaises(ValueError):
                registration_names(doc)
        doc = self.registration()
        doc['backtraceGraph'] = dict(commands=[], files=[], nodes=[dict(file='0')])
        with self.assertRaises(ValueError):
            registration_names(doc)
        # Legitimate pre-build CTest records may omit command/backtrace metadata.
        compare(registration_names(strict_loads(json.dumps(self.registration()))), self.names)

    def test_registration_disabled_representations(self):
        for value in (True, 1, 1.0, 'TRUE', 'On', 'YES', '1', 'Y', ['TRUE'], 2):
            for number in (1, 31):
                with self.subTest(value=value, disabled=number):
                    doc = self.registration()
                    for test in doc['tests'][:number]:
                        test['properties'] = [dict(name='DISABLED', value=value)]
                    with self.assertRaisesRegex(ValueError, 'DISABLED'):
                        registration_names(doc)
        for value in (False, 0, 'OFF', 'FALSE', '0'):
            doc = self.registration()
            doc['tests'][0]['properties'] = [dict(name='DISABLED', value=value)]
            compare(registration_names(doc), self.names)

    def test_execution_positive(self):
        result = validate_report(self.write_report(self.report()), 0, self.names)
        self.assertEqual(result['passed'], 31)

    def test_execution_disabled_skipped_notrun_errors(self):
        for label, status, child in [('disabled', 'disabled', None), ('skipped', 'run', 'skipped'),
                                     ('notrun', 'notrun', None), ('failure', 'run', 'failure'),
                                     ('error', 'run', 'error'), ('missing-status', None, None)]:
            with self.subTest(label=label):
                root = self.report()
                if status is None:
                    del root[0].attrib['status']
                else:
                    root[0].set('status', status)
                if child:
                    ET.SubElement(root[0], child)
                with self.assertRaisesRegex(ValueError, 'status|failure/error/skipped'):
                    validate_report(self.write_report(root, label), 0, self.names)
        root = self.report()
        for case in root:
            case.set('status', 'disabled')
        with self.assertRaisesRegex(ValueError, 'status'):
            validate_report(self.write_report(root, 'all-disabled'), 0, self.names)

    def test_execution_missing_duplicate_extra(self):
        for label in ('missing', 'duplicate', 'extra'):
            with self.subTest(label=label):
                root = self.report()
                if label == 'missing':
                    root.remove(root[0])
                else:
                    new = copy.deepcopy(root[0])
                    if label == 'extra':
                        new.set('name', 'unexpected')
                    root.append(new)
                # Even an exit-zero report whose aggregate matches its records
                # cannot hide a missing expected result.
                root.set('tests', str(len(root)))
                with self.assertRaisesRegex(ValueError, label):
                    validate_report(self.write_report(root, label), 0, self.names)

    def test_execution_schema_security_missing_exit(self):
        good = self.write_report(self.report())
        with self.assertRaisesRegex(ValueError, 'process exit'):
            validate_report(good, 1, self.names)
        with self.assertRaisesRegex(ValueError, 'missing/unreadable'):
            validate_report(self.work/'absent.xml', 0, self.names)
        for i, content in enumerate(('<testsuite', '<testsuite/>', '<testsuites/>',
                                     '<!DOCTYPE x [<!ENTITY x "bad">]><testsuite/>')):
            path = self.work/f'invalid-{i}.xml'
            path.write_text(content)
            with self.subTest(content=content), self.assertRaises(ValueError):
                validate_report(path, 0, self.names)
        for attr, value in [('tests','30'), ('skipped','1'), ('errors','1'), ('time','nan')]:
            root = self.report()
            root.set(attr, value)
            with self.subTest(attr=attr), self.assertRaises(ValueError):
                validate_report(self.write_report(root, attr), 0, self.names)

    def test_overlap_paths(self):
        source = self.work/'source'
        source.mkdir()
        alias = self.work/'alias'
        alias.symlink_to(source, target_is_directory=True)
        for output in (source, source/'output', self.work, alias/'output'):
            with self.subTest(output=str(output)), self.assertRaisesRegex(ValueError, 'disjoint'):
                validate_paths(source, output)
        existing = self.work/'existing'
        existing.mkdir()
        with self.assertRaisesRegex(ValueError, 'preexisting'):
            validate_paths(source, existing)
        validate_paths(source, self.work/'new')

    def test_inventory_types_and_paths(self):
        source, dest = self.work/'source', self.work/'dest'
        source.mkdir(); dest.mkdir()
        file = source/"space apostrophe' Unicode-λ.bin"
        file.write_bytes(bytes(range(256)))
        file.chmod(0o751)
        (source/'link').symlink_to(file.name)
        names = [file.name, 'link', 'tracked-deletion']
        entries = inventory(source, names)
        copy_inventory(source, dest, entries)
        compare_inventory(entries, inventory(dest, names))
        self.assertEqual(entries[file.name]['mode'], 0o751)
        self.assertTrue((dest/'link').is_symlink())
        self.assertEqual(os.readlink(dest/'link'), file.name)
        (dest/file.name).chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'changed='):
            compare_inventory(entries, inventory(dest, names))
        (source/'outside').symlink_to('../../outside')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            inventory(source, ['outside'])
        (source/'absolute').symlink_to(file)
        with self.assertRaisesRegex(ValueError, 'absolute'):
            inventory(source, [file.name, 'absolute'])
        os.mkfifo(source/'fifo')
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            inventory(source, ['fifo'])
        for name in ('../outside', '/absolute', '.git/config'):
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                inventory(source, [name])

    def test_symlink_intermediate_escape(self):
        source, outside = self.work/'source', self.work/'outside'
        source.mkdir(); outside.mkdir()
        (source/'file').write_text('captured')
        (outside/'back').symlink_to('../source/file')
        (source/'bounce').symlink_to('../outside/back')
        with self.assertRaisesRegex(ValueError, 'escapes'):
            inventory(source, ['file','bounce'])
        (source/'directory').symlink_to('../outside', target_is_directory=True)
        (source/'via-directory').symlink_to('directory/back')
        with self.assertRaisesRegex(ValueError, 'symlink directory'):
            inventory(source, ['file','via-directory'])
        # Internal leaf chains remain supported and copied without dereferencing.
        (source/'inner').symlink_to('file')
        (source/'outer').symlink_to('inner')
        entries = inventory(source, ['file','inner','outer'])
        dest = self.work/'destination'
        dest.mkdir()
        copy_inventory(source, dest, entries)
        compare_inventory(entries, inventory(dest, list(entries)))

    def test_inventory_rejects_silent_content_and_type_changes(self):
        source, dest = self.work/'source', self.work/'dest'
        source.mkdir(); dest.mkdir()
        (source/'binary').write_bytes(bytes(range(256)))
        (source/'link').symlink_to('binary')
        entries = inventory(source, ['binary', 'link'])
        copy_inventory(source, dest, entries)
        (dest/'binary').write_bytes(bytes(reversed(range(256))))
        with self.assertRaisesRegex(ValueError, 'changed='):
            compare_inventory(entries, inventory(dest, list(entries)))
        copy_inventory(source, dest, entries)
        (dest/'link').unlink()
        (dest/'link').write_bytes((source/'binary').read_bytes())
        with self.assertRaisesRegex(ValueError, 'changed='):
            compare_inventory(entries, inventory(dest, list(entries)))
        copy_inventory(source, dest, entries)
        (dest/'other').write_bytes((source/'binary').read_bytes())
        (dest/'link').unlink()
        (dest/'link').symlink_to('other')
        with self.assertRaisesRegex(ValueError, 'changed='):
            compare_inventory(entries, inventory(dest, ['binary', 'link', 'other']))

    def test_git_overlay_roundtrip(self):
        runner = Runner(self.work)
        original = Path(__file__).resolve().parents[2]
        source = self.work/"source with apostrophe' and λ"
        dest = self.work/'destination'
        runner.run('clone-source', ['git', 'clone', '--no-hardlinks', '--no-checkout', original, source])
        runner.run('checkout-source', ['git', 'checkout', '--detach', 'a6c6266'], source)
        runner.run('clone-dest', ['git', 'clone', '--no-hardlinks', '--no-checkout', original, dest])
        runner.run('checkout-dest', ['git', 'checkout', '--detach', 'a6c6266'], dest)
        (source/'README.md').write_bytes(b'changed binary\x00\xff\x01')
        (source/'README.md').chmod(0o755)
        (source/'docs/research-log.md').unlink()
        script = source/"new executable' λ"
        script.write_bytes(b'#!/bin/sh\nexit 0\n')
        script.chmod(0o755)
        (source/'new-link').symlink_to(script.name)
        patch = runner.run('diff', ['git','diff','--binary','--no-ext-diff','--no-textconv','a6c6266','--'], source)
        patchfile = self.work/'overlay.patch'
        patchfile.write_bytes(patch)
        runner.run('apply', ['git','apply',patchfile], dest)
        def names(label, root):
            return [n for n in runner.run(label, ['git','ls-files','--cached','--others','--exclude-standard','-z'], root).decode().split('\0') if n]
        entries = inventory(source, names('source-list',source))
        copy_inventory(source, dest, entries)
        compare_inventory(entries, inventory(dest, names('dest-list',dest)))
        self.assertFalse((dest/'docs/research-log.md').exists())
        self.assertEqual((dest/'README.md').read_bytes(), b'changed binary\x00\xff\x01')
        self.assertEqual(entries['README.md']['mode'], 0o755)
        self.assertTrue((dest/'new-link').is_symlink())

    def test_launch_failure_receipt(self):
        runner = Runner(self.work)
        with self.assertRaisesRegex(RuntimeError, 'launch-error'):
            runner.run('absent', [self.work/'does-not-exist'], self.work)
        receipt = json.loads((self.work/'commands.json').read_text())[0]
        self.assertEqual(receipt['classification'], 'launch-error')
        self.assertIsNone(receipt['exit_code'])
        self.assertIn('FileNotFoundError', receipt['error'])
        self.assertLessEqual(receipt['start_unix'], receipt['end_unix'])
        for label, command, cwd, error in (
                ('permission', [self.work/'not-executable'], self.work, 'PermissionError'),
                ('bad-cwd', [sys.executable, '-c', 'pass'], self.work/'absent-cwd', 'FileNotFoundError')):
            (self.work/'not-executable').write_text('not executable')
            (self.work/'not-executable').chmod(0o644)
            with self.subTest(label=label), self.assertRaisesRegex(RuntimeError, 'launch-error'):
                runner.run(label, command, cwd)
            receipt = json.loads((self.work/'commands.json').read_text())[-1]
            self.assertIsNone(receipt['exit_code'])
            self.assertEqual(receipt['classification'], 'launch-error')
            self.assertIn(error, receipt['error'])

    def test_environment_policy(self):
        from unittest.mock import patch
        incoming = dict(PYTHONPATH='sensitive-value', PYTHONHOME='bad', CFLAGS='-bad',
                        CXXFLAGS='-bad', LDFLAGS='-bad', CMAKE_PREFIX_PATH='bad',
                        OMP_NUM_THREADS='999', ASAN_OPTIONS='detect_leaks=0', CC='bad', CXX='bad')
        with patch.dict(os.environ, incoming):
            env, policy = controlled_environment(self.work)
        for name in incoming:
            self.assertNotIn(name, env)
        self.assertNotIn('sensitive-value', json.dumps(policy))
        self.assertEqual(env['MPLCONFIGDIR'], str(self.work/'mpl-cache'))

    def test_real_ctest_disabled_and_skip(self):
        runner = Runner(self.work)
        fixture = self.work/'ctest'
        fixture.mkdir()
        lines = [f'add_test({n} "{sys.executable}" "-c" "pass")' for n in self.names]
        for label, property_line, disabled in [
                ('valid', '', False),
                ('one-disabled', f'set_tests_properties({self.names[0]} PROPERTIES DISABLED TRUE)', True),
                ('all-disabled', f'set_tests_properties({" ".join(self.names)} PROPERTIES DISABLED TRUE)', True),
                ('skipped', f'set_tests_properties({self.names[0]} PROPERTIES SKIP_RETURN_CODE 0)', False)]:
            (fixture/'CTestTestfile.cmake').write_text('\n'.join(lines+[property_line])+'\n')
            raw = runner.run(label+'-names', ['ctest','--test-dir',fixture,'--show-only=json-v1'])
            if disabled:
                with self.assertRaisesRegex(ValueError, 'DISABLED'):
                    registration_names(strict_loads(raw))
            else:
                compare(registration_names(strict_loads(raw)), self.names)
            report = self.work/(label+'.xml')
            runner.run(label, ['ctest','--test-dir',fixture,'--parallel','1','--output-junit',report])
            if label == 'valid':
                self.assertEqual(validate_report(report, 0, self.names)['passed'],31)
            else:
                with self.assertRaisesRegex(ValueError, 'disabled/skipped'):
                    validate_report(report, 0, self.names)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    OUTPUT = args.output.resolve()
    OUTPUT.mkdir(parents=True, exist_ok=False)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RepairTests)
    with (OUTPUT/'unittest.log').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    print((OUTPUT/'unittest.log').read_text())
    (OUTPUT/'summary.json').write_text(json.dumps(dict(tests=result.testsRun, failures=len(result.failures),
                                                      errors=len(result.errors)), indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
