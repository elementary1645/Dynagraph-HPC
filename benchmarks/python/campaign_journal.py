"""Immutable recovery journal v1; inspection never launches, repairs or resumes."""
import os
from pathlib import Path
import re
import stat

from campaign_contract import digest, fields, integer, load_bytes
from workloads import canonical_json, sha256

DIRECTORY = 'recovery-journal'
MAX_ENTRY = 65536
MAX_ENTRIES = 17  # One header, at most launch + terminal for each of eight trials.
SCHEMA = 'dynagraph-pilot-recovery-journal'


def binding(directory, context):
    """Bind observed context and effective OpenMP requests, not host attestation."""
    from campaign_pilot import environment, read_json
    plan, manifest, execution, selected, hardware = context
    controls = {t['trial_id']: {k:v for k,v in environment(t['workers']).items() if k.startswith('OMP_')}
                for t in selected}
    value = dict(campaign_id=plan['campaign_id'], plan_sha256=execution['plan_sha256'],
                 manifest_sha256=sha256(canonical_json(manifest)),
                 execution_manifest_sha256=sha256(canonical_json(execution)),
                 hardware_sha256=sha256(canonical_json(hardware)),
                 admission_sha256=sha256(canonical_json(read_json(directory/'admission.json'))),
                 environment=controls, environment_sha256=sha256(canonical_json(controls)),
                 evidence_schema_version=2, selected_trials=[dict(trial_id=t['trial_id'],sequence=t['sequence'],state='pending') for t in selected],
                 limits=execution['limits'], admission='development-only', measurement_eligible=False)
    value['pilot_execution_id'] = sha256(canonical_json(value))
    return value


def entry(sequence, previous, kind, payload):
    value = dict(schema=SCHEMA, schema_version=1, sequence=sequence,
                 previous_entry_id=previous, kind=kind, payload=payload)
    value['entry_id'] = sha256(canonical_json(value))
    return value


def apply(states, order, payload):
    """Validate the serial lifecycle, including permanent halt after failure."""
    fields(payload, 'trial_id from_state to_state evidence reason', 'journal transition')
    tid = payload['trial_id'];digest(tid)
    if tid not in states or payload['from_state']!=states[tid]:
        raise ValueError('journal unknown trial or invalid source state')
    # Completed trials form a prefix; only the next trial can change state.
    current = next((t for t in order if states[t]!='completed'),None)
    if tid!=current or any(v in ('failed','interrupted') for v in states.values()):
        raise ValueError('journal transition violates deterministic execution order')
    old,new = states[tid],payload['to_state']
    if (old,new) not in (('pending','launched'),('pending','failed'),('pending','interrupted'),
                          ('launched','completed'),('launched','failed'),('launched','interrupted')):
        raise ValueError('invalid journal lifecycle transition')
    if new=='launched':
        if payload['evidence'] is not None or payload['reason'] is not None:
            raise ValueError('launch intent must not claim completed evidence')
    else:
        evidence = payload['evidence']
        fields(evidence, 'path sha256', 'journal evidence reference')
        if evidence['path']!=tid+'/record.json':
            raise ValueError('unexpected journal evidence reference')
        digest(evidence['sha256'])
        if type(payload['reason']) is not str:
            raise ValueError('journal terminal reason required')
    states[tid] = new


