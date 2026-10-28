# Parallel and concurrency validation — Phase 5C-2B

This test-only suite checks complete shortest-path results, graph preservation,
runtime configurations and serialized/independent-client use. It does not establish
race freedom, scalability, speedup or publication-grade performance. Production
algorithms, APIs, heuristic and benchmark timing are unchanged.

## Oracle and corpus

`concurrency-validation-v1` reuses the synchronous, record-based Bellman–Ford in
`sssp_test_support.hpp`, through `system_validation_support.hpp`. It does not use
production shortest paths or CSR traversal to compute expected distances. Complete
distance vectors and authoritative offsets/destinations/weights are compared,
including unreachable vertices. Static expectations are computed before query
repetition; seeded trace expectations for all 17 checkpoints are precomputed.
Small bounded graphs keep all finite path sums safely below uint64 infinity.

The original adversarial fixture constructor moved verbatim into
`adversarial_test_support.hpp` (only the inline function name changed). The old
adversarial executable's main, cases, modes, assertions and trace loops are
unchanged: 14 fixtures, 28 traces, 230 updates, 258 checkpoints, 2064 comparisons.
The new static corpus reuses initial fixture graphs and does not apply their
update lists. Fixture-only hand checks and stale-Dijkstra witness assertions run
outside the repeated parallel query loops, and do not supply expected vectors.

| Case | Family | V / E | Construction |
|---|---|---|---|
| 0 | dense_zero | 13 / 145 | Existing adversarial 1: weight-100 entry into a complete 12-vertex zero region, including loops |
| 1 | hub255 | 257 / 256 | Existing adversarial 3: entry 0→1 at 100, then 255 unit-weight hub edges |
| 2 | hub256 | 258 / 257 | Existing adversarial 4: same construction, degree 256 |
| 3 | hub257 | 259 / 258 | Existing adversarial 5: same construction, degree 257 |
| 4 | frontier_fanin | 49 / 544 | 0→u at 1 for u=1..32; each u→v at 32−u for v=33..48 |
| 5 | light_closure_heavy | 7 / 10 | Existing adversarial 11: 15/16/17 boundary edges, zero edges/cycle and future stale records |
| 6 | stale_hub_chain | 64 / 124 | Existing adversarial 10: entry at 100, hub weights 10v, and zero chain 2→3→…→63 |
| 7 | disconnected_max | 18 / 15 | UINT32_MAX chain 0→…→7, edge 7→1; disconnected chain 9→…→15, zero loop 16→16, isolated 8 and 17 |

At delta 16, measured base case 5 must exhibit at least three light passes and a
heavy phase. Measured case 6 at delta 1/request 1 must report at least 60 stale
delta records. Hub degrees straddle the production 256-edge Work chunk boundary.
Fan-in proposes competing decreasing labels; actual CAS outcomes depend on the
schedule. A positive CAS-retry count is never required.

Extended cases 8..15 are explicitly defined variants of cases 0..7: reverse every
vertex ID with v→V−1−v, move the source from 0 to V−1, preserve zero and
UINT32_MAX weights, and replace each other positive weight w with 2w+1. Sort
records by endpoint afterward. These are related variants, not independently
sampled topologies. Default source is 0 for base cases. A source override is
explicit and requires a selected case. Static fixtures do not depend on the
root seed; the seed controls the reused seeded traces and separate engines.

| Direct profile | Workloads | Deltas | Requests | Metrics modes | Repetitions | Direct queries |
|---|---:|---|---|---|---:|---:|
| fast | 8 | 1,16,UINT64_MAX | 1,2,4 | off,on | 2 | **288** |
| stress | 8 | 1,2,3,16,UINT32_MAX,UINT64_MAX | 1,2,4 | off,on | 20 | **5760** |
| extended | 16 | same six | 1,2,4 | off,on | 100 | **57600** |

No corpus is shortened to meet a budget. Explicit CLI selectors run a documented
subset and print its actual count. Expected work/state fingerprints reuse the
existing little-endian uint64 FNV helper; they are reproducibility markers, not
cryptographic provenance or independent samples. Python pins the base hub257
generation fingerprint to 13210075048839355636.

## Extra fast scenarios and counts

The default C++ executable additionally runs:

- Six measured runtime queries: cases 3 and 4, delta 16, worker requests 0,2,4.
- Two ordinary host callers, each performing four queries on the same immutable
  fan-in graph, with independent metric/result/exception slots: eight queries.
- Two callers owning separate always-delta adaptive engines, one each for seeded
  Phase 5C-1 cases 0 and 7: initialization plus 16 updates each, 34 state checks.
