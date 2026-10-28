"""Read-only analysis-plan and complete timing-evidence import."""
from pathlib import Path
import re
from fractions import Fraction

from experiment_records import loads, uint, validate_dataset, read_jsonl, POLICIES
from workloads import canonical_json, fingerprint, object_fields, parse_graph, parse_trace, sha256

CLASSES=('valid_harness_only','valid_performance_unconfirmed','performance_eligible')
FIGURES=('paired-ratios','policy-runtimes','latency-ecdf','update-profile','family-ratios','adaptive-comparisons','block-order')
ID_FIELDS=('graph_sha256','trace_sha256','executable_sha256','configuration_sha256','manifest_sha256')
CONFIG_FIELDS=('timing_mode','delta','threads','no_effect','warmups')
COMPARISONS=(('incremental','dijkstra','primary'),('heuristic','dijkstra','adaptive'),
             ('heuristic','incremental','adaptive'),('heuristic','delta-stepping','adaptive'))


class ImportRejected(ValueError):
    def __init__(self,code,message):
        super().__init__(message)
        self.code=code


def label(value):
    if not isinstance(value,str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',value) is None:
        raise ValueError('invalid plan label')
    return value


def fields(value,names):
    object_fields(value,names,'analysis plan object')


def text(value):
    if not isinstance(value,str) or not value.strip() or '\x00' in value:
        raise ValueError('nonempty text required')
    return value


def validate_plan(value):
    fields(value,('schema_version','inputs','workloads','compatible_configurations','comparisons','allowed_evidence_classes','figures','exclusions'))
    if type(value['schema_version']) is not int or value['schema_version']!=1:
        raise ValueError('unsupported analysis-plan version')
    for key in ('inputs','workloads','compatible_configurations','comparisons','allowed_evidence_classes','figures','exclusions'):
        if type(value[key]) is not list or len(value[key])>10000:
            raise ValueError('bounded plan arrays required')
    if not value['inputs'] or not value['workloads'] or not value['compatible_configurations']:
        raise ValueError('inputs, workloads and configurations required')
    for key,allowed in (('allowed_evidence_classes',CLASSES),('figures',FIGURES)):
        if any(item not in allowed for item in value[key]) or len(value[key])!=len(set(value[key])):
            raise ValueError('unsupported or duplicate '+key)
    if not value['allowed_evidence_classes']:
        raise ValueError('allowed evidence classes required')
    workloads={}
    content=set()
    for item in value['workloads']:
        if type(item) is not dict:
            raise ValueError('workload object required')
        item.setdefault('weight',{'numerator':'1','denominator':'1'})
        fields(item,('id','graph_sha256','trace_sha256','source','dependence_group','weight'))
        label(item['id']);label(item['dependence_group'])
        for key in ('graph_sha256','trace_sha256'):
            fingerprint(item[key],key)
        uint(item['source'],99999)
        fields(item['weight'],('numerator','denominator'))
        if not uint(item['weight']['numerator']) or not uint(item['weight']['denominator']):
            raise ValueError('positive workload weight required')
        identity=(item['graph_sha256'],item['trace_sha256'],item['source'])
        if item['id'] in workloads or identity in content:
            raise ValueError('duplicate workload identity or label')
        workloads[item['id']]=item;content.add(identity)
    configurations={}
    for item in value['compatible_configurations']:
        fields(item,('id',*CONFIG_FIELDS,'executable_sha256','build_type'))
        label(item['id'])
        if item['id'] in configurations:
            raise ValueError('duplicate configuration group')
        if item['timing_mode'] not in ('full-trace','per-update') or item['no_effect'] not in ('shared_fast_path','execute_selected'):
            raise ValueError('unsupported execution settings')
        if not uint(item['delta']):
            raise ValueError('positive delta required')
        uint(item['threads'],64);uint(item['warmups'],100)
        if item['executable_sha256'] is not None:
            fingerprint(item['executable_sha256'],'expected executable')
        if item['build_type'] is not None:
            text(item['build_type'])
        configurations[item['id']]=item
    inputs=set()
    sessions={}
    for item in value['inputs']:
        fields(item,('id','path','workload_id','configuration_group','hardware_id','session_id','session_independence_declared',
                     'synthetic','evidence_intent','expected_identities','controlled_hardware_evidence','instrumentation_evidence'))
        for key in ('id','workload_id','configuration_group','hardware_id','session_id'):
            label(item[key])
        text(item['path'])
        if item['id'] in inputs or item['workload_id'] not in workloads or item['configuration_group'] not in configurations:
            raise ValueError('duplicate input or unknown plan reference')
        if any(type(item[key]) is not bool for key in ('synthetic','session_independence_declared')) or item['evidence_intent'] not in ('harness','performance','unconfirmed'):
            raise ValueError('invalid evidence declarations')
        fields(item['expected_identities'],ID_FIELDS)
        for key in ID_FIELDS:
            if item['expected_identities'][key] is not None:
                fingerprint(item['expected_identities'][key],key)
        for key in ('controlled_hardware_evidence','instrumentation_evidence'):
            if item[key] is not None:
                fields(item[key],('path','sha256'));text(item[key]['path']);fingerprint(item[key]['sha256'],key)
        session_key=(item['hardware_id'],item['session_id'])
        if session_key in sessions and sessions[session_key]!=item['session_independence_declared']:
            raise ValueError('inconsistent session independence declarations')
        sessions[session_key]=item['session_independence_declared']
        inputs.add(item['id'])
    comparisons=set()
    declared=set()
    for item in value['comparisons']:
        fields(item,('numerator','baseline','family'))
        a,b,f=item['numerator'],item['baseline'],item['family']
        if a not in POLICIES or b not in POLICIES or a==b or f not in ('primary','adaptive','exploratory') or (a,b) in comparisons:
            raise ValueError('invalid or duplicate comparison')
        if (a,b,f) not in COMPARISONS and f!='exploratory':
            raise ValueError('unapproved comparison family')
        comparisons.add((a,b));declared.add((a,b,f))
    if not set(COMPARISONS)<=declared:
        raise ValueError('primary and all adaptive comparisons required')
    excluded=set()
    for item in value['exclusions']:
        fields(item,('input_id','reason'));text(item['reason'])
        if item['input_id'] not in inputs or item['input_id'] in excluded:
            raise ValueError('invalid exclusion reference')
        excluded.add(item['input_id'])
    return value


def read_plan(path):
    data=Path(path).read_bytes()
    if len(data)>1024*1024:
        raise ValueError('analysis plan exceeds 1 MiB')
    return validate_plan(loads(data))


def file_digest(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('evidence must contain regular files without symlinks: '+str(path))
    import hashlib
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(directory):
    directory=Path(directory)
    if directory.is_symlink():
        raise ValueError('symlink experiment directory unsupported')
    result={}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('symlink evidence unsupported')
        if path.is_file():
            result[path.relative_to(directory).as_posix()]=file_digest(path)
    if not result:
        raise ValueError('missing experiment evidence')
    return result


def provenance_files(item,base):
    result={}
    for key,scope in (('controlled_hardware_evidence','controlled_hardware'),('instrumentation_evidence','uninstrumented_build')):
        declaration=item[key]
        if declaration is not None:
            path=(base/declaration['path']).resolve()
            digest=file_digest(path)
            if digest!=declaration['sha256']:
                raise ImportRejected('declaration_identity_mismatch',key)
            data=path.read_bytes()
            if len(data)>65536:
                raise ValueError('declaration exceeds 64 KiB')
            value=loads(data)
            fields(value,('schema_version','scope','statement'))
            if type(value['schema_version']) is not int or value['schema_version']!=1 or value['scope']!=scope:
                raise ValueError('unsupported provenance declaration')
            text(value['statement'])
            result[key]=dict(path=str(path),sha256=digest,origin='user_supplied',statement=value['statement'])
    return result


def classify(item,environments,declarations):
    instrumentation=[]
    unknown=False
    for environment in environments:
        metadata=environment['metadata']
        flags=metadata['flags']['value']
        declared=metadata['sanitizers']['value']
        build=metadata['build_type']['value']
        if not isinstance(flags,str) or not flags.strip() or declared!='none_declared' or build!='Release':
            unknown=True
        if declared=='declared_in_flags' or (isinstance(flags,str) and re.search(r'(?i)sanitize|--coverage|\bcoverage\b|-fprofile|-finstrument|-pg?(?:\s|;|$)',flags)):
            instrumentation.append('declared_instrumentation')
    if item['synthetic']:
        return 'valid_harness_only',['synthetic_fixture_not_measured_performance']
    if instrumentation:
        return 'valid_harness_only',sorted(set(instrumentation))
    if item['evidence_intent']=='harness':
        return 'valid_harness_only',['declared_harness_only']
    if (unknown or item['evidence_intent']!='performance' or
            set(declarations)!= {'controlled_hardware_evidence','instrumentation_evidence'}):
        return 'valid_performance_unconfirmed',['release_build_and_explicit_hardware_and_instrumentation_provenance_required']
    return 'performance_eligible',['eligibility_under_user_supplied_declarations_not_independent_hardware_attestation']


def import_input(item,plan,base,seen):
    directory=base/item['path']
    if directory.is_symlink():
        raise ImportRejected('symlink_evidence','symlink experiment directory unsupported')
    directory=directory.resolve()
    before=inventory(directory)
    # Public complete-dataset acceptance only; never execute any evidence binary.
    validate_dataset(directory/'records.jsonl')
    records=read_jsonl((directory/'records.jsonl').read_bytes())
    first=records[0]
    duplicate=(first['run_id'],before['records.jsonl'])
    if first['run_id'] in {entry[0] for entry in seen} or before['records.jsonl'] in {entry[1] for entry in seen}:
        raise ImportRejected('duplicate_experiment','copied evidence cannot add replication')
    seen.add(duplicate)
    for key,expected in item['expected_identities'].items():
        if expected is not None and first[key]!=expected:
            raise ImportRejected('expected_identity_mismatch',key)
    workload=next(w for w in plan['workloads'] if w['id']==item['workload_id'])
    config=next(c for c in plan['compatible_configurations'] if c['id']==item['configuration_group'])
    manifest=loads((directory/'workload/manifest.json').read_bytes())
    if (first['graph_sha256'],first['trace_sha256'],str(manifest['source'])) != (workload['graph_sha256'],workload['trace_sha256'],workload['source']):
        raise ImportRejected('workload_identity_mismatch',item['workload_id'])
    if any(first['configuration'][key]!=config[key] for key in CONFIG_FIELDS):
        raise ImportRejected('execution_configuration_mismatch',item['configuration_group'])
    if config['executable_sha256'] is not None and first['executable_sha256']!=config['executable_sha256']:
        raise ImportRejected('executable_identity_mismatch',item['configuration_group'])
    environments=[r for r in records if r['record_type']=='environment' and r['trial_id'] is not None]
    if config['build_type'] is not None and any(e['metadata']['build_type']['value']!=config['build_type'] for e in environments):
        raise ImportRejected('build_configuration_mismatch',item['configuration_group'])
    if len({sha256(canonical_json(e['metadata'])) for e in environments})!=1:
        raise ImportRejected('worker_environment_mismatch','incompatible within-run worker metadata')
    declarations=provenance_files(item,base)
    classification,reasons=classify(item,environments,declarations)
    # Actual measured compatibility, not equality of caller labels alone.
    host=next(r['metadata'] for r in records if r['record_type']=='environment' and r['trial_id'] is None)
    host={k:v for k,v in host.items() if k not in ('source_git_revision','source_git_dirty')}
    compatibility=dict(configuration={k:first['configuration'][k] for k in CONFIG_FIELDS},executable_sha256=first['executable_sha256'],
                       worker_metadata=environments[0]['metadata'],host_metadata=host,hardware_id=item['hardware_id'],
                       evidence_class=classification,synthetic=item['synthetic'])
    stratum=sha256(canonical_json(compatibility))
    if inventory(directory)!=before:
        raise ImportRejected('evidence_changed','evidence changed during validation')
    return dict(item=item,directory=directory,inventory=before,records=records,manifest=manifest,stratum=stratum,
                compatibility=compatibility,evidence_class=classification,reasons=reasons,declarations=declarations,workload=workload)


def workload_features(dataset):
    graph=parse_graph((dataset['directory']/'workload/graph.txt').read_bytes())
    trace=parse_trace((dataset['directory']/'workload/trace.txt').read_bytes())
    adjacency=[[] for _ in range(graph.vertices)]
    for u,v,_ in graph.edges:
        adjacency[u].append(v)
    reached={trace.source};pending=[trace.source]
    while pending:
        for v in adjacency[pending.pop()]:
            if v not in reached:
                reached.add(v);pending.append(v)
    schedule=dataset['manifest']['configuration']['trace']['schedule']
    features=[]
    previous=None
    for index,u,v,old,new in trace.updates:
        features.append(dict(update_index=str(index),request_kind='equal' if new==old else 'strict_decrease',decrease_magnitude=str(old-new),
                             consecutive_repeated_endpoints=previous==(u,v),generator_schedule_mode=schedule[index%len(schedule)],
                             tail_reachability='reachable' if u in reached else 'unreachable',feature_origin='derived_from_verified_trace_and_topology',
                             actual_selected_backend=None,affected_vertices=None,actual_workers=None,selector_overhead=None))
        previous=(u,v)
    return features


def trial_rows(dataset):
    from analysis_stats import duration,fraction_text
    item=dataset['item'];manifest=dataset['manifest'];first=dataset['records'][0]
    features=workload_features(dataset)
    starts={r['trial_id']:r for r in dataset['records'] if r['record_type']=='trial_start'}
    probes={r['trial_id']:r for r in dataset['records'] if r['record_type']=='clock_probe'}
    workload_id=item['workload_id']
    base=dict(input_id=item['id'],dependence_group=dataset['workload']['dependence_group'],stratum=dataset['stratum'],workload_id=workload_id,hardware_id=item['hardware_id'],session_id=item['session_id'],
              session_independence_declared=item['session_independence_declared'],evidence_class=dataset['evidence_class'],synthetic=item['synthetic'],
              run_id=first['run_id'],graph_sha256=first['graph_sha256'],trace_sha256=first['trace_sha256'],executable_sha256=first['executable_sha256'],
              configuration_sha256=first['configuration_sha256'],timing_mode=first['configuration']['timing_mode'],
              no_effect=first['configuration']['no_effect'],family=manifest['configuration']['graph']['family'],
              weight_distribution=manifest['configuration']['weights']['kind'],vertices=str(manifest['counts']['vertices']),edges=str(manifest['counts']['edges']))
    rows=[]
    for record in dataset['records']:
        if record['record_type'] not in ('trial_measurement','update_latency'):
            continue
        trial_id=record['trial_id'];probe=probes[trial_id];start=starts[trial_id]
        seconds=duration(record['elapsed_ticks'],probe['period_num'],probe['period_den'],record['elapsed_ns'])
        row=dict(base,trial_id=trial_id,block_id=record['block_id'],policy=record['policy'],policy_position=start['policy_position'],
                 update_index=record['update_index'],elapsed_ticks=record['elapsed_ticks'],elapsed_ns=record['elapsed_ns'],
                 period_num=probe['period_num'],period_den=probe['period_den'],duration_seconds=fraction_text(seconds))
        if record['update_index'] is not None:
            row.update(features[int(record['update_index'])])
        rows.append(row)
    return rows
