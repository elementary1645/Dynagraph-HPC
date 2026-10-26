#include "dynagraph/adaptive/adaptive_sssp.hpp"
#include "sssp_test_support.hpp"
#include "test_support.hpp"

#include <array>
#include <future>
#include <limits>
#include <random>
#include <tuple>
#include <type_traits>

namespace {
using namespace dynagraph;
using test::require;
constexpr std::array<Strategy, 3> strategies{Strategy::dijkstra, Strategy::delta_stepping, Strategy::incremental};
constexpr std::array<PolicyKind, 4> policies{PolicyKind::always_dijkstra, PolicyKind::always_delta_stepping,
                                          PolicyKind::always_incremental, PolicyKind::heuristic};
constexpr std::array<Distance, 6> deltas{1, 2, 3, 16, 4294967295ULL, unreachable_distance};

auto metric_values(const AdaptiveMetrics& m) {
    const auto& r = m.repair;
    const auto& d = m.dijkstra;
    const auto& p = m.parallel;
    return std::make_tuple(m.decision.route, m.decision.selected, m.decision.reason, m.work_collected,
        std::array<std::uint64_t, 11>{r.updates_applied, r.unchanged_weight_requests, r.updates_without_distance_change,
            r.vertices_improved, r.edges_examined, r.relaxation_attempts, r.successful_relaxations,
            r.queue_pushes, r.queue_pops, r.stale_entries, r.counters_saturated ? 1U : 0U},
        std::array<std::uint64_t, 6>{d.vertices_settled, d.edges_examined, d.successful_relaxations,
            d.queue_pushes, d.queue_pops, d.stale_entries}, p.actual_threads,
        std::array<std::uint64_t, 9>{p.buckets_processed, p.light_edge_passes, p.heavy_edge_passes,
            p.stale_entries, p.edges_examined, p.relaxation_attempts, p.successful_relaxations,
            p.cas_retries, p.counters_saturated ? 1U : 0U});
}

AdaptiveMetrics sentinel() {
    AdaptiveMetrics m;
    m.decision = {DecisionRoute::execute, Strategy::delta_stepping, DecisionReason::forced};
    m.work_collected = true;
    m.repair = {11, 12, 13, 14, 15, 16, 17, 18, 19, 20, true};
    m.dijkstra = {21, 22, 23, 24, 25, 26};
    m.parallel = {7, 31, 32, 33, 34, 35, 36, 37, 38, true};
    return m;
}

bool same_decision(const DecisionResult& a, const DecisionResult& b) {
    return a.route == b.route && a.selected == b.selected && a.reason == b.reason;
}

AdaptiveUpdateResult update(AdaptiveSSSPEngine& measured, AdaptiveSSSPEngine& plain, std::vector<InputEdge>& records,
            std::size_t index, std::int64_t weight, const PolicyConfig& config,
            std::optional<Strategy> forced = std::nullopt) {
    auto& edge = records[index];
    const auto old = edge.weight;
    const auto before = measured.distances();
    auto metrics = sentinel();
    const auto a = measured.decrease(static_cast<std::uint64_t>(edge.source),
        static_cast<std::uint64_t>(edge.destination), weight, &metrics, forced);
    const auto b = plain.decrease(static_cast<std::uint64_t>(edge.source),
        static_cast<std::uint64_t>(edge.destination), weight, nullptr, forced);
    edge.weight = weight;
    const auto reference = CSRGraph::from_edges(measured.graph().vertex_count(), records);
    const auto expected = dijkstra(reference, measured.source()).distances;
    require(measured.distances() == expected && plain.distances() == expected, "Both modes match independent fresh Dijkstra");
    if (reference.vertex_count() <= 20) {
        require(expected == test::bellman_ford(static_cast<std::size_t>(reference.vertex_count()), records,
                                              measured.source()), "Independent Bellman-Ford agreement");
    }
    require(measured.graph().weights() == reference.weights() && plain.graph().weights() == reference.weights() &&
            measured.graph().offsets() == reference.offsets() && plain.graph().offsets() == reference.offsets() &&
            measured.graph().destinations() == reference.destinations() && plain.graph().destinations() == reference.destinations(),
            "Both authoritative graphs match separately maintained records");
    std::uint64_t affected = 0;
    std::uint64_t affected_edges = 0;
    std::uint64_t reachable = 0;
    std::uint64_t reachable_edges = 0;
    for (std::size_t v = 0; v < before.size(); ++v) {
        require(expected[v] <= before[v] && (expected[v] == unreachable_distance) == (before[v] == unreachable_distance),
                "Monotone distances and invariant reachability across switches");
        if (expected[v] < before[v]) { ++affected; affected_edges += reference.degree(v); }
        if (expected[v] != unreachable_distance) { ++reachable; reachable_edges += reference.degree(v); }
    }
    const auto outcome = old == weight ? DecreaseOutcome::unchanged_weight :
        (affected == 0 ? DecreaseOutcome::weight_only : DecreaseOutcome::distances_repaired);
    require(a.update.outcome == outcome && a.update.old_weight == static_cast<EdgeWeight>(old) &&
            a.update.new_weight == static_cast<EdgeWeight>(weight) && a.update.vertices_improved == affected,
            "Exact engine outcome");
    require(b.update.outcome == a.update.outcome && b.update.old_weight == a.update.old_weight &&
            b.update.new_weight == a.update.new_weight && b.update.vertices_improved == affected &&
            same_decision(a.decision, b.decision) && same_decision(metrics.decision, a.decision), "Metrics-on/off equivalence");
    const bool bypass = old == weight || (affected == 0 && config.no_effect == NoEffectMode::shared_fast_path);
    AdaptiveMetrics only_active;
    only_active.decision = a.decision;
    only_active.work_collected = !bypass;
    if (bypass) {
        require(a.decision.route == (old == weight ? DecisionRoute::unchanged : DecisionRoute::weight_only) &&
                !a.decision.selected && a.decision.reason == (old == weight ? DecisionReason::equal_weight :
                DecisionReason::no_distance_effect), "Shared bypass is not an executed strategy");
    } else {
        require(a.decision.route == DecisionRoute::execute && a.decision.selected && metrics.work_collected,
                "A selected backend actually executes");
        const auto selected = *a.decision.selected;
        if (forced || config.kind != PolicyKind::heuristic) {
            const auto expected_strategy = forced ? *forced : strategies[static_cast<std::size_t>(config.kind)];
            require(selected == expected_strategy && a.decision.reason == DecisionReason::forced,
                    "Forced override/fixed-policy behavior preserved");
        } else {
            const auto count = reference.edge_count();
            const auto degree = reference.degree(static_cast<std::uint64_t>(edge.destination));
            const auto& h = config.heuristic;
            // Check the reported branch's contract, including precedence.
            const bool small = count <= h.small_graph_edges;
            const bool local = degree <= h.repair_max_degree;
            const bool parallel = count >= h.parallel_min_edges && config.parallel.thread_count >= 2;
            require((a.decision.reason == DecisionReason::small_graph && small && selected == Strategy::dijkstra) ||
                    (a.decision.reason == DecisionReason::local_degree && !small && local && selected == Strategy::incremental) ||
                    (a.decision.reason == DecisionReason::parallel_work && !small && !local && parallel && selected == Strategy::delta_stepping) ||
                    (a.decision.reason == DecisionReason::fallback && !small && !local && !parallel && selected == Strategy::incremental),
                    "Heuristic reason obeys the pre-execution metadata and ordered rules");
        }
        if (selected == Strategy::incremental) {
            only_active.repair = metrics.repair;
            const auto& r = metrics.repair;
            require(r.updates_applied == 1 && r.vertices_improved == affected &&
                    r.updates_without_distance_change == (affected == 0 ? 1U : 0U) &&
                    r.edges_examined == affected_edges && r.relaxation_attempts == affected_edges + 1 &&
                    r.queue_pushes == r.queue_pops && r.queue_pushes == r.successful_relaxations &&
                    r.stale_entries + affected == r.queue_pops && !r.counters_saturated, "Preserved repair accounting");
        } else if (selected == Strategy::dijkstra) {
            only_active.dijkstra = metrics.dijkstra;
            const auto& d = metrics.dijkstra;
            require(d.vertices_settled == reachable && d.edges_examined == reachable_edges &&
                    d.queue_pushes == d.queue_pops && d.queue_pushes == d.successful_relaxations + 1 &&
                    d.stale_entries + reachable == d.queue_pops, "Dijkstra work is full recomputation");
        } else {
            only_active.parallel = metrics.parallel;
            const auto& p = metrics.parallel;
            require(p.actual_threads && *p.actual_threads >= 1 &&
                    (config.parallel.thread_count == 0 || *p.actual_threads <= config.parallel.thread_count) &&
                    p.edges_examined >= reachable_edges && p.successful_relaxations >= reachable - 1 &&
                    p.heavy_edge_passes == p.buckets_processed && !p.counters_saturated, "Measured delta work and actual team");
        }
    }
    require(metric_values(metrics) == metric_values(only_active), "Inactive metrics reset and unmeasured team is absent");
    return a;
}

void heuristic_boundaries() {
    struct Case { HeuristicConfig thresholds; int workers; Strategy strategy; DecisionReason reason; };
    const std::array<Case, 11> cases{{
        {{7, 0, 8}, 2, Strategy::dijkstra, DecisionReason::small_graph}, // E == small.
        {{6, 2, 8}, 2, Strategy::incremental, DecisionReason::local_degree}, // E == small+1, degree == repair.
        {{6, 1, 7}, 2, Strategy::delta_stepping, DecisionReason::parallel_work}, // E == parallel, degree == repair+1.
        {{6, 1, 8}, 2, Strategy::incremental, DecisionReason::fallback}, // E == parallel-1.
        {{6, 1, 7}, 1, Strategy::incremental, DecisionReason::fallback},
        {{6, 1, 7}, 0, Strategy::incremental, DecisionReason::fallback}, // Runtime default is unspecified.
        {{0, 2, 1}, 2, Strategy::incremental, DecisionReason::local_degree}, // Degree rule precedes parallel.
        {{7, 99, 8}, 2, Strategy::dijkstra, DecisionReason::small_graph}, // Small precedes degree.
        {{0, 0, 6}, 2, Strategy::delta_stepping, DecisionReason::parallel_work}, // E > parallel.
        {{0, 1, 7}, 4, Strategy::delta_stepping, DecisionReason::parallel_work},
        {{std::numeric_limits<EdgeOffset>::max() - 1, 0, std::numeric_limits<EdgeOffset>::max()},
            2, Strategy::dijkstra, DecisionReason::small_graph}
    }};
    for (const auto& item : cases) {
        std::vector<InputEdge> records{{0, 1, 10}, {1, 2, 0}, {1, 3, 1}, {2, 4, 0},
                                      {3, 4, 0}, {4, 2, 0}, {5, 6, 7}};
        const auto graph = CSRGraph::from_edges(7, records);
        require(graph.edge_count() == 7 && graph.degree(1) == 2, "Boundary fixture has intended E and destination degree");
        const PolicyConfig config{PolicyKind::heuristic, NoEffectMode::shared_fast_path, {16, item.workers}, item.thresholds};
        auto a = AdaptiveSSSPEngine::initialize(graph, 0, config);
        auto b = AdaptiveSSSPEngine::initialize(graph, 0, config);
        for (const auto weight : {5, 4}) {
            const auto result = update(a, b, records, 0, weight, config);
            require(result.decision.selected == item.strategy && result.decision.reason == item.reason &&
                    result.update.vertices_improved == 4, "Exact heuristic boundary, reason, and repeated effective updates");
        }
        std::int64_t weight = 3;
        for (const auto override : strategies) {
            const auto result = update(a, b, records, 0, weight--, config, override);
            require(result.decision.selected == override && result.decision.reason == DecisionReason::forced,
                    "Forced override takes precedence over every heuristic branch");
        }
        const auto final = update(a, b, records, 0, 0, config);
        require(final.decision.selected == item.strategy && final.decision.reason == item.reason,
                "Heuristic resumes coherently after forced strategies");
    }
    PolicyConfig defaults;
    defaults.kind = PolicyKind::heuristic;
    auto a = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(2, {{0, 1, 10}}), 0, defaults);
    const auto result = a.decrease(0, 1, 5);
    require(result.decision.reason == DecisionReason::small_graph, "Opt-in heuristic defaults are usable");
    for (const auto& invalid : {HeuristicConfig{7, 1, 7}, HeuristicConfig{8, 1, 7}, HeuristicConfig{0, 0, 0},
        HeuristicConfig{std::numeric_limits<EdgeOffset>::max(), 0, std::numeric_limits<EdgeOffset>::max()}}) {
        for (const auto policy : policies) {
            test::require_throws<std::invalid_argument>([&] {
                (void)AdaptiveSSSPEngine::initialize(a.graph(), 0, {policy, NoEffectMode::shared_fast_path, {1, 2}, invalid});
            }, "threshold");
        }
    }
    auto invalid_config = defaults;
    invalid_config.parallel.delta = 0;
    test::require_throws<std::invalid_argument>([&] {
        (void)AdaptiveSSSPEngine::initialize(a.graph(), 0, invalid_config);
    }, "delta");
    invalid_config.parallel = {1, -1};
    test::require_throws<std::invalid_argument>([&] {
        (void)AdaptiveSSSPEngine::initialize(a.graph(), 0, invalid_config);
    }, "threads");
    auto metrics = sentinel();
    const auto before = a.distances();
    const auto weights = a.graph().weights();
    for (const auto weight : {std::int64_t{-1}, std::int64_t{6}, std::int64_t{4294967296LL}}) {
        test::require_throws<std::invalid_argument>([&] { (void)a.decrease(0, 1, weight, &metrics); }, "weight");
    }
    test::require_throws<std::out_of_range>([&] { (void)a.decrease(2, 1, 0, &metrics); }, "");
    test::require_throws<std::out_of_range>([&] { (void)a.decrease(1, 0, 0, &metrics); }, "");
    test::require_throws<std::invalid_argument>([&] {
        (void)a.decrease(0, 1, 0, &metrics, static_cast<Strategy>(99));
    }, "strategy");
    require(a.distances() == before && a.graph().weights() == weights && metric_values(metrics) == metric_values(sentinel()),
            "Invalid heuristic requests preserve state and metrics");
    (void)a.decrease(0, 1, 0);
    require(a.distances()[1] == 0, "Heuristic remains reusable after rejected requests");
}

