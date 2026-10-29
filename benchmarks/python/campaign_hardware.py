"""Read-only Linux observation and fail-closed campaign qualification.

No executable under inspection is run. Reports are evidence, not host attestation.
"""
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess

from campaign_contract import fields, integer, plan_hash, validate_plan
from workloads import canonical_json


def observation(value, source):
    return dict(value=value, source=source, origin='observed' if value is not None else 'unavailable')


def cpu_list(text):
    cpus = set()
    if not text or len(text) > 65536:
        raise ValueError('missing or excessive CPU list')
    for part in text.strip().split(','):
        if re.fullmatch(r'[0-9]+(-[0-9]+)?', part) is None:
            raise ValueError('malformed CPU list')
        ends = [int(v) for v in part.split('-')]
        lo, hi = ends[0], ends[-1]
        if not 0 <= lo <= hi <= 1048575 or hi-lo > 4095:
            raise ValueError('CPU range limit')
        cpus.update(range(lo, hi+1))
        if len(cpus) > 4096:
            raise ValueError('CPU count limit')
    return sorted(cpus)


def read_text(path):
    try:
        with open(path, encoding='utf-8') as stream:
            value = stream.read(1024*1024+1)
        return value.strip() if len(value) <= 1024*1024 else None
    except (OSError, UnicodeError):
        return None


def file_hash(path):
    value = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(65536), b''): value.update(block)
    return value.hexdigest()


def cgroup_ancestry(read=read_text):
    """Resolve unified membership against mount root, then walk every visible ancestor."""
    membership, mounts = read('/proc/self/cgroup'), read('/proc/self/mountinfo')
    if membership is None or mounts is None:
        raise ValueError('cgroup membership/mount information unavailable')
    rows = [line[3:] for line in membership.splitlines() if line.startswith('0::')]
    if len(rows) != 1:
        raise ValueError('unified cgroup v2 membership required')
    relative = PurePosixPath(rows[0])
    if not relative.is_absolute() or '..' in relative.parts:
        raise ValueError('unsafe cgroup membership')
    candidates = []
    for line in mounts.splitlines():
        parts = line.split()
        if '-' not in parts: continue
        sep = parts.index('-')
        if len(parts) <= sep+1 or parts[sep+1] != 'cgroup2' or len(parts) < 6: continue
        # Escaped mount paths are deliberately unsupported; fail closed.
        root, mount = PurePosixPath(parts[3]), PurePosixPath(parts[4])
        if '\\' in str(root)+str(mount) or not root.is_absolute() or not mount.is_absolute() or '..' in root.parts+mount.parts:
            continue
        if relative == root or root in relative.parents:
            candidates.append((len(root.parts), root, mount))
    if not candidates: raise ValueError('cgroup mount does not resolve membership')
    _, root, mount = max(candidates, key=lambda v:v[0])
    current = mount/relative.relative_to(root)
    entries = []
    while True:
        if len(entries) >= 64: raise ValueError('cgroup ancestry depth limit')
        entry = dict(path=str(current))
        for name in ('cpu.max', 'cpuset.cpus.effective', 'memory.max', 'memory.current'):
            value = read(str(current/name))
            if value is None: raise ValueError('missing cgroup ancestor field: '+str(current/name))
            entry[name] = value
        entries.append(entry)
        if current == mount: break
        current = current.parent
    return summarize_cgroups(entries)


def summarize_cgroups(entries):
    if type(entries) is not list or not 1 <= len(entries) <= 64:
        raise ValueError("invalid cgroup ancestry")
    quotas, sets, headroom = [], [], []
    for index, entry in enumerate(entries):
        fields(entry, 'path cpu.max cpuset.cpus.effective memory.max memory.current', 'ancestor')
        path = PurePosixPath(entry['path'])
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('unsafe ancestor path')
        if index and PurePosixPath(entries[index-1]['path']).parent != path:
            raise ValueError('noncontiguous cgroup ancestry')
        if any(type(entry[k]) is not str for k in entry):
            raise ValueError('invalid ancestor field type')
        tokens = entry['cpu.max'].split()
        if len(tokens) != 2 or not tokens[1].isdigit() or int(tokens[1]) <= 0:
            raise ValueError('invalid ancestor CPU quota')
        if tokens[0] != 'max':
            if not tokens[0].isdigit() or int(tokens[0]) <= 0: raise ValueError('invalid ancestor CPU quota')
            quotas.append((int(tokens[0]), int(tokens[1])))
        sets.append(set(cpu_list(entry['cpuset.cpus.effective'])))
        limit, used = entry['memory.max'], entry['memory.current']
        if not used.isdigit() or (limit != 'max' and not limit.isdigit()):
            raise ValueError('invalid ancestor memory limit')
        if limit != 'max': headroom.append(max(0, int(limit)-int(used)))
    return dict(ancestors=entries, effective_cpuset=sorted(set.intersection(*sets)),
                quota_pairs=[list(q) for q in quotas], memory_headroom_bytes=min(headroom) if headroom else None,
                visibility='visible mount ancestors only; outside namespace restrictions unverified')


