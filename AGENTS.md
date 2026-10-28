# DynaGraph-HPC engineering standards

## Authorization and phase gates

- Current authorized scope: Phase 5C-2B parallel and concurrency stress validation,
  explicitly approved after Phase 5C-2A investigation. Extend tests, registration and docs only;
  preserve production algorithms, graph semantics, APIs, heuristic and timing.
- Stop after Phase 5C-2B implementation/testing for independent source review.
  The race-detector acceptance gate remains unmet: the specific work_ TSan report
  was classified LIKELY TOOL/RUNTIME LIMITATION after calibration, not race freedom.
  Preserve tests/tsan_controls and ignored results/validation/phase5c2a* evidence;
  intentional-race controls must stay outside ordinary CTest and CI.
  Inferential statistics, performance claims, heuristic tuning, calibrated/learned
  selection, batch/increase/parallel repair, automatic delta tuning, topology changes
  and concurrent mutation remain deferred. Phase 5B-4B descriptive analysis is merged.
- Do not install dependencies, commit, or push without explicit user permission.
- No sub-agent delegation is required by this repository.

## Scope constraints

- Use C++17, OpenMP, CMake, and Python for benchmark orchestration.
- Initial graphs are directed with fixed vertices and topology, and nonnegative
  integer weights. Prioritize weight decreases.
- The storage API may replace a weight with any supported nonnegative value;
  incremental processing of increases remains deferred, along with insertions,
  deletions, tombstones, and CSR compaction.
- Sequential Dijkstra is the reference. Validate it before implementing parallel
  delta-stepping. Validate individual algorithms before adaptive selection.
- Graph updates occur between completed queries; concurrent mutation is deferred.
- Independent callers may query one immutable graph or own separate engines.
  All access to one shared adaptive engine, including inspection, requires external
  serialization. Record observed OpenMP teams separately from worker requests.

## Engineering standards

- Keep public headers under include/dynagraph and implementation under src.
- Keep CLI parsing, algorithms, graph storage, and experiment orchestration separate.
- Prefer the standard library; justify new dependencies before requesting installation.
- Link OpenMP through OpenMP::OpenMP_CXX; use target-scoped CMake settings.
- Keep warnings clean under -Wall -Wextra -Wpedantic -Wconversion -Wshadow.
- Define input validation, integer overflow handling, unreachable distances, and
  synchronization semantics before implementing the relevant algorithms.
- Use RAII and explicit ownership. Avoid global mutable state and platform-specific
  intrinsics without measured justification and a portable path.

## Verification and research integrity

- Build and run CTest in Debug and Release when changing shared build infrastructure.
- Tests must remain effective with NDEBUG; use the small tests/test_support.hpp
  harness and CTest unless a later approved phase needs more infrastructure.
- Add meaningful correctness tests as functionality is introduced; check dynamic
  results against full recomputation and use an independent small-graph oracle.
- Do not invent measurements or claim speedups before controlled experiments.
- Preserve dataset provenance, seeds, update traces, configurations, compiler and
  hardware metadata, and raw results. Keep large generated artifacts out of Git.
- Record actual commands, outcomes, limitations, and scope changes in docs.
- Before each phase gate, report changed files, verification results, unresolved
  issues, and the next proposed phase. Stop and wait for approval.
