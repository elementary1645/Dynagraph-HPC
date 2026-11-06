"""Bounded workload observations: local consistency, never isolation or authentication."""
import copy
from campaign_contract import fields, integer
from campaign_provenance import cpu_array
from workloads import canonical_json, sha256, parse_graph, parse_trace

POLICY = 'workload-regions-native-v2; development-only'
NATIVE = 'workload-native.json'
BOUND = 'workload-bound.json'


def seal(value):
    value = copy.deepcopy(value)
    value.pop('evidence_sha256', None)
    value['evidence_sha256'] = sha256(canonical_json(value))
    return value


def expected_regions(graph_data, trace_data, policy, no_effect):
    """Independent edge-list oracle determines executed delta calls, not reported teams.

    Bounded pilots have <=4096 edges, so the unchanged heuristic always selects
    Dijkstra. Initialization uses Dijkstra for every policy.
    """
    graph, trace = parse_graph(graph_data), parse_trace(trace_data)
    integer(graph.vertices, 1, 128, 'workload vertices')
    integer(len(graph.edges), 0, 4096, 'workload edges')
    integer(len(trace.updates), 0, 256, 'workload updates')
    edges = {(u, v): w for u, v, w in graph.edges}
    def distances():
        d = [None]*graph.vertices
        d[trace.source] = 0
        for _ in range(graph.vertices-1):
            new = d.copy()
            for (u, v), w in edges.items():
                if d[u] is not None and (new[v] is None or d[u]+w < new[v]):
                    new[v] = d[u]+w
            if new == d: break
            d = new
        return d
    count = 0
    for update in trace.updates:
        # Canonical trace tuples contain index, endpoints and old/new weights.
        _, u, v, old, new = update
        if edges[u, v] != old: raise ValueError('workload trace mismatch')
        before = distances()
        edges[u, v] = new
        effect = before[u] is not None and (before[v] is None or before[u]+new < before[v])
        if policy == 'delta-stepping' and new != old and (no_effect == 'execute_selected' or effect):
            count += 1
    return count


def validate_native(value, receipt, requested, count):
    fields(value, 'schema schema_version measurement_eligible regions', 'native workload')
    integer(value['schema_version'], 2, 2, 'native workload version')
    if value['schema'] != 'dynagraph-workload-native' or value['measurement_eligible'] is not False:
        raise ValueError('unsupported native workload contract')
    regions = value['regions']
    if type(regions) is not list or len(regions) != count or len(regions) > 257:
        raise ValueError('missing or extra workload regions')
    if receipt['state'] != 'verified' or receipt['released'] is not True:
        raise ValueError('workload without verified release')
    if receipt['schema_version'] == 2 and receipt['release']['state'] != 'confirmed_sent':
        raise ValueError('unknown workload GO release')
    observed = receipt['observation']
    pid, ticks = observed['pid'], observed['process_start_ticks']
    # Parent and child are session/group leaders because capture uses setsid.
    cpus = set(receipt['requested_cpus'])
    seen_generations = {}
    for index, region in enumerate(regions):
        fields(region, 'region_id requested_workers configured_workers threads', 'workload region')
        integer(region['region_id'], index, index, 'region ID')
        integer(region['requested_workers'], requested, requested, 'requested workers')
        integer(region['configured_workers'], 1, 64, 'configured workers')
        if requested and region['configured_workers'] != requested:
            raise ValueError('configured/requested workers mismatch')
        threads = region['threads']
        if type(threads) is not list or not 1 <= len(threads) <= region['configured_workers']:
            raise ValueError('invalid actual workload team')
        tids = set(); common = None
        for number, thread in enumerate(threads):
            fields(thread, 'number team level active_level max_active_levels ancestor_sizes ancestor_numbers entry exit', 'workload thread')
            integer(thread['number'], number, number, 'OpenMP thread number')
            integer(thread['team'], len(threads), len(threads), 'actual team')
            level, active, maximum = (thread[k] for k in ('level','active_level','max_active_levels'))
            integer(level, 1, 16, 'OpenMP level');integer(active, 0, level, 'OpenMP active level')
            integer(maximum, 0, (1<<31)-1, 'OpenMP max active levels')
            sizes, numbers = thread['ancestor_sizes'], thread['ancestor_numbers']
            if type(sizes) is not list or type(numbers) is not list or len(sizes) != level+1 or len(numbers) != level+1:
                raise ValueError('missing OpenMP ancestry')
            for size, n in zip(sizes, numbers):
                integer(size, 1, 64, 'ancestor team');integer(n, 0, size-1, 'ancestor thread')
            if (sizes[0] != 1 or numbers[0] != 0 or sizes[-1] != len(threads) or numbers[-1] != number or
                    active != sum(size > 1 for size in sizes) or (len(threads) > 1 and active > maximum)):
                raise ValueError('impossible OpenMP nesting')
            context = (level, active, maximum, sizes, numbers[:-1])
            if common is not None and common != context:
                raise ValueError('contradictory team ancestry')
            common = context
            entry, exit = thread['entry'], thread['exit']
            for sample in (entry, exit):
                fields(sample, 'tid tgid task_pid task_tgid pgrp session cpu start_ticks leader_start_ticks affinity', 'Linux workload task')
                for key in ('tid','tgid','task_pid','task_tgid','pgrp','session'):
                    integer(sample[key], 1, 1<<30, key)
                for key in ('start_ticks','leader_start_ticks'):
                    integer(sample[key], 1, (1<<63)-1, key)
                integer(sample['cpu'], 0, 8191, 'sampled CPU');cpu_array(sample['affinity'])
                if (sample['tgid'] != pid or sample['task_tgid'] != pid or sample['task_pid'] != sample['tid'] or
                        sample['pgrp'] != pid or sample['session'] != pid or sample['leader_start_ticks'] != ticks or
                        sample['start_ticks'] < ticks or (sample['tid'] == pid and sample['start_ticks'] != ticks)):
                    raise ValueError('contradictory workload task membership/generation')
                if not set(sample['affinity']) <= cpus or sample['cpu'] not in sample['affinity']:
                    raise ValueError('workload CPU outside enforced affinity')
                if sample['tid'] in seen_generations and seen_generations[sample['tid']] != sample['start_ticks']:
                    raise ValueError('workload task generation changed')
                seen_generations[sample['tid']] = sample['start_ticks']
            if any(entry[k] != exit[k] for k in ('tid','tgid','task_pid','task_tgid','pgrp','session','start_ticks','leader_start_ticks')):
                raise ValueError('entry/exit identity mismatch')
            if entry['tid'] in tids: raise ValueError('duplicate workload task')
            tids.add(entry['tid'])
    return value


