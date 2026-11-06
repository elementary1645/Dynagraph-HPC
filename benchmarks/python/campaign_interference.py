"""Bounded shared-cgroup observations. Consistency is not isolation or authenticity."""
import copy
from decimal import Decimal
from pathlib import Path, PurePosixPath
import re
import time

from campaign_contract import fields, integer
from campaign_provenance import cpu_array, cpu_list, counter, mounts_for, process_identity
from campaign_workload import seal
from workloads import canonical_json, sha256

POLICY = 'resource-boundaries-v1; development-only'
WORKLOAD_POLICY = 'workload-regions-native-v3; resource-boundaries-v1; development-only'
NATIVE, BOUND, CONFIG = 'resource-native.json', 'resource-bound.json', 'resource-paths.txt'
MAX_NS = (1 << 63)-1
MAX_SPAN = 32_000_000_000
MAX_GAP = 2_000_000_000


def paths_from_views(views):
    paths = set()
    for view in views:
        leaf, endpoint = PurePosixPath(view['leaf']), PurePosixPath(view['mountpoint'])
        if endpoint not in (leaf, *leaf.parents): raise ValueError('invalid resource ancestry')
        while True:
            paths.add(str(leaf))
            if leaf == endpoint: break
            leaf = leaf.parent
            if len(paths) > 16: raise ValueError('resource ancestry limit')
    return sorted(paths)


def configuration(raw):
    if type(raw) is not bytes or len(raw) > 65536: raise ValueError('resource configuration size')
    lines = raw.decode('utf-8').splitlines()
    if len(lines) < 5 or lines[0] != 'DYNAGRAPH_RESOURCE_PATHS 1' or not raw.endswith(b'\n'):
        raise ValueError('resource configuration framing')
    armed = counter(lines[1], 'resource armed timestamp')
    if not armed or re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', lines[2]) is None:
        raise ValueError('resource configuration identity')
    count = counter(lines[3], 'resource paths')
    paths = lines[4:]
    if not 1 <= count <= 16 or len(paths) != count or paths != sorted(set(paths)):
        raise ValueError('resource configuration paths')
    for path in paths:
        p = PurePosixPath(path)
        if not p.is_absolute() or str(p) != path or '..' in p.parts or len(path) > 4096 or '\0' in path:
            raise ValueError('resource configuration absolute path')
    # Exact encoding disallows CRLF and alternate decimal representations.
    expected = f'DYNAGRAPH_RESOURCE_PATHS 1\n{armed}\n{lines[2]}\n{count}\n'+'\n'.join(paths)+'\n'
    if raw != expected.encode(): raise ValueError('noncanonical resource configuration')
    return dict(armed_ns=armed, boot_id=lines[2], paths=paths)


def prepare():
    from campaign_hardware import cgroup_ancestry
    groups = cgroup_ancestry()
    paths = paths_from_views(groups['views'])
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    raw = (f'DYNAGRAPH_RESOURCE_PATHS 1\n{time.monotonic_ns()}\n{boot}\n{len(paths)}\n'+'\n'.join(paths)+'\n').encode()
    configuration(raw)
    return raw


def fact(value):
    fields(value, 'value errno', 'resource fact')
    integer(value['errno'], 0, 4095, 'resource errno')
    if value['errno']:
        if value['value'] is not None: raise ValueError('resource errno/value contradiction')
        return None
    if type(value['value']) is not str or len(value['value'].encode()) > 65536:
        raise ValueError('invalid resource file value')
    return value['value'].strip()


def stat_counters(raw):
    result = {}
    for line in raw.splitlines():
        pair = line.split()
        if len(pair) != 2 or re.fullmatch(r'[a-z_][a-z0-9_.]{0,63}', pair[0]) is None or pair[0] in result:
            raise ValueError('malformed cpu.stat')
        result[pair[0]] = counter(pair[1], 'cpu.stat counter')
    if not {'usage_usec','user_usec','system_usec','nr_periods','nr_throttled','throttled_usec'} <= result.keys():
        raise ValueError('incomplete cpu.stat counters')
    return result


