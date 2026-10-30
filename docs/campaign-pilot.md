# Phase 6B-2A development pilot (R1 hardening)

Phase 6B-2B-1 adds a separate [recovery journal and read-only inspection](campaign-recovery.md).
Pilot evidence stays v2. Phase 6B-2B-2 provides explicit conservative
`resume-pilot` and read-only `inspect-resume`; see the recovery runbook.
New pilots hold directory ownership locks; legacy pilots cannot be resumed.

The `pilot` command executes an explicitly selected subset of an existing Phase
6B-1 trial manifest. This is development harness validation. Every trial has
`measurement_eligible=false`, including verified measured-phase trials. Scientific
plans are rejected. Scheduling is deterministic; timestamps, process outcomes and
raw durations are observations and are not deterministic identities.

## Prepare and execute

Use Python 3.8+ and an already built, trusted `dynagraph_bench`. The executable
reference in a plan is code that the user explicitly authorizes with
`--execute-development`. Its hash must match; no arbitrary command string, shell
expression or plugin is accepted. Do not use untrusted executables. No dependency
installation is needed for the pilot itself.

The retained development example has placeholder build hashes and cannot execute
unchanged. Create a new development plan with the actual executable hash and a
bundle under an explicitly chosen staging root. Do not modify the original plan.
For example, from the repository root, after building Release:

```sh
python3 -B - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, 'benchmarks/python')
from artifacts import write_bundle
from campaign_contract import expand
from workloads import canonical_json, sha256
root = Path('/tmp/dynagraph-pilot-inputs')
root.mkdir(exist_ok=False)
(root/'bin').mkdir()
binary = Path('build/release/dynagraph_bench').read_bytes()
(root/'bin/dynagraph_bench').write_bytes(binary)
p = json.loads(Path('benchmarks/configs/campaign-development-v1.json').read_bytes())
p['build']['executable_sha256'] = sha256(binary)
write_bundle(p['workloads'][0]['recipe'], root/'workloads/chain')
(root/'plan.json').write_bytes(canonical_json(p))
m = expand(p)
(root/'trial-manifest.json').write_bytes(canonical_json(m))
print('Select one trial explicitly:', m['trials'][0]['trial_id'])
PY
python3 -B benchmarks/python/campaign.py pilot \
  --plan /tmp/dynagraph-pilot-inputs/plan.json \
  --manifest /tmp/dynagraph-pilot-inputs/trial-manifest.json \
  --root /tmp/dynagraph-pilot-inputs \
  --trial-id REPLACE_WITH_PRINTED_TRIAL_ID \
  --max-trials 1 --wall-seconds 60 --timeout 10 --output-limit 262144 \
  --output /tmp/dynagraph-pilot-output --execute-development
python3 -B benchmarks/python/campaign.py verify-pilot --output /tmp/dynagraph-pilot-output
```

The input executable need not carry an executable permission bit: verified bytes
are staged as a private executable. Input paths must be contained under `--root`,
with no symlink components. Workload paths use the existing fixed bundle names.
All bundles are verified against their recipe by existing artifact regeneration
and replay. Both graph/trace hashes and the executable hash must match the plan.
The supplied trial manifest must exactly equal the deterministic expansion of the
plan, including schema types, row order, identities and every field.

Repeat `--trial-id` to select more trials and increase `--max-trials` explicitly.
Selection always follows original manifest sequence, independent of argument
order. Empty, duplicate and unknown selections reject. There is no implicit
matrix execution, resume, retry, analysis or comparison command. A new invocation
requires a new output directory; partial evidence is never reused or overwritten.

## Bounds and process contract

| Control | Default | Maximum |
| --- | --- | --- |
| Selected trials | 1 | 8 |
| Campaign wall budget | 60 seconds | 120 seconds |
| Entire individual trial, including preflight | 10 seconds | 30 seconds, also bounded by plan timeout |
| Each stdout/stderr stream per subprocess | 262144 bytes | 1048576 bytes, also bounded by plan output limit |
| Executable bytes per trial | — | 64 MiB |
| Each bundle file | — | 1 MiB |
| Workload | development split | 128 vertices, 4096 edges, 256 updates |

The monotonic wall budget starts before snapshot collection and preparation.
The smaller absolute campaign/trial deadline governs every launch. Remaining time
is recomputed after durable journal publication, and the process layer checks
again immediately before process creation. A known-expired budget authorizes no
new launch; arbitrary OS descheduling prevents a strict userspace real-time guarantee. Filesystem reads, hashing, atomic writes,
process cleanup and final evidence publication are synchronous and can extend
elapsed invocation time beyond the launch budget; this is not a real-time service.
Selected trials run serially. A failure or unverified result stops later launches;
remaining selections receive `not-run` records in manifest order.