def fixed_command(command):
    try:
        result = subprocess.run(command, capture_output=True, timeout=5, check=False,
                                env=dict(os.environ, LC_ALL='C', LANG='C'))
        if result.returncode or len(result.stdout) > 1024*1024: return None
        return result.stdout.decode('utf-8', errors='strict').strip()
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None


def binary_identity(executable=None):
    compiler_path = shutil.which('g++')
    compiler = None
    if compiler_path:
        version = fixed_command([compiler_path, '--version'])
        if version:
            compiler = dict(path=str(Path(compiler_path).resolve()), version=version,
                            sha256=file_hash(compiler_path))
    runtime = None
    if executable is not None and compiler_path:
        # readelf inspects bytes; never use ldd or run an untrusted executable.
        reader = shutil.which('readelf')
        dynamic = fixed_command([reader, '-d', '--', str(Path(executable).absolute())]) if reader else None
        candidate = fixed_command([compiler_path, '-print-file-name=libgomp.so.1'])
        if dynamic and candidate and '[libgomp.so.1]' in dynamic and Path(candidate).is_file():
            runtime = dict(path=str(Path(candidate).resolve()), sha256=file_hash(candidate), soname='libgomp.so.1',
                           linkage='DT_NEEDED match; candidate from compiler; actual loader resolution unverified')
    return compiler, runtime


def mapped_runtime(pid, executable, read=read_text):
    """Optional read-only observation of an already running process, never launched here."""
    if executable is None: return None
    try:
        before = read(f'/proc/{pid}/stat')
        maps = read(f'/proc/{pid}/maps')
        if not before or not maps: return None
        process_exe = f'/proc/{pid}/exe'
        wanted = file_hash(executable)
        if file_hash(process_exe) != wanted: return None
        candidates = set()
        for line in maps.splitlines():
            parts = line.split(None, 5)
            if len(parts) == 6 and re.fullmatch(r'libgomp\.so\.[0-9.]+', Path(parts[5]).name):
                candidates.add((parts[5], parts[3], int(parts[4])))
        if len(candidates) != 1: return None
        path, device, inode = candidates.pop()
        # Read through the process root, not the collector's possibly different namespace.
        actual = Path(f'/proc/{pid}/root')/path.lstrip('/')
        info = actual.stat()
        major, minor = [int(part,16) for part in device.split(':')]
        if (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino) != (major, minor, inode):
            return None
        result = dict(path=path, sha256=file_hash(actual), soname='libgomp.so.1',
                      linkage='observed-process-mapping', executable_sha256=wanted,
                      pid=pid, process_stat=before)
        final_info = actual.stat()
        if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (final_info.st_dev, final_info.st_ino, final_info.st_size, final_info.st_mtime_ns):
            return None
        after = read(f'/proc/{pid}/stat')
        if not after or before.rsplit(')',1)[-1].split()[19] != after.rsplit(')',1)[-1].split()[19] or read(f'/proc/{pid}/maps') != maps or file_hash(process_exe) != wanted:
            return None
        return result
    except (OSError, IndexError, ValueError):
        return None