def pressure(raw):
    result = {}
    for line in raw.splitlines():
        tokens = line.split()
        if len(tokens) != 5 or tokens[0] not in ('some','full') or tokens[0] in result:
            raise ValueError('malformed CPU PSI')
        values = dict(t.split('=',1) for t in tokens[1:] if '=' in t)
        if set(values) != {'avg10','avg60','avg300','total'}: raise ValueError('malformed PSI fields')
        for key in ('avg10','avg60','avg300'):
            if re.fullmatch(r'[0-9]{1,3}\.[0-9]{2}', values[key]) is None or not 0 <= Decimal(values[key]) <= 100:
                raise ValueError('malformed PSI average')
        result[tokens[0]] = counter(values['total'], 'PSI total')
    if set(result) != {'some','full'}: raise ValueError('missing PSI scope')
    return result


def quota(raw):
    pair = raw.split()
    if len(pair) != 2: raise ValueError('malformed CPU quota')
    period = counter(pair[1], 'CPU period')
    limit = None if pair[0] == 'max' else counter(pair[0], 'CPU quota')
    if not period or limit == 0: raise ValueError('zero CPU quota/period')
    return [limit,period]


def assess(native, workload, receipt, config, finished_ns):
    """Inspect every available fact before selecting a verdict; gaps never hide contradictions."""
    issues, changes, interference, deltas = [], [], [], []
    def missing(text): issues.append(text)
    def changed(text): changes.append(text)
    fields(native, 'schema schema_version clock measurement_eligible configuration samples', 'resource native')
    if (native['schema'] != 'dynagraph-resource-native' or type(native['schema_version']) is not int or native['schema_version'] != 1 or
            native['clock'] != 'CLOCK_MONOTONIC' or native['measurement_eligible'] is not False or native['configuration'] != config):
        raise ValueError('resource native contract/configuration mismatch')
    integer(finished_ns, config['armed_ns'], MAX_NS, 'resource completion timestamp')
    if finished_ns-config['armed_ns'] > MAX_SPAN: missing('sampling interval exceeds 32 seconds')
    if receipt['schema_version'] != 2 or receipt['state'] != 'verified' or receipt['released'] is not True or receipt['release']['state'] != 'confirmed_sent':
        raise ValueError('resource completion requires atomic confirmed GO')
    observation = receipt['observation']
    pid, ticks = observation['pid'], observation['process_start_ticks']
    allowed = set(receipt['requested_cpus'])
    if paths_from_views(observation['cgroups']['views']) != config['paths']:
        raise ValueError('resource paths disagree with verified pre-GO ancestry')
    samples = native['samples']
    if type(samples) is not list or len(samples) not in (2,4): raise ValueError('incomplete resource boundaries')
    names = ['pre','workload_entry','workload_exit','post'] if len(samples)==4 else ['pre','post']
    if len(samples) == 2: missing('no sampled delta workload region')
    if workload.get('schema_version') != 3 or workload.get('clock') != 'CLOCK_MONOTONIC':
        raise ValueError('resource observation requires workload monotonic intervals')
    regions = workload['regions']
    if bool(regions) != (len(samples)==4): raise ValueError('resource/workload region disagreement')
    previous_end = config['armed_ns']; histories = {}; configs = []; tasks = {}
    sample_fields = ('boundary region_id start_ns pid tid process_affinity thread_affinity cpu process_stat task_stat task_status '
        'membership mountinfo online boot_id process_schedstat thread_schedstat groups topology process_stat_after membership_after mountinfo_after online_after end_ns')
    for index, sample in enumerate(samples):
        fields(sample, sample_fields, 'resource sample')
        if sample['boundary'] != names[index] or sample['region_id'] != (0 if names[index].startswith('workload') else None):
            raise ValueError('incorrect resource boundary')
        if names[index].startswith('workload'): integer(sample['region_id'],0,0,'resource region ID')
        begin, end = sample['start_ns'], sample['end_ns']
        integer(begin, previous_end, finished_ns, 'resource sample start')
        integer(end, begin, finished_ns, 'resource sample end')
        if begin-previous_end > MAX_GAP or end-begin > MAX_GAP: missing('sampling gap exceeds two seconds')
        previous_end = end
        integer(sample['pid'], pid,pid,'resource PID');integer(sample['tid'],1,1<<30,'resource TID')
        pa, ta = cpu_array(sample['process_affinity']), cpu_array(sample['thread_affinity'])
        integer(sample['cpu'],0,8191,'resource sampled CPU')
        if not set(pa) <= allowed or not set(ta) <= allowed or sample['cpu'] not in ta:
            raise ValueError('resource CPU outside enforced affinity')
        raw = {key:fact(sample[key]) for key in ('process_stat','process_stat_after','task_stat','task_status','membership',
            'membership_after','mountinfo','mountinfo_after','online','online_after','boot_id','process_schedstat','thread_schedstat')}
        for key, value in raw.items():
            if value is None and key not in ('process_schedstat','thread_schedstat'): missing('unavailable '+key)
        for key in ('process_stat','process_stat_after'):
            if raw[key] is not None:
                if process_identity(raw[key],pid) != ticks: raise ValueError('stale resource process generation')
                parts = raw[key][raw[key].rfind(') ')+2:].split()
                if parts[2:4] != [str(pid),str(pid)]: raise ValueError('resource leader group/session mismatch')
        if raw['task_stat'] is not None:
            generation = process_identity(raw['task_stat'],sample['tid'])
            if sample['tid'] in tasks and tasks[sample['tid']] != generation: raise ValueError('stale resource task generation')
            tasks[sample['tid']] = generation
            if sample['tid']==pid and generation != ticks: raise ValueError('stale resource leader task')
        if raw['task_status'] is not None:
            for key, expected in (('Pid',sample['tid']),('Tgid',pid)):
                matches = re.findall(r'^'+key+r':\s+([0-9]+)$', raw['task_status'], re.M)
                if matches != [str(expected)]: raise ValueError('contradictory resource task membership')
        if raw['boot_id'] is not None and raw['boot_id'] != config['boot_id']: raise ValueError('resource boot generation mismatch')
        for key in ('process_schedstat','thread_schedstat'):
            if raw[key] is not None:
                if len(raw[key].split()) != 3: raise ValueError('malformed schedstat')
                for value in raw[key].split(): counter(value,'schedstat')
        online = None if raw['online'] is None else cpu_list(raw['online'])
        online_after = None if raw['online_after'] is None else cpu_list(raw['online_after'])
        if online is not None and online_after is not None and online != online_after: changed('online set changed within sample')
        views = None
        for suffix in ('','_after'):
            member, mounts = raw['membership'+suffix], raw['mountinfo'+suffix]
            if member is not None and mounts is not None:
                if not member.startswith('0::'):
                    missing('unsupported cgroup layout'); continue
                current = mounts_for(member,mounts)
                if paths_from_views(current) != config['paths']:
                    changed('cgroup membership/mount paths changed'); missing('current ancestry not fully sampled')
                if views is not None and views != current: changed('cgroup view changed within sample')
                views = current
        groups = sample['groups']
        if type(groups) is not list or [g.get('path') for g in groups] != config['paths']: raise ValueError('resource ancestry coverage mismatch')
        policies = []
        for group in groups:
            fields(group, 'path open_errno identity cpu.max cpuset.cpus.effective cpu.stat cpu.pressure', 'resource cgroup')
            integer(group['open_errno'],0,4095,'cgroup open errno')
            identity = group['identity']
            if group['open_errno']:
                if identity is not None: raise ValueError('cgroup open identity contradiction')
                missing('unavailable cgroup directory')
            else:
                fields(identity,'device_major device_minor inode','cgroup identity')
                for key in identity: integer(identity[key],0,MAX_NS,'cgroup identity field')
                if not identity['inode']: raise ValueError('zero cgroup inode')
                if views and any(identity['device_major'] != int(v['device'].split(':')[0]) or identity['device_minor'] != int(v['device'].split(':')[1]) for v in views):
                    raise ValueError('cgroup device disagrees with mount identity')
            parsed = {}
            for key, parser in (('cpu.max',quota),('cpuset.cpus.effective',cpu_list),('cpu.stat',stat_counters),('cpu.pressure',pressure)):
                value = fact(group[key])
                if group['open_errno'] and group[key]['errno'] != group['open_errno']: raise ValueError('cgroup open/file contradiction')
                if value is None: missing('unavailable '+key); parsed[key]=None
                else: parsed[key]=parser(value)
            policies.append([group['path'],identity,parsed['cpu.max'],parsed['cpuset.cpus.effective']])
            for key in ('cpu.stat','cpu.pressure'):
                counters = parsed[key]
                if counters is None: continue
                history_key = (group['path'],key)
                prior = histories.get(history_key)
                if prior is not None:
                    common = set(prior)&set(counters)
                    if set(prior) != set(counters): missing('counter fields changed')
                    for name in sorted(common):
                        difference = counters[name]-prior[name]
                        deltas.append([index,group['path'],key,name,difference])
                        if difference < 0: missing('counter reset: '+name)
                        elif difference > 0 and (key=='cpu.pressure' or name in ('nr_throttled','throttled_usec')):
                            interference.append(key+':'+name)
                histories[history_key] = counters
        topology = sample['topology']
        if type(topology) is not list or [t.get('cpu') for t in topology] != pa: raise ValueError('topology CPU coverage')
        parsed_topology = []
        for row in topology:
            fields(row,'cpu physical_package_id core_id thread_siblings_list','resource topology')
            integer(row['cpu'],0,8191,'topology CPU')
            values = []
            for key in ('physical_package_id','core_id','thread_siblings_list'):
                value = fact(row[key])
                if value is None: missing('unavailable topology'); values.append(None)
                elif key == 'thread_siblings_list':
                    siblings = cpu_list(value)
                    if row['cpu'] not in siblings: raise ValueError('contradictory SMT sibling membership')
                    values.append(siblings)
                else: values.append(counter(value,'topology ID'))
            parsed_topology.append([row['cpu'],*values])
        if index == 0:
            if pa != observation['affinity'] or online is not None and online != observation['online_cpus']:
                changed('affinity/online configuration changed since pre-GO')
            prior_views = mounts_for(observation['cgroups']['membership'],observation['cgroups']['mountinfo'])
            if views is not None and views != prior_views: changed('cgroup view changed since pre-GO')
            prior_policies = {}
            for view in observation['cgroups']['views']:
                for ancestor in view['ancestors']:
                    prior_policies[ancestor['path']] = [quota(ancestor['cpu.max']),cpu_list(ancestor['cpuset.cpus.effective'])]
            for path, identity, limit, cpuset in policies:
                prior = prior_policies[path]
                if limit is not None and limit != prior[0] or cpuset is not None and cpuset != prior[1]:
                    changed('cgroup CPU policy changed since pre-GO')
        configs.append([pa,online,views,policies,parsed_topology])
        task_key = ('affinity',sample['tid'])
        if task_key in histories and histories[task_key] != ta: changed('sampler thread affinity changed')
        histories[task_key] = ta
        if names[index].startswith('workload'):
            primary = regions[0]['threads'][0]
            endpoint = 'entry' if names[index]=='workload_entry' else 'exit'
            offset = 0 if endpoint=='entry' else 2
            interval = primary['intervals'][offset:offset+2]
            if not interval[0] <= begin <= end <= interval[1]: raise ValueError('resource sample outside primary workload boundary')
            task = primary[endpoint]
            if task is None: missing('missing primary workload task')
            elif sample['tid'] != task['tid'] or tasks.get(sample['tid']) != task['start_ticks'] or sample['thread_affinity'] != task['affinity']:
                raise ValueError('resource/workload task identity mismatch')
    if finished_ns-previous_end > MAX_GAP: missing('post publication gap exceeds two seconds')
    if any(c != configs[0] for c in configs[1:]): changed('resource configuration changed across interval')
    if regions:
        first = min(t['intervals'][0] for t in regions[0]['threads'])
        last = max(t['intervals'][3] for t in regions[-1]['threads'])
        if samples[0]['end_ns'] > first or samples[-1]['start_ns'] < last: raise ValueError('pre/post workload interval mismatch')
    if regions:
        contexts = [[{k:t[k] for k in ('team','level','active_level','max_active_levels','ancestor_sizes','ancestor_numbers')}
                     for t in region['threads']] for region in regions]
        if any(context != contexts[0] for context in contexts[1:]): changed('OpenMP workload configuration changed')
    coverage = not issues
    status = ('observed_configuration_change' if changes else 'observed_interference' if interference else
              'insufficient_evidence' if issues else 'observed_stable')
    return dict(classification=status,coverage_complete=coverage,issues=sorted(set(issues)),
                changes=sorted(set(changes)),interference=sorted(set(interference)),counter_deltas=deltas)


