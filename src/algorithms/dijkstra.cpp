#include "dynagraph/algorithms/sssp.hpp"

#include <functional>
#include <queue>
#include <stdexcept>
#include <utility>

namespace dynagraph {
namespace {
// A shortest path can be simple: distance <= (V-1)*Wmax. Even a
// scanned candidate is <= V*Wmax <= (2^32-1)^2 < UINT64_MAX.
static_assert(CSRGraph::max_vertex_count <= 0xFFFFFFFFULL);
static_assert(CSRGraph::max_edge_weight <= 0xFFFFFFFFULL);

template <bool Instrumented>
SSSPResult run(const CSRGraph& graph, VertexId source, DijkstraMetrics* metrics) {
    SSSPResult result{source, std::vector<Distance>(
        static_cast<std::size_t>(graph.vertex_count()), unreachable_distance)};
    using Entry = std::pair<Distance, VertexId>;
    std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> queue;
    result.distances[source] = 0;
    queue.emplace(0, source);
    if constexpr (Instrumented) { ++metrics->queue_pushes; }
    while (!queue.empty()) {
        const auto [distance, vertex] = queue.top();
        queue.pop();
        if constexpr (Instrumented) { ++metrics->queue_pops; }
        if (distance != result.distances[vertex]) {
            if constexpr (Instrumented) { ++metrics->stale_entries; }
            continue;
        }
        if constexpr (Instrumented) { ++metrics->vertices_settled; }
        for (const auto edge : graph.outgoing_edges(vertex)) {
            if constexpr (Instrumented) { ++metrics->edges_examined; }
            const Distance candidate = distance + edge.weight; // Proven bound above.
            if (candidate < result.distances[edge.destination]) {
                result.distances[edge.destination] = candidate;
                queue.emplace(candidate, edge.destination);
                if constexpr (Instrumented) {
                    ++metrics->successful_relaxations;
                    ++metrics->queue_pushes;
                }
            }
        }
    }
    return result;
}
} // namespace

SSSPResult dijkstra(const CSRGraph& graph, VertexId source, DijkstraMetrics* metrics) {
    if (source >= graph.vertex_count()) {
        throw std::out_of_range("source outside [0, V)");
    }
    if (metrics != nullptr) {
        *metrics = {};
        return run<true>(graph, source, metrics);
    }
    return run<false>(graph, source, nullptr);
}
} // namespace dynagraph
