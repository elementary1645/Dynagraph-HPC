#include "dynagraph/algorithms/delta_stepping.hpp"
#include "test_support.hpp"

#include <omp.h>

#include <atomic>
#include <cstdlib>
#include <new>

namespace {
// Test-executable-only allocation fault injection: no production hooks or global
// production state. Each selected OpenMP thread fails its Nth C++ allocation.
std::atomic<unsigned> epoch{0};
std::atomic<int> target_thread{0};
std::atomic<unsigned> failure_position{0};
std::atomic<bool> enabled{false};
thread_local unsigned local_epoch = 0;
thread_local unsigned allocations = 0;

void* allocate(std::size_t bytes) {
    if (enabled.load(std::memory_order_relaxed) && omp_in_parallel() != 0 &&
        (target_thread.load(std::memory_order_relaxed) == -1 ||
         omp_get_thread_num() == target_thread.load(std::memory_order_relaxed))) {
        const auto current = epoch.load(std::memory_order_relaxed);
        if (local_epoch != current) { local_epoch = current; allocations = 0; }
        ++allocations;
        const auto position = failure_position.load(std::memory_order_relaxed);
        if ((position == 0 && bytes == 16) || allocations == position) { throw std::bad_alloc(); }
    }
    if (void* pointer = std::malloc(bytes == 0 ? 1 : bytes)) { return pointer; }
    throw std::bad_alloc();
}
} // namespace

void* operator new(std::size_t bytes) { return allocate(bytes); }
void* operator new[](std::size_t bytes) { return allocate(bytes); }
void operator delete(void* pointer) noexcept { std::free(pointer); }
void operator delete[](void* pointer) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { std::free(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { std::free(pointer); }

int main() {
    return dynagraph::test::run("coordinated allocation failure and recovery", [] {
        using namespace dynagraph;
        std::vector<InputEdge> edges;
        for (VertexId v = 1; v < 700; ++v) {
            edges.push_back({0, v, v % 17});
            edges.push_back({v, 700, 700 - v});
        }
        const auto graph = CSRGraph::from_edges(701, edges);
        const auto expected = dijkstra(graph, 0).distances;
        // The first 16-byte allocation inside this query's region is an Entry
        // buffer append, after CAS. Coordinator preparation allocates byte/Work
        // vectors of other sizes. Explicitly verify publication failure aborts.
        target_thread.store(-1);
        failure_position.store(0);
        epoch.fetch_add(1);
        enabled.store(true);
        bool publication_failed = false;
        try { (void)delta_stepping(graph, 0, {16, 2}); }
        catch (const std::bad_alloc&) { publication_failed = true; }
        catch (...) { enabled.store(false); throw; }
        enabled.store(false);
        test::require(publication_failed, "Post-CAS scheduling allocation must propagate failure");
        unsigned exceptions = 0;
        for (const int thread : {0, 1}) {
            target_thread.store(thread);
            const auto previous_exceptions = exceptions;
            for (unsigned position = 1; position <= 45; ++position) {
                failure_position.store(position);
                epoch.fetch_add(1);
                enabled.store(true);
                bool failed = false;
                try {
                    const auto result = delta_stepping(graph, 0, {16, 2});
                    enabled.store(false);
                    test::require(result.distances == expected, "Non-triggered fault must return complete result");
                } catch (const std::bad_alloc&) {
                    enabled.store(false);
                    failed = true;
                    ++exceptions;
                } catch (...) {
                    enabled.store(false);
                    throw;
                }
                if (failed) {
                    test::require(delta_stepping(graph, 0, {16, 2}).distances == expected,
                                  "Fresh query recovers after allocation failure");
                }
            }
            test::require(exceptions > previous_exceptions + 10,
                          "Each team thread must exercise fault propagation");
        }
        test::require(exceptions > 20, "Fault sweep must exercise allocations in both team threads");
        std::cout << "Injected bad_alloc exceptions: " << exceptions << '\n';
    });
}
