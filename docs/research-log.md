# Research log

## 2026-10-28 — Phase 5C-2B bounded parallel and concurrency validation

Explicit implementation authorization followed the Phase 5C-2A investigation.
Initial branch feature/validation-concurrency, HEAD
d840469bafda76ebb601dad9faf809259658584a; the only untracked files were the eight
tests/tsan_controls fixtures/driver/docs. Verified all 938 hashes in the preserved
5C-2A source/evidence manifest before editing. No dependency installation,
delegation, commit, push, PR or production change occurred. Existing benchmark
integration tests ran; no controlled performance experiment was conducted.

Added concurrency_validation_support.hpp, test_parallel_concurrency.cpp,
test_concurrency_runtime.py, adversarial_test_support.hpp under tests/, and
docs/validation-concurrency.md. Changed tests/CMakeLists.txt, the adversarial
executable's fixture wrapper, AGENTS.md, experimental-protocol.md and this log.
The extracted fixture body (apart from inline/name) and complete old main are
byte-for-byte equal to HEAD. Phase 5C-1 case/update/checkpoint semantics and all
existing allocation injectors remain unchanged. CI needs no workflow change.

Version concurrency-validation-v1 reuses the independent record-based synchronous
Bellman–Ford, canonical graph checks, Phase 5C-1 seeded generator and FNV helpers.
The eight static families are dense zero, hub degrees 255/256/257, competing fan-in,
repeated light closure/heavy work, stale hub/chain and disconnected max-weight paths.
Extended cases 8..15 explicitly reverse vertex IDs/source, preserve zero/max
weights and scale other positive weights to 2w+1. Inputs are deterministic;
execution schedules and CAS counts are not. Static fixtures ignore the root seed;
seeded dynamic/client cases use it. Full expected vectors are precomputed outside
static repetitions and for all seeded trace checkpoints.

Exact direct counts: fast 8×3×3×2×2=288, stress 8×6×3×2×20=5760,
extended 16×6×3×2×100=57600. Fast deltas are 1,16,UINT64_MAX; the six-value profiles
reuse 1,2,3,16,UINT32_MAX,UINT64_MAX. Requests are 1/2/4 with both metrics modes in
the matrix. Stress/extended registration defaults OFF with independent options.
Two default CTest entries have 120-second bounds; optional tiers use 180/900 s.

Default C++ extras: six reduced runtime probes; eight immutable shared-graph
queries across two independent host callers; two independent engines with 32
updates plus two initial states; one externally serialized engine with eight
strict decreases plus initialization. The client total is 51 state comparisons.
One mutex covers every shared-engine access, including all inspection, and its
authoritative ledger. Per-client results, snapshots, metrics and exception slots
are independent. A start gate permits concurrency; clients join before diagnostics.

Four existing seeded cases 0/7/14/31, source 0 and requests 2/4 produce eight
16-update traces: 128 updates and 544 complete state comparisons through forced
delta, heuristic, rotating public overrides and standalone delta. Every accepted
update checks complete expected distances and authoritative weights. Default C++
distance comparisons total 889, separately from the 288 direct matrix queries.

Measured direct calls record actual teams and per-thread work, successes and CAS
retries. Adaptive calls expose only available aggregate telemetry/actual teams for
executed measured delta. Other fields remain null. Work participation means
positive observed edge work, not simultaneous execution. Rejected proposals before
CAS are not mislabeled as failed CAS. Neither CAS retries nor full team work
participation is required positive. Source/worker/metrics/repetition selectors,
versioned fingerprints and shell-quoted context/environment reproduce inputs;
interleavings remain unprescribed. Failure handlers also cover setup before a
context exists without inventing vectors or teams.

### Verification record and initial failures

Raw command arrays, exit codes, durations, stdout/stderr SHA-256 and full logs are
preserved under ignored results/validation/phase5c2b/. The initial state receipt
and the Phase 5C-2A evidence remain separate. Durations are validation wall times,
not algorithm performance evidence; some builds/initial suites overlapped.

Initial focused CTest passed 3/3 (0.721121 s); Debug full passed 30/30
(82.553604 s). The first Release full run passed 29/30 (79.703647 s), failing the
existing deterministic analysis figure/provenance test while AGENTS.md became
modified during its two renders. The analyzer records literal Git status in the
manifest; the changed working-tree inventory is consistent with that mismatch.
No analysis code was changed. Final verification freezes source/inventory during
rendering and repeats the full suite, retaining the initial failure.

Initial sandbox ASan/UBSan CTest passed only 5/30 (83.220051 s), exit 8: LSan
reported fatal process-inspection/ptrace errors, not a passing sanitizer check.
The unchanged suite outside the sandbox then passed 30/30 (89.428929 s), with
detect_leaks=1 and halt-on-error still enabled; no sanitizer finding. A final
rebuild also covers the added setup diagnostic and measured closure/stale witnesses.
No test timeout is retried or reported as passing.

The standalone optional Python run passed all 9 tests (3.356714 s command wall),
including actual four-worker teams and active nested inner teams of two within
an outer team of two. Default methods explicitly skip these two optional checks.
Serial-limit probes observe one worker; dynamic TRUE is accepted at its measured
team size. No aggregate host-caller team cap is inferred from THREAD_LIMIT.

### Final verification and observed evidence

The final source adds setup-failure diagnostics, explicit measured light-closure/
stale-record witnesses, complete committed shared-client transaction prefixes,
and preserved Python child observations/timeout context. Rebuilt all three
configurations afterward. Six test/build source SHA-256 hashes were frozen before
final verification and checked unchanged afterward. Only documentation/results
were completed after the final suites. All builds were warning-clean with
-Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror; Release retains NDEBUG and
all require-based checks remain active. Environment: GCC 13.3.0, CMake 3.28.3,
Python 3.14.2, nproc=2, libgomp.so.1. No new dependency was installed.

| Final command (from repository root) | Exit | Result | Command wall seconds |
|---|---:|---|---:|
| `cmake --build --preset debug --parallel 2` | 0 | full build | 8.629723 |
| `cmake --build --preset release --parallel 2` | 0 | full build | 11.440220 |
| `cmake --build build/sanitize --parallel 2` | 0 | full build | 12.217579 |
| `ctest --preset debug` | 0 | 30/30 | 103.894120 |
| `ctest --preset release` | 0 | 30/30 | 49.497688 |
| `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir build/sanitize --output-on-failure` (outside sandbox) | 0 | 30/30, no findings | 145.191154 |
| `ctest --test-dir build/debug -L concurrency-fast --output-on-failure` | 0 | 2/2 | 0.523265 |
| `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_concurrency_runtime.py build/debug/tests/test_parallel_concurrency --optional` | 0 | 9/9, no skips | 1.629962 |
| `ctest --test-dir build/release -L '^concurrency-(stress\|extended)$' --output-on-failure` | 0 | 2/2; 5760 + 57600 direct queries | 41.046475 |

The table's times are recorder wall times; CTest reported final totals 103.82,
49.46 and 145.15 seconds for Debug/Release/sanitizer. The optional tier entries
reported stress 3.71 s and extended 37.07 s. Final focused entries were 0.14 s C++
and 0.33 s Python. Default Python runs nine methods with seven passes and two
explicit optional skips; standalone --optional passed all nine. Overlapping
configurations/stress increased some times; the full sanitizer suite exceeded
the two-minute target, while all finite entry bounds passed. No coverage was cut
and these numbers are not algorithm performance measurements.

All full suites include existing Phase 5C-1 correctness/adversarial/reproduction
and all three isolated allocation-failure executables. Final Debug output confirms
48 cases, 96 traces, 1536 updates, 1632 checkpoints and 13056 comparisons; the
adversarial executable confirms 28 traces, 230 updates and 258 checkpoints.
Existing reproduction passed both Python methods. Default registration remains
30 entries locally (including the already available optional analysis renderer);
all four system/concurrency stress/extended entries and all race controls are
absent with options OFF. CI configuration is unchanged; hosted CI was not run.

The final optional logs were inspected for distinct matrix keys: exactly 5760
(720 per base case) and 57600 (3600 per extended case), with no duplicates or
omissions. Fast logged exactly 288 direct queries and its original fingerprints;
clients report 8 immutable queries, 32 separate-engine updates and 8 serialized
updates, 51 comparisons; seeded traces report 128 updates and 544 comparisons.
Every comparison passed the independent oracle and complete graph checks.

Observed final runtime probes: flat FALSE/limit2 returned actual teams 2, flat
FALSE/limit1 returned 1, dynamic TRUE/limit2 returned 1, and request 0 was exercised.
Nested inactive outer team 2 returned inner teams 1; active nesting with limit4/
max-levels2 observed outer 2 and inner 2. Explicit request4/limit4 achieved actual
4 in both reduced probes. The limited main matrix observed 1 or 2; unmeasured
queries stay null. Recorded per-thread work can be uneven; neither participation
by every thread nor a positive retry counter is assumed. Shared-engine failure
prefixes now retain both clients' committed updates under the mutex.

Commands enabling/disabling optional registration were actually executed:

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2 --target test_parallel_concurrency test_system_adversarial
cmake --preset release
cmake -S . -B build/sanitize -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined
cmake --preset release -DDYNAGRAPH_ENABLE_CONCURRENCY_STRESS=ON -DDYNAGRAPH_ENABLE_CONCURRENCY_EXTENDED=ON
cmake --preset release -DDYNAGRAPH_ENABLE_CONCURRENCY_STRESS=OFF -DDYNAGRAPH_ENABLE_CONCURRENCY_EXTENDED=OFF
```

The first two pre-recorder commands exited 0; their wall times were not retained.
The complete command ledger, including intermediate successful verification,
initial failures, exact parent environments and durations, is in ignored
results/validation/phase5c2b/commands.md with raw JSON/stdout/stderr receipts.
One extended-tier recorder invocation placed its timeout option after a remainder
argument and failed before launching CTest; its not-launched receipt is retained.
Corrected invocations executed the complete tier, including the final 57600 queries.
No timeout occurred or was retried. Final full suites were repeated because
test diagnostics/witnesses changed, not to discard failed trials.

Production preservation diff and git diff --check pass. The initial 938 Phase
5C-2A source/evidence hashes still match. Stress/extended options are restored OFF.
No known correctness failure remains; the earlier environment/provenance failures
are retained above. Ready for independent source audit, with the unresolved
detector gate explicitly carried forward. No packages, commits or pushes.

The race-detector gate remains unmet: 5C-2A's specific work_ warning is LIKELY
TOOL/RUNTIME LIMITATION, not proof of race freedom. No fresh clean TSan claim,
ASan/UBSan race-detection claim, scalability or publication claim is made.
Stop after verification for independent source audit.

## 2026-10-28 — Phase 5C-1 correctness and failure-resilience validation

### Authorization, state and architecture

The implementation request explicitly approved the reviewed 5C-1 design and its
refinements. Confirmed clean feature/validation-correctness at
45e850f5dd6cda1e2515ff27d1e05b99d17ee2a5 before editing. Reinspected engineering
guidance, actual public APIs, individual correctness/fault tests, harness/oracles,
CMake/CI/presets, architecture/protocol and research history. No delegation,
dependency installation, commit, push, branch switch or PR creation occurred.

Added tests/system_validation_support.hpp, tests/test_system_correctness.cpp,
tests/test_system_adversarial.cpp, tests/test_system_reproduction.py and
docs/validation-correctness.md. Extended the three existing allocation-failure
executables, tests/test_benchmark_replay.py and tests/CMakeLists.txt. Updated
AGENTS.md, docs/experimental-protocol.md and this log. All earlier tests remain.
The existing GitHub Actions Debug/Release/ASan+UBSan matrix already runs default
CTest; inspection showed no workflow edit was needed. Stress/extended registration
is opt-in; stress was restored OFF after verification.

The new test-only system-validation-v1 framework generates independent case-local
graphs/traces, keeps an endpoint/weight ledger, and compares standalone incremental
state, four engine policies, rotating overrides and fresh Dijkstra/delta results.
Every checkpoint checks all distances and graph arrays; every update checks
outcomes/improvement counts and reachability invariance. Bellman–Ford reads input
records synchronously without production SSSP or CSR traversal. Hand results
additionally validate zero-region, disconnected and wide-chain fixtures. Caller
record values/order and caller graphs are explicitly checked for immutability.

Fast: 48 graphs, 96 source traces, 1536 updates, 1632 checkpoints, 13056 complete
state comparisons. Stress: 96 graphs, 192 traces, 9216 updates, 9408 checkpoints,
75264 comparisons. Adversarial: 14 fixtures in both no-effect modes, 28 traces,
230 updates, 258 checkpoints, 2064 comparisons. Optional extended implements
384 graphs with exactly two sources per graph, thus 768 traces, 98304 updates,
99072 checkpoints and 792576 comparisons; its full corpus was NOT executed.
Selected extended case 383 is exercised by the reproduction test.

### Failure resilience and coverage

New fault histories contain effective repair, a committed weight-only decrease,
an equal request and another effective update. Adaptive history actually executes
incremental, Dijkstra and delta before the fault target. Each target reconstructs
identical history. Independent Bellman–Ford validates each history operation,
rollback, identical retry and a different subsequent update. Original failure
sweeps and initialization/adoption/bypass tests are preserved.

Final Debug and Release detailed logs recorded the following additional history
coverage (the sanitizer runs also passed these groups):

| Target | Plain | With metrics | Additional coverage |
| --- | ---: | ---: | --- |
| Standalone incremental | 16 faults | 16 faults | 14 after tentative writes per mode |
| Adaptive Dijkstra, each forced/automatic | 12 | 12 | Staged authoritative state unchanged |
| Adaptive delta, each forced/automatic | 9 | 10 | 1/2 post-team allocations |
| Adaptive incremental, each forced/automatic | 16 | 16 | 14 after tentative writes per mode |
| Adaptive region/publication | 2 | 2 | All four mandatory targets triggered |
| Standalone delta history | 7 | 7 | All 14 attempts triggered in these runs |

That is 200 new injected failures per observed suite, in addition to the existing
sweeps. All mandatory targets triggered. Higher standalone delta thread-local
positions remain schedule-dependent in general; untriggered positions are printed
and counted as uncovered rather than treated as injection successes. No production
fault hook was needed. Standalone delta checks input immutability and retry, not
owning-state or caller-metric rollback that its API does not promise. Existing
post-CAS targeting retains its documented 16-byte Entry/layout assumption.

Python replay now adds 112 bounded prefix invocations: seven prefixes, two sources,
four policies and two no-effect modes. A separate endpoint dictionary and Python
integer Bellman–Ford compare all final weights/distances at every prefix. Existing
C++ replay additionally verifies each intermediate state within each invocation.

### Executed verification and timing context

Toolchain: GCC 13.3.0, CMake 3.28.3, Python 3.14.2. Parallel CTest entries explicitly
set worker/thread-limit/dynamic settings; new tests use 2/2/FALSE. The visible
cgroup CPU limit read `max 100000`; no physical-core/isolation claim is inferred.
All runtimes below are validation wall times, not algorithm performance evidence.
Several builds/suites overlapped, so compare no throughput or speedup from them.

Generated logs and JSON command receipts are retained in ignored
results/validation/phase5c1/. Each receipt records the exact argument array,
exit code, subprocess wall time and parent sanitizer/OpenMP environment; CTest
entry-specific environments remain in tests/CMakeLists.txt and detailed logs.

| Final verification | Exit | Result | Wall seconds |
| --- | ---: | --- | ---: |
| Debug full CTest, reviewed source | 0 | 28/28 | 85.060 |
| Release full CTest, reviewed source | 0 | 28/28 | 82.097 |
| ASan/UBSan full CTest, reviewed source | 0 | 28/28, no findings | 82.691 |
| Registered bounded stress, reviewed source | 0 | 1/1, all 9408 checkpoints | 3.359 |
| Standalone Python benchmark replay | 0 | 10/10 | 29.009 |
| Full fast Debug, workers 1 | 0 | 96 traces/1632 checkpoints | 0.348 |
| Full fast Debug, workers 2, first/repeat | 0/0 | Same complete corpus both times | 0.409/0.426 |
| Full fast Release, workers 2 | 0 | Same complete corpus | 0.177 |

Final CTest-reported totals were Debug 85.05 s, Release 82.06 s, sanitizer 82.67 s;
stress entry 3.29 s. The first full suites also passed 28/28: Debug 126.389 s,
Release 118.693 s, sanitizer 169.084 s. Debug exceeded the two-minute target during
three overlapping configurations; benchmark replay dominated (54.735 s for its
ten Debug tests). No coverage was reduced. The final default suites fit the target.
The initial bounded stress also passed (12.540 s) while other validation ran.

Repetition was justified by final helper changes: checking caller record order
directly and capturing returned distance vectors before outcome-metadata assertions.
These changed no production behavior or generator mapping. The final full suites
and bounded stress were rerun afterward. Each final suite includes reproduction
(2 Python tests), all 14 adversarial fixtures, and every prior registered entry,
including the optional renderer already available in the existing local environment.
Hosted CI was not executed; no packages were installed for this phase.

### Executed command ledger

All commands below were actually executed from the repository root through a
receipt/logging wrapper. Times are measured subprocess wall seconds; CTest counts
are entries, not individual assertions. Missing parent ASAN/UBSAN options mean
uninstrumented execution; CTest still supplies its entry-specific OpenMP settings.
Detailed logs and matching JSON receipts use the IDs in the first column.

| Receipt ID | Exact command/environment | Exit | Passed/total | Seconds |
| --- | --- | ---: | --- | ---: |
| bounded-stress-reviewed | `ctest --test-dir build/release -L validation-stress --output-on-failure` | 0 | 1/1 entries | 3.359 |
| bounded-stress | `ctest --test-dir build/release -L validation-stress --output-on-failure` | 0 | 1/1 entries | 12.54 |
| debug-fast-workers1 | `OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE build/debug/tests/test_system_correctness --workers 1` | 0 | 1/1 corpus; 1632 checkpoints | 0.348 |
| debug-fast-workers2-a | `OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE build/debug/tests/test_system_correctness --workers 2` | 0 | 1/1 corpus; 1632 checkpoints | 0.409 |
| debug-fast-workers2-b | `OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE build/debug/tests/test_system_correctness --workers 2` | 0 | 1/1 corpus; 1632 checkpoints | 0.426 |
| debug-full-reviewed | `ctest --preset debug` | 0 | 28/28 entries | 85.06 |
| debug-full | `ctest --preset debug` | 0 | 28/28 entries | 126.389 |
| debug-new-and-failure | `OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE ctest --test-dir build/debug -R '^(system_.*\|incremental_failure\|adaptive_failure\|delta_failure)$' --output-on-failure` | 8 | 5/6 entries | 2.006 |
| debug-new-initial | `OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE ctest --test-dir build/debug -R '^system_' --output-on-failure` | 0 | 2/2 entries | 0.822 |
| debug-targeted-final | `OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE ctest --test-dir build/debug -R '^(system_.*\|incremental_failure\|adaptive_failure\|delta_failure)$' --output-on-failure` | 0 | 6/6 entries | 14.869 |
| python-replay | `PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE python3 tests/test_benchmark_replay.py build/debug/dynagraph_bench` | 0 | 10/10 Python tests | 29.009 |
| release-fast-workers2 | `OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE build/release/tests/test_system_correctness --workers 2` | 0 | 1/1 corpus; 1632 checkpoints | 0.177 |
| release-full-reviewed | `ctest --preset release` | 0 | 28/28 entries | 82.097 |
| release-full | `ctest --preset release` | 0 | 28/28 entries | 118.693 |
| sanitize-full-reviewed | `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir build/sanitize --output-on-failure` | 0 | 28/28 entries | 82.691 |
| sanitize-full | `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir build/sanitize --output-on-failure` | 0 | 28/28 entries | 169.084 |

### Reproducibility

For complete fast corpora, Debug workers 1, Debug workers 2 twice, Release workers
2 and final full suites all reported generation fingerprint 6064859197570865871
and state fingerprint 8157398655181721149. Direct delta observations were actual
1 or actual 2 as requested. Heuristic parallel/fallback decisions legitimately
changed with requested budget; authoritative states did not. Selected case tests
also request 4 with limit 2, without claiming an actual four-worker run.

Pinned example (also asserted by the reproduction test):

```sh
OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE build/debug/tests/test_system_correctness --profile fast --seed 4294967295 --case 31 --source 0 --workers 1
```

Exit 0, 17 checkpoints; generation fingerprint 6423381795917974648 and state
fingerprint 618799244384374341. Its initial standalone execution took 0.151 s by
the command tool (not the later receipt timer). CLI rejection tests cover missing,
duplicate/unknown options, malformed/overflowed numbers, profile/case bounds,
worker bounds and unsupported source combinations. Randomized failures print
complete reproduction context and attempted trace prefix. Fingerprints are test
markers, not SHA-256 evidence authentication.

### Intermediate failures and limitations

An intermediate Debug build exited 2 because the new standalone incremental
history test referenced a nonexistent sentinel helper; replaced it with an
explicit local marker. Its full build runtime was not captured. A prematurely
started targeted CTest then used some stale binaries: 5/6 passed, reproduction
failed because the old binary returned 1 rather than CLI exit 2 for an invalid
source. That run took 2.006 s and is retained as debug-new-and-failure, not counted
as final verification. Fresh build/rejection handling corrected it; subsequent
targeted 6/6, all final suites and reproduction tests passed. Initial new-system
CTest before the history additions passed 2/2 in 0.822 s.

Sanitizer runs used ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 and
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1, outside the sandbox with approval
because the repository documents LeakSanitizer process-inspection restrictions.
Neither sanitizer run had an environmental startup failure or finding. No race
freedom claim follows from ASan/UBSan or repeated correctness runs. Full extended,
other toolchains/platforms, maximum production graphs, exhaustive interleavings,
process-fatal failures and Phase 5C-2 race tooling were not executed.

No unreachable activation or tiny near-UINT64_MAX case was fabricated. Finite
fixed-topology decreases preserve reachability; arithmetic tests exercise wide
distances, cap rejection and sentinel separation within supported bounds. Automatic
small-graph Dijkstra uses separate immutable configurations; varying destination
degree exercises automatic incremental/delta transitions without heuristic tuning.

Final `git diff --check` exited 0 with no output. The following production/scope
check also exited 0 with no output:

```sh
git diff --exit-code 45e850f -- src include apps benchmarks cmake CMakeLists.txt CMakePresets.json .github
```

The final inventory is eight modified tracked files and five new files, confined
to tests, tests/CMakeLists.txt, AGENTS.md and documentation. Ready for independent
review with the explicit unexecuted/portability limits above; no production or
timing changes and no unresolved observed correctness or sanitizer failures.

Stop for independent Phase 5C-1 review. No further phase, publication work,
algorithm modification or performance claim is authorized.

## 2026-10-28 — Phase 5B-4B recovery, completion and verification

### Recovery audit

Recovered feature/benchmark-analysis at e705df6976054903f4ee313b1d1c56fe1d473013.
Initial status was exactly ten untracked analysis implementation/configuration/test
files and modified tests/CMakeLists.txt. Inspected every file, engineering guidance,
architecture, timing/replay/workload contracts, experimental protocol and existing
research records. Preserved a pre-edit copy of all eleven files at
`/tmp/dynagraph-recovery-snapshot`; no original implementation was discarded.
`rg` was absent, so inspection used find/grep/sed. No separate Phase 5B-4A design
or requirements document was present in the checkout or local document inventory.
The explicit continuation request authorizes 5B-4B beyond the stale AGENTS.md gate;
conformance to the absent 4A document remains an independent-review limitation.

Recovered import/statistics/figures/CLI were substantially complete. Import reused
the public complete-dataset validator with no pending override and executed no
staged binaries. Exact rational tick conversion, same-run/block pairing,
conservative zero handling, descriptive per-trial quantiles, weighted complete
panels, adaptive comparisons and explicit absent telemetry were already present.
There were no inferential confidence intervals, significance tests, bootstrap
calculations, fabricated backend selections or performance claims. Main gaps were
documentation, actual-run CLI integration and broader rejection/zero coverage.

Tightened duplicate rejection to cover reused run IDs even with different bytes,
rejected symlink input directories before path resolution, checked all pairing
identities explicitly and reset renderer style defaults. Added actual orchestrator
to CLI integration, tampering/exclusion/public-validator tests and hand-computed
unequal block ratios with numerator/baseline/both-zero cases. Correct recovered
CLI, fixtures, configuration, requirements and existing calculations were retained.

Completed files: benchmarks/python/analysis_import.py, analysis_stats.py and
analysis_figures.py; tests/test_analysis_import.py, test_analysis_stats.py and
tests/CMakeLists.txt. New completion files: tests/test_analysis_integration.py,
docs/benchmark-analysis.md. Updated README.md, docs/architecture.md,
docs/experimental-protocol.md and this log. Retained unchanged recovered files:
benchmarks/python/analyze.py, benchmarks/configs/analysis-example-v1.json,
benchmarks/requirements-analysis.txt, tests/analysis_test_support.py and
tests/test_analysis_figures.py.

### Actual commands and outcomes

Commands below were executed from the repository root. Python was 3.14.2.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_analysis_import.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_analysis_stats.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_analysis_figures.py
```

Before edits: import 6/6 passed; statistics 5/5 passed. The figure test ran and
failed (one error: matplotlib PackageNotFoundError), rather than being skipped.
The user then explicitly approved pinned dependency installation. Created the
local environment without modifying the repository's dependency files:

```sh
python3 -m venv /tmp/dynagraph-analysis-venv
/tmp/dynagraph-analysis-venv/bin/python -m pip install -r benchmarks/requirements-analysis.txt
```

The sandbox installation failed package-index DNS access. Repeated the same pip
command with approved network escalation; installation succeeded for all eleven
pinned packages. No global installation or package upgrade was performed.

An intermediate unittest discovery run executed 17 tests with one failure and
one error: the new tampering test appended permissible JSON whitespace, and the
new integration test lacked its runner under discovery. Corrected the tampering
payload to invalid trailing data and supplied an explicit runner/discovery guard.
The figure deterministic test itself passed in that run. Final standalone suite:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 MPLCONFIGDIR=/tmp/dynagraph-analysis-mpl DYNAGRAPH_BENCH=/workspaces/Dynagraph-HPC/build/release/dynagraph_bench OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE /tmp/dynagraph-analysis-venv/bin/python -m unittest discover -s tests -p 'test_analysis_*.py'
cmake --preset debug -DDYNAGRAPH_ANALYSIS_PYTHON=/tmp/dynagraph-analysis-venv/bin/python
cmake --preset release -DDYNAGRAPH_ANALYSIS_PYTHON=/tmp/dynagraph-analysis-venv/bin/python
cmake --build --preset debug --parallel 2
cmake --build --preset release --parallel 2
ctest --preset debug
ctest --preset release
```

Final standalone suite: 17 tests, all passed, no skips (12.813 s). Both CMake
configures and warning-clean builds exited 0. Debug CTest: 25/25 passed, zero
failures (75.37 s). Release CTest: 25/25 passed, zero failures (69.74 s). Both
registered and executed all four analysis entries: import (9 tests), statistics
(6), integration (1), figures (1). Existing production, timing, replay, artifact
and experiment tests also passed. CTest durations are test diagnostics only.

### Retained end-to-end artifacts and regeneration

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 MPLCONFIGDIR=/tmp/dynagraph-analysis-mpl OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE DYNAGRAPH_ANALYSIS_SMOKE_ROOT=results/analysis/phase5b4b-smoke /tmp/dynagraph-analysis-venv/bin/python tests/test_analysis_integration.py build/release/dynagraph_bench
```

