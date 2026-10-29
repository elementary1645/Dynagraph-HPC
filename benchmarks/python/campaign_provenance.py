"""Hardware report v2 structural validation; no processes or filesystem access.

Supplied evidence is not authenticated. A valid snapshot does not prove ownership
or execution-time stability. Linux cgroup2 and ELF/libgomp are the supported subset.
"""
from pathlib import PurePosixPath
import re

from campaign_contract import fields, digest, integer, path_text
from workloads import canonical_json

VISIBILITY = 'all declared visible mounts reconciled; hidden host restrictions unverified'
MAX_CPU = 1048575
MAX_COUNTER = (1 << 63)-1


def absolute_path(value):
    path_text(value)
    path = PurePosixPath(value)
    if (not path.is_absolute() or value.startswith('//') or path.as_posix() != value or
            '..' in path.parts or '\\' in value):
        raise ValueError('noncanonical absolute evidence path')
    return path


def cpu_list(text):
    if type(text) is not str or not text or len(text) > 65536:
        raise ValueError('missing or excessive CPU list')
    cpus = set()
    for part in text.split(','):
        if re.fullmatch(r'[0-9]{1,7}(-[0-9]{1,7})?', part) is None:
            raise ValueError('malformed CPU list')
        ends = [int(v) for v in part.split('-')]
        lo, hi = ends[0], ends[-1]
        if not 0 <= lo <= hi <= MAX_CPU or hi-lo > 4095:
            raise ValueError('CPU range limit')
        cpus.update(range(lo, hi+1))
        if len(cpus) > 4096: raise ValueError('CPU count limit')
    return sorted(cpus)


def cpu_array(value, name='CPU IDs'):
    if type(value) is not list or not 1 <= len(value) <= 4096:
        raise ValueError(name+': bounded nonempty array required')
    for cpu in value: integer(cpu, 0, MAX_CPU, name)
    if value != sorted(set(value)):
        raise ValueError(name+': sorted unique IDs required')
    return value


def counter(value, name):
    if type(value) is not str or re.fullmatch(r'0|[1-9][0-9]{0,18}', value) is None:
        raise ValueError('malformed '+name)
    return integer(int(value), 0, MAX_COUNTER, name)


def mounts_for(membership, mountinfo):
    if type(membership) is not str or not membership.startswith('0::') or '\n' in membership:
        raise ValueError('unified cgroup v2 membership required')
    member = absolute_path(membership[3:])
    if type(mountinfo) is not str or not mountinfo or len(mountinfo.encode('utf-8')) > 262144:
        raise ValueError('missing or excessive cgroup mount evidence')
    lines = mountinfo.splitlines()
    if len(lines) > 4096: raise ValueError('mount record limit')
    views, ids, points = [], set(), set()
    for line in lines:
        parts = line.split()
        if '-' not in parts or len(parts) < 10:
            raise ValueError('malformed mountinfo record')
        sep = parts.index('-')
        if sep < 6 or len(parts) != sep+4:
            raise ValueError('malformed mountinfo separator')
        mid = counter(parts[0], 'mount ID')
        if mid == 0 or mid in ids: raise ValueError('duplicate or invalid mount ID')
        ids.add(mid)
        counter(parts[1], 'parent mount ID')
        if parts[sep+1] != 'cgroup2': continue
        root, point = absolute_path(parts[3]), absolute_path(parts[4])
        if root != member and root not in member.parents: continue
        if re.fullmatch(r'[0-9]{1,10}:[0-9]{1,10}', parts[2]) is None:
            raise ValueError('invalid cgroup hierarchy device')
        for part in parts[2].split(':'):integer(counter(part,'hierarchy device'),0,(1<<32)-1,'hierarchy device')
        if str(point) in points: raise ValueError('ambiguous cgroup mountpoint')
        points.add(str(point))
        leaf = point/member.relative_to(root)
        views.append(dict(mount_id=mid, device=parts[2], root=str(root), mountpoint=str(point),
                          membership=str(member), leaf=str(leaf), endpoint=str(point)))
    if not views: raise ValueError('cgroup mount does not resolve membership')
    if len(views) > 16 or len({v['device'] for v in views}) != 1:
        raise ValueError('ambiguous or excessive cgroup hierarchies')
    return sorted(views, key=lambda v:v['mount_id'])


