#pragma once

#include "dynagraph/graph/csr_graph.hpp"
#include <cstdint>
#include <limits>
#include <vector>

namespace dynagraph {
using Distance = std::uint64_t;
inline constexpr Distance unreachable_distance = std::numeric_limits<Distance>::max();

struct SSSPResult {
    VertexId source;
    std::vector<Distance> distances; // Indexed by vertex; infinity means unreachable.
};

// Work counters, reset on a valid query. Not timings; separate from the result.
struct DijkstraMetrics {
    std::uint64_t vertices_settled = 0;
    std::uint64_t edges_examined = 0;
    std::uint64_t successful_relaxations = 0;
    std::uint64_t queue_pushes = 0;
    std::uint64_t queue_pops = 0;
    std::uint64_t stale_entries = 0;
};

// Throws out_of_range for invalid sources (including an empty graph).
// No concurrent weight mutation. No predecessor tree is retained.
// O(V + E log(E+1)) time, O(V+E) auxiliary space with lazy queue entries.
// Omitting metrics selects a specialization without counter updates.
[[nodiscard]] SSSPResult dijkstra(const CSRGraph& graph, VertexId source,
                                DijkstraMetrics* metrics = nullptr);
} // namespace dynagraph
