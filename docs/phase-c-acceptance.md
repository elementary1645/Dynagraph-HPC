# Phase C — final system integration acceptance

**APPROVED for local Codespaces system integration validation.** Scientific
eligibility remains false and TSan acceptance remains unmet. This verdict covers
software integration and bounded development evidence, not scientific performance
acceptance or an absence-of-races guarantee.

## Baseline and scope

On 2026-11-07, `feature/phase-c-final-integration`, local `main`, and the read-only
`git ls-remote origin refs/heads/main` check all identified
`7abb9004aaf3b1a784719cbcff5033da838ccb03`. The initial working tree was clean.
This merge contains approved [Phase A](phase-a-acceptance.md) and
[Phase B](phase-b-acceptance.md); the latter merges resource evidence commit
`79f8c6e44f177af728b3e0239574f7ca7df7d7e2` onto `be3588a`.
The explicit Phase C request supersedes the earlier Phase B authorization boundary.
No dependencies, scientific inputs, production implementation, APIs, heuristics,
workload formats, timing boundaries or CI workflows were changed.

The architecture review followed CSR storage, Dijkstra, persistent-team delta
stepping, transactional single-decrease repair, adaptive selection, benchmark
replay/timing, enforcement, workload/resource binding, offline verification and
journal/resume. Existing algorithm and adversarial suites already cover the
requested fixtures; no missing implementation or demonstrated software integration
defect required a fix or duplicate regression test. Fresh profiles establish the
merged baseline, additive diagnostics exercise the Phase A/B integration, and a
retained lifecycle demonstration provides reviewable resume/failure artifacts.

## Evidence and acceptance matrix

New raw evidence is retained, ignored by Git, under
`results/validation/phase-c-final-integration/` (`E`). The complete driver scripts,
exact argv, environments, timestamps, exit statuses and log digests are retained.
Canonical profiles each captured the same clean source inventory at `7abb900`;
`E/postcheck/source-equality.json` records equality. Final changes are acceptance
and authorization documentation only, written after validation. Tests qualify the
unchanged implementation at the baseline, not a future documentation commit hash.
These are local results; no hosted CI result is claimed.

| Requirement | Current evidence | Result |
| --- | --- | --- |
| Debug full canonical profile | `E/debug/acceptance.json`, execution.xml, debug.tar.gz + sidecar | 31/31 PASS |
| Release full profile and smoke | `E/release/acceptance.json`, execution.xml, release.tar.gz + sidecar | 31/31 PASS |
| ASan + UBSan + LeakSanitizer | `E/sanitize-approved/acceptance.json`, execution.xml, archive + sidecar | 31/31 PASS; detect_leaks=1 |
| Additive workload/resource integration | `E/supplemental-approved/{debug,release,sanitize}-diagnostics.xml`; strict acceptances in postcheck | 2/2 CTests per build PASS; 14 workload + 11 resource test methods per build |
| Full campaign regressions | `E/supplemental-approved/campaign-python.log` | 382/382 PASS; no skips |
| Exact additive registration | `E/supplemental-approved/*-optional-registration.log` | Exactly 33 in every build PASS |
| Rendering and Release smoke | `E/release/pipeline/pipeline-result.json` | 32 trials, 14 figures; valid_harness_only |
| Smoke negatives | `E/release/pipeline-negative/negative-results.json` | 9/9 intended rejections PASS |
| Environment/registration negatives | `E/supplemental-approved/test_gate/negative-results.json` | 6/6 intended rejections PASS; missing/extra/duplicate checker controls PASS |
| Compatibility | `E/supplemental-approved/test_compatibility/outcomes.json` | Full 31, minimal 27, library-only 0, optional 37 PASS; full-without-tests rejected |
| Archive regressions | `E/supplemental-approved/test_archive.log` | 59/59 PASS |
| Repair and negative diagnostic regressions | `E/supplemental-approved/{test_repair,test_negative_diagnostics}.log` | 17/17 and 3/3 PASS |
| Standalone offline archive transfer verification | `E/offline-verification.json`, `E/postcheck/offline-archives.log`, copied trusted kit | Three full profiles PASS; SHA-256 sidecars and complete member inventories |
| Retained end-to-end recovery demonstration | `E/lifecycle/summary.json`, original/child trees, postcheck/lifecycle.log | Immutable completed reuse, pending-only launch, renewed resource opt-in, duplicate rejection PASS |
| Failed publication / post-GO interruption | `E/lifecycle/{fail,interrupt}/`; campaign regression log | Failed, never verified-complete; resume rejected PASS |
| Original scientific plan and manifest | `E/supplemental-approved/manifest-preservation.json` | 104 trials; both exact hashes unchanged |

