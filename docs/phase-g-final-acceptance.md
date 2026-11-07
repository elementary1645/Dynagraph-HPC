# Phase G — final system acceptance and release readiness

## Final five-part verdict

| Dimension | Verdict | Scope |
| --- | --- | --- |
| A. SOFTWARE ENGINEERING | **PASS** | Existing algorithm correctness, transactional failure, integration, bounded concurrency and memory/UB/leak checks pass; no race-freedom claim. |
| B. BENCHMARK AND EVIDENCE INFRASTRUCTURE | **PASS** | Deterministic planning, bounded diagnostic enforcement, oracles, observations, offline/journal/resume, negative controls and archive integrity pass. |
| C. DOCUMENTATION AND REPRODUCIBILITY | **PASS** | Documented workflows and both prepared presentation procedures execute in this Codespace; pinned/retained-input dependencies are explicit. |
| D. SCIENTIFIC MULTICORE PERFORMANCE QUALIFICATION | **NOT ESTABLISHED** | Original campaign unexecuted, zero scientific timing samples, no eligible performance CI/speedup, no exclusive-core/isolation evidence and TSan acceptance unmet. |
| E. CODESPACES-CONSTRAINED PROJECT DELIVERABLE | **ACCEPTED** | Ready for a final review PR of this bounded software deliverable, subject to normal review; no PR/push/merge/tag/release performed. |

This is the final planned A–G gate and local handover, not production deployment
certification, formal correctness proof, authenticated producer attestation or a
completed scientific multicore experiment. No additional phase starts automatically.

## Baseline and acceptance scope

Started on the required `feature/phase-g-final-acceptance`, clean at expected base
`fd59a6b27221a5e91280f40d2375b3e9dc785490`, merging accepted Phase F. The initial
repository state, structure and A–F acceptance paths are in `E/baseline.json`.
`E` denotes new ignored `results/validation/phase-g-final-acceptance/` evidence.
Library version remains 0.1.0. The audit inspects public APIs, graph/algorithms,
CLI/benchmark parsing/replay, CMake/OpenMP/test registration, campaign and evidence
contracts, analysis, documentation and retained acceptance/archival provenance.

A single agent performed source/test/evidence review and final execution; this
is not a claim of a separate independent human reviewer or new hosted CI. Existing
scripts were reused. No production algorithm, schema, timing boundary, manifest,
scientific eligibility rule, dependency or workflow changed. No new test was added:
no concrete uncovered acceptance defect was demonstrated. Final changes are
handover/acceptance/index/authorization/research-log documentation only.

## Verification and command provenance

The full canonical matrix is **freshly built and executed**, not substituted by
historical passes. Each profile starts from the same clean fd59a6b source inventory;
`E/postcheck/source-equality.json` records equality. Default 31-name registration,
strict JUnit execution, full pinned environment and archive acceptance are enforced
by existing `tools/validation/ci_verify.py`. Release includes both full-trace and
per-update smoke modes. Optional native tiers are registered afterward and executed
separately, keeping the historical canonical 31-test archive contract unchanged.
Final documentation is written after validation; tests qualify the unchanged
implementation at fd59a6b, not a future documentation commit hash.

Exact top-level commands actually used:

```sh
.venv-analysis/bin/python -B /tmp/dynagraph-phase-g-validate.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-g-tsan.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-g-demo.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-g-postcheck.py
python3 -B /tmp/dynagraph-phase-g-links.py /tmp/dgg/documentation-checks.json
```

Driver/checker copies are retained in E. Full nested argv, cwd, environment controls,
timestamps, exits and log SHA-256 are in `E/regression/commands.json`, profile
`commands.json`, `E/tsan/commands.json`, `E/docchecks/commands.json` and
`E/postcheck/commands.json`. Linux socket/LeakSanitizer-capable approved execution
was used where necessary; no failed/skipped check is counted as passed. No packages
were installed or upgraded. Observed environment is GCC 13.3.0, CMake 3.28.3,
Python 3.14.2 with the existing eleven exact analysis pins and a real Agg render.
Sanitizer flags remain `-fsanitize=address,undefined -fno-omit-frame-pointer`, matching
linker flags, `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1` and
`UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`.