void heuristic_randomized() {
    std::mt19937 random(0x4B22026U);
    for (unsigned trial = 0; trial < 72; ++trial) {
        const auto n = static_cast<VertexId>(1 + random() % 12U);
        std::vector<InputEdge> original;
        for (VertexId u = 0; u < n; ++u) {
            for (VertexId v = 0; v < n; ++v) {
                const bool include = trial % 4 == 0 ? random() % 7U == 0 :
                    (trial % 4 == 1 ? random() % 2U == 0 : (trial % 4 == 2 ? u == 0 || v == n - 1 : v == u + 1));
                if (include) { original.push_back({u, v, static_cast<std::int64_t>(trial % 3 == 0 ? random() : random() % 32U)}); }
            }
        }
        const auto graph = CSRGraph::from_edges(n, original);
        const auto small = trial % 4 == 0 ? graph.edge_count() : EdgeOffset{0};
        const HeuristicConfig thresholds{small, trial % 4 == 1 ? n : (trial % 4 == 2 ? 0U : 1U),
                                         small + 1 + trial % 3};
        const PolicyConfig config{PolicyKind::heuristic,
            trial % 2 == 0 ? NoEffectMode::shared_fast_path : NoEffectMode::execute_selected,
            {deltas[trial % deltas.size()], trial % 5 == 0 ? 0 : (trial % 5 == 1 ? 1 : (trial % 12 == 0 ? 4 : 2))}, thresholds};
        for (VertexId source = 0; source < n; ++source) {
            auto records = original;
            auto a = AdaptiveSSSPEngine::initialize(graph, source, config);
            auto b = AdaptiveSSSPEngine::initialize(graph, source, config);
            std::size_t index = 0;
            for (unsigned step = 0; step < 24 && !records.empty(); ++step) {
                if (step % 3 != 0) { index = static_cast<std::size_t>(random()) % records.size(); }
                const auto old = static_cast<std::uint64_t>(records[index].weight);
                const auto next = step % 5 == 0 ? old : static_cast<std::uint64_t>(random()) % (old + 1);
                const auto forced = step % 4 == 0 ? std::optional<Strategy>{strategies[(step + trial) % strategies.size()]} : std::nullopt;
                (void)update(a, b, records, index, static_cast<std::int64_t>(next), config, forced);
            }
        }
    }
}

