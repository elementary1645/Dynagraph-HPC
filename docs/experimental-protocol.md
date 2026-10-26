# Experimental protocol

## Status

This is a prospective measurement protocol. Phase 1B provides a verified
sequential recomputation baseline but no benchmark results or speedup claims.
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

Proposed Phase 2: first settle delta-stepping distance arithmetic, bucket bounds,
work counters, synchronization and reproducibility; validate against this baseline
and the independent oracle before scaling studies. Incremental repair and adaptive
selection need separate approval and independent validation after that.
