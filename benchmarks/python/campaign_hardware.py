"""Read-only Linux observation and fail-closed campaign qualification.

No executable under inspection is run. Reports are evidence, not host attestation.
"""
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess

from campaign_contract import fields, integer, plan_hash, validate_plan, digest
from workloads import canonical_json
from campaign_provenance import (absolute_path, cpu_list, cpu_array, mounts_for,
    reconcile_cgroups, validate_cgroups, topology_ids, validate_runtime, process_identity, optional_observations)


def observation(value, source):
    return dict(value=value, source=source, origin='observed' if value is not None else 'unavailable')


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
    """Capture every matching visible mount, anchored to raw membership/mountinfo."""
    membership,mountinfo=read('/proc/self/cgroup'),read('/proc/self/mountinfo')
    meta=mounts_for(membership,mountinfo)
    views=[]
    for view in meta:
        point,root=PurePosixPath(view['mountpoint']),PurePosixPath(view['root'])
        current=PurePosixPath(view['leaf']);entries=[]
        while True:
            if len(entries)>=64: raise ValueError('cgroup ancestry depth limit')
            row=dict(path=str(current),cgroup_path=str(root/current.relative_to(point)))
            for name in ('cpu.max','cpuset.cpus.effective','memory.max','memory.current'):
                value=read(str(current/name))
                if value is None:raise ValueError('missing cgroup ancestor field: '+str(current/name))
                row[name]=value
            entries.append(row)
            if current==point:break
            current=current.parent
        views.append(dict(view,ancestors=entries))
    return reconcile_cgroups(dict(membership=membership,mountinfo=mountinfo,views=views,
        effective_cpuset=None,quota_pairs=None,memory_headroom_bytes=None,visibility=None))


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
                           linkage='candidate-library')
    return compiler, runtime


def mapped_runtime(pid, executable, read=read_text):
    """Observe an existing process, recording reconstructible mapping evidence."""
    if executable is None:return None
    try:
        integer(pid,1,1<<30,'runtime PID')
        before,maps=read(f'/proc/{pid}/stat'),read(f'/proc/{pid}/maps')
        start=process_identity(before,pid)
        if not maps:return None
        wanted=file_hash(executable)
        if file_hash(f'/proc/{pid}/exe')!=wanted:return None
        lines=[];paths=set()
        for line in maps.splitlines():
            parts=line.split(None,5)
            if len(parts)==6 and re.fullmatch(r'libgomp\.so\.[0-9.]+',Path(parts[5]).name):
                lines.append(line);paths.add(parts[5])
        if len(paths)!=1:return None
        path=paths.pop();absolute_path(path)
        actual=Path(f'/proc/{pid}/root')/path.lstrip('/')
        info=actual.stat()
        result=dict(path=path,sha256=file_hash(actual),soname='libgomp.so.1',
                    linkage='observed-process-mapping',executable_sha256=wanted,pid=pid,
                    process_stat=before,process_start_ticks=start,mappings=lines,
                    file_identity=dict(device_major=os.major(info.st_dev),device_minor=os.minor(info.st_dev),
                                       inode=info.st_ino,size=info.st_size,mtime_ns=info.st_mtime_ns))
        validate_runtime(result)
        final=actual.stat()
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)!=(final.st_dev,final.st_ino,final.st_size,final.st_mtime_ns):return None
        if (process_identity(read(f'/proc/{pid}/stat'),pid)!=start or
                read(f'/proc/{pid}/maps')!=maps or file_hash(f'/proc/{pid}/exe')!=wanted):return None
        return result
    except (OSError,ValueError):return None


def inspect(executable=None, read=read_text, affinity=None, binaries=True, pid=None):
    if affinity is None:
        try: affinity = sorted(os.sched_getaffinity(0))
        except (OSError, AttributeError): affinity = None
    if affinity is not None:
        if len(affinity) > 4096: raise ValueError('affinity CPU count limit')
        affinity = sorted(affinity)
    cpuinfo = read('/proc/cpuinfo')
    model = next((l.split(':',1)[1].strip() for l in (cpuinfo or '').splitlines() if l.startswith('model name')), None)
    topology,nodes,online=None,None,None
    try:online=cpu_list(read('/sys/devices/system/cpu/online'))
    except ValueError:pass
    if online is not None:
        try:
            topology=[]
            for cpu in online:
                prefix=f'/sys/devices/system/cpu/cpu{cpu}'
                package,core=read(prefix+'/topology/physical_package_id'),read(prefix+'/topology/core_id')
                if package is None or core is None or not package.isdigit() or not core.isdigit():
                    raise ValueError('CPU topology missing')
                topology.append(dict(cpu=cpu,package=int(package),core=int(core),
                                     siblings=cpu_list(read(prefix+'/topology/thread_siblings_list'))))
        except ValueError:topology=None
    try:
        nodes=[]
        for n in cpu_list(read('/sys/devices/system/node/online')):
            text=read(f'/sys/devices/system/node/node{n}/cpulist')
            nodes.append(dict(node=n,cpus=[] if text=='' else cpu_list(text)))
    except ValueError:nodes=None
    frequency=[dict(cpu=c,governor=read(f'/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_governor'),
                    driver=read(f'/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_driver'),
                    current_khz=read(f'/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_cur_freq'),
                    min_khz=read(f'/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_min_freq'),
                    max_khz=read(f'/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_max_freq')) for c in (affinity or [])]
    group_error=None
    try:groups=cgroup_ancestry(read)
    except ValueError as error:
        groups=None;group_error='Cgroup evidence unavailable: '+str(error)
    available = None
    for line in (read('/proc/meminfo') or '').splitlines():
        if re.fullmatch(r'MemAvailable:\s+[0-9]+ kB', line): available = int(line.split()[1])*1024
    if available is not None and groups is not None and groups['memory_headroom_bytes'] is not None:
        available = min(available, groups['memory_headroom_bytes'])
    compiler, runtime = binary_identity(executable) if binaries else (None, None)
    if pid is not None:
        integer(pid, 1, 1 << 30, 'process ID')
        runtime = mapped_runtime(pid, executable, read)
    return dict(schema='dynagraph-hardware', schema_version=2,
        cpu_model=observation(model, '/proc/cpuinfo'),
        logical_cpus=observation(len(online) if online else None, 'sysfs online CPU IDs; not a physical allocation'),
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
        openmp=observation(runtime, 'existing-process mapping evidence' if pid is not None else 'ELF dependency inspection; candidate library identity'),
        executable_sha256=observation(file_hash(executable) if executable else None, 'inspected executable bytes'),
        placement=observation(dict(taskset=shutil.which('taskset')), 'available placement command; no affinity change'),
        frequency=observation(frequency, 'sysfs cpufreq; missing fields remain null'),
        limitations=['No exclusivity attestation', 'No actual OpenMP team observed',
                    'No benchmark executed', 'Hidden cgroup ancestors and host scheduling unverified',
                    'Runtime mappings are snapshots; build flags require separate verified evidence']+([group_error] if group_error else []))


