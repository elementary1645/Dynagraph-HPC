// Reuse the established executable-local injector and complete metric sentinel.
#define main original_adaptive_failure_main
#include "test_adaptive_failure.cpp"
#undef main

int main(int argc, char** argv) {
    unsigned epochs = 4;
    std::string profile = argc == 2 ? argv[1] : "fast";
    if (argc > 2 || (profile != "fast" && profile != "stress" && profile != "extended")) { return 2; }
    if (profile == "stress") { epochs = 20; }
    if (profile == "extended") { epochs = 100; }
    // Exactly one eligible scan edge in the first round: preparation allocates
    // settled/Work buffers, scan allocates one Entry, then merge must allocate.
    // No second worker buffer growth can be mistaken for a merge allocation.
    const auto graph = CSRGraph::from_edges(4, {{0, 1, 100}, {1, 2, 32}, {0, 3, 200}});
    DeltaSteppingMetrics team;
    (void)delta_stepping(graph, 0, {16, 2}, &team);
    std::cout << "CALIBRATION requested=2 observed=" << team.actual_thread_count << '\n';
    if (team.actual_thread_count != 2) { std::cerr << "Required two-worker calibration unavailable\n"; return 1; }
    for (const auto mode : {Mode::inside_first, Mode::publication, Mode::merge}) {
        const char* stage = mode == Mode::inside_first ? "prepare" : mode == Mode::publication ? "publication" : "merge";
        for (const bool measured : {false, true}) {
            for (unsigned epoch_index = 0; epoch_index < epochs; ++epoch_index) {
                std::cout << "BEGIN profile=" << profile << " stage=" << stage << " metrics=" << measured
                          << " epoch=" << epoch_index << " request=2 source=0 delta=16 update=0,1,0\n" << std::flush;
                const int result = test::run(stage, [&] {
                    auto immutable = graph;
                    immutable.replace_weight(0, 1, 0);
                    DeltaSteppingMetrics direct_metrics;
                    bool direct_failed = false;
                    {
                        FaultScope fault(mode, 0);
                        try { (void)delta_stepping(immutable, 0, {16, 2}, measured ? &direct_metrics : nullptr); }
                        catch (const std::bad_alloc&) { direct_failed = true; }
                    }
                    require(direct_failed && injection.worker_triggered.load(), "standalone mandatory injection triggered");
                    namespace sv = dynagraph::test::system;
                    auto direct_ledger = std::vector<InputEdge>{{0, 1, 0}, {0, 3, 200}, {1, 2, 32}};
                    sv::graph_equal(immutable, 4, direct_ledger);
                    sv::checkpoint(immutable, delta_stepping(immutable, 0, {16, 2}).distances, 4, direct_ledger, 0);
                    immutable.replace_weight(0, 3, 0); direct_ledger[1].weight = 0;
                    sv::checkpoint(immutable, delta_stepping(immutable, 0, {16, 2}).distances, 4, direct_ledger, 0);
                    auto engine = AdaptiveSSSPEngine::initialize(graph, 0, config);
                    const auto before = engine.distances();
                    auto metrics = sentinel();
                    bool failed = false;
                    {
                        FaultScope fault(mode, 0);
                        try { (void)engine.decrease(0, 1, 0, measured ? &metrics : nullptr, Strategy::delta_stepping); }
                        catch (const std::bad_alloc&) { failed = true; }
                    }
                    require(failed && injection.worker_triggered.load(), "mandatory stage injection triggered");
                    require(engine.distances() == before && metric_values(metrics) == metric_values(sentinel()),
                            "authoritative distance and caller metrics rollback");
                    sv::graph_equal(engine.graph(), 4, {{0, 1, 100}, {0, 3, 200}, {1, 2, 32}});
                    auto ledger = std::vector<InputEdge>{{0, 1, 0}, {0, 3, 200}, {1, 2, 32}};
                    (void)engine.decrease(0, 1, 0, measured ? &metrics : nullptr, Strategy::delta_stepping);
                    sv::checkpoint(engine.graph(), engine.distances(), 4, ledger, 0);
                    (void)engine.decrease(0, 3, 0, measured ? &metrics : nullptr, Strategy::delta_stepping);
                    ledger[1].weight = 0;
                    sv::checkpoint(engine.graph(), engine.distances(), 4, ledger, 0);
                    // Also recover with a different update directly after failure,
                    // without allowing an identical retry to repair hidden state.
                    auto other = AdaptiveSSSPEngine::initialize(graph, 0, config);
                    {
                        FaultScope fault(mode, 0);
                        failed = false;
                        try { (void)other.decrease(0, 1, 0, nullptr, Strategy::delta_stepping); }
                        catch (const std::bad_alloc&) { failed = true; }
                    }
                    require(failed, "second mandatory injection triggered");
                    (void)other.decrease(0, 3, 0, nullptr, Strategy::delta_stepping);
                    ledger[0].weight = 100;
                    sv::checkpoint(other.graph(), other.distances(), 4, ledger, 0);
                });
                if (result != 0) { return 1; }
            }
        }
    }
    std::cout << "COMPLETE profile=" << profile << " epochs_per_stage_and_metrics=" << epochs
              << " stages=3 faulted_calls=" << epochs * 18 << '\n';
    return 0;
}
