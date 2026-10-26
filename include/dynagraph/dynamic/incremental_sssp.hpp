#pragma once

#include "dynagraph/algorithms/sssp.hpp"

namespace dynagraph {

enum class DecreaseOutcome { unchanged_weight, weight_only, distances_repaired };

struct DecreaseResult {
    DecreaseOutcome outcome;
    EdgeWeight old_weight;
    EdgeWeight new_weight;
    std::uint64_t vertices_improved;
};

// Per-call counters, replaced only on success (never accumulated automatically).
// Event increments saturate; omitting metrics compiles out event updates.
struct RepairMetrics {
    std::uint64_t updates_applied = 0; // Strict committed decreases only.
    std::uint64_t unchanged_weight_requests = 0;
    std::uint64_t updates_without_distance_change = 0; // Includes equal weights.
    std::uint64_t vertices_improved = 0; // Distinct vertices, including seed.
    std::uint64_t edges_examined = 0; // Propagation CSR records, excluding lookup.
    std::uint64_t relaxation_attempts = 0; // Seed check + scanned edges, even if cap-rejected.
    std::uint64_t successful_relaxations = 0; // Includes seed, counts repeated improvements.
    std::uint64_t queue_pushes = 0;
    std::uint64_t queue_pops = 0;
    std::uint64_t stale_entries = 0;
    bool counters_saturated = false;
};

// Owns graph and distances for one fixed source. No concurrent access during
// decrease(), including reads through previously obtained views. Independent
// states own independent storage. No mutable accessors or graph rebinding.
class IncrementalSSSPState {
public:
    // By-value graph acquisition copies lvalues or consumes rvalues. Both
    // factories reject invalid sources (including empty graphs) with out_of_range.
    [[nodiscard]] static IncrementalSSSPState initialize(CSRGraph graph, VertexId source);
    // Recomputes Dijkstra; rejects dimension/distance mismatches with invalid_argument.
    [[nodiscard]] static IncrementalSSSPState from_result_checked(CSRGraph graph, SSSPResult result);

    // Fixed identity and view lifetime; C++17 factory returns use guaranteed elision.
    IncrementalSSSPState(const IncrementalSSSPState&) = delete;
    IncrementalSSSPState& operator=(const IncrementalSSSPState&) = delete;
    IncrementalSSSPState(IncrementalSSSPState&&) = delete;
    IncrementalSSSPState& operator=(IncrementalSSSPState&&) = delete;

    [[nodiscard]] VertexId source() const noexcept { return source_; }
    [[nodiscard]] const CSRGraph& graph() const noexcept { return graph_; }
    [[nodiscard]] const std::vector<Distance>& distances() const noexcept { return distances_; }

    // Existing edge only; equal weights succeed without propagation. Invalid
    // endpoints/absent edges throw out_of_range; invalid weights/increases throw
    // invalid_argument. On every exception graph, distances, and caller metrics
    // are unchanged; scratch marks are restored and the state remains reusable.
    // Returns scalars only. Views remain valid and reflect the committed state.
    [[nodiscard]] DecreaseResult decrease(std::uint64_t source_vertex,
                                          std::uint64_t destination_vertex,
                                          std::int64_t new_weight,
                                          RepairMetrics* metrics = nullptr);

private:
    IncrementalSSSPState(CSRGraph&& graph, SSSPResult&& result);
    template <bool Instrumented>
    DecreaseResult decrease_impl(std::uint64_t u, std::uint64_t v,
                                 std::int64_t new_weight, RepairMetrics* metrics);

    CSRGraph graph_;
    const VertexId source_;
    std::vector<Distance> distances_;
    std::vector<unsigned char> journaled_;
    const Distance cap_;
};

} // namespace dynagraph
