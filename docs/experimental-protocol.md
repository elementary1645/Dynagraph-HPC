# Experimental protocol

## Status

Current scope is Phase 6B-2B-2 [safe development resume](campaign-recovery.md).
Explicit dual authorization permits verified completion reuse and execution of
never-launched pending trials only. A single immutable sibling transaction binds
the original execution and grants a fresh bounded attempt budget. Failed,
interrupted, unresolved, legacy-unowned and repeated attempts are rejected.
Every child launch rechecks the unchanged monotonic deadline after durable journal
publication and at the process boundary. Known-expired budgets authorize no child;
this does not claim real-time scheduling under arbitrary OS descheduling.
The journal adds crash-consistent transition publication and read-only recovery
classification while preserving the completed R1 correctness/evidence protections
and pilot schema v2. Scientific execution, retries, broader recovery and resource isolation remain deferred.
The explicit authorization supersedes earlier execution deferrals only for this
small development harness. Phase 6B-1 plans, deterministic identities, admission
and ELF protections remain unchanged. Every pilot result is measurement-ineligible.
Scientific execution, complete campaigns, analysis, visualization, inference,
tuning and timing-boundary changes remain deferred.

Current authorized infrastructure scope is Phase 5C-3B-3R: intended-diagnostic
controls, portable evidence archives and independent offline verification. The
[reproducibility runbook](reproducibility-validation.md#phase-5c-3b-2-ci-contract-and-bounded-pipeline)
defines exact registration/execution gates and reproduction commands. Historical
phase statements below retain their original context. Stop after implementation
and local verification; Phase 6 is deferred. Hosted CI parity requires actual
hosted job logs and is not established by local workflow or driver checks.

The smoke uses the existing generation, independent verification, compiled replay,
both timing modes, complete dataset import, descriptive analysis and rendering
entry points on one tiny fixed-seed chain. All outputs remain harness-only,
regardless of build type. No algorithm, heuristic, timing boundary, workload format,
pin or scientific measurement definition changes. Artifact digests document
integrity, not producer authentication. TSan acceptance remains unmet.

Phase 5C-1 adds approved test-only [correctness/failure-resilience validation](validation-correctness.md)
on the merged 5B-4B baseline. Shared deterministic traces compare complete graph
states and distance vectors against independent record-based Bellman–Ford after
every operation. History-dependent allocation failures validate rollback, retry
and different-update recovery. Default fast validation runs in the existing
Debug/Release/ASan+UBSan matrix; stress and extended profiles are opt-in. Actual
commands/results are recorded in the research log. No algorithms, timing,
heuristic configuration in benchmarks or scientific evidence are changed.
Stop after 5C-1 implementation/testing for independent review; 5C-2 is deferred.

Phase 5B-4B now implements a separate [descriptive analysis contract](benchmark-analysis.md)
over complete 5B-3B evidence, under the explicit recovery/continuation request.
Earlier phase gates below describe historical scope. Stop after 5B-4B testing for
independent review. The checkout contains no separate 5B-4A design document.

The analysis plan prespecifies workload identities/weights, compatibility groups,
session/hardware declarations, comparisons, exclusions, evidence classes and
figures. Pair full traces within the same run/block, using exact ticks and
rational periods. The primary ratio is incremental / dijkstra; adaptive ratios
compare heuristic with each fixed policy. Retain zero durations and withhold
affected geometric aggregates. Report per-update distributions within trials,
never treating ordered positions as independent replication. No bootstrap,
inferential confidence intervals or significance tests are implemented.

Complete evidence validation is mandatory and independent of scientific
eligibility. Synthetic/instrumented/harness evidence stays explicitly labeled;
Codespaces is never automatically performance eligible. Controlled-hardware and
uninstrumented-build declarations are hashed user statements, not attestation.
No selected adaptive backends, isolated selector overhead or actual teams are
inferred from unavailable telemetry. Raw evidence is read-only and unchanged.

This is a prospective measurement protocol. Phases 1B, 2B, and 3B provide
sequential/parallel recomputation and transactional single-decrease repair
baselines. Phase 4B-1 adds forced-strategy switching with a shared fast path and
Phase 4B-2 adds a deterministic metadata-only heuristic with uncalibrated thresholds.
No calibrated model, benchmark results or speedup claims exist.
The OpenMP smoke test verifies functionality, not performance.
Phase 5A completed a read-only measurement architecture review. Phase 5B-1 now
implements deterministic inputs and independent replay only; no measurements.
Phase 5B-2 adds correctness-only adaptive-engine execution with independent
per-update state/oracle checks, specified in [benchmark-replay.md](benchmark-replay.md).

## Phase 5B-3B implemented timing infrastructure

The normative [timing contract](benchmark-timing.md) defines full-trace and
per-update boundaries, clock probes, raw integer units, fresh engines/processes,
balanced seeded policy order, provenance, durable JSONL and acceptance rules.
Python stages and SHA-256/recipe-verifies the bundle, runs all policies through
full verification, then launches separate measured workers. Each worker performs
independent final-state checks outside timing on its actual measured engine.
Separate preflight per-update verification is never attributed to the timed run.
No statistical analysis, speedups, calibration or performance claims are included.
Codespaces and sanitizer experiments are validation only. Stop at 5B-3B review.

## Phase 5B-2 correctness execution

Run the Python manifest verifier before C++ replay, and preserve the verified
bundle and JSON record together. The runner does not check cryptographic
identities or attest prerequisite completion. All four policies use the same
public engine update path and configuration of shared fast paths. Each update
advances a separate endpoint/weight ledger; a fresh reference graph, Dijkstra
and eligible small-graph Bellman–Ford check all weights and all distances.
Returned update outcomes and improved counts are independently checked.

Full mode checks initialization, every update and final state (including empty
traces). Bounded mode is deferred. Final arrays support comparison with Python's
independent final graph hash. Failures stop execution, exit nonzero and never
emit a success record. There are no clocks, performance comparisons, calibration,
statistics, threshold changes or Phase 5B-3 implementation. The JSON counts refer
to verification work, not performance measurements. Stop at the 5B-2 review gate.

## Phase 5B-1 implemented artifact protocol

The normative configuration, PRNG/draw order, canonical graph/trace/manifest
schemas, quotas, CLI and integrity checks are in [workload-artifacts.md](workload-artifacts.md).
Use the checked-in chain example or a complete schema-1 configuration. Seeds are
separate canonical uint64 decimal strings for graph/weight/source/trace; no host
RNG/distribution or float sampling determines bytes. All five initial families
have exact declared/derived counts and sorted unique endpoint pairs.

Initial requests cycle a declared strict/equal/repeat/unreachable schedule.
Positive-edge pools use specified swap removal; exhausted budgets fail rather
than reset/increase weights, shorten traces, change seeds or substitute modes.
Unreachable classification uses fixed topology, not measured backend outcomes.
Oracle-targeted localized/broad traces and additional families remain deferred.

Bundles preserve full generation configuration, versions, split label, resolved
source, counts, graph/trace SHA-256 and canonical final-graph SHA-256. The verifier
checks hashes before replay, validates each expected old weight using an independent
endpoint ledger, and checks exact regeneration against the recipe. Invalid data
or inconsistent provenance is an error, not a silently skipped observation.
Split labels record provenance; graph-instance split isolation is a later
experimental orchestration requirement, not enforced by this generator.

```sh
python3 benchmarks/python/generate.py generate --spec benchmarks/configs/chain-v1.json --output data/generated/chain-v1
python3 benchmarks/python/generate.py verify --manifest data/generated/chain-v1/manifest.json
ctest --test-dir build/debug -R '^workload_(artifacts|loader)$' --output-on-failure
```

Both artifact tests are in normal Debug/Release/sanitizer CTest. Loader tests use
the built C++ executable on initial/final graphs and independent small-graph
Bellman-Ford, without modifying graph or SSSP contracts. Existing failures/race
limitations remain. No latency, scaling, calibrated thresholds or novelty result
is inferred from regeneration, SHA-256, CTest durations or correctness checks.
Timing infrastructure is now separately authorized in Phase 5B-3B; later phases remain gated.

## Correctness before timing

- Validate graph parsing and storage invariants before algorithm experiments.
- Validate Dijkstra on hand-checked and randomized small graphs with an independent
  oracle. Compare later algorithms with fresh sequential recomputation.
- Include disconnected graphs, self-loops, duplicate-edge policy, zero weights,
  equal-distance alternatives, invalid input, and integer overflow boundaries.
- For dynamic workloads, preserve fixed topology and replay exactly the same
  decrease batches for each method. Validate distances after every batch.

## Reproduction record

Each future run must record the Git revision and dirty state, build type, compiler
and flags, CMake and OpenMP versions, OS, CPU model, physical/logical cores,
memory limits, thread count, affinity, and OpenMP environment. Record the full CLI
invocation, configuration, random seeds, dataset provenance/checksums, source
vertices, and ordered update traces. Preserve raw observations and analysis code.
Pin Python analysis dependencies when those tools are introduced.

## Measurement design

- Define datasets, sources, batch sizes, locality, and weight distributions before
  collecting evaluation results. Document any synthetic weight assignment.
- Separate policy tuning workloads from held-out evaluation workloads.
- Restore identical initial state for each independent run. Use a monotonic clock.
- Separate loading, preprocessing, update application, algorithm work, policy
  overhead, validation, and output. Report end-to-end cost as well as kernel time.
- Predeclare warm-up and repetition counts in experiment configurations; retain
  every measured repetition. Randomize method order with recorded seeds.
- Report distributions and uncertainty, not a single best runtime. State the
  estimator and treatment of failures; do not silently discard outliers.
- Compare against sequential recomputation and validated fixed-policy baselines.
  Define speedup as baseline time divided by candidate time for identical work.
- Measure memory and useful work where possible. Account for instrumentation
  overhead and use matching instrumentation across comparisons.
- Use dedicated multicore hardware for scaling claims. Shared Codespaces runs are
  development checks unless resource isolation is demonstrated.

## Artifact policy

Keep manifests and small curated summaries under version control. Generated data
and raw outputs go under ignored data/ and results/ paths. Provide checksums and
retrieval instructions for externally stored artifacts. Never substitute sample
or synthetic numbers for actual measurements in tables, plots, or the manuscript.


## Implemented Phase 1B correctness baseline

Sequential Dijkstra is the future full-recomputation baseline, not a research
novelty claim. Tests use synchronous Bellman–Ford on original input edge records,
independent of CSR traversal and heap scheduling. Each pass reads the previous
pass and writes a copy, for at most V-1 passes. Distances, rather than predecessor
trees, are compared from every source. Hand-checked fixtures cover sentinel,
zero-cycle, stale-entry, wide-distance, long-chain, and update behavior.

The deterministic differential suite uses mt19937 seed 0x51B2026 and 300 graphs
with 1–19 vertices. Alternating sampling probabilities 1/2 and 1/8 cover dense
and sparse graphs; weight families use small values including zero or full-range
PRNG values. Nonempty graphs are retested after setting the first input edge to
zero and then UINT32_MAX. Each source is run with and without instrumentation,
checking repeatability, counter identities, and all graph arrays for immutability.
The harness remains active with NDEBUG. CLI integration checks exact JSON and
error statuses; existing loader tests cover strict text validation.

Later experiments must record source revision, generator version/seed, input
checksums and provenance, source vertex, weight-update trace, compiler/build flags,
hardware, thread settings, instrumentation mode, and raw samples. Time file loading
separately from algorithm execution; specify whether allocation, initialization,
queue draining, and result destruction are included. Match counter modes across
comparisons and measure their overhead before interpreting instrumented timings.
No benchmark measurements or performance conclusions are supplied by this phase.

Phase 2B implements the fixed-delta parallel recomputation baseline described
below. Phase 3B adds sequential single-decrease repair. Scaling studies, batch or
parallel repair, and calibrated selection need separate approval and validation.

## Implemented Phase 3B validation and future measurement boundaries

IncrementalSSSPState is a sequential distance-repair baseline, not a novelty
claim. Tests maintain original edge records independently, rebuild a reference
graph and recompute Dijkstra after every accepted update, and use synchronous
Bellman–Ford on small graphs. Every accepted update checks componentwise
nonincrease, invariant reachability, exact stored weights/topology, outcomes,
instrumented/plain agreement, and distinct-vertex/queue/edge identities.

The deterministic suite uses mt19937 seed 0x31B2026, 120 graphs with 1–16 vertices,
every source, and 24 updates per nonempty graph/source. Dense/sparse sampling
probabilities alternate 1/2 and 1/7. Weights are full-range PRNG values or 0–31.
Every fifth request keeps its weight; other requests choose by modulo
old_weight+1 using uint64 arithmetic. Every third step reuses the previous edge.
Finite-weight decreases cannot make unreachable vertices reachable; tests assert
that invariant rather than inventing an impossible reachability-transition case.

Hand fixtures exercise zero cycles, equal paths, self-loops, repeated decreases,
unreachable tails, edges into the source, stale heap entries, wide distances,
6,000-vertex chains and a 900-vertex hub/fan-in graph. Initialization/adoption tests
cover invalid sources, dimensions, stale/malformed distances, nonzero sources,
lvalue-copy/rvalue-transfer ownership, independent states and stable array views.
Invalid update tests preserve graph/distances and sentinel metrics exactly.

An isolated sequential allocation-failure executable overrides ordinary C++ new
and delete; it has no OpenMP-specific activation and no production hooks. It first
counts allocations, then faults every observed allocation in both factories and
both repair instrumentation modes. Fixed-size allocation traces observe the live
distance array without allocation to prove failures occur after tentative writes.
Targeted stages cover initial journal/heap insertion and subsequent journal/heap
growth. Each failed update must preserve all graph arrays/distances/metrics,
then accept the same update and another independent update. An armed allocator
also verifies unchanged and weight-only requests need no propagation allocations.
This does not simulate every aligned allocator, OS, or hardware failure.

Useful development commands (actual results in research-log.md):

```sh
ctest --preset debug --output-on-failure
ctest --preset release --output-on-failure
ctest --test-dir build/debug -R '^incremental_(sssp|failure)$' --verbose
ctest --test-dir build/debug -R '^incremental_(sssp|failure)$' --repeat until-fail:20 --output-on-failure
```

Future comparisons must replay identical source/weight snapshots and ordered
traces. Report initial Dijkstra/state construction, graph acquisition/copy,
validation/lookup/commit, repair propagation including journal/heap allocation and
cleanup, and combined public-call latency with explicit boundaries. Use monotonic
wall time outside the kernel, no per-edge clocks. Main timings omit optional work
counters; diagnostic runs may measure phase costs separately. Include full
recomputation allocation/result costs and any future strategy-switching/state
maintenance costs. Do not compare a persistent view with a copied snapshot without
accounting for materialization. Keep loading, correctness oracles and trace resets
outside algorithm timing, but report end-to-end workloads separately.

Vary graph size, density, structure, source, update location/magnitude, warm/cold
execution, delta and actual thread counts. Preserve trace/seed/provenance metadata
and raw observations; monotone traces eventually reach zero, so reset snapshots
between repetitions. Report affected vertices and edges as outcomes; they are not
free features before a future adaptive decision. Tune on separate workloads,
measure initialization amortization, randomize paired method order, and distinguish
Codespaces exploratory checks from controlled multicore experiments. No batch or
adaptive benchmark engine is introduced in this phase.


## Phase 4B-1 switching validation and future fairness requirements

Forced strategies share one authoritative state and must leave it ready for the
next update. Every successful test update independently modifies original input
records, builds a fresh reference graph, compares Dijkstra and small-graph
Bellman–Ford, and verifies graph arrays, monotonicity, reachability, exact outcome,
decision route/reason, active/inactive metric fields and metrics-on/off equivalence.
Tests cover all ordered strategy pairs plus longer mixed sequences, default and
override dispatch, all policies/no-effect modes, singleton/cap-zero loops,
disconnected components, zero cycles, equal paths and uint64 distances. Separate
async host calls exercise concurrent independent engine objects. Same-engine
concurrent access is unsupported.

Randomized switching uses mt19937 seed 0x4B12026, 72 graphs with 1–10 vertices,
every source and 18 updates per nonempty graph/source. Families cycle through
sparse/dense random graphs (probabilities 1/7 and 1/2), hub/fan-in and chains.
Weights use full-range PRNG values or 0–31. Every fifth request keeps its weight;
other values use uint64 modulo old_weight+1. Configured policies cycle, no-effect
modes alternate, all six existing delta values are used, and selected trials
request four workers (otherwise two). Most calls use a cycling forced strategy;
every fourth uses the configured policy. These deterministic correctness traces
are not claimed to represent production traffic or measured scaling.

The new isolated failure executable has an OpenMP-safe injector: workers access
only atomic mode/trigger flags; host allocation counters and fixed-size traces are
accessed only outside parallel regions by the initiating host thread. It does not
activate the existing sequential global injector on workers. Successful host
allocation traces are replayed with a failure at every observed position for all
three strategies with/without metrics. The first three full-strategy allocations
are verified as CSR staging. Delta's new result vector and optional per-thread
metric vector are faulted after team exit. Scalar result validation/aggregation
and commit swap do not allocate; no fabricated allocation-failure case is claimed
there. Repair failures observe tentative writes to authoritative distances and
must roll them back. Separate one-shot atomic triggers fail first parallel-region
allocation and a 16-byte Entry-buffer append after CAS, retaining the standalone
delta test's inspected allocation-size contract. Every injected failure preserves
all graph arrays, distances and sentinel metrics, retries on the same engine, then
switches successfully to a different strategy. Initialization and allocation-free
shared bypasses are also checked. This covers ordinary C++ allocations, not every
aligned/runtime/OS failure; process-fatal OpenMP failures remain outside rollback.

Useful commands (exact results in research-log.md):

```sh
ctest --test-dir build/debug -R '^adaptive_(sssp|failure)$' --verbose
ctest --test-dir build/release -R '^adaptive_(sssp|failure)$' --verbose
ctest --test-dir build/debug -R '^adaptive_(sssp|failure)$' --repeat until-fail:20 --output-on-failure
```

For future evaluation, report forced baselines under the same shared_fast_path
configuration. Equal requests never execute a backend; strict no-effect bypasses
must not be counted as predicted strategy wins. execute_selected is a separately
labeled ablation: full strategies recompute, repair retains its intrinsic check.
Include graph copy, result scan, allocation, vector adoption, cleanup and future
selection costs in public-call latency. Every strategy must remain ready for the
next update. Kernel-only times are diagnostic, not service-level comparisons.
The engine has no timings, calibrated model, trace orchestration or speedup claim.
Phase 4B-2 heuristic validation is described below. Hosted CI for new changes is
distinct from local verification.

## Phase 4B-2 deterministic heuristic validation

The policy is an opt-in, uncalibrated hypothesis. Always policies and shared fast
paths remain baselines. Exact rules/reasons and defaults are documented in README
and architecture: E<=4096 selects Dijkstra, otherwise destination degree<=32
selects repair, otherwise E>=65536 and explicit requested workers>=2 selects delta,
otherwise repair. Thresholds are configurable, unsigned and immutable, with
small_graph_edges < parallel_min_edges checked at initialization. Defaults are
not crossover measurements. Requested workers 0 is unspecified, so does not
enable the parallel heuristic branch; forced delta still uses runtime defaults.
No environment/team query or automatic tuning changes selection.

Equal weights/shared no-effect requests bypass selection and backend execution.
When execution is required, a per-call override precedes the configured policy.
Always policies/overrides keep reason forced; automatic heuristic branches use
small_graph, local_degree, parallel_work or fallback. execute_selected applies
the same ordered heuristic to strict no-effect requests. Metrics capture the
decision made before execution; outcomes/costs never feed back into it.

Eleven explicit boundary configurations run on a verified E=7 graph with updated
destination degree 2: exact small/parallel thresholds and their neighbors, exact
degree threshold and its neighbor, precedence, workers 0/1/2/4 and uint64-scale
thresholds. Effective repeated decreases alternate with all forced backends and
resume automatic selection. Config and request rejection preserve state/metrics.
Existing fast-path tests now include heuristic as well as all fixed policies.

A new mt19937 stream with seed 0x4B22026 tests 72 graphs (1–12 vertices), every
source and 24 requests per nonempty graph/source. Families are sparse/dense random,
hub/fan-in and chains, with small/full-range weights and all six deltas. Small-edge
threshold is E for every fourth trial and 0 otherwise; parallel threshold is
small+1+(trial mod 3), with destination-degree and worker budgets varied. Both
no-effect modes and automatic/forced schedules are exercised. Three of four
requests use the configured heuristic, every fourth a cycling forced override;
every fifth request is unchanged, and every third reuses the previous edge.
Each accepted request runs paired measured/plain engines, checks exact decisions
and reason predicates, updates independent input records, and compares fresh
Dijkstra and small-graph Bellman–Ford. The older random stream and switching tests
remain intact. No current affected count is read by production selection.

Paired 512-vertex fixtures with E=511 and destination degree 1 produce the same
local_degree decision, but improve 2 versus 511 vertices. This establishes a
limitation of the features; it does not show which backend is faster. Keep such
adversarial examples distinct from later representative performance traces.

Failure tests now repeat all host-allocation sweeps under automatic selection
of each backend as well as forced execution. Successful traces compare allocation
count, size and pre/post-team placement with the same forced backend, in both
metrics modes. This checks that selection adds zero dynamic allocations; source
audit checks that metadata/degree work is bounded and has no traversal. No latency
measurement is inferred from those checks. Every fault preserves state/metrics,
then automatically retries and successfully switches to a forced strategy. Existing
OpenMP-safe coordinator/publication and initialization failures still run; the
sequential global injector is not used on workers. All four policies' shared
bypasses remain allocation-free.

Selection is deterministic for fixed pre-update state, immutable configuration and
override, independent of instrumentation and actual OpenMP scheduling. Parallel
latency, actual team size and some work counters can vary. Future performance
studies must include policy, staging and publication costs, retain shared-fast-path
fairness and held-out workloads, and test counterexamples/distribution shifts.
No calibrated model, online learning, benchmark orchestration or speedup evidence
is introduced by these correctness checks.

## Implemented Phase 2B validation and future measurements

Delta-stepping is an established algorithm, not a novelty claim. The new parallel
implementation is a full-recomputation baseline for future incremental repair and
adaptive-policy experiments. Keep sequential Dijkstra and fixed-delta/fixed-thread
parallel runs as separate baselines. Future policy evaluation needs held-out
workloads, selector cost, full query latency, and regret against measured fixed
alternatives. Avoid attributing parallel execution gains to incremental work
avoidance. No experiments or speedup measurements have been performed in Phase 2B.

The test-only synchronous Bellman–Ford oracle is shared between Dijkstra and delta
suites, still reads input records independently, and never calls production code.
Dijkstra retains 300 seeded graph trials (seed 0x51B2026) and now performs four
randomized in-place replacements per nonempty graph before recomputation.
Delta tests use mt19937 seed 0xD317A202, 70 graphs with 1–12 vertices, alternating
dense/sparse sampling, and small or full uint32 weight distributions. Every source
is compared with both oracles across delta {1,2,3,16,UINT32_MAX,UINT64_MAX} and
requested threads {1,2}, with/without metrics. Four in-place replacements per
nonempty random graph alternate zero/max weights; each is checked across all six
deltas with two requested threads. Graph arrays are checked for immutability.

Hand fixtures cover zero cycles, self-loops, isolation, equal paths, exact delta
boundaries, same-bucket repeated improvement, and final-label heavy scans. A
800-vertex hub/fan-in graph exercises 256-edge row chunks and contention over 60
repetitions. Two async host calls each perform 15 independent queries (instrumented
and uninstrumented) on one immutable graph. A 2,000-vertex max-weight chain is
checked at every delta. Selected four-thread requests test oversubscription;
tests print actual team size. A two-thread fixture requires actual participation
by two threads. Default-thread options and CLI metadata are tested separately.

An isolated test executable overrides C++ allocation only for fault injection.
It fails a scheduling-buffer append after CAS, then sweeps allocation positions
1–45 on each of two selected OpenMP threads. Failed queries must throw bad_alloc,
not hang or return partial results; fresh queries must recover. Injection state
is confined to that executable; production has no global hooks. It does not
simulate every allocator/runtime/OS failure. CTest timeouts bound stress/failure
runs. The previous divergent failure-exit bug is documented in architecture.md.

Useful development commands (full verification record in research-log.md):

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --preset debug --output-on-failure
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release --output-on-failure
ctest --test-dir build/debug -R '^(delta_stepping|delta_failure)$' --repeat until-fail:20 --output-on-failure
```

CTest sets OMP_NUM_THREADS=2 and OMP_DYNAMIC=FALSE for parallel checks, allowing
up to eight threads for selected oversubscription/concurrent calls and two for
fault injection. These are correctness checks on a two-logical-CPU host, not
scaling evidence. Repeat races/stress at 4/8/higher actual threads on dedicated
multicore hardware before claiming scaling. Preserve actual/requested team sizes,
delta, source, seed, revision/dirty state, build flags, OpenMP runtime, affinity,
CPU/memory topology, input checksums, update traces, and raw observations.

Phase 5C-2B adds test-only concurrency validation; see
[validation-concurrency.md](validation-concurrency.md). Its direct fast/stress/
extended counts are exactly 288/5760/57600, using eight workload families and
explicitly defined extended variants. Default CTest includes fast only. Runtime
subprocesses distinguish worker requests from measured actual teams; unmeasured
teams and unsupported adaptive per-thread work remain unavailable. Independent
clients share only immutable graph data or own separate engines. Every access to
one shared adaptive engine, including inspection, is protected by one mutex.
No concurrent graph mutation, scheduling change or production fault hook is added.

ASan/UBSan CI runs the entire default suite. LeakSanitizer needs process-inspection
support and can fail under the local sandbox. Phase 5C-2A freshly rebuilt GCC
ThreadSanitizer reproduced a work_ warning and also flagged correctly synchronized
OpenMP barrier controls. Intentional-race/atomic controls, an additional address
layout and complete warning stacks supported LIKELY TOOL/RUNTIME LIMITATION for
that specific warning. Many startup mapping failures persisted outside the sandbox.
Later warnings are retained; no clean race-detector result is claimed, and its
acceptance gate remains unmet. Clang/libomp/Archer was unavailable; installed
Helgrind also failed negative-control calibration. ASan/UBSan and
stress tests do not prove race freedom; barrier/ownership review remains required.
Compatible OpenMP-aware race tooling should be evaluated on suitable hardware.

Later measurements must separate team startup, label initialization/result copy,
light/heavy scans, coordinator map/merge work, and barrier waiting where measurable.
Count CSR inspections as well as matching-class relaxation attempts to expose
filtering and repeated scans. Record successful CAS and retries and per-thread
work imbalance. Match instrumentation modes; the parallel CLI currently enables
metrics to report actual team size, so use the library without metrics for
uninstrumented comparisons. Do not equate summed thread waiting with wall time.

Phase 5C-2C adds isolated repeated coordinator/publication/merge failure profiles
and bounded subprocess recovery checks; see [validation-parallel-failure.md](validation-parallel-failure.md).
These checks do not satisfy the outstanding race-detector acceptance gate.

The 5C-2C verification gate repair restored four analysis registrations lost to a
stale interpreter cache. With the exact pinned project-local .venv-analysis,
Debug, Release and ASan+UBSan each passed the complete 31-test default suite in
sequential runs. Historical 27-test results and the original sanitizer timeout
remain retained; see validation-parallel-failure.md and research-log.md for exact
commands, outcomes and limitations. Race-detector acceptance remains unmet.

## Phase 6B-2B-3A runtime evidence qualification

The [runtime provenance runbook](runtime-provenance.md) distinguishes requested
configuration, observed process configuration, observed OpenMP execution and
scientific admission. Child PID/start identity, executable digest, affinity,
visible quotas/cpusets and mapped libgomp are snapshots with explicit sources,
intervals and scopes. Observer hardware topology/NUMA and compiler/build context
must not be relabelled as workload-region observations. Teams and region counts
remain unavailable because timed metrics are disabled. C++ timing definitions
and algorithms are unchanged. Pilot/resume measurement_eligible remains false.
Environment variables do not prove teams; teams do not prove physical-core
exclusivity; affinity does not prove uncontended execution. GitHub Actions
runners do not establish exclusive physical cores, and the current Codespace
cannot support credible multicore scaling conclusions. Hashed evidence is not
authenticated evidence. No automatic admission or scientific execution is added.

## Phase 6B-2B-3B-1 resource-control and admission contracts

This phase adds read-only assessment contracts, not a resource enforcer. Existing
pilot v2, journal v1, resume v1, runtime provenance v1 and hardware v2 remain
unchanged. Existing campaign-admission v2 remains a separate legacy qualification
interface; this new assessment does not turn that interface into enforcement or
execution authority. All pilot/resume results remain measurement-ineligible.

The new standard-library module `campaign_resources.py` defines four closed
schemas, each with an exact integer `schema_version=1`:

| Schema | Content |
| --- | --- |
| `dynagraph-resource-controls` | Execution/trial/process binding, evidence references, requested settings, requirements, application receipt and observations |
| `dynagraph-affinity-application` | Optional supplied syscall receipt: process binding, requested/applied CPU arrays, outcome, errno, mechanism, timestamp, source and scope |
| `dynagraph-resource-admission` | Deterministic state, reason codes and evidence digests, controls SHA-256, assessment ID, limitations and immutable transition policy |
| `dynagraph-resource-assessment` | Envelope containing controls and the recomputable decision |

The trusted expected context is rebuilt from an independently verified pilot,
not taken from the sidecar. It binds execution content identity, canonical journal
binding digest, deterministic trial ID, process index, executable SHA-256 and,
when the runtime snapshot matched that executable, child PID/start ticks. Fixed
relative references with SHA-256 identify plan, manifest, execution, hardware,
trial record and optional per-process runtime record. No sidecar reference selects
an executable or controls filesystem traversal. Original and resumed trials retain
their existing execution/origin identities. Before/after bounded inventories reject
evidence mutation during inspection; they are not atomic filesystem attestation.

### Requested, applied and observed distinctions

`request` carries the original plan affinity, requested workers/OpenMP environment,
minimum physical cores and SMT policy. A request alone is never an application
receipt. `application` defaults to `{state: not_attempted, cpus: null, receipt:
null}`. Other states are `unavailable`, `failed` and `applied`. The first two have
no receipt or applied CPU array. `failed` requires a matching supplied failure
receipt with positive errno and no applied array. `applied` requires a matching
supplied success receipt, errno zero, and sorted unique applied CPUs exactly equal
to the requested set. Only `sched_setaffinity` receipt syntax is currently defined;
no such syscall is performed by this phase. Receipt time is within the process
interval and no later than the effective-affinity observation when that interval
is known. An interpreter/unmatched executable cannot acquire a receipt binding.

Application receipts are supplied claims whose consistency is validated, not
independent proof that the syscall occurred. There is no trusted receipt producer
in this phase. Application and later effective affinity remain separate facts;
an observed mismatch is a failed alignment requirement, not proof of stability.

Every observation has `value`, `status` (`observed`/`unavailable`), `source`,
`scope`, supporting reference and `start`/`end`. Both times are null when the old
source has no collection interval; no timestamp is fabricated. Observations cover:

- Child leader effective affinity; observer-namespace online/visible CPU IDs.
- Raw visible child cgroup2 ancestry, effective cpuset and rational quota pairs;
  `max` means no finite quota in those visible records, not unlimited host resources.
- Earlier observer physical-core/SMT topology and optional NUMA locality. They are
  not synchronized worker placement or physical ownership observations.
- Workload-region OpenMP teams, exclusivity, uncontended execution and isolation:
  explicitly unavailable. This schema rejects supplied positive or negative
  guarantees for those unsupported evidence categories, including invented teams.

Source provenance is preserved. A missing child snapshot or legacy pilot does not
inherit the observer's affinity as child affinity. Runtime mappings do not prove
OpenMP execution. Affinity, quota, cpusets and CPU counts never prove exclusivity.
Contract validation does not prove physical resource isolation.

### Decision model, evidence requirements and reason codes

The requirements map has exact boolean keys: `applied_affinity`,
`observed_affinity`, `online_cpus`, `cpuset`, `quota`, `topology`, `numa`,
`openmp_team`, `exclusivity`, `uncontended`, `isolation`. Development assessment
defaults to none of these quality requirements; they may be explicitly requested.
Scientific assessment requires all of them and rejects policy weakening.
The already verified trial must have a verified completion for every assessment
purpose. `trial_success` is true for a verified completion, false for a terminal
failure/interruption, and null for an indeterminate journal outcome. Successful
output without a committed terminal transition remains indeterminate.

| State | Meaning in v1 |
| --- | --- |
| `rejected` | Trial failed, or a required condition is known to fail; takes precedence over missing evidence |
| `indeterminate` | No known required failure, but required evidence is unavailable, unsupported or incomplete |
| `development_only` | Functional evidence and selected requirements pass; the phase cap still prohibits scientific measurement |
| `eligible` | Reserved for a future contract; never emitted and always rejected if supplied in v1 |

All decisions set `measurement_eligible=false`,
`scientific_performance_allowed=false` and `execution_authorized=false`, including
successful functional assessments. Valid record verification exits zero even for
a correctly computed rejected/indeterminate decision; malformed or inconsistent
evidence exits 2. No assessment grants permission to launch or resume anything.

Reason codes are deterministic: `TRIAL_NOT_SUCCESSFUL`,
`TRIAL_COMPLETION_UNAVAILABLE`; prefixes
`AFFINITY_APPLICATION`, `AFFINITY_MATCH`, `ONLINE_CPUS`, `CPUSET`, `CPU_QUOTA`,
`PHYSICAL_CORES`, `NUMA_LOCALITY` with `_FAILED` or `_UNAVAILABLE`; and
`OPENMP_TEAM_UNAVAILABLE`, `EXCLUSIVITY_UNAVAILABLE`, `UNCONTENDED_UNAVAILABLE`,
`ISOLATION_UNAVAILABLE`. Every decision includes `SCIENTIFIC_ADMISSION_DISABLED`.
Each reason records failure/unknown/phase-limit outcome and a bounded local
`controls#/...` evidence pointer with canonical SHA-256. The controls' fixed file
references bind those facts to the verified source evidence.

Known failures include requested/observed affinity mismatch, allocation outside
observed online CPUs or visible cpuset, any ancestor quota below requested workers,
insufficient physical cores or forbidden SMT sharing, and requested single-node
NUMA locality failing. Missing topology/coverage or NUMA remains indeterminate
when required. Malformed supplied facts are errors, even when not required.

`immutable-assessment-v1` permits only initial assessment or exact idempotent
reverification with `--previous`. Any changed controls, reasons, identities or
state reject as a transition. New evidence requires a separate assessment; this
phase implements no automatic promotion or mutable admission history. Reserved
scientific transitions need a future version and independently satisfied controls.

### Read-only runbook and deferred enforcement

Keep sidecars outside original pilot directories, whose inventory remains exact:

```sh
python3 -B benchmarks/python/campaign.py inspect-resources \
  --output PILOT --trial-id TRIAL_ID --process-index 0 > /tmp/resources.json
python3 -B benchmarks/python/campaign.py verify-resources \
  --output PILOT --trial-id TRIAL_ID --process-index 0 --evidence /tmp/resources.json
```

`inspect-resources --purpose scientific` assesses evidence gaps without executing
a scientific trial. `verify-resources --previous /tmp/resources.json` additionally
checks idempotence. Completed prefixes in an interrupted journal pilot are
inspectable; pending trials without a receipt are not resource assessments. Legacy
final pilots use the existing full v2 gate. Resumed pilots use their own verified
execution. No old bytes, admission flags, journal transitions or launch deadlines
are rewritten. Sidecar verification is read-only and never executes an archived
runner. Run new controls with `python3 -B tests/test_campaign_resources.py`.

Linux namespaces, visible cgroup mounts, hardware virtualization, unsynchronized
snapshots and unauthenticated producers limit interpretation. Hidden restrictions,
contention and exclusive physical ownership remain unverified. Deferred
Phase 6B-2B-3B-2 work includes designing/implementing a bounded nonprivileged
enforcement lifecycle and trusted application receipts, stability/placement
observations and separate OpenMP workload instrumentation contracts. Privileged
resource operations, isolation guarantees, scientific execution/admission,
performance claims, retries and TSan acceptance remain outside this phase.