def admit(plan, report):
    p = validate_plan(plan)
    keys = ('cpu_model logical_cpus topology numa affinity cgroups available_memory_bytes os kernel '
            'virtualization compiler openmp executable_sha256 placement frequency').split()
    fields(report, 'schema schema_version '+' '.join(keys)+' limitations', 'hardware report')
    if report['schema'] != 'dynagraph-hardware' or type(report['schema_version']) is not int or report['schema_version'] != 2:
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
    try:optional_observations(report)
    except (ValueError,TypeError):failures.append('malformed optional hardware provenance')
    cpus = h['allocated_cpus']
    affinity = value('affinity')
    require(type(affinity) is list and all(type(c) is int for c in affinity) and affinity == cpus, 'effective affinity must equal declared allocation')
    require(type(value('logical_cpus')) is int and type(value('topology')) is list and
            value('logical_cpus')==len(value('topology')), 'contradictory logical CPU count')
    try:
        ids=topology_ids(value('topology'),value('logical_cpus'),value('numa'))
        cores={(ids[c]['package'],ids[c]['core']) for c in cpus}
        require(len(cores)>=h['min_physical_cores'],'insufficient physical cores')
        require(h['allow_smt'] or len(cores)==len(cpus),'SMT siblings disallowed')
    except (ValueError,KeyError,TypeError):
        failures.append('missing or contradictory physical topology')
    try:
        groups=validate_cgroups(value('cgroups'))
        require(set(cpus)<=set(groups['effective_cpuset']),'allocation outside effective cgroup cpuset')
        largest=max(c['workers'] for c in p['configurations'])
        for quota,period in groups['quota_pairs']:
            require(quota>=largest*period,'ancestor CPU quota below requested workers')
        headroom=groups['memory_headroom_bytes']
        if headroom is not None:
            require(type(value('available_memory_bytes')) is int and value('available_memory_bytes')<=headroom,
                    'available memory contradicts cgroup headroom')
    except (ValueError,TypeError):failures.append('missing or malformed cgroup ancestry')
    memory = value('available_memory_bytes')
    require(type(memory) is int and memory >= h['min_available_memory_bytes'], 'insufficient or unavailable memory')
    virt = value('virtualization')
    require(type(virt) is dict and type(virt.get('hypervisor')) is bool and type(virt.get('container')) is bool and
            (h['allow_virtualization'] or not (virt['hypervisor'] or virt['container'])), 'virtualization unavailable or disallowed')
    compiler=value('compiler')
    try:
        fields(compiler,'path version sha256','compiler identity')
        absolute_path(compiler['path']);digest(compiler['sha256'])
        if type(compiler['version']) is not str or not compiler['version'].strip():raise ValueError('missing compiler version')
        require(compiler['sha256']==p['build']['compiler_sha256'],'missing or mismatched compiler identity')
    except (ValueError,TypeError):failures.append('missing or mismatched compiler identity')
    runtime=value('openmp')
    try:
        validate_runtime(runtime)
        require(runtime['sha256']==p['build']['openmp_sha256'],'missing or mismatched openmp identity')
        require(runtime['linkage']=='observed-process-mapping' and
                runtime.get('executable_sha256')==p['build']['executable_sha256'],
                'actual linked OpenMP runtime resolution is unverified')
    except (ValueError,TypeError):failures.append('missing or contradictory OpenMP mapping evidence')
    require(value('executable_sha256')==p['build']['executable_sha256'],'missing or mismatched executable identity')
    freq = value('frequency')
    if h['require_frequency_evidence']:
        require(type(freq) is list and {r.get('cpu') for r in freq if type(r) is dict and type(r.get('cpu')) is int and
                type(r.get('governor')) is str and r['governor'].strip()} >= set(cpus),
                'missing frequency/governor evidence')
    development = h['mode']=='development'
    return dict(schema='dynagraph-campaign-admission', schema_version=2,
                campaign_id=p['campaign_id'], plan_sha256=plan_hash(p),
                hardware_sha256=hashlib.sha256(canonical_json(report)).hexdigest(),
                mode=h['mode'], admitted=development or not failures,
                scientific_performance_allowed=not development and not failures,
                multicore_scaling_claims_allowed=False,
                qualification='development-only' if development else ('qualified-on-evidence' if not failures else 'rejected'),
                failures=failures, declarations=dict(origin='user_declared', exclusive=h['exclusive'], reservation=h['reservation']),
                limitations=report['limitations'])
