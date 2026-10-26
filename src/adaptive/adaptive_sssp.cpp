#include "dynagraph/adaptive/adaptive_sssp.hpp"

#include <limits>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace dynagraph {
namespace {
static_assert(noexcept(std::declval<std::vector<Distance>&>().swap(std::declval<std::vector<Distance>&>())));
static_assert(std::is_nothrow_copy_assignable_v<AdaptiveMetrics>);
static_assert(std::is_nothrow_copy_assignable_v<DecreaseResult>);
static_assert(std::is_nothrow_copy_constructible_v<AdaptiveUpdateResult>);
static_assert(std::is_nothrow_move_constructible_v<AdaptiveUpdateResult>);
static_assert(std::is_nothrow_destructible_v<CSRGraph>);
static_assert(std::is_nothrow_destructible_v<SSSPResult>);
static_assert(std::is_nothrow_destructible_v<DeltaSteppingMetrics>);

void validate_policy(PolicyKind policy) {
    switch (policy) {
    case PolicyKind::always_dijkstra:
    case PolicyKind::always_delta_stepping:
    case PolicyKind::always_incremental:
    case PolicyKind::heuristic: return;
    }
    throw std::invalid_argument("invalid policy kind");
}

DecisionResult policy_decision(const PolicyConfig& config, const CSRGraph& graph, VertexId destination) {
    switch (config.kind) {
    case PolicyKind::always_dijkstra: return {DecisionRoute::execute, Strategy::dijkstra, DecisionReason::forced};
    case PolicyKind::always_delta_stepping: return {DecisionRoute::execute, Strategy::delta_stepping, DecisionReason::forced};
    case PolicyKind::always_incremental: return {DecisionRoute::execute, Strategy::incremental, DecisionReason::forced};
    case PolicyKind::heuristic:
        // Validated destination; degree is a pair of CSR offsets, not a traversal.
        // All features precede execution; no counters, clocks, runtime team query,
        // allocation, graph scan or history enters the decision.
        if (graph.edge_count() <= config.heuristic.small_graph_edges) {
            return {DecisionRoute::execute, Strategy::dijkstra, DecisionReason::small_graph};
        }
        if (graph.degree(destination) <= config.heuristic.repair_max_degree) {
            return {DecisionRoute::execute, Strategy::incremental, DecisionReason::local_degree};
        }
        if (graph.edge_count() >= config.heuristic.parallel_min_edges && config.parallel.thread_count >= 2) {
            return {DecisionRoute::execute, Strategy::delta_stepping, DecisionReason::parallel_work};
        }
        return {DecisionRoute::execute, Strategy::incremental, DecisionReason::fallback};
    }
    throw std::invalid_argument("invalid policy kind"); // Factory validation + immutable config exclude this.
}

void validate_strategy(Strategy strategy) {
    switch (strategy) {
    case Strategy::dijkstra:
    case Strategy::delta_stepping:
    case Strategy::incremental: return;
    }
    throw std::invalid_argument("invalid forced strategy");
}

void add(std::uint64_t& target, std::uint64_t value, bool& saturated) noexcept {
    if (value > std::numeric_limits<std::uint64_t>::max() - target) {
        target = std::numeric_limits<std::uint64_t>::max();
        saturated = true;
    } else { target += value; }
}

DeltaWorkSummary summarize(const DeltaSteppingMetrics& metrics) noexcept {
    DeltaWorkSummary result;
    result.actual_threads = metrics.actual_thread_count;
    result.buckets_processed = metrics.buckets_processed;
    result.light_edge_passes = metrics.light_edge_passes;
    result.heavy_edge_passes = metrics.heavy_edge_passes;
    result.stale_entries = metrics.stale_entries;
    result.counters_saturated = metrics.counters_saturated;
    for (const auto& thread : metrics.per_thread) {
        add(result.edges_examined, thread.edges_examined, result.counters_saturated);
        add(result.relaxation_attempts, thread.relaxation_attempts, result.counters_saturated);
        add(result.successful_relaxations, thread.successful_relaxations, result.counters_saturated);
        add(result.cas_retries, thread.cas_retries, result.counters_saturated);
    }
    return result;
}
} // namespace

AdaptiveSSSPEngine::AdaptiveSSSPEngine(CSRGraph&& graph, VertexId source, PolicyConfig config)
    : state_(IncrementalSSSPState::initialize(std::move(graph), source)), config_(config) {}

