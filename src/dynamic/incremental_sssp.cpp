#include "dynagraph/dynamic/incremental_sssp.hpp"

#include <functional>
#include <limits>
#include <queue>
#include <stdexcept>
#include <utility>

namespace dynagraph {
namespace {
static_assert(CSRGraph::max_vertex_count <= 0xFFFFFFFFULL);
static_assert(CSRGraph::max_edge_weight <= 0xFFFFFFFFULL);

void increment(std::uint64_t& value, bool& saturated) noexcept {
    if (value == std::numeric_limits<std::uint64_t>::max()) { saturated = true; }
    else { ++value; }
}

Distance checked_add(Distance label, EdgeWeight weight, Distance cap) noexcept {
    // Every finite stored label is <= cap. Do not subtract from infinity.
    if (label == unreachable_distance || weight > cap - label) { return unreachable_distance; }
    return label + weight;
}

struct UndoEntry { VertexId vertex; Distance original; };

class UndoJournal {
public:
    UndoJournal(std::vector<Distance>& distances, std::vector<unsigned char>& marks) noexcept
        : distances_(distances), marks_(marks) {}
    UndoJournal(const UndoJournal&) = delete;
    UndoJournal& operator=(const UndoJournal&) = delete;

    void save(VertexId vertex) {
        if (marks_[vertex] == 0) {
            entries_.push_back({vertex, distances_[vertex]}); // May throw before the mark/write.
            marks_[vertex] = 1;
        }
    }

    [[nodiscard]] std::uint64_t size() const noexcept {
        return static_cast<std::uint64_t>(entries_.size()); // <= validated V.
    }

    void commit() noexcept { committed_ = true; }

    ~UndoJournal() noexcept {
        // No lookup, allocation, graph access, or user callbacks in rollback.
        for (const auto entry : entries_) {
            if (!committed_) { distances_[entry.vertex] = entry.original; }
            marks_[entry.vertex] = 0;
        }
    }

private:
    std::vector<Distance>& distances_;
    std::vector<unsigned char>& marks_;
    std::vector<UndoEntry> entries_;
    bool committed_ = false;
};
} // namespace

IncrementalSSSPState::IncrementalSSSPState(CSRGraph&& graph, SSSPResult&& result)
    : graph_(std::move(graph)), source_(result.source), distances_(std::move(result.distances)),
      journaled_(distances_.size(), 0), cap_((graph_.vertex_count() - 1) * CSRGraph::max_edge_weight) {}

IncrementalSSSPState IncrementalSSSPState::initialize(CSRGraph graph, VertexId source) {
    // Dijkstra validates before any cap calculation; only this factory and the
    // checked factory can call the private constructor with a nonempty graph.
    auto result = dijkstra(graph, source);
    return IncrementalSSSPState(std::move(graph), std::move(result));
}

IncrementalSSSPState IncrementalSSSPState::from_result_checked(CSRGraph graph, SSSPResult result) {
    if (result.source >= graph.vertex_count()) { throw std::out_of_range("source outside [0, V)"); }
    if (result.distances.size() != graph.vertex_count()) {
        throw std::invalid_argument("result dimensions do not match graph");
    }
    if (dijkstra(graph, result.source).distances != result.distances) {
        throw std::invalid_argument("result distances do not match current graph");
    }
    return IncrementalSSSPState(std::move(graph), std::move(result));
}

IncrementalSSSPState::PreparedDecrease IncrementalSSSPState::prepare_decrease(
    std::uint64_t u, std::uint64_t v, std::int64_t new_weight) const {
    if (new_weight < 0 || static_cast<std::uint64_t>(new_weight) > CSRGraph::max_edge_weight) {
        throw std::invalid_argument("new weight outside uint32 range");
    }
    const auto replacement = static_cast<EdgeWeight>(new_weight);
    const auto previous = graph_.weight(u, v); // Validates both endpoints and existence.
    if (replacement > previous) { throw std::invalid_argument("weight increase is not supported"); }
    return {static_cast<VertexId>(u), static_cast<VertexId>(v), previous, replacement,
            checked_add(distances_[static_cast<std::size_t>(u)], replacement, cap_)};
}

template <bool Instrumented>
DecreaseResult IncrementalSSSPState::repair_impl(const PreparedDecrease& request, RepairMetrics* metrics) {
    const auto [u, v, previous, replacement, seed] = request;

    RepairMetrics pending;
    if (replacement == previous) {
        if constexpr (Instrumented) {
            pending.unchanged_weight_requests = 1;
            pending.updates_without_distance_change = 1;
            *metrics = pending;
        }
        return {DecreaseOutcome::unchanged_weight, previous, replacement, 0};
    }

    UndoJournal journal(distances_, journaled_);
    using Entry = std::pair<Distance, VertexId>;
    std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> queue;
    const auto improve = [&](VertexId vertex, Distance candidate) {
        if (candidate < distances_[vertex]) {
            journal.save(vertex);
            queue.emplace(candidate, vertex); // Publication allocation precedes distance write.
            distances_[vertex] = candidate;
            if constexpr (Instrumented) {
                increment(pending.successful_relaxations, pending.counters_saturated);
                increment(pending.queue_pushes, pending.counters_saturated);
            }
        }
    };

    if constexpr (Instrumented) { increment(pending.relaxation_attempts, pending.counters_saturated); }
    improve(v, seed);
    while (!queue.empty()) {
        const auto [label, vertex] = queue.top();
        queue.pop();
        if constexpr (Instrumented) { increment(pending.queue_pops, pending.counters_saturated); }
        if (label != distances_[vertex]) {
            if constexpr (Instrumented) { increment(pending.stale_entries, pending.counters_saturated); }
            continue;
        }
        for (const auto edge : graph_.outgoing_edges(vertex)) {
            if constexpr (Instrumented) {
                increment(pending.edges_examined, pending.counters_saturated);
                increment(pending.relaxation_attempts, pending.counters_saturated);
            }
            // Evaluate the new graph without mutating it before commit.
            const auto weight = vertex == u && edge.destination == v ? replacement : edge.weight;
            improve(edge.destination, checked_add(label, weight, cap_));
        }
    }

    const auto affected = journal.size();
    const DecreaseResult result{affected == 0 ? DecreaseOutcome::weight_only : DecreaseOutcome::distances_repaired,
                                previous, replacement, affected};
    if constexpr (Instrumented) {
        pending.updates_applied = 1;
        pending.updates_without_distance_change = affected == 0 ? 1 : 0;
        pending.vertices_improved = affected;
    }

    // CSRGraph validates/locates before its scalar write, and cannot throw after
    // that write. Everything below is nonthrowing, including journal/queue cleanup.
    graph_.replace_weight(u, v, replacement);
    journal.commit();
    if constexpr (Instrumented) { *metrics = pending; }
    return result;
}

DecreaseResult IncrementalSSSPState::decrease(std::uint64_t source_vertex, std::uint64_t destination_vertex,
                                             std::int64_t new_weight, RepairMetrics* metrics) {
    return repair_prepared(prepare_decrease(source_vertex, destination_vertex, new_weight), metrics);
}

DecreaseResult IncrementalSSSPState::repair_prepared(const PreparedDecrease& request, RepairMetrics* metrics) {
    if (metrics != nullptr) {
        return repair_impl<true>(request, metrics);
    }
    return repair_impl<false>(request, nullptr);
}

} // namespace dynagraph
