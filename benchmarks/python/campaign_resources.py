"""Resource-control contracts v1: read-only assessment, never execution authority."""
import copy
from pathlib import Path

from campaign_contract import fields, digest, integer, load_bytes, safe_path
from campaign_provenance import cpu_array, topology_ids, validate_cgroups
from campaign_runtime import MARKER, time_range
from workloads import canonical_json, sha256

REQUIREMENTS = ('applied_affinity', 'observed_affinity', 'online_cpus', 'cpuset',
                'quota', 'topology', 'numa', 'openmp_team', 'exclusivity', 'uncontended', 'isolation')
OBSERVATIONS = ('affinity', 'online_cpus', 'cgroups', 'topology', 'numa',
                'openmp_team', 'exclusivity', 'uncontended', 'isolation')
STATES = ('rejected', 'indeterminate', 'development_only', 'eligible')
LIMITATIONS = ('Contract validation is not physical resource isolation or producer authentication',
               'Child leader snapshots are not worker placement or stable allocation',
               'Topology/NUMA are earlier observer context; hidden host restrictions unverified',
               'Enforcement, workload-region instrumentation and scientific admission are deferred')


def schema(value, name, keys):
    fields(value, 'schema schema_version '+keys, name)
    if (value['schema'] != 'dynagraph-'+name or type(value['schema_version']) is not int or
            value['schema_version'] != 1):
        raise ValueError('unsupported '+name+' schema')


def fact(value, source, scope, reference, start=None, end=None):
    return dict(value=value, source=source, scope=scope, reference=reference,
                start=start, end=end, status='unavailable' if value is None else 'observed')


def resource_context(directory, trial_id, process_index=0):
    """Reverify existing evidence. Never read sidecar-selected paths or run a runner.

    Journal pilots (including incomplete originals) use the recovery gate. Legacy
    final pilots use the full v2 verifier. No old file is relabelled or rewritten.
    """
    from campaign_journal import binding, bounded_inventory, inspect_recovery
    from campaign_pilot import pilot_context, read_json, verify_pilot, regular_bytes, MAX_ARTIFACT
    directory = Path(directory).resolve(strict=True)
    digest(trial_id); integer(process_index, 0, 1, 'process index')
    def evidence_inventory():
        values=bounded_inventory(directory)
        if (directory/'sha256.json').exists():
            values['sha256.json']=sha256(regular_bytes(directory/'sha256.json',MAX_ARTIFACT))
        return values
    inventory = evidence_inventory()
    recovery = None
    if (directory/'recovery-journal').exists():
        recovery = inspect_recovery(directory)
    else:
        verify_pilot(directory)
    context = pilot_context(directory)
    plan, manifest, execution, selected, hardware = context
    if trial_id not in {t['trial_id'] for t in selected}:
        raise ValueError('resource trial not selected')
    record = read_json(directory/trial_id/'record.json')
    if process_index >= len(record['processes']):
        raise ValueError('resource assessment requires a verified process receipt')
    process = record['processes'][process_index]
    trial_success = record['status']=='success'
    if recovery is not None:
        classification = next(t['classification'] for t in recovery['trials'] if t['trial_id']==trial_id)
        trial_success = (True if classification=='verified-complete' else
                         False if classification in ('failed','interrupted') else None)
    bound = binding(directory, context)
    names = dict(plan='plan.json', manifest='trial-manifest.json', execution='execution-manifest.json',
                 hardware='hardware.json', record=trial_id+'/record.json')
    snapshot = None
    if record['execution_observations'] == MARKER:
        name = f"{trial_id}/{process_index}-{process['command'][1]}.runtime.json"
        names['runtime'] = name
        snapshot = read_json(directory/name)['snapshot']
    references = {k:dict(path=v, sha256=inventory[v]) for k,v in names.items()}
    references.setdefault('runtime', None)
    observations = {}
    for key, source_key, scope in (('affinity','affinity','child leader snapshot'),
                                   ('online_cpus','online_cpus','observer namespace'),
                                   ('cgroups','cgroups','child visible cgroup2 hierarchy')):
        row = snapshot[source_key] if snapshot else None
        observations[key] = fact(copy.deepcopy(row['value']) if row else None,
                                 row['source'] if row else 'legacy or unavailable runtime evidence',
                                 row['scope'] if row else scope, 'runtime' if 'runtime' in names else 'record',
                                 snapshot['start'] if snapshot else None, snapshot['end'] if snapshot else None)
    for key in ('topology','numa'):
        observations[key] = fact(copy.deepcopy(hardware[key]['value']), hardware[key]['source'],
                                 'pre-launch observer context; collection time unavailable', 'hardware')
    for key in ('openmp_team','exclusivity','uncontended','isolation'):
        observations[key] = fact(None, 'no supported independent evidence in this phase',
                                 'unverified; no workload-region or resource ownership proof', 'record')
    matched = snapshot is not None and snapshot['executable_match']
    result = dict(binding=dict(execution_id=bound['pilot_execution_id'], trial_id=trial_id,
                             journal_binding_sha256=sha256(canonical_json(bound)),
                             process_index=process_index, executable_sha256=record['executable_sha256'],
                             pid=snapshot['pid'] if matched else None,
                             process_start_ticks=snapshot['process_start_ticks'] if matched else None),
                references=references, request=dict(affinity=plan['hardware']['allocated_cpus'],
                    workers=record['trial']['workers'], openmp=record['openmp_environment'],
                    min_physical_cores=plan['hardware']['min_physical_cores'], allow_smt=plan['hardware']['allow_smt']),
                observations=observations, process_interval=dict(start=process['start'],end=process['end']),
                trial_success=trial_success)
    if evidence_inventory()!=inventory:
        raise ValueError('resource evidence changed during inspection')
    return result


