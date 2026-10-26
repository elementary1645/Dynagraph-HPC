#include "dynagraph/benchmark/replay.hpp"

#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>

namespace {
std::uint64_t number(const std::string& token, std::uint64_t maximum) {
    if (token.empty() || (token.size() > 1 && token.front() == '0')) {
        throw std::invalid_argument("expected canonical unsigned decimal integer");
    }
    std::uint64_t result = 0;
    for (const char ch : token) {
        if (ch < '0' || ch > '9') { throw std::invalid_argument("malformed integer option"); }
        const auto digit = static_cast<std::uint64_t>(ch - '0');
        if (digit > maximum || result > (maximum - digit) / 10) {
            throw std::invalid_argument("numeric option exceeds supported limit");
        }
        result = result * 10 + digit;
    }
    return result;
}
void parse(int argc, char** argv, dynagraph::benchmark::Options& options) {
    if (argc < 2 || std::string(argv[1]) != "verify") { throw std::invalid_argument("expected verify command; see --help"); }
    std::map<std::string, std::string> values;
    for (int i = 2; i < argc; i += 2) {
        const std::string key(argv[i]);
        if (key != "--graph" && key != "--trace" && key != "--source" && key != "--policy" &&
            key != "--delta" && key != "--threads" && key != "--no-effect" && key != "--verification") {
            throw std::invalid_argument("unknown option: " + key);
        }
        if (i + 1 >= argc || !values.emplace(key, argv[i + 1]).second) {
            throw std::invalid_argument("missing value or duplicate option: " + key);
        }
    }
    for (const auto key : {"--graph", "--trace", "--source", "--policy", "--delta", "--threads"}) {
        if (values.count(key) == 0 || values.at(key).empty()) { throw std::invalid_argument(std::string("required option: ") + key); }
    }
    options.graph_path = values.at("--graph"); options.trace_path = values.at("--trace");
    options.source = static_cast<dynagraph::VertexId>(number(values.at("--source"), 99999));
    options.config.parallel.delta = number(values.at("--delta"), std::numeric_limits<std::uint64_t>::max());
    if (options.config.parallel.delta == 0) { throw std::invalid_argument("delta must be positive"); }
    options.config.parallel.thread_count = static_cast<int>(number(values.at("--threads"), 64));
    options.policy = values.at("--policy");
    using dynagraph::PolicyKind;
    if (options.policy == "dijkstra") { options.config.kind = PolicyKind::always_dijkstra; }
    else if (options.policy == "delta-stepping") { options.config.kind = PolicyKind::always_delta_stepping; }
    else if (options.policy == "incremental") { options.config.kind = PolicyKind::always_incremental; }
    else if (options.policy == "heuristic") { options.config.kind = PolicyKind::heuristic; }
    else { throw std::invalid_argument("unsupported policy"); }
    if (values.count("--no-effect") != 0) {
        const auto& mode = values.at("--no-effect");
        if (mode == "execute_selected") { options.config.no_effect = dynagraph::NoEffectMode::execute_selected; }
        else if (mode != "shared_fast_path") { throw std::invalid_argument("unsupported no-effect mode"); }
    }
    if (values.count("--verification") != 0 && values.at("--verification") != "full") {
        throw std::invalid_argument("only full verification is supported");
    }
}
} // namespace

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "--help") {
        std::cout << "Usage: dynagraph_bench verify --graph FILE --trace FILE --source N\n"
                     "  --policy dijkstra|delta-stepping|incremental|heuristic --delta N --threads N\n"
                     "  [--no-effect shared_fast_path|execute_selected] [--verification full]\n"
                     "Canonical v1 artifacts only. Delta: 1..UINT64_MAX; threads: 0..64\n"
                     "(0 uses the OpenMP runtime default). Full per-update verification only.\n"
                     "Run Python generate.py verify --manifest FILE first: this executable does\n"
                     "not verify SHA-256, manifests or provenance. Inputs must remain unchanged.\n"
                     "One JSON record on stdout; diagnostics on stderr; exit 0 success, 2 failure.\n"
                     "Redirect stdout to save the record. No performance measurements.\n";
        return std::cout ? 0 : 2;
    }
    dynagraph::benchmark::Options options;
    dynagraph::benchmark::Report report;
    report.category = "cli_validation";
    try {
        parse(argc, argv, options);
        dynagraph::benchmark::replay(options, report);
    } catch (const std::bad_alloc&) {
        report.success = false; report.category = "resource"; report.message = "allocation failed";
    } catch (const std::exception& error) {
        report.success = false; report.message = error.what();
    }
    try {
        std::cout << dynagraph::benchmark::json_record(options, report);
        std::cout.flush();
        if (!std::cout) { std::cerr << "output write failed\n"; return 2; }
    } catch (const std::exception&) { std::cerr << "output serialization failed\n"; return 2; }
    if (!report.success) { std::cerr << report.category << ": " << report.message << '\n'; }
    return report.success ? 0 : 2;
}
