#pragma once
#include "dynagraph/benchmark/workload.hpp"
#include <chrono>
#include <ostream>
#include <stdexcept>

namespace dynagraph::benchmark {
enum class TimingMode { full_trace, per_update };
struct TickPair { std::int64_t start = 0, stop = 0; };
struct SteadyClock {
    std::int64_t now() const;
};

// Caller preallocates samples; no checks, allocations, logging or oracle calls
// inside these brackets. Callback is the same public update call for both modes.
template<class Clock, class Apply>
void measure_updates(TimingMode mode, const std::vector<TraceUpdate>& updates,
                     Clock& clock, Apply&& apply, std::vector<TickPair>& samples,
                     std::size_t& completed) {
    if (updates.empty() || samples.size() != (mode == TimingMode::full_trace ? 1 : updates.size())) {
        throw std::invalid_argument("invalid measurement storage or empty trace");
    }
    completed = 0;
    if (mode == TimingMode::full_trace) {
        const auto start = clock.now();
        for (; completed < updates.size(); ++completed) { apply(updates[completed]); }
        const auto stop = clock.now();
        samples[0] = {start, stop};
    } else {
        for (; completed < updates.size(); ++completed) {
            const auto& update = updates[completed];
            const auto start = clock.now();
            apply(update);
            const auto stop = clock.now();
            samples[completed] = {start, stop};
        }
    }
}
std::uint64_t elapsed_ticks(TickPair);
std::uint64_t nanoseconds(std::uint64_t ticks, std::uint64_t period_num, std::uint64_t period_den);
struct TimingOptions {
    TimingMode mode = TimingMode::full_trace;
    std::uint64_t warmups = 1;
    std::string run_id = "0", block_id = "0", trial_id = "0";
    std::string graph_sha256, trace_sha256, executable_sha256, configuration_sha256;
};
// Always emits schema-versioned worker JSONL outside measured regions.
int timing_command(const Options&, const TimingOptions&, std::ostream&, std::ostream&);
int timing_failure(const Options&, const TimingOptions&, const std::string&, std::ostream&, std::ostream&);
} // namespace dynagraph::benchmark
