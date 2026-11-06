# Phase A — workload-instrumentation acceptance audit

**Overall result: BLOCKED. Phase A is not accepted; Phases B–G have not started.**

This 2026-11-06 self-audit starts at
`f83ebd4966e9a48a5024114c110731c78834d026` and reviews the reconstruction against
`71d731f877ce41cb110ca7617655be92e6222c76`. There was no separate reviewer and
no hosted-CI result. All execution used the same GitHub Codespaces environment,
including the isolated local checkout. No dependencies were installed, no research
evidence was deleted, and nothing was pushed, merged or submitted as a PR.

## Audited architecture and completion boundary

The existing C++17 library separates fixed-topology CSR storage, reference
Dijkstra, OpenMP delta-stepping, transactional single-decrease incremental repair,
and the deterministic adaptive engine. Call-owned delta query state uses the
existing persistent OpenMP team; optional observation slots are separate from the
algorithm's work state. Graph updates occur between completed queries, and shared
adaptive-engine access still requires external serialization. Existing regression
and failure-injection suites check these components; they were not rebuilt as new
implementations or tuned in this audit.

Python keeps deterministic workload generation, staging/independent oracles,
resource admission/enforcement, process capture, provenance, pilot records and
journal/resume separate. The acknowledgement/GO barrier binds a workload process
before execution. Workload samples are bound after diagnostic exit, and one shared
semantic gate controls offline verification and completed reuse. Descriptive
analysis already exists; renderer validation is unavailable and no new scientifically
eligible performance data was established. Interference/stability observations,
subsequent campaign/analysis phases and whole-project final acceptance remain
blocked by the Phase A boundary. There is no claim of unconditional completion.

## Reproduced defect and fix

A mixed record could contain both an explicit contradiction and a missing task
field. The old classifier returned `insufficient_evidence` whenever *any* sample
was incomplete, even when the original validation error identified a forged leader
generation, foreign TGID or out-of-affinity CPU. A red test reproduced **12 failing
subcases in one test**. This was a classification defect; it did **not** demonstrate
acceptance of a successful/completed trial containing those contradictions.

The fix validates every available task fact and defers the missing-evidence verdict
until the known facts have passed. Known contradictions, including those in other
threads or later regions, therefore take precedence. Missing evidence alone remains
insufficient, and neither classification authorizes completion. Endpoint identity,
duplicate TIDs, generation, OpenMP and CPU restrictions remain enforced. No unknown
identity value is invented to fill a missing field. Native v2/bound v1 schema shapes
and valid completed evidence remain compatible; old malformed/contradictory bound
records are not rewritten to fit the corrected classification.

Additional adversarial tests retain a false `observed_consistent` claim while
independently recomputing native and bound hashes, record inventories, terminal
record references and the journal chain. They cover F1, F2, F3 and missing
membership. Verification rejects them both with a published final inventory and
through recovery's per-trial path without that inventory. This avoids relying on
the verifier under test to label an attack contradictory before testing it.

Changes are confined to `campaign_workload.py`, focused test coverage, test runner
selection for isolated builds, and documentation/scope instructions. C++ algorithms,
native sampling, timing boundaries, CMake, dependency pins, enforcement/cleanup,
resource admission, journal schemas and deterministic campaign inputs are unchanged.

## Acceptance matrix

Evidence references below are relative to
`results/validation/phase-a-acceptance-audit/` unless otherwise stated. Statuses
mean PASS = verified, FAIL = demonstrated unresolved defect, BLOCKED = unavailable
required validation, NOT APPLICABLE = not justified/applicable in this audit.
The original classification FAIL is retained in `classification-red.log`; the
corrected result is PASS. No unresolved software FAIL was demonstrated by these checks.

