#include "dynagraph/adaptive/adaptive_sssp.hpp"
#include "test_support.hpp"

#include <omp.h>

#include <array>
#include <atomic>
#include <cstdlib>
#include <new>
#include <tuple>

namespace {
using namespace dynagraph;
using test::require;
enum class Mode { disabled, outside, inside_first, publication };
struct Allocation { std::size_t bytes = 0; std::size_t changed = 0; bool after_team = false; };
struct Injection {
    std::atomic<Mode> mode{Mode::disabled};
    std::atomic<bool> saw_parallel{false};
    std::atomic<bool> worker_triggered{false};
    std::atomic<int> worker_thread{-1};
    // Only the initiating host thread accesses these fields, never workers.
    std::size_t target = 0;
    std::size_t count = 0;
    const Distance* current = nullptr;
    const Distance* before = nullptr;
    std::size_t vertices = 0;
    std::array<Allocation, 512> trace{};
} injection;

class FaultScope {
public:
    FaultScope(Mode mode, std::size_t target, const std::vector<Distance>* current = nullptr,
               const std::vector<Distance>* before = nullptr) noexcept {
        injection.target = target;
        injection.count = 0;
        injection.current = current == nullptr ? nullptr : current->data();
        injection.before = before == nullptr ? nullptr : before->data();
        injection.vertices = current == nullptr ? 0 : current->size();
        injection.saw_parallel.store(false);
        injection.worker_triggered.store(false);
        injection.worker_thread.store(-1);
        injection.mode.store(mode, std::memory_order_release);
    }
    FaultScope(const FaultScope&) = delete;
    FaultScope& operator=(const FaultScope&) = delete;
    ~FaultScope() noexcept { injection.mode.store(Mode::disabled, std::memory_order_release); }
};

void* allocate(std::size_t bytes) {
    const auto mode = injection.mode.load(std::memory_order_acquire);
    if (mode != Mode::disabled) {
        if (omp_in_parallel() != 0) {
            injection.saw_parallel.store(true, std::memory_order_relaxed);
            // In this delta implementation the first 16-byte region allocation
            // is an Entry buffer append after CAS. Work chunks and membership
            // allocations have different sizes (same targeted contract as the
            // standalone delta regression test). Only one thread injects.
            if ((mode == Mode::inside_first || (mode == Mode::publication && bytes == 16)) &&
                !injection.worker_triggered.exchange(true)) {
                injection.worker_thread.store(omp_get_thread_num());
                throw std::bad_alloc();
            }
        } else if (mode == Mode::outside) {
            std::size_t changed = 0;
            for (std::size_t v = 0; v < injection.vertices; ++v) {
                if (injection.current[v] != injection.before[v]) { ++changed; }
            }
            if (injection.count < injection.trace.size()) {
                injection.trace[injection.count] = {bytes, changed, injection.saw_parallel.load()};
            }
            ++injection.count;
            if (injection.count == injection.target) {
                injection.mode.store(Mode::disabled, std::memory_order_release);
                throw std::bad_alloc();
            }
        }
    }
    if (void* pointer = std::malloc(bytes == 0 ? 1 : bytes)) { return pointer; }
    throw std::bad_alloc();
}

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

CSRGraph fixture() {
    std::vector<InputEdge> edges{{0, 1, 100}, {0, 95, 500}};
    for (VertexId v = 2; v < 95; ++v) {
        edges.push_back({1, v, v});
        edges.push_back({v, 95, 1});
    }
    return CSRGraph::from_edges(96, std::move(edges));
}

constexpr PolicyConfig config{PolicyKind::always_incremental, NoEffectMode::execute_selected, {16, 2}};

void retry_and_switch(AdaptiveSSSPEngine& engine, Strategy strategy, bool measured) {
    AdaptiveMetrics metrics;
    const auto retry = engine.decrease(0, 1, 0, measured ? &metrics : nullptr, strategy);
    require(retry.update.vertices_improved == 95 && engine.distances() == dijkstra(engine.graph(), 0).distances,
            "Same-engine retry restores all affected labels and marks");
    const auto other = strategy == Strategy::incremental ? Strategy::dijkstra : Strategy::incremental;
    const auto next = engine.decrease(0, 95, 0, measured ? &metrics : nullptr, other);
    require(next.update.vertices_improved == 1 && engine.distances() == dijkstra(engine.graph(), 0).distances,
            "Switch after failure/retry uses coherent state");
}

void outside_allocation_failures() {
    const auto graph = fixture();
    for (const auto strategy : {Strategy::dijkstra, Strategy::delta_stepping, Strategy::incremental}) {
        for (const bool measured : {false, true}) {
            std::size_t positions = 0;
            std::array<Allocation, 512> trace{};
            {
                auto engine = AdaptiveSSSPEngine::initialize(graph, 0, config);
                const auto before = engine.distances();
                AdaptiveMetrics metrics;
                FaultScope fault(Mode::outside, 0, &engine.distances(), &before);
                (void)engine.decrease(0, 1, 0, measured ? &metrics : nullptr, strategy);
                positions = injection.count;
                trace = injection.trace;
            }
            require(positions > 4 && positions < trace.size(), "Sweep covers actual host allocations");
            if (strategy != Strategy::incremental) {
                require(trace[0].bytes == graph.offsets().size() * sizeof(EdgeOffset) &&
                        trace[1].bytes == graph.destinations().size() * sizeof(VertexId) &&
                        trace[2].bytes == graph.weights().size() * sizeof(EdgeWeight), "First three allocations are staged CSR copy");
            }
            std::size_t partial = 0;
            std::size_t after_team = 0;
            for (std::size_t position = 1; position <= positions; ++position) {
                auto engine = AdaptiveSSSPEngine::initialize(graph, 0, config);
                const auto before = engine.distances();
                const auto snapshot = engine.graph();
                auto metrics = sentinel();
                bool failed = false;
                {
                    FaultScope fault(Mode::outside, position, &engine.distances(), &before);
                    try { (void)engine.decrease(0, 1, 0, measured ? &metrics : nullptr, strategy); }
                    catch (const std::bad_alloc&) { failed = true; }
                }
                require(failed && injection.count == position, "Every selected host allocation was faulted");
                const auto& record = injection.trace[position - 1];
                require(record.bytes == trace[position - 1].bytes && record.after_team == trace[position - 1].after_team,
                        "Allocation stage matches successful reference trace");
                if (record.changed != 0) { ++partial; }
                if (record.after_team) { ++after_team; }
                require(engine.graph().weights() == snapshot.weights() && engine.graph().offsets() == snapshot.offsets() &&
                        engine.graph().destinations() == snapshot.destinations() && engine.distances() == before &&
                        metric_values(metrics) == metric_values(sentinel()), "Exact graph/distance/metric preservation");
                retry_and_switch(engine, strategy, measured);
            }
            if (strategy == Strategy::incremental) { require(partial > 5, "Repair failures occur after tentative writes"); }
            else { require(partial == 0, "Staged recomputation does not change authoritative labels before commit"); }
            if (strategy == Strategy::delta_stepping) {
                require(after_team == (measured ? 2U : 1U), "Result vector and optional metric vector fail after team exit");
            }
            std::cout << "Strategy " << static_cast<int>(strategy) << ", metrics=" << measured
                      << ": host faults=" << positions << ", partial=" << partial << ", after_team=" << after_team << '\n';
        }
    }
}

void parallel_failures() {
    const auto graph = fixture();
    for (const bool measured : {false, true}) {
        for (const auto mode : {Mode::inside_first, Mode::publication}) {
            auto engine = AdaptiveSSSPEngine::initialize(graph, 0, config);
            const auto before = engine.distances();
            const auto snapshot = engine.graph();
            auto metrics = sentinel();
            bool failed = false;
            {
                FaultScope fault(mode, 0);
                try { (void)engine.decrease(0, 1, 0, measured ? &metrics : nullptr, Strategy::delta_stepping); }
                catch (const std::bad_alloc&) { failed = true; }
            }
            require(failed && injection.worker_triggered.load() && injection.worker_thread.load() >= 0,
                    "Parallel-region allocator must trigger a recoverable C++ exception");
            require(engine.distances() == before && engine.graph().weights() == snapshot.weights() &&
                    engine.graph().offsets() == snapshot.offsets() && engine.graph().destinations() == snapshot.destinations() &&
                    metric_values(metrics) == metric_values(sentinel()), "Worker failure preserves authoritative state and metrics");
            retry_and_switch(engine, Strategy::delta_stepping, measured);
        }
    }
}

void initialization_and_bypass() {
    const auto graph = fixture();
    std::size_t positions = 0;
    {
        FaultScope fault(Mode::outside, 0);
        (void)AdaptiveSSSPEngine::initialize(graph, 0, config);
        positions = injection.count;
    }
    require(positions > 5 && positions < injection.trace.size(), "Initialization allocation trace");
    for (std::size_t position = 1; position <= positions; ++position) {
        bool failed = false;
        {
            FaultScope fault(Mode::outside, position);
            try { (void)AdaptiveSSSPEngine::initialize(graph, 0, config); }
            catch (const std::bad_alloc&) { failed = true; }
        }
        require(failed && graph.weight(0, 1) == 100, "Engine initialization failure preserves lvalue input");
        auto retry = AdaptiveSSSPEngine::initialize(graph, 0, config);
        retry_and_switch(retry, Strategy::dijkstra, true);
    }
    for (const auto policy : {PolicyKind::always_dijkstra, PolicyKind::always_delta_stepping, PolicyKind::always_incremental}) {
        auto engine = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(3, {{0, 1, 0}, {0, 2, 1}, {1, 2, 10}}),
            0, {policy, NoEffectMode::shared_fast_path, {16, 2}});
        AdaptiveMetrics metrics;
        {
            FaultScope fault(Mode::outside, 1);
            (void)engine.decrease(1, 2, 10, &metrics);
            (void)engine.decrease(1, 2, 9, &metrics);
        }
        require(injection.count == 0 && !metrics.work_collected && !metrics.decision.selected &&
                !metrics.parallel.actual_threads && engine.graph().weight(1, 2) == 9, "Every shared bypass avoids backend allocations");
    }
    std::cout << "Engine initialization faults=" << positions << "; parallel-region faults=4\n";
}
} // namespace

void* operator new(std::size_t bytes) { return allocate(bytes); }
void* operator new[](std::size_t bytes) { return allocate(bytes); }
void operator delete(void* pointer) noexcept { std::free(pointer); }
void operator delete[](void* pointer) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { std::free(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { std::free(pointer); }

int main() {
    int failures = 0;
    failures += test::run("all host allocations: staging, algorithms, result preparation and journal rollback", outside_allocation_failures);
    failures += test::run("OpenMP-safe coordinator and post-CAS publication failures", parallel_failures);
    failures += test::run("engine initialization sweep and allocation-free shared bypasses", initialization_and_bypass);
    return failures == 0 ? 0 : 1;
}
