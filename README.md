# DynaGraph-HPC

DynaGraph-HPC is a research project toward adaptive shortest-path computation on
dynamic graphs using C++17, OpenMP, CMake, and Python benchmark orchestration.
Correctness, measured performance, and reproducibility guide development.

## Current status

Phase 4B-2 adds deterministic heuristic selection over sequential Dijkstra, OpenMP
delta-stepping, and transactional incremental repair. One owning incremental
state remains current across strategy switches. Failed updates preserve graph,
distances, and caller metrics. Shared no-effect fast paths apply to every policy.
Tests compare all three with independent Bellman–Ford and exercise allocation
failures. Calibrated/learned selection, batch/parallel repair,
automatic delta tuning, and benchmarks remain planned work.
There are no performance results or speedup claims.

The approved initial graph scope is directed, fixed topology with nonnegative
integer weights. Incremental repair supports single-edge weight decreases only.
Storage permits any valid weight replacement; incremental handling of increases,
edge insertions/deletions, tombstones, and CSR compaction are deferred.

## Requirements

- GCC with C++17 and OpenMP headers/runtime
- CMake 3.21 or newer and Make
- No downloaded C++ testing framework or Python package is required
- Python is reserved for later benchmarking; it is not invoked by this build

GCC 13.3.0 and CMake 3.28.3 are available in the initial Ubuntu 24.04 environment.

## Build and test

From the repository root:

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --preset debug --output-on-failure
./build/debug/dynagraph_cli
./build/debug/dynagraph_cli --version
ctest --test-dir build/debug -R '^openmp$' --verbose

cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release --output-on-failure
```

Both presets select g++, C++17, OpenMP, and warnings as errors. The OpenMP test
requires a team of two threads, checks their participation and reduction result,
and prints the compiled OpenMP specification date. It is a correctness smoke
test and does not measure speedup.

An equivalent explicit configuration is:

```sh
cmake -S . -B build/manual -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON
cmake --build build/manual --parallel 2
ctest --test-dir build/manual --output-on-failure
```

GitHub Actions defines Ubuntu Debug/Release and ASan/UBSan builds and tests.
Hosted CI execution is separate from local verification and requires the workflow to reach GitHub.

## Layout and development

- include/dynagraph/ and src/: library API and CSR implementation; reserved modules
  for future instrumentation; dynamic/ contains repair and adaptive/ the forced engine
- apps/ and tests/: CLI and automated checks
- benchmarks/: future configuration and Python experiment tooling
- data/manifests/ and results/: provenance and generated experiment artifacts
- docs/ and paper/: design, research records, protocol, and future manuscript

See [architecture](docs/architecture.md), [experimental protocol](docs/experimental-protocol.md),
[research log](docs/research-log.md), and [engineering standards](AGENTS.md).
Each implementation phase requires approval before work begins. Phase 4B-2 is
implemented; Phase 4B-3 or Phase 5 requires explicit approval.

## Graph API and semantics

```cpp
#include "dynagraph/graph/csr_graph.hpp"
#include "dynagraph/graph/edge_list_io.hpp"