One integration test passed (14.100 s). It generated a small verified test-spec
bundle and two actual Release experiments, four blocks/all policies/16 trials
each. There are 16 full-trace rows and 144 per-update rows (9 ordered updates per
trial); no latency sum is used as trace time. Both complete validators succeeded.
The analysis CLI ran twice with figures disabled; output inventories were exactly
equal and raw evidence inventories unchanged. There are 16 paired comparison rows
(4 blocks x 4 prespecified comparisons). Every numerator/baseline trial ID maps
to its recorded same block. A plan executable-identity mismatch exited 2 and
produced a failed manifest; existing-output reuse also exited 2. Evidence remained
unchanged. The integration's hardware/session labels are explicit test-plan labels,
not measured hardware identity or claims of independent replication.

Prepared `figure-plan.json` by reading the retained analysis-plan.json with the
strict JSON loader, setting figures to `list(analysis_import.FIGURES)` and writing
canonical JSON. Executed:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 MPLCONFIGDIR=/tmp/dynagraph-analysis-mpl /tmp/dynagraph-analysis-venv/bin/python benchmarks/python/analyze.py --plan results/analysis/phase5b4b-smoke/figure-plan.json --output results/analysis/phase5b4b-smoke/figures-one
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 MPLCONFIGDIR=/tmp/dynagraph-analysis-mpl /tmp/dynagraph-analysis-venv/bin/python benchmarks/python/analyze.py --plan results/analysis/phase5b4b-smoke/figure-plan.json --output results/analysis/phase5b4b-smoke/figures-two
```

Both exited 0 with exactly
`{"accepted_inputs":"2","figures":"14","schema_version":1,"status":"complete"}`.
Using analysis_import.inventory, asserted equality of both directories (25 files
each), and verified all 24 manifest-listed output hashes. Each contains seven SVG
and seven PDF products plus tables, report, acceptance and manifest. This compares
regeneration from the same raw evidence, not repeated measured runtimes. Synthetic
figure tests separately check prominent fixture labels and unchanged evidence.
Both actual-run inputs classify valid_harness_only with declared_harness_only;
no Codespaces performance eligibility is asserted. All generated artifacts are
under ignored results/analysis/phase5b4b-smoke; none rewrites preexisting evidence.

Additional final checks:

```sh
git diff --check
git diff --exit-code e705df6 -- apps include src cmake CMakeLists.txt CMakePresets.json benchmarks/python/run.py benchmarks/python/experiment_records.py benchmarks/python/artifacts.py benchmarks/python/workloads.py benchmarks/python/deterministic.py
```

Both exited 0. Production algorithms, graph code, public APIs, executable sources,
timing implementation, clock boundaries, orchestration and complete validator are
unchanged relative to the base commit. No commits, pushes, branch switches, merges,
resets, deletes or delegation occurred.

### Limits and review gate

No outstanding observed test failures. Phase 5B-4A's absent architecture/approval
record requires review against the external original if available. Hardware and
instrumentation declarations remain user statements, not attestation. Hashes do
not authenticate producers or defeat hostile concurrent writers. Maximum-size
datasets, peak memory, alternate Python/platform/font stacks, sanitizer/race suites
and hosted CI were not executed in this continuation. No inference, publication
performance evidence, calibration, selector telemetry or speedup claim is supplied.
Same-environment SVG/PDF determinism passed; cross-platform identity is unverified.
Stop here for independent Phase 5B-4B review; no further phase is authorized.

## 2026-10-26 — Phase 5B-3B reproducible timing infrastructure

### Authorization and implementation

The attached 5B-3B request explicitly approved implementation after the read-only
5B-3A design review. Started on feature/benchmark-timing at e548d0a with a clean
working tree. Read engineering guidance, existing replay/artifact/protocol/design
records, generator/verifier, adaptive API, tests, CMake and presets. Updated the
phase gate; no dependencies installed, agents delegated, commits or pushes.

Preserved verify's CLI/JSON/per-update oracle behavior and existing tests/goldens.
Exposed existing parser/oracle through workload.hpp and added complete independent
ledger prevalidation for timing. Timing uses the same public decrease call with
metrics and overrides disabled. Full-trace has exactly two clock reads; latency
has two per update and preallocated storage. Initialization, warm-ups, all oracle
checks, output and final destruction are outside timing. Public-call validation,
selection, allocation, synchronization, commit and temporary cleanup remain inside.
Every warm-up and trial initializes a fresh engine. Actual timed-engine final
weights/topology and fresh Dijkstra/eligible Bellman-Ford are independently checked.
Failed latency-prefix observations are diagnostic only; failed trials stay invalid.

Added steady-clock raw tick/period and checked nanosecond contracts, 1024 raw
back-to-back probes, CMake build metadata, and explicit unavailable actual-team
metadata. Optional work counters remain off. Python stages/snapshots inputs and
executable, verifies artifact SHA-256/recipe and all-policy full C++ preflight,
launches sequential fresh worker processes, checks identities throughout, retains
stdout/stderr/exit evidence, and writes fsynced schema-versioned JSONL. A seeded,
pinned SplitMix64/Fisher-Yates balanced schedule precedes execution. Completion
is checked against the entire evidence directory before terminal success is
written; default/public validation rejects missing/truncated terminals. No retry,
resume, statistical analysis, speedups, calibration or Phase 5B-4 implementation.

Initial new-test failures were test-expectation defects: a hand-written seed-zero
schedule transposed labels C/D (correct draws are [3,0,1]), and an evidence-corruption
test initially appended harmless JSON whitespace to an exit file. Corrected the
fixtures to pin the specified draws and mutate exit semantics. Balance tests
already passed. No existing golden values or production algorithm were changed.

### Commands and results

Toolchain: Python 3.14.2, GCC 13.3.0, CMake 3.28.3. Commands executed from root:

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --preset debug --output-on-failure
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release --output-on-failure
python3 tests/test_workloads.py
OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE python3 tests/test_benchmark_replay.py build/debug/dynagraph_bench
OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE python3 tests/test_benchmark_experiment.py build/debug/dynagraph_bench
ctest --test-dir build/debug -R '^benchmark_timing$' --output-on-failure
cmake -S . -B build/sanitize -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined
cmake --build build/sanitize --parallel 2
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ./build/sanitize/tests/test_project_info
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir build/sanitize --output-on-failure
git diff --check
git diff --exit-code -- src/adaptive src/algorithms src/dynamic src/graph include/dynagraph/adaptive include/dynagraph/algorithms include/dynagraph/dynamic include/dynagraph/graph apps/dynagraph_cli.cpp benchmarks/python/artifacts.py benchmarks/python/workloads.py benchmarks/python/deterministic.py tests/test_workloads.py tests/test_benchmark_replay.py .github
```

Debug/Release final builds passed all existing warning flags with Werror; CTest
21/21 passed in each. Standalone workload tests 22/22 passed, unchanged replay
integration 9/9 passed, experiment integration 6/6 passed, and the C++ timing
contract entry passed. Existing loader integration also passed in all full suites.
After final changes, rebuilt Debug/Release/sanitizer targets and repeated the full
suites. Repetition was justified by added oracle/evidence rejection and failed
latency-prefix tests, not by timing stability or policy comparisons.

The instrumented sandbox probe exited 1 with the known LeakSanitizer ptrace/process
inspection restriction. Full ASan/UBSan CTest ran outside the sandbox with approval
and leak detection enabled: 21/21 passed, no findings. Sanitizer data is validation
only. No tests were disabled and no new dependency was installed. Hosted CI was
not executed; its existing full CTest jobs automatically include the new entries.

Tests cover both modes, every policy/no-effect pair, fresh/repeated engines,
equal/repeated decreases, disconnected zero cycles, all final weights/distances,
independent final oracles and deliberately wrong final-ledger rejection. Fake
clocks prove bracket/read counts, failure index and retained successful latency
prefix. Checked arithmetic covers zero duration, negative clock progression,
signed epoch differences and conversion overflow. Python checks seeded position/
adjacency balance, schema/duplicate/numeric rejection, configuration/executable
identity mismatches, prerequisites, failed exits, real subprocess timeout evidence,
fail-fast/no-retry behavior, changed artifacts, invalid exit evidence, malformed/
truncated JSONL and missing terminal records. No test orders algorithm runtimes.

### End-to-end smoke evidence

Created /tmp/dynagraph-5b3-4prq3p1i using tempfile.mkdtemp, generated the existing
chain-v1.json bundle with write_bundle, and wrote canonical configuration files.
Full config used blocks=4, seed=0, delta=16, threads=2, shared_fast_path, warmups=1
and timeout_seconds=30; latency config changed only timing_mode to per-update.
Manifest paths were bundle/manifest.json relative to those configs. Exact final
experiment/validation commands:

```sh
OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE python3 benchmarks/python/run.py run --config /tmp/dynagraph-5b3-4prq3p1i/config.json --runner build/release/dynagraph_bench --output /tmp/dynagraph-5b3-4prq3p1i/reviewed-full-trace
python3 benchmarks/python/run.py validate --input /tmp/dynagraph-5b3-4prq3p1i/reviewed-full-trace/records.jsonl
OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE python3 benchmarks/python/run.py run --config /tmp/dynagraph-5b3-4prq3p1i/per-update-config.json --runner build/release/dynagraph_bench --output /tmp/dynagraph-5b3-4prq3p1i/reviewed-per-update
python3 benchmarks/python/run.py validate --input /tmp/dynagraph-5b3-4prq3p1i/reviewed-per-update/records.jsonl
```

Every command exited 0 with schema_version=1, status=complete, trials="16".
Each experiment had four successful preflights, 16 fresh-process trials, 16 warm-ups,
16 timed-final-state checks and four complete blocks over all policies. Full-trace
produced 16 trace observations and zero latency samples. Per-update produced
192 latency samples (12 updates x 16 trials) and zero trace observations. Their
independent final checks used Dijkstra and small-graph Bellman-Ford. Source=0,
V=8, E=7. Executable snapshot SHA-256:
84ab1106bc1bca003c47cd50bd3742b230edc0f35cb25a7ac739f55bbad30b3d.
Graph/trace hashes remain the Phase 5B-1 pinned chain hashes. Complete evidence
is retained in the two /tmp directories; no raw duration or CTest duration is
interpreted as performance/scaling evidence.

Deterministic regeneration was additionally checked with:

```sh
PYTHONPATH=benchmarks/python python3 - <<'CHECK'
from experiment_records import schedule
assert schedule(8, 0) == schedule(8, 0)
print(schedule(4, 0))
CHECK
```

Automated tests also prove every policy position and every directed adjacent pair
appears once per four-block group, for seed endpoints and multiple groups.

### Files and limitations

Added: benchmarks/configs/timing-smoke-v1.json,
benchmarks/python/experiment_records.py, benchmarks/python/run.py,
cmake/benchmark_build.hpp.in, docs/benchmark-timing.md,
include/dynagraph/benchmark/timing.hpp, include/dynagraph/benchmark/workload.hpp,
src/benchmark/timing.cpp, tests/test_benchmark_experiment.py,
tests/test_benchmark_timing.cpp.

Modified: AGENTS.md, CMakeLists.txt, README.md, apps/dynagraph_bench.cpp,
docs/architecture.md, docs/benchmark-replay.md, docs/experimental-protocol.md,
docs/workload-artifacts.md, docs/research-log.md, src/benchmark/replay.cpp,
tests/CMakeLists.txt.

Inspected tracked and new source/test/schema/build changes. Whitespace and
unchanged-production diff checks passed. No production graph/SSSP/adaptive or
existing artifact generator/golden modifications occurred.

Limitations: actual executed teams remain unavailable with timed metrics disabled;
OpenMP settings are not team observations. Cgroup metadata describes the exposed
v2 root view and may be unavailable. Build Git metadata is configure-time; dirty
source patches and shared libraries are not archived. JSONL completion validation
loads the dataset in memory, and raw evidence can grow substantially; successful
maximum-quota experiments/peak RSS and cross-platform behavior remain untested.
Clock conversion rejects unsupported overflowing intermediates. Inputs are assumed
stable across hash/read intervals; this is not authentication or hostile-writer
protection. Process isolation/warm-ups do not control frequency, thermal state,
scheduling, cache residency or NUMA placement. Dedicated hardware is required for
performance/scaling conclusions. No race-detector or hosted CI result is claimed.

Phase 5B-3B is ready for review; stop here. Phase 5B-4 and all statistical analysis,
speedups, heuristic tuning and performance claims remain unapproved.

## 2026-10-26 — Phase 5B-2 correctness-checked benchmark replay

### Authorization and implementation

The attached Phase 5B-2 request explicitly authorized this work beyond the old
AGENTS.md gate. Initial branch was `feature/benchmark-runner`, HEAD `4e51c31`,
with a clean working tree. Inspected engineering guidance, README, architecture,
protocol, artifact contract, research records, public/internal engine and graph
interfaces, generator/serializer/verifier and existing tests/build/CI. `rg` was
unavailable; used find/sed and direct reads. No dependencies installed, sub-agents
delegated, commits or pushes. No production shortest-path/storage/selector code
or generator/golden artifacts changed.

Implemented `dynagraph_bench verify`, a separate executable linked against the
existing library. CLI parsing lives in apps; replay/parsing/oracles in a separate
src/benchmark module with its declarations under include/dynagraph/benchmark.
All four policies call the same owning engine initialize/decrease APIs. Existing
shared/equal fast paths, execute_selected behavior and default heuristic thresholds
remain intact. No override, alternate backend path, timing, tuning, calibrated
selection, statistics or Phase 5B-3 work was introduced.

Strict bounded canonical graph/trace parsing matches v1, with checked integer
conversion, exact header/version/count/order/spacing/LF rules and Python's byte
and count quotas. Every trace transition validates endpoints, edge existence,
expected ledger weight and nonincrease. Reference records own independent weights;
every update constructs a separate graph and recomputes fresh Dijkstra, comparing
all graph arrays and all distances. Independent synchronous Bellman–Ford runs on
V<=128/E<=4096. Returned old/new weights, outcomes, improved counts and relevant
decision metadata are checked. Only full verification is implemented; bounded
mode is explicitly deferred. Empty traces are verified at initialization.

JSON schema 1 records configuration, input paths, unverified declared graph digest,
explicit external integrity prerequisite, completed execution/verification/oracle
counts, final flags and independently checked final weights/distances. Failures
exit 2, include stable category/index where applicable, omit final arrays and never
claim success. Stdout can be redirected; no output file is opened by the runner.
See benchmark-replay.md for the complete contract and failure categories.

SHA-256, manifest counts/source/seeds, final hash and provenance/regeneration
remain the existing Python verifier's responsibility. C++ does not attest that
this prerequisite ran and deliberately labels the digest as unverified metadata.
Tests explicitly exercise this boundary, including a false but well-formed digest
accepted as unverified by C++ and rejected by Python. Inputs must remain unchanged
between Python verification and C++ execution.

### Exact verification commands and outcomes

Toolchain: Python 3.14.2, GCC 13.3.0, CMake 3.28.3, existing OpenMP setup.
Executed from repository root:

```sh
python3 tests/test_benchmark_replay.py build/debug/dynagraph_bench
python3 tests/test_workloads.py
python3 tests/test_workload_loader.py build/debug/dynagraph_cli
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --preset debug --output-on-failure
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release --output-on-failure
cmake -S . -B build/sanitize -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined
cmake --build build/sanitize --parallel 2
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir build/sanitize --output-on-failure
ctest --test-dir build/debug -R '^benchmark_replay$' --repeat until-fail:2 --output-on-failure
python3 benchmarks/python/generate.py generate --spec benchmarks/configs/chain-v1.json --output /tmp/dynagraph-5b2-4e51c31
python3 benchmarks/python/generate.py verify --manifest /tmp/dynagraph-5b2-4e51c31/manifest.json
git diff --check
git diff --exit-code -- src/adaptive src/algorithms src/dynamic src/graph include/dynagraph/adaptive include/dynagraph/algorithms include/dynagraph/dynamic include/dynagraph/graph apps/dynagraph_cli.cpp benchmarks/python .github
git status --short
git diff --stat
```

Standalone Python workload tests: 22/22 passed, with unchanged goldens. Existing
loader integration: 1/1 passed (30 C++ invocations). New runner integration:
9/9 passed standalone and in CTest. Debug and Release: warning-free builds under
all existing warning flags and Werror, 19/19 CTest entries passed in each.
Two additional consecutive benchmark_replay CTest repetitions passed (9 Python
tests each), and each success matrix case also checks byte-identical repeated
JSON output.

ASan/UBSan compiled warning-free. First full instrumented CTest inside the sandbox
returned 8: 17/19 entries failed with LeakSanitizer process-inspection/ptrace
restrictions (workload_artifacts and cli_invalid_argument passed). The identical
command was rerun outside the sandbox with escalation approval: 19/19 passed with
leak detection enabled, no sanitizer findings. No tests were disabled or weakened.
Hosted CI was not run; its existing CTest invocations include the new entry.

New integration matrix covers all five generated families, all three weight
families, every policy and both no-effect modes, Python-verifier acceptance,
independent final weights and Bellman–Ford distances, repetitions and input
immutability. Additional fixtures cover repeated edges, equal requests, strict
no-effect decreases, zero cycles/self-loops, unreachable components, a source
with no outgoing edges, empty traces, edgeless graphs and V=128/129 oracle
eligibility. Rejections cover malformed integers, limits (including byte quotas),
wrong versions, malformed headers, truncation, counts/trailing data, noncanonical
ordering/spacing, missing edges, invalid endpoints/source/configuration, old-weight
mismatch, increases, duplicate/unknown/missing options and nonexistent files.
A semantic failure at update 1 confirms exactly one executed/verified update and
false final flags. Identity failures are checked at the external Python boundary.

### Cross-language chain evidence

Generated the checked-in chain specification with the commands above. Python
verified V=8, E=7, source=0, updates=12 and final SHA-256
`be98fdabd7e08cd2e88046fbc4269a9c95cd2481040279c981ffac19d57af927`.
The following exact additional command replayed all policies, checked final graph
bytes against Python replay/manifest and repeated each invocation:

```sh
OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OMP_DYNAMIC=FALSE python3 - <<'CHECK'
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, 'benchmarks/python')
from workloads import Graph, graph_bytes, parse_graph, parse_trace, replay
bundle = Path('/tmp/dynagraph-5b2-4e51c31')
manifest = json.loads((bundle / 'manifest.json').read_bytes())
expected = replay(parse_graph((bundle / 'graph.txt').read_bytes()), parse_trace((bundle / 'trace.txt').read_bytes()))
for policy in ('dijkstra', 'delta-stepping', 'incremental', 'heuristic'):
    command = ['build/debug/dynagraph_bench', 'verify', '--graph', str(bundle / 'graph.txt'), '--trace', str(bundle / 'trace.txt'), '--source', '0', '--policy', policy, '--delta', '16', '--threads', '2', '--no-effect', 'shared_fast_path', '--verification', 'full']
    result = subprocess.run(command, capture_output=True, check=True)
    record = json.loads(result.stdout)
    assert record['success'] and record['updates_verified'] == 12
    assert record['reference_recomputations'] == record['bellman_ford_checks'] == 13
    final = Graph(expected.vertices, tuple((u,v,w) for (u,v,_),w in zip(expected.edges, record['final_weights'])))
    digest = hashlib.sha256(graph_bytes(final)).hexdigest()
    assert final == expected and digest == manifest['final_graph_sha256']
    assert subprocess.run(command, capture_output=True, check=True).stdout == result.stdout
    print(json.dumps({'policy': policy, 'updates_verified': record['updates_verified'], 'reference_recomputations':record['reference_recomputations'], 'bellman_ford_checks':record['bellman_ford_checks'], 'python_verified_final_sha256':digest}))
CHECK
```

All four policies reported 12 verified updates, 13 fresh Dijkstra evaluations,
13 Bellman–Ford evaluations; reconstructed final hashes equaled the manifest.
The runner itself reported no hash verification. New automated tests additionally
exercise the actual generation and verification CLIs on a layered workload.

### Changed files, limitations and review gate

Created:
- apps/dynagraph_bench.cpp
- include/dynagraph/benchmark/replay.hpp
- src/benchmark/replay.cpp
- tests/test_benchmark_replay.py
- docs/benchmark-replay.md

Modified:
- AGENTS.md
- CMakeLists.txt
- tests/CMakeLists.txt
- README.md
- docs/architecture.md
- docs/experimental-protocol.md
- docs/workload-artifacts.md
- docs/research-log.md

Inspected the complete tracked diff and new source/test/header/docs. Whitespace
checks passed. Production algorithm/storage/adaptive code and generator/CLI/CI
unchanged checks passed. There are no unexpected production-code modifications.

Known limits: full mode only; no cryptographic verification or manifest loading
inside C++; runtime default workers can exceed the explicit request quota;
maximum-quota successful executions and peak memory were not tested; full oracle
work can be expensive. Only this Linux/GCC/Python environment was run. No new
race-detector or hosted CI result is claimed. Output/OS/process-fatal failures may
leave incomplete stdout; consumers must require exit 0 and complete success JSON.
Inputs are assumed stable; hashes are not signatures. No observed unresolved
functional/build/sanitizer failures remain after the approved outside-sandbox run.

Phase 5B-2 is ready for review. Stop here. Proposed next phase, only after explicit
approval: define Phase 5B-3 timing boundaries and experimental metadata/repetition
contracts before implementing controlled performance execution. No such work has
started and no performance conclusions are supplied.

## 2026-10-26 — Phase 5B-1 interrupted Codespace recovery

### Inspection and requirement audit

Recovered branch `feature/benchmark-framework` at
`647fa071ab12a170c6c108277aa63d563f12d82f` with the preserved dirty tree.
Read AGENTS.md, experimental-protocol.md, workload-artifacts.md (the repository's
Phase 5B-1 specification), all tracked diffs and all eight untracked files.
No separate Phase 5B-1 requirements file was present. Inspected CMake, presets,
CI, existing research records and production-interface boundaries. No reset,
clean, stash, discard, dependency installation, delegation, commit or push.

The preserved implementation already fully covered the documented functional
scope; no implementation defect or missing functional requirement was found:

- Five exact-count directed graph families: chain, grid, sparse_random, layered,
  disconnected; sorted unique endpoints and checked resource quotas.
- Separate graph/weight/source/trace SplitMix64 streams, integer rejection/Floyd
  sampling, three integer weight distributions and explicit/random sources.
- Strict/equal/repeat/unreachable-tail schedules with specified pool order,
  expected-old weights, immutable records and explicit exhaustion errors.
- Canonical graph/trace serialization, versioned complete provenance manifests,
  SHA-256 before replay, independent endpoint-ledger replay, final graph hashes
  and exact recipe regeneration.
- Strict schema/numeric/count/version/identity validation; duplicate JSON keys,
  malformed graph/trace data, increases, nonexistent edges, hash corruption,
  rehashed semantic corruption, traversal paths and artifact symlinks rejected.
- Exclusive output creation, manifest last, nonzero errors and no overwrite;
  Python tests plus unchanged C++ loader/Dijkstra versus Bellman-Ford checks.

Verification and its phase-gate research record were incomplete at recovery.
Completed them here, preserving every implementation byte. This recovery changes
only this research log. Full phase change set (including recovered files):
AGENTS.md, README.md, docs/architecture.md, docs/experimental-protocol.md,
docs/research-log.md, docs/workload-artifacts.md, tests/CMakeLists.txt,
tests/test_workloads.py, tests/test_workload_loader.py,
benchmarks/configs/chain-v1.json, benchmarks/python/artifacts.py,
benchmarks/python/deterministic.py, benchmarks/python/generate.py,
benchmarks/python/workloads.py. Production headers, sources, CLI, root CMake and
CI are unchanged.

### Exact verification commands and results

Executed from the repository root; Python 3.14.2, GCC 13.3.0, CMake 3.28.3.
Builds reused preserved build directories and completed without warnings.

```sh
python3 tests/test_workloads.py
python3 tests/test_workload_loader.py build/debug/dynagraph_cli
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --preset debug --output-on-failure
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release --output-on-failure
cmake -S . -B build/sanitize -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined
cmake --build build/sanitize --parallel 2
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir build/sanitize --output-on-failure
python3 benchmarks/python/generate.py generate --spec benchmarks/configs/chain-v1.json --output /tmp/dynagraph-5b1-recovery-647fa071
python3 benchmarks/python/generate.py verify --manifest /tmp/dynagraph-5b1-recovery-647fa071/manifest.json
git diff --check
git diff --exit-code -- include src apps CMakeLists.txt .github
git status --short
git diff --stat
```

Python: 22/22 tests passed. Standalone loader: one test with 30 C++ invocations
passed (five families x three distributions x initial/final states). Debug and
Release CTest: 18/18 passed each, including all prior correctness/failure suites.
The sanitizer command initially returned 8 inside the sandbox: 16 entries failed
with LeakSanitizer process-inspection/ptrace errors; workload_artifacts and
cli_invalid_argument passed. After escalation approval, reran the identical
sanitizer command outside the sandbox: 18/18 passed with leak detection enabled;
no ASan, UBSan or leak findings. No tests were disabled or weakened.
Whitespace and unchanged-production diff checks passed. Reviewed the complete
tracked diff plus all untracked source/test/spec/document contents.

### Golden fingerprints and reproducibility

All 15 preserved GOLDEN digests in tests/test_workloads.py matched: initial graph,
trace and replayed final graph for each of the five families. Regeneration also
matched manifest bytes. The CLI test generates under PYTHONHASHSEED 0, 1 and
12345 in different paths, with byte-identical graph/trace/manifest output.
SplitMix64 reference vectors (including uint64 wrap), seed endpoints, sampling
rejection/exhaustion, pool swap order and hand-pinned chain records passed.
No golden values or generator versions were changed during recovery.

Checked-in chain-v1.json CLI roundtrip: V=8, E=7, updates=12, source=0:

- Initial graph: e7338d8f282737a360ae0f65fd731f7c576187e624e5fb94904246a08336ea6c
- Trace: 5e2355594505cdc6536fe11de6fd7ba158578105715c2b9b32445925e72c9d38
- Final graph: be98fdabd7e08cd2e88046fbc4269a9c95cd2481040279c981ffac19d57af927

### Limitations and phase gate

No unresolved observed Phase 5B-1 correctness failures. Only Python 3.14.2 and
this Linux/GCC environment were executed; the documented Python 3.8 minimum and
cross-platform byte stability have not been independently exercised. Goldens are
regression pins, not an independent implementation of the full generator.
Maximum-quota workloads and peak memory were not exercised. Inputs must remain
stable during verification; no concurrent-writer defense or authenticity/signature
protocol exists. I/O failure can leave an incomplete new output directory.
Split labels do not enforce graph-instance isolation. No new race-detector result
or hosted CI result is claimed.

Deferred as specified: further graph families and oracle-targeted localized/broad
traces, timed adaptive-engine replay, experimental metadata collection, repetition,
analysis, calibration/learning, batch/increase/parallel repair, delta tuning,
topology changes and concurrent mutation. No timing code, benchmark measurements
or performance claims were added. Phase 5B-1 is ready for review. Stop here;
proposed next phase is Phase 5B-2 only after explicit approval and scope agreement.

## 2026-10-26 — Phase 4B-2 deterministic adaptive heuristic

### Authorization, inspection and implementation

The user explicitly approved Phase 4B-2 after the Phase 4B-1 merge. Verified
feature/adaptive-heuristic at ee2db24 with a clean working tree before edits;
no unrelated work existed. Inspected engineering instructions, current adaptive
and incremental APIs/implementations, existing correctness/failure tests, CMake,
architecture, protocol and research record. Updated AGENTS.md for this scope and
the next approval gate. No dependencies installed, agents delegated, commits,
pushes, source resets/discards, calibrated models, ML, online learning or benchmark
infrastructure. Phase 4B-3 and Phase 5 were not started.

