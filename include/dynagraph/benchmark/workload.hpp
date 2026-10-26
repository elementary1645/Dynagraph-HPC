#pragma once
#include "dynagraph/benchmark/replay.hpp"

namespace dynagraph::benchmark {
struct ReferenceGraph {
    std::uint64_t vertices;
    std::vector<InputEdge> edges;
};
struct TraceUpdate { std::uint64_t u, v, old_weight, new_weight; };
struct PreparedWorkload {
    ReferenceGraph initial;
    ReferenceGraph final;
    std::vector<TraceUpdate> updates;
};
PreparedWorkload prepare_workload(const Options&, Report&);
void verify_final_state(const ReferenceGraph&, const AdaptiveSSSPEngine&, Report&);
std::string json_quote(const std::string&);
} // namespace dynagraph::benchmark
