# Architecture

## Current implementation: Phase 5B-1

Phase 5B-1 adds standard-library Python graph/trace generation and independent
replay validation, specified in [workload artifacts](workload-artifacts.md).
It does not add a benchmark executable, clocks or SSSP algorithm changes.

The project builds a static dynagraph library (alias DynaGraph::dynagraph), a
dynagraph_cli executable, and CTest tests. The public API exposes project version
and the OpenMP specification date used to compile the library, plus fixed-topology
CSR storage, strict text edge-list loading, sequential Dijkstra, and OpenMP
delta-stepping with optional work counters, and an owning sequential transactional
single-decrease repair state. A forced-strategy engine maintains that authoritative
state across all three strategies. Deterministic metadata-only heuristic selection
is implemented; calibrated/learned selection remains planned. The CLI retains
help/version and both recomputation algorithms with JSON output; repair is a
library API only.

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
| dynamic/ | Owning transactional single-edge decrease repair |
| adaptive/ | Transactional strategy switching and deterministic heuristic selection |
| instrumentation/ | Reserved for timing; algorithm work counters live in algorithm APIs |
| apps/ | Command-line entry points |
| tests/ | Correctness and integration tests |
| benchmarks/configs/, benchmarks/python/ | Deterministic graph/trace specs, randomness, artifact I/O and replay CLI; no timing |
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
support is provided. Storage accepts increases as ordinary replacements. The
Phase 3B owning repair API below supports decreases only; it never exposes mutable
graph access and does not borrow an externally mutable graph.

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
delta-stepping. Phase 3B adds sequential single-edge decrease repair. Phase 4B-1
adds forced-strategy switching; Phase 4B-2 adds a deterministic heuristic.
Phase 5A's read-only experimental design is complete; Phase 5B-1 implements only
artifact generation/integrity/replay. Phase 5B-2 requires approval.
Batch/parallel repair, adaptive selection, and automatic
delta tuning remain future work.
Storage updates and full recomputation support increases; incremental processing
of increases remains deferred. Future timed replay will use the adaptive engine;
current artifact interoperability tests consume the existing CLI JSON.


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
parallel recomputation is implemented in Phase 2B, and single-decrease repair in
Phase 3B below.


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
no automatic fallback, delta tuning, or speedup claim in this recomputation API.

## Phase 3B: transactional single-edge decrease repair

### Public API and ownership

`dynagraph/dynamic/incremental_sssp.hpp` declares IncrementalSSSPState,
DecreaseOutcome, DecreaseResult, and RepairMetrics. Factories take CSRGraph by
value: lvalues are copied; rvalues transfer ownership and may be consumed even if
initialization fails. initialize(graph, source) calls Dijkstra, which validates the
source, including rejecting empty graphs. from_result_checked(graph, result)
validates source/dimensions and compares every distance with independently
recomputed Dijkstra before adopting the result. Matching dimensions are not proof
of freshness; arbitrary results are never trusted. Both factories allocate and
perform O(V + E log(E+1)) recomputation. Lvalue graph acquisition adds O(V+E).

A state owns graph, fixed source, distance vector, and V journal-membership bytes.
It is noncopyable/nonmovable and cannot be rebound; C++17 guaranteed factory-return
elision avoids needing partially moved-from state semantics. There is no public
unchecked constructor or mutable accessor. source(), graph(), and distances()
return a scalar or const view. Updates do not resize the graph/distance arrays.
Views reflect the latest committed state, not snapshots, and require a live state.
The caller serializes an update against all access to that state. Independent
states have independent storage; no graph revisions, global state, OpenMP teams,
or mutation hooks are needed. External changes to a copied input graph are isolated.

decrease(uint64_t u, uint64_t v, int64_t new_weight, RepairMetrics* = nullptr)
validates weight range, then both endpoints and edge existence, then rejects an
increase. If multiple preconditions fail, that validation order selects the error.
Range/increase errors use invalid_argument; invalid endpoints/absent edges use
out_of_range. Equal weights return unchanged_weight without a graph write.
Strict decreases return weight_only if no distances change or distances_repaired
otherwise. DecreaseResult contains old/new weights and distinct improved count.
No snapshots are allocated for return. Every successful strict decrease commits
its weight even when it cannot improve a label. Future requests compare against
that committed weight. There is no insertion, deletion, increase, source-change,
batch, or parallel-repair API.

