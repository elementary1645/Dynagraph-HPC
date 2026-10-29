"""Explicitly SYNTHETIC archive fixtures; never validation or performance evidence."""
import copy
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch
import xml.etree.ElementTree as ET

from archive_contract import BASE_STAGES, CLI_CONTROLS, MODES, PIPELINE_STAGES
from archive_transport import file_inventory, sha
from check_execution import validate_report
from check_registration import expected_names
from command_receipts import controlled_environment
from snapshot import inventory, inventory_hash
from test_smoke import DIAGNOSTICS

ROOT = Path(__file__).resolve().parents[2]


def write(root, name, value):
    path = root/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value)+'\n')


def hashes(root, recursive=False):
    values = file_inventory(root)
    values.pop('evidence-sha256.json', None)
    write(root, 'evidence-sha256.json', {n:d['sha256'] for n,d in values.items() if recursive or '/' not in n})


def policy(root):
    _, value = controlled_environment(root)
    write(root, 'environment-policy.json', value)


def receipts(root, names, content, configure=None, negative=False):
    rows = []
    for index, name in enumerate(names):
        path = root/(name+'.log')
        data = content.get(name, b'SYNTHETIC TEST FIXTURE\n')
        path.write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode()+b'\n')
        rows.append(dict(name=name, command=configure if name=='configure' else ['synthetic-fixture', name],
                         cwd=configure[2] if name=='configure' else 'SYNTHETIC', environment={}, start_unix=2*index+1, end_unix=2*index+2,
                         wall_seconds=1, classification='exited', exit_code=2 if negative else 0,
                         error=None, log=path.name, log_sha256=sha(path)))
    write(root, 'commands.json', rows)


def fixture(base, release=False):
    source, evidence = base/'source', base/'evidence'
    source.mkdir(); evidence.mkdir()
    (source/'run ü.sh').write_text('#!/bin/sh\n# SYNTHETIC ONLY\nexit 0\n')
    (source/'run ü.sh').chmod(0o755)
    (source/'benchmarks').mkdir()
    (source/'benchmarks/requirements-analysis.txt').write_text('synthetic-fixture==1.0\n')
    entries = inventory(source, ['run ü.sh', 'benchmarks/requirements-analysis.txt'])
    identity = dict(git_revision='a'*40, dirty=True, git_status=' M fixture',
                    inventory=entries, inventory_sha256=inventory_hash(entries))
    write(evidence,'source-identity.json',identity)
    policy(evidence)
    mode='release' if release else 'debug'
    write(evidence,'result.json',dict(status='complete',source_unchanged=True,mode=mode,passed=31,smoke=release))
    names = expected_names()
    registration=dict(kind='ctestInfo',version=dict(major=1,minor=0),tests=[dict(name=n,properties=[]) for n in names])
    report=ET.Element('testsuite',name='SYNTHETIC',tests='31',failures='0',disabled='0',skipped='0',time='1',timestamp='fixture')
    for name in names:
        case=ET.SubElement(report,'testcase',name=name,status='run',time='0')
        ET.SubElement(case,'system-out')
    ET.ElementTree(report).write(evidence/'execution.xml',encoding='utf-8')
    write(evidence,'acceptance.json',validate_report(evidence/'execution.xml',0,names))
    files=b''.join(n.encode()+b'\0' for n in entries)
    env=dict(python='3.14 SYNTHETIC',renderer='Agg: initialized and rendered',dependencies={'synthetic-fixture':'1.0'})
    content={'revision':b'a'*40+b'\n','status':b' M fixture','source-files':files,'source-files-final':files,
             'registration':registration,'environment':env}
    flags=['cmake','-S',str(source),'-B',str(base/'build'),'-G','Unix Makefiles',
           '-DCMAKE_CXX_COMPILER=g++','-DCMAKE_BUILD_TYPE='+('Release' if release else 'Debug'),
           '-DBUILD_TESTING=ON','-DDYNAGRAPH_WARNINGS_AS_ERRORS=ON','-DDYNAGRAPH_FULL_VALIDATION=ON',
           '-DDYNAGRAPH_ANALYSIS_PYTHON='+str(Path(sys.executable).absolute())]
    stages=list(BASE_STAGES)+(['pipeline','pipeline-negative'] if release else [])+['source-files-final']
    receipts(evidence,stages,content,flags)
    if release:
        pipeline(evidence,identity,content)
    hashes(evidence)
    return source,evidence


