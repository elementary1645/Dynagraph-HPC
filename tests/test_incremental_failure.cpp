#include "dynagraph/dynamic/incremental_sssp.hpp"
#include "test_support.hpp"
#include "system_validation_support.hpp"

#include <array>
#include <cstdlib>
#include <new>

namespace {
using namespace dynagraph;
using test::require;

struct Allocation { std::size_t bytes = 0; std::size_t changed = 0; };
// Isolated sequential test executable. Fixed-size observations never allocate;
// the allocator can observe partial tentative repair without production hooks.
struct Injection {
    bool enabled = false;
    std::size_t target = 0;
    std::size_t count = 0;
    const Distance* current = nullptr;
    const Distance* before = nullptr;
    std::size_t vertices = 0;
    std::array<Allocation, 512> trace{};
} injection;

class FaultScope {
public:
    explicit FaultScope(std::size_t target, const std::vector<Distance>* current = nullptr,
                        const std::vector<Distance>* before = nullptr) noexcept {
        injection.target = target;
        injection.count = 0;
        injection.current = current == nullptr ? nullptr : current->data();
        injection.before = before == nullptr ? nullptr : before->data();
        injection.vertices = current == nullptr ? 0 : current->size();
        injection.enabled = true;
    }
    FaultScope(const FaultScope&) = delete;
    FaultScope& operator=(const FaultScope&) = delete;
    ~FaultScope() noexcept { injection.enabled = false; }
};

void* allocate(std::size_t bytes) {
    if (injection.enabled) {
        std::size_t changed = 0;
        for (std::size_t v = 0; v < injection.vertices; ++v) {
            if (injection.current[v] != injection.before[v]) { ++changed; }
        }
        if (injection.count < injection.trace.size()) { injection.trace[injection.count] = {bytes, changed}; }
        ++injection.count;
        if (injection.count == injection.target) {
            injection.enabled = false; // Never inject into rollback or test diagnostics.
            throw std::bad_alloc();
        }
    }
    if (void* pointer = std::malloc(bytes == 0 ? 1 : bytes)) { return pointer; }
    throw std::bad_alloc();
}

auto metric_values(const RepairMetrics& m) {
    return std::array<std::uint64_t, 11>{m.updates_applied, m.unchanged_weight_requests,
        m.updates_without_distance_change, m.vertices_improved, m.edges_examined,
        m.relaxation_attempts, m.successful_relaxations, m.queue_pushes, m.queue_pops,
        m.stale_entries, m.counters_saturated ? 1U : 0U};
}

CSRGraph fixture() {
    std::vector<InputEdge> edges{{0, 1, 100}, {0, 95, 500}};
    for (VertexId v = 2; v < 95; ++v) {
        edges.push_back({1, v, static_cast<std::int64_t>(v)});
        edges.push_back({v, 95, 1});
    }
    return CSRGraph::from_edges(96, std::move(edges));
}

void initialization_failures() {
    const auto graph = fixture();
    const auto correct = dijkstra(graph, 0);
    const auto weights = graph.weights();
    const auto offsets = graph.offsets();
    const auto destinations = graph.destinations();
    for (const bool checked : {false, true}) {
        std::size_t positions = 0;
        {
            FaultScope fault(0); // Count all allocations in a successful initialization.
            if (checked) { (void)IncrementalSSSPState::from_result_checked(graph, correct); }
            else { (void)IncrementalSSSPState::initialize(graph, 0); }
            positions = injection.count;
        }
        require(positions > 5 && positions < injection.trace.size(), "Initialization sweep covers actual allocations");
        for (std::size_t position = 1; position <= positions; ++position) {
            bool failed = false;
            {
                FaultScope fault(position);
                try {
                    if (checked) { (void)IncrementalSSSPState::from_result_checked(graph, correct); }
                    else { (void)IncrementalSSSPState::initialize(graph, 0); }
                } catch (const std::bad_alloc&) { failed = true; }
            }
            require(failed && injection.count == position, "Every initialization allocation was faulted");
            require(graph.weights() == weights && graph.offsets() == offsets && graph.destinations() == destinations &&
                    correct.distances == dijkstra(graph, 0).distances, "Initialization failure preserves inputs");
            auto retry = IncrementalSSSPState::initialize(graph, 0);
            (void)retry.decrease(0, 1, 0);
            (void)retry.decrease(0, 95, 0);
            require(retry.distances() == dijkstra(retry.graph(), 0).distances, "Initialization retry and subsequent updates");
        }
        std::cout << (checked ? "Checked adoption" : "Initialization") << " allocation failures: " << positions << '\n';
    }
}

void repair_failures() {
    const auto graph = fixture();
    const RepairMetrics sentinel{81, 82, 83, 84, 85, 86, 87, 88, 89, 90, true};
    for (const bool instrumented : {false, true}) {
        std::size_t positions = 0;
        std::array<Allocation, 512> trace{};
        {
            auto state = IncrementalSSSPState::initialize(graph, 0);
            const auto before = state.distances();
            RepairMetrics metrics = sentinel;
            FaultScope fault(0, &state.distances(), &before);
            (void)state.decrease(0, 1, 0, instrumented ? &metrics : nullptr);
            positions = injection.count;
            trace = injection.trace;
        }
        require(positions > 8 && positions < trace.size(), "Repair sweep covers journal and heap growth");
        // With empty local containers: journal insertion, initial heap insertion,
        // journal growth for first child, journal growth for second child, heap
        // growth for second child. No allocation occurs in validation or scanning.
        require(trace[0].changed == 0 && trace[1].changed == 0 && trace[2].changed == 1 &&
                trace[3].changed == 2 && trace[4].changed == 2, "Targeted journal/queue stages and partial writes observed");
        std::size_t partial_failures = 0;
        for (std::size_t position = 1; position <= positions; ++position) {
            auto state = IncrementalSSSPState::initialize(graph, 0);
            const auto before = state.distances();
            const auto weights = state.graph().weights();
            const auto offsets = state.graph().offsets();
            const auto destinations = state.graph().destinations();
            RepairMetrics metrics = sentinel;
            bool failed = false;
            {
                FaultScope fault(position, &state.distances(), &before);
                try { (void)state.decrease(0, 1, 0, instrumented ? &metrics : nullptr); }
                catch (const std::bad_alloc&) { failed = true; }
            }
            require(failed && injection.count == position, "Every repair allocation was faulted");
            require(injection.trace[position - 1].bytes == trace[position - 1].bytes &&
                    injection.trace[position - 1].changed == trace[position - 1].changed,
                    "Fault reached the intended allocation stage");
            if (injection.trace[position - 1].changed != 0) { ++partial_failures; }
            require(state.distances() == before && state.graph().weights() == weights &&
                    state.graph().offsets() == offsets && state.graph().destinations() == destinations,
                    "Failure rolls back distances and preserves every graph array");
            require(metric_values(metrics) == metric_values(sentinel), "Failure preserves caller metrics");
            const auto retry = state.decrease(0, 1, 0, instrumented ? &metrics : nullptr);
            require(retry.vertices_improved == 95 && state.distances() == dijkstra(state.graph(), 0).distances,
                    "Marks restored: same-state retry journals all affected vertices");
            const auto next = state.decrease(0, 95, 0, instrumented ? &metrics : nullptr);
            require(next.vertices_improved == 1 && state.distances() == dijkstra(state.graph(), 0).distances,
                    "Independent subsequent update succeeds");
        }
        require(partial_failures > 5, "Failures must occur after partial tentative propagation");
        std::cout << (instrumented ? "Measured" : "Plain") << " repair allocation failures: " << positions
                  << "; after tentative writes: " << partial_failures << '\n';
    }
}

void no_op_allocations() {
    auto state = IncrementalSSSPState::initialize(CSRGraph::from_edges(3, {{0, 1, 0}, {0, 2, 1}, {1, 2, 10}}), 0);
    RepairMetrics metrics;
    DecreaseResult equal{};
    DecreaseResult weight_only{};
    {
        FaultScope fault(1);
        equal = state.decrease(1, 2, 10, &metrics);
        weight_only = state.decrease(1, 2, 9, &metrics);
    }
    require(injection.count == 0 && equal.outcome == DecreaseOutcome::unchanged_weight &&
            weight_only.outcome == DecreaseOutcome::weight_only && state.graph().weight(1, 2) == 9,
            "Unaffected requests allocate no journal or heap storage");
}

void history_failures() {
    namespace sv = dynagraph::test::system;
    const auto c = sv::history_case();
    const auto graph = CSRGraph::from_edges(c.vertices, c.edges);
    const sv::Update target{0, 1, 80, 0}, next{0, 95, 400, 0};
    const RepairMetrics marker{81, 82, 83, 84, 85, 86, 87, 88, 89, 90, true};
    for (const bool measured : {false, true}) {
        const auto prepare = [&](auto& state, auto& ledger) {
            sv::history_prefix(state, ledger, [&](const auto& u) { return state.decrease(u.u, u.v, u.weight); });
        };
        std::size_t positions = 0;
        {
            auto state = IncrementalSSSPState::initialize(graph, 0);
            auto ledger = c.edges; prepare(state, ledger);
            const auto before = state.distances(); RepairMetrics metrics;
            FaultScope fault(0, &state.distances(), &before);
            (void)state.decrease(target.u, target.v, target.weight, measured ? &metrics : nullptr);
            positions = injection.count;
        }
        require(positions > 8 && positions < injection.trace.size(), "history allocation coverage");
        std::size_t partial = 0;
        for (std::size_t position = 1; position <= positions; ++position) {
            auto state = IncrementalSSSPState::initialize(graph, 0);
            auto ledger = c.edges; prepare(state, ledger);
            const auto before = state.distances(); auto metrics = marker; bool failed = false;
            {
                FaultScope fault(position, &state.distances(), &before);
                try { (void)state.decrease(target.u, target.v, target.weight, measured ? &metrics : nullptr); }
                catch (const std::bad_alloc&) { failed = true; }
            }
            require(failed && injection.count == position, "history fault position " + std::to_string(position));
            partial += injection.trace[position - 1].changed != 0 ? 1U : 0U;
            sv::checkpoint(state.graph(), state.distances(), c.vertices, ledger, 0);
            require(state.distances() == before && metric_values(metrics) == metric_values(marker), "history exact rollback");
            const auto call = [&](const auto& u) { return state.decrease(u.u, u.v, u.weight, measured ? &metrics : nullptr); };
            sv::history_step(state, ledger, target, call); sv::history_step(state, ledger, next, call);
            sv::graph_equal(graph, c.vertices, c.edges);
        }
        require(partial > 5, "history failures after tentative distance changes");
        std::cout << "History repair metrics=" << measured << " faults=" << positions << " partial=" << partial << '\n';
    }
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
    failures += test::run("sequential initialization and checked-adoption allocation failure sweeps", initialization_failures);
    failures += test::run("sequential journal/heap failures, partial repair rollback and recovery", repair_failures);
    failures += test::run("unchanged and weight-only updates allocate no propagation storage", no_op_allocations);
    failures += test::run("history-dependent repair rollback with independent Bellman-Ford", history_failures);
    return failures == 0 ? 0 : 1;
}
