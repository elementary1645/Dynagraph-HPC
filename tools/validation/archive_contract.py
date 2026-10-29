"""Versioned evidence contracts independent of the producer's file inventories."""
import json
import math
from pathlib import PurePosixPath
import re

from archive_transport import file_inventory, safe_name, sha
from check_execution import validate_report
from check_registration import compare, expected_names, registration_names, strict_loads
from pipeline_artifacts import verify_analysis, verify_hashes
from snapshot import inventory_hash
from test_smoke import DIAGNOSTICS, require_rejection

PROFILES = {'debug-full-v1': ('debug', False), 'release-smoke-v1': ('release', True),
            'sanitize-full-v1': ('sanitize', False)}
FAILED = 'failed-run-v1'
BASE_STAGES = ('revision', 'status', 'source-files', 'environment', 'cmake-version',
               'ctest-version', 'g++-version', 'configure', 'registration', 'build', 'ctest')
PIPELINE_STAGES = ('revision', 'status', 'source-files', 'environment', 'cmake-version',
                   'g++-version', 'generate', 'verify-workload', 'full-trace-run',
                   'full-trace-validate', 'per-update-run', 'per-update-validate',
                   'analyze', 'source-files-final')
CLI_CONTROLS = ('tampered-workload', 'incorrect-manifest-hash', 'incomplete-replay',
                'missing-timing', 'invalid-dataset')
MODES = ('full-trace', 'per-update')
POLICIES = ('dijkstra', 'delta-stepping', 'incremental', 'heuristic')
JSON_LIMIT = 16 * 1024 * 1024
# Last whole Unix second representable in UTC year 9999; also caps recorded durations.
MAX_RECEIPT_SECONDS = 253402300799


def require_files(root, names):
    for name in names:
        safe_name(name)
        path = root/name
        if not path.is_file() or path.is_symlink():
            raise ValueError('missing mandatory evidence: ' + name)


def load(root, name, kind=dict):
    require_files(root, [name])
    path = root/name
    if path.stat().st_size > JSON_LIMIT:
        raise ValueError('JSON evidence size limit exceeded: ' + name)
    try:
        value = strict_loads(path.read_bytes())
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('malformed JSON evidence: ' + name) from error
    if not isinstance(value, kind):
        raise ValueError('invalid JSON evidence root: ' + name)
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            raise ValueError('JSON evidence nesting limit exceeded: ' + name)
        if isinstance(item, dict):
            pending.extend((v, depth+1) for v in item.values())
        elif isinstance(item, list):
            pending.extend((v, depth+1) for v in item)
    return value


def digest_inventory(root, recursive=False):
    doc = load(root, 'evidence-sha256.json')
    actual = file_inventory(root)
    if not recursive:
        actual = {n:e for n,e in actual.items() if '/' not in n}
    actual.pop('evidence-sha256.json', None)
    if set(doc) != set(actual):
        raise ValueError('incomplete evidence hash inventory')
    verify_hashes(root, doc)


def policy(root):
    value = load(root, 'environment-policy.json')
    if (not isinstance(value.get('removed_variable_names'), list) or
            any(not isinstance(n, str) for n in value['removed_variable_names']) or
            not isinstance(value.get('policy'), str) or not value['policy'] or
            not isinstance(value.get('overrides'), dict) or
            not isinstance(value.get('inherited_sha256'), dict)):
        raise ValueError('invalid environment policy')
    overrides = value['overrides']
    for key, wanted in dict(PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0',
                            PYTHONNOUSERSITE='1', MPLBACKEND='Agg', LC_ALL='C.UTF-8',
                            TZ='UTC', GIT_OPTIONAL_LOCKS='0').items():
        if overrides.get(key) != wanted:
            raise ValueError('environment policy override mismatch: ' + key)
    for key in ('MPLCONFIGDIR', 'TMPDIR'):
        if not isinstance(overrides.get(key), str) or not overrides[key]:
            raise ValueError('environment policy missing local paths')
    if set(value['inherited_sha256']) != {'PATH', 'HOME'} or any(
            not isinstance(v, str) or re.fullmatch('[0-9a-f]{64}', v) is None
            for v in value['inherited_sha256'].values()):
        raise ValueError('invalid inherited environment hashes')


