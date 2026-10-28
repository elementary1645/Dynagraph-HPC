# Descriptive benchmark analysis — Phase 5B-4B

This layer reads completed Phase 5B-3B experiment directories. It never executes
their staged binaries, modifies raw evidence, changes timing boundaries, or tunes
the engine. Python 3.11+ is required for decimal logarithms. Import and statistics
use the standard library; SVG/PDF rendering requires the exact versions in
`benchmarks/requirements-analysis.txt`. Dependency installation requires approval.

## Reproduction

From the repository root, after producing a complete timing dataset:

```sh
python3 benchmarks/python/analyze.py --plan benchmarks/configs/analysis-example-v1.json --output results/analysis/chain-smoke
```

Use the approved rendering environment's Python instead of `python3` when figures
are requested. The example is explicitly harness-only, with the pinned chain
graph/trace identities. It expects the timing-smoke directory documented in
[benchmark timing](benchmark-timing.md). The output directory must be new. Paths
in the plan are relative to the plan file; outputs inside evidence are rejected.
Successful CLI execution exits 0 with a small JSON result; rejection exits 2.
Set `figures` to `[]` for standard-library-only table generation. Missing or
incorrect rendering dependencies fail explicitly rather than silently omitting
requested figures. CMake registers import, statistics and CLI integration tests
on Python 3.11+, and figure tests when the pinned environment is present; set
`DYNAGRAPH_ANALYSIS_PYTHON` to its interpreter path.

## Version 1 analysis plan

Unknown/duplicate keys, unsupported versions, malformed decimal strings, invalid
digests, duplicate workload identities and missing required comparisons fail.
The example configuration documents all required keys. Top-level arrays are:

| Field | Contract |
| --- | --- |
| inputs | Unique ID, directory, workload/configuration references, hardware/session labels, synthetic flag, evidence intent, independence declaration, expected identities and optional provenance declarations |
| workloads | Unique ID and graph/trace/source identity, dependence group, optional positive rational weight (default 1/1) |
| compatible_configurations | ID, timing mode, delta, requested threads, fast-path mode, warmups, optional executable digest and build type |
| comparisons | Numerator, baseline and primary/adaptive/exploratory family |
| allowed_evidence_classes | Explicit accepted classifications |
| figures | Requested figure types; an empty list disables rendering |
| exclusions | Input ID and prespecified reason; every exclusion remains visible |

Schema version is integer 1; numerical configuration fields and weights are
canonical unsigned decimal strings. `expected_identities` contains graph, trace,
executable, normalized experiment configuration and manifest SHA-256 values;
null means no additional plan constraint, never bypassing actual validation.
Workload graph/trace/source identities are always checked. Compatibility is
computed from actual settings, executable, worker and host metadata, hardware
label, synthetic status and evidence class, rather than trusting group names.
Timing modes remain separate. Labels and independence declarations are supplied
by the researcher, not independently verified replication.

## Complete evidence and eligibility

The importer calls `experiment_records.validate_dataset(records.jsonl)` with its
public default (`pending=False`). This rechecks the terminal success, full
schedule, all policies, exact worker records, exit/stdout/stderr hashes, staged
executable, regenerated workload recipe, identities, preflight and final checks.
Partial worker output is never accepted. Duplicate records, missing evidence,
failed trials, identity mismatches, incomplete runs and reused run IDs/copied
records are rejected. Symlink evidence is rejected. SHA-256 inventories before
and after import/analysis detect changes; they are integrity checks, not producer
authentication or protection against a hostile concurrent writer. Large JSONL
datasets are loaded into memory, as in the existing complete validator.

Structural validity is independent of scientific eligibility:

| Classification | Meaning |
| --- | --- |
| invalid_or_incomplete | Complete validation or plan identity failed; no analysis |
| valid_harness_only | Synthetic fixture, declared instrumentation, or explicit harness intent |
| valid_performance_unconfirmed | Valid evidence lacking required performance provenance or known Release/uninstrumented metadata |
| performance_eligible | Release, no declared instrumentation, explicit performance intent and both hashed user declarations |

Provenance declarations are JSON objects with integer `schema_version:1`,
`scope` equal to `controlled_hardware` or `uninstrumented_build`, and a nonempty
`statement`. Input references contain their path and SHA-256. The manifest keeps
the statements and their user-supplied origin. Eligibility under these declarations
is not independent hardware attestation or publication approval. Codespaces
observations alone never establish controlled performance evidence. Unknown
instrumentation cannot be disproved by `none_declared` build metadata.
Any nonexcluded invalid or disallowed input fails the entire analysis; accepted
inputs are not silently analyzed as a replacement panel. Explicit exclusions are
recorded, and incomplete fixed panels are withheld.

## Statistical contract

