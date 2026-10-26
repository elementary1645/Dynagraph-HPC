# Research log

## 2026-10-26 — Phase 1B sequential SSSP

The attached Phase 1B request explicitly authorized this phase beyond the older
Phase 1A gate. Updated AGENTS.md to reflect that authorization and retain the
next gate. No dependencies were installed, no agents delegated, and no commits
or pushes were made. Existing working-tree files were preserved.

Implemented the reusable SSSPResult/Distance/infinity API, binary-heap Dijkstra,
optional separately stored work metrics, and strict SSSP JSON CLI integration.
Predecessors are omitted pending a concrete path or repair contract. The public
API accepts an optional metric pointer; a template specialization eliminates
per-event instrumentation when omitted. The graph remains const during queries.
Architecture documents the type-bound overflow proof, deterministic heap ties,
lazy duplicates, complexity, and all metric definitions. README specifies JSON
schema v1, exact integer consumption, CLI behavior, and examples.

Added independent synchronous Bellman–Ford over input edge records, 300 seeded
random differential graph trials (all sources, sparse/dense, zero/full-range
weights, plus decreases/increases), hand-checked edge cases, a 10,000-vertex chain,
repeatability, graph immutability, and counter identities. CLI integration checks
exact output including distances above uint32 and unreachable null, paths with
spaces, invalid/duplicate/missing options, source bounds, absent and malformed
files, and empty graphs. No production correctness bugs were discovered.

### Exact verification commands and outcomes

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --preset debug --output-on-failure
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release --output-on-failure
cmake -S . -B build/sanitize -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined
cmake --build build/sanitize --parallel 2
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir build/sanitize --output-on-failure
git diff --check
```

Debug and Release each passed all 10 CTest entries: project_info, openmp,
csr_graph, edge_list_io, dijkstra, cli_launch, cli_help, cli_version,
cli_invalid_argument, and cli_sssp. Builds were warning-free under the unchanged
-Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror settings. The first Debug
run preceded CLI integration and passed all 9 then-registered tests; the complete
10-test suite was then run in both configurations. GCC 13.3.0/CMake 3.28.3 and
OpenMP 4.5 remain the toolchain.

The first sanitizer invocation failed because LeakSanitizer cannot inspect
processes under the sandbox's ptrace restrictions. After approval, the exact
instrumented CTest invocation ran outside the sandbox: all 10 tests passed with
leak detection enabled and no ASan/UBSan findings. No test was disabled or weakened.
Whitespace verification passed. CLI integration executed representative wide,
zero-weight/self-loop, and disconnected graph input and checked exact JSON:

```json
{"schema_version":1,"algorithm":"dijkstra","source":0,"distances":[0,4294967295,8589934590,0,null]}
```

### Changed files and phase gate

Created include/dynagraph/algorithms/sssp.hpp, src/algorithms/dijkstra.cpp,
tests/test_dijkstra.cpp, and tests/test_cli_sssp.cmake. Modified AGENTS.md,
CMakeLists.txt, apps/dynagraph_cli.cpp, tests/CMakeLists.txt, README.md,
docs/architecture.md, docs/experimental-protocol.md, and docs/research-log.md.

No unresolved local correctness, build, warning, or sanitizer failures. Maximum
representable graphs are proven arithmetically but have not been allocated;
capacity remains RAM-dependent and the lazy heap can consume O(E) space. Queries
require externally serialized mutation. JSON consumers must preserve uint64
integer precision. Hosted CI is unrun; there are no benchmark measurements or
speedup claims. This is a recomputation baseline, not an incremental algorithm.

Phase 1B is complete. Stop and await explicit approval. Proposed Phase 2:
specify and validate parallel delta-stepping buckets, arithmetic, synchronization,
and comparable counters against sequential Dijkstra plus the independent oracle
before performance experiments. Incremental repair and adaptive selection remain
separately gated.

## 2026-10-26 — Phase 1A fixed-topology CSR storage

### Authorization and design

The user authorized CSR storage, serial weight replacement, strict text input,
tests, and documentation. AGENTS.md now records the Phase 1A gate. All shortest-
path algorithms, parallel mutation, topology changes, and adaptive policies remain
out of scope. No dependencies were installed; no commits or pushes were made.

Added CSRGraph with uint32_t destinations/weights, uint64_t offsets, immutable
topology, signed validated edge-list inputs, deterministic source/destination
sorting, duplicate rejection, binary-search lookup, and weight replacement that
returns the prior value. Storage replacement accepts all valid weights; this does
not implement incremental handling of weight increases. Counts are checked against
type, byte-allocation, and vector bounds before graph allocation. Input lists can
be moved into the builder. Copies own their arrays, and moved-from objects remain
valid empty graphs.

Added stream/file loading of zero-based V E headers and exactly E triples. The
loader checks unsigned-decimal syntax, numeric overflow, record counts, endpoint
and weight bounds, duplicates, and I/O failures. Errors include line numbers where
applicable and file paths for file loading. See architecture.md for full semantics,
resource limits, iterator lifetimes, complexities, and format examples.

The CLI retains its existing options and exit behavior, with status text updated
to reflect library CSR availability. Existing presets and GitHub Actions workflow
were preserved; their normal test invocations automatically include the new tests.

### Verification commands

Executed from the repository root:

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --preset debug --output-on-failure
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release --output-on-failure
./build/debug/dynagraph_cli
ctest --test-dir build/debug -R '^(csr_graph|edge_list_io|openmp)$' --verbose

cmake -S . -B build/sanitize -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined
cmake --build build/sanitize --parallel 2
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir build/sanitize --output-on-failure
```