Appended PolicyKind::heuristic and four reason values without changing existing
enum values. PolicyConfig appends HeuristicConfig with small_graph_edges=4096,
repair_max_degree=32 and parallel_min_edges=65536. All are unsigned EdgeOffset
thresholds and explicit uncalibrated hypotheses, not measured optimal values.
Default policy remains always_incremental; heuristic use is opt-in. Existing
three-field aggregate configs retain valid defaults. All initialization validates
small_graph_edges < parallel_min_edges, even for fixed policies, after existing
enum/no-effect/delta/thread checks. Zero small/degree thresholds are valid; equal
or reversed small/parallel thresholds reject without constructing a state. No
threshold arithmetic can overflow; uint64-scale comparisons are tested.

For a valid update requiring execution, a forced override takes precedence. With
no override, the first matching heuristic rule is E<=small -> Dijkstra/small_graph;
degree(destination)<=repair -> incremental/local_degree;
E>=parallel_min and explicit requested threads>=2 -> delta/parallel_work;
otherwise incremental/fallback. Equal/shared no-effect bypasses precede selection
and retain no selected strategy. Under execute_selected, strict no-effect updates
also use the ordered policy. Fixed policies and overrides retain forced. Invalid
override enums still reject before request preparation. The same transactional
execution paths and all post-commit nonthrowing assertions remain unchanged.

Thread request 0 remains runtime-default behavior for forced delta, but specifies
no explicit two-worker heuristic budget; it therefore fails the parallel rule.
This avoids runtime/environment-based selection for fixed configuration. Counts
1/2 and selected 4 are tested. No runtime team query/tuning is added. Selection
reads graph edge count, at most one constant-time CSR degree, and immutable config;
it does not traverse, allocate, sample, read timings/counters/history, or use any
current affected-region observation. Parallel timing/work counts can vary while
strategy, reasons and distances remain deterministic across instrumentation modes.

No graph ownership, incremental public contract, journal, recomputation commit,
SSSP algorithm or CLI code changed. CMake/workflow settings remain unchanged;
the extended tests use the existing two CTest entries. No performance/novelty
claim is made. Defaults and the degree-one counterexample are documented.

### Exact commands and observed verification

Executed from repository root using the existing reconfigured build directories:

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --test-dir build/debug -R '^adaptive_(sssp|failure)$' --verbose
ctest --preset debug --output-on-failure
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release --output-on-failure
cmake -S . -B build/sanitize -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined
cmake --build build/sanitize --parallel 2
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir build/sanitize --output-on-failure
ctest --test-dir build/debug -R '^adaptive_(sssp|failure)$' --repeat until-fail:20 --output-on-failure
ctest --test-dir build/release -R '^adaptive_(sssp|failure)$' --verbose
git diff --check
git diff --exit-code -- include/dynagraph/dynamic src/dynamic include/dynagraph/graph src/graph include/dynagraph/algorithms src/algorithms apps CMakeLists.txt tests/CMakeLists.txt .github
```

GCC 13.3.0, CMake 3.28.3, OpenMP 4.5, two logical CPUs. All builds succeeded
warning-free with unchanged C++17/OpenMP and -Wall -Wextra -Wpedantic -Wconversion
-Wshadow -Werror settings. Debug full CTest: 16/16 passed (4.44 s); Release: 16/16
(1.84 s); ASan/UBSan: 16/16 (15.72 s). All Phase 1–4B-1 regression/failure entries
passed. No failed, skipped, disabled or weakened tests; no build warnings occurred.
CTest elapsed times are verification observations under shared host load, not
benchmarks or evidence of speedup.

Sanitizer CTest ran outside the sandbox with approval because earlier phases
established the LeakSanitizer/ptrace restriction. Leak detection remained enabled;
no ASan, UBSan or leak findings, hangs or timeouts. No TSan pass is claimed and
the older startup failure does not establish race freedom. Hosted CI for these
uncommitted changes remains unverified; its unchanged workflow runs the full
registered suites. Whitespace and unchanged-core diff checks passed.

### New tests and failure/overhead checks

Adaptive correctness now has eight groups. Existing forced cases remain, and
shared/execute-selected tests include all four policies. Eleven explicit boundary
configs use a verified E=7 graph with changed destination degree 2. They cover
exact small/parallel boundaries, their neighbors, equal degree threshold, rule
precedence, worker budgets 0/1/2/4 and maximum unsigned threshold values. Effective
updates repeat, override every backend, and resume heuristic selection. Opt-in
defaults, invalid threshold/config/request/override cases, rollback and reuse are
checked. Instrumented/plain engines agree on exact decisions and all distances;
reason predicates include earlier-rule precedence. Fresh Dijkstra uses separately
updated input records, and small graphs use the independent Bellman–Ford oracle.

New randomized stream: mt19937 seed 0x4B22026, 72 graphs with 1–12 vertices,
every source, 24 requests per nonempty graph/source, four graph families, small
and full-range weights, all six deltas, both no-effect modes, workers 0/1/2/4,
explicit varied thresholds, repeated edges, unchanged requests and mixed automatic
and forced schedules. Three of four requests are automatic. The old seed
0x4B12026 random/switching and independent-engine tests remain intact.

Counterexample fixtures each have 512 vertices, 511 edges, changed-edge labels
d[0]=0/d[1]=100 and destination degree 1. Local-degree repair improves 2 vertices
in the disconnected-tail graph and 511 along the reachable chain. This proves
degree does not bound affected region; it does not measure which backend is faster.

The failure entry now has four groups: retained forced host sweeps, automatic
host sweeps/allocation equivalence, OpenMP-safe region failures, and initialization
plus bypass checks. Automatic selection is configured to actually choose each
backend. Its host allocation counts/sizes/pre-post-team positions match forced
execution of that same backend, in both instrumentation modes, checking zero extra
selection allocations. Audit confirms no selection traversal. No latency claim
is inferred. Each automatic fault preserves graph/distances/caller metrics, retries
automatically on that engine, and then switches successfully to another backend.
All four policies' shared bypasses allocate no backend storage.

Observed host positions per forced or automatic sweep: Dijkstra 12 without/12
with metrics; delta 9/10 (including 1/2 post-team allocations); repair 16/16,
with 14 partial-write failures per instrumentation mode. Thus each failure-test
run injects 169 exceptions: 150 host update positions, 15 initialization positions,
4 retained OpenMP-safe region triggers. Fifty-six occur after tentative repair
writes; six after team exit. Debug and Release counts agree. Scalar selection,
summary and commit do not allocate; no fabricated failure stage is claimed.

Final Debug adaptive correctness/failure entries each passed 20 consecutive CTest
repetitions, 40 executions (19.07 s). This includes 3,380 selected allocation
exceptions, 1,120 after tentative repair writes, with successful rollback/retry/
switching and no timeout or mismatch. Separate verbose Release tests passed.

### Files and gate

Modified only:
- AGENTS.md
- include/dynagraph/adaptive/adaptive_sssp.hpp
- src/adaptive/adaptive_sssp.cpp
- tests/test_adaptive_sssp.cpp
- tests/test_adaptive_failure.cpp
- README.md
- docs/architecture.md
- docs/experimental-protocol.md
- docs/research-log.md

No new files, dependencies, algorithm changes or known local correctness/build/
sanitizer failures. Existing serialized-access, view invalidation and recoverable
C++ exception limitations remain. The heuristic can choose expensive repair on
large affected regions; staging can make recomputation costly. Requested workers
need not equal actual workers. Fault injection covers selected ordinary allocations
and the existing inspected 16-byte publication target, not every runtime/OS failure.
Policy overhead latency, threshold quality, speedups and generalization remain
unmeasured. Defaults have no empirical optimality claim.

Phase 4B-2 is complete; stop for review. The correctness foundation supports a
separately approved Phase 4B-3 or Phase 5 design, but calibrated costs and performance
claims require reproducible measurements and held-out evaluation. No later phase
has begun and nothing was committed or pushed.

## 2026-10-26 — Phase 4B-1 forced-strategy engine core

### Authorization, repository state and implementation

The user approved Phase 4A and explicitly authorized only Phase 4B-1. Started on
main at c171546 (Phase 3B PR #1 merge), with a clean working tree. Inspected the
engineering rules, storage, both recomputation algorithms, incremental state,
test harness/oracle, fault injectors and CMake. Phase 3B and its registered tests
were present. Updated AGENTS.md to retain the next Phase 4B-2 gate. No dependencies
installed, sub-agents used, commits, pushes, resets, or source discards. No heuristic,
model, batch/increase support, benchmark orchestration or Phase 5 work was added.

Added AdaptiveSSSPEngine with exactly one authoritative IncrementalSSSPState and
const PolicyConfig. Factories and member construction use direct prvalues with
guaranteed C++17 elision; neither nonmovable object relies on named-local NRVO or
an extra heap wrapper. Every policy initializes with Dijkstra. Public strategy
choices are dijkstra, delta_stepping and incremental; policies are their three
always variants. An optional per-call override supports forced switching. Config
also chooses shared_fast_path/execute_selected and fixed parallel delta/threads.
Enums, positive delta and nonnegative threads are validated, even if the default
policy is nonparallel. Const views expose no mutable state.

Factored only the existing repair request preparation and dispatch: a private
PreparedDecrease carries validated/narrowed endpoints, old/new weights and checked
seed. Public standalone decrease and the engine reuse preparation; requests never
escape or persist across calls. Original validation order/messages, journal,
queue publication ordering, instrumentation and rollback remain intact. One friend
class is the only new access to authoritative storage. No public unchecked result
adoption or mutable accessor was added. CSR, Dijkstra, delta, CLI and workflow
were not changed.

Equal weights bypass every backend without graph writes. Shared strict no-effect
requests commit only the weight and report no executed strategy/work, consistently
for all policies and overrides. execute_selected dispatches a backend for every
strict request; full strategies recompute, while incremental can stop after its
intrinsic seed check. Decisions explicitly distinguish these cases.

Private recomputation copies CSR temporarily, writes the staged weight, executes
exactly the selected algorithm, checks source/size/zero-source label and every
distance for monotonicity, reachability and cap consistency, and counts distinct
improvements. All allocations, including delta result and per-thread metric
preparation, finish before commit. Then authoritative replace_weight is the last
potentially throwing call and distance-vector swap commits the completed result.
The inspected storage setter validates/locates before its only scalar write and
cannot throw afterward. Compile-time assertions enforce nonthrowing swap, scalar
publication/copy/move and relevant destructors. Scratch marks remain clear; no
extra repair or checked-adoption Dijkstra is run for synchronization. Future
repair is immediately current. Distance element pointers/iterators must be
reacquired after recomputation; standalone repair retains stable storage.

AdaptiveMetrics is a locally staged scalar aggregate with decision, work-collected
flag, existing repair/Dijkstra metrics and a saturated delta work summary. Only
the executed backend's fields populate; all others reset. Delta actual team size
is optional and absent unless measured. Recoverable exceptions preserve old graph,
distances and caller metrics; no silent retry happens. Parallel exceptions use
existing collective shutdown. Process-fatal OpenMP/OS failures are not recoverable
C++ exceptions. All access must be serialized against updates; independent engines
have independent ownership and may query concurrently. No timing was added.

### Exact verification commands and outcomes

Commands executed from repository root; existing build directories were
reconfigured. Final builds/tests include the additional no-throw assertions and
wide destination-validation case added during audit.

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --test-dir build/debug -R '^adaptive_(sssp|failure)$' --verbose
ctest --preset debug --output-on-failure
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release --output-on-failure
cmake -S . -B build/sanitize -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined
cmake --build build/sanitize --parallel 2
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir build/sanitize --output-on-failure
ctest --test-dir build/debug -R '^adaptive_(sssp|failure)$' --repeat until-fail:20 --output-on-failure
ctest --test-dir build/release -R '^adaptive_(sssp|failure)$' --verbose
git diff --check
git diff --exit-code -- include/dynagraph/graph src/graph include/dynagraph/algorithms src/algorithms apps .github
```

Environment: GCC 13.3.0, CMake 3.28.3, OpenMP 4.5, two logical CPUs. All builds
passed warning-free with unchanged -Wall -Wextra -Wpedantic -Wconversion -Wshadow
-Werror, -std=c++17 and -fopenmp. Release includes -O3 -DNDEBUG; checks remain
active. Final full suites passed Debug 16/16 (11.40 s), Release 16/16 (8.42 s),
ASan/UBSan 16/16 (17.93 s), including all existing Phase 1–3 tests. There were no
correctness/build/test failures and no tests were disabled or skipped. Elapsed
CTest times are verification observations under shared load, not benchmarks.

The exact sanitizer CTest invocation ran outside the sandbox with approval to
avoid the previously established LeakSanitizer/ptrace restriction. Leak detection
stayed enabled; no ASan, UBSan or leak findings, hangs or timeouts. No knowingly
unsupported sandbox retry was needed. No TSan result is claimed; the older startup
failure remains a limitation, not evidence of race freedom. The unchanged CI
workflow discovers the new tests in its Debug/Release and full sanitizer jobs;
hosted CI for these uncommitted changes is unverified.

### Correctness, switching and failures

Two new CTest entries contain five correctness groups and three failure groups.
Every accepted correctness update compares both instrumentation modes with fresh
Dijkstra over independently updated input records, and small graphs also use
Bellman–Ford. Tests check all graph arrays, monotonicity, invariant reachability,
distinct improved count, decision/outcome, active/inactive metrics and measured
team metadata. All nine ordered pairs of three strategies are exercised, followed
by additional repairs/recomputations and zero-cycle changes. Shared/execute modes
cover every policy, equal/strict no-effect/unreachable-tail updates, singleton
positive loops at cap=0, all six deltas, maximum weights and wide distances.
Invalid weights/endpoints/edges/configurations/forced enums preserve state/metrics;
ownership tests cover lvalue isolation, rvalue transfer, nonzero sources and direct
nonmovable construction. Two async host calls each run 24 mixed updates on their
own instrumented/plain engines while sharing only immutable input.

Randomized switching: mt19937 seed 0x4B12026, 72 graphs, 1–10 vertices, every
source, 18 requests per nonempty graph/source. Families are sparse/dense random,
hub/fan-in and chain graphs; small/full-range weights, equal requests, cycling
policies/overrides, both no-effect modes, deltas {1,2,3,16,UINT32_MAX,UINT64_MAX},
requested threads 2 and selected 4. CTest fixes default workers=2, thread limit=8,
and dynamic teams off. These are correctness checks, not multicore scaling data.

The isolated adaptive failure executable uses atomic worker mode/one-shot flags;
only the host accesses allocation counters and fixed-size distance traces outside
parallel regions. The existing sequential injector is never used by workers.
All observed host allocations are faulted with/without metrics. Counts were the
same in Debug and Release:

| Strategy | Without metrics | With metrics | Observed after tentative writes | Observed after parallel team exit |
| --- | --- | --- | --- | --- |
| Dijkstra | 12 | 12 | 0 | 0 |
| Delta-stepping | 9 | 10 | 0 | 1 without / 2 with metrics |
| Incremental | 16 | 16 | 14 per mode | 0 |

The first three recomputation positions are checked as staged CSR array copies;
subsequent positions include algorithm allocations. Delta's post-team faults are
the distance result vector and optional per-thread metric vector. Scalar checks,
summary aggregation and vector-swap commit do not allocate, so no fictitious
allocation-failure coverage is claimed for them. Two one-shot parallel modes
(first region allocation and 16-byte post-CAS Entry append) each fail with/without
metrics, four region faults total. The publication target uses the same inspected
allocation-size contract as the existing delta failure test. Initialization has
15 fault positions. Each failed update preserves all graph arrays, distances and
sentinel metrics, retries successfully on that engine and then switches to a
different strategy. All policies' shared bypasses allocate no backend storage.

Total: 94 selected allocation exceptions per failure-executable run (75 host
update positions, 15 initialization positions, 4 parallel-region triggers),
including 28 after tentative repair writes and 3 after team exit. Final Debug
correctness/failure entries each passed 20 consecutive repetitions, 40 executions
in 10.34 s: 1,880 selected exceptions, including 560 partial-repair and 80 region
faults across those repetitions. No mismatch/hang/timeout. Separate verbose
Release tests passed. Whitespace and unchanged-core diff checks passed.

### Files, limitations and next gate

Created:
- include/dynagraph/adaptive/adaptive_sssp.hpp
- src/adaptive/adaptive_sssp.cpp
- tests/test_adaptive_sssp.cpp
- tests/test_adaptive_failure.cpp

Modified:
- AGENTS.md
- CMakeLists.txt
- tests/CMakeLists.txt
- include/dynagraph/dynamic/incremental_sssp.hpp
- src/dynamic/incremental_sssp.cpp
- README.md
- docs/architecture.md
- docs/experimental-protocol.md
- docs/research-log.md

No unresolved local build, correctness or sanitizer failures found. Recompute
adds O(V+E) graph copy and O(V) result scan plus allocation/cleanup; these costs
must be charged in future experiments. Peak memory includes a temporary graph,
new result and backend scratch. Engine distance element views invalidate after
recomputation. Fixed topology/finite weights/source and serialized mutation remain
requirements. Fault injection covers ordinary C++ allocations, not every aligned
allocator, runtime or hardware failure; its targeted publication size is tied to
the inspected current implementation. Maximum graphs/counter saturation are not
practically exercised. No heuristic/calibrated selection, tuning, benchmarking,
batch/increase support, adaptive-policy claim or measured speedup was introduced.

Phase 4B-1 is complete; stop for review. Phase 4B-2 can now add a separately
approved deterministic heuristic over cheap pre-execution features, preserving
shared fast-path fairness, failure semantics and coherent forced baselines.
Threshold calibration and performance assessment require later measured evidence;
no subsequent phase has begun and nothing was committed or pushed.

## 2026-10-26 — Phase 3B transactional incremental SSSP

### Authorization and implementation

The user explicitly approved the Phase 3A design and requested Phase 3B
implementation. Inspected AGENTS.md, the graph/SSSP/Dijkstra/delta APIs and
implementations, CMake, test harness/oracles, workflow and existing documentation.
Started on main at 9eb51be with a clean working tree. Updated AGENTS.md for this
authorization and the Phase 4 gate. No dependencies installed, sub-agents used,
commits, pushes, source resets or discarded files. Phase 4 was not started.

Added IncrementalSSSPState with owned CSR, fixed source, owned distances, and one
byte of journal membership per vertex. Factories initialize through Dijkstra or
validate an incoming result by recomputing Dijkstra before adoption. Inputs are
passed by value (lvalue copies, rvalue transfer); failed initialization may consume
rvalues. The state has no unchecked public constructor or mutable accessors and
is noncopyable/nonmovable; guaranteed C++17 return elision supports factories.
Source/graph rebinding is unavailable. External changes to a copied input graph
cannot invalidate a state. Views retain storage but reflect current values;
all access must be serialized against an update.

Single-edge decrease returns unchanged_weight, weight_only, or distances_repaired
with old/new weights and distinct improved count. Invalid endpoints/missing edges,
unsupported weights and increases reject without state/metric changes. Successful
strict decreases always commit their graph weight, even with unchanged distances.
No batches, increases, topology edits, parallel repair or adaptive work was added.

The deterministic min-heap propagates strict decreases through outgoing CSR,
filters stale records, and substitutes the proposed weight through a local view.
A first-change undo entry is allocated before marking a vertex; queue insertion
succeeds before its distance write. The nonthrowing guard restores original
distances and marks on failure. Staged scalar metrics are published only on
success. Existing CSRGraph::replace_weight is the final potentially throwing
operation; its only write follows validation/lookup and has no throwing work
afterward. Remaining publication and journal/queue cleanup cannot throw. There
are no production fault hooks or global state. No full distance copy, full mark
clear, or Dijkstra call occurs inside decrease(). No CSR, Dijkstra, delta, CLI or
workflow changes were necessary.

Checked addition caps candidates at (V-1)*UINT32_MAX after source validation.
Infinity is never subtracted/added, and finite accepted labels never exceed the
cap. Correctness uses old distances as upper bounds on new distances, preserves
that bound on relaxation, and restores shortest-path inequalities by queue
publication. Simple shortest-path prefixes fit the cap. Nonnegative weights and
min-heap order mean each improved row is scanned once; repeated improvements
before a valid pop create stale entries. Strictness handles zero cycles and equal
paths. Fixed topology with finite weights preserves reachability.

For A distinct improved vertices, E_A outgoing edges of those vertices, R strict
label improvements including the seed, and H peak queue entries, update time is
O(log(outdegree(u)+1) + A + E_A + R log(R+1)), R<=E_A+1. Local storage is O(A+H),
persistent repair arrays O(V) beyond CSR. No-distance-change updates perform no
propagation scan/allocation. Large affected regions may make repair slower than
recomputation; no speedups or novelty are asserted. Metrics and exact algorithm,
transaction, ownership and measurement contracts are documented in architecture.md,
README.md and experimental-protocol.md.

### Exact verification commands