AdaptiveSSSPEngine AdaptiveSSSPEngine::initialize(CSRGraph graph, VertexId source, PolicyConfig config) {
    validate_policy(config.kind);
    if (config.no_effect != NoEffectMode::shared_fast_path && config.no_effect != NoEffectMode::execute_selected) {
        throw std::invalid_argument("invalid no-effect mode");
    }
    if (config.parallel.delta == 0 || config.parallel.thread_count < 0) {
        throw std::invalid_argument("delta must be positive and threads nonnegative");
    }
    if (config.heuristic.small_graph_edges >= config.heuristic.parallel_min_edges) {
        throw std::invalid_argument("heuristic small-graph threshold must be below parallel-work threshold");
    }
    // Direct prvalues: guaranteed C++17 elision, no named-local NRVO or heap wrapper.
    return AdaptiveSSSPEngine(std::move(graph), source, config);
}

DecreaseResult AdaptiveSSSPEngine::recompute(const IncrementalSSSPState::PreparedDecrease& request,
                                            Strategy strategy, AdaptiveMetrics* pending) {
    CSRGraph staged(state_.graph_); // Only temporary duplicate; all allocations precede commit.
    staged.replace_weight(request.u, request.v, request.replacement);
    DeltaSteppingMetrics parallel;
    auto result = strategy == Strategy::dijkstra ?
        dijkstra(staged, source(), pending == nullptr ? nullptr : &pending->dijkstra) :
        delta_stepping(staged, source(), config_.parallel, pending == nullptr ? nullptr : &parallel);
    // Delta result and per-thread metric allocation must finish before any commit.
    if (result.source != source() || result.distances.size() != state_.distances_.size()) {
        throw std::logic_error("recomputation result source/dimensions mismatch");
    }
    if (result.distances[source()] != 0) { throw std::logic_error("recomputation source distance is not zero"); }
    std::uint64_t affected = 0;
    for (std::size_t v = 0; v < result.distances.size(); ++v) {
        const auto old = state_.distances_[v];
        const auto next = result.distances[v];
        if (next > old || (next == unreachable_distance) != (old == unreachable_distance) ||
            (next != unreachable_distance && next > state_.cap_)) {
            throw std::logic_error("recomputation violates decrease/reachability/distance bounds");
        }
        if (next < old) { ++affected; } // <= validated vertex count.
    }
    if (pending != nullptr && strategy == Strategy::delta_stepping) { pending->parallel = summarize(parallel); }
    const DecreaseResult update{affected == 0 ? DecreaseOutcome::weight_only : DecreaseOutcome::distances_repaired,
                                request.previous, request.replacement, affected};
    // Last potentially throwing operation. CSR validates/locates before its write.
    state_.graph_.replace_weight(request.u, request.v, request.replacement);
    state_.distances_.swap(result.distances);
    // Only scalar publication and nonthrowing destruction remain. Marks stay clear.
    return update;
}

AdaptiveUpdateResult AdaptiveSSSPEngine::decrease(std::uint64_t u, std::uint64_t v,
    std::int64_t new_weight, AdaptiveMetrics* metrics, std::optional<Strategy> forced) {
    if (forced) { validate_strategy(*forced); }
    const auto request = state_.prepare_decrease(u, v, new_weight);
    AdaptiveMetrics pending;
    DecreaseResult update{DecreaseOutcome::unchanged_weight, request.previous, request.replacement, 0};
    if (request.previous == request.replacement) {
        pending.decision = {DecisionRoute::unchanged, std::nullopt, DecisionReason::equal_weight};
    } else if (config_.no_effect == NoEffectMode::shared_fast_path && request.seed >= state_.distances_[request.v]) {
        pending.decision = {DecisionRoute::weight_only, std::nullopt, DecisionReason::no_distance_effect};
        update.outcome = DecreaseOutcome::weight_only;
        state_.graph_.replace_weight(request.u, request.v, request.replacement);
    } else {
        pending.decision = forced ? DecisionResult{DecisionRoute::execute, *forced, DecisionReason::forced} :
                                   policy_decision(config_, state_.graph_, request.v);
        const auto strategy = *pending.decision.selected;
        pending.work_collected = metrics != nullptr;
        update = strategy == Strategy::incremental ?
            state_.repair_prepared(request, metrics == nullptr ? nullptr : &pending.repair) :
            recompute(request, strategy, metrics == nullptr ? nullptr : &pending);
    }
    // Every operation after the backend's commit is nonthrowing, including copies.
    if (metrics != nullptr) { *metrics = pending; }
    return {update, pending.decision};
}

} // namespace dynagraph
