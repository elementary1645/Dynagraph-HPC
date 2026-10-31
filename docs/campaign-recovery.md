# Phase 6B-2B-1 recovery journal

New development pilots automatically create a separate recovery journal alongside
unchanged pilot schema v2 evidence. Phase 6B-2B-2 adds the explicit conservative resume subset below. No automatic
retry, repair, scientific execution or resource-isolation command is provided. All classifications remain measurement-ineligible.

## Read-only inspection

```sh
python3 -B benchmarks/python/campaign.py inspect-recovery --output /tmp/dynagraph-pilot-output
```

The command never starts a subprocess, signals a process, modifies files or
advances the journal. Canonical JSON on stdout has
`schema=dynagraph-pilot-recovery-inspection`, `schema_version=1`, content-derived
`pilot_execution_id`, `status`, `final_evidence_verified`, committed entry count,
uncommitted filenames, and ordered trial rows. Each row includes the original
trial ID/sequence, journal state, classification, evidence status, and
`measurement_eligible=false`. Rejected inspections produce JSON with
`status=rejected`, a bounded error string, and exit 2; a human diagnostic is also
written to stderr. No subprocess code from retained evidence is executed.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Settled, consistent journal and final v2 evidence; inspect each trial classification for failures/interruption/pending |
| 1 | Consistent but incomplete publication; no automatic action is taken |
| 2 | Corrupt, contradictory, unsupported or unavailable journal/context/evidence |

`verify-pilot` remains the v2 evidence gate; `inspect-recovery` is the additional
journal lifecycle gate. A v2 verification success alone does not certify journal
semantics. The existing `verify-pilot` command still accepts unchanged historical v2 evidence
without a journal. `inspect-recovery` requires journal v1 and does not manufacture
or migrate one for older runs. Pilot v1 evidence remains unsupported by the v2
verifier. Campaign plan/trial-manifest v1, hardware/admission v2, runtime
provenance v3 and all Phase 5C archive contracts remain unchanged.

## Journal v1 binding and identities

`recovery-journal/00000000.json` is an immutable creation entry. Subsequent
`00000001.json` through at most `00000016.json` are immutable transitions. Eight
selected trials permit at most two transitions each. Files are canonical JSON
with LF termination, each capped at 64 KiB. At most 17 committed entries and one
unpublished temporary file are supported. Recovery evidence traversal is bounded
to 512 directory entries and depth four; existing pilot file-size limits apply.

Every entry requires exactly:

- `schema=dynagraph-pilot-recovery-journal`, `schema_version=1`;
- integer `sequence`, `previous_entry_id` (null only for creation);
- `kind` (`created` or `transition`), `payload`, and `entry_id`.

`entry_id` is SHA-256 of canonical entry bytes excluding that field. Sequence,
previous identity, kind and payload therefore determine every transition identity.
Duplicate identities, gaps, reordered entries, noncanonical/truncated committed
JSON, unknown fields and versions reject. Hash chains detect inconsistency; they
are not signatures, authentication or proof that a process ran.

The creation payload binds campaign ID, canonical plan hash, manifest hash,
execution-manifest hash, hardware snapshot hash, admission hash, effective OpenMP
request map/hash, ordered selected trial IDs and original sequence numbers with
initial pending state, execution limits, evidence schema v2, development-only
admission and false measurement eligibility. Its `pilot_execution_id` hashes
these fields before adding that ID. It is a content identity of the recorded
execution context, not a global unique run nonce or host attestation. Neither
journal identities nor wall clocks alter existing deterministic campaign trial IDs.

The recorded environment identity covers the effective OMP_NUM_THREADS,
OMP_DYNAMIC and OMP_THREAD_LIMIT request for each selected trial. It does not
invent observed teams or placement. Hardware snapshots retain their existing
non-atomic and unauthenticated provenance limitations.

## State machine

All selected trials start `pending`. Only the next trial in manifest order can
transition. Completed trials form a prefix. After a failed or interrupted terminal
transition, no later transition or child launch is allowed; later selected
not-run records retain pending journal state.