def pipeline(evidence,identity,content):
    # Reuse existing complete synthetic worker/replay fixtures with the actual tiny chain recipe.
    sys.path.insert(0,str(ROOT/'tests'))
    sys.path.insert(0,str(ROOT/'benchmarks/python'))
    import analysis_test_support as support
    from experiment_records import validate_dataset
    p=evidence/'pipeline';p.mkdir();policy(p)
    spec=json.loads((ROOT/'benchmarks/configs/chain-v1.json').read_bytes())
    for index,mode in enumerate(MODES):
        with patch.object(support,'specification',lambda:copy.deepcopy(spec)):
            support.fixture(p/mode,mode=mode,run_id=str(index+1))
        (p/mode/'runner').chmod(0o755)
        assert validate_dataset(p/mode/'records.jsonl')['trials']=='16'
        first=json.loads((p/mode/'records.jsonl').read_bytes().splitlines()[0])
        write(p,mode+'.json',first['configuration'])
    shutil.copytree(p/'full-trace/workload',p/'bundle')
    write(p,'source-identity.json',identity)
    write(p,'analysis-plan.json',{'synthetic':True})
    manifest=json.loads((p/'bundle/manifest.json').read_bytes())
    executable=sha(p/'full-trace/runner')
    write(p,'pipeline-result.json',dict(status='complete',source_unchanged=True,timing_modes=list(MODES),trials_per_mode=16,
          figures=14,evidence_class='valid_harness_only',producer_authentication=False,workload=manifest['counts'],
          executable_sha256=executable,dataset_sha256={m:sha(p/m/'records.jsonl') for m in MODES},
          workload_sha256={n:sha(p/'bundle'/n) for n in ('manifest.json','graph.txt','trace.txt')}))
    logs=dict(content,**{'verify-workload':dict(status='verified',counts=manifest['counts'])})
    for mode in MODES: logs[mode+'-validate']=dict(schema_version=1,status='complete',trials='16')
    receipts(p,PIPELINE_STAGES,logs)
    a=p/'analysis';a.mkdir()
    acceptance=[dict(input_id=m,accepted=True,structurally_valid=True,classification='valid_harness_only',path=m,
                     inventory={n:d['sha256'] for n,d in file_inventory(p/m).items()}) for m in MODES]
    (a/'acceptance.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in acceptance))
    write(a,'summaries.json',dict(status='complete',accepted_input_count='2'))
    for name in ('trials.csv','paired-ratios.csv','report.md'): (a/name).write_text('SYNTHETIC ONLY\n')
    products=[]
    for kind in ('paired-ratios','policy-runtimes','latency-ecdf','update-profile','family-ratios','adaptive-comparisons','block-order'):
        for extension in ('svg','pdf'):
            path=a/(kind+'.'+extension)
            if extension=='svg': raw=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><path d="M0 0 L1 1"/></svg>'
            else:
                raw=b'%PDF-1.4\n/Type /Catalog /Type /Pages /Type /Page \n'
                raw+=b'xref\nstartxref\n'+str(len(raw)).encode()+b'\n%%EOF\n'
            path.write_bytes(raw)
            products.append(dict(path=path.name,figure_type=kind,sha256=sha(path)))
    write(a,'analysis-manifest.json',dict(status='complete',analysis_plan_sha256=sha(p/'analysis-plan.json'),output_sha256={n:d['sha256'] for n,d in file_inventory(a).items()},
                                        figure_generation=dict(products=products)))
    (p/'mpl-cache').mkdir();(p/'mpl-cache/fontlist.json').write_text('{}')
    hashes(p,recursive=True)
    n=evidence/'pipeline-negative';n.mkdir();policy(n)
    receipts(n,CLI_CONTROLS,{k:DIAGNOSTICS[k].encode() for k in CLI_CONTROLS},negative=True)
    for label in set(DIAGNOSTICS)-set(CLI_CONTROLS): (n/(label+'.log')).write_text(DIAGNOSTICS[label])
    write(n,'negative-results.json',[dict(case=k,rejected=True,diagnostic=v) for k,v in DIAGNOSTICS.items()])
