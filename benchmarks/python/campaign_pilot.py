"""Phase 6B-2A: explicit bounded development pilots, never scientific evidence."""
import os
from datetime import datetime
from pathlib import Path
import stat
import tempfile
import time

from artifacts import generate, verify, validate_manifest
from campaign_contract import (digest, expand, fields, integer, path_text,
                               plan_hash, load_bytes, safe_path, validate_plan)
from campaign_hardware import admit, inspect
from campaign_process import capture, timestamp
from campaign_oracle import METHOD, reconcile
from campaign_provenance import cpu_array
from experiment_records import loads, read_jsonl, validate_worker, verify_preflight
from run import host_metadata
from workloads import canonical_json, graph_dimensions, sha256

MAX_TRIALS = 8
MAX_SECONDS = 120
MAX_TIMEOUT = 30
MAX_OUTPUT = 1048576
MAX_EXECUTABLE = 64 * 1048576
MAX_ARTIFACT = 1048576
REASONS = ('success', 'unverified', 'input-error', 'correctness-failed', 'protocol-failed',
           'timeout', 'output-limit', 'interrupted', 'launch-error', 'capture-error',
           'signal', 'nonzero-exit', 'budget-exhausted', 'not-run')


class OracleUnavailable(ValueError):
    """No supported bounded independent-oracle execution for this workload."""