def reconcile_cgroups(group):
    """Recompute from complete anchored views, independently of claimed summaries."""
    fields(group, 'membership mountinfo views effective_cpuset quota_pairs memory_headroom_bytes visibility', 'cgroup report v2')
    expected = mounts_for(group['membership'], group['mountinfo'])
    if type(group['views']) is not list or len(group['views']) != len(expected):
        raise ValueError('missing cgroup mount views')
    quotas, sets, memory, shared = [], [], [], {}
    total = 0
    for view, meta in zip(group['views'], expected):
        fields(view, 'mount_id device root mountpoint membership leaf endpoint ancestors', 'cgroup mount view')
        if canonical_json({k:v for k,v in view.items() if k!='ancestors'}) != canonical_json(meta):
            raise ValueError('inconsistent cgroup mount evidence')
        entries = view['ancestors']
        if type(entries) is not list or not 1 <= len(entries) <= 64:
            raise ValueError('missing or excessive cgroup ancestry')
        total += len(entries)
        if total > 256: raise ValueError('total cgroup ancestry limit')
        point, root = PurePosixPath(meta['mountpoint']), PurePosixPath(meta['root'])
        current = PurePosixPath(meta['leaf'])
        for entry in entries:
            fields(entry, 'path cgroup_path cpu.max cpuset.cpus.effective memory.max memory.current', 'cgroup ancestor')
            if absolute_path(entry['path']) != current:
                raise ValueError('truncated or noncontiguous cgroup ancestry')
            cgpath = str(root/current.relative_to(point))
            if entry['cgroup_path'] != cgpath:
                raise ValueError('contradictory cgroup hierarchy path')
            if type(entry['cpu.max']) is not str:
                raise ValueError('invalid ancestor CPU quota')
            tokens = entry['cpu.max'].split(' ')
            if len(tokens) != 2:
                raise ValueError('invalid ancestor CPU quota')
            period = counter(tokens[1], 'CPU quota period')
            if not period: raise ValueError('invalid ancestor CPU quota period')
            quota = None if tokens[0]=='max' else counter(tokens[0], 'CPU quota')
            if quota == 0: raise ValueError('invalid ancestor CPU quota')
            cpus = cpu_list(entry['cpuset.cpus.effective'])
            limit = None if entry['memory.max']=='max' else counter(entry['memory.max'], 'memory limit')
            used = counter(entry['memory.current'], 'memory usage')
            policy = (quota,period,cpus,limit)
            if cgpath in shared and shared[cgpath] != policy:
                raise ValueError('contradictory overlapping cgroup policy')
            shared[cgpath] = policy
            if quota is not None: quotas.append([quota,period])
            sets.append(set(cpus))
            if limit is not None: memory.append(max(0,limit-used))
            # Extra copies of the endpoint must not masquerade as more ancestors.
            if current == point:
                current = None
            else:
                current = current.parent
        if current is not None:
            raise ValueError('truncated cgroup ancestry endpoint')
    return dict(membership=group['membership'], mountinfo=group['mountinfo'], views=group['views'],
                effective_cpuset=sorted(set.intersection(*sets)),quota_pairs=quotas,
                memory_headroom_bytes=min(memory) if memory else None,visibility=VISIBILITY)


def validate_cgroups(group):
    computed = reconcile_cgroups(group)
    if canonical_json(computed) != canonical_json(group):
        raise ValueError('contradictory cgroup summaries')
    return computed


