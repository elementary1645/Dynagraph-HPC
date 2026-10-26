#include "dynagraph/benchmark/replay.hpp"

#include <algorithm>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string_view>
#include <utility>

namespace dynagraph::benchmark {
namespace {
constexpr std::uint64_t max_vertices = 100000;
constexpr std::uint64_t max_edges = 500000;
constexpr std::uint64_t max_updates = 100000;
constexpr auto max_weight = CSRGraph::max_edge_weight;

void require(bool condition, const char* message) {
    if (!condition) { throw std::runtime_error(message); }
}

std::uint64_t number(std::string_view token, std::uint64_t maximum) {
    require(!token.empty() && (token.size() == 1 || token.front() != '0'), "noncanonical integer");
    std::uint64_t result = 0;
    for (const char ch : token) {
        require(ch >= '0' && ch <= '9', "malformed integer");
        const auto digit = static_cast<std::uint64_t>(ch - '0');
        require(digit <= maximum && result <= (maximum - digit) / 10, "integer exceeds supported limit");
        result = result * 10 + digit;
    }
    return result;
}

struct Reader {
    std::string data;
    std::size_t position = 0;
    Reader(const std::string& path, std::size_t limit) {
        std::ifstream stream(path, std::ios::binary);
        require(stream.is_open(), "cannot open artifact");
        data.resize(limit + 1);
        stream.read(data.data(), static_cast<std::streamsize>(data.size()));
        require(!stream.bad(), "artifact read failed");
        data.resize(static_cast<std::size_t>(stream.gcount()));
        require(data.size() <= limit, "artifact byte limit exceeded");
    }
    std::string_view line() {
        const auto end = data.find('\n', position);
        require(end != std::string::npos, "truncated artifact or missing final LF");
        const std::string_view result(data.data() + position, end - position);
        position = end + 1;
        return result;
    }
    void done() const { require(position == data.size(), "unexpected trailing records"); }
};

std::vector<std::string_view> fields(std::string_view line, std::size_t count) {
    std::vector<std::string_view> result;
    std::size_t start = 0;
    for (;;) {
        const auto end = line.find(' ', start);
        const auto token = line.substr(start, end == std::string_view::npos ? end : end - start);
        require(!token.empty(), "empty field or noncanonical spacing");
        result.push_back(token);
        require(result.size() <= count, "too many fields");
        if (end == std::string_view::npos) { break; }
        start = end + 1;
    }
    require(result.size() == count, "incorrect field count");
    return result;
}

std::string_view header(Reader& reader, std::string_view key) {
    const auto tokens = fields(reader.line(), 2);
    require(tokens[0] == key, "unexpected trace header key");
    return tokens[1];
}

struct Graph {
    std::uint64_t vertices;
    std::vector<InputEdge> edges; // Independent canonical endpoint/weight ledger.
};
Graph read_graph(const std::string& path) {
    Reader reader(path, 32U * 1024U * 1024U);
    const auto counts = fields(reader.line(), 2);
    Graph graph{number(counts[0], max_vertices), {}};
    const auto count = number(counts[1], max_edges);
    for (std::uint64_t i = 0; i < count; ++i) {
        const auto tokens = fields(reader.line(), 3);
        const auto u = number(tokens[0], max_vertices - 1);
        const auto v = number(tokens[1], max_vertices - 1);
        const auto w = number(tokens[2], max_weight);
        require(u < graph.vertices && v < graph.vertices, "invalid graph vertex");
        InputEdge edge{static_cast<std::int64_t>(u), static_cast<std::int64_t>(v), static_cast<std::int64_t>(w)};
        if (!graph.edges.empty()) {
            const auto& previous = graph.edges.back();
            require(std::make_pair(previous.source, previous.destination) < std::make_pair(edge.source, edge.destination),
                    "graph endpoints must be unique and sorted");
        }
        graph.edges.push_back(edge);
    }
    reader.done();
    return graph;
}
struct Update { std::uint64_t u, v, old_weight, new_weight; };
std::vector<Update> read_trace(const Options& options, Report& report) {
    Reader reader(options.trace_path, 16U * 1024U * 1024U);
    require(reader.line() == "DYNAGRAPH_TRACE 1", "unsupported trace schema/version");
    const auto digest = header(reader, "graph_sha256");
    require(digest.size() == 64 && std::all_of(digest.begin(), digest.end(), [](char ch) {
        return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
    }), "malformed declared graph SHA-256");
    report.declared_graph_sha256 = std::string(digest);
    require(header(reader, "generator") == "dynagraph-trace-v1", "unsupported trace generator");
    require(header(reader, "graph_generator") == "dynagraph-graph-v1", "unsupported graph generator");
    require(header(reader, "prng") == "splitmix64-v1", "unsupported PRNG version");
    for (const auto key : {"graph_seed", "weight_seed", "source_seed", "trace_seed"}) {
        (void)number(header(reader, key), std::numeric_limits<std::uint64_t>::max());
    }
    require(number(header(reader, "source"), max_vertices - 1) == options.source, "source disagrees with trace");
    report.trace_entries = number(header(reader, "updates"), max_updates);
    std::vector<Update> updates;
    for (std::uint64_t i = 0; i < report.trace_entries; ++i) {
        report.update_index = i;
        const auto tokens = fields(reader.line(), 5);
        require(number(tokens[0], max_updates - 1) == i, "nonconsecutive update index");
        updates.push_back({number(tokens[1], max_vertices - 1), number(tokens[2], max_vertices - 1),
                           number(tokens[3], max_weight), number(tokens[4], max_weight)});
    }
    report.update_index.reset();
    reader.done();
    return updates;
}

// Synchronous Bellman-Ford over the independent ledger, without CSR traversal.
std::vector<Distance> bellman_ford(const Graph& graph, VertexId source) {
    std::vector<Distance> distances(static_cast<std::size_t>(graph.vertices), unreachable_distance);
    distances[source] = 0;
    for (std::uint64_t pass = 1; pass < graph.vertices; ++pass) {
        auto next = distances;
        for (const auto& edge : graph.edges) {
            const auto u = static_cast<std::size_t>(edge.source);
            const auto v = static_cast<std::size_t>(edge.destination);
            const auto weight = static_cast<Distance>(edge.weight);
            if (distances[u] != unreachable_distance && weight < unreachable_distance - distances[u]) {
                next[v] = std::min(next[v], distances[u] + weight);
            }
        }
        if (next == distances) { break; }
        distances.swap(next);
    }
    return distances;
}

std::vector<Distance> check(const Graph& ledger, const AdaptiveSSSPEngine& engine, Report& report) {
    report.category = "graph_mismatch";
    const auto reference = CSRGraph::from_edges(ledger.vertices, ledger.edges);
    require(reference.offsets() == engine.graph().offsets() &&
            reference.destinations() == engine.graph().destinations() &&
            reference.weights() == engine.graph().weights(), "engine graph differs from independent ledger");
    report.category = "distance_mismatch";
    auto expected = dijkstra(reference, engine.source()).distances;
    ++report.recomputations;
    if (ledger.vertices <= 128 && ledger.edges.size() <= 4096) {
        const auto independent = bellman_ford(ledger, engine.source());
        ++report.bellman_ford_checks;
        require(independent == expected, "Dijkstra reference disagrees with Bellman-Ford");
    }
    require(expected == engine.distances(), "engine distances differ from fresh reference");
    return expected;
}

std::string quoted(const std::string& value) {
    std::string result = "\"";
    constexpr char hex[] = "0123456789abcdef";
    for (const unsigned char ch : value) {
        if (ch == '"' || ch == '\\') { result += '\\'; result += static_cast<char>(ch); }
        else if (ch < 32 || ch >= 127) {
            result += "\\u00"; result += hex[ch >> 4]; result += hex[ch & 15];
        } else { result += static_cast<char>(ch); }
    }
    return result + '"';
}
} // namespace

void replay(const Options& options, Report& report) {
    report.category = "artifact_validation";
    auto ledger = read_graph(options.graph_path);
    const auto updates = read_trace(options, report);
    require(options.source < ledger.vertices, "source outside graph");
    report.category = "initialization";
    auto engine = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(ledger.vertices, ledger.edges),
                                                options.source, options.config);
    auto previous = check(ledger, engine, report);
    for (std::size_t index = 0; index < updates.size(); ++index) {
        report.update_index = index;
        report.category = "trace_validation";
        const auto& update = updates[index];
        require(update.u < ledger.vertices && update.v < ledger.vertices, "invalid update vertex");
        const auto key = std::make_pair(static_cast<std::int64_t>(update.u), static_cast<std::int64_t>(update.v));
        const auto edge = std::lower_bound(ledger.edges.begin(), ledger.edges.end(), key,
            [](const InputEdge& candidate, const auto& pair) {
                return std::make_pair(candidate.source, candidate.destination) < pair;
            });
        require(edge != ledger.edges.end() && std::make_pair(edge->source, edge->destination) == key,
                "nonexistent update edge");
        require(static_cast<std::uint64_t>(edge->weight) == update.old_weight, "expected old weight mismatch");
        require(update.new_weight <= update.old_weight, "weight increase");
        edge->weight = static_cast<std::int64_t>(update.new_weight);
        report.category = "execution";
        const auto result = engine.decrease(update.u, update.v, edge->weight);
        ++report.executed;
        auto expected = check(ledger, engine, report);
        report.category = "metadata_mismatch";
        std::uint64_t improved = 0;
        for (std::size_t v = 0; v < expected.size(); ++v) {
            require(expected[v] <= previous[v], "decrease increased a reference distance");
            if (expected[v] < previous[v]) { ++improved; }
        }
        const auto outcome = update.new_weight == update.old_weight ? DecreaseOutcome::unchanged_weight :
            (improved == 0 ? DecreaseOutcome::weight_only : DecreaseOutcome::distances_repaired);
        require(result.update.old_weight == update.old_weight && result.update.new_weight == update.new_weight &&
                result.update.vertices_improved == improved && result.update.outcome == outcome,
                "incorrect update metadata");
        // Equal requests always bypass, including execute_selected. Executed forced
        // policies must select their configured strategy; shared bypasses are retained.
        if (update.new_weight == update.old_weight) {
            require(result.decision.route == DecisionRoute::unchanged && !result.decision.selected &&
                    result.decision.reason == DecisionReason::equal_weight, "incorrect equal-weight decision");
        } else if (result.decision.route == DecisionRoute::execute) {
            require(result.decision.selected.has_value(), "executed decision lacks strategy");
            if (options.config.kind != PolicyKind::heuristic) {
                const auto strategy = options.config.kind == PolicyKind::always_dijkstra ? Strategy::dijkstra :
                    (options.config.kind == PolicyKind::always_delta_stepping ? Strategy::delta_stepping : Strategy::incremental);
                require(result.decision.selected == strategy && result.decision.reason == DecisionReason::forced,
                        "forced policy selected another strategy");
            }
        } else {
            require(options.config.no_effect == NoEffectMode::shared_fast_path && improved == 0 &&
                    result.decision.route == DecisionRoute::weight_only && !result.decision.selected &&
                    result.decision.reason == DecisionReason::no_distance_effect, "incorrect no-effect decision");
        }
        previous.swap(expected);
        ++report.verified;
    }
    // Initial check covers empty traces; last per-update check covers nonempty traces.
    report.final_distances = std::move(previous);
    for (const auto& edge : ledger.edges) { report.final_weights.push_back(static_cast<EdgeWeight>(edge.weight)); }
    report.update_index.reset();
    report.category = "none";
    report.success = true;
}

