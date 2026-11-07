# Phase D — reproducible campaign and evidence acceptance

**APPROVED for the permitted bounded diagnostic/software evidence scope.** The
original 104-trial campaign was **not executed**. Scientific eligibility remains
false; there are no scientifically admissible timing observations or speedup
results. Full scientific campaign execution is blocked in Codespaces under the
existing contracts. This is not approval of a completed 104-trial experiment.

## Baseline, manifest and execution decision

The clean `feature/phase-d-benchmark-campaign` branch began at the expected merge
`c1f607af395903eaa5affb9eb207d45e8db7905b`, containing accepted
[Phase A](phase-a-acceptance.md), [Phase B](phase-b-acceptance.md) and
[Phase C](phase-c-acceptance.md). The explicit Phase D request authorizes inspection,
bounded development execution, verification, documentation and a local commit.
It expressly requires respecting existing execution rules.

The original plan and deterministic manifest are preserved in new ignored evidence
`results/validation/phase-d-benchmark-campaign/` (`E`). Canonical hashes:

- Plan: `f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24`
- Manifest: `f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a`

The expansion contains 104 trials: eight diagnostic, 64 warmup and 32 measured
selections. It specifies the development chain (8 vertices, 7 edges), source 0,
12 strict/repeat/equal updates, graph/weight/source/trace seeds 1/2/3/4, positive
weights 16–32, maximum decrement 2, workers 1/2, delta 16, four policies,
shared_fast_path, unchanged 4096/32/65536 heuristic thresholds, four blocks,
two warmups, order seed 7 and campaign-balanced-four-v1. Original rows, IDs,
recipes, configuration order and goldens were not modified.

