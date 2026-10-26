#include "dynagraph/project_info.hpp"
#include "dynagraph/algorithms/sssp.hpp"
#include "dynagraph/algorithms/delta_stepping.hpp"
#include "dynagraph/graph/edge_list_io.hpp"
#include <charconv>
#include <stdexcept>
#include <string>

#include <iostream>
#include <string_view>

int main(int argc, char* argv[]) {
    if (argc == 2 && std::string_view(argv[1]) == "--version") {
        std::cout << "DynaGraph-HPC " << dynagraph::version()
                  << " (OpenMP " << dynagraph::openmp_spec_date() << ")\n";
        return 0;
    }

    if (argc == 1 || (argc == 2 && std::string_view(argv[1]) == "--help")) {
        std::cout << "DynaGraph-HPC: Phase 2B sequential and parallel SSSP\n"
                     "Usage: dynagraph_cli [--help | --version]\n"
                     "CSR storage is available through the library API.\n"
                     "Usage: dynagraph_cli sssp --input graph.txt --source 0 --algorithm dijkstra\n"
                     "       dynagraph_cli sssp --input graph.txt --source 0 --algorithm delta-stepping --delta 16 [--threads 2]\n"
                     "Delta is positive uint64; threads is nonnegative int (0: runtime default).\n"
                     "SSSP emits JSON; unreachable distances are null.\n";
        return 0;
    }

    try {
        if (argc < 2 || std::string_view(argv[1]) != "sssp") {
            throw std::invalid_argument("Unsupported command");
        }
        std::string input;
        dynagraph::VertexId source = 0;
        bool have_source = false;
        bool have_algorithm = false;
        std::string algorithm;
        dynagraph::Distance delta = 0;
        int threads = 0;
        bool have_delta = false;
        bool have_threads = false;
        const auto parse_unsigned = [](std::string_view value, auto& target) {
            if (value.empty() || value.front() < '0' || value.front() > '9') {
                throw std::invalid_argument("Expected an unsigned decimal integer");
            }
            const auto parsed = std::from_chars(value.data(), value.data() + value.size(), target);
            if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size()) {
                throw std::invalid_argument("Malformed or out-of-range unsigned decimal integer");
            }
        };
        for (int i = 2; i < argc; i += 2) {
            if (i + 1 >= argc) { throw std::invalid_argument("Missing option value"); }
            const std::string_view option(argv[i]);
            const std::string_view value(argv[i + 1]);
            if (option == "--input" && input.empty() && !value.empty()) {
                input = value;
            } else if (option == "--source" && !have_source) {
                const auto parsed = std::from_chars(value.data(), value.data() + value.size(), source);
                if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size()) {
                    throw std::invalid_argument("Source must be a uint32 unsigned decimal integer");
                }
                have_source = true;
            } else if (option == "--algorithm" && !have_algorithm &&
                       (value == "dijkstra" || value == "delta-stepping")) {
                have_algorithm = true;
                algorithm = value;
            } else if (option == "--delta" && !have_delta) {
                parse_unsigned(value, delta);
                if (delta == 0) { throw std::invalid_argument("Delta must be positive"); }
                have_delta = true;
            } else if (option == "--threads" && !have_threads) {
                parse_unsigned(value, threads);
                have_threads = true;
            } else { throw std::invalid_argument("Unknown, duplicate, or invalid option"); }
        }
        if (input.empty() || !have_source || !have_algorithm) {
            throw std::invalid_argument("Required: --input, --source, --algorithm");
        }
        if ((algorithm == "dijkstra" && (have_delta || have_threads)) ||
            (algorithm == "delta-stepping" && !have_delta)) {
            throw std::invalid_argument("Delta-stepping requires --delta; --delta/--threads apply only to it");
        }
        const auto graph = dynagraph::load_edge_list_file(input);
        dynagraph::DeltaSteppingMetrics metrics;
        const auto result = algorithm == "dijkstra" ? dynagraph::dijkstra(graph, source) :
            dynagraph::delta_stepping(graph, source, {delta, threads}, &metrics);
        std::cout << "{\"schema_version\":1,\"algorithm\":\"" << algorithm
                  << "\",\"source\":" << result.source;
        if (algorithm == "delta-stepping") {
            std::cout << ",\"delta\":" << delta << ",\"requested_threads\":" << threads
                      << ",\"actual_threads\":" << metrics.actual_thread_count;
        }
        std::cout << ",\"distances\":[";
        for (std::size_t i = 0; i < result.distances.size(); ++i) {
            if (i != 0) { std::cout << ','; }
            if (result.distances[i] == dynagraph::unreachable_distance) { std::cout << "null"; }
            else { std::cout << result.distances[i]; }
        }
        std::cout << "]}\n";
        return std::cout ? 0 : 2;
    } catch (const std::exception& error) {
        std::cerr << error.what() << ". Use --help for usage.\n";
        return 2;
    }
}
