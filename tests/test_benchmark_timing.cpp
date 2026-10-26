#include "dynagraph/benchmark/timing.hpp"
#include "test_support.hpp"
#include <limits>
#include <sstream>
using namespace dynagraph;
using namespace dynagraph::benchmark;
using dynagraph::test::require;
using dynagraph::test::require_throws;
struct FakeClock {
    std::int64_t reads = 0;
    std::int64_t now() { return reads++; }
};
int main() {
    return dynagraph::test::run("timing contracts", [] {
        const std::vector<TraceUpdate> updates{{0,1,8,6},{0,1,6,6},{0,1,6,0},{2,3,8,0}};
        for (const auto mode : {TimingMode::full_trace, TimingMode::per_update}) {
            for (const auto policy : {PolicyKind::always_dijkstra, PolicyKind::always_delta_stepping,
                                     PolicyKind::always_incremental, PolicyKind::heuristic}) {
                for (const auto no_effect : {NoEffectMode::shared_fast_path, NoEffectMode::execute_selected}) {
                    for (int repetition = 0; repetition < 2; ++repetition) {
                        auto engine = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(4,
                            {{0,1,8},{1,0,0},{2,3,8},{3,2,0}}), 0, {policy,no_effect,{16,2}});
                        require(engine.graph().weight(0,1) == 8, "fresh graph");
                        FakeClock clock;
                        std::size_t completed = 0;
                        std::vector<TickPair> samples(mode == TimingMode::full_trace ? 1 : updates.size());
                        measure_updates(mode, updates, clock, [&](const TraceUpdate& update) {
                            require(clock.reads == (mode == TimingMode::full_trace ? 1 : static_cast<std::int64_t>(2 * completed + 1)), "clock bracket");
                            require(engine.graph().weight(update.u,update.v) == update.old_weight, "ordered fresh ledger");
                            (void)engine.decrease(update.u,update.v,static_cast<std::int64_t>(update.new_weight));
                        }, samples, completed);
                        require(completed == 4, "every update");
                        require(clock.reads == (mode == TimingMode::full_trace ? 2 : 8), "exact reads");
                        require(engine.distances() == std::vector<Distance>({0,0,unreachable_distance,unreachable_distance}), "final distances");
                        require(engine.graph().weight(2,3) == 0, "unreachable weights");
                        Report report;
                        ReferenceGraph final{4,{{0,1,0},{1,0,0},{2,3,0},{3,2,0}}};
                        verify_final_state(final, engine, report);
                        require(report.recomputations == 1 && report.bellman_ford_checks == 1, "independent final oracles");
                        final.edges[0].weight = 1;
                        require_throws<std::runtime_error>([&] { verify_final_state(final, engine, report); }, "graph differs");
                        require(clock.reads == (mode == TimingMode::full_trace ? 2 : 8), "oracles outside clock region");
                        for (const auto pair : samples) { require(elapsed_ticks(pair) == 1, "raw ticks"); }
                    }
                }
            }
        }
        FakeClock clock;
        std::size_t completed = 0;
        std::vector<TickPair> samples(1);
        require_throws<std::runtime_error>([&] {
            measure_updates(TimingMode::full_trace, updates, clock, [&](const TraceUpdate&) {
                if (completed == 2) { throw std::runtime_error("injected update"); }
            }, samples, completed);
        }, "injected");
        require(completed == 2 && clock.reads == 1, "stop at failed update");
        clock.reads = 0;
        samples.resize(updates.size());
        require_throws<std::runtime_error>([&] {
            measure_updates(TimingMode::per_update, updates, clock, [&](const TraceUpdate&) {
                if (completed == 2) { throw std::runtime_error("latency failure"); }
            }, samples, completed);
        }, "latency failure");
        require(completed == 2 && clock.reads == 5 && elapsed_ticks(samples[0]) == 1 && elapsed_ticks(samples[1]) == 1,
                "successful latency prefix retained");
        require(nanoseconds(5,1,3) == 1666666666, "integer rounding");
        require(nanoseconds(0,1,1000000000) == 0, "zero retained");
        require(elapsed_ticks({-2,3}) == 5, "signed epoch difference");
        require_throws<std::runtime_error>([] { (void)elapsed_ticks({2,1}); }, "backwards");
        require_throws<std::overflow_error>([] { (void)nanoseconds(std::numeric_limits<std::uint64_t>::max(),1,1); }, "overflow");
        require_throws<std::invalid_argument>([] { (void)nanoseconds(1,1,0); }, "period");
        require_throws<std::invalid_argument>([&] {
            measure_updates(TimingMode::full_trace, {}, clock, [](const TraceUpdate&) {}, samples, completed);
        }, "empty");
    });
}