auto graph = dynagraph::CSRGraph::from_edges(4, {{0, 2, 7}, {0, 1, 0}, {1, 1, 3}});
for (const auto edge : graph.outgoing_edges(0)) {
    // edge.id, edge.destination, edge.weight; sorted by destination.
    (void)edge;
}
const auto previous = graph.replace_weight(0, 2, 4); // Returns 7.
(void)previous;
// Alternatively: auto graph = dynagraph::load_edge_list_file("graph.txt");
```

Graphs are directed, with IDs in [0, V). Self-loops, zero weights, disconnected
components, isolated vertices, and empty graphs are valid. Duplicate ordered
endpoint pairs are rejected. Topology stays fixed; mutation is serial.

Vertex IDs and weights use uint32_t; offsets/counts use uint64_t. Supported vertex
counts are 0 through 4,294,967,295, and weights 0 through 4,294,967,295. Actual graph
sizes are further limited by allocation/index bounds and available RAM. The
signed int64_t builder inputs allow negative values to be diagnosed before storage
conversion. Public arrays are const. Construction takes O(V + E log E), storage
is O(V+E), degree access is O(1), and edge lookup/replacement uses binary search.

## Edge-list input

```text
6 4
0 2 7
0 1 0
1 1 3
3 4 9
```

The first nonblank line declares V E; exactly E nonblank records follow, each with
zero-based source, destination, and weight. Tokens must be unsigned decimal
integers. Blank lines and ordinary ASCII whitespace are accepted; comments,
extra fields/records, missing records, signed numbers, and overflow are rejected.
Use `0 0` for an empty graph or `3 0` for three isolated vertices. Stream/file
loaders validate input and sort identically to the builder. See the architecture
document for full invariants, errors, limits, and iterator lifetimes.

## Optional local sanitizer verification

When GCC AddressSanitizer and UndefinedBehaviorSanitizer runtimes are available:

```sh
cmake -S . -B build/sanitize -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined
cmake --build build/sanitize --parallel 2
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir build/sanitize --output-on-failure
```

LeakSanitizer requires process inspection support; the initial sandbox blocked it.
The same instrumented suite passed outside the sandbox with leak detection enabled.

## Sequential shortest paths

```cpp
#include "dynagraph/algorithms/sssp.hpp"
auto result = dynagraph::dijkstra(graph, 0);
dynagraph::DijkstraMetrics counters;
auto measured = dynagraph::dijkstra(graph, 0, &counters);
```

`SSSPResult` owns `source` and a vertex-indexed `distances` vector. Distances use
uint64_t; `unreachable_distance` (UINT64_MAX) denotes unreachable vertices.
Invalid sources throw std::out_of_range. No predecessors are retained.
Queries are sequential and require no concurrent graph mutation. Updates of either
direction are supported through subsequent full recomputation.

```sh
./build/debug/dynagraph_cli sssp --input graph.txt --source 0 --algorithm dijkstra
```

For the six-vertex input above, output is:

```json
{"schema_version":1,"algorithm":"dijkstra","source":0,"distances":[0,0,7,null,null,null]}
```

Schema v1 is an object with integer `schema_version` equal to 1, string `algorithm`
equal to `dijkstra` or `delta-stepping`, integer `source`, and array `distances` with exactly V entries
in vertex order. Each entry is a nonnegative integer distance or JSON null for
unreachable. Consumers must preserve uint64 integers (JavaScript Number loses
precision above 2^53-1). No timing or counters are included. Required options may
appear in any order, exactly once; unknown options, malformed unsigned decimal
sources, missing values, invalid input, and invalid sources produce a stderr
diagnostic and exit 2. Success exits 0. Existing no-argument/help/version commands
remain available.

See architecture.md for the overflow proof, complexity, and exact metric definitions.

## Parallel shortest paths

```cpp
#include "dynagraph/algorithms/delta_stepping.hpp"
dynagraph::DeltaSteppingMetrics metrics;
auto parallel = dynagraph::delta_stepping(graph, 0, {16, 2}, &metrics);
// Omit the last argument to compile out event-counter updates.
```

`DeltaSteppingOptions` requires positive uint64 delta (including UINT64_MAX).
Its thread count defaults to 0 (the calling thread's OpenMP runtime default);
positive values request a team, negative values are rejected. The runtime may
supply fewer workers. Metrics report the actual team size. Invalid sources throw
out_of_range; invalid options throw invalid_argument. Allocation failures propagate
only after the team exits collectively; no incomplete result is returned.
The existing Dijkstra implementation and result type are unchanged.

```sh
./build/debug/dynagraph_cli sssp --input graph.txt --source 0 --algorithm delta-stepping --delta 16 --threads 2
```

For the six-vertex input above with an actual team of two:

```json
{"schema_version":1,"algorithm":"delta-stepping","source":0,"delta":16,"requested_threads":2,"actual_threads":2,"distances":[0,0,7,null,null,null]}
```

The common v1 fields and distance ordering are preserved. Parallel results add
integer `delta`, `requested_threads` (0 means default), and `actual_threads`.
`--delta` is required for delta-stepping; `--threads` defaults to 0. Both options
are forbidden with Dijkstra. Values must be unsigned decimal and fit their API
types; duplicate options are rejected. The CLI collects optional metrics to
report the actual team size, but emits no work counters or timing.

The implementation repeatedly closes each bucket over light edges (weight <=
delta), then scans heavy edges once per distinct vertex using final labels.
Workers update atomic distances and their own buffers; one coordinator owns all
bucket and work-container mutations between barrier-separated phases. Concurrent
independent queries on an immutable graph are supported; all graph mutations
must wait for every query using that graph to finish.

Checked additions discard walks above (V-1)*UINT32_MAX, a bound on every finite
shortest distance. Sparse buckets avoid allocation proportional to maximum
bucket index. A serial coordinator, barrier costs, atomic contention, repeated
light scans, and retained stale entries limit performance and memory capacity;
no speedup is asserted. Test settings and reproducibility details are in
[experimental protocol](docs/experimental-protocol.md).

## Transactional incremental shortest paths

```cpp
#include "dynagraph/dynamic/incremental_sssp.hpp"