def inspect(executable=None, read=read_text, affinity=None, binaries=True, pid=None):
    if affinity is None:
        try: affinity = sorted(os.sched_getaffinity(0))
        except (OSError, AttributeError): affinity = None
    if affinity is not None:
        if len(affinity) > 4096: raise ValueError('affinity CPU count limit')
        affinity = sorted(affinity)
    cpuinfo = read('/proc/cpuinfo')
    model = next((l.split(':',1)[1].strip() for l in (cpuinfo or '').splitlines() if l.startswith('model name')), None)
    topology, nodes, frequency = None, None, None
    online = None
    try:
        topology = []
        online = cpu_list(read('/sys/devices/system/cpu/online'))
        for cpu in online:
            prefix = f'/sys/devices/system/cpu/cpu{cpu}'
            package, core = read(prefix+'/topology/physical_package_id'), read(prefix+'/topology/core_id')
            if package is None or core is None or not package.isdigit() or not core.isdigit():
                raise ValueError('CPU topology missing')
            topology.append(dict(cpu=cpu, package=int(package), core=int(core),
                                 siblings=cpu_list(read(prefix+'/topology/thread_siblings_list'))))
        nodes = [dict(node=n, cpus=cpu_list(read(f'/sys/devices/system/node/node{n}/cpulist')))
                 for n in cpu_list(read('/sys/devices/system/node/online'))]
        frequency = [dict(cpu=c, governor=read(f'/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_governor'),
                          driver=read(f'/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_driver'),
                          current_khz=read(f'/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_cur_freq'),
                          min_khz=read(f'/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_min_freq'),
                          max_khz=read(f'/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_max_freq')) for c in (affinity or [])]
    except (ValueError, TypeError):
        # Never infer missing core topology from logical counts.
        if not topology or online is None or len(topology) != len(online):
            topology = None
    try: groups = cgroup_ancestry(read)
    except ValueError: groups = None
    available = None
    for line in (read('/proc/meminfo') or '').splitlines():
        if re.fullmatch(r'MemAvailable:\s+[0-9]+ kB', line): available = int(line.split()[1])*1024
    if available is not None and groups is not None and groups['memory_headroom_bytes'] is not None:
        available = min(available, groups['memory_headroom_bytes'])
    compiler, runtime = binary_identity(executable) if binaries else (None, None)
    if pid is not None:
        integer(pid, 1, 1 << 30, 'process ID')
        runtime = mapped_runtime(pid, executable, read)
    return dict(schema='dynagraph-hardware', schema_version=1,
        cpu_model=observation(model, '/proc/cpuinfo'),
        logical_cpus=observation(len(topology) if topology else None, 'online CPU topology'),
        topology=observation(topology, 'sysfs package/core/sibling IDs; may be virtual'),
        numa=observation(nodes, 'sysfs NUMA node CPU lists'),
        affinity=observation(affinity, 'sched_getaffinity'),
        cgroups=observation(groups, '/proc/self/cgroup + mountinfo + all visible ancestors'),
        available_memory_bytes=observation(available, 'MemAvailable intersected with visible cgroup headroom'),
        os=observation(read('/etc/os-release'), '/etc/os-release'),
        kernel=observation(read('/proc/sys/kernel/osrelease'), '/proc/sys/kernel/osrelease'),
        virtualization=observation(dict(hypervisor='hypervisor' in cpuinfo,
            container=read('/.dockerenv') is not None or 'docker' in (read('/proc/1/cgroup') or ''),
            product=read('/sys/class/dmi/id/product_name')), 'CPU flags, container marker and DMI') if cpuinfo else observation(None,'CPU flags unavailable'),
        compiler=observation(compiler, 'fixed g++ query and executable bytes'),
        openmp=observation(runtime, 'ELF dependency inspection; candidate library identity'),
        executable_sha256=observation(file_hash(executable) if executable else None, 'inspected executable bytes'),
        placement=observation(dict(taskset=shutil.which('taskset')), 'available placement command; no affinity change'),
        frequency=observation(frequency, 'sysfs cpufreq; missing fields remain null'),
        limitations=['No exclusivity attestation', 'No actual OpenMP team observed',
                    'No benchmark executed', 'Hidden cgroup ancestors and host scheduling unverified',
                    'Runtime loader resolution and build flags require separate verified evidence'])