def bind(native, workload, workload_bound, receipt, raw_config, finished_ns, hardware_sha256, omp_environment):
    config = configuration(raw_config)
    try:
        if (workload_bound['classification'] != 'observed_consistent' or workload_bound['native_sha256'] != sha256(canonical_json(workload)) or
                workload_bound['enforcement_sha256'] != receipt['evidence_sha256'] or workload_bound['binding'] != receipt['binding']):
            raise ValueError('resource workload dependency mismatch')
        outcome = assess(native,workload,receipt,config,finished_ns)
    except (ValueError,KeyError,TypeError,IndexError) as error:
        outcome = dict(classification='contradictory_evidence',coverage_complete=False,issues=[str(error)],
                       changes=[],interference=[],counter_deltas=[])
    return seal(dict(schema='dynagraph-resource-bound',schema_version=1,classification_version=1,
        binding=copy.deepcopy(receipt['binding']),
        process_generation=dict(pid=receipt['observation']['pid'],start_ticks=receipt['observation']['process_start_ticks'],boot_id=config['boot_id']),
        enforcement_sha256=receipt['evidence_sha256'],
        workload_sha256=workload_bound['evidence_sha256'],native_sha256=sha256(canonical_json(native)),
        configuration_sha256=sha256(raw_config),hardware_sha256=hardware_sha256,
        openmp_environment_sha256=sha256(canonical_json(omp_environment)),
        sampling=dict(policy=POLICY,clock='CLOCK_MONOTONIC',armed_ns=config['armed_ns'],finished_ns=finished_ns,
                      max_gap_ns=MAX_GAP,max_span_ns=MAX_SPAN,max_samples=4,max_paths=16),
        **outcome,measurement_eligible=False,scientific_performance_allowed=False,
        limitations='four boundary samples, first delta region only; visible shared cgroup counters; no attribution, ownership, isolation, authentication or absence-of-contention proof'))


def complete(bound):
    return bound['coverage_complete'] is True and bound['classification'] in (
        'observed_stable','observed_interference','observed_configuration_change')


def verify(bound,native,workload,workload_bound,receipt,raw_config,hardware_sha256,omp_environment,success):
    fields(bound, 'schema schema_version classification_version binding process_generation enforcement_sha256 workload_sha256 native_sha256 '
        'configuration_sha256 hardware_sha256 openmp_environment_sha256 sampling classification coverage_complete issues changes interference '
        'counter_deltas measurement_eligible scientific_performance_allowed limitations evidence_sha256', 'resource bound')
    fields(bound['sampling'], 'policy clock armed_ns finished_ns max_gap_ns max_span_ns max_samples max_paths', 'resource sampling policy')
    expected = bind(native,workload,workload_bound,receipt,raw_config,bound['sampling']['finished_ns'],hardware_sha256,omp_environment)
    if canonical_json(bound) != canonical_json(expected): raise ValueError('resource bound evidence mismatch')
    if success and not complete(expected): raise ValueError('successful resource diagnostic requires complete consistent observations')
    return expected
