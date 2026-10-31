"""Linux self-affinity barrier v1. Local receipts are not authenticated attestation."""
import copy
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
import time

from campaign_contract import fields, digest, integer, load_bytes
from campaign_provenance import cpu_array, cpu_list, process_identity, validate_cgroups
from campaign_hardware import cgroup_ancestry
from campaign_runtime import read_metadata, time_range
from campaign_process import timestamp
from workloads import canonical_json, sha256

POLICY = 'linux-self-affinity-barrier-v1; development-only'
INHERIT = 'inherit; requested plan affinity recorded, not applied'
STATES = ('requested', 'validated', 'application_pending', 'applied', 'verified',
          'rejected', 'indeterminate', 'interrupted')
LIMITATIONS = ['Local integrity checks are not external authentication',
               'Leader pre-exec observations are not worker-team or stable placement evidence',
               'No exclusivity, isolation, uncontended execution or scientific eligibility',
               'Visible cgroup2 only; hidden host restrictions remain unverified']


class EnforcementError(ValueError):
    pass


def permitted(cpus, workers, affinity, online, groups):
    cpu_array(cpus);integer(workers, 1, 64, 'enforcement workers')
    cpu_array(affinity);cpu_array(online);validate_cgroups(groups)
    if not set(cpus)<=set(affinity) or not set(cpus)<=set(online):
        raise EnforcementError('requested CPUs unavailable in effective/online set')
    if not set(cpus)<=set(groups['effective_cpuset']):
        raise EnforcementError('requested CPUs outside visible effective cpuset')
    if any(q<workers*p for q,p in groups['quota_pairs']):
        raise EnforcementError('visible CPU quota insufficient for requested workers')


def preflight(cpus, workers):
    cpu_array(cpus);integer(workers, 1, 64, 'enforcement workers')
    if sys.platform!='linux' or not hasattr(os, 'sched_setaffinity') or os.execve not in os.supports_fd:
        raise EnforcementError('Linux affinity and descriptor exec required')
    online = read_metadata('/sys/devices/system/cpu/online')
    groups = cgroup_ancestry(read_metadata)
    permitted(cpus, workers, sorted(os.sched_getaffinity(0)), cpu_list(online), groups)


def observe(pid):
    """Read the blocked child, not the observer's affinity or cgroup membership."""
    start = timestamp();prefix=f'/proc/{pid}'
    before=read_metadata(prefix+'/stat')
    if before is None or before.rsplit(') ',1)[-1][0] in 'ZXx':
        raise EnforcementError('child unavailable before verification')
    ticks=process_identity(before,pid)
    affinity=sorted(os.sched_getaffinity(pid))
    groups=cgroup_ancestry(lambda p:read_metadata(p.replace('/proc/self/',prefix+'/')))
    online=cpu_list(read_metadata('/sys/devices/system/cpu/online'))
    after=read_metadata(prefix+'/stat')
    if after is None or after.rsplit(') ',1)[-1][0] in 'ZXx' or process_identity(after,pid)!=ticks:
        raise EnforcementError('child exited or process identity changed during verification')
    return dict(start=start,end=timestamp(),pid=pid,process_stat=before,
                process_start_ticks=ticks,affinity=affinity,online_cpus=online,cgroups=groups,
                source='parent sched_getaffinity and /proc child identity/cgroup2; sysfs online')


def binding(bound, trial, index, origin, command, executable, ownership_sha256):
    digest(ownership_sha256)
    attempt_id = (origin['attempt_id'] if origin['kind']=='resume' else
                  sha256(canonical_json(dict(execution_id=bound['pilot_execution_id'],
                                             pilot_ownership_sha256=ownership_sha256))))
    digest(attempt_id)
    return dict(execution_id=bound['pilot_execution_id'],trial_id=trial['trial_id'],attempt_id=attempt_id,
                journal_binding_sha256=sha256(canonical_json(bound)),process_index=index,
                origin=copy.deepcopy(origin),command=command,executable_sha256=executable,
                workers=trial['workers'])