def receipt_time(value, name, key):
    """No int-to-float conversion: arbitrary-size JSON integers are compared safely."""
    label = name + '.' + key
    if type(value) not in (int, float):
        raise ValueError('invalid command receipt time type: ' + label)
    if type(value) is float and not math.isfinite(value):
        raise ValueError('nonfinite command receipt time: ' + label)
    if not 0 <= value <= MAX_RECEIPT_SECONDS:
        raise ValueError('command receipt time out of range: ' + label)


def receipts(root, expected=None, successful=True):
    rows = load(root, 'commands.json', list)
    if not rows:
        raise ValueError('missing command receipts')
    names, result, previous = [], {}, 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid command receipt')
        required = {'name','command','cwd','environment','start_unix','end_unix','wall_seconds',
                    'classification','exit_code','error','log','log_sha256'}
        if not required <= row.keys() or (row['error'] is not None and not isinstance(row['error'], str)):
            raise ValueError('incomplete command receipt schema')
        name = row.get('name')
        if not isinstance(name, str) or not name or name in result:
            raise ValueError('invalid/duplicate command receipt name')
        if row.get('log') != name+'.log':
            raise ValueError('command receipt log/name mismatch')
        safe_name(row['log']); require_files(root, [row['log']])
        if sha(root/row['log']) != row.get('log_sha256'):
            raise ValueError('command log digest mismatch: ' + name)
        command = row.get('command')
        if (not isinstance(command, list) or not command or
                any(not isinstance(v, str) or '\0' in v for v in command) or not command[0] or
                not isinstance(row.get('cwd'), str) or not isinstance(row.get('environment'), dict)):
            raise ValueError('invalid command receipt argv/cwd/environment: ' + name)
        for key in ('start_unix', 'end_unix', 'wall_seconds'):
            receipt_time(row.get(key), name, key)
        if row['start_unix'] < previous or row['end_unix'] < row['start_unix']:
            raise ValueError('nonsequential command receipts: ' + name)
        previous = row['end_unix']
        classification, code = row.get('classification'), row.get('exit_code')
        if (classification not in ('exited', 'launch-error', 'timeout') or
                (classification == 'launch-error' and code is not None) or
                (classification != 'launch-error' and type(code) is not int) or
                (classification == 'launch-error' and not row['error']) or
                (classification == 'timeout' and (code != 124 or not row['error']))):
            raise ValueError('invalid command receipt classification: ' + name)
        if successful and (classification != 'exited' or code != 0 or row.get('error') is not None):
            raise ValueError('unsuccessful stage receipt: ' + name)
        names.append(name); result[name] = row
    if expected is not None and names != list(expected):
        raise ValueError('mandatory stage receipts mismatch: missing=' + str(sorted(set(expected)-set(names))) +
                         ', unexpected/order=' + str(names))
    return result


