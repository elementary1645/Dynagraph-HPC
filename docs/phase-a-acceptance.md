# Phase A — workload-instrumentation acceptance audit

**Current result: APPROVED for Phase A local workload-instrumentation acceptance. All mandatory Phase A gates pass, including recovered original published Phase 5 baseline archives. Phases B–G have not started; scientific eligibility remains false and TSan acceptance remains unmet.**

This 2026-11-06 self-audit starts at
`f83ebd4966e9a48a5024114c110731c78834d026` and reviews the reconstruction against
`71d731f877ce41cb110ca7617655be92e6222c76`. There was no separate reviewer and
no hosted-CI result. All execution used the same GitHub Codespaces environment,
including isolated local checkouts. The initial audit installed no dependencies.
Subsequent explicit user permission restored only the existing exact pins inside
`.venv-analysis`; ambient/system package inventories are unchanged. No research
evidence was deleted, and nothing was pushed, merged or submitted as a PR.
The restored full-profile validation tests clean committed source
`a293d1aa141307d22a4bfbd6c220951bf534de77`; this update changes documentation only.

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
analysis already exists; pinned renderer validation now passes. No scientifically
eligible performance data was established. Interference/stability observations,
subsequent campaign/analysis phases and whole-project final acceptance remain
outside this completed Phase A acceptance scope. There is no claim of unconditional project completion.

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

Initial-audit evidence references below are relative to
`results/validation/phase-a-acceptance-audit/` unless otherwise stated.
**R** denotes the new, separate `results/validation/phase-a-pinned-restoration/`
retention directory. Earlier failure logs remain unchanged; they are not current
failures after environment restoration.
**H** denotes `results/validation/phase5-recovered-github-20261106/`, containing
original historical workflow downloads and their verification/provenance records. Statuses
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
| Fresh Debug full gate | Canonical ci_verify.py, full mode, exact default registration and JUnit | PASS | R/full-verification/debug/, debug.tar.gz and sidecar | 31/31, including analysis_figures; local, not hosted CI |
| Fresh Release full gate and complete smoke | Same canonical profile plus real pipeline and intended negatives | PASS | R/full-verification/release/ and release.tar.gz | 31/31; two 16-trial harness datasets, 14 figures and 9/9 smoke negatives; no scientific eligibility |
| ASan+UBSan+LeakSanitizer full gate | Canonical sanitizer profile, leak detection and halt-on-error enabled | PASS | R/full-verification/sanitize/ and sanitize.tar.gz | 31/31; no TSan/race-freedom implication |
| Campaign Python regressions | Restored venv and freshly built Release runner/fixture | PASS | R/full-verification/campaign-python.log and native-*-workload.log | 371 executed campaign tests; 14 native/workload tests per build; fixture cgroups synthetic except separate real-control execution |
| Archive/repair infrastructure | Existing documented standalone entry points | PASS | Archive 59/59, repair 17/17, negative diagnostics 3/3 logs | Synthetic contract tests do not substitute for historical archives |
| Deterministic inputs | Raw configuration comparison to baseline; canonical plan and 104-trial manifest expansion/digests | PASS | `manifest-preservation.json` | This is deterministic regeneration/comparison, not reopening a missing historical manifest file |
| Available retained Phase 6 evidence | Independent raw SHA-256 checks of five old inventories; archived source compared to f83ebd4 Git objects | PASS | `retained-evidence-verification.json` | 371 artifact checks and 168 source checks, zero mismatches; not Phase 5 archive validation |
| Full pinned analysis environment | Exact eleven versions, pip check, real Agg render, ambient inventory comparison | PASS | R/restoration-result.json, pip-freeze.stdout, environment-gate.stdout | Isolated .venv-analysis only; bootstrap pip 25.3, no pip upgrade or system package changes |
| Full registration and renderer smoke | Actual full configure/checkers, render tests and complete smoke entry point | PASS | R/full-verification/optional-official-registration.log and release/ | Default 31 executed; opt-in diagnostic registration exactly 32; 14 diagnostic tests executed separately per build |
| New current-code archives and sidecars | sha256sum plus copied trusted kit under system Python -I -S -B with checkout/venv/network/subprocess access denied | PASS | R/offline-verification/offline-results.json | Three newly generated full-profile pairs; source a293d1a, not regenerated historical evidence |
| Full-gate negative and compatibility controls | Six intended configure failures; four compatibility configurations; invalid full-without-tests rejection | PASS | R/full-verification/environment-negatives/, compatibility/ | Counts 31 full, 27 minimal, 0 library-only, 37 optional; original gates remain strict |
| Mandatory historical Phase 5 baseline archive/inventory verification | Recover original published workflows; verify original ZIP digests, archive sidecars, complete member inventories, source Git objects and full profiles | PASS | H/recovery-index.json, verification-results.json, workflow-provenance.json | Nine originals verified; earlier separate local-run copies remain unverified and are not used as acceptance inputs |