def controls(context, purpose='development'):
    """Build a sidecar proposal; this function applies no resource setting."""
    if purpose not in ('development','scientific'):
        raise ValueError('invalid resource assessment purpose')
    return dict(schema='dynagraph-resource-controls', schema_version=1, **copy.deepcopy(context),
                purpose=purpose, requirements={k:purpose=='scientific' for k in REQUIREMENTS},
                application=dict(state='not_attempted', cpus=None, receipt=None))


def validate_controls(value, context):
    # Same 1 MiB, depth and node limits as campaign metadata, even for pure callers.
    load_bytes(canonical_json(value))
    schema(value, 'resource-controls', 'binding references request observations process_interval trial_success purpose requirements application')
    for key in ('binding','references','request','observations','process_interval','trial_success'):
        if canonical_json(value[key]) != canonical_json(context[key]):
            raise ValueError('resource evidence/context mismatch: '+key)
    b = value['binding']
    fields(b, 'execution_id trial_id journal_binding_sha256 process_index executable_sha256 pid process_start_ticks', 'resource binding')
    for k in ('execution_id','trial_id','journal_binding_sha256','executable_sha256'): digest(b[k])
    integer(b['process_index'],0,1,'process index')
    if (b['pid'] is None) != (b['process_start_ticks'] is None):
        raise ValueError('incomplete resource process identity')
    if b['pid'] is not None:
        integer(b['pid'],1,1<<30,'resource PID');integer(b['process_start_ticks'],1,(1<<63)-1,'resource start ticks')
    if value['trial_success'] is not None and type(value['trial_success']) is not bool:
        raise ValueError('invalid trial success')
    fields(value['references'],'plan manifest execution hardware record runtime','resource references')
    for key, reference in value['references'].items():
        if key=='runtime' and reference is None:continue
        fields(reference,'path sha256','resource evidence reference')
        safe_path(reference['path']);digest(reference['sha256'])
    fields(value['process_interval'],'start end','resource process interval')
    time_range(value['process_interval']['start'],value['process_interval']['end'])
    if value['purpose'] not in ('development','scientific'):
        raise ValueError('invalid resource assessment purpose')
    fields(value['requirements'], ' '.join(REQUIREMENTS), 'resource requirements')
    if any(type(v) is not bool for v in value['requirements'].values()):
        raise ValueError('resource requirements must be boolean')
    if value['purpose']=='scientific' and not all(value['requirements'].values()):
        raise ValueError('scientific requirements cannot be weakened')
    request = value['request']
    fields(request,'affinity workers openmp min_physical_cores allow_smt','resource request')
    cpu_array(request['affinity']);integer(request['workers'],1,64,'resource workers')
    integer(request['min_physical_cores'],1,4096,'physical core requirement')
    if type(request['allow_smt']) is not bool or request['openmp'] != dict(
            OMP_NUM_THREADS=str(request['workers']),OMP_DYNAMIC='FALSE',OMP_THREAD_LIMIT=str(request['workers'])):
        raise ValueError('invalid requested OpenMP/SMT controls')
    fields(value['observations'],' '.join(OBSERVATIONS),'resource observations')
    for key, row in value['observations'].items():
        fields(row,'value source scope reference start end status','resource observation')
        if any(type(row[k]) is not str or not 1<=len(row[k])<=4096 for k in ('source','scope')):
            raise ValueError('invalid resource source/scope')
        if row['reference'] not in value['references'] or value['references'][row['reference']] is None:
            raise ValueError('missing resource evidence reference')
        if row['status'] != ('unavailable' if row['value'] is None else 'observed'):
            raise ValueError('contradictory resource observation status')
        if row['start'] is None or row['end'] is None:
            if row['start'] is not None or row['end'] is not None:
                raise ValueError('incomplete observation interval')
        else: time_range(row['start'],row['end'])
        v = row['value']
        if v is None: continue
        if key in ('affinity','online_cpus'):cpu_array(v)
        elif key=='cgroups':validate_cgroups(v)
        elif key in ('openmp_team','exclusivity','uncontended','isolation'):
            raise ValueError('unsupported team/isolation guarantee in resource v1')
    topology = value['observations']['topology']['value'];numa = value['observations']['numa']['value']
    if topology is not None:topology_ids(topology,len(topology),numa)
    elif numa is not None:
        # Validate supplied NUMA shape/IDs even if required core topology is missing.
        if type(numa) is not list or not 1<=len(numa)<=1024:raise ValueError('invalid NUMA records')
        seen_nodes=set();seen_cpus=set()
        for row in numa:
            fields(row,'node cpus','NUMA node');integer(row['node'],0,1048575,'NUMA node')
            if row['cpus'] != []:cpu_array(row['cpus'])
            elif type(row['cpus']) is not list:raise ValueError('invalid NUMA CPUs')
            if row['node'] in seen_nodes or seen_cpus.intersection(row['cpus']):raise ValueError('ambiguous NUMA assignment')
            seen_nodes.add(row['node']);seen_cpus.update(row['cpus'])
    validate_application(value)
    return value