### Algorithm and arithmetic

The min-priority_queue orders (distance, vertex) lexicographically. The only seed
is checked_add(d[u], new_weight) for v. Successful strict improvements journal the
vertex once, push a queue record, then change its distance. Pops with labels
differing from current distances are stale and skipped. Each valid pop scans its
outgoing CSR row. A local weight view substitutes new_weight for the changed
ordered endpoint pair; all other edges read stored weights. Topology uniqueness
makes that substitution unambiguous. Propagation never mutates graph storage and
never invokes Dijkstra.

After source validation ensures V>0, L=(V-1)*UINT32_MAX is below UINT64_MAX.
Initial correct distances are infinity or <=L. checked_add returns infinity for
an infinite tail or weight>L-label; otherwise it adds safely. Every accepted
finite candidate is <=L, maintaining the induction needed for the subtraction.
No tentative-label settled-distance assumption is used. Simple shortest paths
and every nonnegative prefix fit L, so rejecting longer walks loses no shortest
path. V=1 gives L=0 safely. Strict improvements prevent zero-cycle/equal-path
work. Nonnegative loops and edges into the source cannot improve its zero label.
Unreachable tails cannot seed improvements. Reachability itself is invariant
under finite-weight changes on fixed topology.

### Correctness and termination

Let D be the old correct distances and delta' the new true distances. Initially
d=D>=delta' because weights only decrease. A relaxation candidate d[x]+w'(x,y)
is also >=delta'(y); accepted labels therefore never underestimate true distances.
Old labels need not remain exact path lengths, only valid upper bounds.

Initially all old shortest-path inequalities hold except possibly the changed
edge. Seeding restores its inequality. Decreasing a vertex label preserves
incoming inequalities and may violate only outgoing ones; queue publication
ensures those are eventually scanned with the final label. At queue exhaustion
all inequalities hold with addition capped to infinity. Following a new simple
shortest path from source proves d<=delta': every prefix fits L and is therefore
not capped. Together the two inequalities establish exact distances. If the seed
does not improve, no propagation is necessary.

Heap extraction keys are nondecreasing: all candidates generated from a valid
pop are at least its key. A vertex cannot improve after its valid pop, so its row
is scanned once. It may improve repeatedly before that pop, leaving stale queue
records. Every accepted change is strict; zero-weight cycles do not invalidate
the argument. These bounds apply to this sequential single-update design, not
automatically to future unordered/parallel repair.

### Transaction and failure guarantees

UndoJournal is a local RAII guard holding original distance entries and references
to distances/marks. A first change appends (vertex, original distance) before
setting the mark; subsequent improvements reuse that entry. Heap insertion also
precedes every distance write. Journal/heap allocation exceptions therefore leave
enough information for complete rollback, including earlier tentative writes.
Journal insertion may succeed and a later heap push fail before a write; restoring
that entry is harmless. Metrics are staged as a local scalar aggregate.

After propagation, compute the scalar result/metrics, then call the existing
CSRGraph::replace_weight as the final potentially throwing operation. Its
validation and lookup precede the scalar store; it cannot throw after the store.
Then mark the journal committed and publish scalar metrics/result. All remaining
assignments and container/guard cleanup are nonthrowing. The guard clears marks
for its own entries on success; on failure it additionally restores original
distances. Rollback performs no graph writes, allocation, lookup, logging, or
callbacks and its destructor is noexcept. Queue and journal payloads are trivial.

At every public call boundary, graph and distances represent the same completed
query state. Any exception preserves graph arrays, distances, and caller metrics,
restores marks, and permits retry. There is no invalid-state recovery mode.
This guarantee covers ordinary C++ exceptions, not process termination, hardware
failure, or unsupported concurrent/reentrant access. Construction failure creates
no state; normal by-value acquisition rules apply to its arguments.

### Exact per-call metrics

Metrics are replaced only on success, including unchanged requests; rejected or
failed requests leave caller metrics unchanged. A one-time template dispatch
removes per-event updates when the pointer is omitted. Counters saturate and set
counters_saturated; there are no timing calls or shared atomic counters.

