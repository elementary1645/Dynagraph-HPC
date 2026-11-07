# Project handover — Codespaces-constrained deliverable

DynaGraph-HPC is C++17/OpenMP research software for exact single-source shortest
paths on directed fixed-topology graphs with nonnegative integer weights and
updates between completed queries. The library version remains 0.1.0; no release,
tag or production deployment certification is created by this handover.

The [final acceptance matrix](phase-g-final-acceptance.md) separates software,
evidence infrastructure, documentation and scientific qualification. The project
is accepted for its verified Codespaces-constrained software scope; scientific
multicore performance is **not established**. The final planned A–G sequence stops
here. New work needs a new explicit request, not an inferred next phase.

## Start and navigation

| Need | Authoritative entry point |
| --- | --- |
| Capabilities, quick start and documentation index | [README](../README.md) |
| Algorithms, ownership, synchronization, complexity, schemas/data flow | [Architecture](architecture.md) |
| Setup through verified local reports, with availability gates | [Reproduction guide](reproducibility-guide.md) |
| Prepared five-/ten-minute command walkthrough and Q&A | [Professor demo](professor-demo.md) |
| Timing boundaries, questions and scientific eligibility | [Protocol](experimental-protocol.md), [timing](benchmark-timing.md) |
| Generation, recipe/digest checks and correctness-only replay | [Workloads](workload-artifacts.md), [replay](benchmark-replay.md) |
| Bounded execution / enforcement / native evidence | [Pilot](campaign-pilot.md), [GO/affinity](resource-enforcement.md), [workload](workload-instrumentation.md), [resources](resource-interference.md) |
| Immutable disk journal, conservative reuse and pending-only resume | [Recovery](campaign-recovery.md) |
| Analysis admission and numerical assumptions | [Analysis](benchmark-analysis.md), [Phase E](phase-e-acceptance.md) |
| Strict test registration/JUnit and bounded archive contracts | [Validation runbook](reproducibility-validation.md) |
| Provenance of failures, corrections and historical phase scope | [Research log](research-log.md), [A](phase-a-acceptance.md), [B](phase-b-acceptance.md), [C](phase-c-acceptance.md), [D](phase-d-acceptance.md), [E](phase-e-acceptance.md), [F](phase-f-acceptance.md), [G](phase-g-final-acceptance.md) |

## Architecture and support boundary

CSR owns sorted offsets/destinations/weights and stable edge IDs. Reference lazy-heap
Dijkstra and persistent-team OpenMP delta-stepping return full uint64 distance
vectors. Sequential single-edge decrease repair owns graph/source/distances, with
RAII undo on recoverable exceptions. The adaptive engine retains one authoritative
state and selects existing backends through forced policies or the unchanged
metadata heuristic; it has no learning, calibrated crossover or automatic delta tuning.

`dynagraph_cli sssp` exposes static Dijkstra/delta JSON output. Incremental repair
is a library API, exercised through `dynagraph_bench verify --policy incremental`;
there is no incremental static-CLI subcommand. The benchmark separates correctness
replay from timing workers. Python owns canonical generation, provenance, bounded
pilot enforcement, offline evidence/journal/resume and verified analysis.

Updates may decrease/equal existing weights. Storage/full recomputation can replace
supported weights, including increases, but incremental increases/topology changes,
batch/parallel repair and concurrent mutation remain deferred. Every access to one
shared adaptive engine needs external serialization. Independent immutable-graph
queries/separate engines have their documented concurrency scope, not a race-freedom
proof or simultaneous-progress guarantee.

## Setup, builds and tests

Use the existing Codespace and follow the reproduction guide's Bash setup and new
short output paths. GCC/OpenMP, CMake >=3.21, Make and existing Python are required;
full analysis/rendering requires the exact existing `.venv-analysis` pins. Do not
install/upgrade or silently weaken full validation when prerequisites are absent.
A clean clone does not contain that ignored environment or raw historical evidence.
Codespace provisioning is a manual prerequisite, not newly validated portability.

The repository provides Debug/Release presets and full canonical validation through
`tools/validation/ci_verify.py`. The latter requires `--python`, `--mode` and a new
`--output`; Release additionally requires `--smoke`. There is no sanitizer preset;
use the existing canonical sanitizer entry point. Its ASan/UBSan flags and leak
controls must remain intact. The final gate uses default 31 CTests per profile,
then two opt-in workload/resource diagnostics; combined registration is exactly 33.

