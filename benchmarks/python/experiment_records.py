"""Strict timing schema v1, worker contracts and completed-dataset validation."""
import json
from pathlib import Path
from deterministic import SplitMix64, UINT64_MAX
from workloads import canonical_json, decimal, fingerprint, object_fields, sha256, parse_graph

CATEGORIES = {'cli_validation', 'artifact_validation', 'trace_validation', 'initialization', 'execution',
              'graph_mismatch', 'distance_mismatch', 'metadata_mismatch', 'resource', 'incorrect_configuration',
              'invalid_artifacts', 'preflight_verification_failure', 'final_oracle_mismatch', 'clock_failure',
              'artifact_changed', 'worker_failure', 'timeout', 'interrupted', 'protocol_failure', 'output_failure'}
SCHEMA = 'dynagraph-timing-jsonl'
POLICIES = ('dijkstra', 'delta-stepping', 'incremental', 'heuristic')
IDENTITIES = ('graph_sha256', 'trace_sha256', 'executable_sha256', 'configuration_sha256')
COMMON = {'schema', 'schema_version', 'record_type', 'run_id', 'sequence', 'block_id', 'trial_id', 'policy', *IDENTITIES}
FIELDS = {
    'run_config': {'configuration', 'schedule', 'manifest_sha256', 'isolation', 'schedule_version'},
    'environment': {'metadata', 'source', 'delta', 'requested_workers', 'no_effect', 'heuristic', 'timing_mode', 'vertices', 'edges', 'updates', 'external_integrity', 'external_preflight', 'identity_origin'},
    'verification': {'scope', 'success', 'per_update_oracles', 'reference_recomputations', 'bellman_ford_checks'},
    'clock_probe': {'clock', 'is_steady', 'period_num', 'period_den', 'method', 'ticks'},
    'block_start': {'order'},
    'trial_start': {'repetition_id', 'policy_position', 'phase'},
    'warmup_end': {'phase', 'warmup_index', 'success'},
    'trial_measurement': {'phase', 'update_index', 'elapsed_ticks', 'elapsed_ns'},
    'update_latency': {'phase', 'update_index', 'elapsed_ticks', 'elapsed_ns'},
    'trial_end': {'success', 'updates_executed', 'sample_count'},
    'failure': {'category', 'message', 'update_index'},
    'block_end': {'success'},
    'run_end': {'success', 'blocks_completed'},
}


def loads(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('invalid JSON constant: ' + value)
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid)


def uint(value, maximum=UINT64_MAX):
    return decimal(value, maximum, 'record integer')