| From | To | Condition |
| --- | --- | --- |
| pending | launched | Commit launch intent before the first child creation attempt |
| pending | failed/interrupted | Preparation/deadline failure or interruption before launch; terminal record has no process evidence |
| launched | completed | Successful trial record committed; independent verification still required |
| launched | failed/interrupted | Failed/unverified/interrupted trial record committed |
| terminal | anything | Forbidden |

A transition payload contains exactly `trial_id`, `from_state`, `to_state`,
`evidence`, and `reason`. Launch intent has null evidence/reason. Terminal evidence
is exactly `{path: TRIAL_ID/record.json, sha256: RECORD_DIGEST}`, with the v2 reason.
Arbitrary paths, traversal and external references reject. `launched` means
committed intent, not proof that OS process creation succeeded. Launch errors are
subsequently recorded as failed. Unsupported-oracle results are failed journal
terminals with explicit unverified evidence, never successful completion.

`indeterminate` is a derived inspection classification, not a transition written
by inspection. A launch without a terminal, or interrupted preparation with no
record, is indeterminate. Missing tail publication is incomplete; a gap before an
existing entry is corruption. Missing creation/binding metadata rejects because
no committed recovery identity can be established.

## Crash consistency and evidence-linked completion

The journal writer creates a new directory exclusively. It cannot reopen an
existing journal or resume. Concurrent creators collide; each entry filename is
also published without replacement. The writer writes a same-directory temporary
file, flushes and fsyncs it, hard-links it exclusively to its sequence filename,
fsyncs the containing directory and removes the temporary name. Creation also
fsyncs the output and its parent directories. It advances in-memory sequence and
state only after successful publication. Journal I/O failure stops the pilot and
prevents further launches or a final success index.

A `.pending-*` file is uncommitted, even if its JSON looks complete. It is never
parsed as an entry. Its presence is reported as incomplete publication. A complete
entry visible under its final name is atomic publication; this does not promise
survival through arbitrary hardware, filesystem, network-storage or fsync failures.
A failure after linking but before confirmed fsync may leave a complete visible
entry. Classification remains evidence-gated. The design requires local POSIX
hard-link/fsync semantics and does not claim distributed-writer consensus.

The terminal record is atomically committed before its journal transition. A
journal `completed` state alone never certifies success. Inspection uses the same
`pilot_context` and `verify_trial_evidence` gates as final `verify-pilot`: strict
schemas and identities, complete exact argv, mandatory regular streams, matching
sizes/hashes/limits, affinity/environment, exit/signal/truncation, independent
ordered-update Bellman–Ford reconciliation, worker correctness and development
eligibility. Journal terminal record hashes and reasons must match that evidence.
When the final inventory exists, the full existing v2 verifier must accept it too.

| Situation | Inspection result |
| --- | --- |
| Completed journal terminal plus fully verified trial record | `verified-complete`; may survive missing final index, while overall status remains incomplete |
| Failed/interrupted terminal plus matching verified failure evidence | `failed`/`interrupted`, preserving the precise v2 reason |
| Valid successful record but launch has no terminal transition | `indeterminate`, with `evidence_status=verified-complete`; never automatically repaired/promoted |
| Pending with no preparation/evidence | `pending` |
| Later not-run record after failure | `pending`, with `evidence_status=not-run` |
| Terminal record absent/modified, missing streams, contradictory outcome or journal alone edited to completed | Rejected, exit 2 |

For an incomplete run without a final inventory, actual bounded file hashes are
reconciled against the terminal record hash and its existing artifact/receipt
hashes. This shares the full per-trial semantic gates rather than trusting file
existence or creating a weaker correctness validator. A whole self-consistent
bundle can still be fabricated without an external trust anchor.

## R1 deadline ordering at the launch boundary

One absolute monotonic overall deadline is created before preparation and is
never reset or extended for journal I/O. Each trial has its own absolute timeout
cap; the earlier of these two deadlines governs every preflight and timing child.

Launch ordering is now:

1. Verify staged identities and check expiry before publishing launch intent.
2. Durably publish required launch intent for the first child attempt.
3. Construct the fixed argv, read the monotonic clock again, and recompute the
   remaining budget against the unchanged earlier deadline.
