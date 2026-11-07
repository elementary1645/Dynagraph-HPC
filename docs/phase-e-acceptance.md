# Phase E — statistical analysis and scientific evidence assessment

**APPROVED for verified diagnostic assessment and tested numerical methods.**
The original campaign remains 104/104 unexecuted. The two Phase D pilot executions
are diagnostic-only, both observed_interference. No scientific performance
statistic, confidence interval or speedup is supported or computed from them.
Scientific eligibility remains false and TSan acceptance remains unmet.

## Baseline and authoritative inputs

The expected clean `feature/phase-e-statistical-analysis` branch began at
`e0ee5ff476376dafcaa11bbcf4d61457300fb4d0`, merging accepted Phase D. The explicit
Phase E request authorizes analysis implementation, adversarial tests, report
generation, regression validation, documentation and a local commit. It does not
authorize new campaigns, dependency installation or historical evidence mutation.

The authoritative input is the retained raw Phase D pilot plus its original/derived
plans, manifests, receipts, native observations, correctness streams and journal.
The preparation JSONL/summary is a secondary export that must agree field-for-field
with reconstructed raw evidence. Its claimed flags are not admission authority.
The complete Phase D retention inventory is anchored to this explicit SHA-256:

`1e0d0c658410a53f3a5824369b9c6b0a1dd4e60bb95add79a2cd83f81cc96f06`.

This expected digest is recorded in the Phase E command and acceptance document;
the program never derives a trusted anchor from the same input directory. Hashes
establish anchored transfer integrity/local consistency, not producer authentication.
The data remains local retained evidence, with its Phase D independent verification
and new Phase E reverification; locality alone does not confer trust. Missing
historical local-run copies are not substituted or endorsed.

The original canonical plan and manifest hashes are unchanged:

- Plan: `f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24`
- Manifest: `f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a`

## Analysis architecture and admission

The existing `analyze.py` entry point retains its legacy `--plan` behavior and
adds mutually exclusive `--phase-d` input with a mandatory explicit
`--inventory-sha256`. There is no scientific eligibility override. Modules:

- `analysis_evidence.py`: bounded regular-file/no-symlink inventory checks; exact
  original-manifest regeneration; existing `verify_pilot` and `inspect_recovery`;
  derived-plan constraints; raw record reconstruction and exact export reconciliation.
- `analysis_inference.py`: exact-rational numerical primitives, sample standard
  deviation, reproducible bootstrap and paired-unit ratios. These mathematical
  functions neither verify evidence nor authorize scientific performance claims.
- `analysis_evidence_report.py`: diagnostic summary/report and accounting SVG/PDF,
  using the existing pinned renderer environment; source/code identities and hashes.

Import requires the complete anchored inventory (at most 8,192 files, 64 MiB per
file, 256 MiB total), unchanged before/after ingestion and again after rendering.
FIFO/device/symlink/extra/missing/digest-corrupted input fails closed. Existing
pilot/journal verifiers recheck trial/attempt/execution identity, confirmed GO,
command/executable, graph/trace/configuration, correctness, process/thread identity,
workload regions, resource classification/coverage, receipts and journal lifecycle.
No archived runner is executed. Only documented build/provenance changes may
separate the derived plan from the original experimental definition. The actual
Release flags file must match its declared digest. Original and derived IDs must
be disjoint; pilot completion is never credited to the original manifest.

Every field and JSON type of the exported original and diagnostic rows is compared
against raw reconstruction, including nested environment/configuration, timestamps,
schema versions, actual workers, artifact digests and journal references. Summary
counts are independently reconstructed and compared. Missing/duplicated/reordered,
substituted or contradictory rows reject even when their outer inventory has been
independently rehashed. Successful integrity verification is separate from
scientific eligibility. Current pilot schema and diagnostic-only observation rules
provide **no scientific timing admission**; the report returns unavailable values
rather than calling numerical performance functions. Future eligible campaigns need
a separately qualified evidence adapter; accepting self-declared true flags is not
an implementation shortcut supplied by this phase.

## Numerical methods and safeguards

The reusable numerical helpers accept bounded lists of nonnegative exact integers
or Fractions. They reject bool, floats (including NaN/Inf), strings, missing and
negative values. They compute exact arithmetic mean, midpoint median, minimum,
maximum and empirical inverse-ECDF nearest-rank p90/p95. Sample standard deviation
uses denominator n−1, Decimal square root at the existing 80-digit working precision
and 40-digit output. For n=0 all estimates are unavailable; n=1 has no sample SD.
Zero durations remain in descriptive mathematics, never silently dropped.