| Performance inference/physical-core speedup | No scientifically eligible observations established by this audit | NOT APPLICABLE | All pilot and bound evidence retains false scientific flags | No confidence intervals, significance or scaling claim is justified |
| Phase B and later phase acceptance | Separate later work from this acceptance decision | NOT APPLICABLE | This report and AGENTS.md | Outside Phase A; no later implementation or acceptance is claimed |

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

The authorized restoration used these exact installation operations (recorded argv,
stdout/stderr, return codes and timestamps are in R/restoration-commands.json):

```sh
python3 -m venv .venv-analysis
.venv-analysis/bin/python -m pip --isolated --disable-pip-version-check --no-cache-dir install --require-virtualenv --no-deps --only-binary=:all: --no-input --report results/validation/phase-a-pinned-restoration/install-report.json -r benchmarks/requirements-analysis.txt
.venv-analysis/bin/python -m pip --isolated check
.venv-analysis/bin/python -m pip --isolated freeze --all
.venv-analysis/bin/python -B tools/validation/check_environment.py
```

The eleven installed project versions exactly match the unchanged specification:

| Package | Version |
| --- | --- |
| matplotlib | 3.10.8 |
| numpy | 2.4.1 |
| contourpy | 1.3.3 |
| cycler | 0.12.1 |
| fonttools | 4.61.1 |
| kiwisolver | 1.4.9 |
| packaging | 25.0 |
| pillow | 12.1.0 |
| pyparsing | 3.3.2 |
| python-dateutil | 2.9.0.post0 |
| six | 1.17.0 |

Pip 25.3 is the standard venv bootstrap tool, not an additional project dependency;
it was not upgraded. Dependency resolution was disabled, only pinned binary wheels
were installed, and pip check confirmed the closed dependency set. The before/after
package inventories of both ambient interpreters are identical. The requirements
file hash is unchanged, and system site packages are disabled for this venv.

The restored driver uses a clean local a293d1a checkout with no overlay, builds and
runs each canonical full profile sequentially, and checks the frozen source stays
unchanged. It includes full registration, real analysis_figures execution and
Release pipeline/negative controls. The optional diagnostic tier is separately
configured and checked for exactly 32 enabled names; its 14-test workload script
runs against the fresh binaries from each canonical profile. Thus the historical
31-name archive contract remains unchanged, and no executed-32-test claim is made.

To reproduce current full profiles, use fresh disjoint outputs and the approved
execution mechanism that supports LeakSanitizer inspection/Unix-domain sockets:

```sh
.venv-analysis/bin/python -B tools/validation/ci_verify.py --python "$PWD/.venv-analysis/bin/python" --mode debug --output /tmp/dynagraph-phase-a-full-new/debug
.venv-analysis/bin/python -B tools/validation/ci_verify.py --python "$PWD/.venv-analysis/bin/python" --mode release --smoke --output /tmp/dynagraph-phase-a-full-new/release
.venv-analysis/bin/python -B tools/validation/ci_verify.py --python "$PWD/.venv-analysis/bin/python" --mode sanitize --output /tmp/dynagraph-phase-a-full-new/sanitize
cmake -S . -B build/phase-a-full-registration -DDYNAGRAPH_FULL_VALIDATION=ON -DDYNAGRAPH_ENABLE_WORKLOAD_DIAGNOSTICS=ON -DDYNAGRAPH_ANALYSIS_PYTHON="$PWD/.venv-analysis/bin/python"
.venv-analysis/bin/python -B tools/validation/check_registration.py --build build/phase-a-full-registration --optional workload-diagnostics
```

Actual source/output paths, selected fresh binaries, environments and commands for
all supplemental tests are retained in R/full-verification/commands.json and the
three profile command catalogues. Sanitizers used canonical
`-fsanitize=address,undefined -fno-omit-frame-pointer` with matching linker flags,
`ASAN_OPTIONS=detect_leaks=1:halt_on_error=1`, and
`UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`. No requirement was disabled.
Fresh complete default profiles each execute **31/31**, including the renderer.
Release verifies both complete 16-trial datasets, all 14 figure files and all nine
specific negative diagnostics. Six environment/registration-negative configurations
and four compatibility configurations also pass their intended checks.

Three **new** archive/sidecar pairs are retained and independently checked with
sha256sum and a copied trusted verifier kit using system Python 3.12.3 with site
packages disabled. An audit hook denies reads from the original/frozen checkouts
or the venv, and denies network/subprocess activity. These current-code archives
carry source a293d1a and current execution timestamps. They are never labeled as
original Phase 5 archives and do not replace their missing historical provenance.