## Exact final test matrix

| Check | Fresh final result | Evidence |
| --- | --- | --- |
| Debug configure/build, full CTest, strict JUnit | 31/31 PASS, zero skipped/disabled/failed | `E/debug/acceptance.json`, execution.xml, commands/logs, archive + sidecar |
| Release configure/build, full CTest, strict JUnit | 31/31 PASS, zero skipped/disabled/failed | `E/release/acceptance.json`, execution.xml, commands/logs, archive + sidecar |
| ASan+UBSan+LeakSanitizer configure/build and CTest | 31/31 PASS; leak detection/halt-on-error enabled | `E/sanitize/acceptance.json`, execution.xml, commands/logs, archive + sidecar |
| Workload and resource diagnostic tiers | 2/2 CTests per configuration PASS; 14 workload + 11 resource methods per build | `E/regression/*-diagnostics.xml`, strict postcheck acceptances, native artifacts |
| Registration | Exactly 31 canonical, exactly 33 with both diagnostics in every build | Canonical registration.log; `E/regression/*-optional-registration.log` |
| Full campaign/evidence/journal/resume Python suite | 382/382 PASS, no skips | `E/regression/campaign-python.log` |
| Statistical/import unit and actual retained-evidence adversaries | 11/11 new unit methods; 17 total analysis_stats methods inside canonical CTest; 6/6 standalone retained-evidence methods PASS | `E/postcheck/new-unit-tests.log`, real-adversarial-tests.log, CTest output |
| Rendering and benchmark smoke | 32 harness trials, 14 figures PASS; valid_harness_only | `E/release/pipeline/pipeline-result.json` |
| Smoke intended negative controls | 9/9 specific rejections PASS | `E/release/pipeline-negative/negative-results.json` |
| Environment/registration negative controls | 6/6 specific rejections PASS; missing/extra/duplicate checker controls PASS | `E/regression/test_gate/` |
| Compatibility configurations | Full 31, minimal 27, library-only 0, optional 37 PASS; full-without-tests rejected | `E/regression/test_compatibility/outcomes.json` |
| Archive / repair / negative diagnostic regressions | 59/59, 17/17, 3/3 PASS | `E/regression/test_archive.log`, test_repair.log, test_negative_diagnostics.log |
| README/reproduction and both demonstration procedures | All executed command blocks PASS, with only prescribed fresh output-path substitutions | `E/docchecks/commands.json`, result.json, per-block logs |
| Fresh bounded diagnostic integration fixture | 1 selected/attempted/completed/verified-complete; scientific eligibility false | `E/pilot/`, `E/docchecks/guide-step-6.log` |
| Current and original historical offline archives | Three new current full-profile pairs and nine original published Phase 5 pairs PASS; retained Phase D pilot and fresh G fixture PASS | `E/offline-verification.json`, isolated kit/transfer files |
| Defined report reproducibility | All six regenerated files byte-identical across two final runs and accepted Phase E output | `E/reproducibility.json`, reproduction-checks.json |
| Manifest expansion | Exactly 104; both golden hashes unchanged | `E/regression/manifest-preservation.json` |
| Historical preservation | 7,681 prior entries, zero differences | `E/historical-before.json`, historical-preservation.json |
| Local links / Mermaid diagrams | Local paths/anchors and restricted static flowchart grammar/references PASS | `E/documentation-checks.json` |
| TSan capability / research acceptance | **NOT ACCEPTED**: race-free default-PIE control cannot start; exit 66, fatal unexpected memory mapping | `E/tsan/assessment.json`, run-atomic-negative.log, elf-header.log |

Final passing components above are actual executions. The separately recorded TSan
startup failure is not converted into a functional-test pass or hidden by the overall
bounded acceptance decision. No other mandatory final test remains failed/skipped.
Build/test runtimes, smoke timings and resource collection intervals are harness
metadata, not scientifically admitted performance observations.