def validate_application(value):
    a = value['application'];fields(a,'state cpus receipt','affinity application')
    if a['state'] in ('not_attempted','unavailable'):
        if a['cpus'] is not None or a['receipt'] is not None:raise ValueError('unapplied affinity contains application evidence')
        return
    if a['state'] not in ('applied','failed'):raise ValueError('invalid affinity application state')
    r=a['receipt'];schema(r,'affinity-application','binding requested_cpus applied_cpus outcome errno mechanism timestamp source scope')
    if canonical_json(r['binding'])!=canonical_json(value['binding']) or value['binding']['pid'] is None:
        raise ValueError('application receipt process binding mismatch')
    if r['mechanism']!='sched_setaffinity' or r['source']!='supplied application receipt' or r['scope']!='child leader only':
        raise ValueError('unsupported application mechanism/source/scope')
    cpu_array(r['requested_cpus'])
    if r['requested_cpus']!=value['request']['affinity']:raise ValueError('application request mismatch')
    integer(r['errno'],0,4095,'application errno')
    time_range(value['process_interval']['start'],r['timestamp'])
    time_range(r['timestamp'],value['process_interval']['end'])
    observed=value['observations']['affinity']
    if observed['start'] is not None:time_range(r['timestamp'],observed['start'])
    if a['state']=='applied':
        cpu_array(a['cpus']);cpu_array(r['applied_cpus'])
        if (r['outcome']!='success' or r['errno']!=0 or a['cpus']!=r['applied_cpus'] or
                a['cpus']!=r['requested_cpus']):raise ValueError('contradictory successful affinity application')
    elif r['outcome']!='failure' or r['errno']==0 or r['applied_cpus'] is not None or a['cpus'] is not None:
        raise ValueError('contradictory failed affinity application')