| Requirement | Verification method | Result | Supporting evidence | Remaining limitation |
| --- | --- | --- | --- | --- |
| F1: leader task generation | Native samples reconciled to parent-bound process generation; forged single/both samples, false consistency claims, rehashed offline/recovery attacks | PASS | `isolated-verification/campaign-python.log`, `classification-green.log`, native samples | Local consistency, not authenticated producer evidence |
| F2: worker membership | Pid/TID, TGID, group/session, generation, duplicate and partial-evidence tests | PASS | Same focused suite and rehashed attacks | Cannot authenticate a wholesale self-consistent fabrication |
| F3: OpenMP nesting | Team/ancestor/level/active/max-active checks; native active, serialized and lowered-max-to-zero fixtures | PASS | `isolated-verification/native-{debug,release,sanitize}/`, focused tests | Bounded development fixtures, not scaling evidence |
| F4: nonleader primary | Joined std::thread invokes the actual delta workload; primary TID differs from bound PID | PASS | Native fixtures and `../phase-a-real-execution/joined/` | No assumption of a dedicated physical core |
| Known contradiction precedence | Red/green tests combine missing fields with forged identities/CPU placement, across endpoints/threads/regions | PASS | `classification-red.log`, `classification-green.log`, 14-test focused suite | Corrected failure labels can differ for old invalid records; no rewriting |
| Actual workload sampling | Source diff review; actual persistent-region entry/exit and per-participant slots | PASS | Baseline diff; retained nine-mode native fixtures | Sampled placement does not prove stable placement |
| Semantic verification beyond hashes | Independently rehashed false consistency claims; full-index and direct per-trial recovery rejection | PASS | New focused adversarial test in the 371-test campaign run | Digests do not provide external authentication |
| Native real-control pilot | Unmocked visible cgroup/affinity enforcement, one- and two-worker diagnostic trials, compiled and Python correctness oracles, offline/recovery checks | PASS | `../phase-a-real-execution/summary.json`, `pilot/`, `offline.json`, `recovery.json` | Visible controls and local consistency only; no interference/ownership conclusion |
| Timing/publication rejection | C++ timing API test; real CLI rejects diagnostic timing and publication over an existing immutable file | PASS | `../phase-a-real-execution/negative/`, CTest benchmark_timing | Diagnostic runs remain measurement-ineligible |
| Pilot/recovery/resume safety | Shared semantic gate; unknown GO, native/receipt downgrade, renewed authorization, immutable reuse, pending-only execution and no retries | PASS | `isolated-verification/campaign-python.log`, 14 focused tests | Abrupt death/external reaping/escaped descendants retain documented limits |
| Fresh Debug build and available CTest | Clean local base plus identified overlay; warnings-as-errors; sequential CTest and JUnit checks | PASS | `isolated-verification/debug-{configure,build,ctest}.log`, `debug-execution.xml` | 31/31 available tests; full renderer registration is blocked |
| Fresh Release build and available CTest | Same fresh procedure and explicit test names | PASS | Release logs/JUnit | 31/31 available tests; not a full-validation profile |
| ASan+UBSan+LeakSanitizer | Fresh instrumented build; leak detection and halt-on-error enabled; process inspection permitted | PASS | Sanitizer logs/JUnit | 31/31 available tests; no TSan/race-freedom implication |
| Campaign Python regressions | All campaign suites use explicitly selected freshly built Release binaries | PASS | `isolated-verification/campaign-python.log`, `campaign-runners.json` | 371 executed tests; fixture cgroups are synthetic except the separate real-control execution |
| Archive/repair infrastructure | Existing documented standalone entry points | PASS | Archive 59/59, repair 17/17, negative diagnostics 3/3 logs | Synthetic contract tests do not substitute for historical archives |
| Deterministic inputs | Raw configuration comparison to baseline; canonical plan and 104-trial manifest expansion/digests | PASS | `manifest-preservation.json` | This is deterministic regeneration/comparison, not reopening a missing historical manifest file |
| Available retained Phase 6 evidence | Independent raw SHA-256 checks of five old inventories; archived source compared to f83ebd4 Git objects | PASS | `retained-evidence-verification.json` | 371 artifact checks and 168 source checks, zero mismatches; not Phase 5 archive validation |
| Full pinned analysis environment | Actual environment checks using Python 3.14.2 and system 3.12.3 | BLOCKED | `dependency-inventory.json`, environment logs | Exact pins unavailable; no installation authorized |
| Full registration and renderer smoke | Actual full CMake configure, official registration checker and full smoke entry point | BLOCKED | `blocked-gates.json`, `full-registration.stderr`, `full-smoke-environment.log` | Expected 32 tests with diagnostic tier; analysis_figures missing. Existing full gates still reject |
| Historical Phase 5 inventories/archive sidecars | Bounded local search and tracked-file inspection | BLOCKED | `historical-evidence-search.json` | No preserved candidates found in the searched locations; history cannot be regenerated as original evidence |
| TSan acceptance/race-freedom claim | Preserve prior calibrated gate outcome and intentional-race-control isolation | BLOCKED | Existing research log and tests/tsan_controls | Prior work_ report remains LIKELY TOOL/RUNTIME LIMITATION; ASan is not a race detector |
| Performance inference/physical-core speedup | No scientifically eligible observations established by this audit | NOT APPLICABLE | All pilot and bound evidence retains false scientific flags | No confidence intervals, significance or scaling claim is justified |
| Phase B and later phase acceptance | Enforce the master request's dependency order | BLOCKED | This report and AGENTS.md | Phase A remains unaccepted; no interference implementation/campaign is presented as completed |

## Native observations and real execution

Each build runs nine modes: one worker, two workers, dynamic team reduction,
three repeated regions, active nesting, serialized nesting, serialization after
lowering max active levels to zero inside an already active outer team, joined
std::thread caller, and serial Dijkstra. The last produces no fabricated delta
region. Each direct delta result matches Dijkstra. The genuine two-trial pilot
also executes the compiled per-update Dijkstra/Bellman–Ford checks and independent
Python final-state Bellman–Ford. Its two trials reach `verified-complete` with
measurement eligibility false. Real-control joined-caller evidence independently
exercises the bound process/TGID distinction. Two real CLI negative controls reject
instrumented timing and preexisting diagnostic publication.

