"""Single-use development resume transaction v1; immutable original evidence."""
from pathlib import Path
import tempfile
import time

from campaign_contract import fields, digest
from campaign_journal import (binding, bounded_inventory, inspect_recovery, read_journal)
from campaign_ownership import directory_lock, owner, OWNER
from campaign_pilot import (pilot_context, read_json, put, stage_inputs, contained,
                            run_pilot, regular_bytes, MAX_ARTIFACT)
from workloads import canonical_json, sha256

SUFFIX = '.resume-v1'


def transaction_path(original):
    original = Path(original).absolute()
    return original.with_name(original.name + SUFFIX)


def preflight(original):
    context = pilot_context(original)
    plan, manifest, execution, selected, hardware = context
    ownership = read_json(original/OWNER)
    fields(ownership, 'schema schema_version protocol input_root output_directory device inode', 'pilot ownership')
    if canonical_json(ownership) != canonical_json(owner(ownership['input_root'], original)):
        raise ValueError('unsupported execution ownership protocol')
    report = inspect_recovery(original)
    if report['uncommitted_files']:
        raise ValueError('unpublished original journal bytes require manual review')
    if any(t['classification'] not in ('verified-complete', 'pending') for t in report['trials']):
        raise ValueError('failed, interrupted or unresolved original trial; no retry supported')
    pending = [t['trial_id'] for t in report['trials'] if t['classification']=='pending']
    reused = [t['trial_id'] for t in report['trials'] if t['classification']=='verified-complete']
    if not pending:
        raise ValueError('no never-launched pending trial to resume')
    expected = binding(original, context)
    _, _, _, count = read_journal(original, expected)
    head = read_json(original/'recovery-journal'/f'{count-1:08d}.json')['entry_id']
    return context, ownership, expected, head, reused, pending


def header(original):
    context, ownership, bound, head, reused, pending = preflight(original)
    value = dict(schema='dynagraph-pilot-resume', schema_version=1, attempt_sequence=1,
                 original=str(original), original_execution_id=bound['pilot_execution_id'],
                 original_chain_head=head, plan_sha256=bound['plan_sha256'],
                 manifest_sha256=bound['manifest_sha256'], selected_trials=bound['selected_trials'],
                 limits=bound['limits'], authorization=dict(execute_development=True, authorize_resume=True),
                 budget_policy='fresh-attempt-including-preflight-v1', development_only=True,
                 measurement_eligible=False, ownership=ownership, reused=reused, pending=pending,
                 original_inventory=bounded_inventory(original),
                 original_sidecar=(sha256(regular_bytes(original/'sha256.json',MAX_ARTIFACT))
                                   if (original/'sha256.json').exists() else None))
    value['attempt_id'] = sha256(canonical_json(value))
    return value, context


def event(sequence, previous, kind, payload):
    value = dict(schema='dynagraph-pilot-resume-event', schema_version=1,
                 sequence=sequence, previous=previous, kind=kind, payload=payload)
    value['entry_id'] = sha256(canonical_json(value))
    return value


