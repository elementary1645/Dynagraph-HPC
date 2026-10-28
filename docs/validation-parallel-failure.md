# Phase 5C-2C parallel failure validation

The initial inspection on feature/validation-concurrency found completed 5C-2B
changes and existing delta/adaptive failure tests. Existing coverage included
single coordinator/publication faults, host allocation sweeps, committed mixed
history, authoritative rollback, identical retry and different-backend recovery.
It did not provide repeated 4/20/100 epoch profiles or a deterministic merge target.
Those existing test sources and all 5C-2B scenarios remain intact. The original
5C-2C build registrations omitted four analysis tests through a stale interpreter
cache; the verification repair below restores equivalent full coverage.

The new isolated `test_parallel_failure` reuses the executable-local allocator,
metric sentinel and comparisons from `test_adaptive_failure.cpp` by renaming its
main at inclusion. Only the injector gains a merge mode; existing modes retain
their behavior. No production hook, dependency, API, benchmark or CI change occurs.

Each profile runs 4, 20 or 100 epochs **for each of three stages and each metrics
mode**, through both standalone delta and forced-delta adaptive updates. Each
stage/mode/epoch injects once in standalone and twice in fresh adaptive engines:
72/360/1800 total faulted calls. The second adaptive fault checks a different
update directly after failure, without an intervening identical retry. The first
checks exact graph/distance/metric preservation, identical retry, then a different
update. Complete vectors use the independent record-based Bellman–Ford oracle.
Standalone graph preservation is checked; standalone metric rollback is not an
API promise and is not asserted.

The fixed graph has four vertices and records (0,1,100), (0,3,200), (1,2,32).
The attempted adaptive decrease is (0,1,0), source 0, delta 16, requested team 2.
The first prepare allocates settled-vertex/Work storage; its first allocation targets
coordinator preparation. Only edge (0,1) is eligible in the first light scan:
(0,3) is heavy. The first 16-byte Entry allocation is therefore post-CAS worker
publication. In merge mode it is observed without failing; the next region
allocation is merge's bucket insertion, after the worker completion barrier.
There can be no second scan-buffer growth in this round. This fixture-specific
allocation contract is source-derived and depends on Entry's 16-byte layout;
it is not a general allocator-stage identification API. Mandatory targets must
throw; a missed target fails the test. A healthy measured probe reports actual
team size and requires two workers; failing calls themselves expose no actual-team
metric. No worker identity or coordinator identity is assumed.

Bounded returns after faults exercise collective prepare publication, worker
completion, merge publication and exception exit barriers, followed by fresh
parallel queries. They are evidence for these executions, not a proof of deadlock
freedom or arbitrary schedules. No simultaneous multiple-worker exception,
every bucket/merge allocation, host allocator implementation or runtime-internal
allocation is claimed covered. Existing allocation sweeps remain complementary.
The TSan acceptance gate remains unmet.

The Python harness runs one fresh subprocess per profile with fixed OpenMP
NUM_THREADS=2, THREAD_LIMIT=2, DYNAMIC=FALSE, MAX_ACTIVE_LEVELS=1. Child timeouts
are 30/120/300 seconds; CTest's outer timeout is 330 seconds. Timeout/nonzero exit
or a missing exact completion receipt fails without retries. Flushed BEGIN lines
identify profile/stage/metrics/epoch and fixed query/update parameters; captured
stdout/stderr and the command/environment survive a timeout. The fixture and
recovery updates (0,1,0) then (0,3,0) above fully specify reproduction.

Default CTest registers `parallel_failure_fast`. The existing concurrency stress
and extended options additionally register `parallel_failure_stress` and
`parallel_failure_extended`; no existing test counts or loops are shortened.

```sh
python3 tests/test_parallel_failure_runtime.py build/debug/tests/test_parallel_failure fast
python3 tests/test_parallel_failure_runtime.py build/debug/tests/test_parallel_failure stress
python3 tests/test_parallel_failure_runtime.py build/debug/tests/test_parallel_failure extended
```

Verification receipts and raw output are under ignored
`results/validation/phase5c2c/`; exact outcomes are recorded in research-log.md.
Stop after implementation and verification for review; no commit/push/PR.

## Verification gate repair — 2026-10-28

The original cached `DYNAGRAPH_ANALYSIS_PYTHON` pointed to the missing
`/tmp/dynagraph-analysis-venv/bin/python`. CMake's interpreter probe consequently
skipped analysis_import, analysis_stats, analysis_integration and analysis_figures.
Thus the previously reported 27 tests represented 30 previous default tests minus
four analysis tests plus parallel_failure_fast, rather than equivalent coverage.
The source registration logic was preserved; no tracked CMake change was needed.

With explicit user approval, created ignored project-local `.venv-analysis` using
Python 3.14.2 and installed the exact eleven pins in requirements-analysis.txt.
Every pinned version matched; pip check passed; Matplotlib's Agg backend produced
a headless PNG. System Python 3.12 lacked ensurepip, so the incomplete environment
was recreated using the available Python 3.14 interpreter. The first pip attempt
could not resolve the package host inside the sandbox; the authorized installation
outside the sandbox succeeded without substituting versions or upgrading system
packages. Raw installation failures and successful output are retained.

Debug, Release and sanitizer now use
`/workspaces/Dynagraph-HPC/.venv-analysis/bin/python` for analysis. Each registered
exactly the retained 5C-2B thirty default names plus parallel_failure_fast: **31**.
All four analysis tests were restored. Builds and complete suites ran sequentially,
Debug then Release then sanitizer, with CTest --parallel 1 and no competing builds
or verification jobs. Full results: Debug **31/31**, 47.56 s; Release **31/31**,
42.53 s; ASan+UBSan **31/31**, 81.37 s, all exit 0. Sanitizer ran outside the sandbox
with ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 and
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1. No sanitizer finding or timeout.
Dijkstra passed in 0.96/0.05/3.00 s respectively under its unchanged 10 s timeout.

Historical evidence remains unchanged: the original outside-sandbox sanitizer
suite passed 26/27 with Dijkstra timing out at 10.06 s; the identical-settings
isolated Dijkstra rerun passed at 2.80 s. Neither is relabeled a full pass. The new
complete run resolves the verification gate; it does not establish the old
timeout's root cause or race freedom.

Optional registration checks preserve all three failure profiles and both
concurrency tiers. Fast/stress were checked again; extended execution evidence
from Phase 5C-2C remains applicable to unchanged source (1800 faulted calls), with
no unnecessary extended rerun. Phase 5C-2B source hashes and retained corpus
receipts preserve 288/5760/57600 queries. Default options are restored OFF.
Exact commands, dependency versions, complete registration lists, exit codes,
wall times and raw stdout/stderr are in ignored
`results/validation/phase5c2c-repair/`. Race-detector acceptance remains unmet.
