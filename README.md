# DynaGraph-HPC

DynaGraph-HPC is a research project toward adaptive shortest-path computation on
dynamic graphs using C++17, OpenMP, CMake, and Python benchmark orchestration.
Correctness, measured performance, and reproducibility guide development.

## Current status

Phase 1B implements sequential binary-heap Dijkstra as the full-recomputation
baseline, with optional work counters, strict JSON CLI output, and independent
Bellman–Ford differential tests. CSR construction, serial weight replacement,
text loading, existing CLI options, and OpenMP smoke tests remain available.
Parallel shortest paths, incremental repair, adaptive selection, and benchmarks
are planned work.
There are no performance results or speedup claims.

The approved initial graph scope is directed, fixed topology with nonnegative
integer weights. Later incremental work prioritizes edge-weight decreases.
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

GitHub Actions defines Ubuntu Debug/Release builds and tests. Hosted CI execution
is separate from local verification and requires the workflow to reach GitHub.

## Layout and development

- include/dynagraph/ and src/: library API and CSR implementation; reserved modules
  for algorithms, dynamic updates, adaptation, and instrumentation
- apps/ and tests/: CLI and automated checks
- benchmarks/: future configuration and Python experiment tooling
- data/manifests/ and results/: provenance and generated experiment artifacts
- docs/ and paper/: design, research records, protocol, and future manuscript

See [architecture](docs/architecture.md), [experimental protocol](docs/experimental-protocol.md),
[research log](docs/research-log.md), and [engineering standards](AGENTS.md).
Each implementation phase requires approval before work begins. Phase 1B is implemented; Phase 2 requires explicit approval.

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
equal to `dijkstra`, integer `source`, and array `distances` with exactly V entries
in vertex order. Each entry is a nonnegative integer distance or JSON null for
unreachable. Consumers must preserve uint64 integers (JavaScript Number loses
precision above 2^53-1). No timing or counters are included. Required options may
appear in any order, exactly once; unknown options, malformed unsigned decimal
sources, missing values, invalid input, and invalid sources produce a stderr
diagnostic and exit 2. Success exits 0. Existing no-argument/help/version commands
remain available.

See architecture.md for the overflow proof, complexity, and exact metric definitions.
