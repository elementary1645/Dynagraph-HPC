# Phase 5C-1 correctness and failure resilience

Phase 5C-1 adds test-only validation on baseline `45e850f`. It changes no
production algorithms, public API, graph semantics, heuristic, workload format,
benchmark record or timing boundary. The existing test harness remains active
under `NDEBUG`. No new framework, package installation or CI dependency is needed.

## Shared-trace architecture

`tests/system_validation_support.hpp` defines `system-validation-v1` and an
external canonical endpoint/weight ledger. `test_system_correctness` constructs
one graph/trace per case and replays the same requests from sources 0 and V−1
through standalone incremental state and five engines: the three fixed policies,
heuristic, and rotating public forced overrides. At initialization and every
update, fresh standalone Dijkstra and delta-stepping also run on a reconstruction
from the ledger. There are eight complete state comparisons per checkpoint.

Synchronous Bellman–Ford reads original `InputEdge` records via
`tests/sssp_test_support.hpp`; it calls no production SSSP routine and traverses
no production CSR. Each pass reads the previous labels and writes a separate
vector. The new oracle adapter bounds V to 4096 and E to 65536: paths considered
in V−1 passes fit far below uint64 infinity even at maximum uint32 weights.
Authoritative offsets/destinations/weights are derived directly from canonical
records independently of the production builder. Fresh CSR reconstruction is a
system under test, not the source of expected labels or expected graph arrays.

Every update checks complete vectors, infinity, all graph arrays, old/new weights,
outcome, independently counted improved vertices, nonincreasing labels and
invariant reachability. Initial caller graphs and input records remain unchanged.
Metrics alternate on/off; actual engine selection comes from `DecisionResult`.
Standalone delta records actual team sizes. Actual engine teams are available
only on measured executed delta calls; other observations are unavailable.

## Corpus and generator version

| Profile | Cases | V | E maximum | Sources | Updates/source | Checkpoints | State comparisons |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fast | 48 | 2–24 | 512 | 2 | 16 | 1632 | 13056 |
| stress | 96 | 2–64 | 1024 | 2 | 48 | 9408 | 75264 |
| extended | 384 | 2–128 | 4096 | 2 | 128 | 99072 | 792576 |

Disconnected cases require at least four vertices. Graphs have unique ordered
endpoint pairs; self-loops are legal. Families cycle sparse directed, dense
directed, disconnected with an isolated suffix, layered, hub/fan-in and chain
with chords. Four weight regimes are small positive, zero-heavy, boundary values
{0,1,UINT32_MAX−1,UINT32_MAX}, and full-range uint32. Two repetitions of all
family/weight combinations make up fast; later profiles add repetitions.

Default root seed is `0x5C102026` (1544560678). Case-local mt19937 stream seeds are
`root XOR (0x9E3779B9 * (case+1)) XOR tag`, with uint32 wrap. Stream tags are
0xA341316C (topology), 0xC8013EA4 (weights), 0xAD90777D (trace), and 0x7E95761E
(input permutation). Mapping uses explicit output modulo bounds, and input/subset
permutations use explicit Fisher–Yates. This is deterministic test sampling, not
a claim of unbiased scientific workload sampling. No standard distribution or
`std::shuffle` mapping enters canonical generation.

For each eight-request cycle, positions 0/3/6 are equal requests, position 2
reuses the preceding endpoints, position 4 zeros an eligible edge, and remaining
positions decrease positive edges when available. Repetition can encounter an
already zero edge. Exhausted positive budgets produce documented equal requests,
never weight increases, shorter traces or seed retries. Every graph has an edge.
Both no-effect modes occur in fast. Delta and branch-probe configurations are
fixed by case, and are never applied to benchmarks or used for tuning.

FNV-1a fingerprints encode uint64 values as eight little-endian bytes. Generation
fingerprints cover V/counts/initial records/complete trace; state fingerprints
cover complete independent expected vectors at all checkpoints. They are small
test reproducibility markers, not cryptographic evidence identities. Each actual
policy state must match the oracle before its checkpoint completes.

## Reproduction and diagnostics

```sh
build/debug/tests/test_system_correctness --profile fast --seed 4294967295 --case 31 --source 0 --workers 1
build/release/tests/test_system_correctness --profile stress --seed 1544560678 --case 95 --source 0 --workers 2
build/debug/tests/test_system_adversarial --case 13 --source 0 --workers 2
```

Options are exact, unique option/value pairs: `--profile fast|stress|extended`,
`--seed` canonical uint32, `--case` within the profile, `--source` within the case,
and `--workers` 1..4. Source requires case. Invalid CLI exits 2; failed validation
exits 1; success exits 0. Adversarial fixtures accept fast only, cases 0..13 and
sources within each fixture. A specific adversarial case runs both no-effect modes.

Failures report version/seed/case/source/update, initial records, attempted trace
prefix including old/new weights, policy/selected backend, delta, no-effect mode,
heuristic configuration, requested/available actual workers, first mismatching
vertex, complete expected/actual vectors and a quoted executable reproduction
command. If an API throws before returning, the actual-vector diagnostic is the
pre-call snapshot, explicitly labeled. Setup failures may have unavailable vectors.

`test_system_reproduction.py` executes repeated selected fast/stress/extended cases
with requests 1,2,2,4 under thread limit 2 and compares fingerprints. A fixed
version-1 fast-case fingerprint is pinned. This includes selected boundary cases
from optional profiles, not their full corpora. Generation never depends on
worker execution or consumes random draws during algorithm calls. Correct results
are deterministic; work assignment, CAS retries and timing need not be.

## Adversarial fixtures and coverage

