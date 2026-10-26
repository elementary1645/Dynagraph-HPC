# Architecture

## Current implementation: Phase 2B

The project builds a static dynagraph library (alias DynaGraph::dynagraph), a
dynagraph_cli executable, and CTest tests. The public API exposes project version
and the OpenMP specification date used to compile the library, plus fixed-topology
CSR storage, strict text edge-list loading, sequential Dijkstra, and OpenMP
delta-stepping with optional work counters. Incremental repair and adaptive
selection remain planned. The CLI retains help/version commands and supports
both SSSP algorithms with JSON output.

CMake requires C++17 without compiler extensions and finds OpenMP through its
imported CXX target. GCC is the supported toolchain for this phase. OpenMP linkage
propagates to library consumers. Debug and Release presets use GCC and treat
compiler warnings as errors. Tests use a dependency-free C++ harness with checks
active in Release; CTest handles discovery, timeouts, and CLI checks.

## Module boundaries

| Location | Responsibility |
| --- | --- |
| include/dynagraph/, src/ | Public API and implementation |
| graph/ | Contiguous CSR storage, weight replacement, and text input validation |
| algorithms/ | Sequential Dijkstra, parallel delta-stepping, shared SSSP result |
| dynamic/ | Future propagation of edge-weight decreases |
| adaptive/ | Future validated algorithm-selection policy |
| instrumentation/ | Reserved for timing; algorithm work counters live in algorithm APIs |
| apps/ | Command-line entry points |
| tests/ | Correctness and integration tests |
| benchmarks/configs/, benchmarks/python/ | Future experiment definitions and Python tooling |
| data/manifests/ | Dataset provenance and checksums; generated data ignored |
| results/ | Generated outputs, ignored by default |
| docs/, paper/ | Design, research records, protocol, and future manuscript |

Empty future modules are tracked with .gitkeep placeholders. They contain no
implementation. Python packages and paper tooling are not Phase 0 dependencies.

## Graph semantics and supported limits

CSRGraph represents a directed graph with explicit vertex count V and vertex IDs
in [0, V). Empty graphs, isolated vertices, disconnected components, self-loops,
and zero-weight edges are valid. Each ordered (source, destination) pair is unique;
the builder rejects duplicates even when their weights agree. The reverse edge
is a distinct edge and is never inserted implicitly.

| Quantity | Type / supported range |
| --- | --- |
| Vertex ID | VertexId = uint32_t, strictly less than V |
| Vertex count | uint64_t API, 0 through 4,294,967,295 |
| Edge weight | EdgeWeight = uint32_t, 0 through 4,294,967,295 |
| Edge offset, ID, count | EdgeOffset = uint64_t |
| Builder edge fields | InputEdge uses int64_t for source, destination, weight |

The deliberate vertex-count limit means the largest usable ID is 4,294,967,294.
Signed builder/update inputs are validated before conversion; values beyond
int64_t are outside those C++ input types and must not be narrowed by callers.
The text loader parses uint64_t tokens before enforcing storage bounds.

The theoretical simple directed graph bound is E <= V*V, including self-loops.
Practical counts must also fit size_t byte arithmetic and vector<T>::max_size()
for every persistent array and the transient InputEdge list. These checks reject
unrepresentable sizes before graph allocation; they cannot guarantee sufficient
RAM. Allocation failures propagate as bad_alloc. Maximum-sized graphs have not
been allocated or validated on this development machine.

## CSR invariants and ownership

- offsets has V+1 uint64_t entries; offsets[0] == 0 and offsets[V] == E.
- Offsets are nondecreasing; an empty row has equal adjacent offsets.
- destinations and weights each have E contiguous entries.
- Row u occupies [offsets[u], offsets[u+1]); destinations are strictly increasing
  within each row and every destination is below V.
- An edge ID is its array index, assigned by ascending source then destination.
  IDs remain stable throughout weight replacements.
- Public arrays are read-only. Topology cannot be mutated through the graph API.

Graphs own their arrays. Copies are independent. Moves leave the source as a
valid empty graph; maintaining its {0} offset sentinel can allocate, so the move
constructor is intentionally not noexcept. Copy assignment preserves the target
if copying fails. Object assignment replaces the whole graph value and invalidates
existing graph views; it is not an edge insertion/deletion operation.

## Public graph API

Headers: dynagraph/graph/csr_graph.hpp and dynagraph/graph/edge_list_io.hpp.

- CSRGraph::from_edges(vertex_count, vector<InputEdge>): validating builder.
  Pass an rvalue to transfer ownership of the input list, or an lvalue to copy it.
- vertex_count(), edge_count(), degree(vertex): graph dimensions and row size.
- offsets(), destinations(), weights(): const references to contiguous arrays.
- outgoing_edges(vertex): allocation-free, read-only range with size(), begin(),
  and end(). Iteration yields OutgoingEdge {id, destination, weight} by value.