| Field | Definition |
| --- | --- |
| updates_applied | 1 for a committed strict decrease; otherwise 0 |
| unchanged_weight_requests | 1 only for unchanged_weight |
| updates_without_distance_change | 1 if affected count is zero, including unchanged weights |
| vertices_improved | Distinct vertices in the successful journal, including seed |
| edges_examined | All outgoing CSR records scanned during propagation, excluding lookup/seed |
| relaxation_attempts | Seed check for a strict decrease plus edges_examined; includes cap rejection |
| successful_relaxations | Every strict label reduction, including seed and repeated improvements |
| queue_pushes / queue_pops | All inserted/removed records, including stale records |
| stale_entries | Pops with obsolete labels |

Before saturation, a successful update has pushes=pops=successful_relaxations
and stale_entries+vertices_improved=pops. Affected fraction is derived as A/V
outside the kernel. Aggregate statistics and timings belong to future orchestration.

### Complexity and research limits

Let A be distinct improved vertices, E_A their outgoing edges, R successful
relaxations including seed, and H maximum live queue records. Each affected row
is scanned once, R<=E_A+1, H<=R. Update time is
O(log(outdegree(u)+1) + A + E_A + R log(R+1)), including journal cleanup.
Both validation and commit use binary search. A no-distance-change request needs
only lookup/seed/commit, no graph scan or heap/journal allocation. Membership bytes
are initialized once in O(V) and cleared in O(A), never O(V) per update.
Persistent repair arrays are O(V) beyond CSR. Local journal is O(A), queue O(H),
and vector capacities grow geometrically; no per-entry node allocation is used.
Containers are local to each update, so repeated repairs include their allocation
and destruction costs. No full distance vector is copied or returned per update.

Worst-case A and E_A cover the reachable graph. Transaction overhead can make
repair slower than full recomputation; no speedup or novelty claim is made.
Paths/predecessors and shared graph ownership are not maintained. Batches,
increases, parallel repair, adaptive scheduling and benchmark orchestration remain
outside this phase. Any future policy must include state-coherence/switching cost
and must not use the actual affected region as a free predecision feature.

## Phase 4B-1: forced-strategy execution and transactional switching

### Ownership and API

AdaptiveSSSPEngine owns one IncrementalSSSPState member and a const PolicyConfig.
There is no second persistent graph, distance vector, history, or policy model.
The engine and state are noncopyable/nonmovable. Engine factory return and member
initialization use direct prvalues under C++17 guaranteed elision, not optional
NRVO or a heap wrapper. Initialization validates policy/no-effect enums, positive
delta and nonnegative requested threads, then initializes every policy through
Dijkstra. Graph argument ownership and source validation match Phase 3B.

The public API in dynagraph/adaptive/adaptive_sssp.hpp exposes initialize, source,
graph, distances, and decrease(u,v,new_weight,AdaptiveMetrics*=nullptr,
optional<Strategy>=nullopt). Strategy has dijkstra, delta_stepping, incremental;
PolicyKind has the three corresponding always policies and the Phase 4B-2 heuristic
described below. Config defaults to
incremental, shared_fast_path, delta 1, runtime-default threads; these are valid
defaults, not calibrated choices. An optional per-call strategy overrides the
policy. Unsupported enum values are rejected, including invalid forced overrides
before request preparation. All parallel options are validated at initialization
even when a nonparallel policy is configured. Heuristic thresholds are validated
at initialization; no model fields exist.

All engine updates and access through existing views require caller serialization.
Separate engines own independent state and can run concurrently, including
independent OpenMP teams. No OpenMP global settings are changed. Recompute swaps
distance storage: element references/pointers/iterators must be reacquired after
successful updates; vector-object and graph const references still expose current
values while their engine lives. On exceptions old storage is preserved. The
standalone repair API continues to preserve its array storage on decrease.
No mutable accessors or unchecked public result setters are exposed.

### Preparation, execution and fast paths

