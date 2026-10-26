# Research log

## 2026-10-26 — Phase 2B final verification gate after Codespace restart

Inspected all 11 modified tracked files and five untracked Phase 2B files against
HEAD 9d6da7e on main. No algorithm, API, test, build, or workflow code was changed
in this verification. Corrected one low-severity stale sentence in architecture.md
(formerly line 227) that still called parallel algorithms future work. This entry
records the new verification; earlier entries describe earlier runs, not new evidence.
No dependencies installed, source files discarded, commits, pushes, or Phase 3 work.

### Code audit

No correctness or concurrency defect identified. References below are to the
unchanged src/algorithms/delta_stepping.cpp:

- Lines 185–201: checked cap subtraction/addition and strict atomic minimum.
  compare_exchange_weak updates the expected value on failure, retries spurious
  failures, and stops when a competing label is already no greater. Every success
  appends its label to the executing worker's buffer. An append failure after CAS
  aborts the whole query rather than returning a distance with unpublished work.
- Lines 138–162 and 205–211: stale entries are filtered both at merge and bucket
  extraction. Monotone labels preserve a record for the final winning improvement;
  superseded records need not be scanned. Membership deduplicates only the heavy
  list, so same-bucket improvements still receive repeated light passes.
- Lines 164–173: heavy work is prepared only after light closure, with labels loaded
  at that quiescent boundary and one heavy scan per distinct settled vertex.
- Lines 39–41, 54–80, 177–211: fixed outer thread-state storage, exclusive worker
  update/metric/error slots, and coordinator-only bucket/work-container changes.
  The single coordinator role can change threads; implicit barriers transfer
  ownership. Relaxed distance atomics carry no ordinary payload; barriers publish
  ordinary work, buffers, flags, and exception state.
- Lines 58–86: throwing work is caught on its executing thread, workers still reach
  the worksharing barrier, failures are inspected before merge, and the next single
  publication barrier precedes the collective exit decision. No old post-merge
  decision remains. Result copying/rethrow occurs after the parallel region.
- Lines 38, 183–186, 237–246: source validation excludes empty graphs before V-1;
  L=(V-1)*UINT32_MAX fits uint64 below infinity, finite labels remain <=L, and
  division uses validated positive delta. Delta UINT64_MAX needs no multiplication
  or dense bucket allocation. Strict improvements terminate zero-weight cycles.
- All query state is call-owned. Graph access is const, and no OpenMP global
  settings are changed. Concurrent independent queries use distinct metrics and
  state; graph mutation, assignment, movement, or destruction requires external
  synchronization against every query.

Reviewed CLI parsing/output, test oracle extraction and replacement tests,
warning flags, CTest environments/timeouts, documentation, and CI. No warning
settings were weakened and no tests were skipped. The existing harness remains
active under NDEBUG. Essential requested coverage was already present, so no tests
were added. The push/pull_request/workflow_dispatch workflow runs both presets
and a separate full ASan/UBSan suite with leak detection; hosted execution of
these uncommitted changes is unverified.

### Exact fresh-build commands and outcomes

Created a new directory with `mktemp -d /tmp/dynagraph-phase2b-gate-XXXXXX`, which
returned /tmp/dynagraph-phase2b-gate-8Sry8N. Commands below ran from the repository
root. All targets were compiled from scratch in three separate build directories.
Environment: GCC 13.3.0, CMake 3.28.3, OpenMP 4.5, two logical CPUs.