- weight(source, destination): deterministic lookup by binary search within a row.
- replace_weight(source, destination, int64_t new_weight): returns the previous
  weight and leaves all topology/edge IDs unchanged. A failed update changes nothing.
- load_edge_list(istream&) and load_edge_list_file(filesystem::path): strict loading.

Invalid builder records/weights and duplicate edges throw invalid_argument.
Unsupported counts throw length_error. Invalid access vertices or missing edges
throw out_of_range. Input syntax errors include line numbers; duplicate errors
identify endpoints after sorting. File-loader diagnostics also include the path.
File/read failures throw runtime_error; streams configured to throw can propagate
ios_base::failure. Allocation failures are not converted into syntax errors.

Iterator dereference returns the current weight; an already copied OutgoingEdge
is a snapshot. Ranges/iterators require a live, unmoved, unassigned graph; standard
iterator preconditions apply (do not dereference end). Weight replacement does not
invalidate ranges, iterators, or array references. All mutation is serial and must
be externally synchronized against every read or write; no concurrent mutation
support is provided. Storage accepts increases as ordinary replacements, but no
shortest-path maintenance for either increases or decreases exists in this phase.

## Construction and complexity

The builder validates counts and all records, sorts the owned edge list in place
by (source, destination), rejects adjacent duplicates, then constructs the three
arrays. It reserves final edge arrays once; no second sorted edge list is made.
Input permutation cannot affect the resulting arrays or edge IDs.

| Operation | Complexity |
| --- | --- |
| Construction | O(V + E log E) time; O(V + E) peak storage including input |
| Persistent CSR payload | 8(V+1) + 8E bytes, excluding vector objects/capacity overhead |
| Degree/count access | O(1) |
| Outgoing row traversal | O(outdegree), O(1) iterator storage |
| Edge lookup/replacement | O(log(outdegree + 1)) |
| Copy | O(V + E) |

Allocation-size checks precede V+1 allocation/index conversion and count-sized
array allocation. The vertex bound makes V+1 and V*V safe in uint64_t. Prefix sums
are bounded by the already validated edge count, so offset arithmetic cannot
overflow. Topology overlays, reverse adjacency, tombstones, and compaction are
unnecessary for this fixed-topology scope and are not implemented.

## Text edge-list format

The first nonblank line contains V E. Exactly E subsequent nonblank lines contain
source destination weight. IDs are zero-based. Tokens are ASCII unsigned decimal
integers; leading zeros are accepted. Spaces, tabs, carriage returns, vertical
tabs, and form feeds separate tokens; blank lines are ignored. A final newline
is optional. Comments, signs (including +), fractional/exponent/hex notation,
byte-order marks, extra columns, and extra/missing records are rejected.

```text
6 4
0 2 7
0 1 0
1 1 3
3 4 9
```

This graph has a zero-weight edge, a self-loop, disconnected components, and an
isolated vertex 5. Vertex 2 and vertex 4 have no outgoing edges. A graph with no
vertices is `0 0`; three isolated vertices are `3 0`.

Loading rejects numeric overflow, impossible declared counts, invalid vertices,
out-of-range weights, duplicates, and stream failures. It initially reserves at
most 4096 records rather than allocating the declared E before any records have
been read; truncated files with enormous declarations therefore fail without that
upfront allocation. Loading buffers one line at a time and owns one growing edge
list, then moves it into the builder. Loading requires O(V+E+L) peak storage for
longest input line length L; the resulting graph is O(V+E). No input file size or
line-length resource quota is imposed by this library.

## Future phase gates

Phases 1B and 2B implement independently verified sequential Dijkstra and parallel
delta-stepping. Phase 3 requires explicit approval. Decrease-only incremental
repair, adaptive selection, and automatic delta tuning remain future work.
Storage updates and full recomputation support increases; incremental processing
of increases remains deferred. Benchmark tooling will later consume CLI JSON.


## Phase 1B: sequential SSSP baseline

Public API: `SSSPResult dijkstra(const CSRGraph&, VertexId,
DijkstraMetrics* = nullptr)` in `dynagraph/algorithms/sssp.hpp`. Results own the
source and distances; no graph copies or predecessor allocations occur. A
predecessor tree is deferred until a concrete path/repair contract justifies it.
Invalid sources, including every query on an empty graph, throw out_of_range
before resetting counters. Allocation failures propagate. Queries never mutate
the graph; callers serialize weight updates between completed queries.

The min-priority_queue orders (distance, vertex ID) lexicographically. The source
is seeded at zero; a strict distance improvement pushes a new entry. Pops with
obsolete distances are discarded. Equal alternatives and zero-weight cycles do
not enqueue equal labels. Nonnegative weights ensure each current entry settles
its vertex once. Each settled row is scanned through the allocation-free CSR
range. No OpenMP regions are used. Deterministic CSR ordering and heap ties make
results and work counts repeatable.

