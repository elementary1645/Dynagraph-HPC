"""Development runtime provenance v1. Snapshots are not authenticated execution proof."""
from datetime import datetime
import os
import errno
import platform
import stat

from campaign_contract import fields, digest, integer
from campaign_provenance import cpu_list, cpu_array, process_identity, validate_runtime, validate_cgroups
from campaign_hardware import mapped_runtime, cgroup_ancestry
from workloads import canonical_json, sha256

MARKER = 'runtime-provenance-v1; child snapshots; OpenMP execution unavailable'
LIMIT = 1048576


def read_metadata(path):
    """Bound pseudo-file reads too; never block on a FIFO or accept a leaf symlink."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('runtime metadata must be regular')
            raw = stream.read(LIMIT+1)
            after = os.fstat(stream.fileno())
            if (before.st_dev, before.st_ino, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_mtime_ns):
                raise ValueError('runtime metadata changed')
        if len(raw) > LIMIT:
            raise ValueError('runtime metadata limit')
        return raw.decode('utf-8').strip()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    except OSError as error:
        # Linux may return EINVAL for mountinfo after the target becomes a zombie.
        if str(path).startswith('/proc/') and error.errno == errno.EINVAL:
            return None
        raise


def fact(value, source, scope):
    return dict(value=value, source=source, scope=scope,
                status='unavailable' if value is None else 'observed')


def collect(pid, executable, expected_hash):
    """One post-spawn snapshot, no retries, child pausing, placement or test region.

    Exec/exit races are explicit missing observations. A proven identity change
    within a snapshot is contradictory and is rejected.
    """
    from campaign_process import timestamp
    integer(pid, 1, 1 << 30, 'child PID')
    start = timestamp()
    prefix = f'/proc/{pid}'
    before = read_metadata(prefix+'/stat')
    identity = process_identity(before, pid) if before is not None else None
    # /proc/PID/exe is a kernel-owned magic link; inspect through one descriptor.
    from campaign_pilot import MAX_EXECUTABLE
    actual = None
    try:
        with open(prefix+'/exe', 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('nonregular process executable')
            raw = stream.read(MAX_EXECUTABLE+1)
        if len(raw) > MAX_EXECUTABLE:
            raise ValueError('process executable limit')
        actual = sha256(raw)
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
    # Script launchers and pre-exec/interpreter transitions are not an identity
    # match. Do not ascribe interpreter affinity/runtime to the staged binary.
    matched = actual == expected_hash and identity is not None and before.rsplit(') ', 1)[-1][0] not in 'ZXx'
    affinity = None
    if matched:
        try: affinity = sorted(os.sched_getaffinity(pid))
        except (ProcessLookupError, PermissionError): pass
    runtime = mapped_runtime(pid, executable, read=read_metadata) if matched else None
    groups = None
    group_error = None
    if matched:
        def child_read(path):
            return read_metadata(path.replace('/proc/self/', prefix+'/'))
        try: groups = cgroup_ancestry(child_read)
        except ValueError as error:
            message = str(error)
            if message.startswith(('missing cgroup', 'unified cgroup', 'noncanonical absolute',
                                   'cgroup mount does not resolve', 'missing or excessive cgroup mount evidence')):
                group_error = message
            else:
                raise
    after = read_metadata(prefix+'/stat')
    if before is not None and after is not None and process_identity(after, pid) != identity:
        raise ValueError('child launch identity changed during observation')
    if after is None or after.rsplit(') ', 1)[-1][0] in 'ZXx':
        matched = False
        affinity = runtime = groups = None
    online = read_metadata('/sys/devices/system/cpu/online')
    result = dict(start=start, end=timestamp(), pid=pid, process_stat=before,
                process_start_ticks=identity, executable_match=matched,
                observed_executable_sha256=actual,
                affinity=fact(affinity, 'sched_getaffinity(child PID)', 'child leader snapshot'),
                cgroups=fact(groups, '/proc/child/cgroup and mountinfo; visible cgroup2 ancestry', 'child process visible hierarchy'),
                openmp=fact(runtime, '/proc/child/maps and bounded ELF metadata', 'child process mapping snapshot'),
                online_cpus=fact(cpu_list(online) if online else None, 'sysfs cpu/online', 'observer namespace'),
                kernel=fact(platform.release(), 'uname', 'observer kernel'),
                os=fact(read_metadata('/usr/lib/os-release'), '/usr/lib/os-release', 'observer namespace'),
                limitations=['Snapshot is not atomic or authenticated',
                            'Exec/exit race or interpreter launch may make child observations unavailable',
                            'Hidden host cgroups, contention and physical-core exclusivity unverified',
                            'Mapped OpenMP library does not prove worker execution']+
                            (['Cgroup source unavailable/unsupported: '+group_error] if group_error else []))
    result['end'] = timestamp()
    validate_snapshot(result, expected_hash)
    return result


def time_range(a, b):
    try:
        x, y = datetime.fromisoformat(a), datetime.fromisoformat(b)
        if x.utcoffset() is None or y.utcoffset() is None or x > y:
            raise ValueError('runtime timestamp order')
    except (ValueError, TypeError) as error:
        raise ValueError('invalid runtime timestamp') from error


def validate_snapshot(value, executable_hash):
    fields(value, 'start end pid process_stat process_start_ticks executable_match observed_executable_sha256 affinity cgroups openmp online_cpus kernel os limitations', 'runtime snapshot')
    time_range(value['start'], value['end'])
    integer(value['pid'], 1, 1 << 30, 'child PID')
    if type(value['executable_match']) is not bool:
        raise ValueError('invalid executable match')
    if value['process_stat'] is not None:
        integer(value['process_start_ticks'], 1, (1 << 63)-1, 'process start ticks')
        if process_identity(value['process_stat'], value['pid']) != value['process_start_ticks']:
            raise ValueError('contradictory process identity')
    elif value['process_start_ticks'] is not None:
        raise ValueError('missing process stat')
    actual = value['observed_executable_sha256']
    if actual is not None: digest(actual)
    if value['executable_match'] and (actual != executable_hash or value['process_stat'] is None):
        raise ValueError('conflicting executable identity')
    if value['executable_match'] and value['process_stat'].rsplit(') ', 1)[-1][0] in 'ZXx':
        raise ValueError('exited process cannot bind child observations')
    for key in ('affinity', 'cgroups', 'openmp', 'online_cpus', 'kernel', 'os'):
        row = value[key]
        fields(row, 'value source scope status', 'runtime fact')
        if any(type(row[k]) is not str or not row[k] for k in ('source','scope')):
            raise ValueError('invalid runtime observation scope/source')
        if row['status'] != ('unavailable' if row['value'] is None else 'observed'):
            raise ValueError('contradictory runtime availability')
        v = row['value']
        if v is None: continue
        if key in ('affinity','online_cpus'): cpu_array(v)
        elif key == 'cgroups': validate_cgroups(v)
        elif key == 'openmp':
            validate_runtime(v)
            if (v['linkage'] != 'observed-process-mapping' or v['pid'] != value['pid'] or
                    v['process_start_ticks'] != value['process_start_ticks'] or
                    v['executable_sha256'] != executable_hash):
                raise ValueError('conflicting OpenMP runtime identity')
        elif type(v) is not str or not v.strip():
            raise ValueError('invalid OS/kernel identity')
    if not value['executable_match'] and any(value[k]['value'] is not None for k in ('affinity','cgroups','openmp')):
        raise ValueError('unbound child observation')
    if type(value['limitations']) is not list or any(type(v) is not str for v in value['limitations']):
        raise ValueError('invalid runtime limitations')
    return value


def provenance(bound, trial, process, snapshot, origin, executable_hash):
    return dict(schema='dynagraph-runtime-provenance', schema_version=1,
                execution_id=bound['pilot_execution_id'], journal_binding_sha256=sha256(canonical_json(bound)),
                trial_id=trial['trial_id'], origin=origin,
                command=process['command'], executable_sha256=executable_hash,
                collection_phase='post-spawn', requested_workers=trial['workers'],
                requested_openmp_environment=bound['environment'][trial['trial_id']],
                snapshot=snapshot, observed_team_size=None, relevant_parallel_regions=None,
                intended_workload_observed=False, team_observation_scope='unavailable; timed metrics disabled',
                measurement_eligible=False, development_only=True)


def verify(value, bound, record, process, origin):
    fields(value, 'schema schema_version execution_id journal_binding_sha256 trial_id origin command executable_sha256 collection_phase requested_workers requested_openmp_environment snapshot observed_team_size relevant_parallel_regions intended_workload_observed team_observation_scope measurement_eligible development_only', 'runtime provenance')
    if value['schema'] != 'dynagraph-runtime-provenance' or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('unsupported runtime provenance schema')
    expected = provenance(bound, record['trial'], process, value['snapshot'], origin, record['executable_sha256'])
    if canonical_json(value) != canonical_json(expected):
        raise ValueError('contradictory runtime provenance binding or team observation')
    if value['snapshot'] is not None:
        validate_snapshot(value['snapshot'], record['executable_sha256'])
        time_range(process['start'], value['snapshot']['start'])
        time_range(value['snapshot']['end'], process['end'])