def topology_ids(rows, logical, numa):
    if type(rows) is not list or not 1 <= len(rows) <= 4096:
        raise ValueError('missing or excessive CPU topology')
    integer(logical,1,4096,'logical CPU count')
    ids, groups = {}, {}
    for row in rows:
        fields(row,'cpu package core siblings','CPU topology')
        for k in ('cpu','package','core'): integer(row[k],0,MAX_CPU,'topology ID')
        cpu_array(row['siblings'],'SMT siblings')
        if row['cpu'] in ids: raise ValueError('duplicate CPU topology ID')
        ids[row['cpu']] = row
        groups.setdefault((row['package'],row['core']),[]).append(row['cpu'])
    if logical != len(ids): raise ValueError('contradictory logical CPU count')
    for row in rows:
        if row['siblings'] != sorted(groups[(row['package'],row['core'])]):
            raise ValueError('nonreciprocal or contradictory SMT topology')
    if numa is not None:
        if type(numa) is not list or not 1 <= len(numa) <= 1024:
            raise ValueError('invalid NUMA topology')
        seen_nodes, seen_cpus, core_nodes = set(), set(), {}
        for node in numa:
            fields(node,'node cpus','NUMA node')
            integer(node['node'],0,MAX_CPU,'NUMA node ID')
            if node['node'] in seen_nodes: raise ValueError('duplicate NUMA node')
            seen_nodes.add(node['node']);
            if node['cpus'] != []:cpu_array(node['cpus'],'NUMA CPUs')
            elif type(node['cpus']) is not list:raise ValueError('invalid NUMA CPU array')
            for cpu in node['cpus']:
                if cpu not in ids or cpu in seen_cpus: raise ValueError('overlapping or unknown NUMA CPU')
                seen_cpus.add(cpu);key=(ids[cpu]['package'],ids[cpu]['core'])
                if key in core_nodes and core_nodes[key] != node['node']:
                    raise ValueError('SMT core split across NUMA nodes')
                core_nodes[key]=node['node']
        if seen_cpus != set(ids): raise ValueError('incomplete NUMA CPU coverage')
    return ids


def process_identity(stat, pid):
    if type(stat) is not str or len(stat) > 16384:
        raise ValueError('invalid process stat evidence')
    match = re.fullmatch(r'([1-9][0-9]*) \((.*)\) ([RSDZTtXxKWPI]) (.*)',stat)
    if match is None or int(match[1]) != pid:
        raise ValueError('process stat PID mismatch')
    tokens=match[4].split()
    if not 49 <= len(tokens) <= 64 or any(re.fullmatch(r'-?[0-9]{1,20}',t) is None for t in tokens):
        raise ValueError('malformed process stat fields')
    return integer(int(tokens[18]),1,MAX_COUNTER,'process start ticks')


def mapping_line(line):
    if type(line) is not str or len(line)>8192: raise ValueError('invalid runtime mapping line')
    parts=line.split(None,5)
    if len(parts)!=6 or re.fullmatch(r'[r-][w-][x-][ps]',parts[1]) is None:
        raise ValueError('invalid runtime mapping permissions')
    address=parts[0].split('-');device=parts[3].split(':')
    if (len(address)!=2 or len(device)!=2 or
            any(re.fullmatch(r'[0-9a-fA-F]{1,16}',t) is None for t in address+device+[parts[2]])):
        raise ValueError('invalid runtime mapping numeric fields')
    lo,hi=[int(t,16) for t in address]
    if lo>=hi: raise ValueError('invalid runtime mapping range')
    major,minor=[int(t,16) for t in device]
    for v in (major,minor):integer(v,0,(1<<32)-1,'mapping device')
    inode=counter(parts[4],'mapping inode')
    if not inode: raise ValueError('invalid mapping inode')
    path=absolute_path(parts[5])
    if re.fullmatch(r'libgomp\.so\.1(\.[0-9]+)*',path.name) is None:
        raise ValueError('mapping soname/path mismatch')
    return dict(lo=lo,hi=hi,path=str(path),device_major=major,device_minor=minor,inode=inode)


