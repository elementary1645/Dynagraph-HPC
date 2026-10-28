#pragma once
#include "system_validation_support.hpp"

namespace dynagraph::test::system {
inline Case adversarial_fixture(std::uint32_t index) {
    Case c;
    switch (index) {
    case 0:
        c.vertices = 256;
        for (VertexId v = 1; v < c.vertices; ++v) { c.edges.push_back({v - 1, v, 4294967295LL}); }
        break;
    case 1:
        c.vertices = 13; c.edges.push_back({0, 1, 100});
        for (VertexId u = 1; u < c.vertices; ++u) {
            for (VertexId v = 1; v < c.vertices; ++v) { c.edges.push_back({u, v, 0}); }
        }
        break;
    case 2:
        c.vertices = 10;
        for (VertexId u = 0; u < 8; ++u) {
            for (VertexId v = 0; v < c.vertices; ++v) {
                if (v / 2 == u / 2 + 1) { c.edges.push_back({u, v, 8}); }
            }
        }
        break;
    case 3: case 4: case 5: {
        const auto degree = static_cast<VertexId>(252 + index); // 255, 256, 257.
        c.vertices = degree + 2; c.edges.push_back({0, 1, 100});
        for (VertexId v = 2; v < c.vertices; ++v) { c.edges.push_back({1, v, 1}); }
        break;
    }
    case 6:
        c.vertices = 8; c.edges = {{0, 1, 10}, {1, 2, 1}, {3, 4, 10}, {4, 3, 0}, {5, 5, 9}}; break;
    case 7:
        c.vertices = 6; c.delta = unreachable_distance;
        c.edges = {{0, 1, 4294967295LL}, {1, 2, 4294967295LL}, {2, 3, 4294967295LL},
                   {3, 4, 4294967295LL}, {4, 5, 4294967295LL}, {5, 1, 4294967295LL}}; break;
    case 8:
        c.vertices = 4; c.edges = {{0, 1, 1000}, {1, 2, 1}, {2, 3, 1}}; break;
    case 9:
        c.vertices = 5; c.edges = {{0, 0, 10}, {0, 1, 1}, {0, 2, 100}, {1, 2, 1}, {2, 0, 10}, {3, 4, 20}}; break;
    case 10:
        c.vertices = 64; c.edges = {{0, 1, 100}};
        for (VertexId v = 2; v < c.vertices; ++v) { c.edges.push_back({1, v, static_cast<std::int64_t>(10 * v)}); }
        for (VertexId v = 2; v + 1 < c.vertices; ++v) { c.edges.push_back({v, v + 1, 0}); }
        break;
    case 11:
        c.vertices = 7; c.edges = {{0, 1, 15}, {0, 2, 16}, {0, 3, 17}, {0, 4, 100},
            {1, 2, 0}, {2, 3, 1}, {3, 4, 16}, {4, 5, 17}, {5, 6, 0}, {6, 3, 0}}; break;
    case 12:
        c.vertices = 1; c.edges = {{0, 0, 4294967295LL}}; break;
    case 13:
        c.vertices = 6; c.edges = {{0, 1, 100}, {0, 2, 100}, {1, 3, 0}, {2, 3, 0}, {2, 4, 0}, {3, 5, 0}}; break;
    default: throw std::invalid_argument("adversarial case must be 0..13");
    }
    std::sort(c.edges.begin(), c.edges.end(), [](const InputEdge& a, const InputEdge& b) {
        return a.source < b.source || (a.source == b.source && a.destination < b.destination);
    });
    auto ledger = c.edges;
    const auto add = [&](VertexId u, VertexId v, EdgeWeight weight) {
        const auto old = static_cast<EdgeWeight>(ledger[edge_index(ledger, u, v)].weight);
        const Update next{u, v, old, weight}; apply(ledger, next); c.updates.push_back(next);
    };
    const auto& first = c.edges.front();
    if (index == 8) {
        for (EdgeWeight weight = 999; weight >= 936; --weight) { add(0, 1, weight); }
    } else if (index == 13) {
        add(0, 1, 90); add(0, 2, 80); add(0, 1, 70); add(0, 2, 60);
    } else if (index == 9) {
        add(0, 2, 99); add(0, 2, 2); add(0, 2, 2); add(3, 4, 0); add(2, 0, 0); add(0, 0, 0); add(0, 2, 0);
    } else {
        const auto u = static_cast<VertexId>(first.source), v = static_cast<VertexId>(first.destination);
        add(u, v, static_cast<EdgeWeight>(first.weight));
        add(u, v, static_cast<EdgeWeight>(first.weight / 2)); add(u, v, 0);
        if (index == 0) { add(127, 128, 0); }
        if (index == 2) { add(1, 2, 0); add(2, 4, 0); }
        if (index == 6) { add(3, 4, 0); add(5, 5, 0); }
        if (index == 11) { add(0, 2, 0); add(0, 3, 0); }
    }
    if (index == 1) {
        test::require(oracle(c.vertices, ledger, 0) == std::vector<Distance>(c.vertices, 0), "hand-calculated zero region");
    }
    if (index == 7) {
        const auto values = oracle(c.vertices, ledger, 0);
        for (VertexId v = 1; v < c.vertices; ++v) {
            test::require(values[v] == static_cast<Distance>(v - 1) * 4294967295ULL, "hand-calculated wide chain");
        }
    }
    if (index == 6) {
        test::require(oracle(c.vertices, ledger, 0) == std::vector<Distance>{0, 0, 1, unreachable_distance,
            unreachable_distance, unreachable_distance, unreachable_distance, unreachable_distance}, "hand-calculated disconnected graph");
    }
    if (index == 10) {
        DijkstraMetrics metrics;
        const auto graph = CSRGraph::from_edges(c.vertices, c.edges);
        test::require(dijkstra(graph, 0, &metrics).distances == oracle(c.vertices, c.edges, 0) && metrics.stale_entries >= 60,
                      "fixture demonstrably creates many stale heap entries");
    }
    return c;
}
} // namespace dynagraph::test::system