The incremental class grants friendship only to AdaptiveSSSPEngine. Its private
PreparedDecrease contains validated VertexId endpoints, old/new EdgeWeight and a
checked seed. prepare_decrease preserves the standalone validation order and
messages: weight bounds, graph endpoint/existence lookup, then increase rejection.
Narrowing follows endpoint validation. The prepared value lives on the current
call's stack, never escapes or becomes a cached handle. Public standalone decrease
and the engine reuse it; repair_prepared dispatches the existing journal algorithm
with or without instrumentation. Seed arithmetic is shared, not duplicated.

AdaptiveUpdateResult holds DecreaseResult plus DecisionResult. Decision route is
unchanged, weight_only, or execute; reasons are equal_weight, no_distance_effect,
or forced for fixed policies; the heuristic reasons below identify its branches.
selected is optional and is engaged only for an executed backend.
distances_repaired describes a distance change under any backend, not necessarily
use of the incremental algorithm.

Equal weights always return unchanged/equal_weight without any backend or graph
write. Under shared_fast_path, a strict seed >= current destination distance
commits just the weight and returns weight_only/no_distance_effect, without calling
an SSSP backend. No queue, journal, staged graph, or backend metrics are allocated.
This route applies to every policy and override. An unreachable tail has an
infinite seed. With execute_selected, every strict update dispatches the selected
backend and reports execute with the applicable policy reason, even when its final outcome is weight_only.
Full strategies actually recompute; repair may stop at its intrinsic seed check.
These are separate experimental configurations; bypasses are not strategy wins.

### Recompute transaction

Engine recompute is private and accepts the same prepared request. It copies the
authoritative graph temporarily, applies the weight there, and calls exactly the
chosen Dijkstra or delta-stepping function with local metrics. It does not call
from_result_checked or run repair to synchronize afterward. The backend produces
its own result; arbitrary caller-supplied distances cannot be adopted.

Before commit, verify result source and vector size, zero source distance,
componentwise nonincrease, unchanged infinity/reachability classification, and
finite labels <= the existing cap. Count distinct improved vertices in the same
O(V) scan. The scan guards against specified consistency violations, not arbitrary
algorithm bugs; reference/oracle tests establish algorithm correctness. Aggregate
delta's per-thread counters into a fixed-size summary before committing. All delta
result/per-thread metric allocation occurs before the algorithm returns.

Then call authoritative CSRGraph::replace_weight as the last potentially throwing
operation; its validation/lookup precede its scalar store. Swap the completed
distance vector with the authoritative vector, publish scalar results/metrics, and
destroy staging, old distances and local metric vectors. Scratch marks stay zero;
no mark reset or repair pass is needed after recomputation. Static assertions
enforce nonthrowing distance swap, scalar publication/copy/move and relevant
destructors. A copy-swap of the entire nonmovable state is unnecessary.

Any recoverable C++ exception during validation, staging, algorithm execution or
allocating result preparation preserves authoritative graph/distances/caller
metrics and permits retry and subsequent strategy switching. Existing repair
exceptions use its first-change undo journal. No silent backend retry occurs.
OpenMP exceptions are caught on executing threads and rethrown after collective
team exit by the existing algorithm; process-fatal runtime/OS failures cannot be
turned into recoverable C++ exceptions by this engine.

### Metrics and cost boundaries

AdaptiveMetrics is an allocation-free scalar aggregate staged locally and replaced
only on success. It contains decision, work_collected, RepairMetrics,
DijkstraMetrics and DeltaWorkSummary. Bypasses have work_collected=false, no
selected strategy, and default work fields. For execute, work_collected is true
only when caller metrics were requested; only the chosen backend fields are
populated. Inactive fields reset, preventing previous-query metadata from leaking.
Delta summary includes optional actual_threads, bucket/light/heavy pass and stale
counts, and sums of edges/attempts/successes/CAS retries across workers. Sums
saturate and propagate the saturation flag. Actual team size is absent unless
measured for an executed delta call. Parallel schedules may change work counters;
decisions, distances and scalar update outcomes agree across instrumentation modes.
There are no clocks, learned thresholds or policy history; Phase 4B-2 adds the
bounded metadata-only selection described below.