void low_degree_counterexample() {
    constexpr VertexId n = 512;
    const PolicyConfig config{PolicyKind::heuristic, NoEffectMode::shared_fast_path, {16, 2}, {0, 1, 1}};
    for (const bool broad : {false, true}) {
        std::vector<InputEdge> records{{0, 1, 100}, {1, 2, 1}};
        for (VertexId u = broad ? 2U : 3U; u < n - 1; ++u) { records.push_back({u, u + 1, 1}); }
        if (!broad) { records.push_back({3, 3, 1}); }
        const auto graph = CSRGraph::from_edges(n, records);
        require(graph.edge_count() == n - 1 && graph.degree(1) == 1, "Counterexamples share E and destination degree");
        auto a = AdaptiveSSSPEngine::initialize(graph, 0, config);
        auto b = AdaptiveSSSPEngine::initialize(graph, 0, config);
        const auto result = update(a, b, records, 0, 0, config);
        require(result.decision.selected == Strategy::incremental && result.decision.reason == DecisionReason::local_degree &&
                result.update.vertices_improved == (broad ? n - 1 : 2U),
                "Same degree-one decision can affect two vertices or almost the entire graph");
    }
}

void construction_and_validation() {
    static_assert(!std::is_move_constructible_v<AdaptiveSSSPEngine> && !std::is_copy_constructible_v<AdaptiveSSSPEngine>);
    static_assert(std::is_same_v<decltype(std::declval<AdaptiveSSSPEngine&>().graph()), const CSRGraph&>);
    static_assert(std::is_same_v<decltype(std::declval<AdaptiveSSSPEngine&>().distances()), const std::vector<Distance>&>);
    auto graph = CSRGraph::from_edges(4, {{0, 1, 10}, {1, 2, 20}});
    auto engine = AdaptiveSSSPEngine::initialize(graph, 0);
    graph.replace_weight(0, 1, 0);
    require(engine.graph().weight(0, 1) == 10 && engine.distances()[2] == 30, "Input graph isolation");
    auto nonzero = AdaptiveSSSPEngine::initialize(graph, 1);
    require(nonzero.source() == 1 && nonzero.distances()[0] == unreachable_distance, "Nonzero fixed source");
    auto moved = AdaptiveSSSPEngine::initialize(std::move(graph), 0);
    require(graph.vertex_count() == 0 && moved.distances()[2] == 20, "Direct nonmovable factory construction");
    test::require_throws<std::out_of_range>([] { (void)AdaptiveSSSPEngine::initialize(CSRGraph{}, 0); }, "source");
    test::require_throws<std::out_of_range>([&] { (void)AdaptiveSSSPEngine::initialize(engine.graph(), 4); }, "source");
    for (const auto& config : {PolicyConfig{static_cast<PolicyKind>(99), NoEffectMode::shared_fast_path, {1, 2}},
        PolicyConfig{PolicyKind::always_incremental, static_cast<NoEffectMode>(99), {1, 2}},
        PolicyConfig{PolicyKind::always_incremental, NoEffectMode::shared_fast_path, {0, 2}},
        PolicyConfig{PolicyKind::always_incremental, NoEffectMode::shared_fast_path, {1, -1}}}) {
        test::require_throws<std::invalid_argument>([&] { (void)AdaptiveSSSPEngine::initialize(engine.graph(), 0, config); }, "");
    }
    const auto before = engine.distances();
    const auto weights = engine.graph().weights();
    auto metrics = sentinel();
    const auto preserved = [&] {
        require(engine.distances() == before && engine.graph().weights() == weights &&
                metric_values(metrics) == metric_values(sentinel()), "Invalid call preserves state and every metric field");
    };
    for (const auto strategy : strategies) {
        for (const auto weight : {std::int64_t{-1}, std::int64_t{11}, std::int64_t{4294967296LL},
                                   std::numeric_limits<std::int64_t>::max()}) {
            test::require_throws<std::invalid_argument>([&] { (void)engine.decrease(0, 1, weight, &metrics, strategy); }, "weight");
            preserved();
        }
        for (const auto& endpoints : {std::pair<std::uint64_t, std::uint64_t>{4, 1}, {0, 4}, {1, 0},
                                      {std::numeric_limits<std::uint64_t>::max(), 0},
                                      {0, std::numeric_limits<std::uint64_t>::max()}}) {
            test::require_throws<std::out_of_range>([&] {
                (void)engine.decrease(endpoints.first, endpoints.second, 0, &metrics, strategy);
            }, "");
            preserved();
        }
    }
    test::require_throws<std::invalid_argument>([&] {
        (void)engine.decrease(0, 1, 0, &metrics, static_cast<Strategy>(99));
    }, "strategy");
    preserved();
    (void)engine.decrease(0, 1, 0, &metrics, Strategy::delta_stepping);
    (void)engine.decrease(1, 2, 0, &metrics, Strategy::incremental);
    require(engine.distances()[2] == 0, "Engine reusable and coherent after invalid requests");
}

