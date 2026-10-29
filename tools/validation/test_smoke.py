"""Retained negative controls against disposable copies of actual smoke products."""
import argparse
import json
from pathlib import Path
import shutil
import sys

from command_receipts import Runner
from pipeline_artifacts import digest, verify_analysis, verify_hashes
from snapshot import validate_paths


DIAGNOSTICS = {
    'tampered-workload': 'workload error: graph SHA-256 mismatch',
    'incorrect-manifest-hash': 'workload error: graph SHA-256 mismatch',
    'incomplete-replay': 'experiment error: incorrect preflight result/configuration',
    'missing-timing': 'experiment error: incomplete worker protocol',
    'invalid-dataset': 'experiment error: unsupported record schema',
    'missing-figure': 'missing/symlink artifact:',
    'malformed-svg': 'malformed SVG:',
    'malformed-pdf': 'malformed PDF:',
    'incorrect-artifact-digest': 'artifact digest mismatch:',
}


def require_rejection(receipt, diagnostic, expected):
    if (receipt['classification'] != 'exited' or receipt['exit_code'] != 2 or
            expected not in ' '.join(diagnostic.split())):
        raise ValueError('negative control failed to demonstrate intended rejection: ' + expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pipeline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pipeline, output = validate_paths(args.pipeline, args.output)
    source = Path(__file__).resolve().parents[2]
    validate_paths(source, output)
    # Validate the positive reference before using it as a negative-control seed.
    verify_hashes(pipeline, json.loads((pipeline/'evidence-sha256.json').read_bytes()))
    verify_analysis(pipeline/'analysis')
    output.mkdir(parents=True, exist_ok=False)
    runner = Runner(output)
    outcomes = []

    def command_reject(label, command):
        try:
            runner.run(label, command, source)
        except RuntimeError:
            receipt = runner.records[-1]
            diagnostic = (output/receipt['log']).read_text()
            require_rejection(receipt, diagnostic, DIAGNOSTICS[label])
            outcomes.append(dict(case=label, rejected=True, exit_code=2,
                                 expected_diagnostic=DIAGNOSTICS[label], diagnostic=' '.join(diagnostic.split())))
        else:
            raise ValueError('negative control incorrectly accepted: ' + label)

    for label in ('tampered-workload', 'incorrect-manifest-hash'):
        fixture = output/label
        shutil.copytree(pipeline/'bundle', fixture)
        if label == 'tampered-workload':
            with (fixture/'graph.txt').open('ab') as stream:
                stream.write(b'tampered\n')
        else:
            manifest = json.loads((fixture/'manifest.json').read_bytes())
            manifest['artifacts']['graph']['sha256'] = '0'*64
            (fixture/'manifest.json').write_text(json.dumps(manifest)+'\n')
        command_reject(label, [sys.executable, '-B', source/'benchmarks/python/generate.py', 'verify',
                               '--manifest', fixture/'manifest.json'])
    for label in ('incomplete-replay', 'missing-timing', 'invalid-dataset'):
        fixture = output/label
        shutil.copytree(pipeline/'per-update', fixture)
        if label == 'incomplete-replay':
            file = fixture/'preflight-dijkstra.stdout'
            report = json.loads(file.read_bytes())
            report['updates_verified'] -= 1
            file.write_text(json.dumps(report)+'\n')
            # Keep hashes consistent so this probes semantic replay acceptance.
            receipt = fixture/'preflight-dijkstra.exit.json'
            value = json.loads(receipt.read_bytes()); value['stdout_sha256'] = digest(file)
            receipt.write_text(json.dumps(value)+'\n')
        else:
            file = fixture/'records.jsonl'
            rows = [json.loads(line) for line in file.read_bytes().splitlines()]
            if label == 'missing-timing':
                rows.pop(next(i for i, row in enumerate(rows) if row['record_type']=='update_latency'))
                for index, row in enumerate(rows):
                    row['sequence'] = str(index)
            else:
                rows[0]['schema_version'] = False
            file.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        command_reject(label, [sys.executable, '-B', source/'benchmarks/python/run.py', 'validate',
                               '--input', fixture/'records.jsonl'])
    for label in ('missing-figure', 'malformed-svg', 'malformed-pdf', 'incorrect-artifact-digest'):
        fixture = output/label
        shutil.copytree(pipeline/'analysis', fixture)
        manifest_path = fixture/'analysis-manifest.json'
        manifest = json.loads(manifest_path.read_bytes())
        extension = '.pdf' if label=='malformed-pdf' else '.svg'
        product = next(p for p in manifest['figure_generation']['products'] if p['path'].endswith(extension))
        file = fixture/product['path']
        if label == 'missing-figure':
            file.unlink()
        elif label == 'incorrect-artifact-digest':
            manifest['output_sha256'][product['path']] = '0'*64
        else:
            file.write_bytes(b'<svg/>' if extension=='.svg' else b'%PDF-1.4\ninvalid\n%%EOF\n')
            # Consistent digests cannot substitute for a structurally valid figure.
            product['sha256'] = digest(file)
            manifest['output_sha256'][product['path']] = product['sha256']
        manifest_path.write_text(json.dumps(manifest)+'\n')
        try:
            verify_analysis(fixture)
        except (ValueError, OSError) as error:
            if DIAGNOSTICS[label] not in str(error):
                raise ValueError('negative control failed intended diagnostic: ' + label) from error
            (output/(label+'.log')).write_text(str(error)+'\n')
            outcomes.append(dict(case=label, rejected=True, diagnostic=str(error)))
        else:
            raise ValueError('negative control incorrectly accepted: ' + label)
    (output/'negative-results.json').write_text(json.dumps(outcomes, indent=2)+'\n')
    verify_hashes(pipeline, json.loads((pipeline/'evidence-sha256.json').read_bytes()))
    print('All nine negative smoke controls rejected; original evidence unchanged')
    return 0


if __name__ == '__main__':
    sys.exit(main())