- One shared always-delta engine on the existing 96-vertex history graph. Each of
  two callers makes four strict decreases to its own entry edge (0→1 by 10,
  0→95 by 25). One mutex covers **every** engine access, inspection, authoritative
  ledger access and local snapshot. Initialization plus eight updates is nine
  state checks. Each client owns a ledger snapshot, output and exception slot;
  the authoritative ledger is protected by the same mutex. Expected values here
  are computed from the locked snapshot because lock acquisition order varies.
  Failure context retains the complete committed transaction prefix from both
  clients plus the attempted update, not just one client's local subsequence.
- Four existing fast seeded cases **0,7,14,31**, root seed 1544560678, source 0,
  requests 2 and 4: eight traces, **128 updates**, **544** state comparisons.
  Each of 17 checkpoints compares always-delta, heuristic, rotating public
  overrides and standalone delta. All 16 original nonincreasing requests remain,
  including equal requests. Metrics alternate. No graph topology changes.

The three client scenarios total **51** state comparisons. Default C++ all-suite
distance comparisons total **889** (288+6+51+544); its **288 direct matrix queries**
are reported separately. Initialization uses the existing engine API, not an
invented parallel initialization path. No-effect/equality bypasses are retained.

A shared-future start gate makes both host callers eligible; thread creation
failure releases and joins already-created clients. Exceptions are captured per
client, all threads are joined, then diagnostics/results are evaluated. Nested
OpenMP errors are likewise captured inside the region and inspected after join.
No concurrent shared-graph mutation or unsynchronized shared-engine call occurs.
Eligibility to execute concurrently is not proof of simultaneous progress.

Existing isolated `delta_failure`, `adaptive_failure` and `incremental_failure`
executables remain unchanged and run with the full suites. They cover coordinator
and post-CAS allocation failures, collective propagation, rollback where promised,
identical retry and a different subsequent update. No fault injector or hook was
added to production or combined with normal client tests. CTest timeouts remain
the deadlock bound; successful bounded execution is not a general deadlock proof.

## Runtime observations and scheduling

`test_concurrency_runtime.py` launches fresh subprocesses with NUM_THREADS=2 and:

| Configuration | THREAD_LIMIT | DYNAMIC | MAX_ACTIVE_LEVELS | Queries |
|---|---:|---|---:|---:|
| bounded flat | 2 | FALSE | 1 | 6 |
| serial constrained | 1 | FALSE | 1 | 6 |
| dynamic flat | 2 | TRUE | 1 | 6 |
| nested inactive | 2 | FALSE | 1 | one per observed outer thread, at most 2 |
| optional active nesting | 4 | FALSE | 2 | one per observed outer thread, at most 2 |
| optional genuine four | 4 | FALSE | 1 | 2 |

The last two require the explicit Python `--optional` flag and are not in default
CI. If the requested optional team is not observed, Python records correctness
at the achieved size and explicitly skips that coverage claim. Serial nested
outer regions need not consume an active level; the inner-serialization assertion
applies when the outer team actually has multiple threads. Genuine worker 4 is a
bounded oversubscription correctness check here, not evidence of four CPU cores.

NUM_THREADS is not an actual-team measurement: production's explicit num_threads
clause can override it. Request 0 uses the runtime default. Dynamic teams can
shrink. THREAD_LIMIT is not assumed to cap the sum of independent ordinary-host
callers' teams. The Python global limit checks apply to isolated flat probes,
not aggregate concurrent clients. No production scheduling was changed.
OMP_SCHEDULE does not override the production `schedule(dynamic,1)` loops.
Repeated runs explore possible assignments without guaranteeing execution diversity.

Each JSON observation records family/version, seed/case/source/delta, request,
metrics mode, policy/observed selected backend, repetition/update/client, and
OpenMP environment. A flat call's `outer_team=0` means no test-owned outer region.
Direct metrics expose actual team size, each thread's edges/attempts/successes/CAS
retries, stale entries and light/heavy passes. `work_participants` counts threads
with positive observed edge work, not necessarily simultaneous execution. Adaptive
APIs expose aggregate work and actual teams for measured executed delta calls,
but no per-thread distribution. Unsupported/bypassed/unmeasured fields are null.
Metrics mode means collection was requested, not that a backend executed.

CAS retries count failed weak compare-exchange attempts; proposals rejected by
the initial candidate<old test do not enter that loop. Their count cannot be
reconstructed reliably from these APIs and is unavailable. No adaptive backend,
participation, selector overhead or unmeasured team is inferred from adjacent calls.

## Registration, commands and budgets

