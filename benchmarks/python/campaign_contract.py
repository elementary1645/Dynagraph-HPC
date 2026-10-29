"""Campaign v1: strict, bounded planning only; never launches a benchmark."""
import hashlib
import json
import re
from pathlib import PurePosixPath

from deterministic import SplitMix64, UINT64_MAX
from experiment_records import POLICIES, schedule
from workloads import canonical_json, integer, object_fields, validate_spec

MAX_INPUT = 1024 * 1024
MAX_TRIALS = 100000
MAX_NODES = 50000
EVIDENCE = ['plan.json', 'trial-manifest.json', 'hardware.json', 'admission.json',
            'records.jsonl', 'stdout', 'stderr', 'exit.json', 'sha256.json']


def fields(value, names, label):
    object_fields(value, names.split(), label)


def label(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', value) is None:
        raise ValueError('invalid campaign label')
    return value


def digest(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('invalid SHA-256 identity')


def safe_path(value):
    if (type(value) is not str or not value or len(value) > 512 or
            any(ord(c) < 32 or ord(c) == 127 for c in value) or
            '\\' in value or ':' in value or PurePosixPath(value).is_absolute() or
            PurePosixPath(value).as_posix() != value or
            any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError('unsafe campaign relative path')


def load_bytes(data):
    if len(data) > MAX_INPUT:
        raise ValueError('campaign input size limit')
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError('duplicate campaign JSON key: ' + k)
            out[k] = v
        return out
    def invalid(value):
        raise ValueError('nonfinite campaign JSON number: ' + value)
    try:
        value = json.loads(data, object_pairs_hook=unique, parse_constant=invalid,
                           parse_float=invalid)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError('malformed campaign JSON') from error
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > 32 or nodes > MAX_NODES:
            raise ValueError('campaign JSON structure limit')
        if type(item) is dict:
            pending.extend((v, depth+1) for v in item.values())
        elif type(item) is list:
            pending.extend((v, depth+1) for v in item)
    return value


def read_json(path):
    with open(path, 'rb') as stream:
        return load_bytes(stream.read(MAX_INPUT+1))


def plan_hash(plan):
    return hashlib.sha256(canonical_json(validate_plan(plan))).hexdigest()


def bounded_list(value, maximum, name):
    if type(value) is not list or not 1 <= len(value) <= maximum:
        raise ValueError(name + ': bounded nonempty array required')


def boolean(value):
    if type(value) is not bool:
        raise ValueError('boolean required')


def validate_plan(p):
    fields(p, 'schema_version campaign_id panel measurement_level timing_mode workloads configurations '
           'policies no_effect heuristic sessions blocks warmups diagnostics order_seed order_version '
           'build hardware limits expected_evidence comparisons', 'campaign')
    integer(p['schema_version'], 1, 1, 'campaign schema version')
    label(p['campaign_id']); label(p['panel'])
    if p['measurement_level'] != 'engine-update-service-v1' or p['timing_mode'] not in ('full-trace', 'per-update'):
        raise ValueError('unsupported campaign measurement level/mode')
    if p['policies'] != list(POLICIES):
        raise ValueError('v1 requires the four canonical policies in order')
    if p['no_effect'] not in ('shared_fast_path', 'execute_selected'):
        raise ValueError('unsupported no-effect mode')
    if p['heuristic'] != {'small_graph_edges':4096, 'repair_max_degree':32, 'parallel_min_edges':65536} or any(
            type(v) is not int for v in p['heuristic'].values()):
        raise ValueError('v1 requires unchanged heuristic thresholds')
    bounded_list(p['workloads'], 128, 'workloads')
    bounded_list(p['configurations'], 64, 'configurations')
    bounded_list(p['sessions'], 32, 'sessions')
    workload_ids, content_ids = set(), set()
    for w in p['workloads']:
        fields(w, 'id recipe recipe_sha256 graph_sha256 trace_sha256 bundle', 'campaign workload')
        label(w['id']); safe_path(w['bundle']); validate_spec(w['recipe'])
        if w['id'] != w['recipe']['workload_id'] or w['recipe']['trace']['count'] == 0:
            raise ValueError('workload identity mismatch or empty trace')
        for key in ('recipe_sha256', 'graph_sha256', 'trace_sha256'):
            digest(w[key])
        if w['recipe_sha256'] != hashlib.sha256(canonical_json(w['recipe'])).hexdigest():
            raise ValueError('recipe hash mismatch')
        identity = (w['graph_sha256'], w['trace_sha256'])
        if w['id'] in workload_ids or identity in content_ids:
            raise ValueError('duplicate workload identity')
        workload_ids.add(w['id']); content_ids.add(identity)
    configs, settings = {}, set()
    for c in p['configurations']:
        fields(c, 'id workers delta', 'campaign configuration'); label(c['id'])
        integer(c['workers'], 1, 64, 'requested workers')
        integer(c['delta'], 1, UINT64_MAX, 'delta')
        key = (c['workers'], c['delta'])
        if c['id'] in configs or key in settings:
            raise ValueError('duplicate configuration identity')
        configs[c['id']] = c; settings.add(key)
    if any(type(s) is not str for s in p['sessions']):
        raise ValueError('invalid session')
    for s in p['sessions']: label(s)
    if len(set(p['sessions'])) != len(p['sessions']):
        raise ValueError('duplicate session')
    integer(p['blocks'], 4, 400, 'blocks')
    if p['blocks'] % 4:
        raise ValueError('blocks must be divisible by four')
    integer(p['warmups'], 0, 100, 'warmups')
    integer(p['diagnostics'], 0, 1, 'diagnostics per policy')
    integer(p['order_seed'], 0, UINT64_MAX, 'order seed')
    if p['order_version'] != 'campaign-balanced-four-v1':
        raise ValueError('unsupported campaign order version')
    b = p['build']
    fields(b, 'revision build_type executable executable_sha256 compiler_sha256 openmp_sha256 '
           'flags_sha256 uninstrumented', 'build requirements')
    if type(b['revision']) is not str or re.fullmatch('[0-9a-f]{40}', b['revision']) is None:
        raise ValueError('invalid build revision')
    if b['build_type'] != 'Release' or b['uninstrumented'] is not True:
        raise ValueError('Release uninstrumented build required')
    safe_path(b['executable'])
    for key in ('executable_sha256', 'compiler_sha256', 'openmp_sha256', 'flags_sha256'): digest(b[key])
    h = p['hardware']
    fields(h, 'mode allocated_cpus min_physical_cores allow_smt allow_virtualization '
           'min_available_memory_bytes require_frequency_evidence exclusive reservation', 'hardware requirements')
    if h['mode'] not in ('development', 'scientific'):
        raise ValueError('unsupported admission mode')
    bounded_list(h['allocated_cpus'], 256, 'allocated CPUs')
    for cpu in h['allocated_cpus']: integer(cpu, 0, 1048575, 'CPU ID')
    if h['allocated_cpus'] != sorted(set(h['allocated_cpus'])):
        raise ValueError('CPU allocation must be sorted and unique')
    integer(h['min_physical_cores'], 1, 64, 'physical core minimum')
    integer(h['min_available_memory_bytes'], 1, 1 << 50, 'memory minimum')
    for k in ('allow_smt', 'allow_virtualization', 'require_frequency_evidence', 'exclusive'): boolean(h[k])
    if type(h['reservation']) is not str or len(h['reservation']) > 1024 or any(ord(c) < 32 or ord(c) == 127 for c in h['reservation']):
        raise ValueError('invalid reservation declaration')
    if h['mode'] == 'scientific' and (not h['exclusive'] or not h['reservation'].strip()):
        raise ValueError('scientific mode requires an explicit exclusive reservation declaration')
    if h['mode'] == 'development' and (h['exclusive'] or h['reservation']):
        raise ValueError('development declarations must not claim exclusive scientific admission')
    if h['min_physical_cores'] > len(h['allocated_cpus']):
        raise ValueError('physical core minimum exceeds allocated CPU count')
    largest = max(c['workers'] for c in configs.values())
    if largest > len(h['allocated_cpus']) or (not h['allow_smt'] and largest > h['min_physical_cores']):
        raise ValueError('workers incompatible with declared CPU/core allocation')
    lim = p['limits']
    fields(lim, 'max_trials timeout_seconds max_memory_bytes max_output_bytes', 'campaign limits')
    integer(lim['max_trials'], 1, MAX_TRIALS, 'trial limit')
    integer(lim['timeout_seconds'], 1, 3600, 'process timeout')
    integer(lim['max_memory_bytes'], 1, 1 << 50, 'memory limit')
    integer(lim['max_output_bytes'], 1, 128 * 1024 * 1024, 'worker output limit')
    if h['min_available_memory_bytes'] < lim['max_memory_bytes']:
        raise ValueError('admission memory minimum below requested memory budget')
    total = len(p['workloads'])*len(configs)*len(p['sessions'])*4*(p['diagnostics']+p['blocks']*(1+p['warmups']))
    if total > lim['max_trials']:
        raise ValueError('campaign expansion exceeds trial limit')
    if p['expected_evidence'] != EVIDENCE:
        raise ValueError('unsupported expected evidence contract')
    if type(p['comparisons']) is not list or len(p['comparisons']) > 256:
        raise ValueError('invalid comparison list')
    seen = set()
    for pair in p['comparisons']:
        fields(pair, 'kind numerator baseline', 'comparison')
        label(pair['numerator']); label(pair['baseline'])
        if pair['numerator'] not in configs or pair['baseline'] not in configs or pair['numerator'] == pair['baseline']:
            raise ValueError('unknown or identical comparison configurations')
        a, b = configs[pair['numerator']], configs[pair['baseline']]
        if pair['kind'] != 'worker-scaling' or a['delta'] != b['delta'] or a['workers'] == b['workers']:
            raise ValueError('incompatible cross-configuration comparison')
        key = (pair['numerator'], pair['baseline'])
        if key in seen: raise ValueError('duplicate comparison')
        seen.add(key)
    return p


def expand(plan):
    p = validate_plan(plan)
    identity = plan_hash(p)
    rng = SplitMix64(p['order_seed'])
    trials = []
    for session in p['sessions']:
        cells = [(w, c) for w in p['workloads'] for c in p['configurations']]
        for i in range(len(cells)-1, 0, -1):
            j = rng.below(i+1); cells[i], cells[j] = cells[j], cells[i]
        for w, c in cells:
            seed = rng.next_u64()
            policies = schedule(p['blocks'], seed)
            for block in range(-p['diagnostics'], p['blocks']):
                for position, policy in enumerate(list(POLICIES) if block < 0 else policies[block]):
                    kinds = ['diagnostic'] if block < 0 else ['warmup']*p['warmups']+['measured']
                    parent = f'{session}/{w["id"]}/{c["id"]}/{block}/{policy}'
                    for index, kind in enumerate(kinds):
                        token = f'{identity}/{parent}/{kind}/{index}'
                        trials.append(dict(trial_id=hashlib.sha256(token.encode()).hexdigest(),
                            sequence=len(trials), session=session, workload_id=w['id'], configuration_id=c['id'],
                            policy=policy, phase=kind, block=block, policy_position=position,
                            worker_group=parent, pairing_id=f'{session}/{w["id"]}/{block}',
                            configuration_pairing_id=f'{session}/{w["id"]}/{c["id"]}/{block}',
                            workers=c['workers'], delta=c['delta']))
    return dict(schema='dynagraph-campaign-trials', schema_version=1, campaign_id=p['campaign_id'],
                plan_sha256=identity, planning_only=True, admission_required=True,
                order_version=p['order_version'], trials=trials)
