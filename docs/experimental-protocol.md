# Experimental protocol

## Status

This is a prospective measurement protocol. Phases 1B and 2B provide verified
sequential and parallel recomputation baselines but no benchmark results or speedup claims.
The OpenMP smoke test verifies functionality, not performance.

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
below. Scaling studies, incremental repair, and adaptive selection need separate
approval and independent validation.


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
