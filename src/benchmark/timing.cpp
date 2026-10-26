#include "dynagraph/benchmark/timing.hpp"
#include "dynagraph_benchmark_build.hpp"
#include <omp.h>
#include <limits>
#include <numeric>
#include <sstream>
#include <type_traits>

namespace dynagraph::benchmark {
std::int64_t SteadyClock::now() const {
    static_assert(std::is_integral_v<std::chrono::steady_clock::rep>);
    static_assert(sizeof(std::chrono::steady_clock::rep) <= sizeof(std::int64_t));
    return static_cast<std::int64_t>(std::chrono::steady_clock::now().time_since_epoch().count());
}
std::uint64_t elapsed_ticks(TickPair pair) {
    if (pair.stop < pair.start) { throw std::runtime_error("clock moved backwards"); }
    return static_cast<std::uint64_t>(pair.stop) - static_cast<std::uint64_t>(pair.start);
}
namespace {
std::uint64_t multiply(std::uint64_t a, std::uint64_t b) {
    if (b != 0 && a > std::numeric_limits<std::uint64_t>::max() / b) { throw std::overflow_error("clock conversion overflow"); }
    return a * b;
}
std::string integer(std::uint64_t value) { return json_quote(std::to_string(value)); }
constexpr auto period_num = static_cast<std::uint64_t>(std::chrono::steady_clock::period::num);
constexpr auto period_den = static_cast<std::uint64_t>(std::chrono::steady_clock::period::den);
std::string observation(const std::string& value, const std::string& origin, const std::string& source) {
    return "{\"value\":" + value + ",\"origin\":" + json_quote(origin) + ",\"source\":" + json_quote(source) + "}";
}
struct OutputError : std::runtime_error { using std::runtime_error::runtime_error; };
std::string digest_value(const std::string& digest) { return digest.empty() ? "null" : json_quote(digest); }
struct Writer {
    const Options& options;
    const TimingOptions& timing;
    std::ostream& out;
    std::uint64_t sequence = 0;
    void emit(const std::string& type, const std::string& fields) {
        out << "{\"schema\":\"dynagraph-timing-jsonl\",\"schema_version\":1,\"record_type\":" << json_quote(type)
            << ",\"run_id\":" << json_quote(timing.run_id) << ",\"sequence\":" << integer(sequence++)
            << ",\"block_id\":" << json_quote(timing.block_id) << ",\"trial_id\":" << json_quote(timing.trial_id)
            << ",\"policy\":" << json_quote(options.policy)
            << ",\"graph_sha256\":" << digest_value(timing.graph_sha256)
            << ",\"trace_sha256\":" << digest_value(timing.trace_sha256)
            << ",\"executable_sha256\":" << digest_value(timing.executable_sha256)
            << ",\"configuration_sha256\":" << digest_value(timing.configuration_sha256)
            << ',' << fields << "}\n";
        if (!out) { throw OutputError("output write failed"); }
    }
};
std::string environment(const Options& options) {
    return "\"metadata\":{\"cmake_version\":" + observation(json_quote(benchmark_build::cmake_version), "build_recorded", "CMake") +
        ",\"compiler_path\":" + observation(json_quote(benchmark_build::compiler_path), "build_recorded", "CMake") +
        ",\"openmp_runtime_version\":" + observation("null", "unavailable", "no portable runtime library version query") +
        ",\"compiler\":" + observation(json_quote(benchmark_build::compiler), "build_recorded", "CMake") +
        ",\"build_type\":" + observation(json_quote(benchmark_build::build_type), "build_recorded", "CMake") +
        ",\"flags\":" + observation(json_quote(benchmark_build::flags), "build_recorded", "CMake") +
        ",\"sanitizers\":" + observation(json_quote(benchmark_build::sanitizers), "build_recorded", "CMake flags; custom instrumentation may be unavailable") +
        ",\"git_revision\":" + observation(json_quote(benchmark_build::revision), "build_recorded", "CMake configure") +
        ",\"git_dirty\":" + observation(json_quote(benchmark_build::dirty), "build_recorded", "CMake configure") +
        ",\"openmp_spec\":" + observation(integer(_OPENMP), "build_recorded", "_OPENMP") +
        ",\"openmp_max_threads\":" + observation(integer(static_cast<std::uint64_t>(omp_get_max_threads())), "observed", "omp_get_max_threads; not actual team") +
        ",\"openmp_dynamic\":" + observation(integer(static_cast<std::uint64_t>(omp_get_dynamic())), "observed", "omp_get_dynamic") +
        ",\"openmp_thread_limit\":" + observation(integer(static_cast<std::uint64_t>(omp_get_thread_limit())), "observed", "omp_get_thread_limit") +
        ",\"actual_workers\":" + observation("null", "unavailable", "metrics disabled in timed calls") +
        "},\"source\":" + integer(options.source) + ",\"delta\":" + integer(options.config.parallel.delta) +
        ",\"requested_workers\":" + integer(static_cast<std::uint64_t>(options.config.parallel.thread_count)) +
        ",\"no_effect\":" + json_quote(options.config.no_effect == NoEffectMode::shared_fast_path ? "shared_fast_path" : "execute_selected") +
        ",\"heuristic\":{\"small_graph_edges\":\"4096\",\"repair_max_degree\":\"32\",\"parallel_min_edges\":\"65536\"}";
}
} // namespace

std::uint64_t nanoseconds(std::uint64_t ticks, std::uint64_t numerator, std::uint64_t denominator) {
    if (numerator == 0 || denominator == 0) { throw std::invalid_argument("invalid clock period"); }
    const auto divisor = std::gcd(denominator, UINT64_C(1000000000));
    denominator /= divisor;
    numerator = multiply(numerator, UINT64_C(1000000000) / divisor);
    const auto whole = multiply(ticks / denominator, numerator);
    const auto fraction = multiply(ticks % denominator, numerator) / denominator;
    if (whole > std::numeric_limits<std::uint64_t>::max() - fraction) { throw std::overflow_error("clock conversion overflow"); }
    return whole + fraction;
}

int timing_failure(const Options& options, const TimingOptions& timing, const std::string& message,
                   std::ostream& out, std::ostream& error) {
    Writer writer{options, timing, out};
    try {
        writer.emit("failure", "\"category\":\"cli_validation\",\"message\":" + json_quote(message) + ",\"update_index\":null");
        writer.emit("trial_end", "\"success\":false,\"updates_executed\":\"0\",\"sample_count\":\"0\"");
        out.flush();
    } catch (...) { error << "output_failure\n"; }
    error << message << '\n';
    return 2;
}

int timing_command(const Options& options, const TimingOptions& timing, std::ostream& out, std::ostream& error) {
    Writer writer{options, timing, out};
    Report report;
    std::size_t completed = 0;
    std::size_t samples_emitted = 0;
    std::vector<TickPair> samples;
    std::string category = "artifact_validation";
    try {
        const auto workload = prepare_workload(options, report);
        category = "incorrect_configuration";
        if (workload.updates.empty()) { throw std::invalid_argument("empty traces cannot be timed"); }
        writer.emit("environment", environment(options) + ",\"timing_mode\":" + json_quote(timing.mode == TimingMode::full_trace ? "full-trace" : "per-update") +
            ",\"vertices\":" + integer(workload.initial.vertices) + ",\"edges\":" + integer(workload.initial.edges.size()) +
            ",\"updates\":" + integer(workload.updates.size()) +
            ",\"external_integrity\":\"unconfirmed\",\"external_preflight\":\"unconfirmed\",\"identity_origin\":\"user_supplied\"");
        category = "clock_failure";
        if (!std::chrono::steady_clock::is_steady) { throw std::runtime_error("steady clock required"); }
        SteadyClock clock;
        std::vector<TickPair> probes(1024);
        for (auto& pair : probes) { pair.start = clock.now(); pair.stop = clock.now(); }
        std::string ticks = "[";
        for (std::size_t i = 0; i < probes.size(); ++i) {
            if (i != 0) { ticks += ','; } ticks += integer(elapsed_ticks(probes[i]));
        }
        writer.emit("clock_probe", "\"clock\":\"std::chrono::steady_clock\",\"is_steady\":true,\"period_num\":" + integer(period_num) +
            ",\"period_den\":" + integer(period_den) + ",\"method\":\"back-to-back-v1\",\"ticks\":" + ticks + "]");
        for (std::uint64_t warmup = 0; warmup < timing.warmups; ++warmup) {
            category = "initialization";
            auto engine = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(workload.initial.vertices, workload.initial.edges), options.source, options.config);
            category = "execution";
            for (std::size_t index = 0; index < workload.updates.size(); ++index) {
                report.update_index = index;
                const auto& update = workload.updates[index];
                (void)engine.decrease(update.u, update.v, static_cast<std::int64_t>(update.new_weight));
            }
            report.update_index.reset();
            category = "final_oracle_mismatch";
            verify_final_state(workload.final, engine, report);
            writer.emit("warmup_end", "\"phase\":\"warmup\",\"warmup_index\":" + integer(warmup) + ",\"success\":true");
        }
        category = "initialization";
        auto engine = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(workload.initial.vertices, workload.initial.edges), options.source, options.config);
        samples.resize(timing.mode == TimingMode::full_trace ? 1 : workload.updates.size());
        category = "execution";
        measure_updates(timing.mode, workload.updates, clock, [&](const TraceUpdate& update) {
            (void)engine.decrease(update.u, update.v, static_cast<std::int64_t>(update.new_weight), nullptr, std::nullopt);
        }, samples, completed);
        category = "clock_failure";
        for (const auto pair : samples) { (void)nanoseconds(elapsed_ticks(pair), period_num, period_den); }
        category = "final_oracle_mismatch";
        const auto previous_recomputations = report.recomputations;
        const auto previous_bf = report.bellman_ford_checks;
        verify_final_state(workload.final, engine, report);
        writer.emit("verification", "\"scope\":\"timed_final_state\",\"success\":true,\"per_update_oracles\":false,\"reference_recomputations\":" +
            integer(report.recomputations - previous_recomputations) + ",\"bellman_ford_checks\":" + integer(report.bellman_ford_checks - previous_bf));
        category = "output_failure";
        for (std::size_t i = 0; i < samples.size(); ++i) {
            const auto ticks_elapsed = elapsed_ticks(samples[i]);
            writer.emit(timing.mode == TimingMode::full_trace ? "trial_measurement" : "update_latency",
                "\"phase\":\"measurement\",\"update_index\":" + (timing.mode == TimingMode::full_trace ? std::string("null") : integer(i)) +
                ",\"elapsed_ticks\":" + integer(ticks_elapsed) + ",\"elapsed_ns\":" + integer(nanoseconds(ticks_elapsed, period_num, period_den)));
            ++samples_emitted;
        }
        writer.emit("trial_end", "\"success\":true,\"updates_executed\":" + integer(completed) + ",\"sample_count\":" + integer(samples.size()));
        out.flush();
        if (!out) { throw OutputError("output write failed"); }
        return 0;
    } catch (const std::exception& exception) {
        if (dynamic_cast<const OutputError*>(&exception) != nullptr) { category = "output_failure"; }
        if (category == "artifact_validation") { category = report.category; }
        error << category << ": " << exception.what() << '\n';
        try {
            // Retain completed latency-prefix observations as diagnostic evidence.
            // The subsequent failure/trial_end=false invalidates every sample.
            if (timing.mode == TimingMode::per_update && category != "output_failure") {
                while (samples_emitted < completed) {
                    const auto i = samples_emitted;
                    std::uint64_t ticks_elapsed = 0, ns = 0;
                    try {
                        ticks_elapsed = elapsed_ticks(samples[i]);
                        ns = nanoseconds(ticks_elapsed, period_num, period_den);
                    } catch (const std::exception&) { break; }
                    writer.emit("update_latency", "\"phase\":\"measurement\",\"update_index\":" + integer(i) +
                        ",\"elapsed_ticks\":" + integer(ticks_elapsed) + ",\"elapsed_ns\":" + integer(ns));
                    ++samples_emitted;
                }
            }
            writer.emit("failure", "\"category\":" + json_quote(category) + ",\"message\":" + json_quote(exception.what()) +
                ",\"update_index\":" + (report.update_index ? integer(*report.update_index) :
                    (category == "execution" ? integer(completed) : std::string("null"))));
            writer.emit("trial_end", "\"success\":false,\"updates_executed\":" + integer(completed) + ",\"sample_count\":" + integer(samples_emitted));
            out.flush();
        } catch (...) { error << "output_failure\n"; }
        return 2;
    }
}
} // namespace dynagraph::benchmark
