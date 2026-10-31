# Development runtime provenance v1

Phase 6B-2B-3A adds observations to new bounded pilots and newly executed resume
trials. Execution still requires the existing explicit development authorization;
resume still requires both execution and resume authorization. No scientific
campaign, retries, resource isolation or automatic scientific admission is added.

| Category | Evidence | Interpretation |
| --- | --- | --- |
| Requested configuration | Original plan/build declarations, trial workers, recorded OpenMP environment and requested affinity | Requests, not execution behavior |
| Observed process configuration | Post-spawn PID/start ticks, executable SHA-256 match, leader affinity, visible cgroup2 ancestry, mapped libgomp ELF identity | A bounded snapshot of a matching child, not worker execution |
| Observer hardware context | Journal-bound hardware v2: topology, NUMA and available compiler identity; per-process online CPU IDs, kernel and OS | Namespace-visible context, not host allocation or stability |
| Observed OpenMP execution | Team size and region count null; intended workload observed false | Unavailable, not zero workers or zero regions |
| Scientific admission | development_only=true, measurement_eligible=false | Never promoted by provenance |

## Collection and scope

`campaign_process.capture` accepts an optional observer. Pilot collection runs once
just after Popen and pipe registration, inside the existing process-group cleanup
scope. It does not pause the child, change affinity, run another parallel region,
retry a missing observation, change scheduling policy or execute a discovery
command. The R1 clock check remains immediately before Popen. Observation time
consumes the same absolute timeout/deadline; finite metadata work and cleanup may
extend elapsed invocation duration. No strict real-time guarantee is introduced.
Snapshots may perturb scheduling; their presence does not create performance
quality evidence. Timeout accounting and C++ timing definitions remain unchanged.

Metadata reads require regular files, reject leaf symlinks, use nonblocking opens,
and read at most 1 MiB. Process executable hashing reads at most the existing
64 MiB executable cap. `/proc/PID/exe` and the existing runtime collector's
`/proc/PID/root` access are explicit kernel magic-link exceptions; the executable
must still be a regular file. Existing bounded ELF metadata, runtime file identity
and mapping reconciliation apply to libgomp. Linux x86-64 ELF/libgomp and cgroup2
are the supported runtime subset. Unsupported/missing sources remain unavailable;
malformed supplied facts or contradictory summaries reject during verification.
Missing cgroup fields and unsupported/unresolvable membership are explicitly
listed in limitations; malformed supported quota/policy records reject collection.

The snapshot retains its collection interval, PID, raw process stat and start
clock ticks. Start identity is checked again after collection. Exited/zombie
processes lose child-scoped observations. Linux EINVAL from terminating-process
proc metadata is treated as unavailable. Interpreter launches, exec races, early
exit, inaccessible sources and unsupported mappings can leave observations
missing. No affinity or runtime is attributed to the staged binary unless its
process executable matches the expected digest. The observer's visible online
CPUs and OS/kernel have their own scope. Affinity refers to the child leader,
not every OpenMP thread; topology/NUMA/compiler context is the earlier hardware
snapshot, not an execution-time observation of the child or compiler invocation.
Build declarations remain bound by the original plan identity and worker output;
querying the current g++ would not prove which compiler built an executable.

Delta-stepping's actual region already records `actual_threads_`, but timed calls
use the uninstrumented metrics path and timing metadata explicitly declares
`actual_workers` unavailable. The replay CLI does not expose an aggregate of
actual workload regions. Exporting/counting these observations would require a
new benchmark instrumentation contract. This phase leaves C++ byte-identical,
keeps both team size and relevant-region count unavailable, and rejects supplied
positive, zero, negative or boolean team assertions under this schema. Requested
versus observed comparison is unavailable; no match or mismatch is invented.

## Records, binding and compatibility

New pilots publish a separate canonical `runtime-contract.json`, with
`schema=dynagraph-runtime-contract`, integer `schema_version=1`, and origin
`{kind: original, attempt_id: null}` or `{kind: resume, attempt_id: ATTEMPT_HASH}`.
Each process receipt has a sibling `N-verify.runtime.json` or `N-time.runtime.json`
using closed `dynagraph-runtime-provenance` schema v1. It binds:

- journal execution content identity and canonical journal-binding SHA-256;
- deterministic trial ID, original/resume origin and resume attempt identity;
- complete command, staged executable SHA-256 and requested OpenMP controls;
- collection phase, interval, observation sources/scopes and limitations;
- explicit unavailable OpenMP execution and false scientific eligibility.

The trial's existing `execution_observations` text explicitly selects this
contract. Its existing artifacts map hashes every provenance record. The journal
terminal hashes the trial record, and the final inventory hashes all evidence.
Offline verification checks exact artifact coverage, schemas, binding, sources,
scopes, CPU arrays, cgroup summaries, runtime identity and timestamp containment.
Unsupported versions, invented teams, false scientific eligibility, missing
records, unknown provenance artifacts and contract downgrades reject. Failed
launches may have a null snapshot; observation failure is a capture error and
retains bounded diagnostics/cleanup. Interruption may likewise leave no snapshot.

Pilot v2, journal v1, hardware v2, runtime-mapping evidence v3 and resume v1 are
unchanged. Legacy pilots without the new marker/artifacts remain verifiable and
are never relabelled as observed. Unsupported new provenance cannot silently pass
as legacy evidence. No historical bytes or schemas are rewritten. SHA-256 binds
consistency; it does not authenticate a producer or prevent fabrication of an
entire self-consistent bundle without an external trust anchor.

Resume re-verifies original trial evidence using the same gate, retaining its
original provenance bytes. Only pending trials execute in a new pilot subtree;
their provenance records carry the separately committed resume attempt ID.
Resume inspection reconciles that origin with the authorization event. Original
inventory binding, ownership locks, no-duplicate completion, orphan protection,
permanent single-use reservation and bounded process cleanup remain in force.

## Runbook and admission limits

Use the existing `campaign.py pilot`, `verify-pilot`, `inspect-recovery`,
`resume-pilot` and `inspect-resume` commands documented in
[campaign-recovery.md](campaign-recovery.md). Ordinary verification is read-only
and never executes an archived runner. There is no new execution authorization.
Run focused tests explicitly after building the Release benchmark:

```sh
python3 -B tests/test_campaign_runtime.py
python3 -B tests/test_campaign_pilot.py
python3 -B tests/test_campaign_journal.py
python3 -B tests/test_campaign_resume.py
```

The latter suites include local Unix-socket integrity fixtures and need an
environment permitting those fixtures. They remain outside the pinned CTest
registration set; existing Debug/Release and sanitizer CTest validate the protected
algorithm/timing contracts independently.

OpenMP environment variables do not prove observed teams. Observed teams would not
prove exclusive physical cores. CPU affinity does not prove uncontended execution
or physical-core exclusivity. GitHub Actions runner allocation does not establish
exclusive physical cores. This Codespace cannot establish credible multicore
scaling. All pilot/resume results remain measurement-ineligible regardless of
observed mappings, affinity, quotas, correctness or successful local tests.

Phase 6B-2B-3B remains deferred: stronger workload-region instrumentation,
execution-time worker placement/stability, stronger process/resource ownership,
repeated recovery, isolation and any scientific-admission design require separate
authorization. Scientific execution, performance claims, inference and the unmet
TSan acceptance gate remain outside this phase.