void switching_and_boundaries() {
    for (const auto first : strategies) {
        for (const auto second : strategies) {
            std::vector<InputEdge> records{{0, 1, 100}, {1, 2, 4294967295LL}, {2, 3, 4294967295LL},
                                          {3, 1, 0}, {4, 4, 0}};
            const PolicyConfig config{PolicyKind::always_incremental, NoEffectMode::execute_selected, {16, 2}};
            auto a = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(5, records), 0, config);
            auto b = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(5, records), 0, config);
            update(a, b, records, 0, 80, config, first);
            update(a, b, records, 0, 60, config, second);
            update(a, b, records, 1, 4294967294LL, config, Strategy::incremental);
            require(a.distances()[3] > CSRGraph::max_edge_weight, "Wide distances survive strategy changes");
            update(a, b, records, 1, 0, config, Strategy::dijkstra);
            update(a, b, records, 2, 0, config, Strategy::delta_stepping); // Zero cycle.
            update(a, b, records, 0, 0, config, Strategy::incremental);
        }
    }
    for (const auto policy : policies) {
        for (const auto mode : {NoEffectMode::shared_fast_path, NoEffectMode::execute_selected}) {
            for (const auto delta : deltas) {
                std::vector<InputEdge> records{{0, 0, 4294967295LL}};
                const PolicyConfig config{policy, mode, {delta, 1}};
                auto a = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(1, records), 0, config);
                auto b = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(1, records), 0, config);
                update(a, b, records, 0, 1, config); // cap=0, no effect.
                update(a, b, records, 0, 0, config);
                update(a, b, records, 0, 0, config);
            }
        }
    }
}

