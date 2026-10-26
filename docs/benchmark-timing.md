# Phase 5B-3B reproducible timing contract

This implements the approved 5B-3A design with its 5B-3B refinements. It collects
raw observations and verification evidence only. No statistics, speedups,
calibration, algorithm changes or scaling conclusions are included. Codespaces
runs and sanitizer observations are harness validation, not performance evidence.

## Commands

Generate a new workload directory if needed, then run the orchestrator:

```sh
python3 benchmarks/python/generate.py generate --spec benchmarks/configs/chain-v1.json --output data/generated/chain-v1
python3 benchmarks/python/run.py run --config benchmarks/configs/timing-smoke-v1.json --runner build/release/dynagraph_bench --output results/raw/timing-smoke
python3 benchmarks/python/run.py validate --input results/raw/timing-smoke/records.jsonl
```

The experiment output directory must not exist. The manifest path in configuration
is relative to the configuration file. A complete example is checked in at
benchmarks/configs/timing-smoke-v1.json. Its exact fields are schema_version
(integer 1), manifest, timing_mode, blocks, order_seed, delta, threads, no_effect,
timeout_seconds and optional warmups (default "1"). All numeric fields except
schema_version are canonical unsigned decimal strings. Unknown/duplicate fields,
leading zeroes, signs, fractions and overflow are errors. Required positive blocks
are divisible by four and <=400; warmups are 0..100; workers 0..64; delta
1..UINT64_MAX; timeout is 1..3600 seconds per subprocess; seed is uint64.
Timing modes are full-trace and per-update. No-effect modes are shared_fast_path
and execute_selected. Source is taken from the verified manifest; all four
policies use the same delta, workers, source and no-effect mode. Heuristic defaults
4096/32/65536 remain unchanged and are explicitly recorded. No tuning interface
is added. Worker request 0 retains the runtime-default semantics.

The single-trial C++ interface is also available:

```sh
./build/release/dynagraph_bench time --graph data/generated/chain-v1/graph.txt --trace data/generated/chain-v1/trace.txt --source 0 --policy incremental --delta 16 --threads 2 --no-effect shared_fast_path --timing-mode per-update --warmups 1
```

It shares verify's six required graph/trace/source/policy/delta/threads options.
--timing-mode is required; --warmups defaults to 1. --verification is forbidden
for time. Optional --run-id, --block-id and --trial-id are uint64 decimal strings
(default 0). Optional --graph-sha256, --trace-sha256, --executable-sha256 and
--configuration-sha256 are lowercase hex digests copied as user-supplied identity
metadata. Missing digests are null. C++ never verifies those hashes or claims
Python integrity/preflight completion. The orchestrator supplies and checks them.
Direct worker JSONL is not a completed experiment dataset.

## Architecture and timing boundaries

Production engine/storage/SSSP implementations are unchanged. Existing verify CLI,
JSON schema 1, per-update checks, counters and failure behavior remain available.
Its parser and independent oracle are reused through workload.hpp; preparation
and final-state checking are exposed by replay.cpp. timing.hpp contains the
injectable timing loop; timing.cpp handles warm-ups, clocks, final checks and
worker JSONL. run.py handles experiments; experiment_records.py validates schemas,
schedules, worker protocols and complete evidence directories.

Before timing, the C++ worker parses the same bounded canonical v1 formats and
validates the entire ordered expected-old-weight ledger, including edge existence,
endpoints and nonincrease. It owns separate initial/final edge records. Empty
traces are rejected. Graph/trace byte/count quotas remain those of Phase 5B-1.
It makes 1024 back-to-back clock probes outside timing, then performs warm-ups.
Every warm-up initializes a new engine from the initial graph, replays the whole
trace, verifies final topology/weights and fresh reference distances (with eligible
Bellman-Ford), then destroys the engine. Warm-up records have phase=warmup and no
durations. A separate fresh engine is constructed for measurement.

Full-trace mode makes exactly one start/stop clock pair around the complete loop.
Inside are immutable-record access, loop control, argument conversion and the
public AdaptiveSSSPEngine::decrease call. Its request validation, policy choice,
shared fast paths, algorithm work, OpenMP synchronization, allocations, commit,
result construction and temporary teardown before return are included. The caller
discards scalar results. No caller allocation, ledger mutation, logging, oracle,
result aggregation or per-update clock call occurs inside this interval. Engine
allocations are part of the operation and intentionally remain included.

Per-update mode reads the prepared record, timestamps immediately before/after
the same public call, then stores the pair in preallocated storage. Exactly one
sample is retained per successfully completed update. On a failed latency trial,
completed prefix samples are diagnostic only and the entire trial is invalid. Engine state
progresses in trace order. Between-call clocks/storage perturb subsequent cache
and scheduling conditions; their summed durations are never emitted as full-trace
time. Run the modes in separate experiments, never mix their datasets.

Both modes exclude loading, semantic prevalidation, initialization, warm-ups,
reference computation, comparisons, output, serialization and engine destruction.
Metrics and per-call overrides are disabled. Policy fast-path behavior is unchanged;
equal requests always bypass, even with execute_selected.