Default CTest adds `parallel_concurrency` and `concurrency_runtime`, labeled
`concurrency-fast`, PROCESSORS=2, timeout 120 s. Environment: NUM_THREADS=2,
THREAD_LIMIT=2, DYNAMIC=FALSE, MAX_ACTIVE_LEVELS=1. Python executes seven default
test methods and explicitly skips two optional methods. It checks a reduced
36-query matrix, 12 selected-case reproduction calls, three flat configurations,
inactive nesting, clients, one seeded trace and 20 malformed CLI invocations.
It does not multiply the full 288 queries by every runtime configuration.

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --test-dir build/debug -L concurrency-fast --output-on-failure
ctest --preset debug
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release
python3 tests/test_concurrency_runtime.py build/debug/tests/test_parallel_concurrency --optional
```

Stress and extended use independent options, default OFF:

```sh
cmake --preset release -DDYNAGRAPH_ENABLE_CONCURRENCY_STRESS=ON
ctest --test-dir build/release -L concurrency-stress --output-on-failure
cmake --preset release -DDYNAGRAPH_ENABLE_CONCURRENCY_STRESS=OFF
cmake --preset release -DDYNAGRAPH_ENABLE_CONCURRENCY_EXTENDED=ON
ctest --test-dir build/release -L concurrency-extended --output-on-failure
cmake --preset release -DDYNAGRAPH_ENABLE_CONCURRENCY_EXTENDED=OFF
```

Optional tier timeouts are 180/900 seconds. Python child timeout is 30 seconds;
timeouts fail without retries. Default concurrency target is under 10 seconds on
this environment, full default CTest under two minutes; these are validation
budgets, not performance comparisons. CI configuration is unchanged: its existing
Debug/Release/ASan+UBSan jobs run the new default entries. Intentional-race controls
are absent from all normal test registration.

## Reproduction and diagnostics

```sh
OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE OMP_MAX_ACTIVE_LEVELS=1 build/debug/tests/test_parallel_concurrency --suite direct --profile fast --case 3 --source 0 --delta 16 --workers 4 --metrics 1 --repeat 1
OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE build/debug/tests/test_parallel_concurrency --suite traces --seed 4294967295 --case 31 --source 0 --workers 4 --delta 16
OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=4 OMP_DYNAMIC=FALSE OMP_MAX_ACTIVE_LEVELS=2 build/debug/tests/test_parallel_concurrency --suite runtime --runtime nested
```

Options are unique option/value pairs. Suites: all/direct/runtime/clients/traces;
profiles: fast/stress/extended; runtime modes: flat/nested/four. Direct selectors
are case/source/delta/workers/metrics/repeat, with repeats bounded by profile.
Workers allow 0,1,2,4; default matrix remains 1,2,4. Trace selectors allow only
the four existing case IDs, source, positive workers and delta. Source requires
case and must fit its graph. CLI failures exit 2; correctness failures exit 1.

Failure reports include context, runtime variables, source/delta/request/observable
actual workers, metrics, policy, client/repetition, complete expected/observed
distance vectors, initial records, attempted trace prefix and shell-quoted exact
reproduction. An exception before a return labels the pre-call snapshot/unavailable
vector explicitly. Setup failures before a case context exists additionally print
the complete original invocation/environment and mark unacquired context/vectors
unavailable. Client failures reproduce the whole gated client suite because
serializing one client changes the tested scenario. Deterministic inputs do not
imply deterministic thread interleavings or the same mutex acquisition order.

## Detector gate and evidence

Phase 5C-2A's fresh GCC TSan builds classified the specific work_ warning as
**LIKELY TOOL/RUNTIME LIMITATION**. Valid implicit/explicit OpenMP barrier controls
also warned; intentional races were detected in the secondary layout experiment;
atomic release/acquire controls could pass. Many processes failed at startup.
Clang/libomp/Archer was unavailable and installed Helgrind failed negative-control
calibration. No blanket suppression, new dependencies or production workaround
was introduced. The eight control files and their evidence (938 previously hashed
files total) are preserved under `tests/tsan_controls/` and ignored phase5c2a directories.

The race-detector acceptance gate remains **unmet**. ASan/UBSan checks other memory
and undefined behavior properties, not data races. These deterministic oracles,
observed teams and bounded failures do not prove race freedom. No scaling,
publication or exhaustive-schedule claim is supported. Recalibrate OpenMP-aware
tooling on an approved suitable environment before treating it as detector evidence.

Exact executed commands, exit codes, pass counts, durations, observed team ranges,
initial/final preservation checks and limitations are recorded in
[research-log.md](research-log.md) and ignored `results/validation/phase5c2b/`.
The latter keeps raw stdout/stderr and JSON receipts; Phase 5C-2A files are not
overwritten. Stop after verification for independent source audit.
