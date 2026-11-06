#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace dynagraph {
// Linux CLOCK_MONOTONIC, explicit nanoseconds; only used by opted-in diagnostics.
std::uint64_t resource_monotonic_ns();
struct ResourceObservations {
    static constexpr std::size_t max_bytes = 1048576;
    static constexpr std::size_t max_paths = 16;
    void load_paths(const std::string& path);
    void before();
    void workload(bool exit);
    void after();
    void publish(const std::string& path) const;
private:
    void capture(const char* boundary, bool in_region);
    std::vector<std::string> paths_;
    std::vector<std::string> samples_;
    std::uint64_t armed_ns_ = 0;
    std::string boot_id_;
    std::size_t bytes_ = 0;
};
} // namespace dynagraph
