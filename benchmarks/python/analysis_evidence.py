"""Read-only, anchored Phase D import. Reuse pilot/journal semantic verifiers.

An expected inventory digest anchors transfer integrity, not producer authenticity.
No pilot record, export flag or caller option can grant scientific admission.
"""
import os
from pathlib import Path
import re
from collections import Counter
from campaign_pilot import read_json, regular_bytes, verify_pilot
from campaign_journal import inspect_recovery
from campaign_contract import expand, plan_hash, safe_path
from workloads import canonical_json, sha256
from analysis_inference import unavailable_performance

PLAN='f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24'
MANIFEST='f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a'
VERSION='phase-e-evidence-v1'


def anchored_inventory(root, expected):
    if type(expected) is not str or not re.fullmatch('[0-9a-f]{64}',expected):
        raise ValueError('explicit trusted inventory SHA-256 required')
    root=Path(root).absolute()
    raw=regular_bytes(root/'audit-sha256.json',4*1048576)
    if sha256(raw)!=expected:raise ValueError('inventory anchor mismatch')
    index=read_json(root/'audit-sha256.json')
    if type(index) is not dict or not 1<=len(index)<=8192:raise ValueError('inventory size')
    actual=set();total=0
    for directory,dirs,files in os.walk(root,followlinks=False):
        for name in dirs:
            if (Path(directory)/name).is_symlink():raise ValueError('symlink directory in input')
        for name in files:
            path=Path(directory)/name;relative=path.relative_to(root).as_posix()
            if relative=='audit-sha256.json':continue
            actual.add(relative)
            if len(actual)>8192:raise ValueError('inventory entry limit')
    if actual!=set(index):raise ValueError('complete input inventory mismatch')
    for name,digest in index.items():
        safe_path(name)
        if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('invalid input digest')
        raw=regular_bytes(root/name,64*1048576);total+=len(raw)
        if total>256*1048576:raise ValueError('input byte budget')
        if sha256(raw)!=digest:raise ValueError('input digest mismatch: '+name)
    return index


def original_rows(manifest):
    rows=[]
    for t in manifest['trials']:
        rows.append(dict(schema='dynagraph-phase-d-evidence-export',schema_version=1,
            scientific_eligibility=False,timing_eligible=False,timing_values=None,
            timing_unavailable_reason='not executed',inference_allowed=False,
            identity_scope='original-preserved-plan',trial_id=t['trial_id'],trial=t,
            algorithm=t['policy'],workload_category='development/chain',requested_workers=t['workers'],
            actual_workers=None,git_revision=None,correctness_status='not-executed',correctness_result=None,
            resource_interference='unavailable',evidence_verification='not-executed',eligibility='unexecuted',
            execution_id=None,attempt_id=None,environment_provenance=None))
    return rows


def diagnostic_row(root,pilot,plan,original,item):
    tid=item['trial_id'];directory=pilot/tid
    record=read_json(directory/'record.json');resource=read_json(directory/'resource-bound.json')
    workload=read_json(directory/'workload-native.json');binding=resource['binding'];t=record['trial']
    if (item['classification']!='verified-complete' or record['status']!='success' or
        record['correctness']['outcome']!='passed' or record['measurement_eligible'] is not False or
        resource['coverage_complete'] is not True or resource['scientific_performance_allowed'] is not False or
        resource['measurement_eligible'] is not False or t['phase']!='diagnostic'):
        raise ValueError('pilot cannot supply eligible scientific timing')
    teams=sorted({thread['team'] for region in workload['regions'] for thread in region['threads']})
    if not teams or any(type(team) is not int or not 1<=team<=t['workers'] for team in teams):
        raise ValueError('invalid observed teams')
    journal=[]
    for path in sorted((pilot/'recovery-journal').glob('*.json')):
        entry=read_json(path)
        if entry['payload'].get('trial_id')==tid:
            journal.append({'path':str(path.relative_to(root)),'sha256':sha256(regular_bytes(path,64*1048576)),'entry_id':entry['entry_id']})
    evidence={str(path.relative_to(root)):sha256(regular_bytes(path,64*1048576)) for path in sorted(directory.rglob('*')) if path.is_file()}
    return dict(schema='dynagraph-phase-d-evidence-export',schema_version=1,
        scientific_eligibility=False,timing_eligible=False,timing_values=None,inference_allowed=False,
        identity_scope='derived-bounded-diagnostic',trial_id=tid,trial=t,
        corresponding_original_trial_id=original['trials'][t['sequence']]['trial_id'],
        algorithm=t['policy'],workload_category='development/chain',requested_workers=t['workers'],actual_workers=teams,
        git_revision=plan['build']['revision'],executable_sha256=record['executable_sha256'],command=binding['command'],
        execution_id=binding['execution_id'],attempt_id=binding['attempt_id'],plan_sha256=record['plan_sha256'],
        manifest_sha256=record['manifest_sha256'],correctness_status=record['correctness']['outcome'],correctness_result=record['correctness'],
        resource_interference=resource['classification'],resource_coverage_complete=resource['coverage_complete'],
        resource_counter_deltas=resource['counter_deltas'],evidence_verification='verified-complete',eligibility='diagnostic-only',
        timing_unavailable_reason='diagnostic verification-only command; timing explicitly excluded by observation contract',
        environment_provenance={'hardware_path':'execution/pilot/hardware.json','hardware_sha256':record['hardware_sha256'],
            'requested_affinity':record['requested_affinity'],'observed_parent_affinity':record['observed_affinity'],
            'openmp_environment':record['openmp_environment'],'process_generation':resource['process_generation']},
        timestamps={'start':record['start'],'end':record['end']},journal=journal,evidence_sha256=evidence,
        schema_versions={'pilot':record['schema_version'],'workload_native':workload['schema_version'],'resource_bound':resource['schema_version'],'journal':1})


