#pragma once
#include "dynagraph/algorithms/sssp.hpp"
#include <utility>

namespace dynagraph::test {
// Independent synchronous Bellman-Ford, using input records rather than CSR.
inline std::vector<Distance> bellman_ford(std::size_t n, const std::vector<InputEdge>& edges, VertexId source) {
    std::vector<Distance> distances(n, unreachable_distance);
    distances[source] = 0;
    for (std::size_t pass = 1; pass < n; ++pass) {
        auto next = distances;
        for (const auto& edge : edges) {
            const auto u = static_cast<std::size_t>(edge.source);
            const auto v = static_cast<std::size_t>(edge.destination);
            if (distances[u] != unreachable_distance) {
                const auto candidate = distances[u] + static_cast<Distance>(edge.weight);
                if (candidate < next[v]) { next[v] = candidate; }
            }
        }
        if (next == distances) { break; }
        distances = std::move(next);
    }
    return distances;
}

} // namespace dynagraph::test