std::string json_record(const Options& options, const Report& report) {
    std::ostringstream out;
    out << "{\"schema_version\":1,\"success\":" << (report.success ? "true" : "false")
        << ",\"failure_category\":" << quoted(report.category) << ",\"message\":" << quoted(report.message)
        << ",\"failing_update_index\":";
    if (report.update_index) { out << *report.update_index; } else { out << "null"; }
    out << ",\"graph_path\":" << quoted(options.graph_path) << ",\"trace_path\":" << quoted(options.trace_path)
        << ",\"declared_graph_sha256\":" << quoted(report.declared_graph_sha256)
        << ",\"identity_origin\":\"unverified_artifact_metadata\",\"integrity\":\"external_python_verifier_required\""
        << ",\"policy\":" << quoted(options.policy) << ",\"source\":" << options.source
        << ",\"delta\":" << options.config.parallel.delta << ",\"requested_workers\":" << options.config.parallel.thread_count
        << ",\"no_effect\":" << quoted(options.config.no_effect == NoEffectMode::shared_fast_path ? "shared_fast_path" : "execute_selected")
        << ",\"verification_level\":\"full\",\"trace_entries\":" << report.trace_entries
        << ",\"updates_executed\":" << report.executed << ",\"updates_verified\":" << report.verified
        << ",\"reference_recomputations\":" << report.recomputations << ",\"bellman_ford_checks\":" << report.bellman_ford_checks
        << ",\"final_graph_verified\":" << (report.success ? "true" : "false")
        << ",\"final_distances_verified\":" << (report.success ? "true" : "false");
    if (report.success) {
        out << ",\"final_weights\":[";
        for (std::size_t i = 0; i < report.final_weights.size(); ++i) {
            if (i != 0) { out << ','; } out << report.final_weights[i];
        }
        out << "],\"final_distances\":[";
        for (std::size_t i = 0; i < report.final_distances.size(); ++i) {
            if (i != 0) { out << ','; }
            if (report.final_distances[i] == unreachable_distance) { out << "null"; }
            else { out << report.final_distances[i]; }
        }
        out << ']';
    }
    out << "}\n";
    return out.str();
}
} // namespace dynagraph::benchmark