class Journal:
    """One new-output writer; cannot reopen an existing journal or resume."""
    class Error(OSError):
        pass

    @classmethod
    def create(cls, directory):
        from campaign_pilot import pilot_context
        self = cls()
        self.root = Path(directory)
        self.path = self.root/DIRECTORY
        self.path.mkdir(exist_ok=False)  # Also excludes concurrent creators.
        for parent in (self.root.parent,self.root):
            fd = os.open(parent,os.O_RDONLY | os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
        context = pilot_context(self.root)
        self.bound = binding(self.root,context)
        self.order = [t['trial_id'] for t in context[3]]
        self.states = {tid:'pending' for tid in self.order}
        self.sequence = 0
        self.previous = None
        self._publish('created',self.bound)
        return self

    def _publish(self, kind, payload):
        from campaign_pilot import atomic_bytes
        if self.sequence>=MAX_ENTRIES:
            raise self.Error('journal entry count limit')
        value = entry(self.sequence,self.previous,kind,payload)
        try:
            atomic_bytes(self.path/f'{self.sequence:08d}.json',canonical_json(value))
        except (OSError,ValueError) as error:
            raise self.Error('journal publication failed: '+str(error)) from error
        self.previous = value['entry_id']
        self.sequence += 1

    def transition(self, tid, state, evidence=None, reason=None):
        payload = dict(trial_id=tid,from_state=self.states.get(tid),to_state=state,
                       evidence=evidence,reason=reason)
        states = dict(self.states)
        apply(states,self.order,payload)
        self._publish('transition',payload)
        self.states = states  # Advance only after complete atomic publication.

    def finish(self, record):
        from campaign_pilot import regular_bytes, MAX_ARTIFACT
        if record['reason']=='not-run':
            return
        tid = record['trial']['trial_id']
        state = ('completed' if record['status']=='success' else
                 'interrupted' if record['reason']=='interrupted' else 'failed')
        reference = tid+'/record.json'
        identity = sha256(regular_bytes(self.root/reference,MAX_ARTIFACT))
        self.transition(tid,state,dict(path=reference,sha256=identity),record['reason'])


def read_journal(directory, expected):
    from campaign_pilot import regular_bytes
    path = directory/DIRECTORY
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise ValueError('journal must be a real directory')
    committed = [];pending = []
    with os.scandir(path) as entries:
        for item in entries:
            if len(committed)+len(pending)>=MAX_ENTRIES+1:
                raise ValueError('journal file count limit')
            mode = item.stat(follow_symlinks=False).st_mode
            if not stat.S_ISREG(mode):
                raise ValueError('nonregular journal entry')
            if re.fullmatch(r'[0-9]{8}\.json',item.name):
                committed.append(item.name)
            elif item.name.startswith('.pending-'):
                # Unpublished temporary bytes are not parsed as a transition.
                regular_bytes(path/item.name,MAX_ENTRY)
                pending.append(item.name)
            else:
                raise ValueError('unexpected journal filename')
    if not committed:
        raise ValueError('journal header absent; no committed recovery identity')
    states = {t['trial_id']:'pending' for t in expected['selected_trials']}
    order = list(states);previous = None;seen = set();terminal = {}
    for sequence,name in enumerate(sorted(committed)):
        if sequence>=MAX_ENTRIES or name!=f'{sequence:08d}.json':
            raise ValueError('missing or out-of-order journal sequence')
        raw = regular_bytes(path/name,MAX_ENTRY);value = load_bytes(raw)
        fields(value,'schema schema_version sequence previous_entry_id kind payload entry_id','journal entry')
        integer(value['schema_version'],1,1,'journal schema version')
        integer(value['sequence'],sequence,sequence,'journal sequence')
        if value['schema']!=SCHEMA or raw!=canonical_json(value):
            raise ValueError('invalid or torn journal entry')
        digest(value['entry_id'])
        if value['previous_entry_id']!=previous or value['entry_id'] in seen:
            raise ValueError('journal hash chain or duplicate entry identity')
        calculated = entry(sequence,previous,value['kind'],value['payload'])
        if value['entry_id']!=calculated['entry_id']:
            raise ValueError('journal transition identity mismatch')
        if sequence==0:
            if value['kind']!='created' or canonical_json(value['payload'])!=canonical_json(expected):
                raise ValueError('journal execution/provenance binding mismatch')
        else:
            if value['kind']!='transition':
                raise ValueError('unexpected journal entry kind')
            apply(states,order,value['payload'])
            if value['payload']['to_state']!='launched':
                terminal[value['payload']['trial_id']] = value['payload']
        seen.add(value['entry_id']);previous = value['entry_id']
    return states,terminal,pending,len(committed)


def bounded_inventory(directory):
    """Hash only bounded regular evidence; never traverse a link or special file."""
    from campaign_pilot import regular_bytes, MAX_EXECUTABLE
    inventory = {};count = 0
    def walk(path,depth):
        nonlocal count
        if depth>4:
            raise ValueError('recovery evidence depth limit')
        with os.scandir(path) as entries:
            for item in entries:
                count += 1
                if count>512:
                    raise ValueError('recovery evidence entry limit')
                mode = item.stat(follow_symlinks=False).st_mode
                p = Path(item.path)
                if stat.S_ISDIR(mode):walk(p,depth+1)
                elif stat.S_ISREG(mode):
                    if p!=directory/'sha256.json':
                        inventory[p.relative_to(directory).as_posix()] = sha256(regular_bytes(p,MAX_EXECUTABLE))
                else:raise ValueError('nonregular recovery evidence')
    walk(directory,0)
    return inventory


def inspect_recovery(directory):
    """Conservative classification; immutable journal facts cannot replace gates."""
    from campaign_pilot import pilot_context, verify_trial_evidence, verify_pilot
    directory = Path(directory).resolve(strict=True)
    context = pilot_context(directory)
    plan,manifest,execution,selected,hardware = context
    expected = binding(directory,context)
    states,terminal,pending,entries = read_journal(directory,expected)
    inventory = bounded_inventory(directory)
    full = False
    if (directory/'sha256.json').exists():
        # Existing full v2 verification remains authoritative when published.
        verify_pilot(directory)
        full = True
    rows = [];unsettled = bool(pending);halted = False
    for trial in selected:
        tid = trial['trial_id'];state = states[tid];reference = tid+'/record.json'
        exists = reference in inventory
        payload = terminal.get(tid)
        if payload:
            if not exists or inventory[reference]!=payload['evidence']['sha256']:
                raise ValueError('journal terminal record absent or modified')
        record = None
        if exists:
            record = verify_trial_evidence(directory,trial,plan,execution,hardware,inventory)
            if halted and record['reason']!='not-run':
                raise ValueError('recovery evidence executed after failure')
            halted = halted or record['reason']!='success'
        classification = 'pending';evidence_status = 'absent'
        if record:
            evidence_status = ('verified-complete' if record['status']=='success' else record['reason'])
        if payload:
            actual = ('completed' if record['status']=='success' else
                      'interrupted' if record['reason']=='interrupted' else 'failed')
            if (actual!=state or payload['reason']!=record['reason'] or record['reason']=='not-run' or
                    (payload['from_state']=='pending' and record['processes'])):
                raise ValueError('journal terminal/evidence contradiction')
            classification = 'verified-complete' if state=='completed' else state
        elif state=='launched':
            classification = 'indeterminate';unsettled = True
        elif record and record['reason']!='not-run':
            # Evidence alone does not repair the missing terminal transition.
            classification = 'indeterminate';unsettled = True
        if state=='pending' and record and record['processes']:
            raise ValueError('process evidence without committed launch intent')
        if state=='pending' and not record and (directory/tid).exists():
            # May be interrupted preparation before launch, never completion.
            classification = 'indeterminate';unsettled = True
        rows.append(dict(trial_id=tid,sequence=trial['sequence'],journal_state=state,
                         classification=classification,evidence_status=evidence_status,
                         measurement_eligible=False))
    if not full:unsettled = True
    return dict(schema='dynagraph-pilot-recovery-inspection',schema_version=1,
                pilot_execution_id=expected['pilot_execution_id'],
                status='incomplete' if unsettled else 'settled',
                final_evidence_verified=full,committed_entries=entries,
                uncommitted_files=pending,trials=rows,development_only=True,
                measurement_eligible=False,read_only=True,
                limitations=['No process liveness inferred; abrupt parent death may leave children running',
                             'Internal consistency is not producer authentication; no automatic resume'])
