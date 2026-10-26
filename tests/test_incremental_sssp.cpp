#include "dynagraph/dynamic/incremental_sssp.hpp"
#include "sssp_test_support.hpp"
#include "test_support.hpp"

#include <array>
#include <limits>
#include <random>
#include <type_traits>
#include <utility>

namespace {
using namespace dynagraph;
using test::require;

auto metric_values(const RepairMetrics& m) {
    return std::array<std::uint64_t, 11>{m.updates_applied, m.unchanged_weight_requests,
        m.updates_without_distance_change, m.vertices_improved, m.edges_examined,
        m.relaxation_attempts, m.successful_relaxations, m.queue_pushes, m.queue_pops,
        m.stale_entries, m.counters_saturated ? 1U : 0U};
}

RepairMetrics sentinel() { return {91, 92, 93, 94, 95, 96, 97, 98, 99, 100, true}; }

RepairMetrics update(IncrementalSSSPState& measured, IncrementalSSSPState& plain,
                     std::vector<InputEdge>& records, std::size_t index, std::int64_t weight) {
    auto& edge = records[index];
    const auto old_weight = edge.weight;
    const auto before = measured.distances();
    const auto old_offsets = measured.graph().offsets();
    const auto old_destinations = measured.graph().destinations();
    RepairMetrics metrics = sentinel();
    const auto result = measured.decrease(static_cast<std::uint64_t>(edge.source),
        static_cast<std::uint64_t>(edge.destination), weight, &metrics);
    const auto other = plain.decrease(static_cast<std::uint64_t>(edge.source),
        static_cast<std::uint64_t>(edge.destination), weight);
    edge.weight = weight; // Independent original-record reference, not a state graph copy.
    const auto reference = CSRGraph::from_edges(measured.graph().vertex_count(), records);
    const auto expected = dijkstra(reference, measured.source()).distances;
    require(measured.distances() == expected && plain.distances() == expected, "Fresh Dijkstra agreement in both modes");
    if (reference.vertex_count() <= 24) {
        require(expected == test::bellman_ford(static_cast<std::size_t>(reference.vertex_count()),
            records, measured.source()), "Independent input-record Bellman-Ford agreement");
    }
    require(measured.graph().weights() == reference.weights() && plain.graph().weights() == reference.weights(),
            "Committed weights match independently updated records");
    require(measured.graph().offsets() == old_offsets && measured.graph().destinations() == old_destinations,
            "Updates preserve topology and IDs");
    std::uint64_t affected = 0;
    std::uint64_t edges = 0;
    for (std::size_t v = 0; v < before.size(); ++v) {
        require(expected[v] <= before[v], "Valid decrease never increases a distance");
        require((expected[v] == unreachable_distance) == (before[v] == unreachable_distance),
                "Fixed finite-weight topology preserves reachability");
        if (expected[v] < before[v]) { ++affected; edges += reference.degree(v); }
    }
    const bool unchanged = old_weight == weight;
    const auto outcome = unchanged ? DecreaseOutcome::unchanged_weight :
        (affected == 0 ? DecreaseOutcome::weight_only : DecreaseOutcome::distances_repaired);
    require(result.outcome == outcome && result.old_weight == static_cast<EdgeWeight>(old_weight) &&
            result.new_weight == static_cast<EdgeWeight>(weight) && result.vertices_improved == affected,
            "Exact update outcome");
    require(other.outcome == result.outcome && other.old_weight == result.old_weight &&
            other.new_weight == result.new_weight && other.vertices_improved == result.vertices_improved,
            "Instrumented and plain scalar results match");
    require(metrics.updates_applied == (unchanged ? 0U : 1U) &&
            metrics.unchanged_weight_requests == (unchanged ? 1U : 0U) &&
            metrics.updates_without_distance_change == (affected == 0 ? 1U : 0U) &&
            metrics.vertices_improved == affected && !metrics.counters_saturated, "Per-call outcome counters");
    require(metrics.edges_examined == edges && metrics.relaxation_attempts == edges + (unchanged ? 0U : 1U),
            "Each affected row is scanned once, plus strict-update seed check");
    require(metrics.successful_relaxations == metrics.queue_pushes && metrics.queue_pops == metrics.queue_pushes &&
            metrics.stale_entries + affected == metrics.queue_pops, "Queue and distinct-vertex identities");
    return metrics;
}

void initialization() {
    static_assert(std::is_same_v<decltype(std::declval<IncrementalSSSPState&>().graph()), const CSRGraph&>);
    static_assert(std::is_same_v<decltype(std::declval<IncrementalSSSPState&>().distances()), const std::vector<Distance>&>);
    static_assert(!std::is_copy_constructible_v<IncrementalSSSPState>);
    static_assert(!std::is_move_constructible_v<IncrementalSSSPState>);
    test::require_throws<std::out_of_range>([] { (void)IncrementalSSSPState::initialize(CSRGraph{}, 0); }, "source");
    auto original = CSRGraph::from_edges(4, {{0, 1, 20}, {1, 2, 30}});
    test::require_throws<std::out_of_range>([&] { (void)IncrementalSSSPState::initialize(original, 4); }, "source");
    const auto correct = dijkstra(original, 0);
    auto state = IncrementalSSSPState::initialize(original, 0);
    auto independent = IncrementalSSSPState::from_result_checked(original, correct);
    require(state.source() == 0 && state.distances() == correct.distances, "Dijkstra initialization");
    const auto* distance_storage = state.distances().data();
    const auto* weight_storage = state.graph().weights().data();
    original.replace_weight(0, 1, 10);
    require(state.graph().weight(0, 1) == 20 && state.distances() == correct.distances, "Original graph isolation");
    (void)state.decrease(0, 1, 5);
    require(independent.graph().weight(0, 1) == 20 && independent.distances() == correct.distances,
            "Independent state ownership");
    require(distance_storage == state.distances().data() && weight_storage == state.graph().weights().data(),
            "No distance/graph array replacement per update");
    test::require_throws<std::invalid_argument>([&] {
        (void)IncrementalSSSPState::from_result_checked(original, correct);
    }, "distances");
    test::require_throws<std::out_of_range>([] {
        (void)IncrementalSSSPState::from_result_checked(CSRGraph{}, {0, {}});
    }, "source");
    test::require_throws<std::out_of_range>([&] {
        (void)IncrementalSSSPState::from_result_checked(original, {4, correct.distances});
    }, "source");
    test::require_throws<std::invalid_argument>([&] {
        (void)IncrementalSSSPState::from_result_checked(original, {0, {0}});
    }, "dimensions");
    auto bad = dijkstra(original, 0);
    bad.distances[0] = 1;
    test::require_throws<std::invalid_argument>([&] {
        (void)IncrementalSSSPState::from_result_checked(original, bad);
    }, "distances");
    bad = dijkstra(original, 0);
    bad.source = 1;
    test::require_throws<std::invalid_argument>([&] {
        (void)IncrementalSSSPState::from_result_checked(original, bad);
    }, "distances");
    // Successful nonzero-source adoption, including unreachable vertices.
    auto nonzero = IncrementalSSSPState::from_result_checked(original, dijkstra(original, 1));
    require(nonzero.source() == 1 && nonzero.distances()[0] == unreachable_distance, "Nonzero fixed source");
    auto moved_graph = CSRGraph::from_edges(1, {{0, 0, 0}});
    auto singleton = IncrementalSSSPState::initialize(std::move(moved_graph), 0);
    require(singleton.distances() == std::vector<Distance>{0} && moved_graph.vertex_count() == 0,
            "Rvalue ownership and zero cap");
}

void fixtures() {
    std::vector<InputEdge> records{{0, 1, 10}, {0, 2, 2}, {2, 1, 2}, {1, 3, 5},
        {3, 1, 0}, {1, 1, 7}, {0, 0, 4294967295LL}, {4, 5, 4294967295LL}, {3, 0, 10}, {5, 6, 1}};
    const auto graph = CSRGraph::from_edges(7, records);
    auto measured = IncrementalSSSPState::initialize(graph, 0);
    auto plain = IncrementalSSSPState::initialize(graph, 0);
    (void)update(measured, plain, records, 0, 9); // Strict decrease, alternative remains shorter.
    (void)update(measured, plain, records, 0, 4); // Equal-cost alternative, distance unchanged.
    (void)update(measured, plain, records, 0, 3); // Local and multi-hop improvements.
    (void)update(measured, plain, records, 0, 3); // Unchanged weight.
    (void)update(measured, plain, records, 2, 0);
    (void)update(measured, plain, records, 3, 0); // Zero cycle 1 -> 3 -> 1.
    (void)update(measured, plain, records, 1, 0);
    (void)update(measured, plain, records, 5, 0); // Non-source self-loop.
    (void)update(measured, plain, records, 6, 0); // Source self-loop.
    (void)update(measured, plain, records, 7, 0); // Unreachable tail, never changes reachability.
    (void)update(measured, plain, records, 8, 0); // Edge into source.
    (void)update(measured, plain, records, 0, 0); // Repeated edge decrease to zero.

    std::vector<InputEdge> stale{{0, 1, 100}, {1, 2, 10}, {1, 3, 1}, {3, 2, 1}, {2, 4, 1}};
    auto a = IncrementalSSSPState::initialize(CSRGraph::from_edges(5, stale), 0);
    auto b = IncrementalSSSPState::initialize(CSRGraph::from_edges(5, stale), 0);
    const auto metrics = update(a, b, stale, 0, 0);
    require(a.distances() == std::vector<Distance>{0, 0, 2, 1, 3} && metrics.stale_entries == 1 &&
            metrics.successful_relaxations == 5 && metrics.vertices_improved == 4, "Exact stale-entry repair");

    std::vector<InputEdge> single{{0, 0, 4294967295LL}};
    auto c = IncrementalSSSPState::initialize(CSRGraph::from_edges(1, single), 0);
    auto d = IncrementalSSSPState::initialize(CSRGraph::from_edges(1, single), 0);
    (void)update(c, d, single, 0, 1); // Positive loop is rejected by checked addition at cap=0.
    (void)update(c, d, single, 0, 0); // Cap=0; no positive or equal cycle propagation.
}

void rejected_requests() {
    const auto graph = CSRGraph::from_edges(4, {{0, 1, 10}, {1, 2, 20}});
    auto state = IncrementalSSSPState::initialize(graph, 0);
    const auto before = state.distances();
    const auto weights = state.graph().weights();
    RepairMetrics metrics = sentinel();
    const auto unchanged = [&] {
        require(state.distances() == before && state.graph().weights() == weights &&
                metric_values(metrics) == metric_values(sentinel()), "Rejection preserves state and caller metrics");
    };
    for (const auto& endpoints : {std::pair<std::uint64_t, std::uint64_t>{4, 1}, {0, 4}, {1, 0},
                                {std::numeric_limits<std::uint64_t>::max(), 0}, {0, std::numeric_limits<std::uint64_t>::max()}}) {
        test::require_throws<std::out_of_range>([&] {
            (void)state.decrease(endpoints.first, endpoints.second, 0, &metrics);
        }, "");
        unchanged();
    }
    for (const auto weight : {std::int64_t{-1}, std::int64_t{4294967296LL},
                              std::numeric_limits<std::int64_t>::max(), std::int64_t{11}}) {
        test::require_throws<std::invalid_argument>([&] { (void)state.decrease(0, 1, weight, &metrics); }, "weight");
        unchanged();
    }
    (void)state.decrease(0, 1, 0, &metrics);
    require(state.distances()[2] == 20, "State reusable after all invalid operations");
}

void large_structures() {
    std::vector<InputEdge> chain;
    constexpr VertexId n = 6000;
    for (VertexId v = 1; v < n; ++v) { chain.push_back({v - 1, v, 4294967295LL}); }
    auto a = IncrementalSSSPState::initialize(CSRGraph::from_edges(n, chain), 0);
    auto b = IncrementalSSSPState::initialize(CSRGraph::from_edges(n, chain), 0);
    (void)update(a, b, chain, 0, 0);
    require(a.distances().back() > CSRGraph::max_edge_weight, "Wide uint64 distance after long repair");
    (void)update(a, b, chain, 3000, 0);
    (void)update(a, b, chain, 3000, 0);
    std::vector<InputEdge> hub{{0, 1, 4294967295LL}};
    for (VertexId v = 2; v < 900; ++v) {
        hub.push_back({1, v, 4294967295LL});
        if (v != 899) { hub.push_back({v, 899, 0}); }
    }
    auto c = IncrementalSSSPState::initialize(CSRGraph::from_edges(900, hub), 0);
    auto d = IncrementalSSSPState::initialize(CSRGraph::from_edges(900, hub), 0);
    (void)update(c, d, hub, 0, 0);
    (void)update(c, d, hub, 1, 0);
}

void randomized() {
    std::mt19937 random(0x31B2026U);
    for (unsigned trial = 0; trial < 120; ++trial) {
        const auto n = static_cast<VertexId>(1 + random() % 16U);
        std::vector<InputEdge> original;
        for (VertexId u = 0; u < n; ++u) {
            for (VertexId v = 0; v < n; ++v) {
                if (random() % (trial % 2 == 0 ? 2U : 7U) != 0) { continue; }
                const auto weight = trial % 3 == 0 ? random() : random() % 32U;
                original.push_back({u, v, static_cast<std::int64_t>(weight)});
            }
        }
        const auto graph = CSRGraph::from_edges(n, original);
        for (VertexId source = 0; source < n; ++source) {
            auto records = original;
            auto a = IncrementalSSSPState::initialize(graph, source);
            auto b = IncrementalSSSPState::from_result_checked(graph, dijkstra(graph, source));
            require(a.distances() == test::bellman_ford(n, records, source), "Initial random oracle agreement");
            std::size_t index = 0;
            for (unsigned step = 0; step < 24 && !records.empty(); ++step) {
                if (step % 3 != 0) { index = static_cast<std::size_t>(random()) % records.size(); }
                const auto old = static_cast<std::uint64_t>(records[index].weight);
                const auto next = step % 5 == 0 ? old : static_cast<std::uint64_t>(random()) % (old + 1);
                (void)update(a, b, records, index, static_cast<std::int64_t>(next));
            }
        }
    }
}
} // namespace

int main() {
    int failures = 0;
    failures += test::run("incremental initialization, checked adoption, ownership and view lifetime", initialization);
    failures += test::run("incremental outcomes, cycles, wide weights and stale heap entries", fixtures);
    failures += test::run("incremental invalid updates preserve graph, distances and metrics", rejected_requests);
    failures += test::run("incremental long chains, high degree and wide distances", large_structures);
    failures += test::run("120 seeded dense/sparse graphs, every source, 24 updates in both modes", randomized);
    return failures == 0 ? 0 : 1;
}
