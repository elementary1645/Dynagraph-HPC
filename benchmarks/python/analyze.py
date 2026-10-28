"""Read-only descriptive analysis of completed Phase 5B-3B evidence."""
import argparse
import csv
from collections import Counter
from fractions import Fraction
import importlib.metadata
from pathlib import Path
import platform
import subprocess
import sys

from analysis_import import (read_plan,inventory,import_input,trial_rows,ImportRejected,file_digest)
from analysis_stats import (CI,PRECISION,OUTPUT_PRECISION,aggregate_pairs,pair_rows,panel_summaries,latency_summary,median,fraction_text)
from workloads import canonical_json,sha256


class AnalysisFailure(ValueError):
    pass


def write_json(path,value):
    Path(path).write_bytes(canonical_json(value))


def csv_value(value):
    if value is None: return ''
    if isinstance(value,bool): return 'true' if value else 'false'
    return str(value)


def write_csv(path,rows,default_fields):
    columns=list(default_fields)+sorted(set().union(*(row.keys() for row in rows))-set(default_fields)) if rows else list(default_fields)
    with Path(path).open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({key:csv_value(value) for key,value in row.items()})


def runtime_summaries(trials):
    groups={}
    for row in trials:
        if row['timing_mode']=='full-trace': groups.setdefault((row['input_id'],row['policy']),[]).append(row)
    result=[]
    for key in sorted(groups):
        rows=groups[key];values=[Fraction(r['duration_seconds']) for r in rows]
        result.append({k:rows[0][k] for k in ('input_id','policy','stratum','workload_id','family','session_id','hardware_id','synthetic','evidence_class')} |
                      dict(count=str(len(values)),minimum_seconds=fraction_text(min(values)),maximum_seconds=fraction_text(max(values)),
                           median_seconds=fraction_text(median(values)),**CI))
    return result


def ecdf_rows(trials):
    groups={}
    for row in trials:
        if row['timing_mode']=='per-update': groups.setdefault((row['input_id'],row['trial_id']),[]).append(row)
    output=[]
    for key in sorted(groups,key=lambda k:(k[0],int(k[1]))):
        rows=groups[key];counts=Counter(Fraction(r['duration_seconds']) for r in rows);cumulative=0
        for value,count in sorted(counts.items()):
            cumulative+=count
            output.append({k:rows[0][k] for k in ('input_id','trial_id','stratum','workload_id','policy')} |
                          dict(duration_seconds=fraction_text(value),cumulative_fraction=fraction_text(Fraction(cumulative,len(rows))),count_at_value=str(count),
                               total_positions=str(len(rows))))
    return output


def code_metadata():
    root=Path(__file__).resolve().parents[2]
    metadata={'revision':None,'dirty':None,'origin':'observed_analysis_working_tree','code_sha256':{}}
    for field,args in (('revision',['git','rev-parse','HEAD']),('dirty',['git','status','--porcelain'])):
        try:
            metadata[field]=subprocess.run(args,cwd=root,capture_output=True,check=True,timeout=10).stdout.decode().strip()
        except (OSError,subprocess.SubprocessError): pass
    for path in sorted((root/'benchmarks/python').glob('analysis_*.py')):
        metadata['code_sha256'][path.name]=file_digest(path)
    metadata['code_sha256']['analyze.py']=file_digest(Path(__file__))
    metadata['requirements_sha256']=file_digest(root/'benchmarks/requirements-analysis.txt')
    return metadata