For each completed full-trace run and block, all four policies must be present.
The primary comparison is incremental / dijkstra. Required adaptive comparisons
are heuristic / dijkstra, heuristic / incremental and heuristic / delta-stepping.
Other directions must be marked exploratory. Every ratio uses the numerator and
baseline trials in the same input/block, with matching workload, actual stratum,
graph/trace/executable/configuration identities, run, hardware, session and evidence
class. Output retains both trial IDs, policy positions, ticks and rational periods.

Seconds are exact `Fraction(ticks * period_num, period_den)`; stored floor
nanoseconds are independently checked. Subnanosecond positive ticks remain
positive. Runtime ratio is candidate time / baseline time; a value below 1 and
a negative log favor the numerator. These are service-path comparisons: shared
fast paths apply to the forced-Dijkstra baseline as well. No speedup or scaling
claim follows from harness observations.

Per-run summaries take the geometric mean of paired block ratios, using decimal
logs with precision 80 and 40 significant output digits, round-half-even. Medians
use the midpoint; observed minimum/maximum/range are descriptive. A zero baseline
leaves the ratio undefined. A zero numerator retains a zero ratio but has no log.
Both-zero pairs are undefined. Every zero observation stays in the tables; any
affected run aggregate and dependent panel aggregate is withheld. No epsilon,
clamping, overhead subtraction, filtering, bootstrap or significance test exists.
All confidence intervals are null with reason `inference_not_implemented`.

Fixed-panel summaries require every declared workload within every session in
each actual compatibility stratum. They average log ratios equally over runs
within session/workload, then apply explicit workload weights, then average
sessions equally. More blocks, runs or updates do not silently give a workload
greater panel weight. Dependence groups and declared session counts are reported;
neither blocks nor updates are claimed to be independent replicates.

Per-update latency is never summed into full-trace time or used as independent
replication. Each trial has its own median, minimum, maximum, zero count and ECDF.
Upper quantiles use the inverse empirical CDF (nearest rank). p90 requires at
least 50 distinct positions, p95 100 and p99 500; otherwise the value is null
with an explicit reason. Trials and positions are not pooled to cross thresholds.

Verified feature joins use canonical update indices, old/new weights, consecutive
endpoint repetition, declared cycling schedule and fixed-topology tail
reachability. Schedule mode is a recipe label, not observed repair behavior.
Initial weight distribution labels describe generation, not evolving weights.
Selected adaptive backend, affected vertices, actual teams and isolated selector
overhead remain null. The public update interval includes selector work; no
counterfactual cost or backend selection accuracy is inferred.

## Outputs and figures

The new directory contains `acceptance.jsonl`, `trials.csv`, `paired-ratios.csv`,
`run-ratios.csv`, `runtime-summary.csv`, `latency-summary.csv`, `latency-ecdf.csv`,
`adaptive-comparisons.csv`, `summaries.json`, `report.md` and
`analysis-manifest.json`. Empty products retain headers. Failure manifests and
acceptance reasons remain available when input rejection or rendering fails;
plan syntax failures happen before output creation. Failed outputs must not be
treated as successful research products.

Figures are paired-ratios, policy-runtimes, latency-ecdf, update-profile,
family-ratios, adaptive-comparisons and block-order. Each is rendered in SVG and
PDF from serialized tables, separated by actual stratum and workload (or family).
Absent timing modes yield explicit skip reasons. Undefined ratios and withheld
summaries have visible counts. ECDFs retain one curve per trial; block/order
panels show raw points. Whiskers are observed ranges, never inferential intervals.
Synthetic fixtures are labeled in figure titles and reports.

Rendering uses Agg, pinned dependencies, DejaVu Sans, fixed colors/markers,
default-reset styles, fixed SVG hash salt and suppressed creation timestamps.
The manifest records dependency/FreeType versions, numerical conventions,
normalized plan, code digests/revision/dirty state, input inventories and all
output digests except its own (avoiding a self hash). Same-environment regeneration
is byte-tested; cross-platform font/FreeType reproducibility is not established.
Raw paths and code working-tree metadata are provenance, so relocating inputs or
changing analysis code can legitimately change the manifest.

## Recovery and review boundary

The October 28, 2026 recovery found ten untracked implementation files and a
modified tests/CMakeLists.txt on feature/benchmark-analysis at e705df6. Those files
were inspected and preserved, with a pre-edit copy under
`/tmp/dynagraph-recovery-snapshot`. No separate Phase 5B-4A architecture or approval
document was present in the repository/local document inventory. The explicit
continuation request supplies this phase's implementation scope, overriding the
older AGENTS.md phase gate; correspondence to an absent 4A document cannot be
independently certified. See [research log](research-log.md) for actual commands,
results and limitations. Stop after implementation/testing for independent review.