def source_identity(root, source):
    identity = load(root, 'source-identity.json')
    entries = identity.get('inventory')
    if (not isinstance(entries, dict) or not entries or
            not isinstance(identity.get('git_revision'), str) or
            re.fullmatch('[0-9a-f]{40}', identity['git_revision']) is None or
            type(identity.get('dirty')) is not bool or not isinstance(identity.get('git_status'), str) or
            identity['dirty'] != bool(identity['git_status']) or
            identity.get('inventory_sha256') != inventory_hash(entries)):
        raise ValueError('source identity mismatch')
    actual = file_inventory(source)
    wanted = {}
    for name, entry in entries.items():
        safe_name(name)
        if (not isinstance(entry, dict) or entry.get('type') != 'file' or
                type(entry.get('mode')) is not int or not 0 <= entry['mode'] <= 0o777):
            raise ValueError('unsupported source identity type/mode')
        wanted[name] = dict(type='file', mode=actual.get(name, {}).get('mode'),
                            sha256=actual.get(name, {}).get('sha256'))
    if set(actual) != set(entries) or entries != wanted:
        raise ValueError('source inventory mismatch')
    require_files(root, ['revision.log', 'status.log', 'source-files.log'])
    if ((root/'revision.log').read_text().strip() != identity['git_revision'] or
            (root/'status.log').read_text() != identity['git_status']):
        raise ValueError('source identity contradicts Git receipts')
    for name in ('source-files.log', 'source-files-final.log'):
        if not (root/name).exists():
            continue  # The latter is not attempted in supported failed-run prefixes.
        raw = (root/name).read_bytes()
        try:
            names = raw.decode('utf-8').split('\0')
        except UnicodeError as error:
            raise ValueError('invalid source file-list encoding') from error
        if not names or names.pop() != '' or len(names) != len(set(names)):
            raise ValueError('invalid source file-list receipt')
        # Tracked deletions are still returned by ls-files; require explicit D status.
        missing = set(names)-set(entries)
        for deleted in missing:
            if not any(len(line) >= 4 and 'D' in line[:2] and line[3:] == deleted
                       for line in identity['git_status'].splitlines()):
                raise ValueError('source file-list inventory mismatch')
        if set(entries)-set(names):
            raise ValueError('source file-list inventory mismatch')
    return identity


def environment(root, source):
    value = load(root, 'environment.log')
    if value.get('renderer') != 'Agg: initialized and rendered' or not isinstance(value.get('python'), str):
        raise ValueError('invalid environment gate result')
    require_files(source, ['benchmarks/requirements-analysis.txt'])
    pins = {}
    for line in (source/'benchmarks/requirements-analysis.txt').read_text().splitlines():
        if line and not line.startswith('#'):
            key, wanted = line.split('==')
            pins[key] = wanted
    if not pins or value.get('dependencies') != pins:
        raise ValueError('pinned environment evidence mismatch')


def recorded_absolute_path(value):
    """Lexical POSIX validation only; never follow historical paths or venv links."""
    if not isinstance(value, str) or not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return False
    path = PurePosixPath(value)
    return (path.is_absolute() and not value.startswith('//') and
            path.as_posix() == value and '..' not in path.parts)


def configuration(row, mode):
    """Accept precisely ci_verify.py's canonical argv, not general CMake syntax."""
    command = row.get('command') if isinstance(row, dict) else None
    if (not isinstance(command, list) or any(not isinstance(a, str) or not a or
            any(ord(c) < 32 or ord(c) == 127 for c in a) for a in command)):
        raise ValueError('invalid canonical configure argv')
    if mode not in ('debug', 'release', 'sanitize'):
        raise ValueError('unsupported configure profile')
    if (len(command) < 7 or command[0] != 'cmake' or command[1] != '-S' or
            command[3] != '-B' or command[5:7] != ['-G', 'Unix Makefiles']):
        raise ValueError('noncanonical configure command prefix')
    if (not recorded_absolute_path(command[2]) or not recorded_absolute_path(command[4]) or
            command[2] == command[4]):
        raise ValueError('invalid canonical configure source/build path')
    if row.get('cwd') != command[2]:
        raise ValueError('configure source/cwd mismatch')
    required = [
        ('CMAKE_CXX_COMPILER', 'g++'),
        ('CMAKE_BUILD_TYPE', 'Release' if mode == 'release' else 'Debug'),
        ('BUILD_TESTING', 'ON'),
        ('DYNAGRAPH_WARNINGS_AS_ERRORS', 'ON'),
        ('DYNAGRAPH_FULL_VALIDATION', 'ON'),
        ('DYNAGRAPH_ANALYSIS_PYTHON', None),
    ]
    if mode == 'sanitize':
        required += [('CMAKE_CXX_FLAGS', '-fsanitize=address,undefined -fno-omit-frame-pointer'),
                     ('CMAKE_EXE_LINKER_FLAGS', '-fsanitize=address,undefined')]
    allowed = dict(required)
    flags = {}
    tail = command[7:]
    for index, arg in enumerate(tail):
        if arg == '-D':
            if index+1 == len(tail) or tail[index+1].startswith('-'):
                raise ValueError('missing value after configure -D')
            raise ValueError('split configure definitions are unsupported')
        if not arg.startswith('-D'):
            raise ValueError('unsupported configure argument: ' + arg)
        match = re.fullmatch(r'-D([A-Z][A-Z0-9_]*)=(.*)', arg)
        if match is None:
            raise ValueError('unsupported configure definition syntax: ' + arg)
        key, value = match.groups()
        if key in flags:
            raise ValueError('duplicate configure setting: ' + key)
        if key not in allowed:
            raise ValueError('unsupported configure setting: ' + key)
        flags[key] = value
    missing = set(allowed)-set(flags)
    if missing:
        raise ValueError('missing canonical configure settings: ' + str(sorted(missing)))
    for key, wanted in required:
        if key == 'DYNAGRAPH_ANALYSIS_PYTHON':
            if not recorded_absolute_path(flags[key]):
                raise ValueError('invalid canonical analysis Python path')
        elif flags[key] != wanted:
            raise ValueError('validation mode contradicts configure receipt: ' + key)
    if list(flags) != [key for key, _ in required]:
        raise ValueError('noncanonical configure definition order')