Executed from the repository root. Existing build directories were reconfigured;
the new source/tests were compiled in all three configurations. Builds and full
suites were repeated after adding the explicit positive self-loop cap-zero case.

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
ctest --test-dir build/debug -R '^incremental_failure$' --verbose
ctest --test-dir build/release -R '^incremental_(sssp|failure)$' --verbose
ctest --test-dir build/debug -R '^incremental_(sssp|failure)$' --repeat until-fail:20 --output-on-failure
git diff --check
git diff --exit-code -- include/dynagraph/graph src/graph include/dynagraph/algorithms src/algorithms apps .github
```

Environment: GCC 13.3.0, CMake 3.28.3, OpenMP 4.5, two logical CPUs. Final builds
passed without warnings under unchanged -Wall -Wextra -Wpedantic -Wconversion
-Wshadow -Werror, C++17 and OpenMP flags. Release flags include -O3 -DNDEBUG;
checks remain active in the dependency-free harness. The first Debug build found
one new test-only range-loop copy warning. Changed the loop variable to a const
reference; no warning flag was disabled. No correctness-test failure was observed.

Final complete suites: Debug 14/14 passed (11.61 s), Release 14/14 (10.24 s),
ASan/UBSan 14/14 (16.48 s). All existing Dijkstra, delta-stepping, storage, OpenMP
and CLI entries passed. These elapsed CTest times reflect shared-host load and
are not performance comparisons. No tests skipped, disabled, or weakened.

The sanitizer CTest command ran outside the sandbox with approval because the
previous phase established that sandbox ptrace prevents LeakSanitizer. Leak
detection remained enabled; no ASan, UBSan, leak finding or timeout occurred.
This phase did not run another knowingly unsupported sandbox sanitizer attempt.
No TSan pass is claimed; the previously recorded startup failure is not evidence
of race freedom. Repair itself is sequential and requires serialized access.
The unchanged CI workflow includes all registered tests in Debug/Release and
ASan/UBSan jobs. Hosted CI for these uncommitted changes remains unverified.

### Correctness, fault coverage and repeat results

The two new CTest entries contain five correctness groups and three failure groups.
Randomized correctness uses mt19937 seed 0x31B2026, 120 dense/sparse graphs with
1–16 vertices, every source, 24 updates per nonempty graph/source, small/full-range
weights, equal requests and repeated edges. Each update runs instrumented/plain
states, independently updates input records, rebuilds a reference graph, compares
fresh Dijkstra and small-graph Bellman–Ford, and checks monotonicity, reachability,
all graph topology/weight arrays, outcomes and counter identities. Hand cases
cover local/multi-hop repair, invalid updates, unchanged/weight-only requests,
unreachable tails, zero cycles, equal paths, source/non-source self-loops, a
singleton positive loop at cap=0, edges into source, exact stale-queue accounting,
6,000-vertex max-weight chains and 900-vertex hubs. Ownership/adoption tests check
original graph isolation, independent states, stable views, invalid sources,
dimensions and stale/malformed result rejection.

The sequential failure executable faults every observed ordinary C++ allocation:
14 initialization positions, 15 checked-adoption positions, 16 repair positions
without metrics and 16 with metrics (61 injected exceptions per executable run).
Fourteen repair positions per mode observe already changed live distances before
throwing (28 failures after partial tentative repair). Fixed-size traces locate
the initial journal/heap insertions and later journal/heap growth; they neither
allocate nor modify the observed state. After each repair failure all graph
arrays/distances and sentinel metrics match the pre-call snapshots, a same-state
retry improves all 95 affected vertices, and a different update succeeds.
Initialization failures preserve lvalue inputs and allow retry. An armed allocator
confirms unchanged/weight-only requests perform zero propagation allocations.
Debug and Release verbose checks reported the same allocation counts.

Final Debug incremental correctness/failure entries each passed 20 consecutive
CTest repetitions: 40 executions in 16.35 s, including 1,220 selected allocation
failures and 560 failures observed after tentative writes across the failure-test
repetitions. No mismatch, hang or timeout occurred. Whitespace verification passed;
the separate diff check confirmed graph, recomputation algorithms, CLI and workflow
remain unchanged.

### Files and gate

Created:
- include/dynagraph/dynamic/incremental_sssp.hpp
- src/dynamic/incremental_sssp.cpp
- tests/test_incremental_sssp.cpp
- tests/test_incremental_failure.cpp

Modified:
- AGENTS.md
- CMakeLists.txt
- tests/CMakeLists.txt
- README.md
- docs/architecture.md
- docs/experimental-protocol.md
- docs/research-log.md

No unresolved local correctness, warning, build or sanitizer failures. Maximum
representable graphs and practical counter saturation cannot be exercised here;
fault injection covers ordinary C++ allocations, not all OS/hardware/aligned
allocator failures. The state is intentionally fixed-identity/nonmovable. Strong
exception guarantees apply to an existing state; by-value initialization can
consume rvalues. Transactions require serialized access, including existing const
views. Paths, batches, increases, parallel repair, shared graph state, adaptive
scheduling and benchmark orchestration remain unimplemented.

Phase 3B is complete. Stop and await approval. Recommended Phase 4 design topics:
fair combined update-and-query timing boundaries, initialization amortization,
reproducible traces/metadata, inexpensive predecision features, held-out workload
evaluation, and state coherence/switching costs when recomputation is selected.
Actual affected fraction/current repair duration are outcomes, not free features
before deciding. Controlled multicore experiments remain necessary for scaling
claims. No Phase 4 implementation was begun and nothing was committed or pushed.

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

## 2026-10-28 — Phase 5C-2C implementation and verification

User authorization supersedes the older 5C-2B scope gate in AGENTS.md: 5C-2B
was independently audited/approved; only missing 5C-2C test/docs work is authorized.
Initial working tree already contained modified AGENTS.md, experimental-protocol,
research-log, tests/CMakeLists.txt and test_system_adversarial.cpp, plus untracked
5C-2B concurrency support/tests/docs and tsan_controls. These were preserved.
Inspection found existing one-shot preparation/publication failure checks, host
allocation sweeps and mixed-history rollback/recovery; no 4/20/100 epoch failure
profiles or deterministic merge-stage target existed. No 5C-2B implementation
was redone. See validation-parallel-failure.md for coverage and limitations.

This phase changes tests/test_adaptive_failure.cpp only to extend its isolated
injector with merge observation; adds tests/test_parallel_failure.cpp and
tests/test_parallel_failure_runtime.py; appends test registration to
tests/CMakeLists.txt and documentation to experimental-protocol.md, this log and
new validation-parallel-failure.md. All existing test bodies remain. Production,
public headers, benchmarks, CI and Phase 5C-2A evidence are untouched. No installs,
commits, pushes or PRs. Fixed corpus has no random seed or generated dataset.
Raw evidence: ignored results/validation/phase5c2c, metadata.json records GCC
13.3.0, CMake 3.28.3, Linux x86_64 and revision d840469bafda76ebb601dad9faf809259658584a.

Commands and final outcomes (all builds warnings-as-errors):

- `cmake --preset debug`; `cmake --build --preset debug --parallel 2`;
  `ctest --preset debug`: final **27/27 passed**, exit 0, 146.44 s
  (debug-final-ctest.log). An earlier complete Debug run also passed 27/27.
- `cmake --preset release`; `cmake --build --preset release --parallel 2`;
  `ctest --preset release`: final **27/27 passed**, exit 0, 151.26 s
  (release-final-ctest.log). An earlier run failed only the new receipt check
  while source/receipt and built executable differed during addition of standalone
  coverage; final rebuilt results supersede it, raw log retained.
- Sanitizer configure: `cmake -S . -B build/sanitize -DCMAKE_CXX_COMPILER=g++
  -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON
  '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer'
  -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined`; build with
  `cmake --build build/sanitize --parallel 2` (exit 0).
- `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1
  UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1
  ctest --test-dir build/sanitize --output-on-failure` inside sandbox finished **2/27 passed, 25 failed**, exit 8,
  because LeakSanitizer reports fatal ptrace incompatibility, including trivial
  project_info/openmp tests; this is not a clean sanitizer result. Raw
  sanitize-ctest.log retained. The same full command outside sandbox finished
  **26/27 passed**, exit 8, 257.60 s: existing dijkstra exceeded its unchanged
  10-second timeout (10.06 s). All other tests, including old failure/concurrency
  tests and new parallel_failure_fast, passed. No sanitizer finding was reported
  in that outside-sandbox run. Concurrent verification runs imposed variable load;
  no definitive cause of the timeout is established.
- Outside sandbox with identical sanitizer options,
  `ctest --test-dir build/sanitize -R '^dijkstra$' --output-on-failure`:
  **1/1 passed**, exit 0, 2.80 s. This isolated pass does not rewrite the full-run
  timeout as a fully passing suite.
- For each build directory debug/release/sanitize,
  `python3 tests/test_parallel_failure_runtime.py build/<dir>/tests/test_parallel_failure
  <profile>` for fast/stress/extended: **all nine invocations exit 0**. Sanitizer
  commands use the same ASAN/UBSAN options outside sandbox. Each receipt records
  4/20/100 epochs per mandatory stage and metrics mode, with 72/360/1800 faulted
  calls respectively. Healthy probe observed 2 workers, requested 2. Failed-call
  actual teams remain unavailable; no inference from the probe is asserted.
- Registration verification: `cmake --preset release
  -DDYNAGRAPH_ENABLE_CONCURRENCY_STRESS=ON
  -DDYNAGRAPH_ENABLE_CONCURRENCY_EXTENDED=ON`; `ctest --test-dir build/release
  -R '^parallel_failure_' --output-on-failure`: **3/3 passed**, exit 0, 18.55 s.
  Both options restored OFF using the same configure command with OFF values.
- `git diff --check`: exit 0. No dependencies installed. Existing tests/tsan_controls
  and ignored phase5c2a evidence preserved; no intentional-race control registered.

Uncovered: simultaneous worker failures, every later preparation/publication/merge
allocation, arbitrary ABI/layouts and all possible schedules/runtime allocation
paths. Targeting is fixture-specific and source-derived; mandatory stage misses
fail rather than silently skip. Existing history/sweep checks remain complementary.
Collective barrier and exception exits returned within bounds for all new profiles;
this does not prove general deadlock freedom or race freedom. The race-detector
acceptance gate remains unmet. ASan+UBSan full-run timeout remains a verification
limitation despite the isolated pass. Next action is independent review of 5C-2C
implementation/evidence and acceptance of these limitations; stop here pending
user direction, with no later production or performance phase authorized.

## 2026-10-28 — Phase 5C-2C verification gate repair

User explicitly authorized a project-local .venv-analysis and installation of
exact requirements-analysis.txt pins. No Phase 5C-2C implementation was redone.
The previous cached analysis interpreter /tmp/dynagraph-analysis-venv/bin/python
no longer existed. Its failed configure probe omitted analysis_import,
analysis_stats, analysis_integration and analysis_figures: 30 previous default
entries minus four plus the new parallel_failure_fast yielded 27. Those historical
runs were incomplete coverage. Their raw logs remain in phase5c2c unchanged.

Environment restoration commands:

```sh
/usr/bin/python3 -m venv .venv-analysis
/home/codespace/.python/current/bin/python3 -m venv .venv-analysis
.venv-analysis/bin/python -m pip install -r benchmarks/requirements-analysis.txt
.venv-analysis/bin/python -m pip check
```

The first command failed because system Python 3.12 lacked ensurepip. A subsequent
--copies attempt with Python 3.14 failed against the partial environment's
system-interpreter symlink (read-only target). Only new partial environment
symlinks were removed, then Python 3.14.2 created the environment successfully.
No existing build directory or retained evidence was deleted. The initial pip
attempt failed DNS inside the sandbox; its outside-sandbox retry succeeded,
exit 0. No pinned package incompatibility or version substitution. No system
package install/upgrade; pip was not upgraded. Added /.venv-analysis/ to .gitignore.

Verified interpreter: /workspaces/Dynagraph-HPC/.venv-analysis/bin/python,
Python 3.14.2, GCC 13.3.0. Exact metadata checks through pinned_versions() matched
matplotlib 3.10.8, numpy 2.4.1, contourpy 1.3.3, cycler 0.12.1,
fonttools 4.61.1, kiwisolver 1.4.9, packaging 25.0, pillow 12.1.0,
pyparsing 3.3.2, python-dateutil 2.9.0.post0, six 1.17.0.
Matplotlib Agg initialized and rendered a 17291-byte PNG in memory; pip check
reported no broken requirements. Exact environment JSON and install output:
results/validation/phase5c2c-repair/ (ignored, separate from original evidence).

Reconfigured Debug/Release using their presets with explicit
-DDYNAGRAPH_ANALYSIS_PYTHON=/workspaces/Dynagraph-HPC/.venv-analysis/bin/python.
Sanitizer used the existing explicit CMake configuration with GCC Debug,
-fsanitize=address,undefined -fno-omit-frame-pointer and matching linker flags.
All four stress/extended options were OFF for defaults. Each generated list
was compared against retained phase5c2b/<build>-final-CTestTestfile.cmake plus
parallel_failure_fast: exactly 31 names, missing=[], extra=[], all three builds.
No tracked CMake infrastructure modification was needed.

Exact configure/build/test argv, environments, exit codes and wall times are in
phase5c2c-repair/commands.json; verify.py preserves the sequential orchestration.
Each build used `cmake --build build/<build> --parallel 2`, then
`ctest --test-dir build/<build> --output-on-failure --parallel 1`.
No verification jobs overlapped. Debug, then Release, then ASan+UBSan ran outside
the sandbox. Common environment PYTHONDONTWRITEBYTECODE=1, PYTHONHASHSEED=0;
sanitizer additionally ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 and
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1.

| Configuration | Registered | Passed | Failed | Exit | CTest wall time |
|---|---:|---:|---:|---:|---:|
| Debug | 31 | 31 | 0 | 0 | 47.56 s |
| Release | 31 | 31 | 0 | 0 | 42.53 s |
| ASan+UBSan | 31 | 31 | 0 | 0 | 81.37 s |

Process wall times including launch overhead were 47.570330, 42.546398 and
81.401338 seconds. Dijkstra passed in 0.96, 0.05 and 3.00 seconds respectively;
its 10-second timeout is unchanged. No failures required retries. Historical
outside-sandbox sanitizer 26/27, Dijkstra timeout at 10.06 s, and isolated
Dijkstra pass at 2.80 s remain accurately recorded above. The new full pass does
not retroactively alter them or establish the original timeout's root cause.

After all full suites ended, enabled both concurrency optional tiers on Release
and confirmed 35 registrations including concurrency_stress/concurrency_extended
and all three parallel_failure profiles. Re-ran only parallel_failure_fast and
parallel_failure_stress: 2/2 passed, exit 0, 0.14 s; restored both options OFF
and confirmed 31 default registrations again. Exact commands/optional lists are
in optional-commands.json and optional-registration.json. Existing unchanged-source
extended receipts retain 1800 faulted calls; no extended rerun was necessary.
Fast/stress counts remain 72/360. Retained Phase 5C-2B source hashes match for
concurrency tests/support and adversarial extraction; corpus receipts preserve
288/5760/57600 queries. All eight TSan controls match their retained hashes.

Repair tracked changes: .gitignore, docs/validation-parallel-failure.md,
docs/research-log.md and docs/experimental-protocol.md. Existing untracked test,
support, documentation and tsan_controls files retained. Final git diff --check
passed; comparison against d840469 for src/include/apps/benchmarks/cmake,
root CMake files and .github is empty. No production/API/benchmark timing,
heuristic, dependency specification or CI changes. No commit/push/PR.

Ready for independent re-audit of restored verification evidence. TSan acceptance
remains unmet; this sanitizer pass does not prove race freedom, exhaustive
schedule coverage or general deadlock freedom. Stop here.

## 2026-10-28 — Phase 5C-3B-1 full-validation and fresh-build verification

Explicit user scope authorizes only the opt-in full-validation gate, exact test
registration checker, environment runbook, negative cases and isolated sequential
verification. Initial state was clean main at a6c6266 (PR #9 merge). Created
feature/reproducibility-validation before edits. No dependency installation,
commit, push, PR, CI edit or production behavior change.

Changes: root CMakeLists.txt adds DYNAGRAPH_FULL_VALIDATION (default OFF) and
rejects its combination with BUILD_TESTING=OFF; tests/CMakeLists.txt adds a
full-mode interpreter/pin/Agg probe and exact configure-time name gate. Existing
registration bodies/options are unchanged. New tools/validation/check_environment.py
requires Python >=3.11, compares all eleven pins and renders in memory using Agg.
check_registration.py consumes CTest JSON (or configure-time names), checks the
reviewed default-tests.json set and detects missing/extra/duplicate names.
Optional names are explicit additions, not a blanket allowance for unknown tests.
The 31-name manifest matches retained Phase 5C-2B's thirty plus parallel_failure_fast.
New test_gate.py and clean_checkout.py provide isolated failure fixtures and
sequential build verification. README links docs/reproducibility-validation.md.
No new CTest entry is added; the approved default remains exactly 31 in full mode.

The existing approved /workspaces/Dynagraph-HPC/.venv-analysis/bin/python was used:
Python 3.14.2, all eleven exact pins matched, Agg initialization and rendering
passed. GCC 13.3.0, CMake 3.28.3, Linux x86_64/glibc 2.39; CMake found OpenMP 4.5
with -fopenmp. This is a demonstrated environment, not certification of other
compiler/platform versions. No package was installed/upgraded in this phase.

Exact top-level commands (output directories were new):

```sh
python3 -B tools/validation/test_gate.py --python "$PWD/.venv-analysis/bin/python" --output results/validation/phase5c3b1/negative
python3 -B tools/validation/test_gate.py --python "$PWD/.venv-analysis/bin/python" --output results/validation/phase5c3b1/negative-v2
python3 -B tools/validation/clean_checkout.py --revision a6c6266 --include-working-tree --python "$PWD/.venv-analysis/bin/python" --output "$PWD/results/validation/phase5c3b1/isolated"
```

The first negative harness run exited 1 because it expected an unwrapped substring
in CMake's correctly emitted missing-package diagnostic. Adjusted only whitespace
normalization of expected diagnostics and made the old-version mock witness
specific (3.10.0 mock). Retained that initial output. The corrected harness exited
0: nonexistent interpreter, unsupported Python, missing package, mismatched pin,
Agg initialization failure and absent analysis_stats all caused actual CMake
configuration failure with the expected specific diagnostic. Interpreter wrappers
and a disposable source fixture avoid modifying the real environment or checkout.
Missing/extra/duplicate comparator checks also passed.

The isolated driver was launched through approved outside-sandbox execution for
LeakSanitizer compatibility. It cloned the local repository without hardlinks,
checked out a6c6266262dff4a59f99fa9d6fd2381f38f3748a detached and verified clean
Git state. Because commits are prohibited in this task, it then applied the
explicit tracked patch and copied new nonignored files. This is honestly a clean
base checkout plus identified uncommitted overlay, not a clean committed revision
of the new implementation. source-identity.json records base cleanliness, patch
SHA-256 and every source-file hash. All tested implementation/CMake hashes still
match the final code; subsequent edits only record documentation outcomes.

Three new sibling build directories used explicit GCC settings equivalent to
Debug/Release presets, BUILD_TESTING=ON, warnings as errors, full mode ON and the
same approved analysis interpreter. Optional tiers remained OFF. Environment
verification and CMake plus generated-CTest exact-name checks preceded every
build. Builds used --parallel 2; complete CTest suites used --parallel 1. Each
configure/build/test command finished before the next began. Start/end timestamps
in commands.json confirm no overlap. No existing CMake cache was reused.

| Build | Registered | Passed | Failed | Exit | CTest wall seconds |
|---|---:|---:|---:|---:|---:|
| Debug | 31 | 31 | 0 | 0 | 48.71 |
| Release | 31 | 31 | 0 | 0 | 43.29 |
| ASan+UBSan | 31 | 31 | 0 | 0 | 82.98 |

Process wall seconds including launch overhead: 48.761115, 43.308121, 83.035355.
Sanitizer flags: -fsanitize=address,undefined -fno-omit-frame-pointer and matching
link flags. ASAN_OPTIONS=detect_leaks=1:halt_on_error=1;
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1. No sanitizer finding or timeout.
Dijkstra passed in 1.07/0.07/3.14 s respectively; no timeout was changed.

After the full suites completed, separate disposable configure checks confirmed:
minimal/full-OFF tolerates an absent analysis interpreter (27 registered names);
BUILD_TESTING=OFF remains configurable; FULL=ON with BUILD_TESTING=OFF fails;
all four optional flags together produce exactly 37 registered names with the
explicit optional-tier checker arguments. The actual CTest JSON CLI also rejected
separate generated fixtures containing a missing, extra or duplicate test name.
All compatibility expectations passed; no optional extended workload rerun was
necessary. Exact commands, diagnostic logs and exits are in compatibility/.

Evidence root: ignored results/validation/phase5c3b1/. isolated/commands.json
retains exact argv, working directory, environment settings, timestamps and exit
codes; per-command logs preserve combined stdout/stderr. environment.log records
interpreter/pins/renderer; compiler logs record identities. summary.json independently
compares all 31 passed test names with registrations, checks sequential timestamps
and verifies final code hashes against the tested snapshot. Historical 5C-1/2A/2B/2C
files and evidence are preserved.

Final git diff --check passed; src/, include/, apps/, benchmarks/ and .github/
remain identical to a6c6266. Root production CMake change is limited to the necessary
opt-in option/incompatible BUILD_TESTING guard. Existing test bodies, intentional-race
control isolation, optional tiers, algorithms, public APIs, heuristic and timing
boundaries are unchanged. No commit/push/PR.

Remaining 5C-3B-2: hosted CI full-suite parity, real end-to-end pipeline/archive
verification and portable evidence distribution; calibrated alternative detector
environment remains separate and unresolved. A clean committed-revision run of
this new implementation can be performed once a later commit is authorized; it is
not conflated with the successful pre-commit overlay validation. TSan acceptance
remains unmet. No race/deadlock freedom or performance/scalability claim follows.
Stop for independent review.

## 2026-10-28 — Phase 5C-3B-1R audit-blocked infrastructure repair

The independent audit blocked the original validation infrastructure even though
its raw Debug/Release/ASan+UBSan suites actually passed 31/31. Name extraction did
not reject disabled CTest entries, exit zero alone did not establish complete
execution, and untracked symlinks were dereferenced during overlay copy. Those
historical results above and all original evidence remain preserved; they do not
validate the repaired tooling by themselves.

Authorized repairs stay within tools/validation, test CMake and documentation.
Strict CTest JSON parsing now validates the envelope, version, entries/properties,
exact mandatory/explicit optional names and DISABLED values. CMake rejects disabled
full-mode tests too. A separate strict JUnit acceptance checker requires all
expected tests exactly once with executed status, no skip/failure/error markers,
valid counts/times/output metadata and process exit zero. DTD/entity declarations
are rejected before XML parsing. The sequential driver retains raw registrations,
JUnit reports, per-test acceptance records, command receipts and evidence hashes.

Overlay copying now preserves file bytes, modes and relative internal symlinks;
source/destination typed inventories must match before building and at final
checkpoints. Tracked binary changes/deletions/executable changes are retained in a
binary patch. Unsupported types and unsafe/uncaptured symlink targets fail clearly.
Canonicalized output/source paths must be disjoint; outputs cannot preexist.
Receipts distinguish launch failures (null exit status) from executed commands,
retain diagnostics and hashes, and bounded command timeouts kill the process group.
The Python renderer probe now receives the source path via argv rather than
interpolating it into Python source. The runner removes influential inherited
Python/build/OpenMP/sanitizer settings, sets explicit controls and records its
policy without dumping environment values or credentials. See the runbook for
precise supported types, environment policy and non-hermetic limitations.

Focused evidence before the new integration run:
- /tmp/dynagraph-phase5c3b1r-focused-v1: 12 tests passed; first focused version.
- /tmp/dynagraph-phase5c3b1r-focused-v2: 13 tests passed after adding a real Git
  binary/deletion/mode/symlink overlay round-trip.
- /tmp/dynagraph-phase5c3b1r-focused-v3: 13 tests passed with final runner policy.
  Subcases cover disabled (all/one), skipped, not-run, missing, duplicate, extra,
  malformed/missing reports, exit-zero incomplete results, nonzero superficially
  passing results, and a valid 31/31 report. Actual CTest fixtures reproduce exit
  zero with disabled/skipped tests and verify rejection; no final suite is mocked.
- /tmp/dynagraph-phase5c3b1r-negative-v1: all six original configure failures
  rejected for their exact expected diagnostics, each from a fresh build directory.
- /tmp/dynagraph-phase5c3b1r-compatibility-v1: actual CMake configuration in a source
  path containing spaces, an apostrophe and Unicode passed with 31 full names;
  minimal absent-interpreter mode retained 27; library-only retained zero; optional
  mode retained the exact 37 names; FULL with BUILD_TESTING=OFF correctly failed.

No approved environment mutation, dependency installation, test timeout change,
production/benchmark/API/heuristic/CI change, commit, push or PR. Full corrected
integration results are recorded below only after execution. TSan acceptance
remains unmet; no race-freedom, general deadlock-freedom or performance claim.

The first corrected isolated run (`/tmp/dynagraph-phase5c3b1r-isolated-v1`) completed
31/31 Debug (50.86 s), Release (44.72 s) and ASan+UBSan (86.46 s), with exit zero,
strict JUnit acceptance and matching source/destination inventories. All evidence
is retained. Subsequent boundary review found an additional reproducibility case:
a relative symlink could traverse outside the source and then return to a captured
file. `/tmp/dynagraph-phase5c3b1r-symlink-hop-probe/before.json` records that accepted
fixture. The final resolver now checks every hop, rejects external intermediate
traversal and symlink directory components, while preserving internal leaf chains.
No source change was made while the first isolated run was active.

The final focused suite (`/tmp/dynagraph-phase5c3b1r-focused-v4`) passed 14 tests,
including rejection of that external-hop fixture and preservation of internal
symlink chains. A new isolated full run is required below for this final source;
the prior run is not relabeled as verification of the later resolver change.

## 2026-10-29 — Phase 5C-3B-1R interrupted-session recovery and final verification

Resumed on feature/reproducibility-validation at
`a6c6266262dff4a59f99fa9d6fd2381f38f3748a`. Found four modified tracked files
(CMakeLists.txt, tests/CMakeLists.txt, README.md, this log), the untracked runbook
and ten untracked tools/validation files. Initial diff --check passed. Preserved
all existing changes and results/validation evidence; no reset, stash, clean,
commit, push or PR. The user explicitly authorized this repair beyond the older
phase authorization text in AGENTS.md; Phase 5C-3B-2 remains deferred.

Actual code inspection found the strict registration/execution validators, typed
snapshot resolver, command receipts, environment policy and fourteen focused tests
already implemented. The log's prior repair /tmp directories were absent in this
workspace, so their outcomes were historical claims rather than available fresh
acceptance evidence. The final external-hop symlink correction still needed a new
complete isolated run. No production correction was needed. This session added
explicit binary-byte, file-versus-link and symlink-target mutation rejection
fixtures, plus PermissionError and invalid-cwd launch receipts. Focused coverage
now comprises fifteen tests; the default CTest suite remains thirty-one.

Audit blocker reconciliation (code inspected, then behavior rerun):

| Item | At recovery | Final evidence / status |
|---|---|---|
| 1 Strict registration JSON structure/fields | COMPLETE | COMPLETE: structural and real CTest fixtures |
| 2 Disabled mandatory registrations | COMPLETE | COMPLETE: one/all disabled rejected |
| 3 Machine-readable execution validation | COMPLETE | COMPLETE: strict JUnit plus three real suites |
| 4 Skipped/not-run/missing/duplicate/unexpected | COMPLETE | COMPLETE: all rejected by focused fixtures |
| 5 False-success exit codes | COMPLETE | COMPLETE: real exit-zero disabled/skipped rejected |
| 6 Overlay unsupported types | COMPLETE | COMPLETE: FIFO and unsafe links rejected |
| 7 Binary/deletion/mode/symlink fidelity | COMPLETE | COMPLETE: Git round-trip plus mutation checks |
| 8 Source/output/clone overlap | COMPLETE | COMPLETE: canonical aliases/ancestors rejected; clone is inside new output |
| 9 Launch failure/OSError receipts | COMPLETE | COMPLETE: absent executable, permission and cwd failures |
| 10 Spaces/apostrophes/Unicode paths | COMPLETE | COMPLETE: Git overlay and actual CMake configurations |
| 11 Environment capture/sanitization | COMPLETE | COMPLETE: policy fixture and retained command environments |
| 12 Focused positive/negative fixtures | COMPLETE | COMPLETE: strengthened 15/15 suite, six configure failures |
| 13 Final sequential isolated verification | PARTIAL | COMPLETE: new Debug/Release/ASan+UBSan 31/31 each |
| 14 Documentation/research log | PARTIAL | COMPLETE: this reconciliation and runbook outcome |

Fresh reproduction commands, all executed without dependency installation:

```sh
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-phase5c3b1r-resume-focused-20261029
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-phase5c3b1r-resume-focused-final-20261029
python3 -B tools/validation/test_gate.py --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-phase5c3b1r-resume-negative-20261029
python3 -B tools/validation/test_compatibility.py --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-phase5c3b1r-resume-compatibility-20261029
python3 -B tools/validation/clean_checkout.py --revision a6c6266 --include-working-tree --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-phase5c3b1r-resume-isolated-20261029
```

First focused baseline: 14/14; strengthened final focused suite: 15/15, zero
failures/errors. All six actual negative configure cases rejected their intended
condition with the required diagnostic. Compatibility configurations reconciled
31 full, 27 minimal with absent analysis interpreter, zero library-only and 37
explicit optional names. FULL with BUILD_TESTING=OFF failed as required. Quoted
source path included spaces, an apostrophe and Unicode. Compatibility completed
before the isolated run started; no verification workload overlapped its suites.

The complete driver ran through the approved outside-sandbox execution mechanism,
using the existing pinned interpreter and fresh external evidence/build directories.
All commands exited zero and sequential command timestamps were verified.

| Build | Registered | Actual accepted passes | CTest process wall seconds | Exit |
|---|---:|---:|---:|---:|
| Debug | 31 | 31 | 47.393872 | 0 |
| Release | 31 | 31 | 41.860162 | 0 |
| ASan+UBSan | 31 | 31 | 80.606576 | 0 |

Each acceptance required the exact expected names, each once, status=run, finite
nonnegative times, output metadata, consistent counts, no disabled/skip/failure/
error markers and process exit zero. Malformed/missing reports and nonzero exits
with superficially passing XML also fail. Raw *-execution.xml reports and
acceptance.json retain per-test results; registrations and command output are
retained separately. Sanitizers used detect_leaks=1:halt_on_error=1 and
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1, without timeout changes.

source-identity.json retains all 122 typed source inventory entries and the binary
patch hash. The initial source/destination and both final inventory comparisons
passed. No source edits occurred during the run. evidence-sha256.json hashes were
independently rechecked after completion. Later changes only append these outcome
records to this log and the runbook; tested implementation/CMake files are unchanged.
All fresh evidence directories above remain local under /tmp; preserve them for
review. The initial focused baseline is retained separately, without relabeling it
as coverage of the later fixture additions.

Changed-file inventory remains CMakeLists.txt, tests/CMakeLists.txt, README.md,
docs/research-log.md, docs/reproducibility-validation.md and ten tools/validation
files (check_environment.py, check_execution.py, check_registration.py,
clean_checkout.py, command_receipts.py, default-tests.json, snapshot.py,
test_compatibility.py, test_gate.py, test_repair.py). Final diff --check passed;
src/, include/, apps/, benchmarks/, .github/ and CMakePresets.json match the base.
Existing optional test bodies, mandatory registrations, pins and timeouts remain
unchanged. No dependency install, commit, push or PR.

Ready for independent read-only audit. Snapshot checks are checkpoint-based,
not atomic; directory modes/ACLs/xattrs and unsupported link/file types are outside
the documented source contract. This is a clean base plus identified uncommitted
overlay, not a committed-revision certification or hermetic OS. TSan acceptance
remains unmet; no race/deadlock freedom or performance claim follows. Stop here;
Phase 5C-3B-2 has not begun.

## 2026-10-29 — Phase 5C-3B-2 CI configuration and real smoke pipeline

Explicit user authorization extends the conditionally approved 5C-3B-1R work to
parser hardening, CI workflow changes and bounded end-to-end validation. Recovery
confirmed feature/reproducibility-validation at a6c6266262dff4a59f99fa9d6fd2381f38f3748a,
four modified tracked files and eleven untracked files. All prior implementation,
historical failures and evidence were preserved. No reset/clean/stash, dependency
installation/upgrade, commit, push or PR occurred.

Closed both conditional parser findings. check_registration.strict_loads rejects
duplicate object keys at every nesting level, JSON NaN/Infinity and floating-point
overflow to infinity. Both generated CTest JSON consumers use that decoder;
configure-time name arrays use it too. Supplied command, backtrace/graph and known
property metadata receive explicit type checks without requiring optional fields
that real pre-build CTest output omits. Unknown extension metadata remains opaque
JSON as documented; no universal future-schema claim. Added top-level/nested/
DISABLED-value duplicate and invalid-metadata fixtures, preserving existing actual
CTest disabled/skipped false-success and source-fidelity controls.

Kept both existing CI jobs and the gcc Debug/Release matrix. Full-history checkout
is required by the retained a6c6266 Git-overlay regression. ubuntu-24.04 plus
setup-python CPython 3.13 provisions a fresh external venv with all eleven unchanged
pins, binary wheels only, pip check and install/freeze logs. Published CPython 3.13
manylinux x86_64 wheel metadata for compiled dependencies was checked on PyPI;
links are in the runbook. This is availability/compatibility evidence, not a
hosted installation or execution result. No dependencies were installed locally.

New ci_verify.py is the shared local/hosted leg: source identity and environment,
toolchain versions, new external CMake build, full validation, exactly 31 enabled
default names, two compile jobs, sequential CTest/JUnit, strict per-test acceptance,
unchanged sanitizer options/timeouts, source recheck, failure diagnostics and
hashes. Existing gcc/sanitize coverage was not removed. Upload-artifact always()
retains logs/metadata/raw reports/acceptance and partial failure evidence where
possible; build and temporary directories are excluded. Release additionally runs
new smoke_pipeline.py and test_smoke.py. No claim of hosted CI parity is made.

The smoke calls existing generate.py generate/verify, run.py run/validate and
analyze.py; pipeline_artifacts.py adds product integrity/structural checks rather
than replacing benchmark/analysis logic. Workload and schedule are deterministic;
run IDs, timestamps, real timings and their dependent artifact digests vary.
The unchanged chain recipe has 8 vertices, 7 edges and 12 updates. Both timing
modes run 16 completed trials over all four policies. Full-trace retains 16 timing
observations; per-update retains 192. Independent artifact replay/regeneration,
full compiled preflight and complete dataset validation precede descriptive
analysis. All seven figure kinds produce SVG and PDF (14 products). These are
harness-only observations, not performance/scalability evidence.

Focused/compatibility evidence (new output directories):
- /tmp/dynagraph-phase5c3b2-focused-v1: 17/17 standalone regressions passed.
- /tmp/dynagraph-phase5c3b2-focused-final: 17/17 passed, including nonfinite numeric
  overflow after final parser hardening. These retain all fifteen prior tests.
- /tmp/dynagraph-phase5c3b2-compatibility-v1 and -compatibility-final: actual CMake
  configurations reconcile 31 full, 27 minimal, zero library-only, 37 optional names;
  FULL with BUILD_TESTING=OFF fails. Source path includes spaces/apostrophe/Unicode.
  No intentional-race controls appear in any accepted registration set.
- /tmp/dynagraph-phase5c3b2-negative-final: all six actual configure failures
  rejected the intended case with the required diagnostic.
- /tmp/dynagraph-phase5c3b2-workflow-v1 and -workflow-final: existing PyYAML 6.0.3
  parsed YAML (BaseLoader preserves the Actions on key), assertions checked jobs,
  matrix, setup and always-upload configuration, and bash -n accepted all five
  run scripts. The final check additionally requires full-history checkout.
  actionlint is unavailable; this is not full GitHub schema/expression validation.

Retained development outcomes:
- /tmp/dynagraph-phase5c3b2-smoke-v1 failed its environment gate under system Python:
  missing matplotlib metadata. It did not generate a successful pipeline. No
  package was installed to bypass the gate.
- /tmp/dynagraph-phase5c3b2-smoke-v2 passed under the existing .venv-analysis and a
  previously reviewed Release executable. Its nine negative controls passed in
  /tmp/dynagraph-phase5c3b2-smoke-negative-v1. This prototype is distinct from the
  final fresh-build acceptance run below.
- /tmp/dynagraph-phase5c3b2-debug-final passed 31/31 before a subsequent workflow-only
  full-history checkout correction. The final snapshot was then verified afresh.

Final local CI-driver commands ran sequentially via the approved outside-sandbox
execution mechanism so LeakSanitizer could retain process-inspection support:

```sh
python3 -B tools/validation/ci_verify.py --mode debug --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-phase5c3b2-ci-debug-final
python3 -B tools/validation/ci_verify.py --mode release --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-phase5c3b2-ci-release-final --smoke
python3 -B tools/validation/ci_verify.py --mode sanitize --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-phase5c3b2-ci-sanitize-final
```

| Mode | Actual accepted passes | CTest process wall seconds | Exit |
|---|---:|---:|---:|
| Debug | 31/31 | 46.962652 | 0 |
| Release | 31/31 | 40.866738 | 0 |
| ASan+UBSan | 31/31 | 80.286637 | 0 |

All three exact registration sets, individual raw-log Passed names and JUnit run
results were independently reconciled. All 38 driver commands succeeded, with
sequential timestamps within and across legs. Sanitizers used detect_leaks=1:
halt_on_error=1 and UBSAN halt_on_error=1:print_stacktrace=1. No test timeout changed.
Local Python is the existing 3.14.2 interpreter, GCC 13.3.0 and CMake 3.28.3;
hosted CPython 3.13/runner execution remains untested.

The final Release pipeline at
/tmp/dynagraph-phase5c3b2-ci-release-final/pipeline passed every stage and hash check.
Nine controls at its sibling pipeline-negative directory rejected tampered workload
bytes, incorrect manifest hash, incomplete replay (with updated stdout digest),
missing timing observations, invalid schema, missing figure, malformed SVG/PDF
(with updated product digests), and incorrect artifact digest. Original positive
artifacts remained unchanged. Stage-level argv is explicitly recorded. Worker
subprocess exits and stdout/stderr hashes are retained by existing orchestration;
child invocations are reconstructible from source/configuration/identities, but
per-worker argv is not individually serialized. This wording was corrected in
Phase 5C-3B-3 following the independent audit.

All three legs identify the same 126-entry source snapshot:
8f93bebc807f3f03efc249d81f8bf30f5a98a8cd0a97acbda6d7786e2541328c.
Git base/dirty state and this snapshot identity are separate from executable
SHA-256 and build metadata. Source inventory rechecks passed; no source edits
occurred during the final run. Top-level CI evidence hashes, recursive pipeline
hashes, analysis output/figure hashes and command log hashes were independently
reverified. /tmp/dynagraph-phase5c3b2-review-final/reconciliation.json records the
raw-evidence reconciliation. Only outcome documentation was appended afterwards.
Relative analysis input paths and artifact inventory names support relocation;
exact command/build provenance still retains original absolute paths.

Complete current uncommitted inventory (including preserved 5C-3B-1 work):
- Tracked: .github/workflows/ci.yml, AGENTS.md, CMakeLists.txt, README.md,
  docs/experimental-protocol.md, docs/research-log.md, tests/CMakeLists.txt.
- Untracked documentation: docs/reproducibility-validation.md.
- Untracked tools/validation: check_environment.py, check_execution.py,
  check_registration.py, ci_verify.py, clean_checkout.py, command_receipts.py,
  default-tests.json, pipeline_artifacts.py, smoke_pipeline.py, snapshot.py,
  test_compatibility.py, test_gate.py, test_repair.py, test_smoke.py.

Current-session edits are CI/scope/documentation, parser consumers/fixtures and
four new pipeline/CI modules. Existing root and test CMake modifications from
5C-3B-1 are preserved. Final git diff --check passed; src/, include/, apps/,
benchmarks/ and CMakePresets.json match a6c6266. No shortest-path/API/heuristic,
benchmark timing boundary, scientific measurement definition, workload format or
pin change. Existing optional tiers and TSan-control isolation remain intact.

Ready for independent review of implementation/local evidence. Hosted provisioning,
all three job logs, 31 actual passes in each hosted leg, uploaded artifacts and
Release pipeline evidence must still be checked after a separately authorized
publication/CI trigger. No push was made solely to trigger CI. Static checks cannot
certify GitHub expressions, artifact service behavior or hosted environment parity.
PDF checks are bounded structural sanity, not general PDF conformance or visual
certification. SHA-256 is integrity, not authentication. Snapshot and environment
limitations from 5C-3B-1R persist. TSan acceptance remains unmet; no race/deadlock
freedom or performance/scalability inference follows. Stop here; 5C-3B-3 not begun.

## 2026-10-29 — Phase 5C-3B-3 interruption recovery and portable evidence

The user explicitly authorized resuming/completing Phase 5C-3B-3, superseding the
historical deferred scope in AGENTS.md. Recovered branch
feature/reproducibility-validation at a6c6266262dff4a59f99fa9d6fd2381f38f3748a.
Preserved all seven tracked modifications, the untracked runbook and all fifteen
existing tools/validation files. No reset, clean, stash, commit, push or PR.

Recovery inspection found Phase 5C-3B-2's parser/CI/smoke implementation complete.
The child-worker argv correction already existed in the preceding log entry;
test_smoke.py already partially checked intended CLI rejection diagnostics.
The interrupted session's test_negative_diagnostics.py contained three focused
unit tests for that helper; it was preserved and exercised. It did not establish
that real negative smoke products had been tested in that session. Artifact-side
diagnostic checks, archive creation, offline verification, archive adversaries,
archive upload integration and release checklist were not implemented.
pipeline_artifacts.py was existing product validation, not archive packaging.

Implemented evidence_archive.py (Python standard library only): creation from
completed CI-driver evidence plus its matching typed source snapshot, complete
file/size/mode/SHA-256 manifest, regular-file permission preservation, safe member
validation before manual extraction and independent offline semantic acceptance.
Rejects unsafe paths, duplicates, parent-file collisions, symlink/hardlink members,
directories, special/unsupported types and special permission bits. Input links
are rejected too. Resource bounds are 50,000 members and 1 GiB declared payload.
Source inventory hashes and actual source files/modes, mandatory exact-name
registration and raw JUnit results, acceptance records, command log hashes,
source Git receipt coherence, declared mode/configure coherence, sanitizer options,
smoke analysis products and all nine intended negative-control logs are checked.
The independently copied kit requires no checkout, build products, Git, renderer,
third-party packages or network. SHA-256 is integrity, not authentication.

ci_verify.py creates/reopens a sibling tarball after successful local/hosted legs.
CI now runs archive/diagnostic regressions and uploads tarballs alongside raw
failure/partial evidence. Top-level build/tmp/renderer caches are omitted; nested
pipeline files referenced by its digest inventory are retained. All nine smoke
controls require intended diagnostics; CLI controls additionally require an
executed exit 2. README/runbook/AGENTS/protocol and a new research-validation
release-readiness checklist document scope, trust/portability limits and gates.
No algorithm, API, heuristic, timing boundary, workload format, pin or timeout edit.

Actual focused commands (new output directories):

```sh
python3 -B tools/validation/test_negative_diagnostics.py
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-3b3-repair-recovery
python3 -B tools/validation/test_gate.py --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b3-gate-recovery
python3 -B tools/validation/test_compatibility.py --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b3-compatibility-recovery
```

Results: 3 diagnostic tests; final 12 archive tests with multiple adversarial
subcases; 17 repair tests; six configure failures with intended diagnostics;
compatibility reconciled 31 full, 27 minimal, 0 library and 37 optional names.
Archive tests cover missing/extra/modified members, mode changes, refreshed outer
hashes with mismatched source, skipped mandatory results, duplicate JSON keys,
revision/configure contradictions, Unicode executable roundtrip, unsafe paths,
duplicate members, links and unsupported types. Existing source/receipt/parser
fixtures remained passing. Logs at /tmp/dynagraph-3b3-focused include archive
iterations, diagnostics, static checks and reconciliation; repair/gate/compatibility
each retain their own fixture directories. No dependencies were installed.

Inspected the surviving original phase5c3b1 command receipts/summary under ignored
results/validation before rerunning. Historical /tmp phase5c3b1r/3b2 roots were
absent after interruption. Retained historical evidence was not substituted for
new acceptance evidence. Recovery first ran ci_verify.py debug to
/tmp/dynagraph-3b3-debug-recovery and release --smoke to
/tmp/dynagraph-3b3-release-recovery. Both suites actually passed 31/31. Release
smoke and all nine intended controls passed, but archive staging failed on
`missing/symlink artifact: mpl-cache/fontlist-v390.json`: an excluded nested cache
was referenced by pipeline evidence-sha256.json. Original evidence remains intact;
/tmp/dynagraph-3b3-focused/interrupted-archive-attempt.json records the failure.
Fixed only packaging selection and added a regression. Restored matching source
from the verified first Debug archive and successfully repackaged that first
Release evidence at /tmp/dynagraph-3b3-release-recovered.tar.gz. Its offline copy
passed as well. These attempts are distinct from the fresh final legs below.

Actual final sequential commands:

```sh
python3 -B tools/validation/ci_verify.py --mode debug --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b3-debug-final
python3 -B tools/validation/ci_verify.py --mode release --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b3-release-final --smoke
python3 -B tools/validation/ci_verify.py --mode sanitize --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b3-sanitize-final
```

Sanitizer was explicitly launched outside the sandbox for LeakSanitizer process
inspection. All directories/build caches were new. Same approved Python 3.14.2
venv with all eleven unchanged pins and working Agg; GCC 13.3.0/CMake 3.28.3.
No suite overlap; raw command timestamps were reconciled independently.

| Leg | Actual accepted passes | CTest process wall seconds | Archive created/reopened |
|---|---:|---:|---|
| Debug | 31/31 | 46.524112 | yes |
| Release | 31/31 | 41.546065 | yes, including smoke/controls |
| ASan+UBSan | 31/31 | 79.471757 | yes |

Sanitizer compile/link flags and leak/halt options are unchanged; raw JUnit and
per-test results agree. Release produced complete 16-trial datasets in both modes,
all 14 SVG/PDF products and nine intended rejections. Source inventories remained
unchanged throughout each final leg. All final legs captured source inventory
`d5044e422ff6cba438a6e9a49720276435906116eba6d1377b0da03471293922`.

Final offline review then added explicit Git-receipt/configure-mode consistency
checks in evidence_archive.py and their regression in test_archive.py. Those two
files postdate the CTest source snapshot. Mandatory JUnit acceptance, driver,
CMake and compiled source/tests did not change. The final 12 focused archive tests
passed, and the stricter verifier directly reaccepted all retained final evidence;
no expensive CTest rerun was needed to test these offline comparisons.

Using the matching final source snapshot restored from the verified Debug archive
at /tmp/dynagraph-3b3-tested-source, called the current creator for each real leg:

```python
create(Path('/tmp/dynagraph-3b3-' + mode + '-final'),
       Path('/tmp/dynagraph-3b3-tested-source'),
       Path('/tmp/dynagraph-3b3-' + mode + '-review.tar.gz'))