Distances are uint64_t, infinity is UINT64_MAX. A shortest path can be chosen
simple by removing nonnegative cycles, so its length is at most (V-1)*Wmax.
With V <= 2^32-1 and Wmax = 2^32-1 the maximum finite shortest-path distance is
(2^32-2)*(2^32-1) = 18446744060824649730. Even a candidate scanned from a settled
vertex is bounded by V*Wmax <= (2^32-1)^2 = 18446744065119617025, strictly below
UINT64_MAX. Thus ordinary uint64 addition cannot overflow or collide with infinity.
Compile-time assertions enforce both graph type bounds; widening storage requires
revisiting this proof. Maximum-size allocations are not part of verification.

Initialization takes O(V); at most E strict improvements create O(E) heap entries.
Time is O(V + E log(E+1)); auxiliary space is O(V+E), including lazy duplicates
and the result. This is a lazy binary heap, with no decrease-key operation.

Optional counters are separate from correctness results and reset on every valid
instrumented call. A single dispatch selects a template specialization; omitting
the pointer removes all per-event counter increments and branches.

| Counter | Definition |
| --- | --- |
| vertices_settled | Pops whose label equals the current distance, including source |
| edges_examined | Outgoing edges scanned from settled vertices, including self-loops |
| successful_relaxations | Strict improvements of a destination label |
| queue_pushes | Initial source entry plus one per successful relaxation |
| queue_pops | Every removed entry, including stale entries |
| stale_entries | Pops whose stored label differs from the current distance |

These uint64 counters fit supported storage: edges are unique endpoint pairs,
E <= V^2, and pushes/pops <= E+1 < UINT64_MAX. A completed query drains the heap.
Settled vertices equal the reachable count; examined edges equal reachable-row
sizes. Counters measure work, not runtime or performance benefit.

The CLI owns parsing/loading/JSON presentation; algorithms depend only on CSR.
Schema v1 and error behavior are documented in README.md. There is no timing in
the CLI. Full recomputation after serial increases or decreases is implemented;
Parallel recomputation is implemented in Phase 2B below; incremental processing
remains future gated work.


## Phase 2B: parallel delta-stepping

Public header: dynagraph/algorithms/delta_stepping.hpp. The API is
`SSSPResult delta_stepping(const CSRGraph&, VertexId,
const DeltaSteppingOptions&, DeltaSteppingMetrics* = nullptr)`.
Options contain required Distance delta and int thread_count=0. Zero delta and
negative threads throw invalid_argument. Invalid sources throw out_of_range.
Argument validation precedes metric reset; metrics may be incomplete after an
execution failure. Allocation/container failures propagate without partial results.
Result source, uint64 distances, infinity, and predecessor omission match Dijkstra.
No sequential algorithm or graph-storage code is changed.

### Bucket and arithmetic invariants

Buckets are an ordered std::map<Distance, vector<Entry>>, keyed by label/delta.
Delta accepts 1 through UINT64_MAX. Keys are selected using map.begin(), never by
incrementing through empty indices. No bucket endpoint multiplication is used.
Light edges have weight <= delta; heavy edges have weight > delta. Entries retain
(vertex, label) snapshots. At a quiescent boundary, labels differing from the
current atomic label are stale and discarded, both on publication and extraction.

The current bucket repeatedly processes all valid entries until no valid entries
remain in it. Every improvement, including an improvement to a previously seen
vertex in the same bucket, can generate another light pass. A coordinator-owned
byte membership array only deduplicates the per-bucket heavy scan list. Once
closure is reached, that list's vertices are scanned using their final labels.
A heavy edge cannot generate a current/earlier-bucket distance. No later bucket
can improve an already closed bucket under nonnegative weights.

Finite shortest paths have simple representatives, so L=(V-1)*UINT32_MAX is a safe
cap, strictly below infinity. With nonempty validated V, the product fits uint64.
All stored finite labels are <=L. Before evaluating du+w, test w>L-du; if true,
discard that walk. Otherwise addition is safe and the candidate is below infinity.
This preserves all shortest paths and all their prefixes without assuming tentative
labels are settled. Static assertions pin the graph bounds used in the proof.
For V=1, L=0 and positive self-loops are skipped safely. Strict improvements stop
zero cycles from producing equal-label work. Unreachable vertices stay at infinity.

### Ownership and synchronization

