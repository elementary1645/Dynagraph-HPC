#pragma once

#include "dynagraph/adaptive/adaptive_sssp.hpp"
#include "sssp_test_support.hpp"
#include "test_support.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace dynagraph::test::system {
inline constexpr const char* generator_version = "system-validation-v1";
inline constexpr std::array<Strategy, 3> strategies{
    Strategy::dijkstra, Strategy::delta_stepping, Strategy::incremental};
inline constexpr std::array<const char*, 3> strategy_names{"dijkstra", "delta", "incremental"};
inline constexpr std::array<Strategy, 4> history_strategies{
    Strategy::incremental, Strategy::dijkstra, Strategy::delta_stepping, Strategy::delta_stepping};
inline constexpr std::array<const char*, 5> policy_names{
    "always_dijkstra", "always_delta_stepping", "always_incremental", "heuristic", "rotating_override"};
inline constexpr std::array<Distance, 6> deltas{1, 2, 3, 16, 4294967295ULL, unreachable_distance};

struct Update { VertexId u; VertexId v; EdgeWeight old_weight; EdgeWeight weight; };
struct Case {
    VertexId vertices = 0;
    std::vector<InputEdge> edges; // Canonical initial records, independent of CSR.
    std::vector<Update> updates;
    Distance delta = 16;
    HeuristicConfig heuristic{0, 1, 1}; // Branch probes, never benchmark tuning.
    NoEffectMode mode = NoEffectMode::shared_fast_path;
};
struct Options {
    std::string profile = "fast";
    std::uint32_t seed = 0x5C102026U;
    std::optional<std::uint32_t> case_index;
    std::optional<VertexId> source;
    int workers = 2;
    std::string executable = "test_system_correctness";
};
struct Limits { std::uint32_t cases; VertexId vertices; std::size_t edges; unsigned updates; };
inline Limits limits(const std::string& profile) {
    if (profile == "fast") { return {48, 24, 512, 16}; }
    if (profile == "stress") { return {96, 64, 1024, 48}; }
    if (profile == "extended") { return {384, 128, 4096, 128}; }
    throw std::invalid_argument("profile must be fast, stress or extended");
}
inline std::uint32_t number(const std::string& value, std::uint32_t maximum) {
    if (value.empty() || (value.size() > 1 && value.front() == '0')) {
        throw std::invalid_argument("canonical unsigned decimal required");
    }
    std::uint64_t result = 0;
    for (const char ch : value) {
        if (ch < '0' || ch > '9' || result > maximum / 10U ||
            (result == maximum / 10U && static_cast<unsigned>(ch - '0') > maximum % 10U)) {
            throw std::invalid_argument("argument outside supported integer range");
        }
        result = result * 10U + static_cast<unsigned>(ch - '0');
    }
    return static_cast<std::uint32_t>(result);
}
inline Options options(int argc, char** argv) {
    Options out; out.executable = argv[0];
    std::vector<std::string> seen;
    for (int index = 1; index < argc; index += 2) {
        const std::string key = argv[index];
        if (index + 1 >= argc || std::find(seen.begin(), seen.end(), key) != seen.end()) {
            throw std::invalid_argument("missing value or duplicate option");
        }
        seen.push_back(key);
        const std::string value = argv[index + 1];
        if (key == "--profile") { out.profile = value; }
        else if (key == "--seed") { out.seed = number(value, 0xFFFFFFFFU); }
        else if (key == "--case") { out.case_index = number(value, 383); }
        else if (key == "--source") { out.source = number(value, 4095); }
        else if (key == "--workers") { out.workers = static_cast<int>(number(value, 4)); }
        else { throw std::invalid_argument("unknown option: " + key); }
    }
    const auto bound = limits(out.profile);
    if (out.workers == 0 || (out.case_index && *out.case_index >= bound.cases) ||
        (out.source && !out.case_index)) {
        throw std::invalid_argument("workers must be 1..4; case must fit profile; source requires case");
    }
    return out;
}