```

The review archives retain the actual tested source snapshot and a separately
inventoried current verifier kit. Copied all three to /tmp/dynagraph-3b3-offline.
The retained offline_verify.py launcher adds only the copied kit to sys.path and
uses a Python audit guard denying /workspaces file opens, socket operations and
subprocess launches. It explicitly confirms source checkout access is denied.
From cwd /tmp, executed each copied archive using:

```sh
python3 -I -B /tmp/dynagraph-3b3-offline/offline_verify.py --verify /tmp/dynagraph-3b3-offline/dynagraph-3b3-debug-review.tar.gz
python3 -I -B /tmp/dynagraph-3b3-offline/offline_verify.py --verify /tmp/dynagraph-3b3-offline/dynagraph-3b3-release-review.tar.gz
python3 -I -B /tmp/dynagraph-3b3-offline/offline_verify.py --verify /tmp/dynagraph-3b3-offline/dynagraph-3b3-sanitize-review.tar.gz
```

All exited 0 with 31 mandatory passes; Release also accepted smoke/negative logs.
A real copied Debug tarball with execution.xml removed exited 1 with complete
inventory/hash/mode mismatch. offline-results.json records exact commands, exits
and copied archive hashes. focused/reconciliation.json reconciles raw reports,
registrations, source identity, sequencing, archive sizes and member counts.
Review tarball SHA-256 values:

- Debug (158 members): e9abb981340130589e021056a5412c45ff51e5c42d32e9ed8d8a608612227604
- Release (658 members): 0f2ebad3ae21d56ec63e531442842a4362bfe19d9ed66af17dcb71dc0c7f2f00
- ASan+UBSan (158 members): 5baadf67e3098a2c630c5234e61de5bcee201256f6b0c088b5b137b299a8941a

Complete working-tree inventory for independent review (26 files):

- Seven modified tracked files: .github/workflows/ci.yml, AGENTS.md,
  CMakeLists.txt, README.md, docs/experimental-protocol.md, docs/research-log.md,
  tests/CMakeLists.txt. Earlier CMake implementation remains preserved.
- Two untracked documents: docs/reproducibility-validation.md,
  docs/research-validation-checklist.md.
- Seventeen untracked tools/validation files: check_environment.py,
  check_execution.py, check_registration.py, ci_verify.py, clean_checkout.py,
  command_receipts.py, default-tests.json, evidence_archive.py,
  pipeline_artifacts.py, smoke_pipeline.py, snapshot.py, test_archive.py,
  test_compatibility.py, test_gate.py, test_negative_diagnostics.py,
  test_repair.py, test_smoke.py.

Of the tools, this recovery modified ci_verify.py/test_smoke.py and added
only evidence_archive.py/test_archive.py. The existing test_negative_diagnostics.py
was preserved, exercised and integrated into CI. Worker argv wording was expanded
in the runbook. Final documentation records outcomes after verification.

Local YAML parse and all six workflow shell syntax checks passed. Every validation
Python module parses with Python 3.8 grammar. Protected src/include/apps/benchmarks,
CMakePresets.json and tests/tsan_controls remain identical to a6c6266; no existing
timeout changed. Final git diff --check passed. No hosted job has run; local checks
cannot certify GitHub provisioning, expression evaluation or artifact upload.

Ready for independent review of local implementation/evidence, with hosted CI
acceptance and the release checklist still pending independent confirmation.
Archives establish integrity, not producer authentication; OS/toolchain isolation
is not hermetic, source checkpoints are not atomic, and portable byte/mode review
is not cross-platform execution or bitwise-build certification. Source revision
metadata is not a cryptographic certificate binding executable bytes to source.
TSan acceptance remains unmet (the calibrated work_ report was LIKELY TOOL/RUNTIME
LIMITATION, not race freedom). No performance/scalability, inferential-statistics
or general deadlock/race-freedom claim. Preserve external /tmp evidence to durable
storage before another lifecycle interruption. Stop before commit/push/PR or Phase 6.

## 2026-10-29 — Phase 5C-3B-3R audit-blocked archive repair

Explicit user authorization resumes only the archive acceptance repair, CI/local
verification and documentation. Initial branch/HEAD remained
feature/reproducibility-validation / a6c6266262dff4a59f99fa9d6fd2381f38f3748a.
All 26 original changed/untracked files were copied faithfully to
/tmp/dynagraph-3b3r-recovery/original, with original SHA-256 inventory and binary
tracked patch retained alongside them. All earlier raw evidence and archives are
preserved. No reset/clean/stash, dependency installation, commit, push or PR.

The independent audit's BLOCKED verdict is preserved here: producer-supplied
inventories could hide a required dataset/hash key, mandatory pipeline stages or
environment policy. failure.json could coexist with an accepted complete result.
Tar iteration did not drain the gzip footer, admitting truncation. EOFError and
array-shaped manifests escaped controlled diagnostics. Broad exception-only tests
missed these defects. The documented launcher retained the kit argument, and
archive SHA-256 sidecars were absent. Passing genuine suites did not excuse these
false-success routes or certify the former archive gate.

Repairs add archive_contract.py with explicit supported success profiles and one
failed-run integrity profile; archive_transport.py implements bounded complete
gzip decoding and a preflighted regular-file/local-PAX tar subset. The archiver
uses format v2, mandatory verifier-kit inventory, full member size/mode/hash checks,
profile/terminal reconciliation and SHA-256 sidecars. Kit modules include unchanged
trusted copies of the four existing standard-library benchmark validators; archived
source and binaries are never executed. The release contract now revalidates both
complete datasets, workload/executable identities, worker/preflight evidence,
mandatory ordered stage receipts and analysis acceptance/input inventories.
The bounded recipe is checked before independent workload regeneration/replay.
See the final runbook section for every mandatory stage/file, limit and policy.

ci_verify.py enforces the three supported successful modes (Release requires
--smoke), preserves original failures, and attempts a separately classified
failed-run archive only when the captured source/evidence supports that profile.
Its original failing command still exits nonzero. CI uploads tarballs and digest
sidecars, including supported failed archives, alongside always() raw evidence.
No mandatory CTest registration, existing timeout or production behavior changes.
The exact documented isolated command now removes its kit argv element and has a
subprocess regression, including a copied kit path containing spaces.

Focused archive fixtures are explicitly SYNTHETIC and never substitute for real
validation evidence. archive_test_support.py reuses existing synthetic worker and
independent replay helpers, with clearly labeled synthetic tables/structural figures.
No missing genuine artifact was fabricated. All 39 final focused tests passed:
/tmp/dynagraph-3b3r-focused/archive-final-v4.log. Earlier 33/35/37-test development
logs remain separate. Every negative assertion now names its intended diagnostic.
Coverage includes all audited self-consistent omissions with refreshed inventories,
conflicting terminal markers, mandatory result variants, receipt/schema/identity
mismatches, complete compressed/tar integrity, metadata/resource bounds, unsafe
paths/links/types, parent collisions, permissions, sidecars and exact offline argv.

Actual focused/configuration commands:

```sh
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/test_negative_diagnostics.py
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-3b3r-repair
python3 -B tools/validation/test_gate.py --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b3r-gate
python3 -B tools/validation/test_compatibility.py --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b3r-compatibility
```

Results: 39 archive tests, 3 diagnostic tests, 17 repair tests, all six intended
configure failures and 31/27/0/37 full/minimal/library/optional registrations passed.
No dependency installation or upgrade. Initial static YAML/six shell syntax checks,
Python 3.8 grammar parsing and protected-path comparison passed. Full current
verification outcomes and exact archive identities are recorded below after actual
completion; no historical suite is claimed as testing this repaired gate.

First genuine repackaging used the retained /tmp/dynagraph-3b3-{mode}-final evidence
and its matching /tmp/dynagraph-3b3-tested-source snapshot (identity
d5044e422ff6cba438a6e9a49720276435906116eba6d1377b0da03471293922).
All three satisfied the new mandatory contract; no required artifact was missing.
Initial repaired archives at /tmp/dynagraph-3b3r-retained-{mode}.tar.gz and their
sidecars remain preserved. Subsequent final-code repackaging/offline checks use new
names and retain the distinction between tested source and reviewed verifier kit.

An intentional actual driver failure exercised the supported failure profile:

```sh
python3 -B tools/validation/ci_verify.py --mode debug --python /nonexistent/intentional-negative-python --output /tmp/dynagraph-3b3r-failed-driver
```

It recorded a launch-error/null exit for environment setup and the top-level command
exited 1. Its diagnostic log, failure classification, source snapshot and raw
receipts remain intact. A .failed.tar.gz and sidecar were produced and reopened;
verification classified failed validation separately from integrity. This is an
intentional infrastructure negative, not a failed algorithm suite. The first
repaired iteration included an accepted-count field of zero; final failed-profile
output instead omits test-count claims entirely. Historical output is not rewritten.

Current working tree contains 29 changed/untracked files: the original seven tracked
modifications and two untracked documents, plus twenty tools/validation files.
New in this repair: archive_contract.py, archive_transport.py, archive_test_support.py.
Modified in this repair: evidence_archive.py, test_archive.py, ci_verify.py,
.github/workflows/ci.yml, AGENTS.md, README.md, docs/experimental-protocol.md,
docs/reproducibility-validation.md, docs/research-validation-checklist.md and this
research log. All other prior implementation is preserved. Root/test CMake changes
from earlier phases remain intact; protected production paths still match a6c6266.

### Phase 5C-3B-3R completed local verification

The final 39-case archive regression log is archive-final-v4.log; all assertions
passed for their intended reasons. Three diagnostic tests and seventeen repair
tests passed. Six actual negative configure cases produced expected diagnostics;
full/minimal/library/optional raw registrations reconciled 31/27/0/37. Earlier
focused development logs are preserved, with no configuration or suite failure
silently retried. No algorithm-suite failure occurred in this repair.

Fresh sequential current-implementation commands, all new directories:

```sh
python3 -B tools/validation/ci_verify.py --mode debug --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b3r-debug-final
python3 -B tools/validation/ci_verify.py --mode release --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b3r-release-final --smoke
python3 -B tools/validation/ci_verify.py --mode sanitize --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b3r-sanitize-final
```

Top-level output was redirected respectively to focused/debug-driver.log,
release-driver.log and sanitize-driver.log under /tmp/dynagraph-3b3r-focused.
Sanitizer used the approved outside-sandbox mechanism for LeakSanitizer inspection.
All commands in each leg were sequential; legs did not overlap. Same existing
approved Python 3.14.2 venv, unchanged eleven pins, working Agg, GCC 13.3.0 and
CMake 3.28.3. No dependency installation, cache reuse or test-timeout change.

| Leg | Exact registrations | Actual accepted passes | CTest process wall seconds |
|---|---:|---:|---:|
| Debug | 31 | 31/31 | 49.598802 |
| Release | 31 | 31/31 | 50.509218 |
| ASan+UBSan | 31 | 31/31 | 85.042869 |

All source identity snapshots equal
76a49ecd77378a0aacafc30d98f9e640b5aaeaf64d638eca8af24f228c52fceb.
Raw registration/JUnit/acceptance and every command-log digest were independently
reconciled. Compile/link sanitizer flags and ASAN_OPTIONS=detect_leaks=1:halt_on_error=1,
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 remain unchanged. Release's complete
16-trial datasets per timing mode, fourteen figures and nine intended control
rejections passed the repaired archive contract, including actual replay/worker
validation and analysis input inventories. These wall times are harness observations,
not performance/scalability measurements.

Current-code genuine historical repackaging used the actual matching old source:

```sh
python3 -B tools/validation/evidence_archive.py --create /tmp/dynagraph-3b3-debug-final --source /tmp/dynagraph-3b3-tested-source --output /tmp/dynagraph-3b3r-retained-debug-final.tar.gz
python3 -B tools/validation/evidence_archive.py --create /tmp/dynagraph-3b3-release-final --source /tmp/dynagraph-3b3-tested-source --output /tmp/dynagraph-3b3r-retained-release-final.tar.gz
python3 -B tools/validation/evidence_archive.py --create /tmp/dynagraph-3b3-sanitize-final --source /tmp/dynagraph-3b3-tested-source --output /tmp/dynagraph-3b3r-retained-sanitize-final.tar.gz
```

All three verified under the repaired profiles without a genuinely missing required
artifact. Their source identity remains d5044e422ff6cba438a6e9a49720276435906116eba6d1377b0da03471293922;
this is separate from the newly tested 3R identity above. The current trusted kit
is separately inventoried. Source files/binaries from those archives are never
executed by verification. Real retained executable modes 0757 were preserved in
both positive datasets and the three negative dataset copies; tests independently
exercise a 0755 Unicode-named source executable as well.

Every pair was copied to /tmp/dynagraph-3b3r-offline with its basename unchanged.
For each old-source repackaged pair and each fresh pair, executed three checks
from that directory: sha256sum -c <basename>.sha256, the exact corrected documented
python3 -I -B -c launcher, and /usr/bin/python3 -I -S -B guarded_verify.py. The
retained-offline-results.json and focused/final-reconciliation.json preserve every
argv and exit. The guard explicitly denies checkout/venv access using normalized
absolute paths and denies socket/subprocess operations. System Python 3.12.3 with
site packages disabled passed all copied archives, including Release replay/worker
and figure structural verification. No network, original checkout, project venv,
compiler or installed project package was needed. All three commands exited 0 for
each pair; no hosted CI result is inferred from this.

The exact documented launcher, also subprocess-tested with a spaced kit directory:

```sh
python3 -I -B -c 'import runpy,sys; kit=sys.argv.pop(1); sys.path.insert(0,kit); runpy.run_path(kit+"/evidence_archive.py",run_name="__main__")' /path/to/kit --verify /path/to/copied-artifacts/evidence.tar.gz --sidecar /path/to/copied-artifacts/evidence.tar.gz.sha256
```

Final fresh archive digests (167/667/167 members, respectively):

- dynagraph-3b3r-debug-final.tar.gz: 48317c1018b794b23f16499f79abb8edebc069dd1b632f768ed61b6e3d63d05f
- dynagraph-3b3r-release-final.tar.gz: 75d8bfc4b5262e43e66a316fe7ff186db3440b861c6a763fcabc740ce5fcfd3e
- dynagraph-3b3r-sanitize-final.tar.gz: da3c22c03905e44bee9cbbae6766ae71bd1e8590e810c3b3cc9ba4214bfe5390

A second final-code intentional driver failure used the same missing-interpreter
command with output /tmp/dynagraph-3b3r-failed-driver-final. Its command exited 1
and retained launch-error/null-exit/error diagnostics. The new failed archive and
sidecar passed all three copied checks, returning integrity-verified /
validation_status failed / failure_classification command-failed with no test-count
claim. Source identity is the same 76a49e... snapshot. Its 157-member archive digest:
6012fb8138950e55fff5cde1c7f95488c0c332c0cf4b8a86479c328436a32ec8.
This tests preservation/classification of an actual failed infrastructure attempt;
it is never presented as a passing suite or fabricated scientific evidence.

Durable-workspace preservation: new ignored results/validation/phase5c3b3r contains
all newly produced archive/sidecar attempts, copied offline kit and checks, focused
logs, selected raw gate/compatibility/repair diagnostics, original 26-file backup
and binary patch, final receipt/source/archive reconciliation and SHA-256 preservation
inventories. Full external builds and all original historical directories remain
untouched. Archived selected raw evidence is complete under its explicit profile;
no build products or ephemeral caches are claimed as portable rebuild environments.

The implementation, tests and CI bytes in every fresh verifier kit match the final
code. Only this outcome documentation and the runbook changed after the fresh
source snapshot. No post-suite implementation strengthening is claimed this time.
Final source-preservation, grammar/YAML/shell checks and git diff --check are recorded
in the final audit evidence. Local work is ready for independent re-audit, not an
assertion that the BLOCKED independent gate has already been cleared.

Remaining limits: one gzip member and a deliberately restricted tar/PAX subset;
regular POSIX modes only; bounded standard-library parsing/replay rather than all
archive formats; no producer authentication/source-to-binary certificate; environment
not hermetic and snapshots not atomic. Failed evidence before source capture or
with source drift may remain raw-only. Hosted Python 3.13 provisioning, all hosted
jobs, archive/sidecar retrieval and artifact service behavior remain unexecuted.
TSan acceptance remains unmet. No race freedom, general deadlock freedom, calibrated
selection, inferential statistics, performance or scalability claim. No dependency
installation, commit, push, PR or Phase 6 work. Stop for independent re-audit.

Complete final 29-file review inventory:

- Modified tracked: .github/workflows/ci.yml
- Modified tracked: AGENTS.md
- Modified tracked: CMakeLists.txt
- Modified tracked: README.md
- Modified tracked: docs/experimental-protocol.md
- Modified tracked: docs/research-log.md
- Modified tracked: tests/CMakeLists.txt
- Untracked: docs/reproducibility-validation.md
- Untracked: docs/research-validation-checklist.md
- Untracked: tools/validation/archive_contract.py
- Untracked: tools/validation/archive_test_support.py
- Untracked: tools/validation/archive_transport.py
- Untracked: tools/validation/check_environment.py
- Untracked: tools/validation/check_execution.py
- Untracked: tools/validation/check_registration.py
- Untracked: tools/validation/ci_verify.py
- Untracked: tools/validation/clean_checkout.py
- Untracked: tools/validation/command_receipts.py
- Untracked: tools/validation/default-tests.json
- Untracked: tools/validation/evidence_archive.py
- Untracked: tools/validation/pipeline_artifacts.py
- Untracked: tools/validation/smoke_pipeline.py
- Untracked: tools/validation/snapshot.py
- Untracked: tools/validation/test_archive.py
- Untracked: tools/validation/test_compatibility.py
- Untracked: tools/validation/test_gate.py
- Untracked: tools/validation/test_negative_diagnostics.py
- Untracked: tools/validation/test_repair.py
- Untracked: tools/validation/test_smoke.py

## 2026-10-29 — Phase 5C-3B-3R2 narrow configuration-validation repair

The independent 3R re-audit confirmed all original six archive false-success cases
closed and reconciled all genuine evidence, but BLOCKED approval on a new profile
bypass. configuration() inspected only joined -DKEY=value arguments and ignored
split -D KEY=value arguments. An appended split override could make native CMake
select Release, disable full validation and clear both sanitizer flags while the
checker accepted the profile. The auditor confirmed actual CMake behavior in
script mode with an anonymous RAM-backed script, without configuring/building.
Separately, math.isfinite(10**400) raised an uncaught OverflowError on a receipt
timestamp. These findings are preserved; the passing real algorithm results were
not invalidated or relabeled by the archive-acceptance findings.

Explicit user authorization permits only this narrow repair and verification.
Branch/HEAD remain feature/reproducibility-validation /
a6c6266262dff4a59f99fa9d6fd2381f38f3748a. All 29 original changed/untracked files,
their SHA-256 inventory and binary tracked patch are preserved under new ignored
results/validation/phase5c3b3r2/original and its adjacent records. All historical
phase5c3b3r evidence is left untouched. No reset, clean, stash or dependency install.

Changed implementation: archive_contract.py now recognizes only the exact argv
representation emitted by the unchanged ci_verify.py. It requires the literal
cmake/-S/-B/-G prefix, canonical absolute source/build paths with source equal to
recorded cwd, Unix Makefiles, the exact ordered compiler/build/testing/warnings/
full-validation/interpreter definitions and the two exact sanitizer definitions
for sanitizer only. Every argument is consumed. Unknown arguments/keys, split or
typed definitions, ambiguous or malformed tokens, and all duplicates (including
identical duplicates) fail. No general CMake normalization or implicit first/last
winner behavior remains. Cache preloads/removals, presets, toolchains and other
unallowlisted override mechanisms fail. Protected values must match the profile;
empty or missing sanitizer settings cannot pass. Metadata paths are checked
lexically only and are never opened or resolved by the verifier.

Receipt times now pass a dedicated type/finite/range check with no int-to-float
conversion. start_unix/end_unix/wall_seconds are int or finite float, excluding
bool, in [0, 253402300799] seconds. The cap is the last whole Unix second in UTC
year 9999 and a broad duration-data cap, not an execution/test timeout. Rejections
identify type, nonfinite value or range and name the receipt/field. Existing
sequential-time checks remain unchanged. No broad exception catch was added.

Only three code files changed: archive_contract.py, archive_test_support.py and
test_archive.py. The fixture producer was corrected to match genuine canonical
argv and cwd; production ci_verify.py and command_receipts.py remain byte-for-byte
unchanged from the 29-file recovery snapshot. Documentation changes are limited
to the reproducibility runbook, this research log and the release checklist.
The overall changed/untracked inventory remains 29 files.

The existing 39 archive regressions passed first, with the corrected fixture:
archive-existing-39.log. Expanded verification then passed 59 tests (39 existing
plus 20 added methods with multiple diagnostic-specific subcases), recorded in
archive-expanded-v1.log. Positive Debug, Release-smoke and sanitizer archives all
exercise the actual verifier. Negative fixtures retain otherwise valid evidence,
refresh supplied hashes/inventories and assert specific configure/time diagnostics.
Coverage includes every requested split/joined override, duplicate, malformed or
missing definition, -C/-U/preset/toolchain/script and injected cache setting,
required flag removal/empty value, all protected settings, paths/order, normal
and boundary timestamps, huge integers, nonfinite values and malformed types.
A real CLI subprocess verifies controlled exit 1 with no traceback for 10**400.
All original mandatory-evidence, terminal-status, gzip/tar, mode/hash/link/path and
manifest security regressions remain in the passing 59-test suite.

Initial local commands:

```sh
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/test_negative_diagnostics.py
```

The first command's two actual runs wrote archive-existing-39.log and
archive-expanded-v1.log respectively; three diagnostic-control tests also passed,
recorded in diagnostic-controls.log. No dependency or environment was changed.
Subsequent genuine-archive and independent CLI checks are recorded below after
actual completion. No previous result is claimed as a new C++ execution.

### 2026-10-29 — Interrupted 3R2 recovery and final local reconciliation

Recovered branch feature/reproducibility-validation at
a6c6266262dff4a59f99fa9d6fd2381f38f3748a, with seven tracked modifications and
22 untracked review files (29 total). Read AGENTS.md and inspected actual code,
tests, producer, runbook and retained logs before executing checks. Both narrow
repairs were COMPLETE in source and regression coverage before interruption;
the final reconciliation/documentation was INCOMPLETE. The inspected 39-test,
59-test and three diagnostic-control logs all have terminal OK results; retained
offline/adversarial records also have terminal exit codes. No interrupted test
run was identified or relabeled as passing. All historical evidence is preserved.

Comparison against phase5c3b3r2/original found exactly six changed files:
tools/validation/archive_contract.py, archive_test_support.py, test_archive.py,
docs/reproducibility-validation.md, docs/research-validation-checklist.md and this
log. The three code changes and three documentation changes predate recovery.
During recovery only this log and the runbook were edited; no implementation
change was needed. ci_verify.py, evidence_archive.py, CI/CMake infrastructure,
production algorithms/APIs/heuristics/timing boundaries, workload formats,
dependency pins and existing timeouts are unchanged from the recovery snapshot.
Production apps/include/src and dependency pins also have no diff against HEAD.

New records are under ignored
results/validation/phase5c3b3r2/recovery-20261029/. Commands and exit codes are in
focused-results.json, genuine-results.json and adversarial-results.json; individual
logs retain actual output. recovered-inventory.json records the working tree and
snapshot comparison, and prior-evidence-sha256.json preserves historical bytes.

Recovery commands `python3 -B tools/validation/test_archive.py` and
`python3 -B tools/validation/test_negative_diagnostics.py` passed 59 tests in
18.004 seconds and three tests in 0.001 seconds respectively. This includes all
39 original archive-security regressions and all 20 added configure/time methods.
The oversized timestamp CLI exits 1 with its range diagnostic and no traceback.

For each of the seven paths in retained genuine-verification.json, ran
`python3 -B tools/validation/evidence_archive.py --verify ARCHIVE --sidecar ARCHIVE.sha256`.
All exited 0: both historical sets of Debug, Release-smoke and sanitizer archives
reported verified/passed/31; Release retained its smoke acceptance. The failed
driver archive reported integrity-verified/failed/command-failed, with no passed
count. Source inventory identities remain d5044e422ff6cba438a6e9a49720276435906116eba6d1377b0da03471293922
and 76a49ecd77378a0aacafc30d98f9e640b5aaeaf64d638eca8af24f228c52fceb.
Archive SHA-256 values in genuine-results.json match the prior recorded values.

The same current-code CLI with sidecars rejected all seven retained synthetic
adversaries: four split overrides and combined-audit with the split-definition
diagnostic, cache-preload with unsupported -C, and huge-time with the revision
start_unix range diagnostic. Every exit was 1 with no traceback. These mutations
are diagnostic controls, not genuine execution evidence. Prior isolated offline
checks and cache corroboration remain retained, not claimed as newly executed.

No expensive C++ suite was rerun: the recovered acceptance logic, producer and
build infrastructure required no further change, and genuine raw results were
reverified directly. Final git diff --check passed. Local repair is ready for
independent re-audit; independent approval and hosted CI remain pending, and the
TSan acceptance gate remains unmet. Archive integrity does not authenticate the
producer or certify source-to-binary correspondence. No dependencies installed,
commit, push, PR or Phase 6 work. Stop here for independent review.
# 2026-10-29 — Phase 6B-1 campaign contracts and hardware admission

The explicit Phase 6B-1 request authorizes implementation and a local feature-branch
commit, superseding the older Phase 6 deferral only for this foundation. AGENTS.md
and the protocol status now state that scope explicitly. Phase 5 evidence below
is historical and unchanged. Started from clean main at
8b05c2b2dc1212176eb70cf24559b0bf1ccd53bd (merged Phase 5C, PR #10). The user reports
hosted validation complete; this work does not claim a new hosted run. Created
feature/phase6b-campaign-foundation. The first git switch failed because sandbox
Git metadata is read-only; the approved filesystem escalation created the branch.

Implemented separate standard-library campaign contract, planning CLI and Linux
hardware collector/admission modules; a development-only example; synthetic tests;
and docs/campaign-foundation.md. Canonical hashes bind plans, explicit trial
coordinates and admission reports. Planning never launches a benchmark. Existing
engine update measurement levels only; no full matrix, executor, new algorithm,
heuristic tuning, inference, native batching or timing change. All four existing
policies and unchanged thresholds are explicit. Unknown/missing fields, unsafe
references, duplicate identities, malformed JSON, excessive expansion, incompatible
worker/delta comparisons and conflicting declarations reject deterministically.

Hardware evidence separates observed/unavailable facts and user declarations.
Visible unified cgroup ancestry is resolved against mount roots and reconciled
for cpusets, quotas and memory headroom. Affinity/topology/SMT and worker budgets
are checked. Scientific qualification requires matching binary/compiler/runtime
evidence and reservation declarations. A compiler candidate library or DT_NEEDED
entry cannot establish loaded runtime identity; optional existing-process maps
must match executable bytes and mapped file device/inode. No target executable
is launched. Development admission remains explicitly unsuitable for scientific
collection/scaling, retaining failed scientific checks. Reports are not authenticated
host attestation, build certification or proof of exclusive ownership.

One narrowly justified CI addition invokes python -B tests/test_campaign.py in
the existing Debug/Release standalone regression step. It continuously checks
this new contract without changing any CTest registration or the 31-test profiles.
Sanitizer workflow, existing timeouts, CMake, pins and production code are unchanged.

Validation records are retained under ignored results/validation/phase6b1/.
focused-results.json, gate-results.json, unsandboxed-result.json, archive-results.json
and cli-final/commands.json record actual commands/outcomes. Core commands:

```sh
python3 -B tests/test_campaign.py
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/test_negative_diagnostics.py
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-phase6b1-repair
.venv-analysis/bin/python -B tools/validation/check_environment.py
python3 -B tools/validation/ci_verify.py --mode debug --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1-debug
python3 -B tools/validation/ci_verify.py --mode release --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1-release --smoke
python3 -B tools/validation/ci_verify.py --mode sanitize --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1-sanitize
python3 -B tools/validation/ci_verify.py --mode sanitize --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1-sanitize-unsandboxed
git diff --check
```

Final campaign regression run: 38 tests passed (campaign-final-v3.log), including
hash-randomization independence, all missing top-level fields, malformed shapes,
schedule balance/coverage, bounds, cross-configuration rejection, cgroup mount
and ancestor fixtures, SMT/affinity/memory contradictions, scientific positive
and negative synthetic reports, runtime inode mismatch and development behavior.
Earlier 30-test exploratory runs passed. The first expanded 37-test run had one
test-authoring failure: it wrongly expected an explicitly empty comparison list
to reject; empty comparisons are valid. Corrected the test and reran successfully.
The final code also binds admission to canonical plan/hardware hashes and rejects
nested boolean/integer aliases and nonstring governor evidence in hardware reports.

Existing archive regressions: 59/59 passed; diagnostic controls: 3/3 passed;
infrastructure repair regressions: 17/17 passed; exact pinned environment/Agg
check passed, with no installation. Fresh Debug and Release gates each built and
passed 31/31 mandatory tests. Release smoke, complete dataset/analysis validation
and intended negative controls passed. The first ASan+UBSan gate failed (driver
exit 1, CTest exit 8): LeakSanitizer explicitly reported ptrace incompatibility.
Preserved that attempt, raw logs and its integrity-verified failed-run archive.
The approved outside-sandbox attempt used a new directory and passed 31/31 with
unchanged leak/halt-on-error settings; it is a separate success, never a relabeling.

All three successful fresh archives and sidecars independently reopened as
verified/passed/31; failed evidence reopened as integrity-verified/failed, without
a passed-count claim. Also reopened the three retained downloaded Phase 5 hosted
archive/sidecar pairs under /tmp/dynagraph-hosted-ci-32; all passed their profiles.
An initial ad-hoc archive import used the wrong sys.path and raised ModuleNotFoundError;
corrected the tools/validation import path and successfully reopened the archive.
No repository implementation defect or evidence rewrite was involved.

The full C++ gates captured source inventory
894942b6bfd970dae34f5811c24e493914b782f153e5ac468ef75dbb36fb9c8a.
Afterward, final review tightened only the new campaign core-count/runtime inode
checks, typed hardware observations and admission hash binding, added the standalone CI invocation and updated
documentation. Final campaign tests exercise those final changes; existing C++,
runner, record, workload, analysis and verifier bytes remain unchanged from the
successful gates. No unnecessary second C++ suite run was made for these isolated
Python guards/documentation changes. Final CLI records show deterministic planning,
development-only admission and scientific rejection on the current SMT VM, even
when binary/compiler/candidate-runtime digests are matched. No performance result
is inferred from validation smoke timings or CTest wall times.

Final git diff --check passed. unchanged-scope.json records comparison against the
main baseline for production APIs/algorithms, timing, existing schemas/goldens,
analysis, dependency pins, CMake and archive tools. New raw evidence, archive pairs
and prior failed attempts remain outside Git. No dependencies installed, no push,
merge or PR; no TSan execution/acceptance or race-freedom claim. This subphase stops
after the authorized local commit for review. Remaining work is a separately
approved executor, resource enforcement, build/provenance linkage and freshness,
actual-team evidence, controlled collection, statistical analysis and replication.

## 2026-10-29 — Phase 6B-1R independent-audit remediation

Started clean on feature/phase6b-campaign-foundation at audited commit
95c515fc802f6a75ce59fdbd236f77be4469fb05. The user authorizes fixes for F1–F4,
fresh local gates and a local commit on this branch, with no push, merge or PR.
AGENTS.md now records that narrow remediation scope. Existing Phase 5/6B-1
records are not rewritten. Their SHA-256 preservation inventory and the clean
baseline are recorded under new ignored results/validation/phase6b1r/.

Before implementation, added eight regressions: direct API and public CLI for
each audited failure. Running python3 -B tests/test_campaign.py produced 46 tests,
with the original 38 passing and exactly the eight new regressions failing.
red-regressions.log and red-result.json preserve this actual before state.

F1 root cause: choosing the most-specific cgroup mount hid visible parent limits;
unanchored ancestor summaries could also be truncated. Hardware report v2 retains
raw unified membership/mountinfo and every relevant anchored mount view. Pure
validation reconstructs leaf/endpoint/hierarchy paths, enforces complete ancestry,
reconciles overlapping policies and recomputes all quota/cpuset/memory constraints.
Missing/ambiguous/contradictory evidence fails closed; unavailable collection has
an explicit reason. Changing memory.current gauges are allowed with conservative
headroom aggregation; hidden host restrictions remain unverified.

F2 root cause: admission trusted a linkage label and two hashes without validating
the mapping record. Closed candidate and observed forms now validate complete
PID/stat/start, raw mappings, file device/inode/size/mtime, path, soname and digest
identities. Unknown fields and contradictory records reject. Positive fixtures
contain complete synthetic Linux records. File/process rechecks do not turn a
non-atomic snapshot into host authentication or execution-time stability proof.

F3 root cause: sibling consistency was checked only for allocated rows, while
NUMA/nested facts were not fully validated. Every CPU's sibling group must now
match its package/core equivalence class before allocation checks. Supplied NUMA
must partition all online CPUs without overlaps or split SMT cores; memory-only
nodes and genuinely unavailable optional NUMA remain supported. Other supplied
optional facts have closed typed schemas. Ownership remains user-declared.

F4 root cause: lexical path checks omitted encoding validation. Strict UTF-8 and
filesystem encoding roundtrip now reject high/low unpaired surrogates before file
access. Legitimate Unicode is preserved without NFC/NFD normalization; byte-distinct
references retain distinct plan hashes. Future staging still needs alias checks.

The first repaired run rejected all audit cases but exposed two legacy diagnostic
expectations, preserved in first-green-attempt.log. Kept the original diagnostics
for unsafe paths and logical-count contradictions; the complete 46-test suite
then passed (green-46.log). Additional nearby API/CLI adversaries expanded coverage
to 62 passing tests (expanded-tests-v2.log): overlapping/truncated mount evidence,
restrictive quota/cpuset/memory parents, policy drift, malformed counters, missing
runtime fields, wrong PID/start/inode/device/soname/hash, candidates denied science,
all-row SMT/NUMA consistency, optional absence and Unicode API/CLI/file roundtrips.

New pure campaign_provenance.py centralizes these validators without filesystem
access or subprocesses. Campaign-plan/trial-manifest v1 is retained. Hardware and
admission v2 deliberately reject incomplete hardware v1 rather than infer missing
provenance. This is not a change to benchmark timing JSONL, v1 workloads, analysis
or Phase 5C archive profiles. No production algorithm, API, heuristic, timing,
dependency pin, CMake registration, CI workflow or existing timeout changes.

Full validation commands/outcomes and remaining limitations are recorded below
once executed. No performance collection, speedup, TSan acceptance or race-freedom
claim is authorized by these infrastructure checks.

### Phase 6B-1R completed local verification

All commands below actually ran. focused-results.json retains exact argv/exit/log
references for the first five; gate-results.json retains the three sandbox driver
attempts and unsandboxed-result.json the approved separate sanitizer attempt.

```sh
python3 -B tests/test_campaign.py
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/test_negative_diagnostics.py
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-phase6b1r-repair
.venv-analysis/bin/python -B tools/validation/check_environment.py
python3 -B tools/validation/ci_verify.py --mode debug --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1r-debug
python3 -B tools/validation/ci_verify.py --mode release --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1r-release --smoke
python3 -B tools/validation/ci_verify.py --mode sanitize --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1r-sanitize
python3 -B tools/validation/ci_verify.py --mode sanitize --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1r-sanitize-unsandboxed
```

Results: 62 campaign tests passed (including all eight initially red regressions),
59 archive regressions passed, three diagnostic controls passed, 17 infrastructure
regressions passed, and the existing exact dependency/Agg environment gate passed.
No installation was performed. Additional source AST parsing and installed PyYAML
loading plus bash -n of all six workflow command blocks passed; GitHub expressions
were replaced with literal placeholders for shell syntax checking only. Workflow
bytes and existing timeouts were unchanged; this is not hosted CI verification.

Fresh Debug and Release each built and passed 31/31 required tests. Release also
completed the existing tiny full-trace/per-update harness smoke, analysis and
intended negative controls. These remain harness validation, not performance data.
The fresh sandbox sanitizer command exited 1 after CTest exit 8, with explicit
LeakSanitizer ptrace-incompatibility diagnostics. Its logs, failure marker and
failed-run archive are preserved. The separately approved outside-sandbox command
used a new directory, retained leak detection and halt-on-error settings unchanged,
and passed 31/31 ASan+UBSan tests. No failed run was relabeled or overwritten.

The full gates all captured source inventory
98a95fdf4906903564064fb7c159c7471e1e1288b5d19c1050d3676596bd4b67.
Every implementation/test byte matches implementation-sha256.json and the final
working implementation: no implementation or test edits postdate the gate runs.
Only this verification outcome text was appended afterward.

Each driver created an archive and sidecar. Independently reopened all four with
the repository verifier, then copied archive/sidecar pairs and a trusted standalone
verifier kit under phase6b1r/. For each copy, sha256sum -c passed, followed by an
isolated Python -I -S -B launcher using only the copied kit and --verify/--sidecar.
All copied checks exited 0. The three success profiles returned verified/passed/31;
the sandbox-failure archive returned integrity-verified/failed/command-failed,
without a passed-count claim. offline-results.json records exact copied commands,
results and archive hashes. Complete nested raw evidence is inside the archives;
selected receipts/reports/logs are also preserved separately, without build trees.
The kit is not loaded from archived untrusted source.

Direct reproducer outcomes are saved in after-reproducers.json:

| Finding | Before repair | After repair |
| --- | --- | --- |
| F1 overlapping mounts, one-CPU parent | CLI 0, scientific allowed | CLI 1, ancestor quota rejection |
| F2 invalid PID/path/soname/stat | CLI 0, scientific allowed | CLI 1, contradictory mapping rejection |
| F3 nonallocated sibling inconsistency | CLI 0, scientific allowed | CLI 1, topology rejection |
| F4 unpaired surrogate path | CLI 0, accepted | CLI 2, controlled encoding diagnostic |

The original development-plan hash and complete expanded manifest are unchanged
(byte-for-byte comparison with preserved Phase 6B-1 CLI output), recorded in
planning-compatibility.json. static-checks.json records unchanged production,
public APIs, algorithms, heuristic/timing code, CMake registrations, workflow,
existing schemas/workload goldens, analysis, dependency pins and archive tools
against 95c515f. All 128 preserved Phase 6B-1 evidence-file hashes still match.
Final git diff --check passed. No historical evidence was modified.

Remaining limitations: supplied records/declarations are not host authentication;
visible mounts do not establish absence of hidden restrictions; compiler/build
linkage and exclusive reservation verification remain separate requirements.
Snapshots and file/process rechecks do not establish execution-time stability.
Unavailable optional NUMA does not establish a placement policy. Hardware v1
requires recapture as complete v2, with no inferred upgrade. Later execution,
resource enforcement, actual-team collection, inference and replication remain
deferred. No performance campaign, tuning, TSan acceptance or race-freedom claim.
Stop after the authorized local remediation commit; no push, merge or PR.

## 2026-10-30 — Phase 6B-1R2 runtime provenance remediation

Started clean at c45c760b134f49feb0c9c37fd7d96eb5e8d39eaf on
feature/phase6b-campaign-foundation. The user authorizes N1/N2 implementation,
fresh validation and a local commit, without push, merge, PR or performance work.
Prior Phase 6B-1 and 6B-1R evidence hashes are captured under the new ignored
results/validation/phase6b1r2 directory before edits. No prior evidence is rewritten.

Independently reran the audit's plain-text mmap reproducer and mapping mutation
matrix before implementation. The fake read-only libgomp file was collected and
scientifically admitted (API true, CLI 0). Added four test methods before fixes:
both plain-text and genuine read-only data mappings, unaligned address/offsets,
and out-of-bounds/overflow offsets. The 66-test red run retained the original 62
passing tests with six failing subcases, saved in red-regressions.log. Original
independent outputs are before-n1.log and before-mutations.log.

N1 root cause was inferring linkage/SONAME from a filename plus file mapping,
without checking ELF structure, executable segments or an explicit dependency.
N2 root cause was discarding mapping offsets and never reconciling page/file/ELF
geometry. New campaign_elf.py performs bounded standard-library ELF64 parsing;
runtime evidence v3 contains raw metadata excerpts for pure offline reparsing,
explicit page size, and complete file-backed load geometry. The supported direct
DT_NEEDED + actual SONAME + complete mappings relationship and its narrow platform
scope are specified in campaign-foundation.md. It does not prove active execution
or symbol binding and is not host authentication. Unsupported/legacy scientific
runtime records reject; plan/trial/hardware/admission versions remain unchanged.

The first repaired 66-test run closed the original failures and exposed one old
collector mock that did not provide the newly required ELF file snapshots. Its
actual output is retained as first-green-attempt.log. Updated that mock to preserve
its original identity/change assertions, retained all previous test cases, and
added independently built synthetic metadata plus a real trusted idle linked
process fixture. No candidate or benchmark is launched by the collector.

### Phase 6B-1R2 completed verification

All commands below actually ran. Exact profile argv, controlled environments,
command receipts and raw outcomes are retained in the three new archives and in
results/validation/phase6b1r2/verification-summary.json. No dependencies were
installed. The sanitizer command used the explicitly approved outside-sandbox
execution path; leak detection and halt-on-error settings were not weakened.

```sh
python3 -B tests/test_campaign.py
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/test_negative_diagnostics.py
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-phase6b1r2-repair
.venv-analysis/bin/python -B tools/validation/check_environment.py
python3 -B tools/validation/ci_verify.py --mode debug --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1r2-debug
python3 -B tools/validation/ci_verify.py --mode release --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1r2-release --smoke
python3 -B tools/validation/ci_verify.py --mode sanitize --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1r2-sanitize-unsandboxed
```

Results: final campaign suite 75 tests passed; archive regressions 59 passed;
diagnostic controls 3 passed; infrastructure regressions 17 passed; exact installed
analysis dependencies and Agg renderer gate passed. The earlier expanded run had
73 passing tests; the final 75 includes additional metadata/RELRO and descriptor
checks. Final-campaign.log retains the final run. All original F1–F4 regressions
remain present and pass.

Fresh Debug, Release and approved outside-sandbox ASan+UBSan each built and passed
31/31 required CTest tests. Release also completed full-trace and per-update smoke,
analysis, raw-artifact checks and intended negative controls. These are harness
validation results, not performance experiments or speedup evidence. Sanitizer
options remained ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 and
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1. No new sanitizer failure occurred;
all historical failed sanitizer archives/logs remain separately preserved and
hash-identical. No TSan acceptance, hosted CI or race-freedom claim is made.

Each full driver created and independently reopened its archive/sidecar pair.
Copied all three pairs into the new evidence directory, then independently ran
sha256sum -c and the trusted copied verifier with Python -I -S -B, --verify and
--sidecar. All six copied checks exited 0. Offline results were verified/passed/31
for debug-full-v1, release-smoke-v1 and sanitize-full-v1; Release smoke=true.
The verifier kit comes from current trusted repository files, never archived code.
Complete nested raw evidence remains inside the archives; build trees are omitted.

All three gates captured identical source inventory
ac07aa6b5f87ecb4dbf3192fe059ceee211b4de0de56f5b44a095a1d55734aa5.
Their captured implementation and test bytes match the five entries in
implementation-sha256.json and the final implementation. No implementation or test
changes postdate those gates; only this outcome documentation was appended later.

Independent after-reproducer results are retained under reproducers/ and in
static-compatibility-reproducers.json and after-n1-api-cli.log:

| Case | Before | After |
| --- | --- | --- |
| Plain-text file, read-only mmap | runtime collected; science true; CLI 0 | collector/CLI inspect unavailable; science false; admission CLI 1 |
| Genuine libgomp mapped only as data | runtime collected; science true | collector/CLI inspect unavailable; science false; admission CLI 1 |
| Unaligned VMA start | science true; CLI 0 | science false; CLI 1 |
| Unaligned file offset | science true; CLI 0 | science false; CLI 1 |
| Out-of-bounds/overflow file offset | science true; CLI 0 | science false; CLI 1 |
| Trusted idle direct-linked helper | not previously required | genuine five-VMA runtime v3 collected; positive synthetic-hardware API/CLI admission |

The positive runtime observation is a real procfs record; the rest of its hardware
fixture is explicitly synthetic. It is not an admission claim for this shared host.
No candidate is executed by collection and no benchmark is run by these reproducers.
Older/incomplete runtime records reject science while development remains admitted
with scientific failures and scientific_performance_allowed=false.

The representative 104-trial development manifest is byte-identical to preserved
Phase 6B-1 output. Plan SHA-256 remains
f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24;
manifest SHA-256 remains
f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a.
All 263 captured prior Phase 6B-1/6B-1R evidence files still match their hashes.
Protected-path comparison against c45c760 confirms unchanged production algorithms,
APIs, heuristic/timing/workload/analysis code, existing schemas/goldens/dependency
pins, CMake registration, workflow, archive tools and TSan controls. AST parsing of
50 Python files and installed PyYAML loading plus bash -n for all six workflow
command blocks passed. GitHub expressions were replaced only for local shell
syntax checking. Git diff checks passed; no hosted workflow execution is claimed.

Changed files are AGENTS.md, campaign_hardware.py, campaign_provenance.py, new
campaign_elf.py, test_campaign.py, new campaign_runtime_support.py, this research log
and campaign-foundation.md. Remaining limitations are the documented narrow ELF
platform/layout/linkage subset, unauthenticated excerpts/declarations, non-atomic
snapshots, hidden host restrictions, unverified symbol binding/active execution,
reservation/build provenance and runtime stability. Later execution/inference
remains deferred. Stop after the authorized local commit for independent re-audit;
no push, merge or PR.

## 2026-10-30 — Phase 6B-1R3 ELF layout hardening

Started clean on feature/phase6b-campaign-foundation at audited commit
8cd8bd10da5aa6031765461659ba47498d9b107d. The user authorizes narrow N3/N4
implementation, fresh validation, and a local commit without push, merge or PR.
Captured prior Phase 6B-1/R/R2 evidence hashes under the new ignored directory
results/validation/phase6b1r3 before changes; historical evidence is not rewritten.
Read the full independent audit, repository guidance, runtime collection/admission,
ELF parser, plan contract, tests and campaign/research documentation.

Before implementation, independently reran the audit matrix: the 2 MiB-alignment
and overlapping anonymous-load cases both returned science=true and CLI 0
(before-independent.log). Inspected the genuine local libgomp ELF first: all four
PT_LOAD alignments were 4096 (genuine-runtime-layout.json). Chose the explicitly
permitted conservative restriction p_align <= 4096 rather than adding larger-
alignment loader emulation.

Added regressions before changing production Python. The genuine library was
copied, program headers were modified, and hashes/path/device/inode/size/mtime
were refreshed from the actual files. A genuine observed baseline qualified first;
both modified cases then incorrectly qualified through API and CLI. Synthetic N4
also reproduced. The first red run recorded three failing subcases; its synthetic
N3 fixture also changed a segment whose vaddr differed from offset, unintentionally
violating existing congruence validation. Corrected that test mutation to change
only the first congruent load, before implementation. The final 78-test red run
has four failing subcases, all API true/CLI 0, with the original 75 tests passing
(red-regressions-final.log). The first attempt is retained separately.

N3 root cause: checking static p_align congruence while reconciling only kernel
page alignment allowed unsupported larger-alignment origins. Every PT_LOAD now
rejects p_align > PAGE; existing 0/1/power-of-two, congruence and page-bias checks
cover the deliberately restricted accepted subset. N4 root cause: overlap checks
used p_filesz and omitted zero-file-size loads, allowing anonymous zero-fill to
clobber certified executable pages. Overlap analysis now uses checked page-rounded
p_memsz intervals for all nonempty loads. Mapping reconciliation also checks
translated memory endpoints for anonymous-only loads without requiring file VMAs
for them. This avoids overflow outside the file-backed coverage loop.

The first repaired 78-test run passed. Added nearby tests for supported/invalid/
unsupported alignments (including an aligned but unsupported larger origin),
congruence, RX/RW/partial-page overlap, nonoverlapping anonymous BSS, ordinary BSS,
empty loads, adjacent and overlapping file-backed loads, memory-endpoint/page-
rounding overflow, and anonymous relocation overflow. Exact rejection diagnostics
are checked so unrelated fixture failures cannot satisfy the original regressions.
No runtime v3 fields, dependency pins, algorithms or existing evidence contracts
change. The full supported layout and trust limitations are in campaign-foundation.md.

### Phase 6B-1R3 completed fresh validation

All commands below actually executed; exact driver argv, controlled environments,
command receipts, raw results and inventory bindings are retained in the fresh
archives and results/validation/phase6b1r3/verification-summary.json. No dependencies
were installed. The sanitizer command ran through the approved outside-sandbox
path, retaining leak detection and halt-on-error settings.

```sh
python3 -B tests/test_campaign.py
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/test_negative_diagnostics.py
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-phase6b1r3-repair
.venv-analysis/bin/python -B tools/validation/check_environment.py
python3 -B tools/validation/ci_verify.py --mode debug --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1r3-debug
python3 -B tools/validation/ci_verify.py --mode release --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1r3-release --smoke
python3 -B tools/validation/ci_verify.py --mode sanitize --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b1r3-sanitize-unsandboxed
```

Fresh outcomes: 85 campaign tests, 59 archive regressions, 3 diagnostic controls
and 17 infrastructure regressions passed. The installed exact dependency/Agg gate
passed without installation. The original F1–F4/N1–N2 protections remain covered.
Fresh Debug and Release each built and passed 31/31 required CTest tests. Release
also completed full-trace/per-update smoke, analysis, artifact checks and intended
negative controls. Approved outside-sandbox ASan+UBSan built and passed 31/31,
with ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 and
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 unchanged. No new sanitizer failure
occurred. These are local validation executions, not performance experiments,
hosted-CI verification, TSan acceptance or race-freedom/scalability evidence.

Each driver created an archive and SHA-256 sidecar and independently reopened it.
Copied all three pairs, then ran sha256sum -c and the copied trusted verifier
through isolated Python -I -S -B with --verify/--sidecar. All six copied checks
passed: debug-full-v1, release-smoke-v1 and sanitize-full-v1 each verified/passed/31;
Release smoke=true. The kit is copied from trusted current repository files,
never untrusted archived code. Nested raw evidence is retained without build trees.
Historical Phase 6B-1 and 6B-1R failed sanitizer archives were also independently
verified using that kit; both remain integrity-verified/failed/command-failed.
Their raw diagnostics and all 911 captured prior evidence-file hashes are unchanged.

All three fresh gates captured the same source inventory:
abaf558a1f8c8b5228becdea2f4109ea426a9e9fcfceb243f9e893ba17f279d3.
Final campaign_elf.py, test_campaign.py and campaign_runtime_support.py bytes match
implementation-sha256.json and every gate's source inventory. No implementation
or test edits followed those gates; only this verification outcome text was added.

The independent audit matrix was repeated after remediation. Its original script
assumed the mutated alignment record could be reparsed while constructing a bias;
the new fail-closed parser now rejects at that point. Preserved that initial
harness result separately, then derived the test bias from the valid baseline
instead. The completed matrix retained its valid genuine-runtime baseline and
rejected N3 and N4 through API/CLI (science=false, CLI 1), alongside N1/N2 nearby
adversaries. Both original binary-backed audit fixtures still have file hashes
matching their declared plans; admission now rejects them, and elf_file rejects
with the exact unsupported-alignment/overlapping-memory diagnostic. Results are in
after-actual-audit-files.json, after-independent.log and retained reproducer records.
The self-contained regression tests also create fresh modified genuine files,
refresh hashes and stat identities, and check the exact diagnostic through the
parser/collector API after API/CLI rejection. No candidate ELF is executed or loaded.

The representative manifest remains byte-identical to retained original Phase
6B-1 output: 104 trials, plan SHA-256
f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24,
manifest SHA-256
f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a.
Development mode still admits incomplete scientific evidence only with science
false. Runtime v3 fields, collection/admission callers, plan contract and manifest
code remain unchanged. Protected-path comparisons confirm unchanged production
algorithms/APIs, timing, heuristics, workloads/goldens, analysis, dependency pins,
CMake registration, workflow, Phase 5C archive tools/contracts and TSan controls.
Python AST checks (50 files), installed PyYAML loading, bash -n of all six workflow
command blocks and Git diff checks passed. GitHub expressions were replaced only
for local shell syntax checks; no hosted workflow run is claimed.

The six changed files are campaign_elf.py, test_campaign.py,
campaign_runtime_support.py, AGENTS.md, campaign-foundation.md and this research
log. Remaining limitations are the documented restricted platform and layout,
unauthenticated supplied excerpts, non-atomic snapshots, uncertified anonymous
contents, unverified symbol binding/active execution, ownership/build provenance
and execution-time stability. Later execution/inference remains deferred. Stop
after the authorized local commit for independent review; no push, merge or PR.

## Phase 6B-2A deterministic development pilot implementation

Authorized base: abd641381e9df6b25ed217dd43686d4f66028b82 on
feature/phase6b2-execution-harness, initially clean. The explicit Phase 6B-2A
request authorizes implementation, bounded development harness verification and a
local commit only. No push, PR, merge, full campaign or scientific experiment.
No dependency installation, production/timing/heuristic/workload-golden changes,
Phase 5C contract changes or workflow/default-test registration changes.

Added campaign_process.py (POSIX bounded pipes/process groups) and
campaign_pilot.py (selection, staging, correctness, v1 records/index, atomic
publication and offline evidence verification); extended campaign.py with pilot
and verify-pilot. Existing manifest generation/admission and artifact/full
preflight/worker validators are reused. The new focused test_campaign_pilot.py
covers synthetic failures and three tiny selected real-worker phase controls.
The runbook campaign-pilot.md specifies schemas, exact bounds, preparation,
verification, trust boundaries, unsupported cases and 6B-2B deferrals. Updated
AGENTS, README, experimental protocol and the foundation cross-reference.

The first 28-test focused run passed. Added shared trial/campaign deadline,
environment and truncation coverage: 32 tests passed. These are correctness and
harness controls; captured timing is never scientific measurement evidence.
Every pilot result has measurement_eligible=false, actual team size null, and
explicit development admission. Unsupported large workloads have unavailable
bounded oracles and are not executed. Requested affinity is recorded separately
from observed parent affinity; no placement or physical-core exclusivity claim.

Validation commands and final outcomes are recorded below after fresh execution.

### Phase 6B-2A final fresh validation

Actually executed:

```sh
python3 -B tests/test_campaign_pilot.py
python3 -B tests/test_campaign.py
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/test_negative_diagnostics.py
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-phase6b2a-repair
python3 -B tools/validation/ci_verify.py --mode debug --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b2a-debug
python3 -B tools/validation/ci_verify.py --mode release --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b2a-release --smoke
python3 -B tools/validation/ci_verify.py --mode sanitize --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b2a-sanitize-unsandboxed
```

Final focused outcomes: pilot 32/32 (including real worker controls for diagnostic,
warmup and measured selections); campaign 85/85; archive 59/59; diagnostics 3/3;
infrastructure 17/17. Python AST parsing and git diff --check passed. Installed
pinned analysis dependencies/Agg passed without installation. Fresh Debug,
Release and approved outside-sandbox ASan+UBSan each built and passed 31/31 default
CTest tests. Release smoke and all nine intended negative smoke controls passed.
Sanitizer receipt retains ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 and
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1. No hosted CI or TSan acceptance,
race freedom or scientific performance validation is claimed.

The three gate archives and SHA-256 sidecars were copied into ignored
results/validation/phase6b2a/archives, with raw non-build evidence beside them.
Fresh isolated Python -I -S -B verification using a copied trusted offline kit
returned verified/passed/31 for debug-full-v1, release-smoke-v1 and
sanitize-full-v1; Release smoke=true. All gates share source inventory
`d4cc392dda4eafb03b8d228ce4080e3f9eaf01790ed75696635907771bf55537`.
Implementation/test digests match implementation-sha256.json after the gates;
only this final outcome text was appended afterward. Focused outcomes and manifest
compatibility are recorded in results/validation/phase6b2a/summary.json.

A separate successful CLI control used a copy of the fresh Debug benchmark and
one explicitly selected measured-phase trial, followed by verify-pilot. Both
exited 0; result measurement_eligible=false, actual team size unavailable. It is
retained in results/validation/phase6b2a/cli-pilot. This fixture's plan intentionally
substitutes the actual executable hash into the development example; it is not
Release build attestation. Its deterministic execution-manifest SHA-256 is
477c5e5cd361eded967f62a08c8b6380cf41363a9900f460f8539f664c4ecdd9.
The result-index SHA-256 is
f269800adf007752968ef8b219502d0c7ff89cfe91c9250bba58fdf7eca0ab45;
that index includes nondeterministic timestamps and is not a scheduling identity.

The original representative Phase 6B-1 manifest remains byte-identical to retained
evidence: 104 trials, plan SHA-256
f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24,
manifest SHA-256
f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a.
Protected-path comparison against abd6413 confirms unchanged algorithms, APIs,
benchmark timing, heuristic thresholds, workload/configuration goldens, dependency
pins, CMake/CTest registration, CI workflow, campaign plan/admission/ELF contracts
and Phase 5C validation tooling. Historical Phase 5 evidence remains untouched.

Ten intended files: AGENTS.md, README.md, campaign.py, new campaign_pilot.py and
campaign_process.py, campaign-foundation.md, new campaign-pilot.md,
experimental-protocol.md, this research log and new test_campaign_pilot.py.
No unresolved validation failure. Known limits include synchronous filesystem/
publication overhead beyond launch deadlines, inherited child affinity, no
execution-time team/runtime/exclusivity observation, no OS memory isolation,
trusted executable/process-group scope and unauthenticated evidence hashes.
Scientific execution, larger workloads, placement/resource isolation, resume,
retry, full matrices, analysis/visualization and inference remain Phase 6B-2B or
later work requiring separate authorization. Stop after the authorized local
commit; no push, merge or pull request.

## Phase 6B-2A-R1 correctness and evidence hardening

Started at e1e1f52b5ec0dc7b6b5ed3b16997a2d7982e7026, clean, on the existing
feature/phase6b2-execution-harness branch. The explicit R1 request authorizes
remediation, bounded tests, fresh full local validation and one local commit;
no push, merge, PR, complete campaign, dependency installation or scientific run.

Before implementation, reran /tmp/dynagraph-6b2a-audit/reproduce.py with correctness,
verifier, capture and fifo. All findings reproduced: the faulty distance
123456789 instead of 29 was certified success; rehashed command/stderr/affinity/
stream-limit contradictions were accepted; cap 128 produced 192 stderr bytes;
the FIFO verifier needed external timeout cleanup. Added red regressions first:
four tests produced nine failed assertions/subtests and one FIFO timeout error.
The red log is retained separately; no historical fixture was rewritten.

P1 root cause: inherited verify_preflight checked distance structure and source,
then trusted the executable's remaining check flags. Added campaign_oracle.py:
reuse graph/trace parsing and ordered expected-old ledger replay, compare final
weights/hash, then synchronous edge-list Bellman–Ford over the actual replayed
final graph. This follows tests/test_workload_loader.py's independent Python
oracle, kept local to the bounded pilot rather than importing a test module or
changing Phase 5C's existing validator. Every distance, including null unreachable
labels, must agree. Every selected trial class receives its own preflight/oracle;
the existing timed worker final-state and per-update C++ checks remain unchanged.

P2 root cause: argv[1] and inventory consistency did not bind full commands or
required streams. Pilot execution/trial/index schema v2 adds stream sizes, hashes
and effective limits. Shared fixed-relative argv reconstruction binds the complete
command to the plan/trial/recipe source and works after relocation. Every receipt,
including failures, must reconcile both streams, exact names, inventory hashes,
sizes, affinity, OpenMP controls, exit/signal/truncation and status. Failed runs
remain integrity-verifiable as failures; later process/trial launches are rejected.
Older pilot v1 evidence is preserved and rejected, never automatically upgraded.
Plan/manifest v1, hardware/admission v2 and runtime provenance v3 are unchanged.

P3 root cause: error text was appended with a fresh full-cap allowance. Diagnostics
now consume remaining stderr capacity only, with truncation marked when omitted;
capture-error classification and group cleanup persist even at zero free space.
P4 root cause: generic read_json opened the initial inventory before file-type
checks. All pilot metadata now uses a bounded nonblocking descriptor reader,
O_NOFOLLOW directory walks and leaf opens, and regular-file fstat before reading.
FIFOs, sockets, devices, directories, symlinks and oversized metadata reject.

Expanded regressions cover all trial classes, rehashed contradictions, reachable/
unreachable distance corruption, source/length/weights/ordered replay, missing
references, zero cycles, relocated evidence, failure reconciliation, limits
0/1/64/128/1048576, saturated diagnostics, simultaneous streams with read errors,
and nonregular metadata via API/CLI. The first socket fixture failed with EPERM
inside the sandbox; the approved outside-sandbox suite exercised the real socket
case and passed. This is recorded as an environment restriction, not a code pass.
Final validation outcomes follow below after fresh execution.

### Phase 6B-2A-R1 final fresh verification

Actual commands:

```sh
python3 -B tests/test_campaign_pilot.py
python3 -B tests/test_campaign.py
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/test_negative_diagnostics.py
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-phase6b2ar1-repair
python3 -B tools/validation/ci_verify.py --mode debug --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b2ar1-debug
python3 -B tools/validation/ci_verify.py --mode release --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b2ar1-release --smoke
python3 -B tools/validation/ci_verify.py --mode sanitize --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b2ar1-sanitize-unsandboxed
```

Pilot regressions ran through the approved outside-sandbox path to cover the Unix
socket fixture: 47/47 passed (baseline 32 plus 15 new methods and adversarial
subtests). Campaign 85/85, archive 59/59, diagnostic 3/3 and infrastructure 17/17
passed. Python AST checks covered 52 files; bash -n passed all six workflow run
blocks, substituting GitHub expressions only for local syntax checking. Git diff
checks passed. No hosted workflow execution is claimed.

Fresh Debug and Release each built and passed 31/31 required CTest tests; Release
smoke and all nine intended negative smoke controls passed. Approved outside-
sandbox ASan+UBSan built and passed 31/31, with leak detection enabled:
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 and
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1. Installed pinned dependencies/Agg
passed without installation. These are local correctness/harness checks, not
scientific execution, hosted-CI success, TSan acceptance or race freedom.

All three drivers generated fresh archives and SHA-256 sidecars, then reopened
them. Copied the pairs and non-build raw evidence into ignored
results/validation/phase6b2ar1. A copied trusted kit under isolated Python
-I -S -B independently verified each copied archive/sidecar: debug-full-v1,
release-smoke-v1 (smoke=true), sanitize-full-v1, each verified/passed/31.
All three gates share source inventory
5279f49674d85530da059130f4c1cf63d3b345e9ab638fc9506f00b0286fe82b.
Implementation/test hashes still match implementation-sha256.json; only this
final outcome text was appended after the gates. Raw focused/red/independent
logs, kit, archive receipts and verification-summary.json are retained there.

Reran the original bounded reproducers after remediation. The distance fault now
exits 1, trial failed/correctness-failed, checked=true/outcome=failed, with the
independent oracle method recorded. Offline verification correctly reports that
intact evidence's execution_status=failed. Capture cap 128 now yields 128 stderr
bytes, preserving capture-error and truncation. FIFO verification promptly exits
2. The old P2 reproducer's original v1 bundles are rejected at the explicit schema
gate. Separately derived a fresh v2 independent CLI pilot and mutation matrix:
valid measured selection passed; argv, missing stream reference, affinity, cap,
exit, signal, correctness, eligibility and schema contradictions all exited 2.
Distance/source mutations with fully refreshed receipt and inventory hashes also
reject in the regression suite, exercising the semantic gates beyond hash checks.
Copied the fresh valid pilot, then verified it at its new location: complete,
measurement_eligible=false, schema v2. No archived executable was run by verification.

The 104-trial original manifest is byte-identical to retained Phase 6B-1 evidence:
plan SHA-256 f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24,
manifest SHA-256 f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a.
Checked all 6,527 captured prior non-build evidence file hashes plus the retained
911-entry R3 preservation map: zero mismatches. The historical Phase 6B-1 and
6B-1R failed sanitizer archive/sidecar pairs independently remain
integrity-verified/failed/command-failed. Historical evidence was not rewritten.

Nine intended files: AGENTS.md, campaign.py, campaign_pilot.py,
campaign_process.py, new campaign_oracle.py, test_campaign_pilot.py,
campaign-pilot.md, experimental-protocol.md and this research log.
Protected-path comparison against e1e1f52 confirms unchanged production SSSP,
APIs, timing brackets, heuristics, workload/configuration goldens, dependency
pins, workflow, CMake/CTest registration, experiment_records.py, workload code,
Phase 5C contracts and Phase 6B-1 hardware/provenance/ELF protections.

No unresolved validation failure. Remaining limits: unauthenticated/fabricable
supplied evidence, trusted executable behavior, synchronous filesystem overhead
outside launch budgets, no hostile-process sandbox or OS memory isolation,
unobserved child affinity/runtime/team/exclusivity and no execution-time stability
proof. The independent Python oracle checks each trial's preflight final vector;
timing workers keep their original C++ final checks and do not expose a second
Python-checked timed vector. Larger/scientific campaigns, placement/resource
isolation, richer execution observations, resume/retry, analysis/visualization,
inference and performance claims remain separately authorized 6B-2B or later work.
Stop after the local remediation commit. Do not push, merge or create a PR.

## Phase 6B-2B-1 recovery contracts and execution journal

Started clean at 71b7ec7c8cadd25c83f43d73464cef2d47ad9fc2 on
feature/phase6b2b-recovery-provenance. The explicit request authorizes a local
implementation/validation/commit only. Actual resume/retry, scientific execution,
resource isolation, analysis and inference remain deferred. No push, PR, merge
or dependency installation. Prior phase evidence retains its historical meaning.

Added campaign_journal.py with separate journal schema v1, leaving pilot evidence
v2 unchanged. An exclusive new journal directory contains canonical immutable
sequence files with SHA-256 transition identities and a previous-entry hash chain.
The creation entry binds plan/manifest/execution identities, ordered selected
trials, limits, effective OpenMP request identities, hardware/admission identities,
development classification and evidence schema. A launch-intent transition is
published before child creation; terminal transitions bind an atomically committed
trial record's exact path/hash/reason. Invalid order, duplicate transitions,
unknown fields, torn committed bytes, nonregular metadata and unsupported versions
fail closed. Unpublished temporary files are never accepted as transitions.

Recovered completion uses extracted shared pilot_context/verify_trial_evidence
functions from the existing v2 verifier, including the independent Bellman–Ford
and full worker gates. No parallel weaker correctness verifier or schema upgrade.
Full final v2 verification is required whenever the final inventory exists.
A missing journal terminal leaves an indeterminate trial even if its record
independently verifies complete; that evidence fact is reported separately.
Terminal journal claims with missing/changed/failed evidence reject. Prior valid
completed terminals can be inspected before final run-index/inventory publication,
with overall incomplete status. Inspection is read-only and never resumes or
signals a process. Old v2 evidence without a journal still passes verify-pilot;
inspect-recovery requires a committed journal identity and never migrates history.

Persistence uses the existing write/flush/fsync/exclusive-link/directory-fsync
primitive. Exclusive directory creation and per-sequence no-replace publication
prevent silent competing-writer overwrites. Journal write errors stop launches
and final publication. Atomic visibility does not claim survival under arbitrary
hardware/filesystem failure or distributed-writer consensus. SIGTERM in the CLI
uses the existing interruption/group-cleanup path through a scoped handler; API
callers retain signal-policy ownership. Abrupt death cannot execute cleanup and
may leave children live; inspection reports indeterminate, never infers liveness.

Initial validation: 28 recovery tests and existing pilot 47/47 passed. Added four
boundary tests for pending state, missing/noncanonical sequence fields, duplicate
writer transitions and real Unix-socket rejection. Focused suites run outside the
socket-restricted sandbox to exercise sockets. Tests explicitly clean up owned
child groups after controlled SIGKILL; they execute only tiny bounded fixtures.
Final validation commands/outcomes are recorded below after fresh execution.

### Phase 6B-2B-1 final fresh validation

Actually executed the following commands. Recovery and pilot focused suites used
the approved outside-sandbox path for actual Unix-socket fixtures; no installation.

```sh
python3 -B tests/test_campaign_journal.py
python3 -B tests/test_campaign_pilot.py
python3 -B tests/test_campaign.py
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/test_negative_diagnostics.py
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-phase6b2b1-repair
python3 -B tools/validation/ci_verify.py --mode debug --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b2b1-debug
python3 -B tools/validation/ci_verify.py --mode release --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b2b1-release --smoke
python3 -B tools/validation/ci_verify.py --mode sanitize --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output /tmp/dynagraph-phase6b2b1-sanitize-unsandboxed
```

Fresh focused results: recovery journal 32/32, pilot 47/47, campaign 85/85,
archive 59/59, diagnostics 3/3 and infrastructure 17/17. Python AST parsing covered
54 files; all six workflow shell blocks passed bash -n after local expression
substitution. Git diff checks passed. Protected-path comparison against 71b7ec7
confirmed unchanged algorithms/APIs, timing brackets, heuristics, workload goldens,
pins, CMake/CTest registration, workflow, Phase 5C tools/contracts, independent
oracle and Phase 6B-1 hardware/provenance/ELF protections. Existing pilot tests were
not edited. Shared verification extraction preserved all v2 gates and identities.

Fresh Debug, Release and approved outside-sandbox ASan+UBSan each built and passed
31/31 required CTest tests. Release smoke and all nine negative smoke controls
passed. Leak detection remained enabled via
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 and
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1. Installed pinned dependency/Agg
checks passed without installation. No hosted CI, TSan acceptance, race freedom
or scientific performance/scaling result is claimed.

Each driver generated fresh archives and SHA-256 sidecars and independently
reopened them. Copied all three pairs and non-build evidence into ignored
results/validation/phase6b2b1. A copied trusted repository verifier kit, run under
isolated Python -I -S -B with --verify/--sidecar, verified debug-full-v1,
release-smoke-v1 and sanitize-full-v1: each verified/passed/31, Release smoke=true.
All gates captured source inventory
135590e6d53964450dd48892358ace8891594ad62a336a82d93fc67880f4872c.
Implementation/test bytes match implementation-sha256.json; only this outcome
text was appended after the gates. Raw focused logs, command receipts, kit,
archives, sidecars, compatibility.json and verification-summary.json are retained.

A separate controlled CLI run selected one measured-phase development trial with
an actual executable digest in a disposable plan/bundle. Pilot, verify-pilot and
inspect-recovery all exited 0. Inspection reported settled, three committed
entries, completed journal state and verified-complete evidence, with false
measurement eligibility and no observed-team inference. Copied that evidence to
its retained location and re-inspected it successfully. CLI commands and raw JSON
are in cli-checks.json; the complete development-only control is in cli-pilot.
Tests additionally exercised SIGTERM (interrupted terminal), SIGKILL (indeterminate,
no inferred child liveness), journal I/O failure, missing final publication and
successful evidence without a terminal transition. Owned test child groups were
explicitly cleaned up after abrupt parent death.

The original representative manifest remains byte-identical to retained evidence:
104 trials, plan SHA-256
f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24,
manifest SHA-256
f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a.
All 7,144 captured prior non-build evidence file hashes and the retained 911-entry
R3 preservation map match. Historical Phase 6B-1 and 6B-1R failed sanitizer archive
pairs independently remain integrity-verified/failed/command-failed. No historical
evidence was rewritten or reclassified as successful.

Ten intended files: AGENTS.md, campaign.py, campaign_pilot.py,
campaign_process.py, new campaign_journal.py, new test_campaign_journal.py,
new campaign-recovery.md, campaign-pilot.md, experimental-protocol.md and this log.
No unresolved validation failures. Residual limits include unauthenticated and
non-atomic observations, content identity rather than a unique global run nonce,
local POSIX hard-link/fsync assumptions, no arbitrary hardware-failure durability,
no liveness/ownership inference after abrupt parent death, synchronous filesystem
overhead outside launch budgets and no OS memory/security sandbox. Read-only
inspection never repairs or resumes; actual resume/retry behavior, stronger
process/resource ownership, scientific execution and later inference remain
separately authorized Phase 6B-2B-2 or later work. Stop after the local commit;
no push, PR or merge.

## Phase 6B-2B-1-R1 deadline enforcement remediation

Started clean at e2d84b79553858f0a7a467358331f6f59bf5e09e on the existing
feature/phase6b2b-recovery-provenance branch. The explicit request authorizes
this targeted implementation, bounded validation and a local commit only;
no push/merge/PR, dependency installation, automatic resume or retry.

Reran the original /tmp/dynagraph-6b2b1-audit/deadline_fsync.py before editing:
a 1.2-second journal directory fsync delay with one-second overall/trial budgets
launched at 1.2288 seconds with stale timeout 0.9750 seconds; the pilot reported
complete and recovery reported settled/verified-complete. Retained the baseline
log. Added a red marker-child regression first; it failed because a child actually
started after expiry. The fixture writes a launch marker before exec of the
trusted small benchmark, not merely a synthetic reported-timeout assertion.

Root cause: remaining time was read before journal publication and reused after
synchronous publication/fsync, potentially authorizing an already-expired launch.
The pilot now computes fixed argv before its final clock check, rereads monotonic
time after publication, and passes only the fresh remaining budget with the same
absolute min(overall deadline, trial deadline). Both preflight and timing launches
use this function. No deadline is extended or reset. The process layer additionally
checks after selector setup immediately before Popen and uses the same absolute
cap when draining/waiting. It raises an internal LaunchDeadlineExpired exception
when it knows no process was created; the caller records no invented process
receipt, exit code or streams. Known-expired budgets become explicit overall
budget-exhausted or per-trial timeout failures and halt subsequent trials.

A durably published launch intent is not proof of an actual process start. The
existing v2 record and journal v1 already represent failed-without-process evidence.
Terminal failures publish normally where possible; a terminal-write failure leaves
indeterminate/incomplete evidence. No evidence schema change, automatic upgrade
or historical evidence reinterpretation. Userspace checks cannot promise a strict
real-time boundary against arbitrary OS descheduling/native spawn latency; the
contract prevents known-expired authorizations and has no unbounded application
journal/filesystem work after the final process-layer check.

Fourteen new deterministic deadline tests cover timely, exact and exceeded journal
publication, delayed directory fsync, fresh tiny/minimum budgets, both deadline
orderings, expiry before intent and after intent, expiry in launch-layer setup,
expiry between preflight and timing, failure publication, actual marker absence,
no later launch, safe recovery classifications and normal successful execution.
Existing synthetic capture wrappers accept the optional absolute-deadline keyword;
checks/assertions remain intact. The existing shared-deadline mock includes the
additional post-publication clock sample. No production/timing/oracle change.

Reran the original reproducer after the fix: it reported zero launches, pilot
failed and recovery failed/budget-exhausted. Its final assertion intentionally
expects the old bug and therefore now fails; preserved that unmodified-reproducer
log separately. A copy with only those obsolete final assertions changed to expect
no launches/failure is /tmp/dynagraph-6b2b1r1-reproducer.py. It passes and retains
the same real directory-fsync injection. Final commands/outcomes follow below.

Fresh final validation (2026-10-30):

- `python3 -B tests/test_campaign_journal.py`: 46/46; pilot: 47/47;
  campaign: 85/85; archive: 59/59; diagnostic controls: 3/3.
- `python3 -B tools/validation/test_repair.py --output
  /tmp/dynagraph-phase6b2b1r1-repair`: 17/17 infrastructure regressions.
- `python3 -B tools/validation/ci_verify.py --mode debug --python
  /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output
  /tmp/dynagraph-phase6b2b1r1-debug`: 31/31 CTest.
- The same driver with `--mode release --smoke --output
  /tmp/dynagraph-phase6b2b1r1-release`: 31/31 CTest, smoke and all nine
  negative smoke controls passed.
- The same driver outside the sandbox with `--mode sanitize --output
  /tmp/dynagraph-phase6b2b1r1-sanitize-unsandboxed`: ASan+UBSan 31/31,
  leak detection enabled, halt-on-error enabled. Existing pinned analysis
  environment and Agg checks passed; no dependencies installed.
- Python AST parsing: 54 files; `bash -n`: six workflow run blocks
  (workflow expressions replaced only for local shell syntax validation).
  `git diff --check` passed.

All three fresh profiles report unchanged source during execution and source
inventory SHA-256
`a1ef55ec369458d5e679d6d6a15f9cf177a021491dee0751fa9366f084c9d54a`.
Copied all three archives and SHA-256 sidecars, then verified with the trusted
copied offline kit under `python3 -I -S -B`: debug-full-v1,
release-smoke-v1 and sanitize-full-v1 all passed. Historical Phase 6B-1 and
6B-1R failed archives remain integrity-verified failed-run-v1, never promoted
to passing results. Prior evidence maps: 7,759 captured retained files and the
911-entry R3 map both have zero mismatches. Large generated evidence remains
ignored under results/validation/phase6b2b1r1; verification-summary.json and
individual receipts preserve commands and outcomes.

Regenerated all 104 trials byte-identically: plan SHA-256
`f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24`;
manifest SHA-256
`f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a`.
Normal one-trial CLI pilot, verify-pilot and inspect-recovery all returned zero;
relocated evidence remained settled, with measurement eligibility false.
Pilot v2 and journal v1 remain unchanged. Protected algorithms, timing brackets,
admission/archive contracts, workload goldens and independent oracle are unchanged.

Nine intended files: AGENTS.md; campaign_pilot.py; campaign_process.py;
test_campaign_journal.py; test_campaign_pilot.py; campaign-recovery.md;
campaign-pilot.md; experimental-protocol.md; this research log. Only this final
outcome documentation was appended after the full gates; implementation/test
SHA-256 receipts remain unchanged. No unresolved validation failures; the
unmodified reproducer's obsolete bug-expecting assertion is documented above.
No hosted CI, performance or race-freedom claim is made. The prior TSan
LIKELY TOOL/RUNTIME LIMITATION classification remains unchanged.

Residual limits: arbitrary OS descheduling/native spawn latency can cross a
real-time boundary after a userspace check; existing local POSIX publication
and durability assumptions remain. Automatic resume/retry, stronger resource
isolation/ownership, Phase 6B-2B-2 execution, scientific experiments and inference
remain deferred pending separate authorization. Stop after the local commit and
report; no push, merge or PR.

## Phase 6B-2B-2 safe development resume

Started clean on feature/phase6b2b2-safe-resume at expected merged base
ab2548d09d0ae68e7b84b7bf0be8705f00dba966. Read existing pilot v2, journal v1,
process, oracle, admission/provenance and recovery contracts before implementing.
The new explicit authorization supersedes the earlier resume deferral only for
this bounded development subset; local commit authorized, no push/merge/PR.

Conservative design chosen before implementation: fully reverify and reuse
completed trials, execute never-launched pending trials, reject failed,
interrupted, launched/indeterminate and contradictory states. Legacy writers
lacked ownership locking, so legacy evidence remains verifiable but cannot safely
resume. New pilots hold a cooperative local-POSIX directory flock through final
publication and publish execution-owner v1 input-root metadata. Resume locks the
same inode and validates all pending input identities before any child starts.
No PID probing or stale PID authorizes retry, and no unrelated process is killed.

A single sibling OUTPUT.resume-v1 reservation holds immutable canonical resume
v1 authorization/terminal events with sequential hash linkage, binding the
original execution, head, snapshot, selected order, limits, authorizations and
attempt sequence 1. The original directory and all committed historical evidence
remain untouched. New pending execution is an ordinary pilot v2/journal v1
under pilot/, reusing the existing command constructor, full verifier and bounded
independent Bellman–Ford oracle. Original/new provenance and reuse are distinct.
Publication uses existing exclusive link/file fsync/directory fsync plus parent
fsync before execution. Any reservation permanently blocks another attempt,
including empty/torn attempts. Repeated interruption is inspectable but repeated
resume is deliberately rejected pending stronger process ownership guarantees.

Budget policy fresh-attempt-including-preflight-v1 explicitly grants one original-
limit wall budget beginning before preflight. Its fixed monotonic deadline flows
through authorization fsync, pilot setup, launch intent and the existing immediate
process-layer check. Per-trial, total-selection and stream limits are unchanged;
no fsync compensation or deadline reset. New pilot ownership publication also
consumes its overall budget. Userspace OS scheduling/native spawn latency remains
a practical real-time limitation. All results remain measurement-ineligible.

The initial 31 resume tests and integrated journal tests passed. Initial sandbox
runs could not bind Unix sockets, so those controls are rerun outside the sandbox.
A synthetic failed-receipt fixture initially contradicted its exit code; corrected
that fixture to represent a genuine nonzero exit. A pilot mock exhausted its
clock samples after an unnecessary duplicate initialization sample; removed the
extra clock read and preserved original mock assertions. Added three further
controls for per-trial expiry, rehashed invalid command binding and real SIGTERM
cleanup. Full fresh validation commands and outcomes follow after completion.

Final review identified a copied-directory ownership bypass in the first draft:
a new directory inode could accept a lock while the original writer was active.
Bound the new ownership marker to output absolute path, device and inode, and
added an independent copied-original rejection test. Relocation remains supported
for ordinary v2 verification, but resume requires the original directory identity.
Fresh final gates supersede the draft-source build results below; no draft result
is claimed as validation of the final implementation. The journal suite is a
direct Python entry point, not a CTest registration; it also imports resume tests.

Draft Debug and Release drivers each passed 31/31 (Release smoke and negative
controls also passed), but predate the ownership-copy fix and are not final-source
acceptance evidence. The concurrent draft sanitizer leg recorded dijkstra TIMEOUT
(30/31 passed); its failed-run archive is retained without promotion. No production
algorithm was changed. Final-source drivers run sequentially to avoid simultaneous
build/test contention, retaining the initial failure and all fresh outcomes.

Final fresh validation (2026-10-30), after the ownership-copy fix:

- `python3 -B tests/test_campaign_resume.py`: 35/35 resume controls.
- `python3 -B tests/test_campaign_journal.py`: 81/81 (46 existing journal/
  deadline controls plus those 35 resume controls); direct Python suite.
- `python3 -B tests/test_campaign_pilot.py`: 47/47, assertions unchanged.
- `python3 -B tests/test_campaign.py`: 85/85;
  `python3 -B tools/validation/test_archive.py`: 59/59;
  `python3 -B tools/validation/test_negative_diagnostics.py`: 3/3.
- `python3 -B tools/validation/test_repair.py --output
  /tmp/dynagraph-phase6b2b2-repair`: 17/17 infrastructure controls.
- Sequential final drivers outside the sandbox:
  `python3 -B tools/validation/ci_verify.py --mode debug --python
  /workspaces/Dynagraph-HPC/.venv-analysis/bin/python --output
  /tmp/dynagraph-phase6b2b2-final-debug`: 31/31 CTest;
  same command with `--mode release --smoke --output
  /tmp/dynagraph-phase6b2b2-final-release`: 31/31, smoke and all nine negative
  controls passed; same command with `--mode sanitize --output
  /tmp/dynagraph-phase6b2b2-final-sanitize`: ASan+UBSan 31/31.
  Sanitizer receipts show detect_leaks=1:halt_on_error=1 and UBSan halt/stacktrace.
  Existing pinned environment/Agg gates passed; no dependency installation.
- AST parsing: 57 Python files. `git diff --check` passed.

All three final profiles report source unchanged and the same inventory SHA-256:
`a09f7fdc1503453418dc7f0fc99157bd7d269f93c1a900e16fc366272964630c`.
All three final tar archives and SHA-256 sidecars passed independent isolated
`python3 -I -S -B` verification using the copied trusted offline kit: debug-full-v1,
release-smoke-v1 and sanitize-full-v1. Draft Debug/Release archives remain clearly
separate from final acceptance; the draft sanitizer timeout archive verifies as
failed-run-v1, never passing. Earlier failed sanitizer classifications remain
unchanged. Large artifacts/raw receipts are ignored in
results/validation/phase6b2b2; final-offline.json and verification-summary.json
retain exact commands and outcomes. Source/test hash receipts match final code;
only this outcome documentation and an AST-identical correction to the journal
test-discovery comment were changed after full validation. The latter corrects
CTest wording to direct Python suite; post-gate-comment.json records both hashes.

Final end-to-end fixture: `python3 -B /tmp/dynagraph-phase6b2b2-demo-final.py`.
It invokes an initial pilot whose parent uses os._exit(89) immediately after the
first completed terminal transition. Subsequent CLI inspect-recovery exits 1
(incomplete original); resume-pilot with both authorizations, inspect-resume and
verify-pilot for the fresh child execution all exit 0. Exactly three marker
launches occur across the original and resume: one original completion reused,
two pending trials executed once. Final demo's 53-file SHA-256 sidecar verifies
independently. The earlier draft demo is retained separately and is not the final
ownership-protocol demonstration.

The original 104-trial expansion remains byte-identical. Plan SHA-256:
`f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24`;
manifest SHA-256:
`f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a`.
The 8,379-entry preservation map and historical 911-entry R3 map have zero
mismatches. Protected production, timing, heuristics, workload/admission/archive
contracts, independent oracle, process-layer R1 checks, dependency pins, CMake and
CI workflows are unchanged. Pilot v2 and journal v1 remain unchanged; new owner,
resume-authorization/event and resume-inspection contracts are separately v1.

Eleven intended files: AGENTS.md; campaign.py; campaign_pilot.py; new
campaign_ownership.py and campaign_resume.py; test_campaign_journal.py; new
test_campaign_resume.py; campaign-pilot.md; campaign-recovery.md;
experimental-protocol.md; this log. No unresolved final validation failures.
Residual limitations: local cooperative flock semantics; trusted producer and
filesystem assumptions (hashes do not authenticate malicious writers); original
path/device/inode required; legacy or relocated evidence cannot resume; any
reservation blocks repeated resume; no proof of orphan ownership for interrupted
or unresolved launches; userspace scheduling/native spawn latency; existing
POSIX link/fsync durability assumptions rather than arbitrary hardware guarantees.
Atomic visibility of a valid linked event remains the existing journal model;
pre-link terminal publication failure leaves an incomplete transaction, while a
read-only inspector cannot infer historical fsync acknowledgements from bytes.

All results remain development-only and measurement-ineligible. Hosted CI is not
claimed from local results. TSan acceptance/race freedom remains unmet with the
historical LIKELY TOOL/RUNTIME LIMITATION classification preserved. Scientific
campaigns/inference, retries, safe repeated resume, unresolved-process recovery,
stronger resource ownership/isolation, CPU placement and tuning remain deferred.
Stop after the authorized local commit/report; no push, merge or PR.

## Phase 6B-2B-3A — runtime observation and evidence contracts (2026-10-31)

Authorized request supersedes the previous phase gate in AGENTS.md. Initial branch
was feature/phase6b2b3-runtime-provenance, HEAD
573982a648c30d7d8cc5521c96d9ae86891ecfdd, with a clean working tree. No delegation,
dependency installation, push, merge or PR. Runtime collection and offline
validation are implemented in campaign_runtime.py, with the optional bounded
process observer in campaign_process.py and pilot/resume integration. New runtime
contract/provenance schemas are separately v1; pilot v2, journal v1, runtime
mapping v3, hardware v2 and resume v1 are preserved. The exact binding and
compatibility rules are in docs/runtime-provenance.md.

The observer records one post-spawn child PID/start identity and executable match,
actual leader affinity, supported visible cgroup2 ancestry and libgomp mapping
identity, namespace-visible online CPUs, OS and kernel. The journal-bound hardware
snapshot retains topology/NUMA context; original build/compiler declarations and
worker output remain separate from current-host observations. Every source has
scope, availability, collection interval and explicit limitations. Unsupported or
missing observations are not successful observations. Malformed supported facts,
conflicting identities, evidence mutation and unsupported schemas reject.
Original/resumed origin is explicit; reused trial evidence is byte-identical.
The resume attempt ID binds new provenance to its authorization event.

Inspection found that actual_threads_ is assigned inside delta-stepping's real
parallel region, while timed metrics are disabled and timing metadata explicitly
reports actual_workers unavailable. The CLI does not export workload-region team
aggregates. No C++ instrumentation was added: team size and region count remain
null, intended_workload_observed=false, and requested/observed comparison is
unavailable. No test parallel region, linkage or environment request is treated as
worker execution. All production source/headers/apps, CMake, pinned dependencies,
workload/configuration files, archive code and CI workflows remain unchanged.

Fresh local checks completed: new runtime suite 11 tests; pilot 47; journal 82;
resume 36 (including original/new provenance preservation); campaign 85; archive
59; diagnostic controls 3; infrastructure repair controls 17. Debug and Release
configure/build and CTest each passed 31/31. ASan+UBSan build and CTest passed
31/31 outside the sandbox, with leak detection and halt-on-error enabled. Release
smoke passed with the existing .venv-analysis interpreter. Gate rejection and
quoted-path/minimal/library/optional-registration compatibility controls passed.
Commands/raw output are retained under ignored
results/validation/phase6b2b3a; infrastructure fixture trees and JUnit reports are
under /tmp/phase6b2b3a-*. Focused Python suites run directly, preserving the pinned
CTest registrations. These are local results, not hosted-CI results.

Initial drafts exposed sandbox-blocked Unix sockets and LeakSanitizer's ptrace
restriction; final runs outside the sandbox passed. An initial smoke invocation
with system Python rejected missing pinned matplotlib; the existing analysis
environment passed, without installing anything. An exit-race probe found Linux
EINVAL for terminating-process mountinfo; this now records source unavailability.
The observation interval ends after all source reads. Early draft logs are kept
separate from final successful logs, rather than overwritten as passing evidence.

A retained one-trial development-only demo runs the compiled Release binary and
passes offline verify-pilot. It is a newly derived fixture, not an execution of
the original scientific/development manifest. The original 104-trial plan remains
f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24;
manifest remains
f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a.
The pre-edit 9,654-file historical evidence snapshot has zero SHA-256 mismatches.
Original evidence and the R1 deadline ordering remain unchanged.

Residual limitations: snapshots are non-atomic, unauthenticated and may perturb
scheduling; fast exits/interpreters can leave child observations unavailable;
Linux/libgomp/cgroup2 support is limited; hidden restrictions, worker affinity,
contention and physical-core exclusivity are unverified. No scientific eligibility
follows from environment variables, affinity, library mappings or correctness.
Observed teams would not establish exclusive physical cores. GitHub Actions and
this Codespace do not establish credible exclusive-core multicore scaling.
measurement_eligible remains false everywhere. TSan acceptance remains unmet with
the historical LIKELY TOOL/RUNTIME LIMITATION classification preserved.

Phase 6B-2B-3B workload-region instrumentation, stronger runtime/process/resource
ownership, repeated recovery and isolation remain deferred. Scientific campaigns,
inference, performance claims, tuning and automatic admission require later
explicit authorization. Stop after the authorized local commit and report.

The first portable Release evidence run passed its 31 CTests and smoke stages but
correctly rejected a concurrent research-log edit at the final source inventory
gate; no passing archive was produced or claimed from that draft. A later exit
probe also exposed disappearing cgroup mount evidence; this supported missing
source is now explicitly unavailable, while malformed supported policies still
reject. Final portable evidence is generated only with a stable source tree.

Final stable-source portable gate passed:
`.venv-analysis/bin/python -B tools/validation/ci_verify.py --python
.venv-analysis/bin/python --mode release --smoke --output
/tmp/phase6b2b3a-release-final`. It passed all 31 CTests, the real smoke pipeline,
negative smoke controls and final source-inventory equality, then created and
reopened a release-smoke-v1 archive. The standalone evidence_archive.py verifier
with its SHA-256 sidecar reports passed/verified. A separate standard-library
verifier independently checks the sidecar and all 689 archive members against
the archive manifest, and all 19 retained demo pilot inventory entries. Archive,
sidecar, independent verifier/results and fresh logs are retained in ignored
results/validation/phase6b2b3a. Final stable runtime/pilot/journal/resume runs pass
11/47/82/36 tests respectively. Historical preservation remains 9,654 files with
zero mismatches; original plan/manifest hashes are unchanged. This final outcome
entry is documentation-only and postdates the archive's source snapshot; runtime
implementation and tests match the verified snapshot. No hosted-CI or scientific
admission claim follows. Eleven intended files comprise AGENTS.md, four campaign
Python modules, two test files and four documentation files. No unresolved local
acceptance failure remains; residual limitations and deferred 6B-2B-3B work remain
as stated above and in the runbook.

### Interrupted-session recovery and final review (2026-10-31)

Resumed on the requested branch at 573982a648c30d7d8cc5521c96d9ae86891ecfdd
with all eleven implementation files already staged. Read AGENTS.md and reviewed
every staged file; preserved the existing implementation and retained evidence.
The collector, process observer, pilot artifacts/verification, resume origin
binding, tests and runbook were already implemented. No unfinished code or
integration gap was found in safe-resume authorization, journal terminal binding,
deadline propagation, bounded cleanup or measurement eligibility.

One offline-validation defect was corrected: a supplied snapshot could assert an
executable match for a process whose retained stat already said zombie/dead,
although collection clears such child observations. The verifier now rejects
that contradiction. A new independent test covers Z/X/x and confirms that exited
identity evidence remains valid with child facts explicitly unavailable. This is
a verification-only tightening; no process execution, timing or algorithm changed.

Fresh commands and outcomes are retained in ignored
`results/validation/phase6b2b3a-resumed` (earlier logs were not overwritten):

- `python3 -B tests/test_campaign_runtime.py`: final 12/12.
- `python3 -B tests/test_campaign_resume.py`: final 36/36;
  `tests/test_campaign_journal.py`: 82/82; `tests/test_campaign_pilot.py`: 47/47.
  Initial sandbox runs failed only while creating Unix-socket fixtures; fresh
  outside-sandbox runs passed, including final runs after the verifier fix.
- `python3 -B tests/test_campaign.py`: 85/85;
  `python3 -B tools/validation/test_archive.py`: 59/59;
  `python3 -B tools/validation/test_negative_diagnostics.py`: 3/3;
  `python3 -B tools/validation/test_repair.py --output
  /tmp/phase6b2b3a-resumed-repair`: 17/17.
- Fresh `ci_verify.py --python /workspaces/Dynagraph-HPC/.venv-analysis/bin/python
  --mode debug --output /tmp/phase6b2b3a-resumed-debug`: 31/31, source unchanged.
  The corresponding Release driver with `--mode release --smoke --output
  /tmp/phase6b2b3a-resumed-release` passed 31/31, smoke, negative controls and
  source equality. These driver snapshots precede the final verifier tightening.
- After the tightening, `ctest --test-dir
  /tmp/phase6b2b3a-resumed-debug/build --output-on-failure` and the corresponding
  Release build each passed 31/31 again. Production/build files are unchanged.
- The fresh sanitize driver built successfully, but sandbox CTest encountered
  LeakSanitizer's explicit ptrace restriction. Final outside-sandbox command:
  `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1
  UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir
  /tmp/phase6b2b3a-resumed-sanitize/build --output-on-failure`: 31/31 passed.
  The failed sandbox driver remains failed evidence, not a passing profile.
- All 61 tracked Python files parsed with `ast.parse`; staged and working-tree
  `git diff --check` passed. Final implementation/test hashes are retained in
  `final-source-sha256.json` beside the fresh logs.

Reverified the retained runtime Release archive with `evidence_archive.py
--verify ... --sidecar ...`; profile release-smoke-v1 passed. The retained
independent standard-library checker also passed all 689 archive members and
19 demo inventory entries. This historical archive predates the final verifier
fix and this log entry; it is not claimed as a final-source archive. Final-source
offline `campaign.py verify-pilot` passed both the runtime demo and the legacy
Phase 6B-2B-2 resumed pilot. Read-only legacy recovery inspection still reports
the expected incomplete original with one verified completion and two pending
trials (exit 1), without inventing completion or executing archived runners.

Rehashed the historical 9,654-file preservation map: zero mismatches. Regenerated
all 104 trials and compared the canonical manifest bytes directly to the retained
original: identical. Plan SHA-256 remains
f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24;
manifest SHA-256 remains
f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a.
No production source/header/app, CMake, configuration, archive infrastructure or
CI workflow differs from the base. Eleven intended files remain in this commit.

No unresolved final local test failure remains. All snapshot, platform, ownership,
scientific-admission and TSan limitations above still apply. Actual OpenMP teams
and workload-region counts remain unavailable; scientific eligibility remains
false. Phase 6B-2B-3B and all scientific execution/inference, retries, resource
isolation and tuning remain deferred. Stop after the authorized local commit;
no hosted-CI claim, dependency installation, push, PR or merge.
