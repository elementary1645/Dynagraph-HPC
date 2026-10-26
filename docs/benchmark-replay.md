# Correctness-checked replay (Phase 5B-2)

`dynagraph_bench` links the existing library and implements correctness-only
execution. `apps/dynagraph_bench.cpp` handles CLI/output; the separate
`src/benchmark/replay.cpp` handles canonical parsing, ledger, oracles and replay.
Production storage, Dijkstra, delta-stepping, repair and adaptive implementations
are unchanged. The `verify` command collects no clocks or measurements. Separate Phase 5B-3B
`time` and Python orchestration are specified in [benchmark-timing.md](benchmark-timing.md).

## Invocation and integrity boundary

```sh
python3 benchmarks/python/generate.py verify --manifest data/generated/chain-v1/manifest.json
./build/debug/dynagraph_bench verify --graph data/generated/chain-v1/graph.txt --trace data/generated/chain-v1/trace.txt --source 0 --policy incremental --delta 16 --threads 2 --no-effect shared_fast_path --verification full
```

Run `generate.py generate --spec benchmarks/configs/chain-v1.json --output
data/generated/chain-v1` first if a new bundle is needed; the output directory
must not exist. Run Python verification again after any artifact modification.
This prerequisite checks manifest schema/versions, both artifact SHA-256 digests,
the trace's initial-graph digest, manifest counts/source/seeds, endpoint-ledger
replay, canonical final-graph SHA-256, and exact regeneration of the declared
configuration and manifest. It rejects artifact symlinks. These are consistency
checks, not producer authentication.

The C++ executable does **not** implement SHA-256, read manifests, regenerate
workloads, or attest that Python ran. It validates digest syntax only. A
well-formed but false graph digest or an altered trace identity must be rejected
by the Python prerequisite; C++ alone cannot detect those identity failures.
Result fields explicitly mark this boundary. Use the manifest beside the result
as the graph/trace identity and provenance record. Paths identify the files opened
by C++; they are not content digests. Inputs must remain stable between the two
commands and during replay. No concurrent-writer defense is provided.

`verify` requires exactly one of each option `--graph FILE`, `--trace FILE`,
`--source N`, `--policy NAME`, `--delta N`, `--threads N`. Policy names are
`dijkstra`, `delta-stepping`, `incremental`, `heuristic`. Delta is an unsigned
integer in 1..UINT64_MAX for every policy; worker request is 0..64, with 0 using
the OpenMP runtime default (which may exceed 64). Actual teams may be smaller
than requested. The upper bound of 64 is a runner input quota, not a tuning
recommendation. No actual-worker measurement is reported.

Optional `--no-effect shared_fast_path|execute_selected` defaults to
`shared_fast_path`. Optional `--verification full` defaults to `full`; all other
levels are rejected. Unknown, missing, duplicate and empty required options,
signed/fractional/overflowed integers and leading zeroes are errors. Options may
appear in any order as separate option/value pairs. `--help` alone prints usage.
Output destination is stdout; redirect it to a separate result file if needed.
Input artifacts are opened only for reading.

All policies use `AdaptiveSSSPEngine::initialize` and `decrease`, with no per-call
override. Forced policies retain the existing engine semantics: equal requests
always bypass, shared no-effect decreases bypass, and execute_selected dispatches
strict decreases. The heuristic uses unchanged default thresholds; the runner
does not expose threshold tuning. Initialization uses Dijkstra for every policy.

## Parsing, limits and independent verification

The graph has no embedded version header: it uses the canonical Phase 5B-1
edge-list format. The trace declares schema 1, dynagraph-trace-v1,
dynagraph-graph-v1 and splitmix64-v1. The parser accepts only exact header order,
single ASCII spaces, canonical decimal integers and LF-terminated lines. Seeds
fit uint64, weights fit uint32. Sorted unique graph endpoint pairs define stable
CSR edge identities. Trace records contain endpoints, not a separate edge-ID
field. Declared record counts must match exactly; blanks, CRLF, missing LF,
extra fields/records, unsupported versions and malformed fields are rejected.
CLI source must match trace source and be inside the graph.

Quotas match Python: V<=100,000, E<=500,000, updates<=100,000, graph<=32 MiB,
trace<=16 MiB. Readers bound bytes before parsing; counts are bounded before
count-sized allocation. Numeric parsing checks multiplication/addition before
performing them. Quotas keep vector indices, count increments and size arithmetic
within the supported host's size_t range. Allocation can still fail. These limits
bound input volume, not total oracle work, peak RSS or wall time. Full verification
of maximum-quota traces can be expensive; maximum-quota successful runs have not
been tested.