def receipt(request):
    return dict(schema='dynagraph-affinity-enforcement',schema_version=1,
                binding=copy.deepcopy(request['binding']),requested_cpus=copy.deepcopy(request['cpus']),
                lifecycle=['requested'],state='requested',acknowledgement=None,observation=None,
                released=False,release_timestamp=None,error=None,measurement_eligible=False,
                scientific_performance_allowed=False,execution_authorized=False,
                limitations=list(LIMITATIONS))


def seal(value):
    value=copy.deepcopy(value);value.pop('evidence_sha256',None)
    value['evidence_sha256']=sha256(canonical_json(value))
    return value


def ack_shape(a):
    fields(a,'pid process_stat requested_cpus applied_cpus executable_sha256 timestamp errno error','affinity acknowledgement')
    integer(a['pid'],1,1<<30,'ack PID');integer(a['errno'],0,4095,'affinity errno')
    cpu_array(a['requested_cpus'])
    if a['applied_cpus'] is not None:cpu_array(a['applied_cpus'])
    if a['executable_sha256'] is not None:digest(a['executable_sha256'])
    if a['timestamp'] is not None:time_range(a['timestamp'],a['timestamp'])
    if a['process_stat'] is not None:process_identity(a['process_stat'],a['pid'])
    if a['error'] is not None and (type(a['error']) is not str or not 1<=len(a['error'])<=1024):
        raise ValueError('invalid acknowledgement error')


def observation_shape(o):
    fields(o,'start end pid process_stat process_start_ticks affinity online_cpus cgroups source','affinity parent observation')
    integer(o['pid'],1,1<<30,'observation PID');integer(o['process_start_ticks'],1,(1<<63)-1,'observation start ticks')
    if process_identity(o['process_stat'],o['pid'])!=o['process_start_ticks']:
        raise ValueError('observation process start mismatch')
    cpu_array(o['affinity']);cpu_array(o['online_cpus']);validate_cgroups(o['cgroups'])
    time_range(o['start'],o['end'])
    if o['source']!='parent sched_getaffinity and /proc child identity/cgroup2; sysfs online':
        raise ValueError('unsupported enforcement observation source')


def validate_ack(a, pid, cpus, executable):
    ack_shape(a)
    if a['pid']!=pid or canonical_json(a['requested_cpus'])!=canonical_json(cpus):
        raise EnforcementError('acknowledgement process/request mismatch')
    if a['error'] is not None:
        if type(a['error']) is not str or not 1<=len(a['error'])<=1024:
            raise EnforcementError('invalid acknowledgement failure')
        raise EnforcementError('child affinity application failed: '+a['error'])
    if a['errno']!=0 or a['executable_sha256']!=executable:
        raise EnforcementError('acknowledgement executable/errno mismatch')
    cpu_array(a['applied_cpus'])
    if a['applied_cpus']!=cpus:
        raise EnforcementError('applied affinity differs from requested affinity')
    time_range(a['timestamp'],a['timestamp'])
    if a['process_stat'] is None or a['process_stat'].rsplit(') ',1)[-1][0] in 'ZXx':
        raise EnforcementError('exited child acknowledgement')
    return process_identity(a['process_stat'],pid)


