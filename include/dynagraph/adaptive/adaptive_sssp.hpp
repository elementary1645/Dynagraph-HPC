#pragma once

#include "dynagraph/algorithms/delta_stepping.hpp"
#include "dynagraph/dynamic/incremental_sssp.hpp"

#include <optional>

namespace dynagraph {

enum class Strategy { dijkstra, delta_stepping, incremental };
enum class PolicyKind { always_dijkstra, always_delta_stepping, always_incremental };
enum class NoEffectMode { shared_fast_path, execute_selected };

struct PolicyConfig {
    PolicyKind kind = PolicyKind::always_incremental;
    NoEffectMode no_effect = NoEffectMode::shared_fast_path;
    DeltaSteppingOptions parallel{1, 0}; // Valid default, not a tuned parameter.
};

enum class DecisionRoute { unchanged, weight_only, execute };
enum class DecisionReason { equal_weight, no_distance_effect, forced };

struct DecisionResult {
    DecisionRoute route = DecisionRoute::unchanged;
    std::optional<Strategy> selected; // Engaged only when a backend was executed.
    DecisionReason reason = DecisionReason::equal_weight;
};

struct AdaptiveUpdateResult {
    DecreaseResult update;
    DecisionResult decision;
};

// Fixed-size aggregation of delta's per-thread work counters, without a vector.
struct DeltaWorkSummary {
    std::optional<int> actual_threads; // Absent unless collected for executed delta.
    std::uint64_t buckets_processed = 0;
    std::uint64_t light_edge_passes = 0;
    std::uint64_t heavy_edge_passes = 0;
    std::uint64_t stale_entries = 0;
    std::uint64_t edges_examined = 0;
    std::uint64_t relaxation_attempts = 0;
    std::uint64_t successful_relaxations = 0;
    std::uint64_t cas_retries = 0;
    bool counters_saturated = false;
};

// Replaced only on success. work_collected is false for bypass routes. Only the
// selected backend's work fields are populated; other fields reset to defaults.
struct AdaptiveMetrics {
    DecisionResult decision;
    bool work_collected = false;
    RepairMetrics repair;
    DijkstraMetrics dijkstra;
    DeltaWorkSummary parallel;
};

// Forced execution foundation only: no heuristic/model selection or timings.
// One authoritative IncrementalSSSPState; no second persistent graph/result.
// All access must be serialized against updates. Independent engines own all
// state and may execute concurrently; the OpenMP runtime may reduce team sizes.
class AdaptiveSSSPEngine {
public:
    // Copies lvalue graphs or consumes rvalues. Validates config (including
    // delta>0 and threads>=0 even for nonparallel policies), then uses Dijkstra
    // for initialization. Invalid config throws invalid_argument; invalid source
    // throws out_of_range. Failed acquisition may consume rvalue inputs.
    [[nodiscard]] static AdaptiveSSSPEngine initialize(CSRGraph graph, VertexId source,
                                                       PolicyConfig config = {});
    AdaptiveSSSPEngine(const AdaptiveSSSPEngine&) = delete;
    AdaptiveSSSPEngine& operator=(const AdaptiveSSSPEngine&) = delete;
    AdaptiveSSSPEngine(AdaptiveSSSPEngine&&) = delete;
    AdaptiveSSSPEngine& operator=(AdaptiveSSSPEngine&&) = delete;

    [[nodiscard]] VertexId source() const noexcept { return state_.source(); }
    [[nodiscard]] const CSRGraph& graph() const noexcept { return state_.graph(); }
    [[nodiscard]] const std::vector<Distance>& distances() const noexcept { return state_.distances(); }

    // Same weight/endpoint validation as standalone repair. Invalid forced enums
    // are rejected before request preparation. A forced override still obeys
    // shared fast paths. execute_selected dispatches even for strict no-effect
    // requests; incremental's intrinsic seed check can avoid propagation.
    // On any recoverable exception graph/distances/caller metrics are unchanged.
    // Reacquire distance element pointers/iterators after successful updates:
    // recomputation replaces their storage. No snapshot allocation in the return.
    [[nodiscard]] AdaptiveUpdateResult decrease(std::uint64_t u, std::uint64_t v,
        std::int64_t new_weight, AdaptiveMetrics* metrics = nullptr,
        std::optional<Strategy> forced = std::nullopt);

private:
    AdaptiveSSSPEngine(CSRGraph&& graph, VertexId source, PolicyConfig config);
    DecreaseResult recompute(const IncrementalSSSPState::PreparedDecrease& request,
                             Strategy strategy, AdaptiveMetrics* pending);

    IncrementalSSSPState state_;
    const PolicyConfig config_;
};

} // namespace dynagraph