The reference ledger is an owned vector of original canonical `(u,v,weight)`
records, independent of engine storage and cached distances. Each record checks
consecutive index, endpoints, edge existence, ledger old weight, new uint32 weight
and nonincrease. Repeated requests use the ledger's most recent committed weight.
The ledger changes before the identical engine call. A failed run stops there;
it never resumes with a partially advanced ledger.

Initialization and each successful update construct a fresh CSR reference graph
from the ledger. All offsets, destinations and weights are compared with the
engine; fresh production sequential Dijkstra is then computed on this separate
graph and every distance compared. It is never seeded from engine labels.
Graphs with V<=128 and E<=4096 additionally use independent synchronous
Bellman–Ford over ledger records: each pass reads old labels and writes a copy,
stopping at convergence or V-1 passes. It calls no production algorithm and does
not traverse CSR. The unreachable label is UINT64_MAX; checked addition excludes
overflow/sentinel candidates. Under these quotas, simple finite paths are at
most 99,999*UINT32_MAX, strictly below infinity. Zero cycles terminate through
strict improvement; unreachable vertices remain explicitly compared.

After each update the runner checks returned old/new weights, outcome and exact
distinct improved-vertex count using consecutive independently recomputed labels.
It checks equal/shared-bypass decision metadata and the selected strategy/reason
for executed forced policies. Heuristic branch choice is covered by existing
engine tests; the runner verifies its resulting graph/distances without copying
the heuristic into another selector. No optional work counters are requested.

Only full verification is implemented. Every update executes and is checked;
the last per-update check verifies final state. For empty traces, the initial
check verifies final state. There is no duplicate final oracle evaluation.
Bounded/checkpoint mode is deferred and is not silently substituted.

## JSON schema 1 and failures

One compact JSON object plus LF is emitted. Consumers must preserve uint64
integer precision; unreachable distances are JSON null. Order is stable and
there are no host/time fields. Repeated calls with identical paths/options/input
produce byte-identical success records.

| Fields | Meaning |
| --- | --- |
| schema_version | 1 |
| success | Boolean overall correctness result; accept only with exit 0 |
| failure_category, message | `none` and empty on success; category/diagnostic on failure |
| failing_update_index | Zero-based parsing/replay update, or null for errors outside a record |
| graph_path, trace_path | Input identities by caller-supplied path; not verified hashes |
| declared_graph_sha256 | Copied trace metadata, empty if not parsed |
| identity_origin | Always `unverified_artifact_metadata` |
| integrity | Always `external_python_verifier_required`; never asserts prerequisite completion |
| policy, source, delta, requested_workers, no_effect | Requested execution configuration; partial/default values on CLI errors |
| verification_level | `full` (unsupported requested levels fail) |
| trace_entries | Declared count once parsed, otherwise 0; not a verified provenance claim |
| updates_executed | Successfully returned engine updates |
| updates_verified | Updates completing all state/oracle/metadata checks |
| reference_recomputations | Completed fresh Dijkstra evaluations, including initialization |
| bellman_ford_checks | Completed Bellman–Ford evaluations, including initialization |
| final_graph_verified, final_distances_verified | True only when the entire run succeeds |
| final_weights | Success only: independently verified weights in canonical edge order |
| final_distances | Success only: independently verified labels in vertex order |

For N successful updates there are N+1 reference recomputations, and N+1
Bellman–Ford checks for eligible graphs (otherwise zero). There are N verified
update checkpoints plus the initialization check; final state is included.
Final arrays let independent Python tests reconstruct canonical final graph bytes
and compare the manifest's final hash; the C++ runner itself does not hash them.

Stable categories are `cli_validation`, `artifact_validation`,
`trace_validation`, `initialization`, `execution`, `graph_mismatch`,
`distance_mismatch`, `metadata_mismatch`, `resource`, and `none`.
Artifact category includes syntax, counts, byte/count quotas and input I/O.
Trace category covers ledger transitions. Resource denotes bad_alloc.
Initialization failures execute no updates. Update failures stop at that index;
completed counters can be nonzero, but final flags stay false and final arrays
are absent. Parsing happens before initialization, so a later syntax error can
reject the whole trace before any updates; semantic ledger checks occur in order.
Failures exit 2 and write diagnostics to stderr plus a failure record to stdout.
Serialization/output failure also exits 2 and may leave incomplete stdout;
process-fatal/runtime/OS failures cannot promise a JSON record. A result consumer
must require a complete JSON object, `success:true`, and exit 0.

CTest's `benchmark_replay` runs standard-library Python integration tests against
the executable, all four policies and both no-effect modes, Python generation and
verification, independent final weights/distances, deterministic repetitions,
parser/CLI/ledger rejection and the explicit external integrity boundary. Existing
algorithm/fault-injection tests remain unchanged. This establishes correctness on
tested cases, not performance, race freedom or cryptographic authentication.
The existing verification contract remains unchanged. Stop at the Phase 5B-3B
review gate; Phase 5B-4 remains unapproved.
