# Development workload-region observations (Phase 6B-2B-3B-3)

This opt-in diagnostic records participation inside delta-stepping's existing
persistent parallel region. Scientific eligibility remains false. Default CLI
records, policy decisions, update semantics, reference oracles and timing brackets
retain their contracts. No dependencies are added or installed. The new CTest tier is explicitly enabled
with `DYNAGRAPH_ENABLE_WORKLOAD_DIAGNOSTICS`; the historical 31-name default
registration list and archive evidence profiles retain their meanings.

## Native architecture and bounds

`DeltaSteppingOptions::workload_observations` is a nullable, call-owned pointer.
A null pointer performs no observation, allocation or additional synchronization.
The caller must serialize access to a shared collector and retain it through the
query. Independent collectors support independent immutable-graph calls.
`WorkloadObservations::prepare` reserves distinct worker slots before entry. Each
participant writes only its slot. Observation exceptions enter existing per-thread
exception slots; collective barriers and a single coordinator publish failure.
Failures propagate after collective region exit, before returning a successful
SSSP result. Entry errors prevent algorithm work; exit errors prevent success.

Limits are 257 regions, 64 configured workers, 16 OpenMP levels, an 8192-CPU kernel
affinity mask, 64 KiB per proc read and 1 MiB serialized evidence. The Python CPU
array contract additionally limits each observed affinity to 4096 entries. Larger
unsupported observations fail closed. Linux syscalls are conditional at compile
time; opt-in observations fail on other platforms. Ordinary algorithms remain
available there. Observations perturb execution and must not be timed.

Native schema `dynagraph-workload-native` version **2** contains consecutive
`region_id` records, requested and configured workers, and actual participating
thread slots. Each slot records OpenMP number, actual team, parallel/active/max
active levels, and ancestor team sizes/numbers including the initial and current
levels. Entry and exit samples contain syscall TID, getpid TGID, independently
read task-status Pid/Tgid, task-stat generation ticks, leader task-stat generation
ticks, process group, session, sched_getcpu and effective thread affinity.

The `team` field and slot count are actual workload observations, including valid
runtime reduction and nested serialization. Initialization and serial algorithms
use Dijkstra and produce no fictitious regions. A bounded independent edge-list
Bellman-Ford replay derives how many delta calls should occur, accounting for equal
updates and no-effect bypasses. Bounded pilot graphs have at most 4096 edges;
the unchanged default heuristic selects Dijkstra on that subset.

Publication uses exclusive no-follow creation, checks the entire write, fsync and
close, and never overwrites existing evidence. A crash may leave incomplete output;
no completed receipt or successful reuse follows from those bytes. CLI correctness
output is only successful after diagnostic publication succeeds.

## Binding, resources and verification

Bound schema `dynagraph-workload-bound` version **1** binds the canonical native
object digest to the affinity receipt digest and its complete binding: execution,
trial, attempt, journal context, process index, command, executable digest, worker
request and original/resume origin. It also binds the hardware digest, expected
region count, recomputed classification, explicit scientific false flags and
limitations. Native byte integrity is separately covered by trial/global artifact
inventories. Digests provide local consistency, not authenticated provenance.

Bound resource observations retain parent pre-GO process affinity, online CPUs,
visible cgroup effective cpuset and quota pairs. The hardware digest references
`hardware.json`'s available package/core/SMT-sibling and NUMA observations. Existing
enforcement validation reconciles the requested set against online/cpuset/quota
limits; workload validation checks every sampled CPU against its thread affinity
and every thread affinity against the enforced set. Migration between valid sample
CPUs is allowed. A narrower valid thread affinity is allowed.

Classifications are `observed_consistent`, `observed_contradictory`, and
`insufficient_evidence`. All available task facts are checked even when another
field, endpoint, thread or region lacks evidence. Any known contradiction takes
precedence over missing facts. Missing mandatory task evidence alone is insufficient. Both prevent successful
trial completion and `verified-complete` recovery. Unknown fields, including
invented availability flags, are rejected. Missing/truncated/malformed JSON or
missing bound artifacts cannot establish completion. Consistency concerns only
reported entry/exit samples and pre-GO resources; absent optional topology cannot
establish physical-core or isolation conclusions. For serial policies, consistency
means the independently expected absence of delta regions, with no team claim.

### Four historical audit defects prevented

| Finding | Mandatory reconciliation |
| --- | --- |
| F1: leader start identity | Every entry/exit leader tick equals the enforcement-bound process generation. A participating leader's own tick must also equal it. Rehashing either or both samples does not remove the check. There is no flag that disables it. |
| F2: foreign worker membership | Every task's TGID and status Tgid equal the bound PID; status Pid equals syscall TID. Group/session equal the bound session leader PID. Generations must be stable across entry/exit and repeated appearances, and cannot precede process creation. Group/affinity agreement alone is insufficient. |
| F3: impossible nesting | Actual team equals current ancestor size; thread numbers are valid; initial team is 1/thread 0; active level equals the number of ancestor teams larger than one; a newly active workload team cannot exceed max active levels. A serialized inner team may retain an enclosing active level after its caller lowers that ICV. All teammates agree on enclosing ancestry. Active two-thread regions with max active levels zero fail. Serialized nesting is valid. |
| F4: primary versus leader | OpenMP thread 0 is the encountering primary. The Linux leader is TGID, with separately sampled start ticks. No TID=TGID requirement is imposed on OpenMP thread 0. A real joined std::thread fixture exercises this distinction through the affinity barrier and semantic verifier. |