## Algorithm correctness and integration findings

Dijkstra tests cover full distances/unreachable sentinels, isolated/disconnected/
zero-weight/equal-path/seeded sparse/dense graphs, uint32 boundary weights and uint64
sums, invalid inputs, stable graph state and documented determinism. Empty graphs
have no valid source and correctly reject SSSP queries. Supported type arithmetic
has the documented finite-path overflow bound; maximum-size graph allocation is
not claimed tested.

Delta tests cover six deltas through UINT64_MAX, runtime-default and explicit
requests, oracle agreement, same-bucket repeated light closure, final-label heavy
scan, stale work, sparse buckets, competing atomic relaxation, 256-edge partition
boundaries, per-call ownership, synchronization, failure/exception paths, nested/
dynamic teams and independent callers. Observed teams are separate from requested
workers. Full functional/sanitizer checks and bounded deadlock timeouts are not an
exhaustive-schedule, race-freedom or portable scaling proof.

Incremental/adaptive tests cover equality, weight-only and successful repair,
repeated decreases, complete-state agreement with fresh recomputation and independent
edge-record Bellman–Ford, policy switching/shared fast paths, allocation failures,
rollback and subsequent state reuse. Increases/topology changes remain outside repair.
The heuristic remains fixed metadata-only, uncalibrated and not claimed optimal.
Shared engine access, including inspection, requires external serialization.

Integration validates generated graph/trace verification, static CLI distance equality,
all four benchmark policies, full per-update oracle checks, original planning,
confirmed-GO/affinity/native workload/resource evidence, offline consistency,
settled journal lifecycle, verified analysis and report generation. Full campaign
regressions include conservative unknown GO, cleanup, deadlines, interruption,
publication failure, ownership, explicit pending-only resume, immutable completed
reuse, duplicate prevention and independently rehashed substitution attacks.
No new recovery rule or automatic retry is introduced by this audit.

## Reproduction and professor demonstration acceptance

The existing guide's literal Bash blocks and prepared five-/ten-minute procedures
are executed under errexit. Build/data paths follow its stated fresh-name rule:
`DG_BUILD=/tmp/dgg/release/build`, `DG_DOC_RUN=/tmp/dgg`; README paths are rebased
to that freshly accepted Release build and a new identical recipe bundle. This
changes locations only, not interfaces, graph/trace/algorithm parameters or intended
observations. Full build/test/campaign commands shared with the fresh matrix execute
once rather than redundantly rerunning whole suites within the guide.

The guide's one explicitly opted-in diagnostic fixture is new and distinct from
historical D/F trials. It uses max_trials=1, wall=60 s, timeout=20 s and 1 MiB streams;
all existing enforcement/observation limits apply. No original campaign row is
executed. Its observed classification/coverage/team are retained, not fabricated
or predetermined: requested/observed workers 2/2, observed_interference, complete coverage, no issues;
new trial ID `ac0d6fa74a7e59a21ebe1cd74d21aaf93b98b961f22744ae9b8003e07ef29e4b`. No timing worker, ambiguous retry or resume
was used. Demonstration correctness comparisons use the actual documented chain,
source 0, delta 16 and policy paths, not an unrelated fixture.

Both presentation readiness checks pass, including verification of the actual
historical input and generated outputs. The five-/ten-minute durations are prepared
outlines, not a timed human rehearsal. Manual Codespace provisioning and portability
to another host are not newly tested. Complete historical presentation elsewhere
requires original retained bytes and exact dependency pins, as the guide explicitly
checks. A clone/PR alone lacks ignored evidence/venv. No missing data is silently
recreated. Mermaid receives static subset syntax/reference checks; no installed
renderer or rendered-Mermaid claim. Accounting SVG/PDF is actually regenerated.

## Evidence integrity and scientific assessment

The exact canonical hashes remain:

- Plan: `f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24`
- Expanded manifest: `f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a`

