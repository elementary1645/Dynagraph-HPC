# Phase 6B-1 campaign foundation

Phase 6B-1 implements planning and read-only hardware qualification, not an
experiment executor. The user's Phase 6B-1 authorization supersedes the older
Phase 6 deferral for this subphase only. Phase 5C is merged at 8b05c2b; hosted
completion is supplied by the user, not newly established by these local checks.
Historical Phase 5 documents/results keep their original meaning. No performance,
race-freedom, or ThreadSanitizer acceptance claim follows from this work.

## Commands

Run from the repository root. No command executes the benchmark or changes
hardware placement. JSON goes to stdout; errors go to stderr. The caller chooses
whether to retain output in a new location. There is no run, resume or retry command.

```sh
python3 -B benchmarks/python/campaign.py validate --plan benchmarks/configs/campaign-development-v1.json
python3 -B benchmarks/python/campaign.py expand --plan benchmarks/configs/campaign-development-v1.json
python3 -B benchmarks/python/campaign.py inspect
python3 -B benchmarks/python/campaign.py inspect --executable build/release/dynagraph_bench
python3 -B benchmarks/python/campaign.py admit --plan benchmarks/configs/campaign-development-v1.json --hardware results/raw/hardware.json
python3 -B tests/test_campaign.py
```

For actual runtime-mapping evidence, `inspect --executable FILE --pid PID` may
read an **already-running** matching executable's Linux procfs mappings. This
never starts or attaches a debugger to the target. Do not start a benchmark for
this foundation's validation. Permission failures/missing mappings remain
unavailable evidence. Without --pid, ELF DT_NEEDED and the compiler's candidate
libgomp are only hints and cannot satisfy scientific runtime admission.

Exit codes: 0 valid plan/manifest/inspection or qualified/development admission;
1 scientific hardware rejected (diagnostics remain in JSON); 2 invalid input,
unsupported schema or collection I/O failure. Development exit 0 does not confer
scientific eligibility. The example has explicit zero placeholder build digests
and a two-logical-CPU development allocation; replace them with actual evidence
in a separately reviewed scientific plan. It is not an experiment matrix.

## Campaign schema 1

All listed keys are required, with exact fields at each schema level. There are
no scientific defaults. Integer fields are JSON integers (bool/floats rejected),
except the embedded unchanged v1 recipe's decimal-string seeds. Duplicate JSON
keys, nonfinite/fractional numbers, invalid UTF-8, excessive nesting and unknown
fields fail. Labels are 1..64 ASCII identifier characters; hashes are lowercase
64-character SHA-256; revision is a full 40-character Git object ID.

| Field | Contract |
| --- | --- |
| schema_version, campaign_id, panel | Version 1, researcher-assigned campaign ID, explicit panel ID |
| measurement_level, timing_mode | `engine-update-service-v1`; `full-trace` or `per-update` |
| workloads | 1..128 objects: id, complete recipe, recipe_sha256, graph_sha256, trace_sha256, bundle |
| configurations | 1..64 objects: unique id, workers 1..64, delta 1..UINT64_MAX; duplicate settings rejected |
| policies | Exactly dijkstra, delta-stepping, incremental, heuristic in canonical order |
| no_effect | Explicit shared_fast_path or execute_selected |
| heuristic | Exact existing 4096/32/65536 thresholds, with named fields |
| sessions | 1..32 unique session labels, in declared order |
| blocks | 4..400, divisible by four; repetitions per policy per cell/session |
| warmups, diagnostics | 0..100 warmups per measured worker group; 0 or 1 separate diagnostic per policy/cell/session |
| order_seed, order_version | uint64 seed; campaign-balanced-four-v1 |
| build | revision, Release build_type, executable relative path, executable_sha256, compiler_sha256, openmp_sha256, flags_sha256, uninstrumented=true |
| hardware | mode, allocated_cpus, min_physical_cores, allow_smt, allow_virtualization, min_available_memory_bytes, require_frequency_evidence, exclusive, reservation |
| limits | max_trials (<=100000), timeout_seconds (1..3600), max_memory_bytes (<=2^50), max_output_bytes (<=128 MiB) |
| expected_evidence | Exact ordered list in the example: plan.json, trial-manifest.json, hardware.json, admission.json, records.jsonl, stdout, stderr, exit.json, sha256.json |
| comparisons | Explicit configuration references; only worker-scaling with equal delta and differing workers |

A workload recipe is validated with existing `workloads.validate_spec`, includes
all graph/trace/weight/source parameters and four seeds, and must have a nonempty
trace. Its id matches recipe.workload_id, and the canonical recipe digest must
match recipe_sha256. Duplicate workload content identities are rejected. No
recipe generation, artifact read or benchmark execution occurs during planning.
Graph/trace hashes are **expected** identities; their correspondence to the recipe
must be verified by existing artifact regeneration before future execution. This
foundation does not falsely certify nonexistent bundles or compiled flags.

Bundle/executable references must be canonical relative POSIX paths with no
parent traversal, empty/dot components, absolute paths, backslashes, colons or
control characters. Planning never opens those references. A future executor
must also enforce containment against symlink aliases when staging files.
The CLI input paths are explicitly chosen local files; no embedded command,
plugin, shell expression or import path is accepted.

Serialization reuses sorted-key compact LF-terminated `canonical_json`. The plan
hash is SHA-256 of validated canonical bytes, independent of source JSON key order
and whitespace; array order is intentional and hashed. Campaign IDs are not a
global registry: the plan hash disambiguates reused labels. Version 1 permits a
bounded workload/configuration cross product, not an arbitrary executable matrix.

