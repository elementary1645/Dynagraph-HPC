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


_TASK_FIELDS = ('tid', 'tgid', 'task_pid', 'task_tgid', 'pgrp', 'session',
                'cpu', 'start_ticks', 'leader_start_ticks', 'affinity')
_IDENTITY_FIELDS = ('tid', 'tgid', 'task_pid', 'task_tgid', 'pgrp', 'session',
                    'start_ticks', 'leader_start_ticks')


class _IncompleteTaskEvidence(ValueError):
    """Only raised after every available task fact has passed semantic checks."""


def _task_sample(sample, pid, ticks, cpus):
    """Validate known facts even in incomplete samples; return whether any are missing.

    Deferring the missing-evidence verdict lets a contradiction anywhere in the
    document take precedence. Missing fields never substitute for observed facts.
    """
    if sample is None:
        return True
    if type(sample) is not dict or set(sample)-set(_TASK_FIELDS):
        raise ValueError('invalid Linux workload task fields')
    for key in ('tid', 'tgid', 'task_pid', 'task_tgid', 'pgrp', 'session'):
        if key in sample:
            integer(sample[key], 1, 1<<30, key)
    for key in ('start_ticks', 'leader_start_ticks'):
        if key in sample:
            integer(sample[key], 1, (1<<63)-1, key)
    if 'cpu' in sample:
        integer(sample['cpu'], 0, 8191, 'sampled CPU')
    if 'affinity' in sample:
        cpu_array(sample['affinity'])
    if (any(key in sample and sample[key] != pid for key in ('tgid', 'task_tgid', 'pgrp', 'session')) or
            ('tid' in sample and 'task_pid' in sample and sample['task_pid'] != sample['tid']) or
            ('leader_start_ticks' in sample and sample['leader_start_ticks'] != ticks) or
            ('start_ticks' in sample and (sample['start_ticks'] < ticks or
                (sample.get('tid') == pid and sample['start_ticks'] != ticks)))):
        raise ValueError('contradictory workload task membership/generation')
    if 'affinity' in sample and (not set(sample['affinity']) <= cpus or
            ('cpu' in sample and sample['cpu'] not in sample['affinity'])):
        raise ValueError('workload CPU outside enforced affinity')
    if 'cpu' in sample and sample['cpu'] not in cpus:
        raise ValueError('workload CPU outside enforced affinity')
    return any(key not in sample for key in _TASK_FIELDS)


def validate_native(value, receipt, requested, count):
    version = value.get('schema_version') if type(value) is dict else None
    integer(version, 2, 3, 'native workload version')
    fields(value, 'schema schema_version measurement_eligible regions'+(' clock' if version==3 else ''), 'native workload')
    if version == 3 and value['clock'] != 'CLOCK_MONOTONIC': raise ValueError('invalid workload clock')
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
    incomplete = False
    previous_exit = 0
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
        tids = {}; common = None
        for number, thread in enumerate(threads):
            # An absent endpoint is unavailable evidence, not permission to skip
            # contradictions in another endpoint/thread/region.
            shaped = dict(thread, entry=thread.get('entry'), exit=thread.get('exit')) if type(thread) is dict else thread
            fields(shaped, 'number team level active_level max_active_levels ancestor_sizes ancestor_numbers entry exit'+(' intervals' if version==3 else ''), 'workload thread')
            if version == 3:
                times = thread['intervals']
                if type(times) is not list or len(times) != 4: raise ValueError('invalid workload interval')
                previous = previous_exit
                for stamp in times:
                    integer(stamp, previous, (1<<63)-1, 'workload monotonic timestamp');previous=stamp
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
            entry, exit = thread.get('entry'), thread.get('exit')
            for sample in (entry, exit):
                incomplete |= _task_sample(sample, pid, ticks, cpus)
                if sample is None:
                    continue
                if 'tid' in sample:
                    previous = tids.setdefault(sample['tid'], number)
                    if previous != number:
                        raise ValueError('duplicate workload task')
                if 'tid' in sample and 'start_ticks' in sample:
                    if sample['tid'] in seen_generations and seen_generations[sample['tid']] != sample['start_ticks']:
                        raise ValueError('workload task generation changed')
                    seen_generations[sample['tid']] = sample['start_ticks']
            if entry is not None and exit is not None and any(
                    entry[key] != exit[key] for key in _IDENTITY_FIELDS if key in entry and key in exit):
                raise ValueError('entry/exit identity mismatch')
        if version == 3:
            if max(t['intervals'][1] for t in threads) > min(t['intervals'][2] for t in threads):
                raise ValueError('overlapping workload entry/exit intervals')
            previous_exit = max(t['intervals'][3] for t in threads)
    if incomplete:
        raise _IncompleteTaskEvidence('missing workload task evidence')
    return value


def classification(native, receipt, requested, count):
    try:
        validate_native(native, receipt, requested, count)
    except _IncompleteTaskEvidence as error:
        return 'insufficient_evidence', str(error)
    except (ValueError, KeyError, TypeError) as error:
        return 'observed_contradictory', str(error)
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