## Correctness and concurrency coverage

`dijkstra` and `delta_stepping` validate empty-graph source rejection, single
vertices, isolated/disconnected vertices, self-loops, zero cycles, equal-distance
paths, sparse/dense seeded fixtures, UINT32_MAX edges, distances above uint32,
bucket boundaries and high-weight distance arithmetic. The delta tests cover six deltas
from 1 through UINT64_MAX, requested workers 1/2/4 and runtime-default requests,
metrics on/off and graph immutability. Finite fixtures cannot exhaust every graph
or runtime configuration. Storage rejects weights outside its supported uint32
range. These bounded fixtures do not create a uint64-distance overflow: a simple
path with at most V−1 uint32 weights fits below the uint64 infinity sentinel.
No unbounded-size overflow experiment is claimed.

`incremental_sssp`, `incremental_failure`, `adaptive_sssp`, `adaptive_failure`,
`system_correctness` and `system_adversarial` compare repeated supported decreases
and no-effect updates across fixed policies, heuristic and forced overrides.
The independent synchronous Bellman–Ford oracle reads input edge records rather
than production CSR or SSSP results. Shared-trace fast validation checks 48 seeded
cases, 1,632 checkpoints and 13,056 complete state comparisons; adversarial tests
cover 14 fixtures. Transactional injection verifies rollback and subsequent reuse.
Empty graphs have no valid source; acceptance requires rejection, not a fabricated
empty shortest-path result. Weight increases are supported by storage/full
recomputation only; incremental increases remain deferred.

`parallel_concurrency`, `concurrency_runtime`, `parallel_failure_fast` and delta
failure tests check atomic competing relaxations, same-bucket closure, stale work,
256-edge partition boundaries, synchronization, dynamic reductions, nested and
serialized teams, independent clients and externally serialized shared engines.
Workload diagnostics add nine native modes including a nonleader std::thread
caller and max-active-levels lowered inside an active region. Requested and
observed teams are checked separately. Timeouts and repeated result comparisons
provide bounded deadlock/scheduling-variation coverage, not a universal proof of
deadlock freedom. Sanitizers pass without establishing race freedom.

## Evidence binding and recovery

Real diagnostic attempts bind graph/trace and algorithm configuration to execution,
trial, attempt, executable, command, generation, enforcement receipt, observed
OpenMP workload, resource observations, oracle and journal. Offline verification
and recovery share semantic validation. Tests mutate identities, native/bound
classifications, workloads, configuration, process generations, receipts and
resource policy; they also remove/truncate records and substitute cross-trial
artifacts. Rehashed attacks rebuild applicable inventories and journal chains,
so digest consistency alone cannot authorize completion. Missing, contradictory,
stale or unknown-GO evidence fails closed.

The retained demonstration intentionally stops the coordinator between trials.
Inspection reports one verified-complete and one pending. Missing renewed
resource authorization is rejected. Authorized resume creates a child attempt
with dispositions `reused,new`, checks every original file hash unchanged, and
rejects a second resume. Separate publication-error and real-child post-GO
KeyboardInterrupt controls remain failed and cannot resume. Fault injection is
explicit test control, not an accidental interruption or original observation.
Full campaign regressions additionally exercise signals, process cleanup,
descendant pipes, deadlines, ownership, partial/reordered/duplicate journals,
missing receipts, stale metadata and unresolved launches. No failed benchmark
attempt was retried as part of resume.

Diagnostic completion requires adequate evidence; it does not require an
`observed_stable` classification and never grants timing/scientific eligibility.
Native resource artifacts remain raw observations. Synthetic stability and
counter/identity mutations are adversarial controls, not measurements or proof of
exclusive ownership.

## Commands, environment and reproducibility

Exact historical argv and results are in `E/**/commands.json`. Top-level drivers:

```sh
.venv-analysis/bin/python -B /tmp/dynagraph-phase-c-validation.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-c-approved.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-c-postcheck.py
```

The first driver completed Release and preserved an unsuccessful sandbox sanitizer
run. The approved driver ran a fresh sanitizer profile and all supplemental tests.
The postcheck ran the standalone verifier, retained lifecycle demonstration and
strict diagnostic JUnit/source equality checks. Copies of all drivers and the
independent verifier script are in E. They use the original `/tmp` paths and fresh
output directories; choose new paths for a new run, never overwrite retained data.

Canonical profile commands for new disjoint outputs:

```sh
.venv-analysis/bin/python -B tools/validation/ci_verify.py --python "$PWD/.venv-analysis/bin/python" --mode debug --output /tmp/dynagraph-phase-c-new/debug
.venv-analysis/bin/python -B tools/validation/ci_verify.py --python "$PWD/.venv-analysis/bin/python" --mode release --smoke --output /tmp/dynagraph-phase-c-new/release
.venv-analysis/bin/python -B tools/validation/ci_verify.py --python "$PWD/.venv-analysis/bin/python" --mode sanitize --output /tmp/dynagraph-phase-c-new/sanitize
```

Supplemental commands configure each canonical build with
`-DDYNAGRAPH_ENABLE_WORKLOAD_DIAGNOSTICS=ON` and
`-DDYNAGRAPH_ENABLE_RESOURCE_DIAGNOSTICS=ON`, check exact registration, and execute
only `workload_instrumentation|resource_interference`. The full campaign command is
`python -B -m unittest discover -s tests -p 'test_campaign*.py' -v`, with
`DYNAGRAPH_PILOT_TEST_RUNNER` and `DYNAGRAPH_WORKLOAD_TEST_FIXTURE` selecting fresh
Release binaries. Drivers record these paths, diagnostic retention destinations,
sanitizer controls and test-gate/archive/compatibility commands exactly.

Python 3.14.2 passes the existing eleven exact dependency pins and real Agg render.
No package was installed. All canonical builds use warnings as errors. Sanitizer
flags remain `-fsanitize=address,undefined -fno-omit-frame-pointer`, linker
`-fsanitize=address,undefined`, `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1`, and
`UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`.

The sandbox denied a Unix-domain socket probe and prevented LeakSanitizer thread
inspection, producing its explicit ptrace limitation diagnostic. That sanitizer
run is retained as failed in `E/sanitize/` and `E/sanitize.failed.tar.gz`; it is
not counted as passing. Approved execution supports sockets and the full fresh
sanitizer profile passes with no requirement disabled. Sandbox DNS also blocked
the initial remote-main query; the approved read-only query succeeded. These
execution restrictions required no source fix or benchmark retry.

A copied trusted verifier kit runs under system Python `-I -S -B`. Its audit hook
denies checkout/venv reads, network and subprocess creation. All three transferred
archive/sidecar pairs pass profile and complete inventory validation there.
`E/audit-sha256.json` inventories retained bytes; build trees, transient caches and
configure/repair fixture copies are excluded from retention. Original working build paths
remain under `/tmp/dynagraph-phase-c-20261107` for this session. Historical Phase 5,
Phase A and Phase B evidence directories were not modified or regenerated.

Plan SHA-256:
`f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24`.
Manifest SHA-256:
`f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a`.
No scientific golden was changed.

## Remaining limitations and phase boundary

No mandatory local Phase C integration gate remains blocked. The independent
race-detector acceptance gate remains unmet: the earlier work_ report is
LIKELY TOOL/RUNTIME LIMITATION, not race freedom. Scientific eligibility remains
false. Codespaces provides no evidence of exclusive physical cores, stable CPU
isolation, absence of contention, physical-core scaling or publishable multicore
speedup. Bounded snapshots cannot detect all between-sample changes or hidden
ancestors, and hashes do not authenticate an entirely fabricated producer.
Concurrent mutation, incremental increases, topology changes, tuning, inference,
scientific campaigns and later phases remain deferred.

Changed files: `AGENTS.md`, `docs/phase-c-acceptance.md`, `docs/research-log.md`.
A local documentation commit records this acceptance. No push, PR or merge was
performed. Stop after the Phase C report. Any later phase requires a new request;
none is started or implicitly approved here.
