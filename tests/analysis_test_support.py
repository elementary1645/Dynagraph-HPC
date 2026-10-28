"""SYNTHETIC timing evidence for contract tests, never measured performance."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'benchmarks/python'))
from artifacts import write_bundle
from experiment_records import POLICIES,IDENTITIES,record,schedule
from workloads import canonical_json,sha256,parse_graph,parse_trace,replay
from test_workloads import specification
from test_workload_loader import bellman_ford
from analysis_import import COMPARISONS,FIGURES


def fixture(directory,mode='full-trace',run_id='1',seed='1',ticks=None,period=(1,1000000000),instrumentation=False):
    directory=Path(directory);directory.mkdir()
    spec=specification();spec['seeds']['weight']=seed
    write_bundle(spec,directory/'workload')
    import json
    manifest=json.loads((directory/'workload/manifest.json').read_bytes())
    graph=parse_graph((directory/'workload/graph.txt').read_bytes());trace=parse_trace((directory/'workload/trace.txt').read_bytes())
    final=replay(graph,trace)
    (directory/'runner').write_bytes(b'SYNTHETIC FIXTURE ONLY: NOT A BENCHMARK EXECUTABLE\n')
    (directory/'artifact-verification.json').write_bytes(canonical_json(dict(schema_version=1,status='verified',workload_id=manifest['workload_id'],
          source=manifest['source'],counts=manifest['counts'],final_graph_sha256=manifest['final_graph_sha256'])))
    config=dict(schema_version=1,manifest='workload/manifest.json',timing_mode=mode,blocks='4',order_seed='0',delta='16',threads='2',
                no_effect='shared_fast_path',timeout_seconds='20',warmups='1')
    ids=dict(graph_sha256=manifest['artifacts']['graph']['sha256'],trace_sha256=manifest['artifacts']['trace']['sha256'],
             executable_sha256=sha256((directory/'runner').read_bytes()),configuration_sha256=sha256(canonical_json(config)))
    def observation(value): return dict(value=value,origin='observed',source='SYNTHETIC TEST FIXTURE')
    metadata={k:observation('fixture') for k in ('compiler','compiler_path','cmake_version','build_type','flags','sanitizers','git_revision','git_dirty',
         'openmp_spec','openmp_max_threads','openmp_dynamic','openmp_thread_limit','openmp_runtime_version','actual_workers')}
    metadata['build_type']=dict(value='Release',origin='build_recorded',source='SYNTHETIC TEST FIXTURE')
    metadata['flags']=dict(value='-O3 -fsanitize=address' if instrumentation else '-O3',origin='build_recorded',source='SYNTHETIC TEST FIXTURE')
    metadata['sanitizers']=dict(value='declared_in_flags' if instrumentation else 'none_declared',origin='build_recorded',source='SYNTHETIC TEST FIXTURE')
    metadata['actual_workers']=dict(value=None,origin='unavailable',source='metrics disabled')
    order=schedule(4,0);records=[]
    def append(kind,block=None,trial=None,policy=None,**payload):
        records.append(record(kind,run_id,ids,len(records),block,trial,policy,**payload))
    env=dict(source=str(manifest['source']),delta='16',requested_workers='2',no_effect='shared_fast_path',
             heuristic={'small_graph_edges':'4096','repair_max_degree':'32','parallel_min_edges':'65536'},timing_mode=mode,
             vertices=str(graph.vertices),edges=str(len(graph.edges)),updates=str(len(trace.updates)))
    append('run_config',configuration=config,schedule=order,manifest_sha256=sha256((directory/'workload/manifest.json').read_bytes()),
           isolation='fresh-process-per-trial-v1',schedule_version='balanced-four-splitmix64-fisher-yates-v1')
    append('environment',**env,metadata={'cpu_model':observation('SYNTHETIC')},external_integrity='python_verified',external_preflight='pending',identity_origin='python_sha256')
    def evidence(stem,raw):
        (directory/(stem+'.stdout')).write_bytes(raw);(directory/(stem+'.stderr')).write_bytes(b'')
        (directory/(stem+'.exit.json')).write_bytes(canonical_json(dict(returncode=0,stdout_sha256=sha256(raw),stderr_sha256=sha256(b''))))
    for policy in POLICIES:
        report=dict(schema_version=1,success=True,failure_category='none',message='',failing_update_index=None,
                    graph_path='SYNTHETIC/graph.txt',trace_path='SYNTHETIC/trace.txt',declared_graph_sha256=ids['graph_sha256'],
                    identity_origin='unverified_artifact_metadata',integrity='external_python_verifier_required',policy=policy,source=manifest['source'],delta=16,
                    requested_workers=2,no_effect='shared_fast_path',verification_level='full',trace_entries=len(trace.updates),updates_executed=len(trace.updates),
                    updates_verified=len(trace.updates),reference_recomputations=len(trace.updates)+1,bellman_ford_checks=len(trace.updates)+1,
                    final_graph_verified=True,final_distances_verified=True,final_weights=[w for _,_,w in final.edges],final_distances=bellman_ford(final,manifest['source']))
        evidence('preflight-'+policy,canonical_json(report))
        append('verification',policy=policy,scope='external_full_preflight',success=True,per_update_oracles=True,
               reference_recomputations=str(len(trace.updates)+1),bellman_ford_checks=str(len(trace.updates)+1))
    for block,policies in enumerate(order):
        append('block_start',str(block),order=policies)
        for position,policy in enumerate(policies):
            trial=str(4*block+position);worker=[]
            append('trial_start',str(block),trial,policy,repetition_id=str(block),policy_position=str(position),phase='measurement')
            def emit(kind,**payload): worker.append(record(kind,run_id,ids,len(worker),str(block),trial,policy,**payload))
            emit('environment',**env,metadata=metadata,external_integrity='unconfirmed',external_preflight='unconfirmed',identity_origin='user_supplied')
            emit('clock_probe',clock='std::chrono::steady_clock',is_steady=True,period_num=str(period[0]),period_den=str(period[1]),method='back-to-back-v1',ticks=['0']*1024)
            emit('warmup_end',phase='warmup',warmup_index='0',success=True)
            emit('verification',scope='timed_final_state',success=True,per_update_oracles=False,reference_recomputations='1',bellman_ford_checks='1')
            count=1 if mode=='full-trace' else len(trace.updates)
            for index in range(count):
                value=ticks(policy,block,index) if ticks else {'dijkstra':10,'delta-stepping':8,'incremental':5,'heuristic':7}[policy]*(block+1)*(index+1)
                emit('trial_measurement' if mode=='full-trace' else 'update_latency',phase='measurement',update_index=None if mode=='full-trace' else str(index),
                     elapsed_ticks=str(value),elapsed_ns=str(value*period[0]*1000000000//period[1]))
            emit('trial_end',success=True,updates_executed=str(len(trace.updates)),sample_count=str(count))
            evidence('trial-'+trial,b''.join(canonical_json(r) for r in worker))
            for value in worker:
                copy=dict(value,sequence=str(len(records)));records.append(copy)
        append('block_end',str(block),success=True)
    append('run_end',success=True,blocks_completed='4')
    (directory/'records.jsonl').write_bytes(b''.join(canonical_json(r) for r in records))
    return directory


def plan_for(paths,modes=None):
    import json
    paths=list(map(Path,paths));inputs=[];configs=[];workloads=[]
    for index,path in enumerate(paths):
        first=json.loads((path/'records.jsonl').read_bytes().splitlines()[0]);manifest=json.loads((path/'workload/manifest.json').read_bytes())
        workload='workload-'+first['graph_sha256'][:12]
        if workload not in [w['id'] for w in workloads]:
            workloads.append(dict(id=workload,graph_sha256=first['graph_sha256'],trace_sha256=first['trace_sha256'],source=str(manifest['source']),dependence_group='graph-group'))
        group='configuration-'+str(index)
        configs.append(dict(id=group,**{k:first['configuration'][k] for k in ('timing_mode','delta','threads','no_effect','warmups')},
                            executable_sha256=first['executable_sha256'],build_type='Release'))
        inputs.append(dict(id='input-'+str(index),path=str(path),workload_id=workload,configuration_group=group,hardware_id='fixture-hardware',session_id='session-1',
                           session_independence_declared=False,synthetic=True,evidence_intent='harness',
                           expected_identities={k:first[k] for k in (*IDENTITIES,'manifest_sha256')},controlled_hardware_evidence=None,instrumentation_evidence=None))
    return dict(schema_version=1,inputs=inputs,workloads=workloads,compatible_configurations=configs,
                comparisons=[dict(numerator=a,baseline=b,family=f) for a,b,f in COMPARISONS],allowed_evidence_classes=['valid_harness_only'],
                figures=list(FIGURES),exclusions=[])
