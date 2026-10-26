#pragma once

#include "dynagraph/adaptive/adaptive_sssp.hpp"
#include <optional>
#include <string>

namespace dynagraph::benchmark {
struct Options {
    std::string graph_path;
    std::string trace_path;
    VertexId source = 0;
    PolicyConfig config;
    std::string policy;
};

// Full verification only. Failures retain completed counters, never final state.
struct Report {
    std::string category = "initialization";
    std::string message;
    std::string declared_graph_sha256;
    std::optional<std::uint64_t> update_index;
    std::uint64_t trace_entries = 0;
    std::uint64_t executed = 0;
    std::uint64_t verified = 0;
    std::uint64_t recomputations = 0;
    std::uint64_t bellman_ford_checks = 0;
    bool success = false;
    std::vector<EdgeWeight> final_weights;
    std::vector<Distance> final_distances;
};

void replay(const Options& options, Report& report);
std::string json_record(const Options& options, const Report& report);
} // namespace dynagraph::benchmark