```sh
cmake -S . -B /tmp/dynagraph-phase2b-gate-8Sry8N/debug -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON
cmake --build /tmp/dynagraph-phase2b-gate-8Sry8N/debug --parallel 2
ctest --test-dir /tmp/dynagraph-phase2b-gate-8Sry8N/debug --output-on-failure
cmake -S . -B /tmp/dynagraph-phase2b-gate-8Sry8N/release -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON
cmake --build /tmp/dynagraph-phase2b-gate-8Sry8N/release --parallel 2
ctest --test-dir /tmp/dynagraph-phase2b-gate-8Sry8N/release --output-on-failure
cmake -S . -B /tmp/dynagraph-phase2b-gate-8Sry8N/sanitize -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined
cmake --build /tmp/dynagraph-phase2b-gate-8Sry8N/sanitize --parallel 2
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir /tmp/dynagraph-phase2b-gate-8Sry8N/sanitize --output-on-failure
ctest --test-dir /tmp/dynagraph-phase2b-gate-8Sry8N/debug -R '^(delta_stepping|delta_failure)$' --repeat until-fail:20 --output-on-failure
ctest --test-dir /tmp/dynagraph-phase2b-gate-8Sry8N/debug -R '^(delta_stepping|delta_failure)$' --verbose
git diff --check
```

All three configure/build runs succeeded without warnings. Generated flags retain
-Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror, -std=c++17, and -fopenmp;
Release also has -O3 -DNDEBUG; sanitizer has both requested instruments.
Debug passed 12/12 (5.65 s); Release passed 12/12 (9.36 s). These CTest elapsed
times are verification observations under shared host load, not benchmarks.

The initial sanitizer CTest command inside the sandbox exited 8: 11/12 tests
failed with `LeakSanitizer has encountered a fatal error` and
`LeakSanitizer does not work under ptrace (strace, gdb, etc)`. The negative CLI
test alone reported success; that is not evidence of a healthy sanitizer run.
With approval, reran the identical sanitizer CTest command outside the sandbox:
12/12 passed (6.62 s), leak detection enabled, no ASan/UBSan/leak findings or
timeouts. The sandbox failures were environmental, not reported memory defects.
Full CTest logs remain in each temporary build's Testing/Temporary directory.

### Stress coverage, results, and limitations

Both delta_stepping and delta_failure passed 20 consecutive Debug repetitions,
40 executions total (51.90 s). A subsequent verbose run passed both tests,
confirmed requested 4 / actual 4 threads, and reported 63 bad_alloc exceptions in
the 90-position allocation sweep, in addition to the separate post-CAS failure.
Triggered positions vary with scheduling; every failed query must allow a fresh
query to recover. No timeout or mismatch was observed.

Coverage confirmed in tests/test_delta_stepping.cpp: six deltas at line 13;
threads 1/2 and independent Dijkstra/Bellman–Ford comparison at lines 40–53;
zero cycles at lines 76–77; repeated closure and final-label heavy-edge regression
at lines 79–88; stale future records at lines 89–91; runtime-default and selective
four-thread repetitions at lines 92–99; 70 seeded randomized graphs with in-place
updates at lines 102–125; 800-vertex hub/fan-in contention, 60 repetitions, two
independent async queries, and max-weight chains at lines 129–153. Instrumented
and uninstrumented results are compared. tests/test_delta_failure.cpp lines 52–94
cover post-CAS publication failure, both team-thread allocation sweeps, and recovery.
CLI integration covers all six deltas with threads 0/1/2. Dijkstra's separate suite
retains 300 seeded trials and independent input-record Bellman–Ford validation.

No current blocking defect found; Phase 2B is ready for a user-authorized commit.
No race-detector pass is claimed: prior TSan failed during startup, and was not
rerun here. ASan/UBSan and stress success do not prove race freedom. External
serialization of mutation and separate metric objects for concurrent calls remain
caller obligations. OpenMP runtime/OS team-creation failures are outside the C++
allocation fault sweep; four-thread correctness on two CPUs is not scaling
evidence. Large-machine validation and compatible OpenMP-aware race tooling remain
future verification needs. Stop at this gate and await approval; no Phase 3 work.

## 2026-10-26 — Phase 2B parallel delta-stepping

### Authorization, implementation, and audit corrections

The attached Phase 2B request explicitly approved implementation following the
Phase 2A read-only design. Updated AGENTS.md to record this scope and the Phase 3
gate. No dependencies were installed, no sub-agents used, and nothing was committed
or pushed. The working tree was clean before this phase.

