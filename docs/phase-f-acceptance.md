# Phase F — final documentation and reproducibility acceptance

**APPROVED for documentation, reproducibility-command and presentation readiness
in the existing Codespace.** This is not scientific performance or whole-research
acceptance. Scientific timing eligibility remains false and TSan acceptance unmet.

## Baseline, scope and source audit

Started clean on `feature/phase-f-final-documentation` at expected base
`0b660ec12927a79c3c88944189a10ce6c1d265d0`, merging Phase E. The explicit Phase F
request authorizes documentation, diagrams, demonstration/command validation,
existing tests and a local commit. No production algorithm, public API, evidence
contract, timing boundary, dependency, workflow or benchmark manifest was changed.

The audit followed public headers, CSR/Dijkstra/delta/repair/adaptive source,
CLI parsers, benchmark replay/timing, CMake/test registration, campaign/enforcement/
workload/resource/journal/resume validators and analysis code. Existing Phase A–E
matrices and raw Phase D/E inputs were inspected and reverified as described below.
Source and raw evidence take precedence over historical prose. Unimplemented gates
were not described as completed experiments.

Documentation corrections include stale architecture claims that instrumentation
was reserved, adaptive/benchmark infrastructure unimplemented, or timing future-only;
old README phase gates and assumed ungenerated input files; broad statements that
all verify modes lack clocks/actual-team observations; and superseded runtime
instrumentation deferrals. Ordinary correctness verification has no algorithm timing,
while explicit diagnostic modes add monotonic observation envelopes and sidecars.
Legacy timing analysis and the Phase E diagnostic adapter now have distinct scope.
Detailed algorithm contracts were retained, including overflow, ownership, rollback,
synchronization and justified complexity; static CLI JSON schema details were moved
from the long README into architecture. Historical acceptance records and dated
research-log entries were preserved as as-of records, not rewritten as current status.

## Deliverables and consistency

| Deliverable | Content and validation |
| --- | --- |
| `README.md` | Project/capabilities/boundaries, conceptual Mermaid flow, verified full 31-test quick start, evidence workflow, limitations and documentation index |
| `docs/architecture.md` | Complete implemented stack, module/schema boundaries, 13-node Mermaid flow, detailed algorithms/APIs/complexity/synchronization, evidence/recovery/analysis |
| `docs/reproducibility-guide.md` | Per-step directory/dependency/success/limitation gates, fresh build and bundle, all algorithms, 382-test command, hashes, bounded diagnostic, archives, verified historical analysis |
| `docs/professor-demo.md` | Prepared five-/ten-minute walkthroughs, readiness checks, literal terminal commands, expected observations and technical Q&A |
| `docs/experimental-protocol.md` | Current answerable research questions, original seeds/design/counts/hashes, evidence limits and clearly marked historical evolution |
| Existing replay/analysis/runtime/validation references | Corrected scope statements, current entry-point links and retained strict contracts |
| `docs/research-log.md`, `AGENTS.md`, this matrix | Actual commands/outcomes, authorization boundary, preservation and outstanding limitations |

README is now a visitor/reviewer entry point; architecture retains the detailed API
and algorithm reference, the reproduction guide owns the current end-to-end workflow,
and the presentation guide points to it rather than inventing another setup path.
The older validation runbook remains authoritative for exact archive-profile/
independent-offline-kit requirements. Research questions distinguish bounded
correctness/evidence findings from unanswered performance/scaling questions.

Markdown local paths/anchors and both Mermaid diagrams are checked with the
retained static checker. Mermaid uses a restricted `flowchart LR` grammar with
quoted node labels, unique declared nodes and checked directed edges. No Mermaid
parser/renderer is installed; no package was installed and no rendered-Mermaid
claim is made. The source/table diagrams can be read locally; actual Phase E
accounting SVG/PDF generation is separately executed and verified.

## Verified commands and demonstration

New ignored evidence is under
`results/validation/phase-f-final-documentation/` (`E`). Commands/working directories,
controlled environments, exits and log hashes are in `E/check/commands.json`,
`E/docchecks/commands.json` and `E/postcheck/commands.json`. Full command-smoke
scripts are retained. The guide's literal Bash blocks were executed under errexit;
the identical full CTest/campaign commands already exercised in the matrix were
not needlessly repeated within that guide run. README's distinct default 31-test
quick start was executed literally, including its new build/data paths.

- Configure/build, registration, CLI help, generation and independent bundle
  verification succeeded. GCC 13.3.0, CMake 3.28.3, Python 3.14.2 and all eleven
  unchanged analysis pins passed the actual Agg environment gate.
