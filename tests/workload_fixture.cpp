#include "dynagraph/algorithms/delta_stepping.hpp"
#include "dynagraph/algorithms/sssp.hpp"
#include "dynagraph/instrumentation/workload.hpp"
#include <omp.h>
#include <thread>
#include <exception>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
    try {
        if (argc != 3) { throw std::invalid_argument("MODE OUTPUT required"); }
        const std::string mode(argv[1]);
        dynagraph::WorkloadObservations observations;
        const auto graph = dynagraph::CSRGraph::from_edges(5, {{0,1,9},{0,2,2},{1,4,1},{2,1,2},{2,3,1},{3,4,2}});
        const auto oracle = dynagraph::dijkstra(graph, 0).distances;
        std::exception_ptr error;
        auto run = [&] {
            try {
                const int workers = mode == "one" ? 1 : 2;
                const int repeats = mode == "repeated" ? 3 : 1;
                for (int r = 0; r < repeats; ++r) {
                    if (dynagraph::delta_stepping(graph, 0, {2, workers, &observations}).distances != oracle) {
                        throw std::runtime_error("correctness oracle failed");
                    }
                }
            } catch (...) { error = std::current_exception(); }
        };
        if (mode == "joined") { std::thread caller(run); caller.join(); }
        else if (mode == "active" || mode == "serialized" || mode == "serialized-zero") {
            omp_set_max_active_levels(mode == "active" ? 2 : 1);
#pragma omp parallel num_threads(2) default(none) shared(run, mode)
            {
#pragma omp single
                { if (mode == "serialized-zero") { omp_set_max_active_levels(0); } run(); }
            }
        } else if (mode == "serial") { (void)dynagraph::dijkstra(graph, 0); }
        else if (mode == "one" || mode == "two" || mode == "repeated" || mode == "dynamic") {
            if (mode == "dynamic") { omp_set_dynamic(1); }
            run();
        } else { throw std::invalid_argument("unsupported mode"); }
        if (error) { std::rethrow_exception(error); }
        observations.publish(argv[2]);
        std::cout << "{\"oracle_passed\":true}\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 2; }
}