The CTest fixtures deliberately use synthetic cgroup visibility with real Linux
affinity/TID/generation/CPU samples. The separate `phase-a-real-execution` run uses
**no cgroup/hardware mocks**. It records only the controls visible to this Codespaces
namespace. Neither source of evidence establishes uncontended execution, stable
CPU availability, exclusive ownership, NUMA isolation or physical-core independence.
The proposed Phase B before/during/after interference assessment is still absent.

## Reproducibility and evidence retention

The fresh audit driver uses the existing Runner, snapshot, registration and JUnit
checkers. It clones locally without network/hardlinks, verifies a clean f83ebd4 base,
applies an explicit captured working-tree overlay, hashes the frozen source, and
builds/tests Debug, Release and sanitizer configurations sequentially. It records
commands, environments, timestamps, return codes and log digests. The frozen
checkout inventory remains unchanged. Final explanatory documents are written
after results; implementation/test content is compared against the frozen snapshot.
This is a clean-base-plus-overlay audit, not a claim that the final audit commit
was already built under its future commit hash.

Raw top-level command logs, receipts, source inventory/patch, JUnit reports and
native fixture evidence are retained in `isolated-verification/`. The original
working directories/builds and live negative special-file fixtures remain under
`/tmp/dynagraph-phase-a-audit-20261106`; those build products/special fixtures are
not copied into a purported portable archive. The two audit driver scripts are
retained for inspection. These audit catalogues are not a successful historical
`debug-full-v1`, `release-smoke-v1` or `sanitize-full-v1` archive/profile.

To reproduce available checks from this commit in Codespaces, choose new build
paths. Explicit OFF below reports available tests only and does not bypass or
satisfy the mandatory full gate:

```sh
cmake -S . -B build/phase-a-debug -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON -DDYNAGRAPH_ENABLE_WORKLOAD_DIAGNOSTICS=ON -DDYNAGRAPH_FULL_VALIDATION=OFF
cmake --build build/phase-a-debug --parallel 2
ctest --test-dir build/phase-a-debug --parallel 1 --output-on-failure
cmake -S . -B build/phase-a-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON -DDYNAGRAPH_ENABLE_WORKLOAD_DIAGNOSTICS=ON -DDYNAGRAPH_FULL_VALIDATION=OFF
cmake --build build/phase-a-release --parallel 2
ctest --test-dir build/phase-a-release --parallel 1 --output-on-failure
DYNAGRAPH_PILOT_TEST_RUNNER="$PWD/build/phase-a-release/dynagraph_bench" DYNAGRAPH_WORKLOAD_TEST_FIXTURE="$PWD/build/phase-a-release/tests/workload_fixture" python3 -B -m unittest discover -s tests -p 'test_campaign*.py'
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-phase-a-repair-new
python3 -B tools/validation/test_negative_diagnostics.py
```

For sanitizer reproduction, use a fresh build with
`-DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer -fno-pie'`
and `-DCMAKE_EXE_LINKER_FLAGS='-fsanitize=address,undefined -no-pie'`.
Run CTest with `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1` and
`UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`, through the approved mechanism
that permits LeakSanitizer inspection and existing Unix-socket negative fixtures.
No sanitizer requirement was disabled.

The immutable reference plan remains byte-identical to baseline. Its canonical
SHA-256 is `f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24`;
the deterministic 104-trial manifest SHA-256 is
`f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a`.
Only disposable development copies substitute the current executable digest and
observed CPU request for genuine diagnostic execution.

## Blocking prerequisites and next action

The exact eleven-package rendering requirements remain unchanged. The ambient
Python 3.14.2 environment matches only one pin; system Python 3.12.3 matches none.
Both fail the actual gate on missing matplotlib==3.10.8. The former has venv and
ensurepip available; the latter lacks ensurepip. The repository's existing
reproducibility runbook describes an ignored `.venv-analysis` environment, but
AGENTS.md requires explicit dependency-install permission. No installation was
attempted. Full configuration, analysis_figures, renderer smoke and corresponding
figure controls remain blocked until that prerequisite is restored and validated.

The searched local `/tmp`, `/workspaces` and `/home/codespace` trees (depth six)
contain no preserved historical archive/sidecar candidates; `results/validation`
has no Phase 5 retention directory. This bounded search does not establish that
copies do not exist elsewhere. Supply the retained location/files if available;
new synthetic fixtures or regenerated outputs cannot establish historical integrity.
Available Phase 6 retention has been independently checked without mutation.

Next: obtain authorization to restore the existing pinned analysis environment
**inside Codespaces**, locate/restore the original historical evidence, and rerun
the blocked gates. Phase B must wait. Scientific eligibility remains false, TSan
acceptance remains unmet, and no unconditional project completion is declared.