def schedule(blocks, seed):
    if type(blocks) is not int or blocks <= 0 or blocks > 400 or blocks % 4:
        raise ValueError('blocks must be positive, <=400 and divisible by four')
    random = SplitMix64(seed)
    labels = list(POLICIES)
    # Descending Fisher-Yates, three draws including the bound=2 draw.
    for index in range(3, 0, -1):
        selected = random.below(index + 1)
        labels[index], labels[selected] = labels[selected], labels[index]
    rows = ((0, 1, 3, 2), (1, 2, 0, 3), (2, 3, 1, 0), (3, 0, 2, 1))
    return [[labels[i] for i in rows[(block % 4 + seed % 4 + (block // 4) % 4) % 4]]
            for block in range(blocks)]


def configuration(value):
    required = {'schema_version', 'manifest', 'timing_mode', 'blocks', 'order_seed', 'delta', 'threads', 'no_effect', 'timeout_seconds'}
    if type(value) is not dict or not required <= value.keys() or value.keys() - required - {'warmups'}:
        raise ValueError('incorrect experiment configuration fields')
    result = dict(value)
    result.setdefault('warmups', '1')
    if type(result['schema_version']) is not int or result['schema_version'] != 1:
        raise ValueError('unsupported experiment version')
    if not isinstance(result['manifest'], str) or not result['manifest']:
        raise ValueError('manifest path required')
    if result['timing_mode'] not in ('full-trace', 'per-update') or result['no_effect'] not in ('shared_fast_path', 'execute_selected'):
        raise ValueError('unsupported timing or no-effect mode')
    blocks = uint(result['blocks'], 400)
    schedule(blocks, uint(result['order_seed']))
    if uint(result['delta']) == 0 or uint(result['timeout_seconds'], 3600) == 0:
        raise ValueError('delta and timeout must be positive')
    uint(result['threads'], 64)
    uint(result['warmups'], 100)
    return result


def record(kind, run_id, identities, sequence, block_id=None, trial_id=None, policy=None, **payload):
    return dict(schema=SCHEMA, schema_version=1, record_type=kind, run_id=run_id,
                sequence=str(sequence), block_id=block_id, trial_id=trial_id, policy=policy,
                **identities, **payload)


def validate_record(value):
    if type(value) is not dict:
        raise ValueError('record must be an object')
    kind = value.get('record_type')
    if kind not in FIELDS or set(value) != COMMON | FIELDS[kind]:
        raise ValueError('incorrect fields or unsupported record type')
    if value['schema'] != SCHEMA or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('unsupported record schema')
    for key in ('run_id', 'sequence'):
        uint(value[key])
    for key in ('block_id', 'trial_id'):
        if value[key] is not None:
            uint(value[key])
    if value['policy'] is not None and value['policy'] not in POLICIES:
        raise ValueError('unknown policy')
    for key in IDENTITIES:
        if value[key] is not None:
            fingerprint(value[key], key)
    for key in ('success', 'per_update_oracles', 'is_steady'):
        if key in value and type(value[key]) is not bool:
            raise ValueError('boolean required')
    for key in ('source', 'delta', 'requested_workers', 'vertices', 'edges', 'updates', 'reference_recomputations',
                'bellman_ford_checks', 'period_num', 'period_den', 'warmup_index', 'elapsed_ticks', 'elapsed_ns',
                'updates_executed', 'sample_count', 'blocks_completed', 'repetition_id', 'policy_position'):
        if key in value:
            uint(value[key])
    if 'update_index' in value and value['update_index'] is not None:
        uint(value['update_index'])
    if kind == 'clock_probe':
        if value['clock'] != 'std::chrono::steady_clock' or value['is_steady'] is not True or value['method'] != 'back-to-back-v1':
            raise ValueError('clock contract mismatch')
        if not uint(value['period_num']) or not uint(value['period_den']) or type(value['ticks']) is not list or len(value['ticks']) != 1024:
            raise ValueError('invalid clock period or probes')
        for tick in value['ticks']:
            uint(tick)
    if kind == 'environment':
        if type(value['metadata']) is not dict:
            raise ValueError('metadata object required')
        for item in value['metadata'].values():
            object_fields(item, ('value', 'origin', 'source'), 'metadata observation')
            if item['origin'] not in ('observed', 'build_recorded', 'user_supplied', 'unavailable') or not isinstance(item['source'], str):
                raise ValueError('invalid metadata provenance')
    if kind == 'run_config':
        fingerprint(value['manifest_sha256'], 'manifest identity')
    if kind in ('run_config','run_end') and any(value[key] is not None for key in ('block_id','trial_id','policy')):
        raise ValueError('incorrect global context')
    if kind in ('block_start','block_end') and (value['block_id'] is None or value['trial_id'] is not None or value['policy'] is not None):
        raise ValueError('incorrect block context')
    if kind == 'failure' and (value['category'] not in CATEGORIES or not isinstance(value['message'], str)):
        raise ValueError('failure diagnostic required')
    return value


def read_jsonl(data):
    if not data or not data.endswith(b'\n') or b'\n\n' in data:
        raise ValueError('missing/truncated JSONL records')
    return [validate_record(loads(line)) for line in data.splitlines()]


def validate_worker(records, expected, config, updates, vertices, edges):
    for index, item in enumerate(records):
        validate_record(item)
        if item['sequence'] != str(index) or any(item[key] != expected[key] for key in (*IDENTITIES, 'run_id', 'block_id', 'trial_id', 'policy')):
            raise ValueError('worker sequence or identity mismatch')
    kinds = [item['record_type'] for item in records]
    samples = updates if config['timing_mode'] == 'per-update' else 1
    measurement = 'update_latency' if config['timing_mode'] == 'per-update' else 'trial_measurement'
    warmups = uint(config['warmups'])
    if kinds != ['environment', 'clock_probe'] + ['warmup_end'] * warmups + ['verification'] + [measurement] * samples + ['trial_end']:
        raise ValueError('incomplete worker protocol')
    env, probe = records[:2]
    expected_env = dict(source=expected['source'], delta=config['delta'], requested_workers=config['threads'],
                        no_effect=config['no_effect'], timing_mode=config['timing_mode'], vertices=str(vertices), edges=str(edges), updates=str(updates),
                        external_integrity='unconfirmed', external_preflight='unconfirmed', identity_origin='user_supplied',
                        heuristic={'small_graph_edges':'4096', 'repair_max_degree':'32', 'parallel_min_edges':'65536'})
    required_metadata = {'compiler','compiler_path','cmake_version','build_type','flags','sanitizers','git_revision','git_dirty',
                         'openmp_spec','openmp_max_threads','openmp_dynamic','openmp_thread_limit','openmp_runtime_version','actual_workers'}
    if set(env['metadata']) != required_metadata or env['metadata']['actual_workers']['value'] is not None or env['metadata']['actual_workers']['origin'] != 'unavailable':
        raise ValueError('missing or incorrect worker metadata')
    if any(env[key] != value for key, value in expected_env.items()):
        raise ValueError('worker configuration mismatch')
    for index in range(warmups):
        item = records[2 + index]
        if item['success'] is not True or item['phase'] != 'warmup' or item['warmup_index'] != str(index):
            raise ValueError('invalid warmup evidence')
    verification = records[2 + warmups]
    if (verification['scope'] != 'timed_final_state' or verification['success'] is not True or verification['per_update_oracles'] is not False or
            verification['reference_recomputations'] != '1' or verification['bellman_ford_checks'] != ('1' if vertices <= 128 and edges <= 4096 else '0')):
        raise ValueError('invalid final verification evidence')
    for index, item in enumerate(records[3 + warmups:-1]):
        if item['phase'] != 'measurement' or item['update_index'] != (str(index) if measurement == 'update_latency' else None):
            raise ValueError('incorrect sample index')
        ns = uint(item['elapsed_ticks']) * uint(probe['period_num']) * 1000000000 // uint(probe['period_den'])
        if ns > UINT64_MAX or item['elapsed_ns'] != str(ns):
            raise ValueError('incorrect nanosecond conversion')
    end = records[-1]
    if end['success'] is not True or end['sample_count'] != str(samples) or end['updates_executed'] != str(updates):
        raise ValueError('incomplete worker execution')



def verify_preflight(data, config, manifest, policy):
    result = loads(data)
    expected = dict(schema_version=1, success=True, failure_category='none', failing_update_index=None,
                    policy=policy, source=manifest['source'], delta=uint(config['delta']), requested_workers=uint(config['threads']),
                    no_effect=config['no_effect'], verification_level='full', trace_entries=manifest['counts']['updates'],
                    updates_executed=manifest['counts']['updates'], updates_verified=manifest['counts']['updates'],
                    reference_recomputations=manifest['counts']['updates'] + 1, final_graph_verified=True, final_distances_verified=True,
                    declared_graph_sha256=manifest['artifacts']['graph']['sha256'], identity_origin='unverified_artifact_metadata', integrity='external_python_verifier_required')
    eligible = manifest['counts']['vertices'] <= 128 and manifest['counts']['edges'] <= 4096
    expected['bellman_ford_checks'] = manifest['counts']['updates'] + 1 if eligible else 0
    if type(result) is not dict or set(result) != set(expected) | {'message','graph_path','trace_path','final_weights','final_distances'}:
        raise ValueError('incorrect preflight schema')
    if not all(isinstance(result[key], str) for key in ('message','graph_path','trace_path')):
        raise ValueError('incorrect preflight strings')
    distances = result['final_distances']
    if type(distances) is not list or len(distances) != manifest['counts']['vertices'] or any(value is not None and (type(value) is not int or not 0 <= value < UINT64_MAX) for value in distances):
        raise ValueError('incorrect preflight distances')
    if distances[manifest['source']] != 0:
        raise ValueError('incorrect source label')
    if any(type(result.get(key)) is not type(value) or result.get(key) != value for key, value in expected.items()):
        raise ValueError('incorrect preflight result/configuration')
    final_graph = parse_graph((Path(manifest['_bundle']) / 'graph.txt').read_bytes())
    if not isinstance(result.get('final_weights'), list) or len(result['final_weights']) != len(final_graph.edges):
        raise ValueError('missing final weights')
    from workloads import Graph, graph_bytes
    final = Graph(final_graph.vertices, tuple((u, v, weight) for (u,v,_),weight in zip(final_graph.edges, result['final_weights'])))
    if sha256(graph_bytes(final)) != manifest['final_graph_sha256']:
        raise ValueError('incorrect preflight final graph')
    return result



def validate_dataset(path, *, pending=False):
    records = read_jsonl(Path(path).read_bytes())
    first = records[0]
    if pending:
        # Internal pre-completion check only. Public/default validation still
        # requires the actual terminal line and never accepts missing records.
        records.append(record('run_end', first['run_id'], {key:first[key] for key in IDENTITIES},
                              len(records), success=True, blocks_completed=first['configuration']['blocks']))
    if first['record_type'] != 'run_config':
        raise ValueError('run_config must be first')
    for key in IDENTITIES:
        fingerprint(first[key], key)
    config = configuration(first['configuration'])
    if sha256(canonical_json(config)) != first['configuration_sha256'] or first['schedule'] != schedule(uint(config['blocks']), uint(config['order_seed'])):
        raise ValueError('configuration identity or schedule mismatch')
    identities = {key: first[key] for key in IDENTITIES}
    for index, item in enumerate(records):
        if item['sequence'] != str(index) or item['run_id'] != first['run_id'] or any(item[key] != identities[key] for key in IDENTITIES):
            raise ValueError('dataset sequence or identity mismatch')
        if item['record_type'] == 'failure' or item.get('success') is False:
            raise ValueError('failed dataset')
    from artifacts import verify_bundle
    directory = Path(path).parent
    bundle = directory / 'workload'
    manifest_bytes = (bundle / 'manifest.json').read_bytes()
    manifest = loads(manifest_bytes)
    if sha256(manifest_bytes) != first['manifest_sha256'] or any(manifest['artifacts'][name]['sha256'] != identities[name + '_sha256'] for name in ('graph','trace')):
        raise ValueError('artifact identity mismatch')
    verification = verify_bundle(bundle / 'manifest.json')
    if loads((directory / 'artifact-verification.json').read_bytes()) != verification or sha256((directory / 'runner').read_bytes()) != identities['executable_sha256']:
        raise ValueError('artifact/executable evidence mismatch')
    if first['isolation'] != 'fresh-process-per-trial-v1' or first['schedule_version'] != 'balanced-four-splitmix64-fisher-yates-v1':
        raise ValueError('unsupported execution protocol')
    position = 1
    if records[position]['record_type'] != 'environment' or records[position]['trial_id'] is not None:
        raise ValueError('host environment missing')
    host = records[position]
    for key, value in dict(source=str(manifest['source']), delta=config['delta'], requested_workers=config['threads'],
                           no_effect=config['no_effect'], timing_mode=config['timing_mode'], vertices=str(manifest['counts']['vertices']),
                           edges=str(manifest['counts']['edges']), updates=str(manifest['counts']['updates']),
                           external_integrity='python_verified', external_preflight='pending', identity_origin='python_sha256').items():
        if host[key] != value:
            raise ValueError('host configuration mismatch')
    position += 1
    for policy in POLICIES:
        item = records[position]
        if (item['record_type'] != 'verification' or item['policy'] != policy or item['scope'] != 'external_full_preflight' or
                item['success'] is not True or item['per_update_oracles'] is not True):
            raise ValueError('preflight missing')
        stem = directory / ('preflight-' + policy)
        result = verify_preflight((Path(str(stem) + '.stdout')).read_bytes(), config, dict(manifest, _bundle=str(bundle)), policy)
        if item['reference_recomputations'] != str(result['reference_recomputations']) or item['bellman_ford_checks'] != str(result['bellman_ford_checks']):
            raise ValueError('preflight counts mismatch')
        validate_exit(stem)
        position += 1
    for block, order in enumerate(first['schedule']):
        start = records[position]
        if start['record_type'] != 'block_start' or start['block_id'] != str(block) or start['order'] != order:
            raise ValueError('block order mismatch')
        position += 1
        for policy_position, policy in enumerate(order):
            start = records[position]
            trial_id = str(block * 4 + policy_position)
            if (start['record_type'] != 'trial_start' or start['block_id'] != str(block) or start['trial_id'] != trial_id or
                    start['policy'] != policy or start['repetition_id'] != str(block) or start['policy_position'] != str(policy_position) or start['phase'] != 'measurement'):
                raise ValueError('trial order mismatch')
            position += 1
            begin = position
            while position < len(records) and records[position]['record_type'] != 'trial_end':
                position += 1
            if position >= len(records):
                raise ValueError('trial terminal missing')
            worker = [dict(item, sequence=str(i)) for i,item in enumerate(records[begin:position + 1])]
            env = worker[0]
            expected = dict(start, source=str(manifest['source']))
            validate_worker(worker, expected, config, manifest['counts']['updates'], manifest['counts']['vertices'], manifest['counts']['edges'])
            raw_worker = read_jsonl((directory / ('trial-' + trial_id + '.stdout')).read_bytes())
            if worker != raw_worker:
                raise ValueError('worker evidence differs from dataset')
            validate_exit(directory / ('trial-' + trial_id))
            position += 1
        end = records[position]
        if end['record_type'] != 'block_end' or end['block_id'] != str(block) or end['success'] is not True:
            raise ValueError('block terminal missing')
        position += 1
    if position != len(records) - 1 or records[position]['record_type'] != 'run_end' or records[position]['success'] is not True or records[position]['blocks_completed'] != config['blocks']:
        raise ValueError('run terminal missing')
    return {'schema_version': 1, 'status': 'pending' if pending else 'complete', 'trials': str(uint(config['blocks']) * 4)}


def validate_exit(stem):
    evidence = loads(Path(str(stem) + '.exit.json').read_bytes())
    if evidence != {'returncode': 0, 'stdout_sha256': sha256(Path(str(stem) + '.stdout').read_bytes()),
                    'stderr_sha256': sha256(Path(str(stem) + '.stderr').read_bytes())}:
        raise ValueError('worker exit evidence mismatch')