These observations cannot authenticate proc contents against a malicious producer.
A self-consistent wholesale fabrication by an actor controlling all evidence is
outside the local integrity contract; independent semantic contradictions remain
errors even after refreshing digests, record hashes, inventories and journal chains.

## Pilot, offline, journal and resume integration

`campaign.py pilot --observe-workload` requires both `--execute-development` and
`--enforce-affinity`, explicit bounded trial IDs, and diagnostic-phase trials only.
It adds `--workload-observations workload-native.json` to the existing verify argv;
it never instruments a timing worker. The full C++ replay oracle and independent
Python correctness oracle remain mandatory. After successful process exit, the
parent publishes `workload-bound.json` and requires consistent diagnostics before
publishing a successful trial and completed journal transition.

Pilot execution v2 gains an optional exact `workload_policy` marker. Legacy pilot
v2 without it remains readable. Diagnostic files without the marker are rejected
as a downgrade. Native v1 cannot satisfy the new native v2 contract. Affinity
receipts v1 and v2 remain readable under their existing strict semantics. New
workload-contract completion requires v2 atomic GO accounting; a v1 receipt is
readable but insufficient for that stronger contract. This prevents a rehashed
affinity-receipt downgrade from authorizing observed completed reuse. Unknown
or unconfirmed GO delivery never establishes completion.

The shared `verify_trial_evidence` gate verifies workload evidence for both
`verify-pilot` and `inspect-recovery`. Completed reuse therefore repeats semantic
validation without executing archived code. Journal schema remains v1. Resume
requires renewed `--observe-workload`, `--enforce-affinity`,
`--execute-development` and `--authorize-resume`; its authorization header is v3.
Legacy resume headers v1/v2 remain unchanged. A legacy original cannot be upgraded
to the workload-observation resume contract: its completed evidence lacks mandatory
membership observations and cannot be reused under that contract. New diagnostics bind the fresh attempt
ID; reused originals are immutable. Existing single-use reservation, ordered
pending-only execution and no-retry rules remain in force.

## Commands

Build and exercise the real bounded fixtures (the test harness uses actual Linux
affinity, task identities and GO syscalls with a **synthetic visible cgroup hierarchy**
to avoid depending on container cgroup visibility):

```sh
cmake --preset debug -DDYNAGRAPH_ENABLE_WORKLOAD_DIAGNOSTICS=ON
cmake --build --preset debug -j2
python3 -B tests/test_campaign_workload.py build/debug/tests/workload_fixture build/debug/dynagraph_bench
cmake --preset release -DDYNAGRAPH_ENABLE_WORKLOAD_DIAGNOSTICS=ON
cmake --build --preset release -j2
ctest --preset debug
ctest --preset release
python3 -B -m unittest discover -s tests -p 'test_campaign*.py'
```

Set `DYNAGRAPH_WORKLOAD_EVIDENCE_DIR` to a new directory for retained real fixture
native observations, process receipts, bindings and stdout/stderr. The nine modes
are one worker, two workers, dynamic reduction, three repeated regions, active
nesting, serialized nesting (including max active levels lowered to zero inside an active outer team), joined-thread caller and serial Dijkstra. Each delta
result is checked against Dijkstra; pilot tests additionally use independent Python
Bellman-Ford. Native fixtures alone can be reproduced with
`build/release/tests/workload_fixture MODE NEW_OUTPUT.json`; set
`OMP_THREAD_LIMIT=1` for dynamic reduction, and 4 for active nesting.

An already prepared development plan/manifest can opt in with:

```sh
python3 -B benchmarks/python/campaign.py pilot --plan PLAN --manifest MANIFEST --root INPUT_ROOT --output NEW_OUTPUT --trial-id DIAGNOSTIC_ID --execute-development --enforce-affinity --observe-workload
python3 -B benchmarks/python/campaign.py verify-pilot --output NEW_OUTPUT
python3 -B benchmarks/python/campaign.py inspect-recovery --output NEW_OUTPUT
python3 -B benchmarks/python/campaign.py resume-pilot --output INTERRUPTED_ORIGINAL --execute-development --authorize-resume --enforce-affinity --observe-workload
```

Do not change scientific plans or workload goldens to enable these diagnostics.
The timing CLI rejects `--workload-observations`; the timing API also rejects a
non-null collector before reading inputs or emitting timing samples.

## Limits and deferred work

Entry/exit sampling does not prove stable placement, CPU ownership, absence of
contention, NUMA isolation, externally authenticated evidence or physical-core
scaling. No performance claim or scientific campaign is authorized. The unmet
TSan acceptance gate remains unmet; its earlier LIKELY TOOL/RUNTIME LIMITATION
classification is preserved. No retries, dependency installation, push, merge or
PR are part of this phase. See the research log for actual validation outcomes and
missing local historical evidence/dependency limitations.

Resource opt-in adds native workload v3 CLOCK_MONOTONIC entry/exit envelopes while
preserving exact v2 fields without that opt-in. These intervals bind the separate
resource collector to actual workload boundaries. See the
[resource interference contract](resource-interference.md) and
[Phase B acceptance evidence](phase-b-acceptance.md).
