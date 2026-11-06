#pragma once
#include <string>
#include <vector>
#include <cstdint>

namespace dynagraph {
struct ResourceObservations;
// Call-owned development diagnostics. External serialization required for reuse.
// Fixed limits fail closed; no OpenMP exceptions escape a collective region.
struct WorkloadSample {
    int tid = 0, tgid = 0, task_pid = 0, task_tgid = 0, pgrp = 0, session = 0, cpu = -1;
    std::uint64_t start_ticks = 0, leader_start_ticks = 0;
    std::vector<int> affinity;
};
struct WorkloadThread {
    int number = 0, team = 0, level = 0, active_level = 0, max_active_levels = 0;
    std::vector<int> ancestor_sizes, ancestor_numbers;
    WorkloadSample entry, exit;
    std::uint64_t entry_begin_ns=0, entry_end_ns=0, exit_begin_ns=0, exit_end_ns=0;
};
struct WorkloadRegion {
    int requested = 0, configured = 0;
    std::vector<WorkloadThread> threads;
};
struct WorkloadObservations {
    static constexpr unsigned max_regions = 257;
    static constexpr int max_workers = 64;
    std::vector<WorkloadRegion> regions;
    ResourceObservations* resources = nullptr; // Explicit diagnostic-only extension.
    // Called outside the region; bounded allocation before workers enter.
    void prepare(int requested, int configured);
    void capture(int number, bool exit);
    void finish(int actual);
    std::string json() const;
    // Exclusive publication. Any write/close failure fails the diagnostic run.
    void publish(const std::string& path) const;
};
} // namespace dynagraph