def validate_pipeline(root, identity):
    require_files(root, ['pipeline-result.json', 'analysis-plan.json', 'source-identity.json',
                         'commands.json', 'environment-policy.json', 'evidence-sha256.json',
                         'bundle/manifest.json', 'bundle/graph.txt', 'bundle/trace.txt',
                         'analysis/analysis-manifest.json', 'analysis/acceptance.jsonl'])
    for mode in MODES:
        require_files(root, [mode+'/records.jsonl', mode+'/runner', mode+'/artifact-verification.json',
                             mode+'.json'] + [mode+'/workload/'+n for n in ('manifest.json','graph.txt','trace.txt')])
        for stem in ['preflight-'+p for p in POLICIES] + ['trial-'+str(i) for i in range(16)]:
            require_files(root, [mode+'/'+stem+suffix for suffix in ('.stdout','.stderr','.exit.json')])
    p = load(root, 'pipeline-result.json')
    if (p.get('status') != 'complete' or p.get('source_unchanged') is not True or
            p.get('timing_modes') != list(MODES) or type(p.get('trials_per_mode')) is not int or
            p['trials_per_mode'] != 16 or p.get('figures') != 14 or
            p.get('evidence_class') != 'valid_harness_only' or p.get('producer_authentication') is not False):
        raise ValueError('incomplete/conflicting smoke result')
    if load(root, 'source-identity.json') != identity:
        raise ValueError('pipeline source identity mismatch')
    if not isinstance(p.get('dataset_sha256'), dict) or set(p['dataset_sha256']) != set(MODES):
        raise ValueError('mandatory dataset hash keys mismatch')
    if not isinstance(p.get('workload_sha256'), dict) or set(p['workload_sha256']) != {'manifest.json','graph.txt','trace.txt'}:
        raise ValueError('mandatory workload hash keys mismatch')
    policy(root)
    rows = receipts(root, PIPELINE_STAGES)
    digest_inventory(root, recursive=True)
    workload = load(root/'bundle', 'manifest.json')
    if workload.get('counts') != dict(vertices=8, edges=7, updates=12) or p.get('workload') != workload['counts']:
        raise ValueError('unsupported smoke workload bounds')
    recipe = workload.get('configuration')
    if (not isinstance(recipe, dict) or recipe.get('graph') != {'family':'chain', 'vertices':8} or
            recipe.get('source') != {'kind':'explicit', 'vertex':0} or
            recipe.get('weights') != {'kind':'positive_uniform', 'min':16, 'max':32} or
            recipe.get('trace') != {'count':12, 'schedule':['strict','repeat','equal'], 'max_decrement':2}):
        raise ValueError('unsupported smoke workload recipe bounds')
    verification = load(root, 'verify-workload.log')
    if verification.get('status') != 'verified' or verification.get('counts') != workload['counts']:
        raise ValueError('incomplete replay verification evidence')
    verify_hashes(root/'bundle', p['workload_sha256'])
    # Reuse the established pure-Python validators, not claims in summary manifests.
    from experiment_records import validate_dataset, read_jsonl
    for mode in MODES:
        path = root/mode/'records.jsonl'
        if path.stat().st_size > JSON_LIMIT:
            raise ValueError('smoke dataset size limit exceeded')
        verify_hashes(root/mode/'workload', p['workload_sha256'])
        verify_hashes(root/mode, {'records.jsonl': p['dataset_sha256'][mode]})
        if sha(root/mode/'runner') != p.get('executable_sha256') or not ((root/mode/'runner').stat().st_mode & 0o111):
            raise ValueError('smoke executable identity/mode mismatch')
        result = validate_dataset(path)
        first = read_jsonl(path.read_bytes())[0]
        if first['configuration']['timing_mode'] != mode or first['executable_sha256'] != p['executable_sha256']:
            raise ValueError('smoke dataset identity mismatch')
        if result != dict(schema_version=1, status='complete', trials='16') or load(root, mode+'-validate.log') != result:
            raise ValueError('incomplete dataset validation receipt')
    manifest = load(root/'analysis', 'analysis-manifest.json')
    load(root/'analysis', 'summaries.json')
    generation = manifest.get('figure_generation')
    if (not isinstance(manifest.get('output_sha256'), dict) or
            not isinstance(generation, dict) or not isinstance(generation.get('products'), list) or
            any(not isinstance(p, dict) or any(not isinstance(p.get(k), str) for k in ('path','sha256','figure_type'))
                for p in generation['products'])):
        raise ValueError('invalid analysis manifest structure')
    analysis = verify_analysis(root/'analysis')
    if analysis['figures'] != 14:
        raise ValueError('required figure inventory mismatch')
    manifest = load(root/'analysis', 'analysis-manifest.json')
    if manifest.get('analysis_plan_sha256') != sha(root/'analysis-plan.json'):
        raise ValueError('analysis plan identity mismatch')
    path = root/'analysis/acceptance.jsonl'
    if path.stat().st_size > JSON_LIMIT:
        raise ValueError('analysis acceptance size limit exceeded')
    accepted = [strict_loads(line) for line in path.read_bytes().splitlines()]
    if (len(accepted) != 2 or any(not isinstance(a, dict) for a in accepted) or
            any(not isinstance(a.get('input_id'), str) for a in accepted) or
            {a.get('input_id') for a in accepted} != set(MODES)):
        raise ValueError('required analysis acceptance inventory mismatch')
    for a in accepted:
        mode = a['input_id']
        actual = {n:d['sha256'] for n,d in file_inventory(root/mode).items()}
        if (a.get('accepted') is not True or a.get('structurally_valid') is not True or
                a.get('classification') != 'valid_harness_only' or a.get('path') != mode or
                a.get('inventory') != actual):
            raise ValueError('analysis input acceptance mismatch: ' + mode)
    return rows