The optional numerical confidence interval is a **95% IID experimental-unit
percentile bootstrap of the arithmetic mean**, with 2,000 resamples, SplitMix64-v1
seed 7, unbiased bounded integer selection, nearest-rank 2.5%/97.5% endpoints.
Sample order is part of the numerical input; paired keys are sorted. Seeds and
resample bounds are explicit and deterministic. CI is withheld for fewer than five
units and for constant/zero-resolution samples; the threshold is a conservative
software policy, not a proof of coverage or adequate experiment design. Resampling
work is capped at two million resampled selections. No independence is inferred from trial or
session labels. Bootstrap percentile intervals are approximate, not a guaranteed
coverage statement for arbitrary distributions.

Pairing primitives require exactly matching, nonempty named independent-unit keys,
retain complete pairs and resample ratios as units. They report candidate/baseline
runtime ratios with an explicit direction, not an unlabeled speedup. Zero in
either member makes the ratio unavailable. Incomplete keys reject and small paired
samples withhold CI. Provenance/configuration compatibility belongs to verified
ingestion; the pure numerical dictionaries are not an evidence ingestion API.
The current adapter accepts no eligible timing rows, so neither these helpers nor
the existing legacy descriptive functions receive Phase D diagnostic durations.
No per-update position, warmup or repeated query is promoted to independent
replication. No bootstrap or inference is performed on actual Phase D evidence.

## Actual findings and generated artifacts

New evidence is ignored under
`results/validation/phase-e-statistical-analysis/` (`E`). Actual analysis outputs
are in `E/analysis-one/`, with an independently regenerated copy in
`E/analysis-two/`.

| Accounting | Original campaign | Derived pilot manifest |
| --- | ---: | ---: |
| Planned expansion | 104 | 104 |
| Selected | 0 | 2 |
| Attempted | 0 | 2 |
| Completed | 0 | 2 |
| Verified-complete | 0 | 2 |
| Interrupted | 0 | 0 |
| Rejected executed trials | 0 | 0 |
| Unexecuted (including unselected) | 104 | 102 |
| Diagnostic-only executed | 0 | 2 |
| Scientifically eligible | 0 | 0 |

Both selected pilot trials are observed_interference with complete coverage and
passed correctness. Requested/observed teams are 1/1 and 2/2. Timing is null by the
verification-only command contract. There is no defensible mean/median/SD/runtime
percentile, performance confidence interval, paired performance comparison or
multicore speedup. All those report fields are explicitly null with a reason;
scientific sample count is zero. Resource counters are shared observations, not
algorithm timings or an independent measurement of contention causes. The Phase D
visible CPUs are SMT siblings on one core; no physical-core scaling follows.

Outputs:

- `summary.json`: exact original/derived accounting, full reconstructed diagnostic
  rows, resource classes, unavailable-performance reasons, all input hashes,
  analysis version/code hashes, Python/package versions and numerical configuration.
- `diagnostic-trials.jsonl`: verified diagnostic rows with identities/provenance.
- `report.md`: human-readable assessment, exclusions and scientific limitations.
- `accounting.svg`, `accounting.pdf`: one accounting figure in two formats,
  explicitly diagnostic-only; pilot categories overlap and must not be summed.
- `analysis-manifest.json`: complete output digests, source inventory anchor and
  analysis metadata. No runtime, scaling or speedup chart is generated.

## Validation, reproducibility and preservation

| Gate | Final Phase E evidence/result |
| --- | --- |
| New numerical/import tests | 11/11 PASS; existing analysis_stats totals 17 methods |
| Retained-evidence adversarial tier | 6/6 methods PASS, including independently rehashed promotions/substitutions |
| Debug / Release / sanitizer full profiles | 31/31 each PASS; strict JUnit, no skipped tests |
| Additive workload/resource tiers | 2/2 CTests per build PASS; 14 + 11 methods |
| Full campaign/evidence/recovery suite | 382/382 PASS; no skips |
| Registration | Default 31 and additive 33 verified |
| Rendering / Release smoke | 32 smoke trials, 14 existing figures; 2 new accounting formats PASS |
| Smoke / environment negatives | 9/9 and 6/6 intended rejections PASS |
| Compatibility | Full 31, minimal 27, library-only 0, optional 37 PASS; invalid full-without-tests rejected |
| Archive / repair / negative diagnostic regressions | 59/59, 17/17, 3/3 PASS |
| Standalone offline verification | Three new current profiles, nine original published Phase 5 profiles and retained Phase D pilot PASS |
| Manifest | 104 original rows; both required hashes unchanged |
| Repeated report generation | All six output files byte-identical |
| Historical preservation | 5,563 prior entries unchanged, zero differences |

Canonical evidence is in `E/{debug,release,sanitize}/`, supplemental logs and
registrations in `E/regression-continuation/`, final campaign/control logs in
`E/tail/`, new tests and offline checks in
`E/postcheck/`. The original top-level driver received unexpected SIGTERM (exit
143) after Release wrote its successful result and archive/sidecar. Its cause is
not established. Nested receipts, strict JUnit and independent archive verification
establish the completed Debug/Release legs; no validation child remained running.
A separate continuation ran only the never-started sanitizer and supplemental
checks. The original driver is not claimed to have exited successfully. Its logs
and `E/driver-interruption.json` are preserved; no completed leg or ambiguous
benchmark attempt was retried.