Fourteen fixtures run through all eight comparison paths in both no-effect modes:
28 source traces, 230 updates, 258 checkpoints and 2064 state comparisons.

| Case IDs | Coverage |
| --- | --- |
| 0 | 256-vertex maximum-weight chain, early/middle decreases |
| 1 | Dense zero-weight region including self-loops, positive entry edge |
| 2 | Equal-cost layered alternatives |
| 3/4/5 | Hubs of degree 255/256/257 across delta work-chunk boundaries |
| 6 | Disconnected components, isolates, unreachable decreases and loops |
| 7 | Wide maximum-weight path with cap-rejected cyclic candidates |
| 8 | 64 consecutive strict decreases to one edge |
| 9 | Dominated/equal-cost edges, no-op, unreachable tail, loops, edge into source |
| 10 | Hub/chain generating at least 60 stale Dijkstra entries |
| 11 | Delta−1/delta/delta+1 edges, future stale buckets and zero cycles |
| 12 | Singleton positive/zero loop, cap zero |
| 13 | Automatic incremental/delta transitions by destination degree |

Hand-calculated complete results additionally check the dense-zero, disconnected
and wide-chain fixtures. Existing CSR tests retain permutation/duplicate/invalid
input coverage. Existing individual suites retain all-source random comparisons,
invalid calls, checked adoption, all nine ordered forced-strategy pairs, heuristic
boundaries and concurrency regressions. The new framework complements these tests.

Finite weight decreases cannot activate unreachable vertices. Tiny graphs cannot
realize distances near UINT64_MAX under uint32 weights; arithmetic proof and
actual cap/sentinel boundaries are the appropriate validation. Immutable topology
also fixes E: automatic small-graph Dijkstra cannot transition to nonsmall branches
in one engine. Separate configurations test small/local/parallel/fallback branches;
public overrides exercise arbitrary backend transitions.

## Failure resilience

Existing isolated allocation injectors remain in `test_incremental_failure`,
`test_adaptive_failure` and `test_delta_failure`. No production hooks were added.
The shared 96-vertex history includes an effective decrease 100→90, a weight-only
direct-edge decrease 500→400, an equal request 400→400, and another effective
decrease 90→80. Owning-engine history uses incremental, Dijkstra and delta public
overrides; equality still bypasses. Each injection attempt reconstructs that history.

For standalone repair, every counted allocation of a subsequent 80→0 repair is
faulted, with/without metrics. Adaptive tests do the same for every backend,
forced/automatic selection and metrics on/off. They additionally require first
parallel-region and post-CAS publication failures after history. Independent
Bellman–Ford checks initialization, every history step, rollback, identical retry,
and a different subsequent update. Full graph arrays and strong-guarantee caller
metrics are checked after failure. Tentative writes and post-team allocations are
explicitly counted; intended mandatory stages must trigger.

Standalone delta owns no persistent mutable query state. Its history test first
commits caller graph decreases, faults the query, verifies caller-graph immutability,
retries, then changes another edge and queries again. It asserts no transactional
metric guarantee: valid delta calls may leave partial/reset metrics on failure.
Publication and first-region allocation targets must trigger; higher per-thread
allocation positions are schedule-dependent, with every untriggered position
printed and counted as uncovered. Allocation-size targeting of publication retains
the existing 16-byte Entry/layout assumption; it is not a universal allocator hook.

Process-fatal/runtime/OS failures and exhaustive OpenMP schedules are outside this
coverage. Failure-injection observation buffers are bounded. Diagnostics/oracles
run with injection disabled, avoiding accidental failures in reporting or rollback.

## Benchmark replay integration

The additional Python test replays every prefix (including empty) of a six-update
trace from a reachable and an isolated source through all four policies and both
no-effect modes: 112 public CLI invocations. An independent endpoint dictionary
and synchronous Python-integer Bellman–Ford compare complete final weights and
distances for every prefix. Every invocation also performs existing C++ per-update
verification. Existing nine integration tests and canonical artifacts are preserved.

## CMake, CI and budgets

Default CTest adds `system_correctness`, `system_adversarial`, and
`system_reproduction`, labeled `validation-fast`, with PROCESSORS=2, 120-second
timeouts and OMP_NUM_THREADS=2/OMP_THREAD_LIMIT=2/OMP_DYNAMIC=FALSE. The existing
Debug/Release/ASan+UBSan workflow already executes these; no workflow change is
necessary. Optional analysis renderer registration is unchanged.

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --preset debug
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release
cmake --preset release -DDYNAGRAPH_ENABLE_VALIDATION_STRESS=ON
ctest --test-dir build/release -L validation-stress --output-on-failure
cmake --preset release -DDYNAGRAPH_ENABLE_VALIDATION_STRESS=OFF
```

Stress is opt-in (180-second timeout). Extended is manual opt-in through
`DYNAGRAPH_ENABLE_VALIDATION_EXTENDED=ON` (900-second timeout); neither is registered
by default. The default full-suite target is under two minutes; profile budgets
are validation limits, not performance evidence or permission to skip cases.

Use the existing sanitizer configuration with
`-fsanitize=address,undefined -fno-omit-frame-pointer`, leak detection and
halt-on-error enabled. Keep the same fast corpus. LeakSanitizer may require
outside-sandbox execution. Environmental startup failures are failures/unavailable
coverage, not passes. ASan/UBSan does not establish race freedom; Phase 5C-2 remains
separate. Maximum production sizes and exhaustive schedules remain unverified.

Actual commands, exit codes, pass counts, runtimes, sanitizer environment and
unexecuted configurations are recorded in [research-log.md](research-log.md).
Generated logs/JSON command receipts remain under ignored
`results/validation/phase5c1/`. Stop for independent review after Phase 5C-1.