def analyze(plan_path,output):
    plan_path=Path(plan_path).resolve();base=plan_path.parent
    original_plan_sha=file_digest(plan_path)
    plan=read_plan(plan_path)
    output=Path(output).resolve()
    for item in plan['inputs']:
        directory=(base/item['path']).resolve()
        if output==directory or directory in output.parents:
            raise AnalysisFailure('output must not be inside raw evidence')
    # No writes to any raw evidence path, including artifacts or staged executable.
    output.mkdir(parents=True,exist_ok=False)
    acceptances=[];datasets=[];seen=set();guards=[];fatal=False
    exclusions={item['input_id']:item['reason'] for item in plan['exclusions']}
    for item in sorted(plan['inputs'],key=lambda x:x['id']):
        directory=(base/item['path']).resolve()
        entry=dict(input_id=item['id'],path=item['path'],classification='invalid_or_incomplete',accepted=False,
                   session_id=item['session_id'],hardware_id=item['hardware_id'],declaration_origin='user_supplied',reasons=[],inventory={})
        try:
            before=inventory(directory);entry['inventory']=before;guards.append((directory,before))
            dataset=import_input(item,plan,base,seen)
            entry.update(classification=dataset['evidence_class'],reasons=dataset['reasons'],structurally_valid=True,
                         declaration_evidence=dataset['declarations'],stratum=dataset['stratum'])
            if item['id'] in exclusions:
                entry['reasons']=[dict(code='explicit_plan_exclusion',message=exclusions[item['id']])]
            elif dataset['evidence_class'] not in plan['allowed_evidence_classes']:
                entry['reasons'].append('evidence_class_not_allowed')
                fatal=True
            else:
                entry['accepted']=True;datasets.append(dataset)
        except Exception as exception:
            entry.update(structurally_valid=False,reasons=[dict(code=exception.code if isinstance(exception,ImportRejected) else 'structural_or_plan_validation_failure',
                                                               message=str(exception))])
            if item['id'] not in exclusions: fatal=True
        acceptances.append(entry)
    def acceptance_file():
        (output/'acceptance.jsonl').write_bytes(b''.join(canonical_json(row) for row in acceptances))
    acceptance_file()
    trials=[] if fatal else [row for dataset in datasets for row in trial_rows(dataset)]
    trials.sort(key=lambda r:(r['stratum'],r['workload_id'],r['input_id'],int(r['block_id']),int(r['trial_id']),-1 if r['update_index'] is None else int(r['update_index'])))
    pairs=pair_rows(trials,plan['comparisons'])
    runs=aggregate_pairs(pairs)
    latency=latency_summary(trials)
    runtime=runtime_summaries(trials)
    panels=panel_summaries(runs,plan['workloads'])
    for panel in panels:
        subset=[d for d in datasets if d['stratum']==panel['stratum']]
        declarations={d['item']['session_id'] for d in subset if d['item']['session_independence_declared']}
        panel['declared_independent_session_count']=str(len(declarations))
        panel['session_independence_origin']='user_supplied_not_independently_verified'
    adaptive=[]
    from decimal import Decimal
    for row in runs:
        if row['numerator']=='heuristic':
            relation=None if row['mean_log_ratio'] is None else ('below_one' if Decimal(row['mean_log_ratio'])<0 else 'above_one' if Decimal(row['mean_log_ratio'])>0 else 'equal_one')
            adaptive.append(dict(row,observed_relation=relation,interpretation='descriptive_observed_runtime_not_selection_accuracy'))
    write_csv(output/'trials.csv',trials,('input_id','stratum','workload_id','run_id','block_id','trial_id','policy','timing_mode','update_index','duration_seconds'))
    write_csv(output/'paired-ratios.csv',pairs,('input_id','workload_id','block_id','numerator','baseline','runtime_ratio','log_runtime_ratio'))
    write_csv(output/'latency-summary.csv',latency,('input_id','trial_id','policy','count','median','p90','p95','p99'))
    write_csv(output/'run-ratios.csv',runs,('input_id','stratum','workload_id','numerator','baseline','geometric_mean_ratio'))
    write_csv(output/'runtime-summary.csv',runtime,('input_id','stratum','workload_id','policy','median_seconds','minimum_seconds','maximum_seconds'))
    write_csv(output/'latency-ecdf.csv',ecdf_rows(trials),('input_id','stratum','workload_id','trial_id','policy','duration_seconds','cumulative_fraction'))
    write_csv(output/'adaptive-comparisons.csv',adaptive,('input_id','workload_id','numerator','baseline','observed_relation','geometric_mean_ratio'))
    summaries=dict(schema_version=1,status='rejected_inputs' if fatal else 'complete',descriptive_only=True,run_ratios=runs,fixed_workload_panels=panels,
                   accepted_input_count=str(sum(row['accepted'] for row in acceptances)),run_count=str(len(datasets)) if not fatal else '0',
                   declared_session_count=str(len({(d['item']['hardware_id'],d['item']['session_id']) for d in datasets})) if not fatal else '0',
                   verified_independent_session_count=None,session_count_origin='user_supplied_labels_not_independently_verified',
                   declared_independent_session_count=str(len({(d['item']['hardware_id'],d['item']['session_id']) for d in datasets if d['item']['session_independence_declared']})) if not fatal else '0',
                   block_count=str(len({(r['input_id'],r['block_id']) for r in trials})),trial_count=str(len({(r['input_id'],r['trial_id']) for r in trials})),
                   update_sample_count=str(sum(r['timing_mode']=='per-update' for r in trials)),**CI)
    write_json(output/'summaries.json',summaries)
    figures=dict(products=[],skipped=[],settings={},dependencies={})
    rendering_error=None
    if not fatal and plan['figures'] and trials:
        try:
            from analysis_figures import render
            figures=render(output,plan['figures'])
        except Exception as exception:
            rendering_error=str(exception);fatal=True
    else:
        (output/'figures').mkdir()
        figures['skipped']=[dict(figure_type=kind,reason='rejected_or_empty_analysis') for kind in plan['figures']]
    for directory,before in guards:
        if inventory(directory)!=before:
            fatal=True
            acceptances.append(dict(input_id=None,accepted=False,classification='invalid_or_incomplete',reasons=[dict(code='evidence_changed_during_analysis',message=str(directory))]))
    for dataset in datasets:
        for declaration in dataset['declarations'].values():
            if file_digest(declaration['path'])!=declaration['sha256']:
                fatal=True;acceptances.append(dict(input_id=dataset['item']['id'],accepted=False,classification='invalid_or_incomplete',reasons=['declaration_changed_during_analysis']))
    if file_digest(plan_path)!=original_plan_sha:
        fatal=True;acceptances.append(dict(input_id=None,accepted=False,classification='invalid_or_incomplete',reasons=['analysis_plan_changed']))
    acceptance_file()
    if fatal:
        summaries['status']='failed';write_json(output/'summaries.json',summaries)
    manifest=dict(schema_version=1,status='failed' if fatal else 'complete',analysis_plan_sha256=original_plan_sha,
                  normalized_plan_sha256=sha256(canonical_json(plan)),normalized_plan=plan,analysis_code=code_metadata(),python=platform.python_version(),
                  input_evidence=[dict(input_id=e['input_id'],files=e.get('inventory',{})) for e in acceptances if e.get('inventory')],
                  numerical_conventions=dict(exact='Fraction seconds from raw ticks and rational period',decimal_precision=PRECISION,decimal_output_significant_digits=OUTPUT_PRECISION,rounding='ROUND_HALF_EVEN',
                                             median='midpoint',upper_quantiles='inverse_ecdf',thresholds={'p90':50,'p95':100,'p99':500},zero_ticks='withhold_affected_aggregate',inference='not_implemented'),
                  sorting='stratum, workload_id, input_id, numeric block/trial/update IDs; comparisons in plan order',
                  eligibility='strict complete validator; classification independent of structural validity; declared provenance not attestation',
                  figure_generation=figures,rendering_error=rendering_error,exclusions=[e for e in acceptances if not e['accepted']])
    outputs={p.relative_to(output).as_posix():file_digest(p) for p in sorted(output.rglob('*')) if p.is_file()}
    manifest['output_sha256']=outputs
    write_json(output/'analysis-manifest.json',manifest)
    title='SYNTHETIC FIXTURE ANALYSIS' if any(d['item']['synthetic'] for d in datasets) else 'Descriptive timing analysis'
    (output/'report.md').write_text('# '+title+'\n\nStatus: '+manifest['status']+'.\n\n'+
        'Primary: incremental / dijkstra. Prespecified adaptive comparisons: heuristic / dijkstra, incremental, delta-stepping. Negative log ratios favor the numerator.\n\n'+
        'All confidence intervals are null: inference_not_implemented. Blocks and ordered updates are correlated. Four balanced Codespaces blocks do not establish independent hardware replication. Session labels and independence declarations are user-supplied.\n\n'+
        'Full-trace and per-update modes, executable builds, actual execution settings, evidence classes and hardware environments are separate strata. Panels require all declared workloads within every session and use explicit workload weights.\n\n'+
        'Figures use derived CSV tables. Observed ranges are descriptive, not confidence intervals. Initial recipe distributions are not distributions measured throughout the evolving trace.\n\n'+
        'Selected adaptive backends, affected counts, actual teams, isolated selector cost and counterfactual runtimes are unavailable. The public update interval includes selector work; no isolated overhead is inferred. Shared fast paths also apply to the forced-Dijkstra service baseline.\n\n'+
        'Raw evidence was not executed or modified. See acceptance.jsonl for all eligibility/exclusion reasons and analysis-manifest.json for identity inventories.\n',encoding='utf-8')
    manifest['output_sha256']={p.relative_to(output).as_posix():file_digest(p) for p in sorted(output.rglob('*')) if p.is_file() and p.name!='analysis-manifest.json'}
    write_json(output/'analysis-manifest.json',manifest)
    if fatal: raise AnalysisFailure('analysis failed; inspect acceptance.jsonl and analysis-manifest.json')
    return dict(schema_version=1,status='complete',accepted_inputs=summaries['accepted_input_count'],figures=str(len(figures['products'])))


def main():
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('--plan',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        result=analyze(args.plan,args.output)
        sys.stdout.buffer.write(canonical_json(result));return 0
    except Exception as exception:
        print('analysis error: '+str(exception),file=sys.stderr);return 2


if __name__=='__main__': sys.exit(main())