The immutable reference plan remains byte-identical to baseline. Its canonical
SHA-256 is `f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24`;
the deterministic 104-trial manifest SHA-256 is
`f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a`.
Only disposable development copies substitute the current executable digest and
observed CPU request for genuine diagnostic execution.

## Historical recovery and Phase A acceptance decision

The initial storage search checked **112 documented references**, traversed
**5,946 directories / 48,181 file entries**, and found no archive candidates in
accessible local storage outside excluded new outputs. It included Codespaces
persisted/shared mounts under `/workspaces/.codespaces`. Directory symlinks were
not followed; `/tmp/codex-daemon-1000` was access-denied and reported. This was a
local search result, not a claim that no backup existed elsewhere.

The repository's workflow documents upload of original verification bundles.
The already configured GitHub CLI could read their existing artifact records.
A read-only listing returned all **75 available artifacts**, including **nine
original Phase 5 artifacts** at source heads `02aecf155dca...` and `8b05c2b2dc12...`.
These were downloaded, not regenerated. No workflow, push, PR, merge, upload or
external computing job was triggered; all inspection/verification ran in Codespaces.

For every recovered artifact:

1. Original ZIP bytes match GitHub's recorded SHA-256 digest.
2. The original canonical `.tar.gz` and `.tar.gz.sha256` bytes were extracted
   without rewriting. Other uploaded negative fixtures remain inert ZIP data.
3. `sha256sum -c` and the copied trusted bounded offline verifier pass under system
   Python `-I -S -B`, with live checkout/venv access and network/subprocess denied.
4. Complete member hash/mode/size inventories and the original full profile pass.
   There are three originals each for debug-full-v1, release-smoke-v1 and
   sanitize-full-v1; each records 31 accepted tests. Those historical tests were
   not rerun or regenerated here.
5. All **133 archived source files per artifact** match original repository Git
   object bytes: **1,197 checks, zero mismatches**. Push and pull-request run
   provenance is retained. The three pull-request records retain their recorded
   merge revision `1471e90b...`; their complete source content also matches the
   workflow head `02aecf1...`. No revision metadata was rewritten.

The nine artifact IDs are 12917025344, 12916715606, 12915912063, 12915818384,
12915673958, 12915648737, 12915009363, 12914629585 and 12914479883. The three
original workflow contexts are push run 40916057294, pull-request run 40916117142,
and push run 40916519138. API provenance, original creation dates, current download
times, original bytes and all verification commands/results remain in H. These
records establish transfer/local consistency, not externally authenticated evidence
or a hosted-CI result for the current a293d1a implementation.

**Decision: the historical baseline gate is now PASS because original published
Phase 5 archives and their inventories/sidecars have actually been recovered and
verified.** The earlier BLOCKED assessment was made before that recovery. This is
new original evidence becoming available, not a waiver based on fresh regeneration.
The code's verification gates, archive contract and scientific restrictions were
not weakened.

The distinct earlier local-run retention directories, including
`results/validation/phase5c3b3r/`, are still absent. Their specific locally reported
hashes/runs have **not** been verified or claimed recovered. Their absence does not
block Phase A's current-code qualification now that an original published Phase 5
baseline covering all three full profiles is verified. They are not inputs to
current execution, completed-trial reuse or any scientific result. Any future claim
or analysis relying on those particular unavailable local runs remains blocked
until their genuine payloads are restored. This approval does not certify every
historical local-run claim or complete research provenance.

## Remaining project limitations outside Phase A

| Requirement | Result | Reason / minimum action if it is needed |
| --- | --- | --- |
| Verify specific missing older local-run copies | BLOCKED | Obtain their genuine payloads and original inventories/sidecars before using or endorsing those runs; published originals above are a separate verified baseline |
| TSan research acceptance / race-freedom claim | BLOCKED | Prior work_ report remains LIKELY TOOL/RUNTIME LIMITATION; rendering/ASan recovery does not satisfy that separate gate |
| Scientific performance eligibility | NOT APPLICABLE | Remains false; no eligible performance observations or physical-core speedup claim |
| Current-code hosted CI | NOT APPLICABLE | Current verification is local Codespaces execution; no new hosted workflow was triggered or claimed |
| Phase B interference assessment and later phases | NOT APPLICABLE | Not performed by this Phase A restoration/acceptance task; later work remains required |

**Phase A is APPROVED for the implemented local workload-instrumentation and
evidence-verification scope.** All mandatory Phase A gates pass. There are no
remaining Phase A software/dependency blockers. Scientific eligibility stays false,
TSan acceptance stays unmet, and whole-project completion is not declared.