def assess(value, context):
    validate_controls(value,context)
    request=value['request'];obs=value['observations'];required=value['requirements'];reasons=[]
    def reason(code, outcome, pointer, evidence):
        reasons.append(dict(code=code,outcome=outcome,evidence=[dict(reference='controls#/'+pointer,
                            sha256=sha256(canonical_json(evidence)))]))
    def check(key, condition, code, pointer, evidence):
        if not required[key]:return
        if condition is None:reason(code+'_UNAVAILABLE','unknown',pointer,evidence)
        elif not condition:reason(code+'_FAILED','failure',pointer,evidence)
    if value['trial_success'] is False:reason('TRIAL_NOT_SUCCESSFUL','failure','trial_success',False)
    elif value['trial_success'] is None:reason('TRIAL_COMPLETION_UNAVAILABLE','unknown','trial_success',None)
    app=value['application']
    check('applied_affinity', True if app['state']=='applied' else False if app['state']=='failed' else None,
          'AFFINITY_APPLICATION','application',app)
    affinity=obs['affinity']['value'];cpus=request['affinity'];online=obs['online_cpus']['value'];groups=obs['cgroups']['value']
    check('observed_affinity',None if affinity is None else affinity==cpus,'AFFINITY_MATCH','observations/affinity',obs['affinity'])
    check('online_cpus',None if online is None else set(cpus)<=set(online),'ONLINE_CPUS','observations/online_cpus',obs['online_cpus'])
    check('cpuset',None if groups is None else set(cpus)<=set(groups['effective_cpuset']),
          'CPUSET','observations/cgroups',obs['cgroups'])
    check('quota',None if groups is None else all(q>=request['workers']*p for q,p in groups['quota_pairs']),
          'CPU_QUOTA','observations/cgroups',obs['cgroups'])
    topology=obs['topology']['value'];numa=obs['numa']['value'];enough=None
    if topology is not None:
        ids=topology_ids(topology,len(topology),numa)
        if set(cpus)<=set(ids):
            cores={(ids[c]['package'],ids[c]['core']) for c in cpus}
            enough=len(cores)>=request['min_physical_cores'] and (request['allow_smt'] or len(cores)==len(cpus))
    check('topology',enough,'PHYSICAL_CORES','observations/topology',obs['topology'])
    check('numa',None if numa is None else any(set(cpus)<=set(n['cpus']) for n in numa),
          'NUMA_LOCALITY','observations/numa',obs['numa'])
    for key in ('openmp_team','exclusivity','uncontended','isolation'):
        check(key,None,key.upper(),'observations/'+key,obs[key])
    state=('rejected' if any(r['outcome']=='failure' for r in reasons) else
           'indeterminate' if any(r['outcome']=='unknown' for r in reasons) else 'development_only')
    reason('SCIENTIFIC_ADMISSION_DISABLED','phase_limit','purpose',value['purpose'])
    result=dict(schema='dynagraph-resource-admission',schema_version=1,binding=copy.deepcopy(value['binding']),
                controls_sha256=sha256(canonical_json(value)),state=state,reasons=reasons,
                measurement_eligible=False,scientific_performance_allowed=False,execution_authorized=False,
                transition_policy='immutable-assessment-v1',limitations=list(LIMITATIONS))
    result['assessment_id']=sha256(canonical_json(result))
    return result


def bundle(context, purpose='development'):
    value=controls(context,purpose)
    return dict(schema='dynagraph-resource-assessment',schema_version=1,controls=value,decision=assess(value,context))


def verify_bundle(value, context, previous=None):
    load_bytes(canonical_json(value))
    schema(value,'resource-assessment','controls decision')
    decision=value['decision']
    schema(decision,'resource-admission','binding controls_sha256 state reasons measurement_eligible scientific_performance_allowed execution_authorized transition_policy limitations assessment_id')
    if decision['state'] not in STATES or decision['state']=='eligible':
        raise ValueError('unsupported or premature eligible admission state')
    if canonical_json(decision)!=canonical_json(assess(value['controls'],context)):
        raise ValueError('contradictory resource admission decision')
    if previous is not None:
        verify_bundle(previous,context)
        if canonical_json(previous)!=canonical_json(value):
            raise ValueError('invalid admission transition; assessments are immutable')
    return decision
