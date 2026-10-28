#pragma once
#include "adversarial_test_support.hpp"

#include <omp.h>
#include <charconv>
#include <cstdlib>
#include <exception>
#include <future>
#include <mutex>
#include <sstream>
#include <thread>

namespace dynagraph::test::concurrency {
namespace sv = dynagraph::test::system;
inline constexpr const char* version = "concurrency-validation-v1";
inline constexpr std::array<const char*, 8> families{
    "dense_zero", "hub255", "hub256", "hub257", "frontier_fanin",
    "light_closure_heavy", "stale_hub_chain", "disconnected_max"};
inline constexpr std::array<std::uint32_t, 4> trace_cases{0, 7, 14, 31};
inline constexpr std::array<const char*, 7> env_names{
    "OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "OMP_DYNAMIC", "OMP_MAX_ACTIVE_LEVELS",
    "OMP_SCHEDULE", "OMP_PROC_BIND", "OMP_PLACES"};

inline std::string quote(const std::string& text) {
    std::string out = "\"";
    constexpr char hex[] = "0123456789abcdef";
    for (const unsigned char ch : text) {
        if (ch == '\\' || ch == '"') { out += '\\'; out += static_cast<char>(ch); }
        else if (ch < 32) { out += "\\u00"; out += hex[ch >> 4U]; out += hex[ch & 15U]; }
        else { out += static_cast<char>(ch); }
    }
    return out + '"';
}
inline std::string shell_quote(const std::string& text) {
    std::string out = "'";
    for (const char ch : text) { out += ch == '\'' ? "'\\''" : std::string(1, ch); }
    return out + '\'';
}
inline void environment(std::ostream& out) {
    out << '{';
    for (std::size_t i = 0; i < env_names.size(); ++i) {
        if (i != 0) { out << ','; }
        out << quote(env_names[i]) << ':';
        const auto* value = std::getenv(env_names[i]);
        out << (value ? quote(value) : "null");
    }
    out << '}';
}
inline std::uint64_t number(const std::string& text) {
    std::uint64_t value = 0;
    const auto parsed = std::from_chars(text.data(), text.data() + text.size(), value);
    if (text.empty() || (text.size() > 1 && text.front() == '0') ||
        parsed.ec != std::errc{} || parsed.ptr != text.data() + text.size()) {
        throw std::invalid_argument("canonical uint64 decimal required");
    }
    return value;
}
struct Options {
    std::string executable, suite = "all", profile = "fast", runtime = "flat";
    std::uint32_t seed = 0x5C102026U;
    std::optional<std::uint32_t> index, repetition;
    std::optional<VertexId> source;
    std::optional<int> workers;
    std::optional<bool> measured;
    std::optional<Distance> delta;
};
inline unsigned repetitions(const Options& opt) {
    return opt.profile == "fast" ? 2U : opt.profile == "stress" ? 20U : 100U;
}
inline Options options(int argc, char** argv) {
    Options opt; opt.executable = argv[0]; std::vector<std::string> seen;
    for (int i = 1; i < argc; i += 2) {
        const std::string key = argv[i];
        if (i + 1 == argc || std::find(seen.begin(), seen.end(), key) != seen.end()) {
            throw std::invalid_argument("missing value or duplicate option");
        }
        seen.push_back(key); const std::string value = argv[i + 1];
        if (key == "--suite") { opt.suite = value; }
        else if (key == "--profile") { opt.profile = value; }
        else if (key == "--runtime") { opt.runtime = value; }
        else {
            const auto n = number(value);
            if (key == "--seed" && n <= 0xFFFFFFFFULL) { opt.seed = static_cast<std::uint32_t>(n); }
            else if (key == "--case" && n <= 47) { opt.index = static_cast<std::uint32_t>(n); }
            else if (key == "--source" && n < 4096) { opt.source = static_cast<VertexId>(n); }
            else if (key == "--workers" && (n == 0 || n == 1 || n == 2 || n == 4)) { opt.workers = static_cast<int>(n); }
            else if (key == "--metrics" && n <= 1) { opt.measured = n == 1; }
            else if (key == "--repeat" && n < 100) { opt.repetition = static_cast<std::uint32_t>(n); }
            else if (key == "--delta" && n > 0) { opt.delta = n; }
            else { throw std::invalid_argument("unknown/out-of-range option: " + key); }
        }
    }
    if (opt.profile != "fast" && opt.profile != "stress" && opt.profile != "extended") { throw std::invalid_argument("invalid profile"); }
    if (opt.suite != "all" && opt.suite != "direct" && opt.suite != "runtime" && opt.suite != "clients" && opt.suite != "traces") { throw std::invalid_argument("invalid suite"); }
    if (opt.runtime != "flat" && opt.runtime != "nested" && opt.runtime != "four") { throw std::invalid_argument("invalid runtime mode"); }
    if (opt.runtime != "flat" && opt.suite != "runtime") { throw std::invalid_argument("runtime mode requires runtime suite"); }
    const bool selected = opt.index || opt.source || opt.workers || opt.measured || opt.repetition || opt.delta;
    if (selected && opt.suite != "direct" && opt.suite != "traces") { throw std::invalid_argument("selectors require direct/traces suite"); }
    if (opt.source && !opt.index) { throw std::invalid_argument("source requires case"); }
    if (opt.suite == "traces") {
        if (opt.repetition || opt.measured || (opt.workers && *opt.workers == 0) ||
            (opt.index && std::find(trace_cases.begin(), trace_cases.end(), *opt.index) == trace_cases.end())) {
            throw std::invalid_argument("trace case must be 0,7,14,31; workers positive; no repeat/metrics selector");
        }
    } else if (opt.suite == "direct") {
        if ((opt.index && *opt.index >= (opt.profile == "extended" ? 16U : 8U)) ||
            (opt.repetition && *opt.repetition >= repetitions(opt))) { throw std::invalid_argument("selector outside profile"); }
    }
    return opt;
}

struct Workload { sv::Case c; std::uint32_t index = 0; VertexId source = 0; std::string family; };
inline void sort_records(std::vector<InputEdge>& records) {
    std::sort(records.begin(), records.end(), [](const InputEdge& a, const InputEdge& b) {
        return a.source < b.source || (a.source == b.source && a.destination < b.destination);
    });
}
inline Workload workload(std::uint32_t index) {
    Workload out; out.index = index; const auto family = index % 8U; out.family = families[family];
    constexpr std::array<std::uint32_t, 8> existing{1, 3, 4, 5, 0, 11, 10, 0};
    if (family != 4 && family != 7) { out.c = sv::adversarial_fixture(existing[family]); }
    else if (family == 4) {
        // 32 independently scheduled frontier rows propose successively better
        // labels to 16 destinations. Rejected proposals need not enter CAS.
        out.c.vertices = 49;
        for (VertexId u = 1; u <= 32; ++u) {
            out.c.edges.push_back({0, u, 1});
            for (VertexId v = 33; v < 49; ++v) { out.c.edges.push_back({u, v, 32 - u}); }
        }
    } else {
        out.c.vertices = 18;
        for (VertexId v = 1; v < 8; ++v) { out.c.edges.push_back({v - 1, v, 4294967295LL}); }
        out.c.edges.push_back({7, 1, 4294967295LL});
        for (VertexId v = 10; v < 16; ++v) { out.c.edges.push_back({v - 1, v, 4294967295LL}); }
        out.c.edges.push_back({16, 16, 0}); // isolated zero loop; vertex 17 isolated.
    }
    out.c.updates.clear(); // Direct corpus uses immutable initial fixtures only.
    if (index >= 8) {
        // Explicit extended variant: reverse vertex IDs; preserve zero/max,
        // replace other positive weights w with 2w+1. Same family, new records.
        for (auto& edge : out.c.edges) {
            edge.source = out.c.vertices - 1 - edge.source;
            edge.destination = out.c.vertices - 1 - edge.destination;
            if (edge.weight > 0 && edge.weight < 4294967295LL) { edge.weight = 2 * edge.weight + 1; }
        }
        out.source = out.c.vertices - 1;
        out.family += "_relabel_scaled";
    }
    sort_records(out.c.edges);
    return out;
}
struct Context {
    Workload w;
    std::string suite = "direct", policy = "standalone_delta", selected = "delta", actual_workers = "unavailable";
    int workers = 1, client = -1, outer_team = 0;
    unsigned repetition = 0;
    std::int64_t step = -1;
    Distance delta = 16;
    bool measured = true, returned = false;
    std::vector<Distance> expected, observed;
};
inline void identity(std::ostream& out, const Options& opt, const Context& ctx) {
    out << "\"version\":" << quote(version) << ",\"family\":" << quote(ctx.w.family)
        << ",\"seed\":" << opt.seed << ",\"case\":" << ctx.w.index << ",\"source\":" << ctx.w.source
        << ",\"suite\":" << quote(ctx.suite) << ",\"policy\":" << quote(ctx.policy) << ",\"selected\":" << quote(ctx.selected)
        << ",\"delta\":" << ctx.delta << ",\"requested_workers\":" << ctx.workers
        << ",\"metrics\":" << (ctx.measured ? "true" : "false") << ",\"client\":" << ctx.client
        << ",\"repetition\":" << ctx.repetition << ",\"update\":" << ctx.step << ",\"environment\":";
    environment(out);
}
inline void diagnostic(std::ostream& out, const Options& opt, const Context& ctx) {
    out << "CONCURRENCY FAILURE {"; identity(out, opt, ctx);
    out << ",\"actual_workers\":" << quote(ctx.actual_workers) << ",\"vector_status\":"
        << quote(ctx.returned ? "returned" : "pre-call snapshot or unavailable") << "}\n";
    sv::vector_print("expected", ctx.expected); sv::vector_print("observed", ctx.observed);
    out << "initial_records V=" << ctx.w.c.vertices << '\n';
    for (const auto& e : ctx.w.c.edges) { out << e.source << ' ' << e.destination << ' ' << e.weight << '\n'; }
    out << "trace_prefix (last entry attempted if API threw):\n";
    for (std::size_t i = 0; i < ctx.w.c.updates.size() && static_cast<std::int64_t>(i) <= ctx.step; ++i) {
        const auto& u = ctx.w.c.updates[i]; out << i << ' ' << u.u << ' ' << u.v << ' ' << u.old_weight << ' ' << u.weight << '\n';
    }
    out << "reproduce: env";
    for (const auto* name : env_names) { const auto* value = std::getenv(name); if (value) { out << ' ' << shell_quote(std::string(name) + '=' + value); } }
    out << ' ' << shell_quote(opt.executable) << " --suite " << ctx.suite << " --profile " << opt.profile << " --seed " << opt.seed;
    if (ctx.suite == "direct" || ctx.suite == "traces") {
        out << " --case " << ctx.w.index << " --source " << ctx.w.source << " --delta " << ctx.delta << " --workers " << ctx.workers;
        if (ctx.suite == "direct") { out << " --metrics " << ctx.measured << " --repeat " << ctx.repetition; }
    } else if (ctx.suite == "runtime") { out << " --runtime " << opt.runtime; }
    out << '\n';
}
inline void observation(std::ostream& out, const Options& opt, const Context& ctx,
                        const DeltaSteppingMetrics* metrics, const AdaptiveMetrics* adaptive = nullptr) {
    out << "{\"type\":\"observation\","; identity(out, opt, ctx);
    out << ",\"outer_team\":" << ctx.outer_team << ",\"actual_workers\":";
    if (metrics) { out << metrics->actual_thread_count; }
    else if (adaptive && adaptive->parallel.actual_threads) { out << *adaptive->parallel.actual_threads; }
    else { out << "null"; }
    out << ",\"per_thread\":";
    std::uint64_t successes = 0, retries = 0; unsigned participants = 0;
    if (metrics) {
        out << '[';
        for (std::size_t i = 0; i < metrics->per_thread.size(); ++i) {
            const auto& t = metrics->per_thread[i];
            if (i != 0) { out << ','; }
            out << "{\"thread\":" << i << ",\"edges\":" << t.edges_examined << ",\"attempts\":" << t.relaxation_attempts
                << ",\"successes\":" << t.successful_relaxations << ",\"cas_retries\":" << t.cas_retries << '}';
            successes += t.successful_relaxations; retries += t.cas_retries;
            if (t.edges_examined > 0) { ++participants; }
        }
        out << ']';
    } else { out << "null"; }
    out << ",\"work_participants\":" << (metrics ? std::to_string(participants) : "null")
        << ",\"successes\":" << (metrics ? std::to_string(successes) : adaptive && adaptive->parallel.actual_threads ? std::to_string(adaptive->parallel.successful_relaxations) : "null")
        << ",\"cas_retries\":" << (metrics ? std::to_string(retries) : adaptive && adaptive->parallel.actual_threads ? std::to_string(adaptive->parallel.cas_retries) : "null")
        << ",\"stale_entries\":" << (metrics ? std::to_string(metrics->stale_entries) : "null")
        << ",\"light_passes\":" << (metrics ? std::to_string(metrics->light_edge_passes) : "null")
        << ",\"heavy_passes\":" << (metrics ? std::to_string(metrics->heavy_edge_passes) : "null") << "}\n";
}
inline void query(const Options& opt, Context& ctx, const CSRGraph& graph, std::ostream& out) {
    ctx.returned = false; ctx.observed.clear(); ctx.actual_workers = "unavailable";
    DeltaSteppingMetrics metrics;
    const auto result = delta_stepping(graph, ctx.w.source, {ctx.delta, ctx.workers}, ctx.measured ? &metrics : nullptr);
    ctx.returned = true; ctx.observed = result.distances;
    if (ctx.measured) {
        ctx.actual_workers = std::to_string(metrics.actual_thread_count);
        const auto bound = ctx.workers == 0 ? omp_get_max_threads() : ctx.workers;
        require(metrics.actual_thread_count >= 1 && metrics.actual_thread_count <= bound, "actual team respects request");
        require(metrics.per_thread.size() == static_cast<std::size_t>(metrics.actual_thread_count), "metric team shape");
        require(!metrics.counters_saturated, "bounded fixture counters do not saturate");
        for (const auto& t : metrics.per_thread) {
            require(t.successful_relaxations <= t.relaxation_attempts && t.relaxation_attempts <= t.edges_examined,
                    "per-thread work accounting");
        }
        if (ctx.suite == "direct" && ctx.w.index == 5 && ctx.w.source == 0 && ctx.delta == 16) {
            require(metrics.light_edge_passes >= 3 && metrics.heavy_edge_passes > 0,
                    "closure fixture exercises repeated light passes and heavy phase");
        }
        if (ctx.suite == "direct" && ctx.w.index == 6 && ctx.w.source == 0 && ctx.delta == 1 && ctx.workers == 1) {
            require(metrics.stale_entries >= 60, "stale hub/chain creates observed delta stale records");
        }
    }
    require(result.source == ctx.w.source && ctx.observed == ctx.expected, "complete Bellman-Ford vector agreement");
    sv::graph_equal(graph, ctx.w.c.vertices, ctx.w.c.edges);
    observation(out, opt, ctx, ctx.measured ? &metrics : nullptr);
}
struct Client {
    Context ctx;
    std::ostringstream output;
    std::exception_ptr error;
};
template <typename Call>
void two_clients(const Options& opt, std::array<Client, 2>& clients, Call call) {
    std::promise<void> start; const auto ready = start.get_future().share();
    std::vector<std::thread> threads;
    try {
        for (std::size_t i = 0; i < clients.size(); ++i) {
            threads.emplace_back([&, i] {
                ready.wait();
                try { call(i, clients[i]); } catch (...) { clients[i].error = std::current_exception(); }
            });
        }
    } catch (...) { start.set_value(); for (auto& thread : threads) { thread.join(); } throw; }
    start.set_value();
    for (auto& thread : threads) { thread.join(); }
    // No diagnostics/inspection races: host clients have all joined first.
    for (auto& client : clients) {
        std::cout << client.output.str();
        if (client.error) { diagnostic(std::cerr, opt, client.ctx); }
    }
    for (const auto& client : clients) { if (client.error) { std::rethrow_exception(client.error); } }
}
} // namespace dynagraph::test::concurrency