void fast_paths() {
    for (const auto policy : policies) {
        for (const auto mode : {NoEffectMode::shared_fast_path, NoEffectMode::execute_selected}) {
            std::vector<InputEdge> records{{0, 1, 0}, {0, 2, 1}, {1, 2, 10}, {3, 4, 20}, {2, 1, 0}};
            const PolicyConfig config{policy, mode, {3, 2}};
            auto a = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(5, records), 0, config);
            auto b = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(5, records), 0, config);
            update(a, b, records, 2, 10, config); // Equal, never executes a backend.
            update(a, b, records, 2, 9, config);
            update(a, b, records, 3, 0, config); // Unreachable tail.
            update(a, b, records, 2, 1, config, Strategy::delta_stepping); // Equal-cost path.
            update(a, b, records, 2, 0, config, Strategy::incremental); // Must use committed earlier weights.
            update(a, b, records, 1, 0, config, Strategy::dijkstra);
        }
    }
}

void randomized() {
    std::mt19937 random(0x4B12026U);
    for (unsigned trial = 0; trial < 72; ++trial) {
        const auto n = static_cast<VertexId>(1 + random() % 10U);
        std::vector<InputEdge> original;
        for (VertexId u = 0; u < n; ++u) {
            for (VertexId v = 0; v < n; ++v) {
                const bool include = trial % 4 == 0 ? random() % 7U == 0 :
                    (trial % 4 == 1 ? random() % 2U == 0 : (trial % 4 == 2 ? u == 0 || v == n - 1 : v == u + 1));
                if (include) { original.push_back({u, v, static_cast<std::int64_t>(trial % 3 == 0 ? random() : random() % 32U)}); }
            }
        }
        const auto graph = CSRGraph::from_edges(n, original);
        const PolicyConfig config{policies[trial % 3], trial % 2 == 0 ? NoEffectMode::shared_fast_path : NoEffectMode::execute_selected,
                                  {deltas[trial % deltas.size()], trial % 8 == 0 ? 4 : 2}};
        for (VertexId source = 0; source < n; ++source) {
            auto records = original;
            auto a = AdaptiveSSSPEngine::initialize(graph, source, config);
            auto b = AdaptiveSSSPEngine::initialize(graph, source, config);
            for (unsigned step = 0; step < 18 && !records.empty(); ++step) {
                const auto index = static_cast<std::size_t>(random()) % records.size();
                const auto old = static_cast<std::uint64_t>(records[index].weight);
                const auto next = step % 5 == 0 ? old : static_cast<std::uint64_t>(random()) % (old + 1);
                const auto forced = step % 4 == 0 ? std::optional<Strategy>{} :
                    std::optional<Strategy>{strategies[(step + trial) % strategies.size()]};
                update(a, b, records, index, static_cast<std::int64_t>(next), config, forced);
            }
        }
    }
}