## Trial manifest

The envelope contains schema=dynagraph-campaign-trials, schema_version=1,
campaign_id, plan_sha256, planning_only=true, admission_required=true,
order_version and trials. Each row includes:

- trial_id (SHA-256 of plan hash and stable semantic coordinates), sequence;
- session, workload_id, configuration_id, policy, workers, delta;
- phase=warmup/diagnostic/measured, block and policy_position;
- worker_group, pairing_id and configuration_pairing_id.

Every trial references an immutable hashed plan rather than duplicating its build,
resource and workload requirements. Measured/warmup rows with one worker_group
belong to one future worker lifecycle: fresh engine warmups then a fresh measured
engine, preserving existing timing semantics. These are planned events, **not**
claims that each warmup should become a separate subprocess. Diagnostic groups
use block=-1 and are distinct from measured groups. Existing four-policy schedule
rows are position-balanced and balance ordered adjacent pairs in every four
blocks. Within each session, workload/configuration cells use seeded descending
Fisher-Yates with SplitMix64. Each cell consumes a fresh uint64 schedule seed.
Outer cells are randomized, not asserted to be position-balanced across sessions.

pairing_id joins the same workload/session/repetition across configurations;
configuration_pairing_id also fixes configuration for policy comparison. Neither
permits joining different timing modes, fast paths, delta, builds or workloads.
Those remain fixed at campaign level or checked by explicit comparisons. Planning
is not a statistical analysis engine.

Expansion is checked before constructing rows:

`workloads * configurations * sessions * 4 * (diagnostics + blocks * (1 + warmups))`

must fit both declared max_trials and the global 100000-event ceiling. Input is
bounded to 1 MiB, depth 32 and 50000 JSON nodes. CPU lists/ranges are separately
bounded. Declared future runtime/memory/output budgets are recorded, **not enforced
by a nonexistent executor**. No existing runner timeout changes.

## Hardware report and admission

Every observation has value, source and origin=observed/unavailable. Unavailable
values are null. User declarations are separate in the plan/admission output;
they never become observed exclusivity facts. The report records CPU model,
online logical CPUs, package/core/sibling IDs, NUMA CPU lists, effective affinity,
visible cgroup v2 ancestors, quota fractions, cpuset intersection, memory headroom,
MemAvailable, OS/kernel, virtualization/container indicators, compiler identity,
OpenMP library identity, executable digest, placement tools and cpufreq data.

Unified membership is resolved against `/proc/self/mountinfo`'s mount root, not
assumed to live at the namespace root. Every visible ancestor contributes CPU
quota, effective cpuset and memory limits/current usage. Missing controllers,
cgroup v1, escaped/unsupported mount mappings and hidden ancestry remain explicit
limitations. Unlimited visible quota never establishes ownership. Memory is a
point-in-time minimum of MemAvailable and visible ancestor headroom.

Scientific qualification requires:

- An explicit exclusive reservation declaration with a nonempty reference.
- Effective process affinity exactly matching sorted unique allocated CPUs.
- Consistent per-CPU topology, enough distinct package/core pairs, and no SMT
  sibling allocation unless explicitly permitted.
- Worker counts compatible with allocation/core requirements and every observed
  ancestor quota; allocated CPUs contained in the effective cpuset.
- Sufficient memory, with summaries consistent with recorded ancestor data.
- Allowed virtualization indicators; matching compiler, executable and runtime
  digests; runtime mapped by a matching observed process, not merely a candidate.
- Governor evidence for every allocated CPU when required.

Admission output binds the decision to campaign_id, canonical plan_sha256 and
canonical hardware_sha256; it cannot be interpreted as a result for another plan.
Missing or contradictory required observations reject scientific qualification.
Missing declarations/invalid plans reject both modes. Development plans explicitly
claim no exclusive reservation and can qualify for harness checks despite missing
scientific observations; every failed scientific check remains visible and
scientific_performance_allowed=false. No admission result authorizes multicore
scaling claims; multicore_scaling_claims_allowed is always false in this phase.

Reports can be copied or fabricated: this is qualification **on supplied evidence**,
not authenticated hardware attestation. Topology may itself be virtualized; CPU
model/count never establish physical ownership. Compiler identity is the inspected
host compiler, not proof of how an executable was built. Recorded revision, flags
hash and uninstrumented requirement still need a separately verified build record.
PID mapping observation is non-atomic and read-only; matching executable and stable
maps/start identity and mapped file device/inode checks reduce accidental mismatch, not hostile-host attacks. Runtime
support is currently Linux ELF/libgomp only. No binary under inspection is run;
fixed g++/readelf introspection commands use trusted host tools, without a shell.

## Acceptance and remaining work

Acceptance requires deterministic plans/hashes/schedules, strict rejection and
bounds, positive and negative synthetic hardware qualification, development-only
behavior on this host, unchanged legacy gates/goldens/analysis/archives and no
production code/timing/heuristic/dependency changes. New tests remain outside CTest,
keeping the existing 31-test acceptance profiles unchanged. The only CI change adds
`python -B tests/test_campaign.py` to the existing standalone archive/diagnostic
regression step in Debug/Release jobs, so the new contract is continuously checked
without adding acceptance tests or changing sanitizer jobs.

Future reviewed subphases must implement execution/staging, resource enforcement,
build-evidence linkage, observation freshness and reservation verification,
actual-team telemetry, controlled collection, additional measurement levels,
statistical inference and independent replication. No full experiment matrix,
benchmark results, speedups, heuristic tuning or native batch repair is included.