- README static Dijkstra/delta results were `[0,32,51,76,100,119,139,162]` for the
  initial chain, actual delta team 2. The guide independently compares full vectors.
  These are correctness outputs, not timings.
- All four guide policy replays succeeded. The incremental fixture checked 12
  requests, 13 fresh Dijkstra states and 13 independent small-graph Bellman–Ford
  states, including final graph/distances. Focused repair/rollback CTests passed.
- Original validate/expand commands produced 104 rows and both exact canonical
  hashes. No original row was executed or modified.
- One new Phase F diagnostic command fixture was explicitly authorized and selected
  through the existing pipeline: delta, requested 2, observed `[2]`, one process,
  confirmed GO, full correctness and complete resource coverage. Its classification
  was `observed_interference`, issues empty, measurement eligibility false. Its new
  ID is `cddcea525f956e17cd426a7932b49b4cd64b19baad524c7cf39a818d6f482536`.
  It is distinct from the accepted historical Phase D two-trial pilot; no original
  campaign completion or historical count was incremented. No timing worker,
  ambiguous retry or resume was used. Raw data remains in `E/pilot/`.
- Raw Phase D pilot/journal verification passed and the anchored Phase E adapter
  regenerated its diagnostic report: 104 originals unexecuted, 2 historical
  diagnostic completions, observed_interference twice, zero scientific timings and
  null performance statistics. All six output files are present in `E/phase-e/`.
- All readiness, five-minute and ten-minute terminal command blocks passed,
  including output hashes and a fresh anchored raw-evidence inspection. The
  suggested presentation schedule is a prepared outline, not a measured rehearsal
  or a guarantee of human delivery time.

The fresh demo recipe/inputs are staged under new output paths; historical runner,
receipt, native observation, journal and report bytes were not modified. Fresh
pilot classifications are observations, not predetermined labels or isolation
proof. Future users need explicit execution authorization; one diagnostic fixture
is not authorization for the 104-trial matrix.

## Validation matrix and retained evidence

| Gate | Phase F result | Evidence |
| --- | --- | --- |
| Fresh README Release full default | 31/31 PASS | `E/docchecks/readme-quickstart.log`; new `build/review` |
| Fresh guide Release with both diagnostic tiers | 33/33 PASS, strict JUnit and exact registration | `E/check/release-{execution.xml,acceptance.json}`; new `/tmp/dgf/b` |
| Relevant Debug CTest, source-equivalent existing build | 33/33 freshly executed PASS | `E/check/debug-{execution.xml,acceptance.json}` |
| Relevant ASan+UBSan+LeakSanitizer CTest, source-equivalent existing build | 33/33 freshly executed PASS; detect_leaks=1, halt_on_error=1 | `E/check/sanitize-{execution.xml,acceptance.json}` |
| Equivalence of reused implementation/build/test sources | 145 files, zero mismatches | `E/check/reused-source-equality.json` |
| Campaign Python, evidence/recovery/resume controls | 382/382 freshly executed PASS, no skips | `E/check/campaign-python.log` |
| Rendering and Release smoke | 32 harness trials, 14 figures PASS | `E/check/smoke/pipeline-result.json` |
| Smoke negatives / archive / diagnostic controls | 9/9 intended rejections; 59/59; 3/3 PASS | `E/check/smoke-negative/`, test_archive.log, test_negative_diagnostics.log |
| Literal README/reproduction/presentation commands | All executed blocks PASS | `E/docchecks/result.json`, commands.json and per-block logs |
| Fresh diagnostic offline/recovery verification | 1/1 verified-complete, diagnostic-only | `E/pilot/`, `E/docchecks/guide-step-6.log` |
| Historical Phase D and Phase E assessment | 2 historical diagnostic completions; science sample count 0 | `E/docchecks/guide-step-{7,8}.log`, `E/phase-e/` |
| Independent archive transfer verification | Three retained Phase E canonical profiles + nine original published Phase 5 profiles PASS; fresh F pilot PASS | `E/offline-verification.json`, copied trusted kit |
| Original campaign preservation | 104 rows, both hashes PASS | `E/check/manifest-preservation.json` |
| Historical evidence preservation | 6,652 prior entries unchanged, zero differences | `E/historical-before.json`, historical-preservation.json |
| Markdown/Mermaid consistency | Local paths/anchors and restricted diagram grammar/reference checks PASS | `E/documentation-checks.json` |