4. If positive, call the process layer with only this fresh timeout and the same
   absolute deadline. No further application journal or filesystem I/O occurs
   between this final check and the call.
5. The process layer checks its effective absolute deadline after selector setup,
   immediately before Popen, and uses it while waiting/draining pipes as well.

A userspace clock check cannot guarantee a strict real-time launch boundary under
arbitrary OS descheduling or native process-creation latency. The guarantee is
that a known-expired budget never intentionally authorizes a new launch. Fsync,
cleanup and evidence publication can still extend invocation duration; they never
replenish the child launch budget.

If the budget expires after durable intent but before process creation, the v2
record has budget-exhausted (overall) or timeout (trial), no new process receipt,
no invented return code or stdout/stderr, and false measurement eligibility.
Existing preflight evidence is retained if only the later timing launch expires.
A valid terminal failed journal transition is published where possible; later
selected trials remain not-run/pending. Inspection reports failed, never
verified-complete. If terminal publication fails, durable intent plus partial
failure evidence remains indeterminate/incomplete. Launch intent continues to
mean an attempted authorization, not proof that an OS process started.

Pilot schema v2 and journal v1 already represent these states; no migration or
version change is required. Older evidence is not rewritten or reinterpreted as
proof of compliance with this corrected runtime deadline ordering. The independent
correctness gate, process-group cleanup and bounded capture remain unchanged.

## Interruption and limits

Timeout, output/capture errors, launch failure and KeyboardInterrupt retain the
existing bounded process-group cleanup. The CLI temporarily maps SIGTERM to the
same interruption path while executing `pilot`, restoring the prior handler on
exit. Repeated SIGTERM is ignored after the first request while cleanup and
interruption evidence publication finish. SIGTERM during child execution can produce failed v2 evidence and an
interrupted journal terminal. Interruption before final publication may leave
only partial evidence and returns 130. Library/API callers retain responsibility
for their own signal policy; the API does not install process-global handlers.

SIGKILL, host death or abrupt parent termination cannot run cleanup. A launched
journal state never proves the child or descendants stopped. Inspection reports
indeterminate and does not signal or launch anything. An operator must assess
liveness separately before any future recovery decision. Tests explicitly clean
up their owned child groups after controlled abrupt parent death.

Only terminal records that pass existing v2 evidence checks can be classified
verified-complete. No interruption, journal edit or missing-file heuristic can
promote an incomplete trial. Normal successful pilot behavior and all existing
v2 record fields remain unchanged; the final inventory additionally hashes the
separate journal files.

Run the focused tests explicitly (outside the socket-restricted sandbox for the
real Unix-socket fixtures):

```sh
python3 -B tests/test_campaign_journal.py
python3 -B tests/test_campaign_pilot.py
```

Phase 6B-2B-2 actual resume/retry decisions, liveness ownership/attestation,
scientific execution, resource isolation, larger campaigns, analysis and inference
remain deferred and require separate authorization. No hosted-CI, race-freedom,
TSan acceptance or performance claim follows from journal validation.

## Phase 6B-2B-2: explicit safe resume v1

Only new pilots using `execution-owner.json` / `directory-flock-v1` are resumable.
Ownership binds the original output path, device and inode: copied or relocated
evidence remains verifiable but cannot bypass the original writer lock to resume.
The writer holds an exclusive nonblocking lock on the output directory inode
through final publication. Resume holds that same lock throughout preflight and
execution. This requires a trusted local POSIX filesystem implementing directory
`flock`; it coordinates cooperating writers, not malicious filesystem mutation.
Legacy evidence without this protocol remains inspectable and verifiable but is
rejected for resume: absence of a live writer cannot otherwise be established.
No PID, parent death, stale PID file or liveness guess authorizes execution or
signals another process.

```sh
python3 -B benchmarks/python/campaign.py resume-pilot \
  --output /tmp/dynagraph-pilot-output \
  --execute-development --authorize-resume
python3 -B benchmarks/python/campaign.py inspect-resume \
  --output /tmp/dynagraph-pilot-output.resume-v1
```

