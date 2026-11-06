#include "dynagraph/instrumentation/workload.hpp"
#include <omp.h>
#include "dynagraph/instrumentation/resources.hpp"
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <memory>
#ifdef __linux__
#include <sys/syscall.h>
#include <unistd.h>
#include <sched.h>
#include <fcntl.h>
#endif

namespace dynagraph {
namespace {
void require(bool ok) { if (!ok) { throw std::runtime_error("workload observation unavailable or exceeds bound"); } }
#ifdef __linux__
std::string read(const std::string& path) {
    std::ifstream in(path);
    std::string value(65537, '\0');
    in.read(value.data(), static_cast<std::streamsize>(value.size()));
    require(!in.bad() && in.gcount() > 0 && in.gcount() <= 65536);
    value.resize(static_cast<std::size_t>(in.gcount()));
    return value;
}
std::uint64_t ticks(const std::string& path, int pid, int& pgrp, int& session) {
    const auto raw = read(path);
    require(std::stoi(raw) == pid);
    const auto pos = raw.rfind(") "); require(pos != std::string::npos);
    std::istringstream in(raw.substr(pos + 2));
    std::string token;
    std::uint64_t start = 0;
    for (int field = 3; field <= 22; ++field) {
        require(static_cast<bool>(in >> token));
        if (field == 5) { pgrp = std::stoi(token); }
        if (field == 6) { session = std::stoi(token); }
        if (field == 22) { start = std::stoull(token); }
    }
    require(start > 0); return start;
}
WorkloadSample sample() {
    WorkloadSample s;
    s.tid = static_cast<int>(syscall(SYS_gettid)); s.tgid = static_cast<int>(getpid());
    const auto prefix = "/proc/self/task/" + std::to_string(s.tid);
    const auto status = read(prefix + "/status");
    std::istringstream lines(status); std::string line;
    while (std::getline(lines, line)) {
        if (line.rfind("Pid:", 0) == 0) { s.task_pid = std::stoi(line.substr(4)); }
        if (line.rfind("Tgid:", 0) == 0) { s.task_tgid = std::stoi(line.substr(5)); }
    }
    s.start_ticks = ticks(prefix + "/stat", s.tid, s.pgrp, s.session);
    int group = 0, session = 0;
    s.leader_start_ticks = ticks("/proc/self/task/" + std::to_string(s.tgid) + "/stat", s.tgid, group, session);
    require(group == s.pgrp && session == s.session && s.task_pid == s.tid && s.task_tgid == s.tgid);
    // Fixed 8192 CPU bound. Kernel rejects an undersized mask; never truncate.
    constexpr std::size_t bytes = 1024;
    auto free_mask = [](cpu_set_t* mask) { CPU_FREE(mask); };
    std::unique_ptr<cpu_set_t, decltype(free_mask)> owned(CPU_ALLOC(8192), free_mask);
    auto* mask = owned.get(); require(mask != nullptr);
    CPU_ZERO_S(bytes, mask);
    const int result = sched_getaffinity(0, bytes, mask);
    if (result == 0) {
        for (int cpu = 0; cpu < 8192; ++cpu) { if (CPU_ISSET_S(static_cast<std::size_t>(cpu), bytes, mask)) { s.affinity.push_back(cpu); } }
    }
    require(result == 0 && !s.affinity.empty());
    s.cpu = sched_getcpu(); require(s.cpu >= 0);
    return s;
}
#else
WorkloadSample sample() { throw std::runtime_error("Linux workload observations required"); }
#endif
void array(std::ostream& out, const std::vector<int>& values) {
    out << '[';
    for (std::size_t i = 0; i < values.size(); ++i) { if (i) { out << ','; } out << values[i]; }
    out << ']';
}
void emit(std::ostream& out, const WorkloadSample& s) {
    out << "{\"tid\":" << s.tid << ",\"tgid\":" << s.tgid << ",\"task_pid\":" << s.task_pid
        << ",\"task_tgid\":" << s.task_tgid << ",\"pgrp\":" << s.pgrp << ",\"session\":" << s.session
        << ",\"cpu\":" << s.cpu << ",\"start_ticks\":" << s.start_ticks
        << ",\"leader_start_ticks\":" << s.leader_start_ticks << ",\"affinity\":";
    array(out, s.affinity); out << '}';
}
}
void WorkloadObservations::prepare(int requested, int configured) {
    require(regions.size() < max_regions && configured > 0 && configured <= max_workers);
    regions.push_back({requested, configured, std::vector<WorkloadThread>(static_cast<std::size_t>(configured))});
}
void WorkloadObservations::capture(int number, bool exit) {
    auto& t = regions.back().threads.at(static_cast<std::size_t>(number));
    if (exit) {
        if (resources) { t.exit_begin_ns=resource_monotonic_ns(); }
        t.exit=sample();
        if (resources) {
            if (number==0 && regions.size()==1) { resources->workload(true); }
            t.exit_end_ns=resource_monotonic_ns();
        }
        return;
    }
    if (resources) { t.entry_begin_ns=resource_monotonic_ns(); }
    t.number = number; t.team = omp_get_num_threads(); t.level = omp_get_level();
    t.active_level = omp_get_active_level(); t.max_active_levels = omp_get_max_active_levels();
    require(t.level >= 1 && t.level <= 16);
    for (int level = 0; level <= t.level; ++level) {
        t.ancestor_sizes.push_back(omp_get_team_size(level));
        t.ancestor_numbers.push_back(omp_get_ancestor_thread_num(level));
    }
    t.entry = sample();
    if (resources) {
        if (number==0 && regions.size()==1) { resources->workload(false); }
        t.entry_end_ns=resource_monotonic_ns();
    }
}
void WorkloadObservations::finish(int actual) { regions.back().threads.resize(static_cast<std::size_t>(actual)); }
std::string WorkloadObservations::json() const {
    std::ostringstream out;
    out << "{\"schema\":\"dynagraph-workload-native\",\"schema_version\":" << (resources ? 3 : 2) << ",\"measurement_eligible\":false";
    if (resources) { out << ",\"clock\":\"CLOCK_MONOTONIC\""; }
    out << ",\"regions\":[";
    for (std::size_t r = 0; r < regions.size(); ++r) {
        if (r) { out << ','; }
        const auto& region = regions[r];
        out << "{\"region_id\":" << r << ",\"requested_workers\":" << region.requested
            << ",\"configured_workers\":" << region.configured << ",\"threads\":[";
        for (std::size_t i = 0; i < region.threads.size(); ++i) {
            if (i) { out << ','; } const auto& t = region.threads[i];
            out << "{\"number\":" << t.number << ",\"team\":" << t.team << ",\"level\":" << t.level
                << ",\"active_level\":" << t.active_level << ",\"max_active_levels\":" << t.max_active_levels
                << ",\"ancestor_sizes\":"; array(out, t.ancestor_sizes);
            out << ",\"ancestor_numbers\":"; array(out, t.ancestor_numbers);
            out << ",\"entry\":"; emit(out, t.entry); out << ",\"exit\":"; emit(out, t.exit);
            if (resources) {
                out << ",\"intervals\":[" << t.entry_begin_ns << ',' << t.entry_end_ns << ',' << t.exit_begin_ns << ',' << t.exit_end_ns << ']';
            }
            out << '}';
        }
        out << "]}";
    }
    out << "]}\n"; return out.str();
}
void WorkloadObservations::publish(const std::string& path) const {
#ifdef __linux__
    const auto raw = json(); require(raw.size() <= 1048576);
    const int fd = open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    require(fd >= 0);
    const auto written = write(fd, raw.data(), raw.size());
    const bool synced = fsync(fd) == 0;
    const bool closed = close(fd) == 0;
    if (written != static_cast<ssize_t>(raw.size()) || !synced || !closed) {
        unlink(path.c_str()); require(false);
    }
#else
    (void)path; require(false);
#endif
}
}