// mt19937 outputs and unsigned wrap are specified. No library distributions or shuffle.
// Each case/stream is independent of sources, worker count and previous cases.
inline std::mt19937 stream(std::uint32_t root, std::uint32_t index, std::uint32_t tag) {
    return std::mt19937(root ^ (0x9E3779B9U * (index + 1U)) ^ tag);
}
inline std::size_t draw(std::mt19937& random, std::size_t bound) {
    require(bound > 0, "nonempty test sampling domain");
    return static_cast<std::size_t>(random()) % bound; // Explicit test sampling, not artifact generation.
}
inline std::size_t edge_index(const std::vector<InputEdge>& records, VertexId u, VertexId v) {
    for (std::size_t index = 0; index < records.size(); ++index) {
        if (records[index].source == u && records[index].destination == v) { return index; }
    }
    throw std::runtime_error("independent ledger: absent edge");
}
inline void apply(std::vector<InputEdge>& records, const Update& update) {
    auto& edge = records[edge_index(records, update.u, update.v)];
    require(edge.weight == update.old_weight && update.weight <= update.old_weight, "ledger transition");
    edge.weight = update.weight;
}
inline Case generate(const Options& opt, std::uint32_t index) {
    const auto bound = limits(opt.profile);
    auto topology = stream(opt.seed, index, 0xA341316CU);
    auto weights = stream(opt.seed, index, 0xC8013EA4U);
    auto requests = stream(opt.seed, index, 0xAD90777DU);
    Case out;
    const unsigned family = index % 6U;
    out.vertices = static_cast<VertexId>(2 + draw(topology, bound.vertices - 1U));
    if (family == 2) { out.vertices = std::max(VertexId{4}, out.vertices); }
    const auto n = out.vertices;
    const unsigned distribution = (index / 6U) % 4U;
    for (VertexId u = 0; u < n; ++u) {
        for (VertexId v = 0; v < n; ++v) {
            bool include = false;
            switch (family) {
            case 0: include = draw(topology, 8) == 0; break;
            case 1: include = draw(topology, 2) == 0; break;
            case 2: // Two components, with the last vertex isolated.
                include = u != n - 1 && v != n - 1 && u / (n / 2) == v / (n / 2) &&
                          (v == u + 1 || draw(topology, 4) == 0); break;
            case 3: include = v / 2 == u / 2 + 1; break;
            case 4: include = (u == 0 && v > 0) || (u > 0 && u < n - 1 && v == n - 1); break;
            case 5: include = v == u + 1 || (v > u + 1 && draw(topology, 8) == 0); break;
            default: break;
            }
            // Guarantee a usable trace without making the isolated vertex incident.
            include = include || (u == 0 && v == 1);
            if (!include) { continue; }
            std::uint32_t weight = 0;
            if (distribution == 0) { weight = static_cast<std::uint32_t>(1 + draw(weights, 31)); }
            else if (distribution == 1) { weight = draw(weights, 4) == 0 ? static_cast<std::uint32_t>(1 + draw(weights, 31)) : 0; }
            else if (distribution == 2) {
                constexpr std::array<std::uint32_t, 4> values{0, 1, 0xFFFFFFFEU, 0xFFFFFFFFU};
                weight = values[draw(weights, values.size())];
            } else { weight = static_cast<std::uint32_t>(weights()); }
            out.edges.push_back({u, v, weight});
        }
    }
    // Explicit Fisher-Yates subset when dense cases exceed the tier edge budget.
    if (out.edges.size() > bound.edges) {
        for (auto size = out.edges.size(); size > 1; --size) {
            std::swap(out.edges[size - 1], out.edges[draw(topology, size)]);
        }
        out.edges.resize(bound.edges);
        std::sort(out.edges.begin(), out.edges.end(), [](const InputEdge& a, const InputEdge& b) {
            return a.source < b.source || (a.source == b.source && a.destination < b.destination);
        });
    }
    auto ledger = out.edges;
    std::size_t previous = 0;
    for (unsigned step = 0; step < bound.updates; ++step) {
        std::vector<std::size_t> positive;
        for (std::size_t e = 0; e < ledger.size(); ++e) { if (ledger[e].weight > 0) { positive.push_back(e); } }
        const bool equal = step % 8U == 0 || step % 8U == 3 || step % 8U == 6;
        std::size_t chosen = draw(requests, ledger.size());
        if (step % 8U == 2 || step % 8U == 3) { chosen = previous; }
        else if (!equal && !positive.empty()) { chosen = positive[draw(requests, positive.size())]; }
        auto& edge = ledger[chosen];
        const auto old = static_cast<EdgeWeight>(edge.weight);
        auto next = old;
        if (!equal && old > 0) {
            next = step % 8U == 4 ? 0 : static_cast<EdgeWeight>(old - 1 - draw(requests, old));
        }
        out.updates.push_back({static_cast<VertexId>(edge.source), static_cast<VertexId>(edge.destination), old, next});
        edge.weight = next; previous = chosen;
    }
    out.delta = deltas[index % deltas.size()];
    out.mode = (index / 24U) % 2U == 0 ? NoEffectMode::shared_fast_path : NoEffectMode::execute_selected;
    if (index % 3U == 0) { out.heuristic = {static_cast<EdgeOffset>(out.edges.size()), 0, static_cast<EdgeOffset>(out.edges.size() + 1)}; }
    else if (index % 3U == 1) { out.heuristic = {0, 1, 1}; }
    else { out.heuristic = {0, 0, static_cast<EdgeOffset>(out.edges.size() + 1)}; }
    return out;
}