After timing, while the measured engine exists, a separate graph is constructed
from the independent final ledger. Every offset, destination and weight is compared.
Fresh sequential Dijkstra recomputes every distance, including infinity. Independent
synchronous Bellman-Ford additionally checks V<=128/E<=4096. Success requires all
checks. This is an actual timed-engine final-state check, not per-update oracle
verification. The separate full verify preflight provides per-update correctness
evidence from its own execution.

## Clock contract

Clock is std::chrono::steady_clock, required steady with integral ticks fitting
int64. Elapsed differences are checked for backwards readings, formed without
signed subtraction overflow and stored as uint64 decimal strings. Preserve period
numerator/denominator in seconds per tick. Nanoseconds are rounded down by checked
integer arithmetic; overflow (including unsupported intermediate conversion) fails
rather than wraps. No floating-point time is canonical. No overhead subtraction,
zero clamping or filtering occurs. The 1024 probe tick deltas are raw diagnostics,
not an exact overhead correction. The nominal tick period is not measured resolution.
The testable loop accepts a fake clock independently of probes and initialization.

## Python experiment protocol

A new output directory receives bounded copies of graph.txt, trace.txt and
manifest.json plus a snapshot of the executable. Python validates SHA-256,
manifest/source/count/seed consistency, independent ledger replay/final hash and
exact recipe regeneration with the existing verifier. It saves that evidence.
Configuration identity is SHA-256 of canonical normalized configuration JSON,
including the explicit/default warmup count. Graph/trace identities come from the
verified bundle; executable identity is computed over the staged executable.

Full C++ verify runs for every policy with the exact intended settings. It must
exit 0, match configuration and oracle counts, and expose final weights whose
canonical graph hash matches the manifest. Stdout, stderr and hashed exit evidence
are preserved. Timed trials start only after all four preflights succeed.

Each trial starts a fresh process, executes its warm-ups and one measured trace,
then independently verifies the timed engine's final state. Trials run sequentially.
Artifact and staged-executable hashes are checked before/after each preflight/trial
and at run completion. Python validates worker schema, sequence, identities,
configuration, warm-ups, sample counts/conversions and final checks before merging
its output into records.jsonl. Worker data is buffered/written outside timing.
Subprocess timeout includes preparation, warm-ups and final checks, not just timing.

A single Python writer emits LF-terminated compact JSONL, flushing and fsyncing
each record. Child stdout/stderr and exit evidence live beside it; retain the
whole directory. Missing evidence after a crash invalidates the dataset even if
some JSONL survives. A failed output medium may prevent failure records; absence
of terminal success is never success. No overwrite, resume or implicit retry exists.

## Deterministic order

