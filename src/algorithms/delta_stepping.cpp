#include "dynagraph/algorithms/delta_stepping.hpp"

#include <omp.h>

#include <algorithm>
#include <atomic>
#include <exception>
#include <limits>
#include <map>
#include <memory>
#include <stdexcept>
#include <utility>

namespace dynagraph {
namespace {
static_assert(CSRGraph::max_vertex_count <= 0xFFFFFFFFULL);
static_assert(CSRGraph::max_edge_weight <= 0xFFFFFFFFULL);

void increment(std::uint64_t& counter, bool& saturated) noexcept {
    if (counter == std::numeric_limits<std::uint64_t>::max()) { saturated = true; }
    else { ++counter; }
}

struct Entry { VertexId vertex; Distance label; };
struct Work { std::size_t begin; std::size_t end; Distance label; };
struct ThreadState {
    std::vector<Entry> updates;
    DeltaSteppingThreadMetrics metrics;
    bool saturated = false;
    std::exception_ptr error;
};

template <bool Instrumented>
class Query {
public:
    Query(const CSRGraph& graph, VertexId source, Distance delta, int requested,
          DeltaSteppingMetrics* metrics)
        : graph_(graph), delta_(delta), cap_((graph.vertex_count() - 1) * CSRGraph::max_edge_weight),
          labels_(std::make_unique<std::atomic<Distance>[]>(static_cast<std::size_t>(graph.vertex_count()))),
          threads_(static_cast<std::size_t>(requested)),
          in_set_(static_cast<std::size_t>(graph.vertex_count()), 0), metrics_(metrics) {
        for (std::size_t v = 0; v < graph.vertex_count(); ++v) {
            labels_[v].store(unreachable_distance, std::memory_order_relaxed);
        }
        labels_[source].store(0, std::memory_order_relaxed);
        buckets_[0].push_back({source, 0});
    }

    SSSPResult execute(VertexId source, int requested) {
        // All throwing operations in the region are caught by the executing
        // thread. Implicit single/for barriers publish each state transition.
#pragma omp parallel num_threads(requested) default(none) shared(source)
        {
#pragma omp single
            { actual_threads_ = omp_get_num_threads(); }
            auto& local = threads_[static_cast<std::size_t>(omp_get_thread_num())];
            while (true) {
#pragma omp single
                {
                    try { if (!error_) { prepare(); } }
                    catch (...) { error_ = std::current_exception(); }
                } // Publication barrier: work_, heavy_, done_, error_.
                if (error_ || done_) { break; } // Collective decision.
#pragma omp for schedule(dynamic, 1)
                for (std::size_t i = 0; i < work_.size(); ++i) {
                    if (!local.error) {
                        try { scan(work_[i], local); }
                        catch (...) { local.error = std::current_exception(); }
                    }
                } // Worker completion barrier: updates and exception slots.
#pragma omp single
                {
                    for (const auto& state : threads_) {
                        if (state.error) { error_ = state.error; break; }
                    }
                    if (!error_) {
                        try { merge(); }
                        catch (...) { error_ = std::current_exception(); }
                    }
                } // Publication barrier; no worker accesses buffers while merged.
                // Re-enter single collectively before observing failure. A fast
                // coordinator may otherwise change error_ for the next round
                // while a slower worker is still testing the previous round.
            }
        }
        if (error_) { std::rethrow_exception(error_); }
        SSSPResult result{source, std::vector<Distance>(static_cast<std::size_t>(graph_.vertex_count()))};
        for (std::size_t v = 0; v < result.distances.size(); ++v) {
            result.distances[v] = labels_[v].load(std::memory_order_relaxed);
        }
        if constexpr (Instrumented) {
            metrics_->actual_thread_count = actual_threads_;
            metrics_->per_thread.reserve(static_cast<std::size_t>(actual_threads_));
            for (int t = 0; t < actual_threads_; ++t) {
                const auto& state = threads_[static_cast<std::size_t>(t)];
                metrics_->per_thread.push_back(state.metrics);
                metrics_->counters_saturated |= state.saturated;
            }
        }
        return result;
    }

private:
    void stale() noexcept {
        if constexpr (Instrumented) { increment(metrics_->stale_entries, metrics_->counters_saturated); }
    }

    void append_work(VertexId vertex, Distance label) {
        // Split skewed rows without copying adjacency or prepartitioning weights.
        const auto& offsets = graph_.offsets();
        auto begin = static_cast<std::size_t>(offsets[vertex]);
        const auto end = static_cast<std::size_t>(offsets[static_cast<std::size_t>(vertex) + 1]);
        constexpr std::size_t chunk = 256;
        while (begin < end) {
            const auto next = begin + std::min(chunk, end - begin);
            work_.push_back({begin, next, label});
            begin = next;
        }
    }

