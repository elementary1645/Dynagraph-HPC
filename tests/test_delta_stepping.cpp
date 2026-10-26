#include "dynagraph/algorithms/delta_stepping.hpp"
#include "sssp_test_support.hpp"
#include "test_support.hpp"

#include <array>
#include <future>
#include <random>
#include <stdexcept>

namespace {
using namespace dynagraph;
using test::require;
constexpr std::array<Distance, 6> deltas{1, 2, 3, 16, 4294967295ULL, unreachable_distance};

void verify(const CSRGraph& graph, VertexId source, const std::vector<Distance>& expected,
            Distance delta, int threads) {
    DeltaSteppingMetrics metrics;
    metrics.stale_entries = 999;
    const auto result = delta_stepping(graph, source, {delta, threads}, &metrics);
    require(result.source == source && result.distances == expected, "Delta distance/oracle agreement");
    require(delta_stepping(graph, source, {delta, threads}).distances == expected,
            "Uninstrumented agreement");
    require(metrics.actual_thread_count >= 1 && metrics.actual_thread_count <= threads,
            "Actual team respects request");
    require(metrics.per_thread.size() == static_cast<std::size_t>(metrics.actual_thread_count),
            "Per-thread metrics match actual team");
    require(!metrics.counters_saturated && metrics.heavy_edge_passes == metrics.buckets_processed &&
            metrics.light_edge_passes >= metrics.buckets_processed, "Completed phase accounting");
    std::uint64_t successes = 0;
    for (const auto& local : metrics.per_thread) {
        require(local.successful_relaxations <= local.relaxation_attempts &&
                local.relaxation_attempts <= local.edges_examined, "Worker accounting");
        successes += local.successful_relaxations;
    }
    std::uint64_t reachable = 0;
    for (const auto distance : expected) { if (distance != unreachable_distance) { ++reachable; } }
    require(successes >= reachable - 1, "Every reached non-source label was generated");
}

void compare(std::uint32_t n, const std::vector<InputEdge>& edges) {
    const auto graph = CSRGraph::from_edges(n, edges);
    const auto weights = graph.weights();
    const auto offsets = graph.offsets();
    const auto destinations = graph.destinations();
    for (VertexId source = 0; source < n; ++source) {
        const auto expected = test::bellman_ford(n, edges, source);
        require(dijkstra(graph, source).distances == expected, "Independent baseline agreement");
        for (const auto delta : deltas) {
            for (const int threads : {1, 2}) { verify(graph, source, expected, delta, threads); }
        }
    }
    require(weights == graph.weights() && offsets == graph.offsets() &&
            destinations == graph.destinations(), "Immutable shared CSR");
}

void fixtures() {
    DeltaSteppingMetrics metrics;
    metrics.buckets_processed = 9;
    test::require_throws<std::out_of_range>([&] {
        (void)delta_stepping(CSRGraph{}, 0, {1, 2}, &metrics);
    }, "source");
    auto graph = CSRGraph::from_edges(1, {{0, 0, 4294967295LL}});
    test::require_throws<std::out_of_range>([&] {
        (void)delta_stepping(graph, 1, {1, 2}, &metrics);
    }, "source");
    test::require_throws<std::invalid_argument>([&] {
        (void)delta_stepping(graph, 0, {0, 2}, &metrics);
    }, "delta");
    test::require_throws<std::invalid_argument>([&] {
        (void)delta_stepping(graph, 0, {1, -1}, &metrics);
    }, "threads");
    require(metrics.buckets_processed == 9, "Invalid calls preserve counters");
    compare(1, {{0, 0, 4294967295LL}});
    compare(1, {{0, 0, 0}});
    compare(4, {});
    compare(7, {{0, 1, 0}, {1, 2, 0}, {2, 1, 0}, {2, 3, 5}, {0, 3, 5},
                {3, 3, 0}, {5, 6, 1}});
    compare(4, {{0, 1, 4294967295LL}, {1, 2, 4294967295LL}, {2, 3, 4294967295LL}});
    // Within bucket 0, v1 must run at 10 then again at 2. Heavy v1->v4
    // must run at the final label 2; an encountered-once suppression is wrong.
    const std::vector<InputEdge> closure{{0, 1, 10}, {0, 2, 1}, {2, 1, 1},
                                        {1, 3, 1}, {1, 4, 20}};
    compare(5, closure);
    graph = CSRGraph::from_edges(5, closure);
    require(delta_stepping(graph, 0, {16, 2}, &metrics).distances ==
            std::vector<Distance>{0, 2, 1, 3, 22}, "Closure/final-heavy-label regression");
    require(metrics.actual_thread_count == 2, "Two-thread fixture must actually use two workers");
    require(metrics.light_edge_passes >= 3, "Same-bucket light processing repeats");
    // Boundary weights and exact bucket multiples, plus a stale future record.
    compare(6, {{0, 1, 15}, {0, 2, 16}, {0, 3, 17}, {1, 2, 0},
                {2, 3, 1}, {3, 4, 16}, {0, 4, 100}, {4, 5, 17}});
    const auto defaults = delta_stepping(graph, 0, {16, 0}, &metrics);
    require(defaults.distances == dijkstra(graph, 0).distances && metrics.actual_thread_count >= 1,
            "Runtime-default team");
    (void)delta_stepping(graph, 0, {16, 4}, &metrics);
    std::cout << "Requested 4 threads, actual team: " << metrics.actual_thread_count << '\n';
    for (int repeat = 0; repeat < 20; ++repeat) {
        verify(graph, 0, dijkstra(graph, 0).distances, 16, 4);
    }
}

void randomized() {
    std::mt19937 random(0xD317A202U);
    for (unsigned trial = 0; trial < 70; ++trial) {
        const auto n = static_cast<std::uint32_t>(1 + random() % 12U);
        std::vector<InputEdge> edges;
        for (VertexId u = 0; u < n; ++u) {
            for (VertexId v = 0; v < n; ++v) {
                if (random() % (trial % 2 == 0 ? 2U : 7U) != 0) { continue; }
                const auto weight = trial % 3 == 0 ? random() : random() % 25U;
                edges.push_back({u, v, static_cast<std::int64_t>(weight)});
            }
        }
        compare(n, edges);
        auto graph = CSRGraph::from_edges(n, edges);
        for (unsigned update = 0; update < 4 && !edges.empty(); ++update) {
            auto& edge = edges[static_cast<std::size_t>(random()) % edges.size()];
            edge.weight = update % 2 == 0 ? 0 : 4294967295LL;
            graph.replace_weight(static_cast<VertexId>(edge.source),
                                 static_cast<VertexId>(edge.destination), edge.weight);
            const auto source = static_cast<VertexId>(random() % n);
            const auto expected = test::bellman_ford(n, edges, source);
            require(dijkstra(graph, source).distances == expected, "Updated Dijkstra oracle");
            for (const auto delta : deltas) { verify(graph, source, expected, delta, 2); }
        }
    }
}

void stress() {
    std::vector<InputEdge> edges;
    constexpr VertexId n = 800;
    for (VertexId v = 1; v < n - 1; ++v) {
        edges.push_back({0, v, v % 16});
        edges.push_back({v, n - 1, n - v});
    }
    const auto graph = CSRGraph::from_edges(n, edges);
    const auto expected = dijkstra(graph, 0).distances;
    for (int repeat = 0; repeat < 60; ++repeat) {
        verify(graph, 0, expected, deltas[static_cast<std::size_t>(repeat) % deltas.size()], 2);
    }
    // Independent host threads, independent OpenMP teams and call-owned state.
    auto first = std::async(std::launch::async, [&] {
        for (int i = 0; i < 15; ++i) { verify(graph, 0, expected, 16, 2); }
    });
    auto second = std::async(std::launch::async, [&] {
        for (int i = 0; i < 15; ++i) { verify(graph, 0, expected, 3, 2); }
    });
    first.get();
    second.get();
    edges.clear();
    for (VertexId v = 1; v < 2000; ++v) { edges.push_back({v - 1, v, 4294967295LL}); }
    const auto chain = CSRGraph::from_edges(2000, edges);
    for (const auto delta : deltas) { verify(chain, 0, dijkstra(chain, 0).distances, delta, 2); }
}
} // namespace

int main() {
    int failures = 0;
    failures += test::run("delta fixtures, boundaries, repeated closure and oversubscription", fixtures);
    failures += test::run("70 seeded delta differential graphs and in-place updates", randomized);
    failures += test::run("skew, contention, chains and concurrent independent queries", stress);
    return failures == 0 ? 0 : 1;
}