void independent_engines() {
    std::vector<InputEdge> records{{0, 1, 1000}};
    for (VertexId v = 2; v < 300; ++v) { records.push_back({1, v, v}); }
    const auto graph = CSRGraph::from_edges(300, records);
    const auto run = [&](unsigned offset) {
        auto local = records;
        const PolicyConfig config{PolicyKind::always_incremental, NoEffectMode::execute_selected, {16, 2}};
        auto a = AdaptiveSSSPEngine::initialize(graph, 0, config);
        auto b = AdaptiveSSSPEngine::initialize(graph, 0, config);
        for (unsigned step = 0; step < 24; ++step) {
            update(a, b, local, 0, 999 - step, config, strategies[(step + offset) % strategies.size()]);
        }
    };
    auto first = std::async(std::launch::async, run, 0);
    auto second = std::async(std::launch::async, run, 1);
    first.get();
    second.get();
    require(graph.weight(0, 1) == 1000, "Concurrent independent engines preserve shared input graph");
}
} // namespace

int main() {
    int failures = 0;
    failures += test::run("adaptive construction, ownership, invalid requests and recovery", construction_and_validation);
    failures += test::run("all ordered strategy pairs, wide distances, cycles and six deltas", switching_and_boundaries);
    failures += test::run("shared fast paths and execute-selected semantics for every policy", fast_paths);
    failures += test::run("72 seeded graph families, every source, mixed default/forced schedules", randomized);
    failures += test::run("concurrent independent engine objects and longer alternating traces", independent_engines);
    failures += test::run("heuristic branch boundaries, precedence, worker budgets and validation", heuristic_boundaries);
    failures += test::run("72 seeded heuristic graphs, repeated updates and forced switches", heuristic_randomized);
    failures += test::run("low destination degree does not bound the affected region", low_degree_counterexample);
    return failures == 0 ? 0 : 1;
}