    void prepare() {
        work_.clear();
        if (heavy_) {
            for (const auto vertex : settled_) { in_set_[vertex] = 0; }
            settled_.clear();
            active_ = false;
            heavy_ = false;
        }
        while (true) {
            if (!active_) {
                if (buckets_.empty()) { done_ = true; return; }
                bucket_ = buckets_.begin()->first; // Never walk empty indices.
                active_ = true;
            }
            bool valid = false;
            const auto found = buckets_.find(bucket_);
            if (found != buckets_.end()) {
                auto entries = std::move(found->second);
                buckets_.erase(found);
                for (const auto entry : entries) {
                    if (entry.label != labels_[entry.vertex].load(std::memory_order_relaxed)) {
                        stale();
                        continue;
                    }
                    // Records are inserted only under entry.label/delta_.
                    valid = true;
                    if (in_set_[entry.vertex] == 0) {
                        in_set_[entry.vertex] = 1;
                        settled_.push_back(entry.vertex);
                    }
                    append_work(entry.vertex, entry.label);
                }
            }
            if (valid) {
                if constexpr (Instrumented) {
                    if (!counted_) {
                        increment(metrics_->buckets_processed, metrics_->counters_saturated);
                    }
                    increment(metrics_->light_edge_passes, metrics_->counters_saturated);
                }
                counted_ = true;
                return; // Repeated entries remain eligible for light processing.
            }
            if (settled_.empty()) { active_ = false; continue; } // Stale-only bucket.
            heavy_ = true;
            counted_ = false;
            for (const auto vertex : settled_) {
                append_work(vertex, labels_[vertex].load(std::memory_order_relaxed));
            }
            if constexpr (Instrumented) {
                increment(metrics_->heavy_edge_passes, metrics_->counters_saturated);
            }
            return;
        }
    }

    void scan(const Work& work, ThreadState& local) {
        for (auto edge = work.begin; edge < work.end; ++edge) {
            if constexpr (Instrumented) { increment(local.metrics.edges_examined, local.saturated); }
            const Distance weight = graph_.weights()[edge];
            if ((weight > delta_) != heavy_) { continue; }
            if constexpr (Instrumented) { increment(local.metrics.relaxation_attempts, local.saturated); }
            // Every finite shortest path has a simple representative <= cap_.
            // Discard longer walks without ever adding or colliding with infinity.
            if (weight > cap_ - work.label) { continue; }
            const Distance candidate = work.label + weight;
            const auto destination = graph_.destinations()[edge];
            auto old = labels_[destination].load(std::memory_order_relaxed);
            while (candidate < old) {
                if (labels_[destination].compare_exchange_weak(old, candidate,
                        std::memory_order_relaxed, std::memory_order_relaxed)) {
                    if constexpr (Instrumented) {
                        increment(local.metrics.successful_relaxations, local.saturated);
                    }
                    // If allocation throws after CAS, the entire query fails;
                    // an updated label is never returned without its scheduling record.
                    local.updates.push_back({destination, candidate});
                    break;
                }
                if constexpr (Instrumented) { increment(local.metrics.cas_retries, local.saturated); }
            }
        }
    }

    void merge() {
        for (auto& local : threads_) {
            for (const auto entry : local.updates) {
                if (entry.label != labels_[entry.vertex].load(std::memory_order_relaxed)) { stale(); }
                else { buckets_[entry.label / delta_].push_back(entry); }
            }
            local.updates.clear(); // Retain capacity within this query.
        }
    }

    const CSRGraph& graph_;
    Distance delta_;
    Distance cap_;
    std::unique_ptr<std::atomic<Distance>[]> labels_;
    std::vector<ThreadState> threads_;
    std::vector<unsigned char> in_set_;
    std::vector<VertexId> settled_;
    std::map<Distance, std::vector<Entry>> buckets_;
    std::vector<Work> work_;
    DeltaSteppingMetrics* metrics_;
    std::exception_ptr error_;
    Distance bucket_ = 0;
    int actual_threads_ = 0;
    bool active_ = false;
    bool counted_ = false;
    bool heavy_ = false;
    bool done_ = false;
};
} // namespace

SSSPResult delta_stepping(const CSRGraph& graph, VertexId source,
                         const DeltaSteppingOptions& options, DeltaSteppingMetrics* metrics) {
    if (source >= graph.vertex_count()) { throw std::out_of_range("source outside [0, V)"); }
    if (options.delta == 0 || options.thread_count < 0) {
        throw std::invalid_argument("delta must be positive and threads nonnegative");
    }
    const int requested = options.thread_count == 0 ? omp_get_max_threads() : options.thread_count;
    if (metrics != nullptr) {
        *metrics = {};
        return Query<true>(graph, source, options.delta, requested, metrics).execute(source, requested);
    }
    return Query<false>(graph, source, options.delta, requested, nullptr).execute(source, requested);
}
} // namespace dynagraph