Canonical policy labels start as [dijkstra, delta-stepping, incremental, heuristic].
Seed the existing SplitMix64 with order_seed. For indices 3,2,1 in descending order,
draw j=below(index+1), then swap labels[index] and labels[j]. Map labels A..D to
rows [A,B,D,C], [B,C,A,D], [C,D,B,A], [D,A,C,B]. For zero-based block b, choose row
(b%4 + seed%4 + (b//4)%4)%4. Thus every four-block group is position-balanced and
contains each ordered adjacent policy pair once. The whole expanded schedule and
version balanced-four-splitmix64-fisher-yates-v1 are recorded before execution.
For seed 0, shuffle draws are [3,0,1]. No platform RNG or hash chooses order.
The random uint64 run ID identifies a run and does not affect schedule generation.
Block IDs and repetition IDs coincide; trial ID is 4*block+policy_position.

## JSONL schema 1

All records have schema=dynagraph-timing-jsonl, schema_version=1, record_type,
run_id, sequence, block_id, trial_id, policy, graph_sha256, trace_sha256,
executable_sha256 and configuration_sha256. Global contexts use null block/trial/
policy fields. IDs, counters, seeds, clock periods and durations are canonical
uint64 decimal strings; booleans stay booleans. Schema version is the integer 1.
Unknown/duplicate keys and malformed numeric fields fail validation. Digests are
64 lowercase hex characters (or null only for unavailable direct-worker identities).

| Type | Additional fields |
| --- | --- |
| run_config | configuration, schedule, manifest_sha256, isolation, schedule_version |
| environment | metadata, source, delta, requested_workers, no_effect, heuristic, timing_mode, vertices, edges, updates, external_integrity, external_preflight, identity_origin |
| verification | scope, success, per_update_oracles, reference_recomputations, bellman_ford_checks |
| clock_probe | clock, is_steady, period_num, period_den, method, ticks (1024 deltas) |
| block_start | order |
| trial_start | repetition_id, policy_position, phase |
| warmup_end | phase, warmup_index, success |
| trial_measurement | phase, update_index=null, elapsed_ticks, elapsed_ns |
| update_latency | phase, update_index, elapsed_ticks, elapsed_ns |
| trial_end | success, updates_executed, sample_count |
| failure | category, message, update_index (nullable) |
| block_end | success |
| run_end | success, blocks_completed |

Completion is validated against the complete evidence before run_end success is
written. Public/default validation always requires the actual terminal line.

Global order: run_config, host environment, four external_full_preflight
verification records, then scheduled blocks, then run_end. Each block starts
with block_start, contains four trial_start/worker sequences, then block_end.
A successful worker sequence is environment, clock_probe, W warmup_end records,
one timed_final_state verification, one trial_measurement or N update_latency
records, and trial_end. Parent assigns contiguous global sequence values; raw
worker files preserve their independent sequences starting at zero.

The completion validator rechecks schemas, identities, schedule, exact transitions,
preflight evidence, staged workload/executable, worker evidence bytes and successful
exit hashes. It requires exact sample counts, successful final checks and all
terminal records. Missing/truncated records, extra trials or mismatched evidence
fail. Durations alone are not valid results. Configuration and records must remain
consistent with evidence; this is integrity checking, not cryptographic authentication
of a producer. Validation performs no statistical analysis.

## Metadata and limitations

Each metadata observation has value, origin and source. Origin is observed,
build_recorded, user_supplied or unavailable; unavailable values are null with a
source explaining the limitation. Python records CPU model, host-visible logical
count, process affinity, cgroup v2 namespace-root quota/cpuset where readable, OS,
kernel, working-tree revision/status and allowlisted inherited OpenMP settings.
Cgroup v1 or non-root hierarchies are not resolved; those values can be unavailable
or only describe the exposed namespace-root view. No physical-core or isolation
claim is inferred from these observations.

CMake records compiler ID/version/path, CMake version, build type, flags, declared
sanitizer status and configure-time Git revision/dirty state. These are configure-
time facts; executable SHA-256 identifies the actual snapshot. Dirty source content
is not archived, so preserve the source diff separately for independent rebuilding.
No time macros or host data enter workload goldens. Worker records compiled OpenMP
specification, runtime max-thread/dynamic/thread-limit settings and unavailable
runtime-library version/actual team size. omp_get_max_threads and requested workers
are not actual executed team observations. Timed calls keep optional metrics off.
Externally injected instrumentation may not be detectable from recorded flags;
none_declared is not proof of absence. Sanitizer records are validation only.

Default warm-ups warm the policy/runtime only if the trace actually executes those
paths. Shared bypasses or heuristic choices may avoid OpenMP entirely. Process
isolation reduces allocator/history carryover, but cannot ensure cold caches,
stable CPU frequency, no scheduler interference, equal NUMA placement or thermal
conditions. No automatic affinity/frequency changes or cache flushing is performed.
Use controlled dedicated hardware before performance or multicore-scaling claims;
the two-logical-CPU Codespace is a harness test environment. Maximum-quota timing
experiments, peak RSS and cross-platform clock behavior remain unverified. The
completion validator currently loads JSONL in memory; large experiment outputs
can require substantial memory and disk space. Worker stdout is capped at 128 MiB
when read by the orchestrator.

## Failures and review gate

Categories include cli_validation, artifact_validation, trace_validation,
initialization, execution, graph_mismatch, distance_mismatch, metadata_mismatch,
resource, incorrect_configuration, invalid_artifacts, preflight_verification_failure,
final_oracle_mismatch, clock_failure, artifact_changed, worker_failure, timeout,
interrupted, protocol_failure and output_failure. Failures stop immediately, preserve
evidence and exit nonzero. No failed trial is replaced or reordered. Interrupted
runs without successful terminal records are incomplete. Worker failures can leave
partial raw evidence; their duration records are never accepted. Entire failed
runs are rejected rather than silently salvaging earlier blocks. Invalid config
or an existing destination can fail before an experiment directory is created.

Input stability is assumed during each hash/read interval; there is no defense
against a hostile writer changing and restoring bytes. Shared libraries are not
snapshotted. No complete machine-image or power-loss transaction guarantee exists.

Stop after Phase 5B-3B verification and review. Phase 5B-4 and later work remain
unapproved; no speedups, policy tuning, statistics or performance claims are added.

## Actual local smoke completion example

This is the terminal record from the recorded local harness smoke run. It is
accepted only with the preceding records and evidence directory:

```json
{"block_id":null,"blocks_completed":"4","configuration_sha256":"385e416b49a123634d86c49cec02947749ff90bd5ebd3976e52ddd0db4fb66ad","executable_sha256":"84ab1106bc1bca003c47cd50bd3742b230edc0f35cb25a7ac739f55bbad30b3d","graph_sha256":"e7338d8f282737a360ae0f65fd731f7c576187e624e5fb94904246a08336ea6c","policy":null,"record_type":"run_end","run_id":"14945857020754390271","schema":"dynagraph-timing-jsonl","schema_version":1,"sequence":"126","success":true,"trace_sha256":"5e2355594505cdc6536fe11de6fd7ba158578105715c2b9b32445925e72c9d38","trial_id":null}
```
