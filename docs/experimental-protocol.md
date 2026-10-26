# Experimental protocol

## Status

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

ASan/UBSan CI now runs the entire suite. LeakSanitizer needs process-inspection
support and can fail under the local sandbox. GCC ThreadSanitizer was investigated
but failed before test execution with an unexpected-memory-mapping error, including
outside the sandbox. No clean race-detector result is claimed. ASan/UBSan and
stress tests do not prove race freedom; barrier/ownership review remains required.
Compatible OpenMP-aware race tooling should be evaluated on suitable hardware.

Later measurements must separate team startup, label initialization/result copy,
light/heavy scans, coordinator map/merge work, and barrier waiting where measurable.
Count CSR inspections as well as matching-class relaxation attempts to expose
filtering and repeated scans. Record successful CAS and retries and per-thread
work imbalance. Match instrumentation modes; the parallel CLI currently enables
metrics to report actual team size, so use the library without metrics for
uninstrumented comparisons. Do not equate summed thread waiting with wall time.