Both flags are required. Ordinary pilot, verify-pilot and inspect-recovery never
resume. The original recorded input root is required; all pending inputs and the
binary are checked against original hashes before any child starts. The plan,
manifest, ordered selection, journal chain, terminal references, stream hashes,
full correctness evidence and independent Bellman–Ford oracle are reverified.
A corrupt or contradictory state rejects the entire operation. Pending prepared
but incomplete trial directories are conservatively indeterminate and rejected.
Failed trials are never retried. Interrupted or launched-without-terminal trials
are blocked because old descendants may survive. Fully verified completed trials
are reused without touching their evidence bytes, timestamps or provenance.
No all-complete no-op attempt is created.

The original directory and journal v1 are immutable during resume. A sibling
`OUTPUT.resume-v1` is reserved with exclusive mkdir and never reopened for writing.
It contains canonical immutable `00000000.json` (authorized) and optional
`00000001.json` (finished), using resume-event schema v1 with sequence, previous
entry hash and SHA-256 entry identity. The authorized payload uses resume schema
v1 and binds original absolute location, execution identity, chain head, plan and
manifest hashes, full original inventory plus final-inventory hash if present,
ordered selection, original limits, ownership protocol, explicit authorizations,
reused/pending IDs, attempt sequence 1 and development-only classification.
The terminal event binds the attempt identity, fresh pilot inventory and verified
recovery outcome. Both use existing no-replace link/file-fsync/directory-fsync
publication. Parent fsync makes the reservation durable before child execution.
Unpublished temporary bytes never count as committed events.

`pilot/` is an ordinary pilot v2 / journal v1 execution containing only pending
IDs in original order, with fresh observed hardware/provenance. It uses the same
runner, command construction, limits, verifier and oracle. Reused trials are
explicitly labelled original; newly executed trials are labelled resume.
No reuse overhead enters C++ benchmark timing. Every result remains
`measurement_eligible=false`; no team-size, CPU placement or exclusivity claim
is introduced. The original 104-trial expansion and all scientific admission
contracts remain unchanged.

Budget policy `fresh-attempt-including-preflight-v1` explicitly grants one fresh
bounded wall budget equal to the original recorded limit, starting before resume
preflight. This does not consume or reinterpret the old monotonic clock. Input
checks, publication/fsync and launch setup consume the new fixed budget. The
absolute cap flows into the existing runner and process layer; neither resets
nor compensates for I/O. Original per-trial, stream and total selection caps apply.
Known-expired budgets authorize no new process. Userspace scheduling/native spawn
latency remains a practical real-time limitation. Process-group cleanup and CLI
SIGTERM/KeyboardInterrupt handling remain in force.

`inspect-resume` is bounded and read-only. It checks both chains, original snapshot,
fresh context/limits/selection and existing v2 per-trial evidence. Exit 0 means a
settled transaction; inspect `execution_status` for complete versus failed.
Exit 1 means incomplete publication; exit 2 means rejected/corrupt/unavailable.
The execution command exits 1 for a failed or incomplete outcome. If terminal
publication fails, inspection retains verified new completions but reports an
incomplete transaction. Missing initial authorization is rejected, never inferred.

Repeated attempts are deliberately unsupported. Any reservation, even empty,
blocks another resume. After a crash or SIGTERM, inspect original and resume
journals to distinguish reused completion, newly verified completion, pending,
failed/interrupted and indeterminate launch. Do not delete a reservation to force
retry: descendants may still run. A second authorization cannot override this
barrier. Relocation of resume transactions is unsupported because original
location and sibling identity are bound. Stronger process ownership, safe repeated
resume, retries and resource isolation require future separately authorized work.
These integrity hashes do not authenticate a malicious producer or guarantee
arbitrary hardware-failure durability.

## Phase 6B-2B-3A runtime observations

New original pilots and new resume trials use the separate
[runtime provenance v1 contract](runtime-provenance.md). Reused trials retain
original observations byte-for-byte; new trials bind observations to the resume
attempt ID. The existing pilot v2 and journal v1 formats and R1 launch ordering
remain unchanged. Missing process observations do not imply execution failure or
scientific eligibility; contradictory provenance rejects evidence verification.
No observed OpenMP teams are claimed by this phase.