Added DeltaSteppingOptions/DeltaSteppingMetrics and the parallel algorithm,
returning the existing SSSPResult. Sequential Dijkstra implementation and its API
were preserved. Each query owns one persistent OpenMP team, atomic labels,
per-thread updates/metrics/exceptions, a coordinator-owned sparse bucket map,
heavy-list membership bytes, and immutable work descriptors splitting rows into
256-edge chunks. Light closure allows repeated processing; heavy scans use final
labels once per distinct vertex. Checked cap-based arithmetic preserves all finite
shortest distances and supports delta UINT64_MAX. The caller serializes graph
mutation against all queries. Optional instrumentation compiles out event updates.

CLI adds --algorithm delta-stepping --delta N [--threads N], reporting requested
and actual team sizes with the existing distance/infinity JSON representation.
Dijkstra JSON remains byte-for-byte compatible in integration tests. Parallel CLI
runs enable metrics to obtain actual team size, so they are not uninstrumented
kernel measurements. No timing or work counters are emitted in JSON.

Addressed all Phase 2A audit corrections: ASan/UBSan CI job, outdated phase text,
randomized in-place weight replacements with recomputation, and an explicit empty
source argument test that preserves the argv element. The independent test-only
Bellman–Ford was extracted for use by both algorithm suites. Architecture and
experimental protocol now define invariants, ownership, barriers, failures,
metrics, reproducibility, and limitations.

### Verification commands

Executed from the repository root (builds were repeated after the failure-path
correction below):

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

ctest --test-dir build/debug -R '^(delta_stepping|delta_failure)$' --repeat until-fail:20 --output-on-failure