def validate_negative(root):
    policy(root)
    rows = receipts(root, CLI_CONTROLS, successful=False)
    controls = load(root, 'negative-results.json', list)
    if (len(controls) != 9 or any(not isinstance(c, dict) for c in controls) or
            any(not isinstance(c.get('case'), str) for c in controls) or
            {c.get('case') for c in controls} != set(DIAGNOSTICS) or
            any(c.get('rejected') is not True or not c.get('diagnostic') for c in controls)):
        raise ValueError('incomplete intended negative diagnostics')
    for label, expected in DIAGNOSTICS.items():
        require_files(root, [label+'.log'])
        diagnostic = (root/(label+'.log')).read_text()
        if label in CLI_CONTROLS:
            require_rejection(rows[label], diagnostic, expected)
        elif expected not in diagnostic:
            raise ValueError('incorrect intended artifact diagnostic: ' + label)


def validate_evidence(root, source, profile):
    if profile not in (*PROFILES, FAILED):
        raise ValueError('unsupported archive profile')
    require_files(root, ['source-identity.json', 'environment-policy.json', 'commands.json', 'evidence-sha256.json'])
    policy(root)
    identity = source_identity(root, source)
    if profile == FAILED:
        failure = load(root, 'failure.json')
        if (failure.get('status') != 'failed' or failure.get('classification') not in
                ('command-failed', 'validation-rejected', 'interrupted') or
                not isinstance(failure.get('error'), str) or not failure['error'].strip()):
            raise ValueError('invalid explicit failed-run classification')
        rows = receipts(root, successful=False)
        names = list(rows)
        allowed = list(BASE_STAGES)+['source-files-final']
        release_allowed = list(BASE_STAGES)+['pipeline','pipeline-negative','source-files-final']
        if names != allowed[:len(names)] and names != release_allowed[:len(names)]:
            raise ValueError('failed-run stage prefix mismatch')
        if failure['classification'] == 'command-failed' and not any(
                r['classification'] != 'exited' or r['exit_code'] != 0 for r in rows.values()):
            raise ValueError('failed-run classification lacks failed receipt')
        if (root/'result.json').exists() and load(root, 'result.json').get('status') == 'complete':
            raise ValueError('conflicting success marker in failed-run evidence')
        for row in list(rows.values())[:-1]:
            if row['classification'] != 'exited' or row['exit_code'] != 0 or row['error'] is not None:
                raise ValueError('failed-run receipt progression contradicts stop-on-failure')
        if (root/'pipeline/pipeline-result.json').exists():
            nested = load(root, 'pipeline/pipeline-result.json')
            parent = rows.get('pipeline', {})
            if nested.get('status') == 'complete' and (parent.get('classification') != 'exited' or parent.get('exit_code') != 0):
                raise ValueError('conflicting completed pipeline in failed-run evidence')
        digest_inventory(root)
        return dict(status='integrity-verified', validation_status='failed', profile=profile,
                    failure_classification=failure['classification'], source_inventory_sha256=identity['inventory_sha256'])
    # Failure markers anywhere in success evidence are contradictory, including nested stages.
    if any(root.rglob('failure.json')):
        raise ValueError('conflicting failure marker in successful evidence')
    mode, smoke = PROFILES[profile]
    require_files(root, ['result.json', 'execution.xml', 'acceptance.json'])
    result = load(root, 'result.json')
    if (result.get('status') != 'complete' or result.get('source_unchanged') is not True or
            result.get('mode') != mode or result.get('smoke') is not smoke or
            type(result.get('passed')) is not int or result['passed'] != 31):
        raise ValueError('validation result/profile mismatch')
    if not smoke and ((root/'pipeline').exists() or (root/'pipeline-negative').exists()):
        raise ValueError('unexpected smoke evidence in non-smoke profile')
    stages = list(BASE_STAGES) + (['pipeline','pipeline-negative'] if smoke else []) + ['source-files-final']
    rows = receipts(root, stages)
    environment(root, source)
    configuration(rows['configure'], mode)
    compare(registration_names(load(root, 'registration.log')), expected_names())
    accepted = validate_report(root/'execution.xml', rows['ctest']['exit_code'], expected_names())
    if accepted != load(root, 'acceptance.json'):
        raise ValueError('mandatory test acceptance mismatch')
    if mode == 'sanitize':
        settings = rows['ctest']['environment']
        if (settings.get('ASAN_OPTIONS') != 'detect_leaks=1:halt_on_error=1' or
                settings.get('UBSAN_OPTIONS') != 'halt_on_error=1:print_stacktrace=1'):
            raise ValueError('missing sanitizer acceptance options')
    if smoke:
        validate_pipeline(root/'pipeline', identity)
        validate_negative(root/'pipeline-negative')
    digest_inventory(root)
    return dict(status='verified', validation_status='passed', profile=profile, mode=mode,
                passed=accepted['passed'], smoke=smoke,
                source_inventory_sha256=identity['inventory_sha256'])
