"""Summarize preserved 5C-2A records; startup failures never become passes."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'results/validation/phase5c2a'


def state(record):
    if record['timed_out']:
        return 'timeout'
    if record['warnings']:
        return 'warning'
    if record['fatal']:
        return 'mapping' if all('unexpected memory mapping' in x for x in record['fatal']) else 'fatal'
    return {0: 'exit0', 1: 'fixture_failure', -11: 'signal11'}.get(record['exit_code'], 'other')


def main():
    results = {}
    rows = []
    reports = {}
    for directory in (DEST, ROOT / 'results/validation/phase5c2a-fixed'):
        totals = defaultdict(Counter)
        controls = defaultdict(Counter)
        cells = defaultdict(Counter)
        for path in sorted(directory.glob('*.json')):
            match = re.fullmatch(r'(sandbox|outside)-(one|env1-team2|two)-r([0-2])-(.+)', path.stem)
            if match:
                context, variant, repeat, target = match.groups()
                record = json.loads(path.read_text())
                outcome = state(record)
                totals[context][outcome] += 1
                cells[(context, variant, target)][outcome] += 1
                if target in ('ordinary_race', 'openmp_race', 'barrier_publication-implicit',
                              'barrier_publication-explicit', 'atomic_publication'):
                    controls[target][outcome] += 1
            if path.stem.startswith('followup-'):
                record = json.loads(path.read_text())
                reports[str(path.relative_to(ROOT))] = dict(outcome=state(record),
                    exit_code=record['exit_code'], warnings=len(record['warnings']),
                    summaries=dict(Counter(re.findall(r'SUMMARY: ThreadSanitizer: ([^\n]+)',
                        path.with_suffix('.stderr').read_text()))))
        results[directory.name] = dict(totals={k: dict(v) for k, v in totals.items()},
                                      controls={k: dict(v) for k, v in controls.items()})
        for (context, variant, target), counts in cells.items():
            rows.append(dict(layout=directory.name, context=context, variant=variant,
                             target=target, outcomes=dict(counts)))
    output = dict(matrix_totals=results, matrix_cells=rows, followup=reports)
    (DEST / 'summary.json').write_text(json.dumps(output, indent=2) + '\n')
    table = ['# Recorded project matrix', '',
        'Each cell counts three attempted processes. exit0 means normal exit; it is not a race-freedom claim.', '',
        '| Layout/context | NUM_THREADS / THREAD_LIMIT | delta tests | probe workers=1 | probe workers=2 | system case 3 |',
        '|---|---|---|---|---|---|']
    for layout, contexts in results.items():
        for context in contexts['totals']:
            for variant, env in (('one', '1 / 1'), ('env1-team2', '1 / 2'), ('two', '2 / 2')):
                columns = []
                for target in ('delta-tests', 'work-probe-w1', 'work-probe-w2', 'system-case'):
                    cell = next(r for r in rows if r['layout'] == layout and r['context'] == context
                                and r['variant'] == variant and r['target'] == target)
                    columns.append(', '.join(f'{k}={v}' for k, v in sorted(cell['outcomes'].items())))
                table.append('| ' + ' | '.join([layout + '/' + context, env, *columns]) + ' |')
    (DEST / 'matrix.md').write_text('\n'.join(table) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