def reconcile_exports(root,original,diagnostics):
    """Compare every serialized field/type, including unavailable flags and IDs."""
    for name,rows in (('original-trials.jsonl',original),('diagnostic-trials.jsonl',diagnostics)):
        raw=regular_bytes(Path(root)/'phase-e-preparation'/name,4*1048576)
        if raw!=b''.join(canonical_json(row) for row in rows):
            raise ValueError('export contradicts verified evidence: '+name)


def load_phase_d(root,expected_inventory):
    root=Path(root).absolute();before=anchored_inventory(root,expected_inventory)
    p=read_json(root/'original-plan.json');original=read_json(root/'original-manifest.json')
    if plan_hash(p)!=PLAN or sha256(canonical_json(original))!=MANIFEST or canonical_json(expand(p))!=canonical_json(original):
        raise ValueError('original manifest/golden mismatch')
    pilot=root/'execution/pilot';verified=verify_pilot(pilot);recovery=inspect_recovery(pilot)
    if verified['execution_status']!='complete' or recovery['status']!='settled':raise ValueError('pilot incomplete')
    plan=read_json(pilot/'plan.json');derived=read_json(pilot/'trial-manifest.json')
    if canonical_json(plan)!=canonical_json(read_json(root/'execution/inputs/plan.json')) or canonical_json(derived)!=canonical_json(expand(plan)):
        raise ValueError('derived manifest substitution')
    # Only the documented build/provenance fields may differ; all experimental
    # parameters and ordering must stay equal, never joining by a rewritten ID.
    normalized=read_json(pilot/'plan.json')
    for key in ('revision','executable_sha256','compiler_sha256','openmp_sha256','flags_sha256'):
        normalized['build'][key]=p['build'][key]
    normalized['hardware']['allocated_cpus']=p['hardware']['allocated_cpus']
    if canonical_json(normalized)!=canonical_json(p):raise ValueError('incompatible derived configuration')
    if sha256(regular_bytes(root/'build-provenance/release/dynagraph_bench-flags.make',1048576))!=plan['build']['flags_sha256']:
        raise ValueError('build flags identity mismatch')
    if {t['trial_id'] for t in original['trials']}&{t['trial_id'] for t in derived['trials']}:
        raise ValueError('original/pilot identities overlap')
    if len(recovery['trials'])!=2:raise ValueError('Phase D selected trial count mismatch')
    diagnostics=[diagnostic_row(root,pilot,plan,original,item) for item in recovery['trials']]
    if sorted(row['requested_workers'] for row in diagnostics)!=[1,2]:raise ValueError('worker configuration mismatch')
    original_export=original_rows(original);reconcile_exports(root,original_export,diagnostics)
    summary=read_json(root/'phase-e-preparation/summary.json')
    counts={'planned':104,'selected':0,'attempted':0,'completed':0,'verified_complete':0,
            'interrupted':0,'rejected':0,'unexecuted':104,'diagnostic_only':0,'scientifically_eligible':0}
    pilot_counts={'planned':104,'selected':2,'attempted':2,'completed':2,'verified_complete':2,
                  'interrupted':0,'rejected':0,'unexecuted':102,'diagnostic_only':2,'scientifically_eligible':0}
    expected_original={k:v for k,v in counts.items() if k!='selected'}
    expected_derived={'planned_for_execution':2,'attempted':2,'completed':2,'verified_complete':2,'interrupted':0,
                      'rejected':0,'unexecuted_selected':0,'scientifically_eligible':0,'diagnostic_only':2,'expanded_manifest':104,'unselected':102}
    classifications=dict(sorted(Counter(row['resource_interference'] for row in diagnostics).items()))
    expected_summary={'original_campaign':expected_original,'derived_pilot':expected_derived,
        'regression_controls':'separate test fixtures, excluded from campaign/pilot counts',
        'full_campaign_authorized_by_current_executor':False,'scientific_eligibility':False,'statistics_computed':False,
        'resource_classifications':classifications,'paths':{'original_rows':'phase-e-preparation/original-trials.jsonl','diagnostic_rows':'phase-e-preparation/diagnostic-trials.jsonl'}}
    if canonical_json(summary)!=canonical_json(expected_summary):raise ValueError('Phase D summary contradicts evidence')
    if anchored_inventory(root,expected_inventory)!=before:raise ValueError('input changed during analysis')
    return {'analysis_version':VERSION,'source_inventory_sha256':expected_inventory,'input_files':before,
            'original_plan_sha256':PLAN,'original_manifest_sha256':MANIFEST,
            'original_campaign':counts,'derived_pilot':pilot_counts,'resource_classifications':classifications,
            'diagnostics':diagnostics,'scientific_eligibility':False,'performance':unavailable_performance(),
            'limitations':['local consistency and anchored transfer integrity, not authenticated producer evidence',
                          'original 104 trials unexecuted; two diagnostic verification-only processes',
                          'observed interference; no scientific timing, isolation or physical-core scaling evidence',
                          'TSan acceptance unmet; scientific adapter not implemented for future campaigns']}