auto graph = dynagraph::CSRGraph::from_edges(4, {{0, 1, 10}, {1, 2, 5}});
auto state = dynagraph::IncrementalSSSPState::initialize(graph, 0); // Owns a copy.
dynagraph::RepairMetrics metrics;
const auto update = state.decrease(0, 1, 2, &metrics);
// update: distances_repaired, old_weight=10, new_weight=2, vertices_improved=2.
// state.distances(): [0, 2, 7, unreachable_distance].
```

`initialize(CSRGraph, VertexId)` runs Dijkstra. The graph argument copies an lvalue
or consumes an rvalue. `from_result_checked(CSRGraph, SSSPResult)` validates source
and dimensions, recomputes Dijkstra, compares every distance, then adopts the result.
Checked adoption is not a shortcut around recomputation. Acquisition/initialization
can allocate; rvalue inputs may have been consumed if initialization throws.
There is no unchecked public constructor. The state cannot be copied, moved, or
rebound; C++17 factory returns use guaranteed copy elision.

The API exposes `source()`, `graph()` and `distances()` as scalar/const views.
Changing the original graph does not affect a state created from its copy.
Views retain their storage across updates and show the latest committed values;
they are not historical snapshots. Serialize every update against all access to
that state, including reads through existing views. Independent states own
independent storage; no mutable graph or distance accessor is exposed.

`decrease(uint64_t u, uint64_t v, int64_t new_weight, RepairMetrics* = nullptr)`
returns scalar `DecreaseResult {outcome, old_weight, new_weight, vertices_improved}`:

| Outcome | Meaning |
| --- | --- |
| unchanged_weight | Same weight, no graph write or propagation |
| weight_only | Strict decrease committed, no distances change |
| distances_repaired | Strict decrease committed, distances restored |

Invalid endpoints/nonexistent edges throw out_of_range. Negative/out-of-range
weights and increases throw invalid_argument. Every exception preserves the
existing state's graph, distances, and caller metrics; the state remains reusable.
Repair uses a deterministic min-heap, stale-entry checks, checked arithmetic, and
an undo journal. It evaluates a proposed weight without mutating the graph, then
commits that weight after propagation. No full distance copy, full mark clearing,
or full recomputation occurs in `decrease()`.

Zero cycles, self-loops, equal-cost alternatives, unreachable vertices, and wide
uint64 distances are supported. Strict improvements alone generate queue work.
Fixed topology and finite weights mean reachability cannot change. Only distances
are maintained, not paths/predecessors. Source changes require a new state.
Batch updates, increases, topology changes, parallel repair and concurrent access
during an update are unsupported. Incremental repair currently has no CLI command.

Optional per-call metrics are replaced only on success, not accumulated: strict
updates, unchanged requests, no-distance-change requests (including unchanged),
distinct improved vertices, edges, relaxation attempts (seed plus propagation),
successful relaxations, queue pushes/pops, and stale entries. Event increments
saturate with a flag. Omitting metrics compiles out event updates. No timings are
collected. See architecture.md for exact definitions, invariants and complexity;
large affected regions can cost as much as recomputation plus transaction overhead.

## Forced-strategy engine core

```cpp
#include "dynagraph/adaptive/adaptive_sssp.hpp"

dynagraph::PolicyConfig config{dynagraph::PolicyKind::always_incremental,
    dynagraph::NoEffectMode::shared_fast_path, {16, 2}};
auto engine = dynagraph::AdaptiveSSSPEngine::initialize(
    dynagraph::CSRGraph::from_edges(4, {{0, 1, 10}, {1, 2, 5}}), 0, config);
