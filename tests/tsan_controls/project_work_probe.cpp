// Public-API-only probe: explicit workers avoid existing fixture assumptions.
#include "dynagraph/algorithms/delta_stepping.hpp"
#include "sssp_test_support.hpp"
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    if (argc != 2 || (std::string(argv[1]) != "1" && std::string(argv[1]) != "2")) { return 2; }
    const int workers = std::string(argv[1]) == "1" ? 1 : 2;
    std::vector<dynagraph::InputEdge> records;
    for (dynagraph::VertexId vertex = 1; vertex < 39; ++vertex) {
        records.push_back({0, vertex, vertex}); records.push_back({vertex, 39, 40 - vertex});
    }
    const auto graph = dynagraph::CSRGraph::from_edges(40, records);
    const auto expected = dynagraph::test::bellman_ford(40, records, 0);
    std::cerr << "project probe requested_workers=" << workers << " (actual unavailable until query returns)\n";
    for (int repeat = 0; repeat < 8; ++repeat) {
        dynagraph::DeltaSteppingMetrics metrics;
        const auto result = dynagraph::delta_stepping(graph, 0, {16, workers}, &metrics);
        if (result.distances != expected || metrics.actual_thread_count < 1 || metrics.actual_thread_count > workers) { return 3; }
        std::cout << "repeat=" << repeat << " actual_team=" << metrics.actual_thread_count << '\n';
    }
}