def classification(native, receipt, requested, count):
    try:
        validate_native(native, receipt, requested, count)
    except (ValueError, KeyError, TypeError) as error:
        # Missing mandatory evidence is never strong. Known contradictions are
        # checked on all complete samples; no availability flag can hide them.
        missing = False
        if type(native) is dict and type(native.get('regions')) is list:
            for region in native['regions']:
                if type(region) is not dict or type(region.get('threads')) is not list:
                    continue
                for thread in region['threads']:
                    if type(thread) is not dict:
                        continue
                    for key in ('entry', 'exit'):
                        sample = thread.get(key)
                        if type(sample) is not dict or not {
                            'tid','tgid','task_pid','task_tgid','start_ticks','leader_start_ticks'
                        } <= sample.keys():
                            missing = True
        return ('insufficient_evidence' if missing else 'observed_contradictory'), str(error)
    if receipt['schema_version'] == 1:
        return 'insufficient_evidence', 'legacy receipt lacks atomic GO accounting required by the workload contract'
    return 'observed_consistent', None


def bind(native, receipt, hardware_sha256, count):
    status, issue = classification(native, receipt, receipt['binding']['workers'], count)
    return seal(dict(schema='dynagraph-workload-bound', schema_version=1,
        binding=copy.deepcopy(receipt['binding']), enforcement_sha256=receipt['evidence_sha256'],
        native_sha256=sha256(canonical_json(native)), hardware_sha256=hardware_sha256,
        expected_regions=count, classification=status, issue=issue,
        resource_observation=dict(process_affinity=receipt['observation']['affinity'],
            online_cpus=receipt['observation']['online_cpus'],
            effective_cpuset=receipt['observation']['cgroups']['effective_cpuset'],
            quota_pairs=receipt['observation']['cgroups']['quota_pairs'],
            topology_and_smt_reference='hardware.json#topology',
            scope='parent pre-GO resources correlated with workload entry/exit thread samples'),
        measurement_eligible=False, scientific_performance_allowed=False,
        limitations='entry/exit samples; no stable placement, ownership, isolation or authentication'))


def verify(bound, native, receipt, expected_binding, hardware_sha256, count, success):
    if canonical_json(receipt['binding']) != canonical_json(expected_binding):
        raise ValueError('workload execution/trial/attempt binding mismatch')
    expected = bind(native, receipt, hardware_sha256, count)
    if canonical_json(bound) != canonical_json(expected):
        raise ValueError('workload bound evidence mismatch')
    if success and expected['classification'] != 'observed_consistent':
        raise ValueError('successful workload requires consistent membership: '+str(expected['issue']))
    return expected['classification']