The final raw receipts provide exact reproducible commands, counts and identities;
use [Phase G acceptance](phase-g-final-acceptance.md#verification-and-command-provenance)
and the validation runbook rather than guessing flags. Run campaign regressions
with the freshly built benchmark/fixture paths; all 382 tests are required by the
current acceptance matrix. Intentional-race TSan controls remain outside CTest/CI.

## Demonstration and artifact availability

The five-/ten-minute procedures are prepared presentations, not measured promises
of presenter delivery time. Build/generate/verify and check retained evidence before
the timer. Final acceptance executes their real command blocks; it does not replace
the intended workload with an unrelated fixture. Fresh path names are permitted
by the guide to avoid overwriting outputs.

The algorithm portion works with newly generated canonical chain bytes. A complete
historical evidence/analysis presentation also needs the **whole original Phase D
retention directory** and explicit anchor below. Missing original bytes are an
unavailable prerequisite, not permission to fabricate a substitute. A fresh authorized
diagnostic pilot receives new identities and cannot be relabeled as historical Phase D.
The guide checks raw evidence and generated report hashes before presentation.

## Preserve evidence before moving or deleting a Codespace

Generated data, build trees and `results/validation/` are ignored by Git. A PR/clone
alone is not a backup of experimental or acceptance evidence. Preserve at least:

- The complete `results/validation/phase-d-benchmark-campaign/` directory, including
  all nested native/receipt/oracle/journal/export/build-provenance files and its
  original `audit-sha256.json`. Trusted inventory SHA-256 is
  `1e0d0c658410a53f3a5824369b9c6b0a1dd4e60bb95add79a2cd83f81cc96f06`.
- Original published Phase 5 downloads/archives/sidecars and provenance under
  `results/validation/phase5-recovered-github-20261106/`. These are distinct from
  particular still-missing older local-run copies, which remain unverified.
- The retained A–G acceptance directories, command receipts/logs, inventories,
  archive/sidecar pairs, native controls and generated analysis. Phase G evidence is
  `results/validation/phase-g-final-acceptance/`; its final `audit-sha256.json`
  inventories the retained bytes. Do not overwrite older inventories or failed logs.

No transfer/upload/delete is performed by this handover. Choose an explicitly
authorized storage destination outside an ephemeral Codespace before relying on
long-term retention. Verify archive sidecars and complete inventories after transfer
with the copied trusted offline kit; it needs no checkout/venv/network/subprocess.
A matching digest establishes integrity/identity reconciliation, not authenticated
producer evidence. Do not execute archived runners during verification.

The original campaign remains 104 planned, 0 executed. Preserve canonical hashes:

- Plan: `f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24`
- Manifest: `f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a`

Historical Phase D has two selected/attempted/completed/verified diagnostic trials,
both observed_interference, timing null and zero scientific timing samples. Phase E
report generation is byte-reproducible from verified original input and current
matching code/pins; it reports statistics unavailable, not zero runtime. No performance
confidence interval or multicore speedup is supported. Later command-validation
fixtures, regression smoke and synthetic numerical tests are separate scopes and
must never increment original or Phase D historical completion/replication counts.

## Recovery and maintenance guidance

Reverify recipe/hash identity before replay. Treat process success, integrity,
correctness, lifecycle completion and scientific eligibility as different decisions.
Inspect `execution_status` even when `verify-pilot` exits zero. Unknown GO, incomplete
publication, failed/interrupted/unresolved attempts, stale ownership and repeated
resume attempts must remain fail-closed. Resume requires explicit execute/resume
and renewed observation authorizations, verified immutable original completions and
only never-launched pending work in one fresh child attempt. Do not automatically
retry or rewrite completed evidence.

For future changes, keep public headers/implementation/CLI/orchestration separate,
C++17/OpenMP target-scoped flags and pinned dependencies unchanged unless separately
authorized. Preserve uint32 graph limits, uint64 infinity/overflow invariants,
transaction rollback and external-serialization requirements. Add regression tests
only for concrete uncovered defects; never change goldens, profiles or timeouts to
hide failures. Run the required matrix, retain failures, distinguish fresh execution
from historical records and obtain authorization for scope/dependency changes.

The final TSan capability check uses the existing race-free atomic control with
default layout, no suppressions or system/toolchain changes. It fails at runtime
startup with unexpected memory mapping. TSan acceptance remains unmet; passing
functional/OpenMP tests or ASan/UBSan/LeakSanitizer cannot establish race freedom.
The earlier work_ warning retains its historical LIKELY TOOL/RUNTIME LIMITATION
classification. Do not adopt unapproved layout/runtime workarounds as acceptance.

## Future scientific qualification and release boundary

A future request would need a genuinely authorized full executor and scientific
admission adapter, qualified/compatible build/runtime/hardware evidence, actual
eligible timing observations and justified independent experimental units. CPU
requests, affinity, quotas, snapshots and arbitrary session labels cannot establish
exclusive physical cores, stable isolation or independence. The accepted Phase D
CPUs are visible SMT siblings on one core and resource counters are shared.
Ordered updates/warmups are not independent replications. Numerical bootstrap
primitives do not supply missing experimental evidence or guarantee CI coverage.

These are nonblocking limitations for this accepted Codespaces-constrained software
handover, but remain blockers to scientific performance claims. Release-readiness
means ready for a final review PR of this bounded deliverable, not a GitHub release,
tag, merge, deployment certificate, race-freedom proof or publishable speedup. No
push/PR/merge/tag/release is performed. Preserve the clean local commit and stop;
any publication, deployment or additional experimental work needs a new request.