// Record-based expected topology: no CSR construction/traversal in the oracle.
inline void graph_equal(const CSRGraph& graph, VertexId vertices, const std::vector<InputEdge>& records) {
    require(graph.vertex_count() == vertices && graph.edge_count() == records.size(), "graph dimensions");
    std::vector<EdgeOffset> offsets(static_cast<std::size_t>(vertices) + 1, 0);
    std::vector<VertexId> destinations;
    std::vector<EdgeWeight> weights;
    for (const auto& edge : records) {
        ++offsets[static_cast<std::size_t>(edge.source) + 1];
        destinations.push_back(static_cast<VertexId>(edge.destination));
        weights.push_back(static_cast<EdgeWeight>(edge.weight));
    }
    for (std::size_t v = 1; v < offsets.size(); ++v) { offsets[v] += offsets[v - 1]; }
    require(graph.offsets() == offsets && graph.destinations() == destinations && graph.weights() == weights,
            "complete authoritative topology/weight mismatch");
}
inline bool same_records(const std::vector<InputEdge>& a, const std::vector<InputEdge>& b) {
    if (a.size() != b.size()) { return false; }
    for (std::size_t index = 0; index < a.size(); ++index) {
        if (a[index].source != b[index].source || a[index].destination != b[index].destination ||
            a[index].weight != b[index].weight) { return false; }
    }
    return true;
}
inline std::vector<Distance> oracle(VertexId vertices, const std::vector<InputEdge>& records, VertexId source) {
    require(vertices > 0 && vertices <= 4096 && source < vertices && records.size() <= 65536, "bounded oracle domain");
    // At most V-1 synchronous edges per path: <=4095*UINT32_MAX, far below uint64 infinity.
    return bellman_ford(vertices, records, source);
}
inline void checkpoint(const CSRGraph& graph, const std::vector<Distance>& distances,
                       VertexId vertices, const std::vector<InputEdge>& ledger, VertexId source) {
    graph_equal(graph, vertices, ledger);
    require(distances == oracle(vertices, ledger, source), "independent Bellman-Ford checkpoint");
}
inline void outcome(const DecreaseResult& result, const Update& update,
                    const std::vector<Distance>& before, const std::vector<Distance>& expected) {
    std::uint64_t improved = 0;
    for (std::size_t v = 0; v < before.size(); ++v) {
        require(expected[v] <= before[v] && (expected[v] == unreachable_distance) == (before[v] == unreachable_distance),
                "monotonicity/invariant reachability");
        if (expected[v] < before[v]) { ++improved; }
    }
    const auto kind = update.weight == update.old_weight ? DecreaseOutcome::unchanged_weight :
        (improved == 0 ? DecreaseOutcome::weight_only : DecreaseOutcome::distances_repaired);
    require(result.old_weight == update.old_weight && result.new_weight == update.weight &&
            result.vertices_improved == improved && result.outcome == kind, "outcome/old/new/improvement count");
}
inline Case history_case() {
    Case c; c.vertices = 96; c.edges = {{0, 1, 100}, {0, 95, 500}};
    for (VertexId v = 2; v < 95; ++v) { c.edges.push_back({1, v, v}); c.edges.push_back({v, 95, 1}); }
    std::sort(c.edges.begin(), c.edges.end(), [](const InputEdge& a, const InputEdge& b) {
        return a.source < b.source || (a.source == b.source && a.destination < b.destination);
    });
    c.updates = {{0, 1, 100, 90}, {0, 95, 500, 400}, {0, 95, 400, 400}, {0, 1, 90, 80}};
    return c;
}
template <typename State, typename Call>
void history_step(State& state, std::vector<InputEdge>& ledger, const Update& u, Call call) {
    const auto before = oracle(96, ledger, 0);
    auto next = ledger; apply(next, u);
    const auto expected = oracle(96, next, 0);
    const auto result = call(u);
    outcome(result, u, before, expected); ledger = std::move(next);
    checkpoint(state.graph(), state.distances(), 96, ledger, 0);
}
template <typename State, typename Call>
void history_prefix(State& state, std::vector<InputEdge>& ledger, Call call) {
    checkpoint(state.graph(), state.distances(), 96, ledger, 0);
    for (const auto& u : history_case().updates) { history_step(state, ledger, u, call); }
}
struct Counts {
    std::uint64_t traces = 0, checkpoints = 0, updates = 0;
    std::uint64_t generation_hash = 14695981039346656037ULL, state_hash = 14695981039346656037ULL;
    std::array<std::uint64_t, 7> decisions{};
    int minimum_workers = 5, maximum_workers = 0;
};
inline void hash(std::uint64_t& value, std::uint64_t number_value) {
    for (unsigned byte = 0; byte < 8; ++byte) { value ^= (number_value >> (8U * byte)) & 255U; value *= 1099511628211ULL; }
}
inline void case_hash(std::uint64_t& value, const Case& test_case) {
    hash(value, test_case.vertices); hash(value, test_case.edges.size()); hash(value, test_case.updates.size());
    for (const auto& e : test_case.edges) { hash(value, static_cast<std::uint64_t>(e.source)); hash(value, static_cast<std::uint64_t>(e.destination)); hash(value, static_cast<std::uint64_t>(e.weight)); }
    for (const auto& u : test_case.updates) { hash(value, u.u); hash(value, u.v); hash(value, u.old_weight); hash(value, u.weight); }
}
inline void vector_print(const char* label, const std::vector<Distance>& values) {
    std::cerr << label;
    for (const auto value : values) { std::cerr << ' ' << value; }
    std::cerr << '\n';
}
struct Context {
    std::string policy = "initialization", selected = "unavailable", actual_workers = "unavailable";
    std::int64_t step = -1;
    std::vector<Distance> expected, actual;
};
inline void diagnostic(const Options& opt, std::uint32_t index, VertexId source, const Case& c, const Context& ctx) {
    std::cerr << "generator=" << generator_version << " seed=" << opt.seed << " case=" << index << " source=" << source
              << " update=" << ctx.step << " policy=" << ctx.policy << " selected=" << ctx.selected << " delta=" << c.delta
              << " requested_workers=" << opt.workers << " actual_workers=" << ctx.actual_workers << '\n';
    std::cerr << "no_effect=" << (c.mode == NoEffectMode::shared_fast_path ? "shared_fast_path" : "execute_selected")
              << " heuristic=" << c.heuristic.small_graph_edges << ',' << c.heuristic.repair_max_degree << ',' << c.heuristic.parallel_min_edges << '\n';
    std::cerr << "initial_graph " << c.vertices << ' ' << c.edges.size() << '\n';
    for (const auto& e : c.edges) { std::cerr << e.source << ' ' << e.destination << ' ' << e.weight << '\n'; }
    std::cerr << "executed_trace_prefix (last entry is attempted on exception):\n";
    for (std::size_t step = 0; step < c.updates.size() && static_cast<std::int64_t>(step) <= ctx.step; ++step) {
        const auto& u = c.updates[step];
        std::cerr << step << ' ' << u.u << ' ' << u.v << ' ' << u.old_weight << ' ' << u.weight << '\n';
    }
    std::cerr << "first_mismatching_vertex=";
    std::size_t v = 0;
    while (v < ctx.expected.size() && v < ctx.actual.size() && ctx.expected[v] == ctx.actual[v]) { ++v; }
    if (v == ctx.expected.size() && v == ctx.actual.size()) { std::cerr << "none"; } else { std::cerr << v; }
    std::cerr << '\n'; vector_print("expected", ctx.expected); vector_print("actual (pre-call snapshot if call threw)", ctx.actual);
    std::cerr << "reproduce: '" << opt.executable << "' --profile " << opt.profile << " --seed " << opt.seed
              << " --case " << index << " --source " << source << " --workers " << opt.workers << '\n';
}
inline void trace(const Case& c, VertexId source, const Options& opt, std::uint32_t index, Counts& counts) {
    Context ctx;
    auto ledger = c.edges;
    try {
        ctx.expected = oracle(c.vertices, ledger, source);
        auto shuffled = c.edges;
        auto permutation = stream(opt.seed, index, 0x7E95761EU);
        for (auto size = shuffled.size(); size > 1; --size) { std::swap(shuffled[size - 1], shuffled[draw(permutation, size)]); }
        const auto caller_records = shuffled;
        const auto input = CSRGraph::from_edges(c.vertices, shuffled);
        auto repair = IncrementalSSSPState::initialize(input, source);
        const PolicyConfig base{PolicyKind::always_incremental, c.mode, {c.delta, opt.workers}, c.heuristic};
        auto d = AdaptiveSSSPEngine::initialize(input, source, {PolicyKind::always_dijkstra, c.mode, base.parallel, c.heuristic});
        auto p = AdaptiveSSSPEngine::initialize(input, source, {PolicyKind::always_delta_stepping, c.mode, base.parallel, c.heuristic});
        auto r = AdaptiveSSSPEngine::initialize(input, source, base);
        auto h = AdaptiveSSSPEngine::initialize(input, source, {PolicyKind::heuristic, c.mode, base.parallel, c.heuristic});
        auto rotating = AdaptiveSSSPEngine::initialize(input, source, base);
        const std::array<AdaptiveSSSPEngine*, 5> engines{&d, &p, &r, &h, &rotating};
        const auto compare = [&](const CSRGraph& graph, const std::vector<Distance>& distances) {
            ctx.actual = distances;
            require(distances == ctx.expected, "complete distance vector mismatch");
            graph_equal(graph, c.vertices, ledger);
        };
        const auto check = [&] {
            ctx.policy = "standalone_incremental"; ctx.selected = "unavailable"; ctx.actual_workers = "unavailable";
            compare(repair.graph(), repair.distances());
            for (std::size_t policy = 0; policy < engines.size(); ++policy) {
                ctx.policy = policy_names[policy]; compare(engines[policy]->graph(), engines[policy]->distances());
            }
            // Reconstruct from the external ledger, never from an engine graph.
            const auto fresh = CSRGraph::from_edges(c.vertices, ledger);
            ctx.policy = "standalone_dijkstra"; compare(fresh, dijkstra(fresh, source).distances);
            ctx.policy = "standalone_delta"; DeltaSteppingMetrics metrics;
            const auto result = delta_stepping(fresh, source, {c.delta, opt.workers}, &metrics);
            ctx.actual_workers = std::to_string(metrics.actual_thread_count);
            counts.minimum_workers = std::min(counts.minimum_workers, metrics.actual_thread_count);
            counts.maximum_workers = std::max(counts.maximum_workers, metrics.actual_thread_count);
            require(metrics.actual_thread_count >= 1 && metrics.actual_thread_count <= opt.workers, "observed worker count");
            compare(fresh, result.distances);
            graph_equal(input, c.vertices, c.edges);
            require(same_records(shuffled, caller_records), "caller record values and order unchanged");
            for (const auto distance : ctx.expected) { hash(counts.state_hash, distance); }
            ++counts.checkpoints;
        };
        check();
        for (std::size_t step = 0; step < c.updates.size(); ++step) {
            ctx.step = static_cast<std::int64_t>(step);
            const auto& u = c.updates[step];
            const auto before = ctx.expected;
            apply(ledger, u); ctx.expected = oracle(c.vertices, ledger, source);
            ctx.policy = "standalone_incremental"; ctx.selected = "incremental"; ctx.actual_workers = "unavailable"; ctx.actual = repair.distances();
            RepairMetrics repair_metrics;
            const bool measured = step % 2 == 0;
            const auto repair_result = repair.decrease(u.u, u.v, u.weight, measured ? &repair_metrics : nullptr);
            ctx.actual = repair.distances();
            outcome(repair_result, u, before, ctx.expected);
            compare(repair.graph(), repair.distances());
            for (std::size_t policy = 0; policy < engines.size(); ++policy) {
                auto& engine = *engines[policy];
                ctx.policy = policy_names[policy]; ctx.selected = "unavailable"; ctx.actual_workers = "unavailable"; ctx.actual = engine.distances();
                AdaptiveMetrics metrics;
                const auto forced = policy == 4 ? std::optional<Strategy>{strategies[step % 3]} : std::nullopt;
                const auto result = engine.decrease(u.u, u.v, u.weight, measured ? &metrics : nullptr, forced);
                ctx.actual = engine.distances();
                ctx.selected = result.decision.selected ? strategy_names[static_cast<std::size_t>(*result.decision.selected)] : "none";
                if (measured && metrics.parallel.actual_threads) { ctx.actual_workers = std::to_string(*metrics.parallel.actual_threads); }
                outcome(result.update, u, before, ctx.expected);
                compare(engine.graph(), engine.distances()); // Correctness independent of selection assertions below.
                const auto& decision = result.decision;
                ++counts.decisions[static_cast<std::size_t>(decision.reason)];
                if (u.weight == u.old_weight) {
                    require(decision.route == DecisionRoute::unchanged && !decision.selected && decision.reason == DecisionReason::equal_weight, "equal request bypass");
                } else if (c.mode == NoEffectMode::shared_fast_path && result.update.vertices_improved == 0) {
                    require(decision.route == DecisionRoute::weight_only && !decision.selected && decision.reason == DecisionReason::no_distance_effect, "shared weight-only bypass");
                } else {
                    require(decision.route == DecisionRoute::execute && decision.selected.has_value(), "executed strategy present");
                    if (policy != 3) {
                        const auto expected_strategy = forced ? *forced : strategies[policy];
                        require(decision.selected == expected_strategy && decision.reason == DecisionReason::forced, "fixed/forced strategy contract");
                    } else {
                        std::size_t degree = 0;
                        for (const auto& edge : ledger) { if (edge.source == u.v) { ++degree; } }
                        const bool small = ledger.size() <= c.heuristic.small_graph_edges;
                        const bool local = degree <= c.heuristic.repair_max_degree;
                        const bool parallel = ledger.size() >= c.heuristic.parallel_min_edges && opt.workers >= 2;
                        const auto expected_reason = small ? DecisionReason::small_graph : local ? DecisionReason::local_degree :
                            parallel ? DecisionReason::parallel_work : DecisionReason::fallback;
                        const auto expected_strategy = small ? Strategy::dijkstra : (!local && parallel ? Strategy::delta_stepping : Strategy::incremental);
                        require(decision.reason == expected_reason && decision.selected == expected_strategy, "heuristic branch contract");
                    }
                }
            }
            check(); ++counts.updates;
        }
        ++counts.traces;
    } catch (...) { diagnostic(opt, index, source, c, ctx); throw; }
}
} // namespace dynagraph::test::system
