"""Bounded real end-to-end harness validation; timings are not performance evidence."""
import argparse
import json
import os
from pathlib import Path
import sys

from ci_verify import source_identity, hashes
from command_receipts import Runner
from pipeline_artifacts import digest, verify_analysis, verify_hashes
from snapshot import compare_inventory, inventory, validate_paths


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--runner', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = validate_paths(args.source, args.output)
    executable = args.runner.resolve(strict=True)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError('compiled executable required')
    output.mkdir(parents=True, exist_ok=False)
    runner = Runner(output)
    before = source_identity(runner, source)
    executable_hash = digest(executable)
    python = Path(sys.executable).absolute()
    bench = source/'benchmarks/python'
    try:
        runner.run('environment', [python, '-B', source/'tools/validation/check_environment.py'], source)
        for tool in ('cmake', 'g++'):
            runner.run(tool+'-version', [tool, '--version'], source)
        runner.run('generate', [python, '-B', bench/'generate.py', 'generate', '--spec',
                               source/'benchmarks/configs/chain-v1.json', '--output', output/'bundle'], source)
        verification = json.loads(runner.run('verify-workload', [python, '-B', bench/'generate.py', 'verify',
                                                               '--manifest', output/'bundle/manifest.json'], source))
        manifest = json.loads((output/'bundle/manifest.json').read_bytes())
        # The existing verifier checks canonical regeneration, hashes, an independent
        # expected-old-weight ledger and the final graph fingerprint before timing.
        if verification['status'] != 'verified' or verification['counts'] != manifest['counts']:
            raise ValueError('independent workload verification incomplete')
        initial_bundle = {name: digest(output/'bundle'/name) for name in ('graph.txt', 'trace.txt', 'manifest.json')}
        inputs, configs = [], []
        for mode in ('full-trace', 'per-update'):
            config = dict(schema_version=1, manifest='bundle/manifest.json', timing_mode=mode,
                          blocks='4', order_seed='0', delta='16', threads='2', no_effect='shared_fast_path',
                          timeout_seconds='30', warmups='1')
            write(output/(mode+'.json'), config)
            runner.run(mode+'-run', [python, '-B', bench/'run.py', 'run', '--config', output/(mode+'.json'),
                                    '--runner', executable, '--output', output/mode], source)
            result = json.loads(runner.run(mode+'-validate', [python, '-B', bench/'run.py', 'validate',
                                                             '--input', output/mode/'records.jsonl'], source))
            if result.get('status') != 'complete' or result.get('trials') != '16':
                raise ValueError('complete 16-trial dataset required for ' + mode)
            first = json.loads((output/mode/'records.jsonl').read_bytes().splitlines()[0])
            if first['executable_sha256'] != executable_hash:
                raise ValueError('staged executable mismatch')
            configs.append(dict(id=mode, **{k: config[k] for k in ('timing_mode', 'delta', 'threads', 'no_effect', 'warmups')},
                                executable_sha256=executable_hash, build_type=None))
            inputs.append(dict(id=mode, path=mode, workload_id='chain', configuration_group=mode,
                               hardware_id='validation-host', session_id='smoke', session_independence_declared=False,
                               synthetic=False, evidence_intent='harness',
                               expected_identities={k: first[k] for k in ('graph_sha256', 'trace_sha256',
                                                                       'executable_sha256', 'configuration_sha256', 'manifest_sha256')},
                               controlled_hardware_evidence=None, instrumentation_evidence=None))
        template = json.loads((source/'benchmarks/configs/analysis-example-v1.json').read_bytes())
        template.update(inputs=inputs, compatible_configurations=configs,
                        workloads=[dict(id='chain', graph_sha256=manifest['artifacts']['graph']['sha256'],
                                        trace_sha256=manifest['artifacts']['trace']['sha256'], source=str(manifest['source']),
                                        dependence_group='chain-topology')])
        write(output/'analysis-plan.json', template)
        runner.run('analyze', [python, '-B', bench/'analyze.py', '--plan', output/'analysis-plan.json',
                               '--output', output/'analysis'], source)
        products = verify_analysis(output/'analysis')
        verify_hashes(output/'bundle', initial_bundle)
        if digest(executable) != executable_hash:
            raise ValueError('executable changed during smoke')
        raw = runner.run('source-files-final', ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], source)
        compare_inventory(before, inventory(source, [n for n in raw.decode().split('\0') if n]))
        write(output/'pipeline-result.json', dict(status='complete', evidence_class='valid_harness_only',
                                                 timing_modes=['full-trace', 'per-update'], trials_per_mode=16,
                                                 workload=manifest['counts'], figures=products['figures'],
                                                 executable_sha256=executable_hash, workload_sha256=initial_bundle,
                                                 dataset_sha256={mode: digest(output/mode/'records.jsonl') for mode in ('full-trace', 'per-update')},
                                                 source_unchanged=True, producer_authentication=False))
        hashes(output)
        verify_hashes(output, json.loads((output/'evidence-sha256.json').read_bytes()))
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        write(output/'failure.json', dict(status='failed', error=str(error)))
        if (output/'pipeline-result.json').exists():
            write(output/'pipeline-result.json', dict(status='failed', error=str(error)))
        raise
    finally:
        hashes(output)
    print('All smoke stages and final artifact hashes verified', flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        print('Smoke pipeline failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