Each child uses an argument list, explicit trial working directory, null stdin,
private POSIX session and bounded pipe capture. The v2 argv uses `./runner` and
fixed relative workload paths within that explicit trial cwd, so complete command
reconciliation also works after evidence is relocated. Timeout covers inherited pipes,
including a child that exits while a descendant retains stdout. The process group
is killed and the direct child reaped on completion, failure, timeout, output
limit or keyboard interruption. Exit codes and negative-returncode signals are
retained. No silent retry occurs. POSIX process groups do not contain a hostile
child that deliberately escapes its session; trusted benchmark execution is the
supported scope. This is not a process or filesystem security sandbox.

The existing plan memory declaration is retained as an admission requirement;
this phase does not enforce an OS address-space/RSS limit. Small workload and
input/output caps bound harness work; they do not certify total native-process
memory. Resource isolation and executable build attestation remain deferred.

## Correctness and classification

Every executable trial first runs the existing `verify --verification full`
protocol for its selected policy, delta and worker request. The existing
`verify_preflight` gate validates complete update counts, fresh Dijkstra checks,
small-graph Bellman–Ford coverage, final weights and output structure. R1 adds an
independent Python final-state reconciliation after that existing gate. It parses
the immutable graph and trace, replays the ordered updates with the existing
endpoint ledger (including expected-old-weight checks), and checks final weights
and the final-graph hash. Synchronous edge-list Bellman–Ford computes reference
distances using previous-round labels, independently of production graph engines
and reported distances. Every label must match, with `null` for unreachable
vertices, exact vector length and an independently checked source. Python integers
avoid intermediate overflow; the bounded graph/uint32 weights fit finite uint64
shortest paths. The method is `python-synchronous-bellman-ford-v1`, following the
existing test-only Python oracle without importing test modules at runtime.

This gate runs freshly for every diagnostic, warmup and measured selection, and
is reapplied offline to successful evidence. Missing references or mismatches
fail closed. It supplements the unchanged C++ per-update Dijkstra/Bellman–Ford
checks; it does not replace them. Timed workers retain their existing final-state
checks and output format; Python does not claim to inspect distance vectors that
the timing protocol does not expose. Inputs and
executable bytes are rehashed around each child. No correctness gate is weakened.

Diagnostic selections perform that full verification only. Warmup and measured
selections additionally run one existing `time` worker with `--warmups 0`; the
existing JSONL worker validator checks identities, complete timing/final-state
protocol and final verification. A warmup selection's captured durations remain
warmup evidence; its identity is never relabeled as measured. Worker decimal IDs
use the deterministic sequence number; the outer record retains the original
SHA-256 trial ID. There are no extra unselected trial repetitions.

`success` requires every applicable gate and zero child exit status. Unsupported
large workloads have no supported bounded oracle here: they are `unverified`,
`checked=false`, `outcome=unavailable`, and are not executed. Invalid inputs are
`input-error`; invalid or failing preflight is `correctness-failed`; invalid timing
JSONL is `protocol-failed`. Process reasons include `nonzero-exit`, `signal`,
`launch-error`, `capture-error`, `timeout`, `output-limit`, and `interrupted`.
Deadlines before launch produce `budget-exhausted` or `timeout`. Partial streams
are retained and never certify success. Output/publication I/O failure may leave
an incomplete directory with no index or inventory; offline verification rejects
it. An interruption during publication has the same incomplete-evidence behavior.

CLI exits: 0 completed pilot or integrity-verified evidence; 1 completed failed or
unverified pilot; 2 invalid requests, unsupported inputs or publication failures.
`verify-pilot` can return 0 for intact **failed** evidence; inspect its explicit
`execution_status`. Integrity verification is not validation success.

## Evidence schemas and inspection

All JSON is sorted-key compact canonical JSON with LF termination. Exclusive
hard-link publication after write/fsync provides atomic complete-file visibility
without replacement; parent directories are fsynced. Trial IDs and scheduling do
not depend on machine paths or wall time.

| File | Version and contract |
| --- | --- |
| `plan.json`, `trial-manifest.json` | Unchanged Phase 6B-1 v1 canonical inputs |
| `hardware.json`, `admission.json` | Existing v2 snapshot and recomputed development admission |
| `execution-manifest.json` | `dynagraph-pilot-execution` v2: campaign/plan/manifest hashes, selected full trial rows, effective limits, development and affinity policy |
| `TRIAL_ID/record.json` | `dynagraph-pilot-trial` v2, closed required fields listed below |
| `TRIAL_ID/workload/*`, `runner` | Staged immutable-input identities; raw staged bytes retained |
| `TRIAL_ID/N-verify.stdout`, `.stderr`, `N-time.stdout`, `.stderr` | Bounded raw child streams, including failed/partial output |
| `result-index.json` | `dynagraph-pilot-index` v2: execution-manifest hash, start/end, ordered record references, complete/failed status, false measurement eligibility |
| `sha256.json` | Relative filename to SHA-256 inventory of every evidence file except itself |

