"""Phase 5B-3B experiment orchestration; raw timing only, no analysis."""
import argparse
import os
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import sys

from artifacts import read_bounded, verify_bundle
from workloads import (MAX_JSON_BYTES, MAX_GRAPH_BYTES, MAX_TRACE_BYTES, canonical_json,
                       sha256)
from experiment_records import (IDENTITIES, POLICIES, configuration, loads, read_jsonl, record,
                                schedule, uint, validate_dataset, validate_record, validate_worker, verify_preflight)


class ExperimentError(Exception):
    def __init__(self, category, message):
        super().__init__(message)
        self.category = category


def observed(value, source, origin='observed'):
    return dict(value=value, source=source, origin=origin if value is not None else 'unavailable')


def read_optional(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def host_metadata():
    cpu = read_optional('/proc/cpuinfo')
    model = next((line.split(':', 1)[1].strip() for line in (cpu or '').splitlines()
                  if line.startswith('model name') and ':' in line), None)
    try:
        affinity = [str(i) for i in sorted(os.sched_getaffinity(0))]
    except (AttributeError, OSError):
        affinity = None
    metadata = dict(cpu_model=observed(model, '/proc/cpuinfo; virtualized description possible'),
                    logical_processors=observed(str(os.cpu_count()) if os.cpu_count() is not None else None, 'os.cpu_count; host visible'),
                    affinity=observed(affinity, 'os.sched_getaffinity'),
                    cpu_quota=observed(read_optional('/sys/fs/cgroup/cpu.max'), 'cgroup v2 root cpu.max; namespace view'),
                    cpuset=observed(read_optional('/sys/fs/cgroup/cpuset.cpus.effective'), 'cgroup v2 root effective cpuset; namespace view'),
                    os=observed(platform.system(), 'platform.system'), kernel=observed(platform.release(), 'platform.release'))
    for key in ('OMP_NUM_THREADS', 'OMP_DYNAMIC', 'OMP_THREAD_LIMIT', 'OMP_PROC_BIND', 'OMP_PLACES', 'OMP_WAIT_POLICY', 'GOMP_CPU_AFFINITY'):
        metadata[key] = observed(os.environ.get(key), 'inherited environment; intent, not observed placement', 'user_supplied')
    return metadata


def execute(command, stem, timeout):
    """Keep complete stdout/stderr and exit evidence, including timeout/interrupt."""
    stdout = Path(str(stem) + '.stdout')
    stderr = Path(str(stem) + '.stderr')
    with stdout.open('xb') as out, stderr.open('xb') as error:
        process = subprocess.Popen(command, stdout=out, stderr=error)
        try:
            returncode = process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exception:
            process.kill()
            process.wait()
            Path(str(stem) + '.exit.json').write_bytes(canonical_json({'returncode': process.returncode,
                'failure': 'timeout' if isinstance(exception, subprocess.TimeoutExpired) else 'interrupted'}))
            raise ExperimentError('timeout' if isinstance(exception, subprocess.TimeoutExpired) else 'interrupted', str(exception)) from exception
    for path in (stdout, stderr):
        with path.open('rb') as evidence_stream:
            os.fsync(evidence_stream.fileno())
    evidence = dict(returncode=returncode, stdout_sha256=sha256(stdout.read_bytes()), stderr_sha256=sha256(stderr.read_bytes()))
    Path(str(stem) + '.exit.json').write_bytes(canonical_json(evidence))
    if returncode != 0:
        raise ExperimentError('worker_failure', 'worker failed; see ' + str(stem))
    return read_bounded(stdout, 128 * 1024 * 1024)


class Writer:
    def __init__(self, stream, run_id, identities):
        self.stream, self.run_id, self.identities = stream, run_id, identities
        self.sequence = 0

    def emit(self, kind, block_id=None, trial_id=None, policy=None, **payload):
        value = record(kind, self.run_id, self.identities, self.sequence, block_id, trial_id, policy, **payload)
        validate_record(value)
        self.stream.write(canonical_json(value))
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.sequence += 1

    def merge(self, value):
        self.emit(value['record_type'], value['block_id'], value['trial_id'], value['policy'],
                  **{key:item for key,item in value.items() if key not in record(value['record_type'], self.run_id, self.identities, 0)})


def run_experiment(config_path, runner_path, output):
    config_path, runner_path, output = Path(config_path).resolve(), Path(runner_path).resolve(), Path(output)
    config = configuration(loads(read_bounded(config_path, MAX_JSON_BYTES)))
    source_manifest = (config_path.parent / config['manifest']).resolve()
    # Never merge with or overwrite an existing experiment.
    output.mkdir(parents=True, exist_ok=False)
    run_id = str(secrets.randbits(64))
    initial_ids = {key: None for key in IDENTITIES}
    initial_ids['configuration_sha256'] = sha256(canonical_json(config))
    writer = None
    block_id = trial_id = policy = None
    completed_blocks = 0
    stage = 'invalid_artifacts'
    with (output / 'records.jsonl').open('xb') as stream:
        try:
            bundle = output / 'workload'
            bundle.mkdir()
            # Copy bounded bytes, reject artifact symlinks exactly as verifier does.
            for name, limit in (('manifest.json', MAX_JSON_BYTES), ('graph.txt', MAX_GRAPH_BYTES), ('trace.txt', MAX_TRACE_BYTES)):
                source = source_manifest if name == 'manifest.json' else source_manifest.parent / name
                if source.is_symlink():
                    raise ExperimentError('invalid_artifacts', 'staging symlinks is unsupported')
                (bundle / name).write_bytes(read_bounded(source, limit))
            verification = verify_bundle(bundle / 'manifest.json')
            manifest = loads((bundle / 'manifest.json').read_bytes())
            if manifest['counts']['updates'] == 0:
                raise ExperimentError('incorrect_configuration', 'empty traces cannot be timed')
            (output / 'artifact-verification.json').write_bytes(canonical_json(verification))
            stage = 'worker_failure'
            staged_runner = (output / 'runner').resolve()
            shutil.copy2(runner_path, staged_runner)
            initial_ids.update(graph_sha256=manifest['artifacts']['graph']['sha256'], trace_sha256=manifest['artifacts']['trace']['sha256'],
                               executable_sha256=sha256(staged_runner.read_bytes()))
            stage = 'protocol_failure'
            writer = Writer(stream, run_id, initial_ids)
            order = schedule(uint(config['blocks']), uint(config['order_seed']))
            writer.emit('run_config', configuration=config, schedule=order, manifest_sha256=sha256((bundle / 'manifest.json').read_bytes()),
                        isolation='fresh-process-per-trial-v1', schedule_version='balanced-four-splitmix64-fisher-yates-v1')
            metadata = host_metadata()
            for field, command in (('source_git_revision', ['git','rev-parse','HEAD']), ('source_git_dirty', ['git','status','--porcelain'])):
                try:
                    result = subprocess.run(command, capture_output=True, check=True, timeout=10)
                    metadata[field] = observed(result.stdout.decode().strip(), 'orchestrator working tree; not executable build provenance')
                except (OSError, subprocess.SubprocessError):
                    metadata[field] = observed(None, 'git unavailable')
            writer.emit('environment', metadata=metadata, source=str(manifest['source']), delta=config['delta'], requested_workers=config['threads'],
                        no_effect=config['no_effect'], heuristic={'small_graph_edges':'4096','repair_max_degree':'32','parallel_min_edges':'65536'},
                        timing_mode=config['timing_mode'], vertices=str(manifest['counts']['vertices']), edges=str(manifest['counts']['edges']), updates=str(manifest['counts']['updates']),
                        external_integrity='python_verified', external_preflight='pending', identity_origin='python_sha256')
            baseline_hashes = {name: sha256((bundle / name).read_bytes()) for name in ('manifest.json','graph.txt','trace.txt')}

            def integrity():
                if any((bundle / name).is_symlink() or sha256(read_bounded(bundle / name, limit)) != baseline_hashes[name]
                       for name,limit in (('manifest.json',MAX_JSON_BYTES),('graph.txt',MAX_GRAPH_BYTES),('trace.txt',MAX_TRACE_BYTES))):
                    raise ExperimentError('artifact_changed', 'staged workload changed')
                if staged_runner.is_symlink() or sha256(staged_runner.read_bytes()) != initial_ids['executable_sha256']:
                    raise ExperimentError('artifact_changed', 'executable identity changed')

            base = ['--graph',str((bundle / 'graph.txt').resolve()),'--trace',str((bundle / 'trace.txt').resolve()),
                    '--source',str(manifest['source']),'--delta',config['delta'],'--threads',config['threads'],'--no-effect',config['no_effect']]
            stage = 'preflight_verification_failure'
            for policy in POLICIES:
                integrity()
                try:
                    raw = execute([str(staged_runner),'verify',*base,'--policy',policy,'--verification','full'], output / ('preflight-' + policy), uint(config['timeout_seconds']))
                except ExperimentError as exception:
                    if exception.category == 'worker_failure':
                        raise ExperimentError('preflight_verification_failure', str(exception)) from exception
                    raise
                integrity()
                checked_manifest = dict(manifest, _bundle=str(bundle))
                result = verify_preflight(raw, config, checked_manifest, policy)
                writer.emit('verification', policy=policy, scope='external_full_preflight', success=True, per_update_oracles=True,
                            reference_recomputations=str(result['reference_recomputations']), bellman_ford_checks=str(result['bellman_ford_checks']))
            stage = 'protocol_failure'
            for block, policies in enumerate(order):
                block_id = str(block)
                trial_id = policy = None
                writer.emit('block_start', block_id=block_id, order=policies)
                for position, policy in enumerate(policies):
                    trial_id = str(block * 4 + position)
                    integrity()
                    writer.emit('trial_start', block_id, trial_id, policy, repetition_id=block_id, policy_position=str(position), phase='measurement')
                    command = [str(staged_runner),'time',*base,'--policy',policy,'--timing-mode',config['timing_mode'],'--warmups',config['warmups'],
                               '--run-id',run_id,'--block-id',block_id,'--trial-id',trial_id]
                    for key in IDENTITIES:
                        command.extend(['--' + key.replace('_','-'), initial_ids[key]])
                    raw = execute(command, output / ('trial-' + trial_id), uint(config['timeout_seconds']))
                    integrity()
                    records = read_jsonl(raw)
                    expected = dict(initial_ids, run_id=run_id, block_id=block_id, trial_id=trial_id, policy=policy, source=str(manifest['source']))
                    validate_worker(records, expected, config, manifest['counts']['updates'], manifest['counts']['vertices'], manifest['counts']['edges'])
                    for item in records:
                        writer.merge(item)
                writer.emit('block_end', block_id=block_id, success=True)
                completed_blocks += 1
            integrity()
            validate_dataset(output / 'records.jsonl', pending=True)
            writer.emit('run_end', success=True, blocks_completed=str(completed_blocks))
        except (Exception, KeyboardInterrupt) as exception:
            category = exception.category if isinstance(exception, ExperimentError) else ('interrupted' if isinstance(exception, KeyboardInterrupt) else ('output_failure' if isinstance(exception, OSError) and stage == 'protocol_failure' else stage))
            if writer is None:
                writer = Writer(stream, run_id, initial_ids)
            writer.emit('failure', block_id, trial_id, policy, category=category, message=str(exception), update_index=None)
            if block_id is not None:
                writer.emit('block_end', block_id=block_id, success=False)
            writer.emit('run_end', success=False, blocks_completed=str(completed_blocks))
            raise ExperimentError(category, str(exception)) from exception
    return {'schema_version': 1, 'status': 'complete', 'trials': str(uint(config['blocks']) * 4)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', allow_abbrev=False)
    run.add_argument('--config', required=True)
    run.add_argument('--runner', required=True)
    run.add_argument('--output', required=True)
    validate = commands.add_parser('validate', allow_abbrev=False)
    validate.add_argument('--input', required=True)
    args = parser.parse_args()
    try:
        result = run_experiment(args.config, args.runner, args.output) if args.command == 'run' else validate_dataset(args.input)
        sys.stdout.buffer.write(canonical_json(result))
        return 0
    except (Exception, KeyboardInterrupt) as exception:
        print('experiment error: ' + str(exception), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