dynagraph::AdaptiveMetrics metrics;
auto first = engine.decrease(0, 1, 2, &metrics, dynagraph::Strategy::dijkstra);
auto second = engine.decrease(1, 2, 1); // Uses configured incremental strategy.
// Current distances: [0, 2, 3, unreachable_distance].
```

The engine owns exactly one authoritative IncrementalSSSPState. It is noncopyable
and nonmovable; factories construct direct prvalues using guaranteed C++17 elision.
Initialization uses Dijkstra for every policy. Graph lvalues are copied and rvalues
may be consumed even on initialization failure. Const source/graph/distance
accessors expose current state. No mutable accessor or public unchecked result
adoption exists. Engine operations and all view access require external
serialization; independently owned engines may execute concurrently.

Policy kinds are always_dijkstra, always_delta_stepping, always_incremental, and heuristic.
The optional per-call Strategy overrides the configured policy. Configuration also
sets delta (>0) and requested threads (>=0, 0 uses the runtime default); options
are validated even for nonparallel policies so a later override is safe. Invalid
enum values are rejected. Defaults are incremental/shared fast path/delta 1/runtime
threads, not calibrated performance settings. Existing fixed policies remain the
default; heuristic selection is opt-in. No cost model or timing instrumentation
is implemented.

Equal weights always return route unchanged/reason equal_weight with no backend.
Under shared_fast_path, a strict decrease whose checked seed cannot improve its
destination commits only its weight, returning route weight_only/reason
no_distance_effect. Both routes have no selected strategy and no backend work
metrics. This shortcut is shared by all policies, including forced overrides.
With execute_selected, strict no-effect requests use route execute and the selected policy's reason:
full strategies recompute, while incremental retains its intrinsic seed check.
All executed calls report their selected strategy even when distances are unchanged.

Full recomputation copies the graph temporarily, applies the proposed weight,
executes the chosen backend, checks source/size and all distance monotonicity,
reachability and finite bounds, and counts improvements. It then commits the
authoritative weight and swaps the completed distances. All allocating work,
including delta result/metric preparation, precedes that commit. On a recoverable
C++ exception the old state and caller metrics are unchanged; no fallback strategy
is silently retried. Process-fatal runtime failures are outside this guarantee.

After recomputation, distance element pointers/iterators are invalidated: reacquire
them after successful updates. Current const vector views expose the new values,
not historical snapshots. Standalone IncrementalSSSPState::decrease retains its
existing stable-storage guarantee.

AdaptiveUpdateResult contains the ordinary DecreaseResult plus DecisionResult
(route, optional selected strategy, reason). Optional AdaptiveMetrics are scalar
aggregates, published only on success. work_collected is false on bypasses. Only
the executed backend's fields are populated; others reset. Delta work is summed
with saturation from its per-thread metrics, and actual_threads is an optional
value present only when that work was measured. No full distance copy is returned.
Staging adds O(V+E) copying and O(V) result checking to full strategies, with a
temporary duplicate graph/result. These costs must be included in later fair
comparisons; no performance advantage is claimed.

## Deterministic heuristic selection

```cpp
dynagraph::PolicyConfig config;
config.kind = dynagraph::PolicyKind::heuristic;
config.parallel = {16, 2}; // Explicit requested budget for the parallel branch.
config.heuristic = {4096, 32, 65536}; // Uncalibrated initial hypotheses.
```

HeuristicConfig contains unsigned edge-count/degree thresholds. In order, for an
update requiring execution, let E be graph edge count and d the changed edge's
destination outdegree:

| First matching condition | Selected strategy | Decision reason |
| --- | --- | --- |
| E <= small_graph_edges | Dijkstra | small_graph |
| d <= repair_max_degree | Incremental repair | local_degree |
| E >= parallel_min_edges and requested threads >= 2 | Delta-stepping | parallel_work |
| Otherwise | Incremental repair | fallback |

Defaults are small_graph_edges=4096, repair_max_degree=32, parallel_min_edges=65536.
They are explicit starting hypotheses, not measured crossover points or optimal
settings. Initialization requires small_graph_edges < parallel_min_edges for all
policies, in addition to existing enum/delta/thread validation; equal/reversed
thresholds throw invalid_argument. Zero small/degree thresholds are allowed, and
threshold extremes can intentionally suppress later rules. Thresholds never change
automatically. Existing three-field PolicyConfig initializers retain their defaults.

Thread count 0 requests the OpenMP runtime default when delta-stepping executes,
but specifies no guaranteed two-worker budget. It therefore does not enable the
heuristic parallel branch; use an explicit request >=2 for that branch. Forced
delta-stepping still accepts 0 exactly as before. Selection does not inspect the
environment or predict actual team size; runtime constraints may supply fewer
workers. No delta/thread tuning is performed.

Precedence is request validation, equal/shared-no-effect bypass, a valid per-call
forced override, then the configured policy. A heuristic override uses reason
forced; a bypass has no selected strategy. The existing always policies still
use forced. Under execute_selected, strict no-effect requests also run this
ordered policy; repair can still finish at its intrinsic seed check.

Selection reads only E, CSR degree and immutable configuration after the existing
checked-seed test. It performs O(1) work, no dynamic allocation, no traversal,
sampling, timing feedback or post-execution observation. Decisions agree for the
same pre-update state/configuration/override with metrics on/off. Parallel timing
and work counters can vary without changing selection or distances.

Low destination degree does not guarantee local or cheap repair. Tests construct
two 512-vertex graphs with E=511 and destination degree 1: the same local_degree
decision improves 2 vertices in one and 511 in the other. This demonstrates a
feature limitation, not a measured timing comparison. Full recomputation still
pays staged-copy and result-scan costs. No speedup or policy optimality is established.