A trial record requires schema/version, campaign ID, canonical plan and manifest
hashes, complete deterministic trial row, complete workload identity/recipe and
input hashes, executable hash, `admission=development-only`, hardware hash,
requested plan affinity, observed **parent** affinity, effective OpenMP environment,
`observed_team_size=null`, unavailable execution observations, UTC start/end,
status/reason/message, correctness `{checked,outcome,oracle}`, false measurement
eligibility, child process receipts and an artifact hash map. Each receipt requires
complete argv, UTC start/end, returncode, signal, reason, truncation flag,
per-stream limit and stdout/stderr references, byte sizes and SHA-256 hashes. Unknown top-level schema fields reject during verification.

Read `result-index.json`, then its ordered `records` references. Inspect each
record's `trial.phase`, `correctness`, `reason`, `processes` and `artifacts`.
`verify-pilot` checks the complete file inventory, rejects symlinks, recomputes
admission and deterministic selection, reconciles identities and reapplies the
preflight/worker validators to successful retained output without executing it.
Every process receipt, including failed runs, must match the complete expected
argv reconstructed from the plan, trial and deterministic recipe source. Both
stream references must have their exact expected names; duplicate/extra aliases
reject. Both files must exist as regular files with matching sizes and hashes in
the receipt, trial artifact map and complete inventory. Receipt stream limits
must equal the execution-manifest limit, and actual byte counts must fit.
Requested affinity must equal the plan allocation, and the three recorded OpenMP
controls must equal the v2 execution contract. Observed parent affinity remains
separate; no child placement or team is inferred. Exit codes, signals, truncation,
correctness outcomes and trial/index status are reconciled. No process may follow
a failed process; after a failed/unverified trial, later selections must be not-run.

All pilot metadata, including the initial sha256.json, is read using nonblocking,
regular-file-only descriptors with bounded reads. Parent directories are walked
using directory descriptors with O_NOFOLLOW; the opened leaf is also O_NOFOLLOW
and checked by fstat before reading. FIFOs, sockets, devices, directories and
symlinks reject with controlled CLI failures. The same reader covers plan,
manifest, admission, hardware, index, records and staged bundle metadata. Same-user
concurrent mutation of a whole evidence tree is not an authenticated snapshot.
Capture I/O diagnostics use only remaining stderr capacity; omitted diagnostic
bytes set truncation while preserving capture-error and process-group cleanup.

R1 requires pilot execution/trial/index schema version 2. Version 1 is rejected;
no automatic migration or reinterpretation is performed, including for historical
contradictory evidence. Recapture a new explicitly selected pilot in a new output
directory. Phase 6B-1 plan/manifest v1, hardware/admission v2 and runtime provenance
v3 remain unchanged. Correctness.oracle records the independent Python method
alongside full preflight and, where applicable, worker validation. `checked=true`
with outcome=failed means gate validation was attempted and failed, not that all
oracle stages completed.

The verifier never executes an archived runner. Hashes detect accidental alteration; a
report and its inventory can both be fabricated. They are not authentication.

The snapshot uses the existing read-only collector without external compiler
queries (`binaries=False`); scientific runtime/compiler provenance may therefore
be unavailable, explicitly preserved in admission failures. Requested affinity
is recorded but not applied; parent affinity is observed separately and child
placement remains unavailable. Inherited `OMP_`, `GOMP_`, `KMP_`, and `LD_`
controls are removed; explicit OMP_NUM_THREADS, OMP_DYNAMIC=FALSE and
OMP_THREAD_LIMIT are retained in each record. These requests do not observe an
actual team. No snapshot proves active execution, exclusivity or future stability.

## Validation and Phase 6B-2B deferrals

Run `python3 -B tests/test_campaign_pilot.py` after building Release. The suite
uses synthetic failures and tiny real-worker controls, never the full campaign.
The Unix-socket metadata fixture requires socket-binding permission; run the
focused suite through the approved outside-sandbox path when the local sandbox
denies it. No dependencies are installed for these tests.
Set `DYNAGRAPH_PILOT_TEST_RUNNER` to an explicit built benchmark to test another
build. The new focused suite stays separate from the unchanged Phase 5C default
CTest/archive contract; run it explicitly with the existing focused regressions.

Phase 6B-2B work requires separate authorization: scientific execution/admission,
execution-time runtime/team/affinity observations, enforced placement and resource
isolation, larger workloads, resumption/retries, campaign matrix execution,
statistical analysis, visualization, performance/scaling claims and inference.
TSan acceptance and race freedom remain unestablished.