class Barrier:
    """Own pipes/descriptors until cleanup; workload release is one explicit byte."""
    def __init__(self, request, command, cwd, environment, stop):
        self.request=request;self.command=command;self.cwd=cwd;self.environment=environment
        self.stop=stop;self.value=receipt(request);self.fds=[];self.pid=None;self.process=None

    def boundary(self):
        if time.monotonic()>=self.stop:raise TimeoutError('affinity enforcement deadline expired')

    def spawn(self):
        self.boundary();preflight(self.request['cpus'],self.request['binding']['workers']);self.boundary()
        self.value['lifecycle'].append('validated')
        target=os.open(str(Path(self.cwd)/self.command[0]),os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
        self.fds.append(target);self.target=target
        if not stat.S_ISREG(os.fstat(target).st_mode):raise EnforcementError('executable must be regular')
        with os.fdopen(os.dup(target),'rb') as stream:
            raw=stream.read(64*1048576+1)
        os.lseek(target,0,os.SEEK_SET)
        if len(raw)>64*1048576 or sha256(raw)!=self.request['binding']['executable_sha256']:
            raise EnforcementError('pinned executable identity mismatch before child launch')
        ar,aw=os.pipe();self.fds.extend((ar,aw));gr,gw=os.pipe();self.fds.extend((gr,gw))
        self.ack=ar;self.gate=gw
        helper=Path(__file__).with_name('campaign_affinity_child.py')
        argv=[sys.executable,'-I','-S','-B',str(helper),str(aw),str(gr),str(target),
              canonical_json(self.request['cpus']).decode().strip(),self.request['binding']['executable_sha256'],
              repr(self.stop),*self.command]
        self.boundary();self.value['lifecycle'].append('application_pending');self.boundary()
        self.process=subprocess.Popen(argv,cwd=self.cwd,env=self.environment,stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,
                                 pass_fds=(aw,gr,target))
        process=self.process;self.pid=process.pid
        for fd in (aw,gr):os.close(fd);self.fds.remove(fd)
        return process

    def verify_and_release(self, process):
        self.boundary();raw=bytearray();os.set_blocking(self.ack,False)
        with selectors.DefaultSelector() as sel:
            sel.register(self.ack,selectors.EVENT_READ)
            while not raw.endswith(b'\n'):
                self.boundary()
                if not sel.select(min(0.05,max(0,self.stop-time.monotonic()))):continue
                data=os.read(self.ack,65536)
                if not data:raise EnforcementError('child exited before acknowledgement')
                raw.extend(data)
                if len(raw)>65536:raise EnforcementError('acknowledgement size limit')
        self.boundary();a=load_bytes(bytes(raw));self.value['acknowledgement']=a
        ticks=validate_ack(a,process.pid,self.request['cpus'],self.request['binding']['executable_sha256'])
        self.value['lifecycle'].append('applied');self.boundary()
        o=observe(process.pid);self.value['observation']=o
        if o['pid']!=process.pid or o['process_start_ticks']!=ticks or process.poll() is not None:
            raise EnforcementError('child identity mismatch or exit before release')
        if o['affinity']!=self.request['cpus']:
            raise EnforcementError('independent effective affinity mismatch')
        permitted(self.request['cpus'],self.request['binding']['workers'],o['affinity'],o['online_cpus'],o['cgroups'])
        # Recheck pinned staged bytes before GO. A hostile same-UID writer after
        # this check is outside local integrity guarantees (not authentication).
        os.lseek(self.target,0,os.SEEK_SET)
        with os.fdopen(os.dup(self.target),'rb') as stream:
            raw=stream.read(64*1048576+1)
        os.lseek(self.target,0,os.SEEK_SET)
        if len(raw)>64*1048576 or sha256(raw)!=self.request['binding']['executable_sha256']:
            raise EnforcementError('executable changed before workload release')
        time_range(a['timestamp'],o['start']);self.boundary()
        self.value['lifecycle'].append('verified')
        # No journal I/O or observation after this final check and before GO.
        release=timestamp()
        candidate=copy.deepcopy(self.value)
        candidate.update(state='verified',released=True,release_timestamp=release)
        load_bytes(canonical_json(seal(candidate)))  # Metadata cap before authorizing exec.
        self.boundary()
        if os.write(self.gate,b'G')!=1:raise EnforcementError('workload release failed')
        self.value=candidate
        os.close(self.gate);self.fds.remove(self.gate)

    def fail(self, state, error):
        self.value.update(state=state,error=str(error)[:2048])
        self.value['lifecycle'].append(state)

    def close(self):
        for fd in self.fds:os.close(fd)
        self.fds=[]


def verify(value, expected, cpus, process, runtime_snapshot=None):
    """Offline semantic reconciliation in addition to inventory/digest checks."""
    load_bytes(canonical_json(value))
    fields(value,'schema schema_version binding requested_cpus lifecycle state acknowledgement observation released release_timestamp error measurement_eligible scientific_performance_allowed execution_authorized limitations evidence_sha256','affinity enforcement')
    if value['schema']!='dynagraph-affinity-enforcement' or type(value['schema_version']) is not int or value['schema_version']!=1:
        raise ValueError('unsupported affinity enforcement schema')
    if canonical_json(value['binding'])!=canonical_json(expected) or canonical_json(value['requested_cpus'])!=canonical_json(cpus):
        raise ValueError('affinity receipt execution/trial/request mismatch')
    cpu_array(cpus);digest(value['evidence_sha256'])
    if value!=seal(value):raise ValueError('affinity evidence digest mismatch')
    if any(value[k] is not False for k in ('measurement_eligible','scientific_performance_allowed','execution_authorized')) or value['limitations']!=LIMITATIONS:
        raise ValueError('unsupported affinity authority claim')
    path=value['lifecycle'];prefix=['requested','validated','application_pending','applied','verified']
    if type(path) is not list or len(path)<2 or path[0]!='requested' or any(type(s) is not str or s not in STATES for s in path):
        raise ValueError('invalid enforcement lifecycle')
    success=value['state']=='verified'
    if success:
        if path!=prefix or value['released'] is not True or value['error'] is not None:
            raise ValueError('contradictory verified enforcement')
    elif (value['state'] not in ('rejected','indeterminate','interrupted') or path[-1]!=value['state'] or
          path[:-1]!=prefix[:len(path)-1] or len(path)>6 or value['released'] is not False or
          value['release_timestamp'] is not None or type(value['error']) is not str or not 1<=len(value['error'])<=2048 or
          process['reason']=='exited'):
        raise ValueError('contradictory unsuccessful enforcement')
    if success and process['returncode'] is None:
        raise ValueError('verified enforcement requires an actual child exit receipt')
    if value['state']=='interrupted' and process['reason']!='interrupted':
        raise ValueError('enforcement interruption/process mismatch')
    a=value['acknowledgement'];o=value['observation']
    if a is not None:ack_shape(a)
    if o is not None:
        observation_shape(o)
        if 'applied' not in path:raise ValueError('observation without applied acknowledgement')
    # Partial failure diagnostics are bounded JSON, never a successful observation.
    if 'applied' in path or success:
        if a is None:raise ValueError('missing applied acknowledgement')
        ticks=validate_ack(a,a['pid'],cpus,expected['executable_sha256'])
        time_range(process['start'],a['timestamp']);time_range(a['timestamp'],process['end'])
    if 'verified' in path or success:
        if o is None:raise ValueError('missing parent verification')
        fields(o,'start end pid process_stat process_start_ticks affinity online_cpus cgroups source','affinity parent observation')
        if (o['pid']!=a['pid'] or type(o['pid']) is not int or type(o['process_start_ticks']) is not int or
                o['process_start_ticks']!=ticks or process_identity(o['process_stat'],o['pid'])!=ticks or
                o['process_stat'].rsplit(') ',1)[-1][0] in 'ZXx' or o['affinity']!=cpus or
                o['source']!='parent sched_getaffinity and /proc child identity/cgroup2; sysfs online'):
            raise ValueError('contradictory parent process/affinity observation')
        permitted(cpus,expected['workers'],o['affinity'],o['online_cpus'],o['cgroups'])
        time_range(a['timestamp'],o['start']);time_range(o['start'],o['end']);time_range(o['end'],process['end'])
    if runtime_snapshot is not None and a is not None:
        if runtime_snapshot['pid']!=a['pid']:
            raise ValueError('enforcement/runtime PID mismatch')
        if ('applied' in path and runtime_snapshot['process_start_ticks'] is not None and
                runtime_snapshot['process_start_ticks']!=ticks):
            raise ValueError('enforcement/runtime start identity mismatch')
    if success:
        time_range(o['end'],value['release_timestamp']);time_range(value['release_timestamp'],process['end'])
    return value
