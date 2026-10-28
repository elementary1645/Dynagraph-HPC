# Research log

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