def resume_pilot(original, *, execute=False, authorize=False):
    if execute is not True or authorize is not True:
        raise ValueError('both --execute-development and --authorize-resume are required')
    original = Path(original).absolute()
    begin = time.monotonic()
    with directory_lock(original):
        value, context = header(original)
        plan, manifest, execution, selected, hardware = context
        limits = value['limits']
        deadline = begin + limits['wall_seconds']
        root = Path(value['ownership']['input_root'])
        # Validate every original input before the first child, using the same
        # bounded identity/oracle subset checks as ordinary execution.
        with tempfile.TemporaryDirectory(prefix='dynagraph-resume-preflight-') as temporary:
            for trial in selected:
                if trial['trial_id'] in value['pending']:
                    target = Path(temporary)/trial['trial_id']; target.mkdir()
                    workload = next(w for w in plan['workloads'] if w['id']==trial['workload_id'])
                    stage_inputs(root, target, workload, contained(root,plan['build']['executable']),
                                 plan['build']['executable_sha256'])
        attempt = transaction_path(original)
        attempt.mkdir(exist_ok=False)  # Permanent, single-use reservation, even if publication fails.
        with directory_lock(attempt):
            first = event(0, None, 'authorized', value)
            put(attempt, '00000000.json', first)
            # Parent directory fsync is required for durable attempt reservation.
            import os
            fd = os.open(attempt.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try: os.fsync(fd)
            finally: os.close(fd)
            run_pilot(plan, manifest, root, attempt/'pilot', value['pending'], execute=True,
                      max_trials=limits['max_trials'], wall_seconds=limits['wall_seconds'],
                      timeout=limits['timeout_seconds'], output_limit=limits['stream_bytes'],
                      _deadline=deadline, _runtime_origin=dict(kind='resume', attempt_id=value['attempt_id']))
            child = inspect_recovery(attempt/'pilot')
            payload = dict(attempt_id=value['attempt_id'],
                           pilot_inventory=bounded_inventory(attempt/'pilot'),
                           outcome=child)
            put(attempt, '00000001.json', event(1, first['entry_id'], 'finished', payload))
    return inspect_resume(attempt)


def inspect_resume(attempt):
    """Read only: reverify original and fresh v2 evidence; never execute code."""
    attempt = Path(attempt).absolute()
    # This shallow tree contains only two events and one ordinary pilot subtree.
    # Validate type/depth/count of the whole tree before parsing or walking it.
    bounded_inventory(attempt)
    allowed = {'00000000.json','00000001.json','pilot'}
    if any(p.name not in allowed and not p.name.startswith('.pending-') for p in attempt.iterdir()):
        raise ValueError('unexpected resume artifact')
    first = read_json(attempt/'00000000.json')
    if regular_bytes(attempt/'00000000.json',MAX_ARTIFACT)!=canonical_json(first):
        raise ValueError('noncanonical resume event')
    fields(first, 'schema schema_version sequence previous kind payload entry_id', 'resume event')
    if canonical_json(first) != canonical_json(event(0,None,'authorized',first['payload'])):
        raise ValueError('invalid resume header event')
    value = first['payload']
    digest(value['attempt_id'])
    original = Path(value['original'])
    if transaction_path(original) != attempt:
        raise ValueError('resume directory identity mismatch; relocation unsupported')
    expected, context = header(original)
    if canonical_json(value) != canonical_json(expected):
        raise ValueError('resume binding or original evidence mismatch')
    child = None
    if (attempt/'pilot').exists():
        # A crash before complete context publication has no reusable outcome.
        required = ['plan.json','trial-manifest.json','execution-manifest.json','hardware.json',
                    'admission.json','recovery-journal/00000000.json',OWNER]
        for name in required:
            if (attempt/'pilot'/name).exists():
                read_json(attempt/'pilot'/name)  # malformed partial context rejects
        if all((attempt/'pilot'/name).exists() for name in required):
            child = inspect_recovery(attempt/'pilot')
            p,m,e,s,h = pilot_context(attempt/'pilot')
            if (attempt/'pilot/runtime-contract.json').exists():
                contract = read_json(attempt/'pilot/runtime-contract.json')
                if contract.get('origin') != dict(kind='resume', attempt_id=value['attempt_id']):
                    raise ValueError('resumed runtime origin mismatch')
            if (canonical_json(p)!=canonical_json(context[0]) or canonical_json(m)!=canonical_json(context[1]) or
                    e['limits']!=value['limits'] or [t['trial_id'] for t in s]!=value['pending'] or
                    canonical_json(read_json(attempt/'pilot'/OWNER))!=canonical_json(owner(value['ownership']['input_root'],attempt/'pilot'))):
                raise ValueError('resumed execution parameter mismatch')
    terminal = attempt/'00000001.json'
    finished = terminal.exists()
    if finished:
        last = read_json(terminal)
        if regular_bytes(terminal,MAX_ARTIFACT)!=canonical_json(last):
            raise ValueError('noncanonical resume terminal')
        payload = dict(attempt_id=value['attempt_id'], pilot_inventory=bounded_inventory(attempt/'pilot'), outcome=child)
        if child is None or child['status']!='settled' or canonical_json(last)!=canonical_json(event(1,first['entry_id'],'finished',payload)):
            raise ValueError('invalid resume terminal or evidence')
    if any(p.name.startswith('.pending-') for p in attempt.iterdir()):
        finished = False
    rows = [dict(trial_id=t, disposition='reused', classification='verified-complete', origin='original') for t in value['reused']]
    rows += [dict(trial_id=t, disposition='new', classification=(next(r['classification'] for r in child['trials'] if r['trial_id']==t) if child else 'indeterminate'), origin='resume') for t in value['pending']]
    return dict(schema='dynagraph-pilot-resume-inspection',schema_version=1,
                attempt_id=value['attempt_id'], attempt_directory=str(attempt),
                status='settled' if finished else 'incomplete',
                execution_status=('complete' if finished and all(r['classification']=='verified-complete' for r in rows) else 'incomplete' if not finished else 'failed'),
                trials=rows, read_only=True, measurement_eligible=False,
                repeated_resume='unsupported; existing reservation permanently blocks another attempt')