Preparation/fast paths cost O(log(outdegree(u)+1)) without graph scans or propagation
allocation. Repair retains Phase 3B complexity. Full strategies add O(V+E) graph
copying and O(V) result checking to their existing algorithm work, plus logarithmic
staged/authoritative weight writes and temporary teardown. Commit swaps vectors
without copying their payload, but old-buffer and graph destruction is part of the
complete update cost. Persistent ownership is one CSR + distance + journal marks;
full execution additionally holds temporary CSR, new distances, and algorithm
scratch. No O(V) per-call scratch reset is introduced. Future comparisons must
charge these coherence, allocation and publication costs to each forced strategy.
P4, tuning, batches, increases and benchmarking remain gated. The forced core
and Phase 4B-2 heuristic establish no performance superiority.

## Phase 4B-2: deterministic workload-aware heuristic

PolicyKind::heuristic is appended to the enum, preserving the original values.
PolicyConfig appends HeuristicConfig with explicit unsigned EdgeOffset fields
small_graph_edges=4096, repair_max_degree=32 and parallel_min_edges=65536. These
are uncalibrated hypotheses, not measurements. Three-field aggregate initializers
remain source-compatible. always_incremental remains the default policy. All
initialization validates small_graph_edges < parallel_min_edges, including fixed
policies, before constructing a state. Equality/reversal (including parallel
threshold 0) is invalid_argument; small/degree threshold 0 is valid. Thresholds
are compared directly without multiplication/addition, so UINT64-scale boundaries
do not wrap. Degree thresholds may exceed any particular graph's degree and edge
thresholds may exceed its size, intentionally suppressing later branches.

Execution precedence is unchanged request preparation/validation and shared fast
paths first, then per-call forced override if present, then configured selection.
Invalid forced enums still reject before request preparation. Equal weights and
shared no-effect requests do not select or execute any backend. Fixed policies
and explicit overrides keep reason forced. For heuristic execution, the first
matching rule is:

1. E <= small_graph_edges: Dijkstra, small_graph.
2. degree(destination) <= repair_max_degree: incremental, local_degree.
3. E >= parallel_min_edges and configured parallel.thread_count >= 2:
   delta-stepping, parallel_work.
4. Otherwise: incremental, fallback.

Only E and, after the first rule fails, destination degree are read by selection.
CSR degree is O(1) offset subtraction; the destination was already validated.
The helper performs no loop, allocation, traversal, sampling, backend call, clock
or runtime-team query. Its valid-config path is O(1); existing request validation
retains its binary edge lookup and checked seed. It consumes no affected count,
work counter, latency or historical observations. Configuration is copied once
and immutable. No source/graph/state ownership or transaction code changed.

Requested threads 0 is an unspecified OpenMP runtime default, not an explicit
two-worker budget, so it fails rule 3. This deliberately avoids environment-based
policy choices for a fixed configuration. Counts 1/2 distinguish serial/parallel
eligibility; actual runtime team size is a post-execution metric and may be lower.
Forced delta retains thread-count-0 behavior. Delta and threads never auto-tune.
Under execute_selected, strict no-effect requests also use the rule order; repair
retains its seed check. Selection/reasons are independent of instrumentation and
parallel schedule, while parallel execution time and event counts can vary.

The four new reason values append to existing ones. Decisions are prepared before
any backend and published through the unchanged scalar transaction path. No extra
failure/commit stage, graph copy, journal reset or mutable history is introduced.
Invalid requests preserve state/metrics. Existing failure tests remain, augmented
with automatic selection of every backend followed by fault/retry/forced switch.
Recorded host allocation sequences for heuristic vs forced execution of the same
backend are identical, checking zero added selection allocations. Source review
establishes bounded metadata operations; no timing-based overhead claim is made.

Small/local rules are hypotheses about work, not guarantees. Paired 512-vertex
fixtures have the same E=511, changed edge/labels and destination degree 1; a
local_degree decision improves 2 vertices in one and 511 in the other. The latter
is a long propagation chain. This does not establish which strategy is faster;
it establishes that cheap degree metadata cannot bound the affected region.
Neither optimality nor speedup nor novelty is claimed. Calibration/online learning,
benchmark infrastructure, topology/increase/batch changes and later phases remain
unimplemented and require separate approval.
