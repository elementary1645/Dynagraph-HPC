#pragma once

#include "dynagraph/algorithms/sssp.hpp"

namespace dynagraph {
struct DeltaSteppingOptions {
    Distance delta; // Required: 1..UINT64_MAX.
    int thread_count = 0; // 0 uses omp_get_max_threads(); positive requests a team.
};

struct DeltaSteppingThreadMetrics {
    std::uint64_t edges_examined = 0;
    std::uint64_t relaxation_attempts = 0;
    std::uint64_t successful_relaxations = 0;
    std::uint64_t cas_retries = 0;
};

struct DeltaSteppingMetrics {
    int actual_thread_count = 0;
    std::uint64_t buckets_processed = 0;
    std::uint64_t light_edge_passes = 0;
    std::uint64_t heavy_edge_passes = 0;
    std::uint64_t stale_entries = 0;
    bool counters_saturated = false;
    std::vector<DeltaSteppingThreadMetrics> per_thread;
};

// Immutable graph, independent call-owned state; no concurrent graph mutation.
// Throws out_of_range for invalid source, invalid_argument for delta=0 or
// negative threads. Allocation failures propagate after collective team exit.
// Invalid arguments leave metrics unchanged; valid calls reset metrics, which
// may be incomplete on failure. Actual team size may differ from the request.
// Identical uint64/infinity semantics to Dijkstra; no predecessor information.
[[nodiscard]] SSSPResult delta_stepping(const CSRGraph& graph, VertexId source,
                                      const DeltaSteppingOptions& options,
                                      DeltaSteppingMetrics* metrics = nullptr);
} // namespace dynagraph