### Actual outcomes

- GCC 13.3.0, CMake 3.28.3, OpenMP 4.5; Debug and Release builds succeeded.
- Final builds emitted no compiler warnings with -Wall -Wextra -Wpedantic
  -Wconversion -Wshadow -Werror.
- All 8 CTest tests passed in Debug and Release. The new graph executable runs
  five test groups; the loader executable runs three test groups.
- Coverage includes empty/single/isolated vertices, directed and disconnected
  graphs, self-loops, zero/max weights, duplicate rejection, invalid endpoints,
  negative/out-of-range weights, numeric/allocation-size overflow checks, exact
  offsets, deterministic ordering, iteration, serial updates, failed-update
  preservation, copy/move invariants, malformed files, and simulated read failures.
- Exhaustively checked 120 input permutations of a five-edge graph. Randomized
  tests checked 250 small graphs and weight replacements against an independent
  ordered-map oracle, using mt19937 seed 0xD1A6A123 and explicit Fisher-Yates shuffling.
- CLI launches successfully. OpenMP smoke output remains:
  `OpenMP 201511; team_size=2; participants=2; thread_id_sum=1`.
- All 8 sanitizer tests passed with AddressSanitizer, UndefinedBehaviorSanitizer,
  and leak detection enabled, without sanitizer findings.

The first Debug build identified two test-code warnings: an intentional explicit
self-move and an implicit PRNG result conversion. Both were corrected without
disabling warnings; self-move behavior remains tested through a two-reference
assignment helper. The first sanitizer run failed because LeakSanitizer could not
inspect processes inside the sandbox (ptrace restriction). After permission, the
same instrumented suite ran outside the sandbox and passed with leak detection
enabled; the final suite was rebuilt and verified there after the last test edit.

### Limitations and phase gate

No unresolved build, correctness-test, or sanitizer failures. Maximum-sized graphs
have not been allocated; practical capacity depends on available RAM and allocator
limits. Loading has no line-length/input-size quota. Mutation requires external
serialization. Hosted CI has not run because nothing was pushed. No performance
benchmarks or speedup claims were produced.

Phase 1A is complete. Stop and await approval. Recommended Phase 1B: specify
distance/infinity/overflow and source/result semantics, implement sequential
Dijkstra using the CSR API, and validate hand-checked and deterministic randomized
cases against an independent small-graph oracle. Keep parallel algorithms,
incremental repair, and adaptive policies behind subsequent gates.

## 2026-10-26 — Phase 0 foundation

Approved scope: C++17/OpenMP/CMake with Python benchmarking later; directed,
fixed-topology graphs; nonnegative integer weights; decrease-only updates first.
CSR, all shortest-path algorithms, incremental repair, and adaptive selection
remain outside Phase 0.

Implemented the library/CLI build, GCC presets, dependency-free CTest harness,
two-thread OpenMP smoke test, CI definition, modular directory placeholders, and
engineering/reproduction documentation. No third-party dependencies were added.

### Local verification

Environment: Ubuntu 24.04.5 LTS, x86-64, GCC 13.3.0, CMake 3.28.3. The host
reports two logical CPUs. CMake detected OpenMP CXX 4.5 with -fopenmp.

Commands executed from the repository root:

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --preset debug
./build/debug/dynagraph_cli
./build/debug/dynagraph_cli --version
ctest --test-dir build/debug -R '^openmp$' --verbose
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release
ldd build/debug/tests/test_openmp
git diff --check
git check-ignore build/debug/CMakeCache.txt data/generated/example.graph results/raw/run.json
```

- Debug and Release configure/build succeeded; all four targets built in each:
  dynagraph, dynagraph_cli, test_project_info, and test_openmp.
- No compiler warnings were emitted with -Wall -Wextra -Wpedantic -Wconversion
  -Wshadow -Werror. Generated flags confirmed -std=c++17 and -fopenmp in both
  builds; Release also used -O3 -DNDEBUG.
- All six CTest tests passed in each configuration: project_info, openmp,
  cli_launch, cli_help, cli_version, and cli_invalid_argument.
- Verbose OpenMP output: `OpenMP 201511; team_size=2; participants=2; thread_id_sum=1`.
  Dynamic linking inspection resolved libgomp.so.1 with no missing libraries.
- CLI launch printed Phase 0 usage; --version printed
  `DynaGraph-HPC 0.1.0 (OpenMP 201511)`.
- Whitespace checks passed. Ignore checks confirmed build products, generated
  data, and raw result paths are excluded; check-ignore used hypothetical data
  and result paths and did not generate datasets or benchmark observations.

### Limitations and phase gate

No unresolved local build or test failures. The GitHub Actions definition has
not run on hosted infrastructure; no commits or pushes were made. No dependencies
were installed. These checks establish functionality only, not performance.

Phase 0 implementation is complete. Await approval before Phase 1. Recommended
next scope: settle graph type/range and input semantics, implement simple CSR
with fixed topology and mutable nonnegative weights, and validate storage
invariants and deterministic fixtures. Dijkstra remains a subsequent gated step.
