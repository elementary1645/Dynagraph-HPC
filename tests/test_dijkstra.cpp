#include "dynagraph/algorithms/sssp.hpp"
#include "test_support.hpp"
#include "sssp_test_support.hpp"

#include <random>
#include <stdexcept>
#include <vector>

namespace {
using namespace dynagraph;
using dynagraph::test::require;


void compare(std::uint32_t n, const std::vector<InputEdge>& edges) {
    const auto graph = CSRGraph::from_edges(n, edges);
    const auto weights = graph.weights();
    const auto offsets = graph.offsets();
    const auto destinations = graph.destinations();
    for (VertexId source = 0; source < n; ++source) {
        DijkstraMetrics metrics;
        const auto expected = test::bellman_ford(n, edges, source);
        const auto result = dijkstra(graph, source, &metrics);
        require(result.source == source && result.distances == expected, "Bellman-Ford agreement");
        require(dijkstra(graph, source).distances == expected, "Repeated uninstrumented query");
        DijkstraMetrics again;
        require(dijkstra(graph, source, &again).distances == expected, "Repeated instrumented query");
        require(again.queue_pops == metrics.queue_pops && again.stale_entries == metrics.stale_entries,
                "Deterministic work");
        std::uint64_t reachable = 0;
        std::uint64_t examined = 0;
        for (std::size_t v = 0; v < expected.size(); ++v) {
            if (expected[v] != unreachable_distance) { ++reachable; examined += graph.degree(v); }
        }
        require(metrics.vertices_settled == reachable && metrics.edges_examined == examined,
                "Reachable work counts");
        require(metrics.queue_pushes == metrics.successful_relaxations + 1 &&
                metrics.queue_pops == metrics.queue_pushes &&
                metrics.stale_entries + reachable == metrics.queue_pops, "Queue accounting");
    }
    require(weights == graph.weights() && offsets == graph.offsets() &&
            destinations == graph.destinations(), "Queries preserve graph arrays");
}

void fixtures() {
    test::require_throws<std::out_of_range>([] { (void)dijkstra(CSRGraph{}, 0); }, "source");
    const auto isolated = CSRGraph::from_edges(4, {});
    test::require_throws<std::out_of_range>([&] { (void)dijkstra(isolated, 4); }, "source");
    test::require_throws<std::out_of_range>([&] { (void)dijkstra(isolated, 0xFFFFFFFFU); }, "source");
    compare(1, {});
    compare(4, {});
    compare(7, {{0, 0, 3}, {0, 1, 0}, {1, 2, 0}, {2, 1, 0}, {2, 3, 5},
                {0, 3, 5}, {0, 4, 20}, {3, 4, 1}, {5, 6, 0}});
    compare(4, {{0, 1, 4294967295LL}, {1, 2, 4294967295LL}, {2, 3, 4294967295LL}});
    const auto wide = dijkstra(CSRGraph::from_edges(3, {{0, 1, 4294967295LL},
                                                       {1, 2, 4294967295LL}}), 0);
    require(wide.distances[2] == 8589934590ULL, "Distances exceed uint32");
    auto graph = CSRGraph::from_edges(3, {{0, 1, 10}, {0, 2, 2}, {2, 1, 1}});
    DijkstraMetrics metrics;
    require(dijkstra(graph, 0, &metrics).distances == std::vector<Distance>{0, 3, 2}, "Alternative route");
    require(metrics.vertices_settled == 3 && metrics.edges_examined == 3 &&
            metrics.successful_relaxations == 3 && metrics.queue_pushes == 4 &&
            metrics.queue_pops == 4 && metrics.stale_entries == 1, "Exact stale-entry counts");
    graph.replace_weight(0, 1, 0);
    require(dijkstra(graph, 0, &metrics).distances[1] == 0, "Decrease recomputation");
    require(metrics.queue_pushes == 3 && metrics.stale_entries == 0, "Metrics reset");
    graph.replace_weight(0, 1, 4294967295LL);
    require(dijkstra(graph, 0).distances[1] == 3, "Increase recomputation");
    std::vector<InputEdge> chain;
    constexpr std::uint32_t n = 10000;
    for (std::uint32_t v = 1; v < n; ++v) { chain.push_back({v - 1, v, 4294967295LL}); }
    const auto result = dijkstra(CSRGraph::from_edges(n, chain), 0);
    require(result.distances.back() == static_cast<Distance>(n - 1) * 4294967295ULL, "Long chain");
}

void randomized() {
    std::mt19937 random(0x51B2026U);
    for (unsigned trial = 0; trial < 300; ++trial) {
        const auto n = static_cast<std::uint32_t>(1 + random() % 19U);
        std::vector<InputEdge> edges;
        for (VertexId u = 0; u < n; ++u) {
            for (VertexId v = 0; v < n; ++v) {
                // Alternating dense and sparse graphs, including zero/full-range weights.
                if (random() % (trial % 2 == 0 ? 2U : 8U) != 0) { continue; }
                const auto weight = trial % 3 == 0 ? random() % 4U : random();
                edges.push_back({u, v, static_cast<std::int64_t>(weight)});
            }
        }
        compare(n, edges);
        if (!edges.empty()) {
            // Preserve the original rebuilt-graph differential cases as well as
            // adding storage-update integration checks below.
            edges.front().weight = 0;
            compare(n, edges);
            edges.front().weight = 4294967295LL;
            compare(n, edges);
            auto graph = CSRGraph::from_edges(n, edges);
            for (unsigned update = 0; update < 4; ++update) {
                auto& edge = edges[static_cast<std::size_t>(random()) % edges.size()];
                edge.weight = update % 2 == 0 ? 0 : 4294967295LL;
                graph.replace_weight(static_cast<VertexId>(edge.source),
                                     static_cast<VertexId>(edge.destination), edge.weight);
                for (VertexId source = 0; source < n; ++source) {
                    require(dijkstra(graph, source).distances == test::bellman_ford(n, edges, source),
                            "Randomized in-place replacement then recomputation");
                }
            }
            compare(n, edges);
        }
    }
}
} // namespace

int main() {
    return test::run("Dijkstra fixtures and 300 seeded differential graphs with updates", [] {
        fixtures();
        randomized();
    });
}