OMP_NUM_THREADS=2 OMP_DYNAMIC=FALSE ./build/debug/dynagraph_cli sssp --input 'build/debug/tests/cli_sssp/graph with spaces.txt' --source 0 --algorithm delta-stepping --delta 16 --threads 2
./build/debug/dynagraph_cli sssp --input 'build/debug/tests/cli_sssp/graph with spaces.txt' --source 0 --algorithm dijkstra
git diff --check
```

Race-tool investigation commands:

```sh
command -v clang++
command -v valgrind
valgrind --version
clang++ --version
find /usr/lib -iname '*archer*' -o -name 'libomp.so*'
cmake -S . -B build/tsan -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON '-DCMAKE_CXX_FLAGS=-fsanitize=thread -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=thread
cmake --build build/tsan --target test_delta_stepping --parallel 2
OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=8 OMP_DYNAMIC=FALSE ./build/tsan/tests/test_delta_stepping
```

### Actual results and discovered regression

Environment: GCC 13.3.0, CMake 3.28.3, OpenMP 4.5, two logical CPUs. Final Debug
and Release builds were warning-free with unchanged -Wall -Wextra -Wpedantic
-Wconversion -Wshadow -Werror flags. All 12 CTest entries passed in each final
configuration: project_info, openmp, csr_graph, edge_list_io, dijkstra,
delta_stepping, cli_launch, cli_help, cli_version, cli_invalid_argument, cli_sssp,
and delta_failure. Hosted CI has not run; its job definition is local only.

The first sanitizer invocation hit the known sandbox LeakSanitizer/ptrace
restriction and its allocation-failure test timed out at 60 seconds. Reviewing
the failure path identified a genuine synchronization bug in the initial new
implementation: after merge, a fast thread could enter the next single preparation
and change exception state while a slower thread still tested the previous round's
exit condition. That could cause divergent barrier participation. Removed the
inter-round exit check; every thread now re-enters single preparation before the
single publication barrier and collective exit decision. The coordinator skips
preparation if an exception is already recorded. Fault sweeps and a targeted
post-CAS scheduling-buffer allocation failure cover this regression. No existing
Dijkstra bug was found or changed.

After rebuilding, the full ASan/UBSan suite ran outside the sandbox with approval:
all 12 tests passed with leak detection enabled, no sanitizer findings, and no
timeouts. The final Debug parallel/failure tests each passed 20 consecutive CTest
repetitions (40 executions total). Four-thread requests printed actual team size
4 on this two-CPU host; the dedicated two-thread fixture requires actual size 2.
Fault injection sweeps 90 selected allocation positions per execution, plus one
explicit publication-failure query, and checks recovery; how many selected
positions allocate is schedule-dependent and reported by the executable.

Delta tests run three groups: fixtures/boundaries/closure/oversubscription;
70 deterministic randomized graph trials (mt19937 seed 0xD317A202, every source,
dense/sparse and small/full-range weights) plus four in-place replacements per
nonempty graph; and high-degree/fan-in, chains, and concurrent independent calls.
Matrix: delta {1,2,3,16,4294967295,18446744073709551615}, requested threads {1,2},
both instrumentation modes. Selected queries request 4 threads; default 0 is also
checked. Repeated results match Dijkstra and original-record Bellman–Ford exactly.
Counters satisfy completed-phase and worker-work identities. Dijkstra retains its
300 seeded trials and gains randomized storage-update/query integration checks.
CLI integration covers 18 explicit delta/thread pairs (six deltas, threads 0/1/2),
default threads, strict invalid/duplicate/missing arguments, and unchanged Dijkstra
output including a preserved empty argv source. Graph weights/topology remain
unchanged by queries.

Clang 18.1.3 and Valgrind 3.22.0 are installed, but the /usr/lib search found no
Archer/libomp. GCC TSan configuration and target build succeeded. The executable
failed before tests with `FATAL: ThreadSanitizer: unexpected memory mapping`, exit
66, both inside the sandbox and on an approved retry outside it. Consequently no
race-detector pass is claimed; no dependencies were installed to change tooling.
The TSan startup failure predates algorithm execution and is not a race report.
ASan/UBSan and stress success are not a proof of race freedom.

Manual CLI results for the five-vertex integration graph:

```json
{"schema_version":1,"algorithm":"delta-stepping","source":0,"delta":16,"requested_threads":2,"actual_threads":2,"distances":[0,4294967295,8589934590,0,null]}
{"schema_version":1,"algorithm":"dijkstra","source":0,"distances":[0,4294967295,8589934590,0,null]}
```

### Files, limitations, and next gate

Created:
- include/dynagraph/algorithms/delta_stepping.hpp
- src/algorithms/delta_stepping.cpp
- tests/sssp_test_support.hpp
- tests/test_delta_stepping.cpp
- tests/test_delta_failure.cpp

Modified:
- .github/workflows/ci.yml
- AGENTS.md
- CMakeLists.txt
- apps/dynagraph_cli.cpp
- tests/CMakeLists.txt
- tests/test_dijkstra.cpp
- tests/test_cli_sssp.cmake
- README.md
- docs/architecture.md
- docs/experimental-protocol.md
- docs/research-log.md

No unresolved local functional/build/sanitizer failures. Race-tool verification
and multicore scaling remain unestablished. The serial coordinator, repeated light
scans, atomic contention, dynamic scheduling, and lazy-entry/buffer memory growth
are known design costs; no speedup or O(V+E) memory bound is asserted. Maximum
representable graphs have not been allocated. Fault injection covers selected
C++ allocation paths, not every runtime/OS failure. Counter saturation is handled,
but practical tests cannot generate UINT64_MAX events. Mutation must remain
externally serialized. No performance experiments or measurements were invented.

Phase 2B is complete. Stop for approval. Recommended Phase 3A: first design a
fixed-topology, decrease-only update-batch and incremental-repair contract, define
source/result freshness and atomic batch/error semantics, then implement a simple
independently validated repair baseline in a separately approved step. Compare
every repaired result with fresh Dijkstra and Bellman–Ford on small graphs. Keep
weight-increase repair, automatic delta tuning, and adaptive selection deferred.
Before policy research, add reproducible update traces and controlled timing,
validate on larger multicore hardware, and record raw results and metadata.

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