def validate_runtime(value):
    if type(value) is not dict: raise ValueError('invalid runtime evidence')
    kind=value.get('linkage')
    if kind=='candidate-library':
        fields(value,'path sha256 soname linkage','runtime candidate')
    elif kind=='observed-process-mapping':
        fields(value,'path sha256 soname linkage executable_sha256 pid process_stat process_start_ticks mappings file_identity','observed runtime')
        integer(value['pid'],1,1<<30,'runtime PID')
        digest(value['executable_sha256'])
        integer(value['process_start_ticks'],1,MAX_COUNTER,'process start ticks')
        if process_identity(value['process_stat'],value['pid']) != value['process_start_ticks']:
            raise ValueError('runtime process start mismatch')
        info=value['file_identity']
        fields(info,'device_major device_minor inode size mtime_ns','runtime file identity')
        for k in ('device_major','device_minor'):integer(info[k],0,(1<<32)-1,'runtime device')
        for k in ('inode','size'):integer(info[k],1,MAX_COUNTER,'runtime file '+k)
        integer(info['mtime_ns'],0,MAX_COUNTER,'runtime file mtime')
        lines=value['mappings']
        if type(lines) is not list or not 1<=len(lines)<=256 or any(type(l) is not str for l in lines):
            raise ValueError('missing runtime mappings')
        if len(set(lines))!=len(lines):raise ValueError('duplicate runtime mappings')
        parsed=[mapping_line(l) for l in lines]
        for row in parsed:
            if row['path']!=value['path'] or any(row[k]!=info[k] for k in ('device_major','device_minor','inode')):
                raise ValueError('runtime mapping/file identity mismatch')
        ordered=sorted(parsed,key=lambda r:r['lo'])
        if any(a['hi']>b['lo'] for a,b in zip(ordered,ordered[1:])):
            raise ValueError('overlapping runtime mappings')
    else: raise ValueError('unsupported runtime evidence kind')
    absolute_path(value['path']);digest(value['sha256'])
    if value['soname']!='libgomp.so.1' or re.fullmatch(r'libgomp\.so\.1(\.[0-9]+)*',PurePosixPath(value['path']).name) is None:
        raise ValueError('runtime soname/path mismatch')
    return value


def optional_observations(report):
    """Validate supplied optional facts; absence remains explicit, contradictions fail."""
    def value(key):return report[key]['value']
    for key in ('cpu_model','os','kernel'):
        v=value(key)
        if v is not None and (type(v) is not str or not v.strip() or len(v)>65536):
            raise ValueError('invalid '+key+' observation')
    if value('placement') is not None:
        fields(value('placement'),'taskset','placement evidence')
        if value('placement')['taskset'] is not None:absolute_path(value('placement')['taskset'])
    if value('virtualization') is not None:
        v=value('virtualization');fields(v,'hypervisor container product','virtualization evidence')
        if type(v['hypervisor']) is not bool or type(v['container']) is not bool:
            raise ValueError('invalid virtualization indicators')
        if v['product'] is not None and (type(v['product']) is not str or len(v['product'])>4096):
            raise ValueError('invalid DMI observation')
    freq=value('frequency')
    if freq is not None:
        if type(freq) is not list or len(freq)>4096:raise ValueError('invalid frequency evidence')
        seen=set()
        for row in freq:
            fields(row,'cpu governor driver current_khz min_khz max_khz','frequency observation')
            integer(row['cpu'],0,MAX_CPU,'frequency CPU')
            if row['cpu'] in seen:raise ValueError('duplicate frequency CPU')
            seen.add(row['cpu'])
            for key in ('governor','driver'):
                if row[key] is not None and (type(row[key]) is not str or not row[key].strip() or len(row[key])>128):
                    raise ValueError('invalid frequency '+key)
            for key in ('current_khz','min_khz','max_khz'):
                if row[key] is not None:counter(row[key],key)
            if row['min_khz'] is not None and row['max_khz'] is not None and int(row['min_khz'])>int(row['max_khz']):
                raise ValueError('contradictory frequency bounds')