def atomic_bytes(path, data, mode=0o600):
    """Publish a complete file with link(2)'s exclusive, no-replace semantics."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        os.unlink(temporary)


def put(directory, name, value):
    atomic_bytes(directory/name, canonical_json(value))


def regular_bytes(path, limit):
    # O_NONBLOCK prevents named pipes from hanging validation; refuse symlinks.
    absolute = Path(path).absolute()
    directory_fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in absolute.parts[1:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        fd = os.open(absolute.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                     dir_fd=directory_fd)
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('regular file required')
            data = stream.read(limit+1)
    finally:
        os.close(directory_fd)
    if len(data) > limit:
        raise ValueError('pilot file size limit')
    return data


def read_json(path):
    """All pilot metadata uses the same descriptor-checked bounded reader."""
    return load_bytes(regular_bytes(path, MAX_ARTIFACT))


def contained(root, reference):
    safe_path(reference)
    candidate = root/reference
    current = root
    for part in Path(reference).parts:
        current = current/part
        if current.is_symlink():
            raise ValueError('pilot input symlinks unsupported')
    candidate.resolve().relative_to(root)
    return candidate


def select(plan, manifest, trial_ids, max_trials=1):
    validate_plan(plan)
    if plan['hardware']['mode'] != 'development':
        raise ValueError('pilot supports development mode only')
    # Canonical comparison catches bool/int aliases, altered identities, unknown
    # fields, duplicate rows and ordering changes without trusting supplied labels.
    if canonical_json(manifest) != canonical_json(expand(plan)):
        raise ValueError('trial manifest differs from deterministic expansion')
    integer(max_trials, 1, MAX_TRIALS, 'pilot trial limit')
    if type(trial_ids) is not list or not trial_ids or len(trial_ids) > max_trials:
        raise ValueError('explicit bounded trial IDs required')
    for value in trial_ids:
        digest(value)
    if len(set(trial_ids)) != len(trial_ids):
        raise ValueError('duplicate pilot trial ID')
    requested = set(trial_ids)
    selected = [t for t in manifest['trials'] if t['trial_id'] in requested]
    if len(selected) != len(requested):
        raise ValueError('unknown pilot trial ID')
    return selected


def bounds(plan, max_trials, wall_seconds, timeout, output_limit):
    integer(max_trials, 1, MAX_TRIALS, 'pilot trial limit')
    integer(wall_seconds, 1, MAX_SECONDS, 'pilot wall seconds')
    integer(timeout, 1, min(MAX_TIMEOUT, plan['limits']['timeout_seconds']), 'pilot timeout')
    integer(output_limit, 1, min(MAX_OUTPUT, plan['limits']['max_output_bytes']), 'pilot stream bytes')


def stage_inputs(root, directory, workload, executable, executable_hash):
    # Fail before executing on workload sizes outside the small independent-oracle
    # subset. Bundle verification then regenerates only a bounded graph/trace.
    source = contained(root, workload['bundle'])
    raw = {name: regular_bytes(source/name, MAX_ARTIFACT)
           for name in ('manifest.json', 'graph.txt', 'trace.txt')}
    manifest = loads(raw['manifest.json'])
    validate_manifest(manifest)
    counts = manifest['counts']
    vertices, edges = graph_dimensions(manifest['configuration']['graph'])
    if manifest['split'] != 'development':
        raise ValueError('unsupported pilot workload split')
    if (max(vertices, counts['vertices']) > 128 or max(edges, counts['edges']) > 4096 or
            max(manifest['configuration']['trace']['count'], counts['updates']) > 256):
        raise OracleUnavailable('workload outside bounded pilot oracle subset; not executed')
    if (manifest['configuration'] != workload['recipe'] or
            any(sha256(raw[name+'.txt']) != workload[name+'_sha256'] for name in ('graph', 'trace'))):
        raise ValueError('campaign input identity mismatch')
    verify(manifest, raw['graph.txt'], raw['trace.txt'])
    binary = regular_bytes(executable, MAX_EXECUTABLE)
    if sha256(binary) != executable_hash:
        raise ValueError('campaign executable SHA-256 mismatch')
    bundle = directory/'workload'
    bundle.mkdir()
    for name, data in raw.items():
        atomic_bytes(bundle/name, data)
    atomic_bytes(directory/'runner', binary, 0o700)
    return dict(manifest, _bundle=str(bundle)), {**{f'workload/{n}':sha256(d) for n,d in raw.items()},
                                                'runner':sha256(binary)}


def integrity(directory, identities):
    for name, expected in identities.items():
        limit = MAX_EXECUTABLE if name == 'runner' else MAX_ARTIFACT
        if sha256(regular_bytes(directory/name, limit)) != expected:
            raise ValueError('staged input changed: '+name)


def config(plan, trial):
    return dict(delta=str(trial['delta']), threads=str(trial['workers']),
                no_effect=plan['no_effect'], timing_mode=plan['timing_mode'], warmups='0')


def oracle_label(trial):
    return 'full-preflight+'+METHOD+('' if trial['phase']=='diagnostic' else '+worker')


def command(plan, trial, source, kind):
    """Version-2 argv is relative to the explicit private trial cwd.

    Relative fixed references keep verification valid after evidence relocation.
    No archived pathname or argv controls executable selection by the verifier.
    """
    base = ['./runner', kind, '--graph', 'workload/graph.txt', '--trace', 'workload/trace.txt',
            '--source', str(source), '--delta', str(trial['delta']),
            '--threads', str(trial['workers']), '--no-effect', plan['no_effect'],
            '--policy', trial['policy']]
    if kind == 'verify':
        return base+['--verification', 'full']
    if kind != 'time' or trial['phase']=='diagnostic':
        raise ValueError('unsupported pilot process kind')
    cfg = config(plan, trial)
    identities = dict(graph_sha256=next(w['graph_sha256'] for w in plan['workloads'] if w['id']==trial['workload_id']),
                      trace_sha256=next(w['trace_sha256'] for w in plan['workloads'] if w['id']==trial['workload_id']),
                      executable_sha256=plan['build']['executable_sha256'],
                      configuration_sha256=sha256(canonical_json(cfg)))
    base += ['--timing-mode', plan['timing_mode'], '--warmups', '0', '--run-id', '0',
             '--block-id', str(trial['sequence']), '--trial-id', str(trial['sequence'])]
    for key, value in identities.items():
        base += ['--'+key.replace('_', '-'), value]
    return base


def check_preflight(raw, cfg, bundle, policy):
    if not raw.endswith(b'\n'):
        raise ValueError('truncated pilot preflight output')
    result = verify_preflight(raw, cfg, bundle, policy)
    reconcile(regular_bytes(Path(bundle['_bundle'])/'graph.txt', MAX_ARTIFACT),
              regular_bytes(Path(bundle['_bundle'])/'trace.txt', MAX_ARTIFACT), bundle, result)
    return result


def environment(workers):
    # Preserve ordinary OS environment, discard all inherited OpenMP/runtime
    # controls and loader injection. Record the resulting relevant configuration.
    env = {k:v for k,v in os.environ.items() if not k.startswith(('OMP_', 'GOMP_', 'KMP_', 'LD_'))}
    env.update(OMP_NUM_THREADS=str(workers), OMP_DYNAMIC='FALSE', OMP_THREAD_LIMIT=str(workers))
    return env


def validate_trial(record):
    fields(record, 'schema schema_version campaign_id plan_sha256 manifest_sha256 trial '
           'workload executable_sha256 admission hardware_sha256 requested_affinity observed_affinity '
           'openmp_environment observed_team_size execution_observations start end status reason '
           'message correctness measurement_eligible processes artifacts', 'pilot trial record')
    if (record['schema'] != 'dynagraph-pilot-trial' or type(record['schema_version']) is not int or
            record['schema_version'] != 2 or record['admission'] != 'development-only' or
            record['measurement_eligible'] is not False or record['observed_team_size'] is not None or
            record['reason'] not in REASONS):
        raise ValueError('unsupported pilot trial record')
    for key in ('plan_sha256','manifest_sha256','hardware_sha256','executable_sha256'):
        digest(record[key])
    if type(record['processes']) is not list or len(record['processes'])>2 or type(record['artifacts']) is not dict:
        raise ValueError('invalid pilot process/artifact collections')
    trial = record['trial']
    fields(trial, 'trial_id sequence session workload_id configuration_id policy phase block policy_position '
           'worker_group pairing_id configuration_pairing_id workers delta', 'pilot trial identity')
    digest(trial['trial_id']);integer(trial['sequence'],0,99999,'trial sequence')
    integer(trial['workers'],1,64,'requested workers');integer(trial['delta'],1,(1<<64)-1,'delta')
    if trial['phase'] not in ('diagnostic','warmup','measured'):
        raise ValueError('unsupported pilot phase')
    cpu_array(record['requested_affinity'])
    if record['observed_affinity'] is not None:
        cpu_array(record['observed_affinity'])
    if record['openmp_environment'] != {'OMP_NUM_THREADS':str(trial['workers']),
                                        'OMP_DYNAMIC':'FALSE','OMP_THREAD_LIMIT':str(trial['workers'])}:
        raise ValueError('invalid pilot OpenMP configuration')
    if type(record['message']) is not str or len(record['message'])>2048:
        raise ValueError('invalid pilot diagnostic')
    time_range(record['start'],record['end'])
    fields(record['correctness'], 'checked outcome oracle', 'pilot correctness')
    if record['correctness']['outcome'] not in ('passed','failed','unavailable','not-checked'):
        raise ValueError('invalid correctness outcome')
    if type(record['correctness']['checked']) is not bool:
        raise ValueError('invalid correctness checked flag')
    if record['correctness']['checked'] != (record['correctness']['outcome'] in ('passed','failed')):
        raise ValueError('contradictory correctness outcome')
    success = record['reason'] == 'success'
    if record['status'] != ('success' if success else ('unverified' if record['reason']=='unverified' else 'failed')):
        raise ValueError('contradictory pilot status')
    oracle = oracle_label(record['trial'])
    if success and (record['correctness'] != dict(checked=True, outcome='passed', oracle=oracle) or
                    not record['processes'] or any(p['reason']!='exited' or p['returncode']!=0 for p in record['processes'])):
        raise ValueError('unverified pilot success')
    for process in record['processes']:
        fields(process, 'command start end returncode signal reason truncated stdout stderr stdout_size stderr_size stdout_sha256 stderr_sha256 stream_limit', 'pilot process')
        if (type(process['command']) is not list or not process['command'] or
                any(type(arg) is not str for arg in process['command']) or
                type(process['truncated']) is not bool or
                (process['returncode'] is not None and type(process['returncode']) is not int)):
            raise ValueError('invalid pilot process fields')
        if (process['reason'] not in ('exited','timeout','output-limit','interrupted','launch-error',
                                     'capture-error','signal','nonzero-exit') or
                (process['signal'] is not None and (type(process['signal']) is not int or process['signal']<1)) or
                (process['reason']=='exited' and (process['returncode']!=0 or process['signal'] is not None or process['truncated']))):
            raise ValueError('contradictory pilot process outcome')
        time_range(process['start'],process['end'])
        integer(process['stream_limit'], 1, MAX_OUTPUT, 'process stream limit')
        for key in ('stdout','stderr'):
            safe_path(process[key])
            integer(process[key+'_size'], 0, process['stream_limit'], 'captured bytes')
            digest(process[key+'_sha256'])
        code = process['returncode']
        if (process['signal'] != (-code if code is not None and code < 0 else None) or
                (process['reason']=='launch-error' and code is not None) or
                (process['reason'] in ('timeout','output-limit','capture-error') and code is None) or
                (process['reason']=='nonzero-exit' and (code is None or code<=0)) or
                (process['reason']=='signal' and (code is None or code>=0)) or
                (process['reason']=='output-limit' and not process['truncated']) or
                (process['truncated'] and process['reason'] not in ('output-limit','capture-error','launch-error'))):
            raise ValueError('contradictory pilot exit/signal/truncation')
        if process['truncated'] and max(process['stdout_size'],process['stderr_size']) != process['stream_limit']:
            raise ValueError('truncation without saturated stream')
    for name, identity in record['artifacts'].items():
        safe_path(name);digest(identity)
    return record


def reconcile_processes(directory, record, plan, execution, inventory):
    """Bind every receipt, including failed runs, to its exact v2 request."""
    trial = record['trial']
    if record['requested_affinity'] != plan['hardware']['allocated_cpus']:
        raise ValueError('pilot requested affinity mismatch')
    processes = record['processes']
    expected_kinds = ['verify'] if trial['phase']=='diagnostic' else ['verify','time']
    if len(processes)>len(expected_kinds):
        raise ValueError('unexpected pilot process')
    if processes:
        workload = record['workload']
        vertices, edges = graph_dimensions(workload['recipe']['graph'])
        if vertices>128 or edges>4096 or workload['recipe']['trace']['count']>256:
            raise ValueError('unsupported process workload')
        source = generate(workload['recipe'])[0]['source']
    for i,(process,kind) in enumerate(zip(processes,expected_kinds)):
        if (datetime.fromisoformat(process['start'])<datetime.fromisoformat(record['start']) or
                datetime.fromisoformat(process['end'])>datetime.fromisoformat(record['end']) or
                (i and datetime.fromisoformat(process['start'])<datetime.fromisoformat(processes[i-1]['end']))):
            raise ValueError('pilot process timestamp context mismatch')
        if process['command'] != command(plan,trial,source,kind):
            raise ValueError('pilot complete argv mismatch')
        if process['stream_limit'] != execution['limits']['stream_bytes']:
            raise ValueError('pilot process stream limit mismatch')
        for stream in ('stdout','stderr'):
            reference = f'{i}-{kind}.{stream}'
            if process[stream] != reference:
                raise ValueError('unexpected or duplicate pilot stream reference')
            data = regular_bytes(directory/reference,process['stream_limit'])
            identity = sha256(data)
            if (len(data)!=process[stream+'_size'] or identity!=process[stream+'_sha256'] or
                    record['artifacts'].get(reference)!=identity or
                    inventory.get(trial['trial_id']+'/'+reference)!=identity):
                raise ValueError('pilot stream size/hash mismatch')
        if i<len(processes)-1 and process['reason']!='exited':
            raise ValueError('process launched after failure')
    reason = record['reason']
    correctness = record['correctness']
    if reason=='success' and len(processes)!=len(expected_kinds):
        raise ValueError('missing successful pilot process')
    if reason in ('not-run','unverified') and processes:
        raise ValueError('nonexecuted trial contains processes')
    if reason=='unverified' and correctness!=dict(checked=False,outcome='unavailable',oracle=None):
        raise ValueError('contradictory unavailable oracle')
    if reason=='not-run' and correctness!=dict(checked=False,outcome='not-checked',oracle=None):
        raise ValueError('contradictory not-run correctness')
    if reason=='correctness-failed' and (len(processes)!=1 or processes[0]['reason']!='exited' or
            correctness!=dict(checked=True,outcome='failed',oracle='full-preflight+'+METHOD)):
        raise ValueError('contradictory failed preflight')
    if reason=='protocol-failed' and (len(processes)!=2 or any(p['reason']!='exited' for p in processes) or
            correctness!=dict(checked=True,outcome='passed',oracle='full-preflight+'+METHOD)):
        raise ValueError('contradictory failed worker protocol')
    if reason in ('launch-error','capture-error','signal','nonzero-exit','output-limit') and (
            not processes or processes[-1]['reason']!=reason):
        raise ValueError('trial/process failure mismatch')
    if processes and processes[-1]['reason']!='exited' and processes[-1]['reason']!=reason:
        raise ValueError('trial/process termination mismatch')
    if correctness['checked'] and not processes:
        raise ValueError('checked trial without process evidence')
    if correctness['outcome']=='failed' and reason!='correctness-failed':
        raise ValueError('failed correctness without failed preflight status')
    if not correctness['checked'] and correctness['oracle'] is not None:
        raise ValueError('unchecked trial claims an oracle')
    if correctness['outcome']=='passed' and reason!='success':
        if correctness['oracle']!='full-preflight+'+METHOD or not processes or processes[0]['reason']!='exited':
            raise ValueError('contradictory passed preflight')
        bundle = read_json(directory/'workload/manifest.json')
        validate_manifest(bundle)
        if bundle['configuration']!=record['workload']['recipe']:
            raise ValueError('pilot preflight input configuration mismatch')
        check_preflight(regular_bytes(directory/processes[0]['stdout'],processes[0]['stream_limit']),
                        config(plan,trial),dict(bundle,_bundle=str(directory/'workload')),trial['policy'])


def time_range(start, end):
    try:
        a,b = (datetime.fromisoformat(s) for s in (start,end))
        if a.utcoffset() is None or b.utcoffset() is None or b<a:
            raise ValueError('invalid pilot timestamp range')
    except (TypeError, ValueError) as error:
        raise ValueError('invalid pilot timestamp range') from error


def verify_success(directory, record, plan):
    """Reapply existing scientific-correctness gates, without executing evidence."""
    trial = record['trial'];workload = record['workload']
    bundle_dir = directory/'workload'
    bundle = loads(regular_bytes(bundle_dir/'manifest.json', MAX_ARTIFACT))
    validate_manifest(bundle)
    vertices, edges = graph_dimensions(bundle['configuration']['graph'])
    if (vertices>128 or edges>4096 or bundle['configuration']['trace']['count']>256 or
            bundle['split']!='development'):
        raise ValueError('unsupported pilot verification workload')
    verify(bundle, regular_bytes(bundle_dir/'graph.txt', MAX_ARTIFACT),
           regular_bytes(bundle_dir/'trace.txt', MAX_ARTIFACT))
    if (bundle['configuration']!=workload['recipe'] or
            any(bundle['artifacts'][n]['sha256']!=workload[n+'_sha256'] for n in ('graph','trace')) or
            sha256(regular_bytes(directory/'runner', MAX_EXECUTABLE))!=record['executable_sha256']):
        raise ValueError('pilot staged identity mismatch')
    expected_kinds = ['verify'] if trial['phase']=='diagnostic' else ['verify','time']
    if len(record['processes'])!=len(expected_kinds):
        raise ValueError('incomplete pilot processes')
    cfg = config(plan,trial)
    for process,kind in zip(record['processes'],expected_kinds):
        if len(process['command'])<2 or process['command'][1]!=kind or process['truncated']:
            raise ValueError('pilot command/stream mismatch')
        raw = regular_bytes(directory/process['stdout'], MAX_OUTPUT)
        if kind=='verify':
            if not raw.endswith(b'\n'):
                raise ValueError('truncated pilot preflight output')
            check_preflight(raw,cfg,dict(bundle,_bundle=str(bundle_dir)),trial['policy'])
        else:
            expected = dict(graph_sha256=workload['graph_sha256'],trace_sha256=workload['trace_sha256'],
                            executable_sha256=record['executable_sha256'],configuration_sha256=sha256(canonical_json(cfg)),
                            run_id='0',block_id=str(trial['sequence']),trial_id=str(trial['sequence']),
                            policy=trial['policy'],source=str(bundle['source']))
            validate_worker(read_jsonl(raw),expected,cfg,bundle['counts']['updates'],
                            bundle['counts']['vertices'],bundle['counts']['edges'])


def run_pilot(plan, manifest, root, output, trial_ids, *, execute=False, max_trials=1,
              wall_seconds=60, timeout=10, output_limit=262144):
    selected = select(plan, manifest, trial_ids, max_trials)
    bounds(plan, max_trials, wall_seconds, timeout, output_limit)
    if execute is not True:
        raise ValueError('--execute-development is required to launch a pilot')
    if os.name != 'posix':
        raise ValueError('pilot requires POSIX process groups')
    root = Path(root).resolve(strict=True)
    path_text(str(root));output = Path(output).absolute();path_text(str(output))
    # Reserve the output once. Existing/partial evidence is never overwritten.
    output.mkdir(parents=True, exist_ok=False)
    output = output.resolve()
    started = timestamp();deadline = time.monotonic()+wall_seconds
    put(output, 'plan.json', plan);put(output, 'trial-manifest.json', manifest)
    hardware = inspect(binaries=False)
    admission = admit(plan, hardware)
    put(output, 'hardware.json', hardware);put(output, 'admission.json', admission)
    execution = dict(schema='dynagraph-pilot-execution', schema_version=2,
                     campaign_id=plan['campaign_id'], plan_sha256=plan_hash(plan),
                     manifest_sha256=sha256(canonical_json(manifest)), selected_trials=selected,
                     limits=dict(max_trials=max_trials, wall_seconds=wall_seconds,
                                 timeout_seconds=timeout, stream_bytes=output_limit),
                     development_only=True, measurement_eligible=False,
                     affinity_policy='inherit; requested plan affinity recorded, not applied')
    put(output, 'execution-manifest.json', execution)
    records = [];halted = False
    for trial in selected:
        trial_deadline = min(deadline, time.monotonic()+timeout)
        directory = output/trial['trial_id'];directory.mkdir()
        workload = next(w for w in plan['workloads'] if w['id']==trial['workload_id'])
        env = environment(trial['workers'])
        affinity = host_metadata()['affinity']['value']
        record = dict(schema='dynagraph-pilot-trial', schema_version=2,
                      campaign_id=plan['campaign_id'], plan_sha256=execution['plan_sha256'],
                      manifest_sha256=execution['manifest_sha256'], trial=trial, workload=workload,
                      executable_sha256=plan['build']['executable_sha256'], admission='development-only',
                      hardware_sha256=sha256(canonical_json(hardware)),
                      requested_affinity=plan['hardware']['allocated_cpus'],
                      observed_affinity=[int(c) for c in affinity] if affinity is not None else None,
                      openmp_environment={k:v for k,v in env.items() if k.startswith('OMP_')},
                      observed_team_size=None,
                      execution_observations='child affinity, runtime mapping, exclusivity and stability unavailable',
                      start=timestamp(), end=None, status='failed', reason='not-run', message='',
                      correctness=dict(checked=False,outcome='not-checked',oracle=None),
                      measurement_eligible=False, processes=[], artifacts={})
        inputs = {}
        try:
            if halted:
                record['reason'] = 'not-run'
            elif time.monotonic() >= deadline:
                record['reason'] = 'budget-exhausted'
            else:
                record['reason'] = 'input-error'
                executable = contained(root, plan['build']['executable'])
                bundle, inputs = stage_inputs(root, directory, workload, executable, plan['build']['executable_sha256'])
                cfg = config(plan, trial)
                def launch(kind):
                    integrity(directory, inputs)
                    remaining = trial_deadline-time.monotonic()
                    if remaining <= 0:
                        record['reason'] = 'budget-exhausted' if time.monotonic()>=deadline else 'timeout'
                        return None
                    process, streams = capture(command(plan, trial, bundle['source'], kind),
                                                directory, env, remaining, output_limit)
                    for name, data in streams.items():
                        reference = f'{len(record["processes"])}-{kind}.{name}'
                        atomic_bytes(directory/reference, data);process[name] = reference
                        process[name+'_size'] = len(data)
                        process[name+'_sha256'] = sha256(data)
                    process['stream_limit'] = output_limit
                    record['processes'].append(process)
                    if process['reason'] != 'exited':
                        record['reason'] = process['reason']
                        return None
                    integrity(directory, inputs)
                    return streams['stdout']
                raw = launch('verify')
                if raw is not None:
                    record['reason'] = 'correctness-failed'
                    record['correctness'] = dict(checked=True,outcome='failed',oracle='full-preflight+'+METHOD)
                    if not raw.endswith(b'\n'):
                        raise ValueError('truncated pilot preflight output')
                    check_preflight(raw, cfg, bundle, trial['policy'])
                    record['correctness'] = dict(checked=True,outcome='passed',oracle='full-preflight+'+METHOD)
                    if trial['phase'] != 'diagnostic':
                        ids = dict(graph_sha256=workload['graph_sha256'],trace_sha256=workload['trace_sha256'],
                                   executable_sha256=plan['build']['executable_sha256'],
                                   configuration_sha256=sha256(canonical_json(cfg)))
                        raw = launch('time')
                        if raw is not None:
                            record['reason'] = 'protocol-failed'
                            expected = dict(ids, run_id='0', block_id=str(trial['sequence']),
                                            trial_id=str(trial['sequence']),policy=trial['policy'],source=str(bundle['source']))
                            validate_worker(read_jsonl(raw), expected, cfg, bundle['counts']['updates'],
                                            bundle['counts']['vertices'],bundle['counts']['edges'])
                    if raw is not None:
                        oracle = oracle_label(trial)
                        record['correctness'] = dict(checked=True,outcome='passed',oracle=oracle)
                        record.update(reason='success',status='success')
        except KeyboardInterrupt:
            record.update(reason='interrupted',message='keyboard interruption')
        except OracleUnavailable as error:
            record.update(reason='unverified',status='unverified',message=str(error),
                          correctness=dict(checked=False,outcome='unavailable',oracle=None))
        except (ValueError, OSError, KeyError, TypeError, RecursionError) as error:
            record['message'] = str(error)[:2048]
        record['end'] = timestamp()
        # Hash even partial staging and failed output. Interrupted/atomic I/O
        # failures without a final index are incomplete evidence, never success.
        record['artifacts'] = {p.relative_to(directory).as_posix():sha256(regular_bytes(p, MAX_EXECUTABLE))
                               for p in sorted(directory.rglob('*')) if p.is_file()}
        validate_trial(record)
        put(directory, 'record.json', record)
        records.append(record)
        halted = halted or record['reason'] != 'success'
    index = dict(schema='dynagraph-pilot-index', schema_version=2,
                 execution_manifest_sha256=sha256(canonical_json(execution)),start=started,end=timestamp(),
                 status='complete' if all(r['status']=='success' for r in records) else 'failed',
                 measurement_eligible=False, records=[r['trial']['trial_id']+'/record.json' for r in records])
    put(output, 'result-index.json', index)
    inventory = {p.relative_to(output).as_posix():sha256(regular_bytes(p, MAX_EXECUTABLE))
                 for p in sorted(output.rglob('*')) if p.is_file()}
    put(output, 'sha256.json', inventory)
    return index


def verify_pilot(directory):
    """Offline consistency and hash verification; never runs an archived executable."""
    directory = Path(directory).resolve(strict=True)
    inventory = read_json(directory/'sha256.json')
    if type(inventory) is not dict or not inventory:
        raise ValueError('invalid pilot inventory')
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    if any(p.is_symlink() for p in directory.rglob('*')):
        raise ValueError('symlink in pilot evidence')
    if any(not (stat.S_ISREG(p.lstat().st_mode) or stat.S_ISDIR(p.lstat().st_mode))
           for p in directory.rglob('*')):
        raise ValueError('nonregular artifact in pilot evidence')
    if actual != set(inventory)|{'sha256.json'}:
        raise ValueError('incomplete/extra pilot files')
    for name, expected in inventory.items():
        digest(expected)
        if sha256(regular_bytes(contained(directory,name), MAX_EXECUTABLE)) != expected:
            raise ValueError('pilot artifact digest mismatch: '+name)
    plan = validate_plan(read_json(directory/'plan.json'));manifest = read_json(directory/'trial-manifest.json')
    execution = read_json(directory/'execution-manifest.json')
    fields(execution, 'schema schema_version campaign_id plan_sha256 manifest_sha256 selected_trials limits '
           'development_only measurement_eligible affinity_policy', 'pilot execution manifest')
    if (execution['schema']!='dynagraph-pilot-execution' or type(execution['schema_version']) is not int or
            execution['schema_version']!=2 or execution['development_only'] is not True or
            execution['measurement_eligible'] is not False):
        raise ValueError('invalid pilot execution schema')
    limits = execution['limits'];fields(limits,'max_trials wall_seconds timeout_seconds stream_bytes','pilot limits')
    bounds(plan,limits['max_trials'],limits['wall_seconds'],limits['timeout_seconds'],limits['stream_bytes'])
    selected = select(plan,manifest,[t['trial_id'] for t in execution['selected_trials']],limits['max_trials'])
    if canonical_json(selected)!=canonical_json(execution['selected_trials']):
        raise ValueError('pilot selection order mismatch')
    if (execution['plan_sha256']!=plan_hash(plan) or execution['manifest_sha256']!=sha256(canonical_json(manifest)) or
            execution['campaign_id']!=plan['campaign_id']):
        raise ValueError('pilot execution identity mismatch')
    hardware = read_json(directory/'hardware.json')
    if canonical_json(admit(plan,hardware))!=canonical_json(read_json(directory/'admission.json')):
        raise ValueError('pilot admission mismatch')
    index = read_json(directory/'result-index.json')
    fields(index,'schema schema_version execution_manifest_sha256 start end status measurement_eligible records','pilot index')
    time_range(index['start'],index['end'])
    expected_records = [t['trial_id']+'/record.json' for t in selected]
    if (index['schema']!='dynagraph-pilot-index' or type(index['schema_version']) is not int or index['schema_version']!=2 or
            index['measurement_eligible'] is not False or index['records']!=expected_records or
            index['execution_manifest_sha256']!=sha256(canonical_json(execution))):
        raise ValueError('pilot result index mismatch')
    records = []
    halted = False
    for trial,name in zip(selected,expected_records):
        record = validate_trial(read_json(directory/name));records.append(record)
        if (canonical_json(record['trial'])!=canonical_json(trial) or record['plan_sha256']!=execution['plan_sha256'] or
                record['manifest_sha256']!=execution['manifest_sha256'] or record['hardware_sha256']!=sha256(canonical_json(hardware)) or
                record['campaign_id']!=plan['campaign_id'] or record['executable_sha256']!=plan['build']['executable_sha256'] or
                canonical_json(record['workload'])!=canonical_json(next(w for w in plan['workloads'] if w['id']==trial['workload_id']))):
            raise ValueError('pilot record identity mismatch')
        base = Path(name).parent
        for artifact,identity in record['artifacts'].items():
            if inventory.get((base/artifact).as_posix())!=identity:
                raise ValueError('pilot result artifact identity mismatch')
        actual_artifacts = {p.relative_to(directory/base).as_posix() for p in (directory/base).rglob('*') if p.is_file()}
        if actual_artifacts != set(record['artifacts'])|{'record.json'}:
            raise ValueError('incomplete pilot artifact index')
        reconcile_processes(directory/base,record,plan,execution,inventory)
        if (datetime.fromisoformat(record['start'])<datetime.fromisoformat(index['start']) or
                datetime.fromisoformat(record['end'])>datetime.fromisoformat(index['end'])):
            raise ValueError('pilot trial timestamp context mismatch')
        if halted and record['reason']!='not-run':
            raise ValueError('trial executed after earlier failure')
        halted = halted or record['reason']!='success'
        if record['status']=='success':
            verify_success(directory/base,record,plan)
    status = 'complete' if all(r['status']=='success' for r in records) else 'failed'
    if index['status']!=status:
        raise ValueError('pilot completion mismatch')
    time_range(index['start'],index['end'])
    return dict(schema_version=2,status='integrity-verified',execution_status=status,
                trials=len(records),measurement_eligible=False)