def admit(plan, report):
    p = validate_plan(plan)
    keys = ('cpu_model logical_cpus topology numa affinity cgroups available_memory_bytes os kernel '
            'virtualization compiler openmp executable_sha256 placement frequency').split()
    fields(report, 'schema schema_version '+' '.join(keys)+' limitations', 'hardware report')
    if report['schema'] != 'dynagraph-hardware' or type(report['schema_version']) is not int or report['schema_version'] != 1:
        raise ValueError('unsupported hardware report')
    for k in keys:
        fields(report[k], 'value source origin', 'observation')
        if type(report[k]['source']) is not str or not report[k]['source'] or report[k]['origin'] not in ('observed', 'unavailable'):
            raise ValueError('invalid hardware observation')
        if (report[k]['value'] is None) != (report[k]['origin']=='unavailable'):
            raise ValueError('contradictory hardware observation')
    if type(report['limitations']) is not list or any(type(v) is not str for v in report['limitations']):
        raise ValueError('invalid hardware limitations')
    h, failures = p['hardware'], []
    def require(test, reason):
        if not test: failures.append(reason)
    def value(key): return report[key]['value']
    cpus = h['allocated_cpus']
    affinity = value('affinity')
    require(type(affinity) is list and all(type(c) is int for c in affinity) and affinity == cpus, 'effective affinity must equal declared allocation')
    topology = value('topology')
    try:
        if type(topology) is not list or not topology: raise ValueError('missing topology')
        ids, cores = {}, set()
        for row in topology:
            fields(row, 'cpu package core siblings', 'CPU topology')
            for k in ('cpu', 'package', 'core'): integer(row[k], 0, 1048575, 'topology ID')
            if (row['cpu'] in ids or type(row['siblings']) is not list or
                    any(type(c) is not int for c in row['siblings']) or row['cpu'] not in row['siblings']):
                raise ValueError('contradictory topology')
            ids[row['cpu']] = row
        require(type(value('logical_cpus')) is int and value('logical_cpus') == len(ids), 'contradictory logical CPU count')
        for cpu in cpus:
            row = ids[cpu]; cores.add((row['package'],row['core']))
            peers = sorted(c for c,r in ids.items() if (r['package'],r['core']) == (row['package'],row['core']))
            if sorted(row['siblings']) != peers: raise ValueError('inconsistent SMT siblings')
        require(len(cores) >= h['min_physical_cores'], 'insufficient physical cores')
        require(h['allow_smt'] or len(cores)==len(cpus), 'SMT siblings disallowed')
    except (ValueError, KeyError, TypeError):
        failures.append('missing or contradictory physical topology')
    groups = value('cgroups')
    try:
        if type(groups) is not dict: raise ValueError('missing groups')
        require(set(cpus) <= set(groups['effective_cpuset']), 'allocation outside effective cgroup cpuset')
        largest = max(c['workers'] for c in p['configurations'])
        for quota, period in groups['quota_pairs']:
            integer(quota, 1, 1 << 63, 'CPU quota'); integer(period, 1, 1 << 63, 'CPU period')
            require(quota >= largest*period, 'ancestor CPU quota below requested workers')
        require(canonical_json(groups) == canonical_json(summarize_cgroups(groups['ancestors'])), 'contradictory cgroup summaries')
        headroom = groups.get('memory_headroom_bytes')
        if headroom is not None:
            require(type(value('available_memory_bytes')) is int and value('available_memory_bytes') <= headroom,
                    'available memory contradicts cgroup headroom')
    except (ValueError, KeyError, TypeError): failures.append('missing or malformed cgroup ancestry')
    memory = value('available_memory_bytes')
    require(type(memory) is int and memory >= h['min_available_memory_bytes'], 'insufficient or unavailable memory')
    virt = value('virtualization')
    require(type(virt) is dict and type(virt.get('hypervisor')) is bool and type(virt.get('container')) is bool and
            (h['allow_virtualization'] or not (virt['hypervisor'] or virt['container'])), 'virtualization unavailable or disallowed')
    for key, wanted in [('compiler','compiler_sha256'),('openmp','openmp_sha256')]:
        observed = value(key)
        require(type(observed) is dict and observed.get('sha256') == p['build'][wanted], 'missing or mismatched '+key+' identity')
    require(value('executable_sha256') == p['build']['executable_sha256'], 'missing or mismatched executable identity')
    # DT_NEEDED plus a compiler candidate is not actual linked runtime evidence.
    # Require the optional, separate observation of an existing process mapping.
    runtime = value('openmp')
    require(type(runtime) is dict and runtime.get('linkage') == 'observed-process-mapping' and
            runtime.get('executable_sha256') == p['build']['executable_sha256'],
            'actual linked OpenMP runtime resolution is unverified')
    freq = value('frequency')
    if h['require_frequency_evidence']:
        require(type(freq) is list and {r.get('cpu') for r in freq if type(r) is dict and type(r.get('cpu')) is int and
                type(r.get('governor')) is str and r['governor'].strip()} >= set(cpus),
                'missing frequency/governor evidence')
    development = h['mode']=='development'
    return dict(schema='dynagraph-campaign-admission', schema_version=1,
                campaign_id=p['campaign_id'], plan_sha256=plan_hash(p),
                hardware_sha256=hashlib.sha256(canonical_json(report)).hexdigest(),
                mode=h['mode'], admitted=development or not failures,
                scientific_performance_allowed=not development and not failures,
                multicore_scaling_claims_allowed=False,
                qualification='development-only' if development else ('qualified-on-evidence' if not failures else 'rejected'),
                failures=failures, declarations=dict(origin='user_declared', exclusive=h['exclusive'], reservation=h['reservation']),
                limitations=report['limitations'])