The existing [pilot contract](campaign-pilot.md#bounds-and-process-contract)
limits a selection to **eight trials**, a **120 s** wall budget and **30 s** per
trial. There is no matrix executor. The experimental protocol defers complete
campaigns. Workload/resource observations require diagnostic selections and
explicitly exclude timing. Serial executions without a delta region cannot
establish complete resource coverage. The original example also has placeholder
build digests and cannot execute unchanged. A full diagnostic or scientific run
is therefore not permitted by this executor; no batching, enlarged bound,
disabled observation gate, relabeling of warmups/measured selections or new
competing framework was used to bypass those restrictions.

Following the documented staging procedure, a separate derived development plan
records the current source revision, actual executable/compiler/candidate-libgomp
hashes, the hash of the retained Release flags.make file and observed CPU allocation.
`E/execution/derivation.json` records every changed field. Workloads, seeds,
parameters, policies and scheduling remain equal to the original plan. Derived
trial IDs are different; they are never represented as original-manifest executions.
Two diagnostic delta-stepping trials, workers 1 and 2, were selected. Each runs
full compiled verification and the independent Python oracle, with all enforcement,
workload and resource opt-ins. Bounds were 60 s wall, 20 s per trial and 1 MiB per
stream. No timed process was launched by this pilot.

## Environment qualification and pilot observations

Ubuntu 24.04.5 LTS, kernel 6.8.0-1064-azure; GCC 13.3.0, CMake 3.28.3 and
Python 3.14.2. The visible model is AMD EPYC 7763, with two online logical CPUs.
Parent/child requested affinity and effective cpuset are `[0,1]`. Sysfs reports
both CPUs as **SMT siblings on package 0, core 0**, not two independent physical
cores. Cgroup v2 exposes `/sys/fs/cgroup/init` and `/sys/fs/cgroup`, each with
`cpu.max="max 100000"` and `memory.max="max"`. No finite visible quota or memory
headroom bound was observed; hidden host restrictions remain unknown. The snapshot
reported 6,033,170,432 available memory bytes; this is an observation, not a future
allocation guarantee or enforced RSS limit.

The Release executable SHA-256 is
`bbc1bc6d9c78bbafd19b84491c9c0e4adc92fed989134bfdf26aa37473e621a7`.
The candidate runtime is `/usr/lib/x86_64-linux-gnu/libgomp.so.1.0.0`, SHA-256
`135f3c8f006d2fe5e68e51281c7974cb991a03de3bfb3593d68d174dfcf854d1`.
Both early runtime snapshots report unavailable child OpenMP mapping evidence;
that absence is retained. Confirmed enforcement and workload/native generations
are verified through their separate gates. Observed workload teams are `[1]` and
`[2]`. Both trials have complete resource coverage, no issues/configuration changes,
and **observed_interference** from positive shared CPU PSI totals. Visible
throttling counters did not increase in these intervals. These facts do not imply
unlimited host resources or establish a source for the observed pressure.

Full raw facts are in `E/execution/hardware.json`, `E/environment-qualification.json`,
`E/execution/pilot/hardware.json`, child runtime/affinity sidecars and native resource
artifacts. Tool versions, compile flags in `E/build-provenance/`, exact executable bytes/digest and clean
source inventories are retained. The initial inspector's libgomp is explicitly a
candidate identity; individual child mapping snapshots can be unavailable during
exec/exit and are not promoted into active-runtime proof. Actual teams come from
validated workload regions, independently of worker requests.

The development admission result grants no scientific performance eligibility.
No declaration or snapshot establishes exclusive physical cores, stable isolation,
absence of contention, independent physical-core scaling or authenticated producer
identity. Resource counters are shared and include observer/oracle/other processes;
positive PSI/throttling deltas have no causal attribution. Even an observed_stable
result would establish only sampled-boundary consistency. TSan acceptance remains
unmet, with the historical work_ report classified LIKELY TOOL/RUNTIME LIMITATION.

## Exact execution accounting

| Category | Original preserved manifest | Separately identified derived pilot |
| --- | ---: | ---: |
| Planned for campaign / selected for pilot execution | 104 | 2 |
| Attempted | 0 | 2 |
| Completed successfully | 0 | 2 |
| Verified-complete | 0 | 2 |
| Interrupted | 0 | 0 |
| Rejected executed trials | 0 | 0 |
| Unexecuted original / unexecuted selected pilot | 104 | 0 |
| Scientifically eligible | 0 | 0 |
| Diagnostic-only executions | 0 | 2 |

The derived plan also expands to 104 rows; 102 were unselected and never launched.
Its two executions do not reduce the original manifest's 104 unexecuted count.
Unexecuted/deferred rows are not failed or rejected runtime attempts. Smoke and
regression fixtures are separate harness controls and excluded from these campaign
counts; their actual test/trial counts appear below. There was no pilot failure,
interruption, retry or resume invocation. Read-only journal inspection establishes
the settled lifecycle; explicit resume/immutable reuse/failure invariants are
exercised by the complete existing campaign tests.

## Independent verification and Phase E preparation

`verify-pilot` and `inspect-recovery` both pass for the retained pilot. They check
manifest membership, trial/configuration identity, execution/attempt bindings,
executable/argv, input hashes, full compiled and Python oracle outcomes, stream
receipts, process generations, workload membership/teams, resource coverage,
eligibility flags, inventory and journal semantics. Existing negative tests reject
missing, malformed, substituted, contradictory and independently rehashed evidence.
Unknown GO, unresolved launch, failed/interrupted attempts and incomplete publication
cannot authorize completion or an automatic retry.

A copied trusted verifier kit and relocated pilot are independently checked using
system Python `-I -S -B`, with an audit hook denying checkout/venv/working-build
reads, network and subprocess creation. All three new canonical full-profile
archives and all nine transferred original published Phase 5 archives pass
SHA-256 sidecars, bounded transport, complete member inventories and semantic
profiles. Historical archives are transferred original bytes, not regenerated
experiments. `E/offline-verification.json` records results. The separate
`E/pilot-transfer.tar.gz` + sidecar packages pilot evidence and Phase E rows with a
complete inventory; reopening reapplies the existing pilot/journal gates. It is
not mislabeled as a canonical CTest archive profile.

Machine-readable outputs:

- `E/phase-e-preparation/original-trials.jsonl`: all 104 original rows, unexecuted,
  unknown correctness/resource/actual-worker observations and null timing.
- `E/phase-e-preparation/diagnostic-trials.jsonl`: two verified diagnostic rows,
  original-sequence correspondence without identity substitution, configuration,
  requested/observed teams, source/executable/command, execution/attempt identities,
  correctness, resource classification/counter deltas, provenance, timestamps,
  journal references, schema versions and all per-trial artifact digests.
- `E/phase-e-preparation/summary.json` and `sha256.json`: explicit counts,
  classifications and output hashes.

Timing values are **null**, with a reason: these are diagnostic verification-only
processes. Collector intervals and process timestamps are not algorithm timings.
No performance ratio, speedup, significance test, confidence interval or diagnostic
latency statistic was computed. Phase E can inspect evidence completeness and
exclusions; no scientific timing analysis is admissible from this pilot. The
summary driver re-verifies evidence before exporting, checks disjoint manifest
IDs, observed teams, coverage, correctness and false eligibility flags.

## Required regression and preservation matrix

| Gate | Fresh Phase D result | Evidence |
| --- | --- | --- |
| Debug canonical full profile | 31/31 PASS | `E/debug/acceptance.json`, execution.xml, archive + sidecar |
| Release canonical full profile | 31/31 PASS | `E/release/acceptance.json`, execution.xml, archive + sidecar |
| ASan+UBSan+LeakSanitizer | 31/31 PASS; leak detection enabled | `E/sanitize/acceptance.json`, execution.xml, archive + sidecar |
| Workload/resource diagnostics | 2/2 CTests per build PASS; 14 + 11 methods each | `E/regression/*-diagnostics.xml`, strict postcheck acceptances |
| Campaign Python tests | 382/382 PASS; no skips | `E/regression/campaign-python.log` |
| Additive registration | Exactly 33 in all builds PASS | `E/regression/*-optional-registration.log` |
| Rendering and Release smoke | 32 trials, 14 figures PASS; valid_harness_only | `E/release/pipeline/pipeline-result.json` |
| Smoke negative controls | 9/9 intended rejections PASS | `E/release/pipeline-negative/negative-results.json` |
| Environment/registration negatives | 6/6 intended rejections PASS | `E/regression/test_gate/negative-results.json` |
| Compatibility | Full 31, minimal 27, library 0, optional 37; invalid full-without-tests rejected | `E/regression/test_compatibility/outcomes.json` |
| Archive / repair / negative diagnostics | 59/59, 17/17, 3/3 PASS | `E/regression/test_*.log`, repair/summary.json |
| Standalone current/historical archive and pilot verification | Three current, nine original profiles, two pilot trials PASS | `E/offline-verification.json` |
| Original plan/manifest | 104 rows, both required hashes PASS | `E/manifest-preservation.json` |
| Historical evidence preservation | 4,357 entries; zero differences | `E/historical-before.json`, historical-preservation.json |

Canonical profiles captured the identical clean source inventory at c1f607a;
`E/postcheck/source-equality.json` records equality. Documentation was written
after these checks; unchanged implementation is qualified at the baseline, not
under a future documentation commit hash. No demonstrated software defect required
production changes or new duplicate tests. All results are local Codespaces
execution, not hosted CI.

## Commands and reproduction

Exact argv, controlled environments, start/end times, exits and log hashes are in
`E/**/commands.json`; complete driver copies are retained. Top-level commands:

```sh
.venv-analysis/bin/python -B /tmp/dynagraph-phase-d-regression.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-d-postcheck.py
```

The regression driver calls existing `ci_verify.py` for Debug, Release `--smoke`
and sanitizer in fresh disjoint output directories, then diagnostic registration,
CTest, full campaign discovery and archive/negative/compatibility tests. Approved
execution mode supports LeakSanitizer inspection and Unix-domain enforcement
sockets; no requirements were disabled. The exact pinned environment passes a real
Agg render without dependency installation. Sanitizer controls remain
`ASAN_OPTIONS=detect_leaks=1:halt_on_error=1` and
`UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`, with
`-fsanitize=address,undefined -fno-omit-frame-pointer` and matching linker flags.

The postcheck stages the derived pilot through the existing campaign CLI, runs
verification, independent transfers, JUnit/source checks, summary generation,
pilot packaging and historical preservation. The actual pilot argv, including its
two derived trial IDs, is in `E/execution/commands.json`. The authoritative public
commands remain `campaign.py validate`, `expand`, `inspect`, `admit`, `pilot`,
`verify-pilot` and `inspect-recovery`. `resume-pilot` requires separate explicit
`--execute-development --authorize-resume` and renewed affinity/workload/resource
flags; it was not needed for this completed pilot.

To reproduce, choose **new** staging/output paths in the retained drivers, preserve
the original plan/goldens, build the expected revision, and derive a new plan using
current observed identities. Derived trial IDs change if any hashed plan field
changes. Never overwrite evidence, reuse an ambiguous attempt or remove diagnostic
labels. The original example is a planning fixture, not an executable scientific
manifest. Build trees, caches and inert configure/repair fixtures are excluded from
retained evidence; full logs, native artifacts, staged runners, inputs, transfer
archives, scripts and SHA-256 inventories remain. `E/audit-sha256.json` records the
final retained-byte inventory. Original build paths remain under
`/tmp/dynagraph-phase-d-20261107` in this session.

## Limitations and phase boundary

Full 104-trial execution requires a separately authorized executor/contract that
preserves evidence and recovery guarantees; it cannot be enabled by silently
raising pilot limits or splitting the matrix. Scientific measurement additionally
requires genuine qualified hardware/runtime/build evidence and the documented
eligibility gates. Codespaces cannot establish those missing assurances. The
original placeholder build provenance must not be treated as actual
provenance. TSan acceptance, hidden host constraints and authenticated producer
identity remain unresolved. Particular older missing local-run copies remain
unverified; only the nine recovered published originals are reverified here.

Changed files: `AGENTS.md`, `docs/experimental-protocol.md`,
`docs/reproducibility-validation.md`, `docs/phase-d-acceptance.md` and
`docs/research-log.md`. These are documentation only. No dependency, algorithm, public API, selection heuristic, workload golden,
trial definition, timing boundary, pilot/journal schema or executor limit changed.
Historical Phase A/B/C and Phase 5 evidence remains unchanged. No push, PR or merge
was performed. Stop after the local Phase D commit/report. Phase E is not started;
any later execution or scientific analysis needs a new request and satisfied gates.