Reused Debug/sanitizer binaries were built during Phase E from e0ee5ff plus its
recorded implementation overlay. Their embedded historical revision metadata is
not relabeled as 0b660ec. All 145 relevant files, including native apps/library,
Python analysis/orchestration, tests and build settings, match the current baseline
exactly. Current source-based Python tests and CTests ran freshly, with new JUnit/
logs; only equivalent compiled products were reused. Fresh README/guide Release
builds independently exercise the current base. No infrastructure was changed and
no earlier phase's implementation was rebuilt as new functionality.

The copied trusted offline kit runs under system Python `-I -S -B`, denying
checkout/venv/working-build reads and network/subprocess creation. Three Phase E
archive/sidecar pairs are **transferred retained evidence**, not newly produced
Phase F canonical archives. Nine original published Phase 5 pairs are likewise
original bytes, not regenerated historical experiments. Fresh F pilot relocation
passes ordinary semantic verification without executing its staged runner.

Phase E's recorded canonical 31-test Debug/Release/sanitizer profiles and its
compatibility/environment-negative results remain accepted **retained** evidence,
not claimed newly run here. Fresh Phase F checks are distinguished above. All local
results are Codespaces execution; no hosted CI outcome is inferred or triggered.
No validation failure remains. The static link scan initially found only references
to this not-yet-written acceptance file; the completed final scan passes.

## Manifest and finding preservation

Canonical plan SHA-256:
`f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24`.
Expanded manifest SHA-256:
`f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a`.

Accepted results remain bounded software correctness, transaction/recovery and
evidence-integrity findings. Original campaign execution is still 0/104. Historical
Phase D selected/attempted/completed/verified counts remain 2/2/2/2, both diagnostics
and observed_interference. Scientific eligible timing count remains zero. The new
one-trial F command fixture is explicitly separate and equally ineligible. Neither
CPU pressure deltas, algorithm work counters nor test/process times supply missing
scientific measurements. No performance statistic, multicore speedup or scientific
confidence interval is invented. TSan acceptance remains unmet; the earlier work_
report classification is LIKELY TOOL/RUNTIME LIMITATION, not race freedom.

## Files changed

`AGENTS.md`, `README.md`, `docs/architecture.md`, `docs/benchmark-analysis.md`,
`docs/benchmark-replay.md`, `docs/experimental-protocol.md`,
`docs/reproducibility-validation.md`, `docs/runtime-provenance.md`,
`docs/reproducibility-guide.md`, `docs/professor-demo.md`,
`docs/phase-f-acceptance.md`, `docs/research-log.md`.

## Reproduction limits and remaining documentation issues

No unresolved documentation/source contradiction remains within the audited scope.
Limitations are explicit rather than hidden:

- Codespace creation/start is a manual platform prerequisite and was not re-provisioned
  or claimed tested by these terminal commands. All actual commands ran entirely in
  the existing Codespace; no external hardware/service is needed afterward.
- A fresh clone lacks the ignored pinned venv and retained historical evidence.
  Obtain exact original bytes/explicit dependency permission before dependent
  historical/rendering steps. The guide checks availability/identity and stops
  rather than fabricating a historical replacement. The complete demonstration is
  ready in this verified workspace; it is conditional on those prerequisites elsewhere.
- Mermaid renderer availability is not established. Static syntax/reference checks
  cover the deliberately simple grammar; text/data-flow and accounting artifacts
  remain reviewable without installing a package.
- Specific missing older local-run copies are still unverified; recovered published
  originals are a distinct verified baseline. Digests provide integrity, not producer
  authentication. Missing early runtime mappings stay unavailable.
- Qualified scientific timing, a full authorized executor/admission adapter,
  independent replication, exclusive physical-core/isolated resources and TSan
  acceptance are not supplied by documentation or diagnostic success.

Exact actual top-level commands:

```sh
.venv-analysis/bin/python -B /tmp/dynagraph-phase-f-validate.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-f-doccommands.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-f-postcheck.py
python3 -B /tmp/dynagraph-phase-f-links.py /tmp/dgf/documentation-checks.json
```

Driver/checker copies and complete nested argv are retained in E. Raw builds/data
still exist in the printed session paths (`/tmp/dgf`, `build/review`, `data/review-chain`)
but are excluded from portable retention where appropriate. Logs, native artifacts,
staged runners, bundle, raw new pilot, regenerated report, transferred archives and
SHA-256 inventories remain in E; `E/audit-sha256.json` indexes retained bytes.
Stop after the authorized documentation commit/report. No push, PR, merge,
dependency install or later phase is authorized or performed.