The first supplemental campaign run executed all 382 tests but one socket fixture
could not bind: the long continuation TMPDIR exceeded the AF_UNIX pathname limit.
That failed log remains in `E/regression-continuation/campaign-python.log` and is
not counted as passing. The same complete suite passed 382/382 with the fresh,
shorter `E/tail/` temporary path; final gate/compatibility/archive controls also use
that path. This was an execution-path correction, not a source/criteria change or
retry of an ambiguous campaign measurement.

Two complete report runs produce byte-identical JSON, JSONL, Markdown, SVG, PDF
and manifest files; `E/reproducibility.json` records each digest. The renderer
removes timestamp metadata and uses a fixed SVG hash salt, font/style and pinned
versions. The actual accounting preview was visually inspected. Output directories
are new/exclusive and must be outside immutable input evidence. Rendering or
validation failures do not publish a successful analysis manifest.

All profiles use one unchanged implementation/test inventory over the e0ee5ff base
with an explicitly captured dirty overlay; `E/postcheck/source-equality.json`
records equality. Final acceptance/runbook documents were written after checks.
The default full archive contract remains 31 registrations, additive diagnostics
33. No CMake/test-name, production algorithm, timing boundary, heuristic, pinned
dependency or historical evidence contract changed. All verification is local;
no hosted CI pass is claimed.

Exact actual regeneration command (use a fresh output path):

```sh
MPLCONFIGDIR=/tmp/dynagraph-phase-e-new-mpl .venv-analysis/bin/python -B benchmarks/python/analyze.py \
  --phase-d results/validation/phase-d-benchmark-campaign \
  --inventory-sha256 1e0d0c658410a53f3a5824369b9c6b0a1dd4e60bb95add79a2cd83f81cc96f06 \
  --output /tmp/dynagraph-phase-e-new-analysis
```

Numerical/import tests use `python -B tests/test_analysis_evidence.py`; the standalone
retained-evidence attack tier additionally takes the Phase D directory argument.
The 11 new unit tests also execute through existing `analysis_stats` CTest, with
17 total analysis_stats methods. The separate six retained-evidence methods need
no benchmark launch and are not skipped ordinary CI prerequisites.

Exact regression/postcheck top-level commands:

```sh
.venv-analysis/bin/python -B /tmp/dynagraph-phase-e-regression.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-e-regression-continue.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-e-regression-tail.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-e-postcheck.py
```

Copies of these drivers, standalone offline verifier and history/retention scripts
are in E. Exact nested argv, controlled environments, timestamps, exits and log
hashes are in `E/**/commands.json`. The approved execution mode supports sanitizer
inspection and Unix-domain sockets required by regression controls. Leak detection
remains on (`ASAN_OPTIONS=detect_leaks=1:halt_on_error=1`), UBSan remains halt-on-error,
and canonical address/undefined sanitizer flags are unchanged. The existing Python
3.14.2 venv passes all eleven exact dependency pins and actual Agg rendering;
no dependencies were installed. Numerical fixtures are synthetic controls, not
benchmark observations. Regression smoke/native fixtures remain harness-only and
are not counted as new Phase D campaign measurements.

Historical inventories and original archives are checked read-only. Build trees,
caches and inert configure/repair fixture copies are excluded from retention;
commands, logs, source inventories, new canonical archives/sidecars, transferred
original archive bytes, reports, native regression artifacts and scripts remain.
`E/audit-sha256.json` inventories retained bytes. No historical Phase D summary,
runner, receipt, journal or native observation was changed or relabeled.

## Remaining blockers and phase boundary

Scientific performance statistics require actual qualified timing measurements,
compatible hardware/configuration, meaningful independent replication and a
scientific evidence admission contract. The original campaign remains unexecuted;
no present diagnostic flag grants that authority. Exclusive physical cores,
stable isolation, absent interference, authenticated production and race-detector
acceptance remain unestablished. Mathematical synthetic tests do not demonstrate
performance or CI validity for this Codespaces workload. Legacy descriptive
harness analysis is preserved with its existing limitations; it is not silently
upgraded to scientific inference. Specific missing older local-run copies remain
unverified, and are not acceptance inputs.

Changed files: `AGENTS.md`, `README.md`, `benchmarks/python/analyze.py`,
`benchmarks/python/analysis_evidence.py`, `benchmarks/python/analysis_evidence_report.py`,
`benchmarks/python/analysis_inference.py`, `tests/test_analysis_evidence.py`,
`tests/test_analysis_stats.py`, `docs/benchmark-analysis.md`,
`docs/experimental-protocol.md`, `docs/reproducibility-validation.md`,
`docs/research-log.md` and `docs/phase-e-acceptance.md`.

Stop after the authorized local commit/report. No push, PR or merge; later phases
and experimental execution require a new request and satisfied prerequisites.