Original campaign: 104 planned, 0 selected/executed/completed/verified, 104 unexecuted.
Historical derived Phase D: 2 selected, 2 attempted, 2 completed, 2 verified-complete,
0 interrupted/rejected, both diagnostic-only and observed_interference with complete
coverage. Requested/observed teams are 1/1 and 2/2. Scientifically eligible timing
samples: 0. Timing/performance confidence intervals, speedup and multicore scaling:
unavailable. Phase E's anchored raw-input reconciliation reproduces these facts;
pilot, regression smoke and synthetic numerical controls are not independent
scientific replications. The fresh G fixture and historical F fixture remain separate
and never increment original/D accounting.

Raw pilot/journal, correctness, receipts, native classifications, identities and
all required digests are reverified beyond matching an outer hash. The complete
Phase D retention anchor remains
`1e0d0c658410a53f3a5824369b9c6b0a1dd4e60bb95add79a2cd83f81cc96f06`.
The copied trusted offline kit verifies new and original archive sidecars, bounded
gzip/tar expansion, complete member hash/mode/size inventories and semantic profiles
under system Python `-I -S -B`, denying checkout/venv/working-build reads, network
and subprocess creation. No archived executable runs. Original historical archive
bytes are transferred, never regenerated or relabeled as current tests. Specific
still-missing older local-run copies remain unverified and are not acceptance inputs.
Hashes establish local consistency/anchored transfer integrity, not authentication.

The TSan negative control is the existing `atomic_publication.cpp`, compiled with
GCC `-fsanitize=thread`, OpenMP/pthread, default PIE and no suppression. ELF DYN is
recorded. It fails at startup with unexpected memory mapping, before useful detector
calibration. No new toolchain, ASLR/system setting, fixed-layout flags or runtime
workaround is attempted. Current acceptance is therefore not achievable through
this default-runtime path; race-detector acceptance remains unmet. The earlier
work_ warning retains its historical LIKELY TOOL/RUNTIME LIMITATION classification;
this new startup probe does not reclassify it or establish race freedom.

## Files changed

`AGENTS.md`, `README.md`, `docs/reproducibility-validation.md`,
`docs/research-log.md`, `docs/phase-g-final-acceptance.md` and
`docs/project-handover.md`. All are Markdown; source, tests, build settings,
contracts, manifests and dependencies are unchanged.

## Release-readiness decision and outstanding limitations

Ready for a final review PR of the **Codespaces-constrained software deliverable**.
No software/evidence/documentation blocker remains within that accepted scope.
There is no GitHub release/tag, deployment certification, independent human approval,
push, PR creation, merge or new hosted CI claim. Final source changes are documentation
only; implementation/build/test code matches the clean validated baseline.

Remaining nonblocking handover limitations and scientific blockers are explicit:

- TSan cannot start in this default Codespace configuration; detector acceptance
  and race freedom remain unestablished, independently of ASan/UBSan success.
- Scientific qualification needs an explicitly authorized full executor/admission
  contract, genuine qualified timings, compatible build/runtime/hardware provenance
  and justified independent replication. No eight-trial-cap bypass or full campaign
  is authorized. No scientifically unqualified performance claim belongs in the PR.
- Visible logical CPUs/affinity/quota and snapshot consistency cannot prove exclusive
  physical cores, stable isolation, absence of contention or hidden host capacity.
  Phase D's two visible CPUs are SMT siblings on one core; counters are shared.
- A new Codespace requires its prerequisites and original ignored evidence. Preserve
  the complete raw retention directories before depending on long-term availability;
  no backup/upload/transfer outside this workspace is performed here.
- Some particular older local-run payloads remain absent/unverified, and hashes are
  not producer attestation. Manual provisioning, other-platform portability and
  Mermaid rendering are not claimed newly validated.

See [project handover](project-handover.md) for navigation, maintenance, artifact
custody and future qualification requirements without duplicating the runbooks.
The final planned sequence ends after this local commit/report; any publication,
release, deployment or further experiment needs separate explicit authorization.