Each call owns a fixed atomic distance array, thread-state vector, sparse buckets,
work descriptors, heavy-list membership bytes, and result. No mutable global state
or OpenMP global-setting changes occur. The thread-state ownership vector is sized
before entering one persistent `parallel num_threads(requested)` region. Zero
requested threads resolves through omp_get_max_threads() in the caller's context;
the actual team size is observed inside the region. Nested/runtime constraints may
reduce it. Independent host threads may query the same immutable CSR with separate
metrics. Assignment, movement, destruction, and weight replacement of that graph
must be externally serialized against every query.

Only the `single` coordinator changes map/vector structure for shared buckets,
work descriptors, the heavy list, and membership bytes. The coordinator role can
move between team threads across rounds; barriers transfer ownership. Work splits
CSR rows into at most 256-edge descriptors with a source-label snapshot, allowing
high-degree rows to be shared. Workers use `for schedule(dynamic,1)` and only read
the descriptors/CSR. Each worker appends exclusively to its own update vector and
updates exclusively its own metric/exception slot. Update capacity is retained
within a query; outer thread-state storage never resizes during execution.

Every round has:

1. single preparation and its implicit publication barrier;
2. a collective completion/failure decision;
3. worksharing scan and its implicit worker-completion barrier;
4. single failure inspection/update merge and its implicit publication barrier;
5. collective re-entry to the next single preparation before any exit decision.

No nowait or OpenMP cancellation is used. Atomic min uses compare_exchange_weak
with relaxed success/failure memory orders, and relaxed loads. Distances publish
no associated payload; barrier synchronization publishes ordinary work/buffer
state. No ordinary access aliases the atomic distance array. Successful CAS
operations append scheduling records; superseded records are discarded after the
worker barrier, preserving the final winner. Copying into ordinary result distances
occurs after the team exits.

### Exception safety

All potentially throwing coordinator work is inside a try/catch in `single`.
Each worker catches scan exceptions on that same thread, records exception_ptr,
and still encounters the worksharing barrier. A worker with a recorded exception
skips further assigned scans, while peers finish the round. The coordinator
inspects slots before merging; a failed round is never used to return a result.
All threads re-enter the next single/publication barrier, then exit collectively.
Only after team shutdown is the exception rethrown. If update-vector allocation
fails after CAS, the entire query fails; no label with lost work is returned.
Pre-region and result/metric allocation failures propagate through normal RAII.

The initial implementation had a failure-exit decision immediately after merge.
A fast coordinator could set the next round's exception while another thread was
still testing the old round, causing divergent barrier participation. Fault
injection exposed a timeout. The fixed design makes failure exit decisions only
after the next preparation publication barrier. The allocation-failure sweep and
post-CAS publication-failure test retain regression coverage.

### Work metrics

Instrumentation uses a one-time dispatch to template specializations. Uninstrumented
scans have no event counter updates. Coordinator counters have a single writer;
worker counters are private to fixed thread-state slots and copied after team exit.
No shared atomic metric increments are used. Counter increments saturate at
UINT64_MAX and set counters_saturated rather than wrap. Metrics are work counts,
not benchmark timing; scheduling can change successes, retries, and work assignment.

| Field | Exact definition |
| --- | --- |
| actual_thread_count | Actual team size observed inside the region |
| buckets_processed | Bucket keys selected with at least one valid entry; excludes stale-only keys |
| light_edge_passes | Nonempty valid frontier rounds, even when their vertices have no outgoing edges |
| heavy_edge_passes | One completed heavy phase per processed bucket, including empty-edge phases |
| stale_entries | Superseded scheduling records discarded during merge or extraction |
| per_thread.edges_examined | All CSR records inspected, including edges filtered out by phase |
| per_thread.relaxation_attempts | Edges matching the phase class, including cap-rejected candidates |
| per_thread.successful_relaxations | Successful strictly decreasing CAS operations |
| per_thread.cas_retries | Failed CAS attempts, including spurious compare_exchange_weak failures |

Each reachable row is scanned in heavy processing once, and in one or more light
passes. The current CSR layout filters weights in each phase; inspections therefore
include classification overhead. No prepartitioned edge copies are maintained.

### Complexity and limitations

Do not transfer Dijkstra's bounds to this implementation. Let C be total scanned
CSR records, R successful relaxations, M maximum live sparse bucket keys, and Q
maximum retained scheduling records. Work includes O(V+C+R log(M+1)) plus frontier,
merge, and synchronization costs; label reprocessing can make C and R much larger
than E. Extra storage includes atomic/result arrays, O(V) membership/heavy lists,
work descriptors, Q entries, map nodes, and retained per-thread capacities.
Lazy duplicates mean there is no claimed O(V+E) peak-memory bound for arbitrary
workloads. The serial coordinator can bottleneck; atomics may contend or be
implemented with runtime locks on other platforms. One persistent team reduces
repeated startup but small queries can still be slower than Dijkstra. There is
no automatic fallback, delta tuning, incremental processing, or speedup claim.
