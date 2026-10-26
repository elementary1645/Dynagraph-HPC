#include "dynagraph/graph/csr_graph.hpp"
#include "test_support.hpp"

#include <algorithm>
#include <cstdint>
#include <iterator>
#include <limits>
#include <map>
#include <numeric>
#include <random>
#include <stdexcept>
#include <utility>
#include <vector>

namespace {

using dynagraph::CSRGraph;
using dynagraph::EdgeOffset;
using dynagraph::EdgeWeight;
using dynagraph::InputEdge;
using dynagraph::VertexId;
using dynagraph::test::require;
using dynagraph::test::require_throws;

void check_invariants(const CSRGraph& graph) {
    require(graph.offsets().size() == graph.vertex_count() + 1, "Offsets must have V+1 entries");
    require(graph.offsets().front() == 0, "Offsets must start at zero");
    require(graph.offsets().back() == graph.edge_count(), "Last offset must equal E");
    require(graph.weights().size() == graph.edge_count(), "Weights must have E entries");
    require(std::is_sorted(graph.offsets().begin(), graph.offsets().end()), "Offsets must be monotonic");
    for (std::uint64_t vertex = 0; vertex < graph.vertex_count(); ++vertex) {
        const auto edges = graph.outgoing_edges(vertex);
        require(edges.size() == graph.degree(vertex), "Degree/range size must agree");
        require(static_cast<EdgeOffset>(std::distance(edges.begin(), edges.end())) == edges.size(),
                "Iterator distance must match degree");
        std::uint64_t visited = 0;
        VertexId previous = 0;
        for (const auto edge : edges) {
            require(edge.destination < graph.vertex_count(), "Destination must be in range");
            require(visited == 0 || previous < edge.destination, "Rows must be strictly sorted");
            require(edge.id == graph.offsets()[static_cast<std::size_t>(vertex)] + visited,
                    "Edge ID must equal its CSR index");
            require(edge.weight == graph.weight(vertex, edge.destination), "Lookup and iteration must agree");
            previous = edge.destination;
            ++visited;
        }
        require(visited == graph.degree(vertex), "All outgoing edges must be visited");
    }
}

void empty_and_isolated() {
    const CSRGraph empty;
    check_invariants(empty);
    require(empty.vertex_count() == 0 && empty.edge_count() == 0, "Default graph must be empty");
    require(empty.offsets() == std::vector<EdgeOffset>{0}, "Empty graph offsets");
    const auto built_empty = CSRGraph::from_edges(0, {});
    require(built_empty.offsets() == empty.offsets(), "Empty builder must match default");
    require_throws<std::out_of_range>([&] { (void)empty.degree(0); }, "outside [0, V)");
    require_throws<std::out_of_range>([&] { (void)empty.outgoing_edges(0); }, "outside [0, V)");
    for (const auto count : {1U, 5U}) {
        const auto graph = CSRGraph::from_edges(count, {});
        check_invariants(graph);
        require(graph.vertex_count() == count && graph.edge_count() == 0, "Isolated vertex counts");
        require(graph.offsets() == std::vector<EdgeOffset>(count + 1, 0), "Isolated offsets");
        for (std::uint64_t v = 0; v < count; ++v) {
            require(graph.outgoing_edges(v).begin() == graph.outgoing_edges(v).end(), "Isolated range empty");
        }
    }
}

void ordering_and_semantics() {
    const std::vector<InputEdge> records{{3, 4, 9}, {0, 2, 7}, {1, 1, 0}, {0, 1, 4}, {4, 3, 5}};
    const auto graph = CSRGraph::from_edges(6, records);
    check_invariants(graph);
    require(records.front().source == 3, "Lvalue edge list must not be mutated");
    require(graph.offsets() == std::vector<EdgeOffset>{0, 2, 3, 3, 4, 5, 5}, "Exact CSR offsets");
    require(graph.destinations() == std::vector<VertexId>{1, 2, 1, 4, 3}, "Exact destination order");
    require(graph.weights() == std::vector<EdgeWeight>{4, 7, 0, 9, 5}, "Weights must follow sorted edges");
    require(graph.weight(1, 1) == 0, "Zero-weight self-loop must be preserved");
    require_throws<std::out_of_range>([&] { (void)graph.weight(1, 0); }, "does not exist");
    require_throws<std::out_of_range>([&] { (void)graph.weight(2, 0); }, "does not exist");
    auto iterator = graph.outgoing_edges(0).begin();
    require(iterator->destination == 1 && iterator->weight == 4, "Iterator arrow proxy");
    const auto old_iterator = iterator++;
    require(old_iterator->destination == 1 && iterator->destination == 2, "Postfix iteration");
    require(++iterator == graph.outgoing_edges(0).end(), "Prefix iteration reaches end");
    require(CSRGraph::EdgeIterator{} == CSRGraph::EdgeIterator{}, "Default iterators compare equal");

    auto permutation = records;
    std::sort(permutation.begin(), permutation.end(), [](const InputEdge& a, const InputEdge& b) {
        return a.source < b.source || (a.source == b.source && a.destination < b.destination);
    });
    const auto less = [](const InputEdge& a, const InputEdge& b) {
        return a.source < b.source || (a.source == b.source && a.destination < b.destination);
    };
    do {
        const auto reordered = CSRGraph::from_edges(6, permutation);
        require(reordered.offsets() == graph.offsets() && reordered.destinations() == graph.destinations() &&
                reordered.weights() == graph.weights(), "Every permutation must produce identical CSR");
    } while (std::next_permutation(permutation.begin(), permutation.end(), less));
}

void invalid_records_and_limits() {
    require_throws<std::invalid_argument>([] { (void)CSRGraph::from_edges(1, {{0, 0, 1}, {0, 0, 2}}); },
                                          "duplicate directed edge (0, 0)");
    require_throws<std::invalid_argument>([] {
        (void)CSRGraph::from_edges(3, {{1, 2, 0}, {0, 1, 9}, {1, 2, 0}});
    }, "duplicate directed edge (1, 2)");
    for (const auto& edge : std::vector<InputEdge>{{-1, 0, 1}, {0, -1, 1}, {2, 0, 1}, {0, 2, 1},
                                                  {std::numeric_limits<std::int64_t>::max(), 0, 1}}) {
        require_throws<std::invalid_argument>([&] { (void)CSRGraph::from_edges(2, {edge}); }, "outside [0, V)");
    }
    require_throws<std::invalid_argument>([] { (void)CSRGraph::from_edges(0, {{0, 0, 0}}); }, "outside [0, V)");
    for (const std::int64_t invalid : {-1LL, 4294967296LL, 9223372036854775807LL}) {
        require_throws<std::invalid_argument>([&] { (void)CSRGraph::from_edges(1, {{0, 0, invalid}}); },
                                              "edge weight must be");
    }
    const auto max_weight = CSRGraph::from_edges(1, {{0, 0, 4294967295LL}});
    require(max_weight.weight(0, 0) == std::numeric_limits<EdgeWeight>::max(), "Maximum weight supported");
    require_throws<std::length_error>([] { (void)CSRGraph::from_edges(4294967296ULL, {}); }, "vertex count");
    require_throws<std::length_error>([] {
        (void)CSRGraph::from_edges(std::numeric_limits<std::uint64_t>::max(), {});
    }, "vertex count");
    require_throws<std::out_of_range>([&] { (void)max_weight.degree(1); }, "outside [0, V)");
    require_throws<std::out_of_range>([&] { (void)max_weight.weight(0, 4294967296ULL); }, "outside [0, V)");
}

void updates_and_value_semantics() {
    auto graph = CSRGraph::from_edges(4, {{0, 1, 9}, {0, 3, 4}, {1, 1, 0}});
    const auto original = graph;
    const auto offsets = graph.offsets();
    const auto destinations = graph.destinations();
    const auto range = graph.outgoing_edges(0);
    require(graph.replace_weight(0, 1, 0) == 9, "Replacement returns previous weight");
    require(graph.replace_weight(0, 3, 4294967295LL) == 4, "Storage allows full-range replacement");
    require(graph.replace_weight(1, 1, 7) == 0, "Self-loop update");
    require(graph.replace_weight(1, 1, 7) == 7, "Idempotent update");
    require(range.begin()->weight == 0, "Existing iterator reads current weight");
    require(graph.offsets() == offsets && graph.destinations() == destinations, "Updates preserve topology");
    require(original.weight(0, 1) == 9, "Copies own independent weight arrays");
    const auto weights = graph.weights();
    for (const auto invalid : {-1LL, 4294967296LL}) {
        require_throws<std::invalid_argument>([&] { graph.replace_weight(0, 1, invalid); }, "edge weight");
    }
    require_throws<std::out_of_range>([&] { graph.replace_weight(1, 0, 2); }, "does not exist");
    require_throws<std::out_of_range>([&] { graph.replace_weight(2, 0, 2); }, "does not exist");
    require_throws<std::out_of_range>([&] { graph.replace_weight(4, 0, 2); }, "outside [0, V)");
    require_throws<std::out_of_range>([&] { graph.replace_weight(0, 4, 2); }, "outside [0, V)");
    require(graph.weights() == weights, "Failed updates must not modify any weights");
    check_invariants(graph);

    auto moved = std::move(graph);
    check_invariants(graph);
    require(graph.vertex_count() == 0, "Moved-from graph must be empty");
    check_invariants(moved);
    graph = original;
    require(graph.weights() == original.weights(), "Copy assignment");
    graph = std::move(moved);
    check_invariants(moved);
    require(moved.vertex_count() == 0, "Move assignment preserves empty source invariant");
    graph = graph;
    check_invariants(graph);
    const auto move_assign = [](CSRGraph& target, CSRGraph& source) { target = std::move(source); };
    move_assign(graph, graph);
    check_invariants(graph);
    require(graph.weights() == weights, "Self-assignment must preserve value");
}

void randomized_graphs() {
    constexpr std::uint32_t seed = 0xD1A6A123U;
    std::mt19937 random(seed);
    for (unsigned trial = 0; trial < 250; ++trial) {
        const auto vertices = static_cast<std::uint32_t>(random() % 17U);
        std::vector<InputEdge> edges;
        std::map<std::pair<std::uint32_t, std::uint32_t>, EdgeWeight> oracle;
        for (std::uint32_t source = 0; source < vertices; ++source) {
            for (std::uint32_t destination = 0; destination < vertices; ++destination) {
                if (random() % 4U != 0) { continue; }
                const auto weight = static_cast<EdgeWeight>(random());
                edges.push_back({source, destination, weight});
                oracle.emplace(std::make_pair(source, destination), weight);
            }
        }
        const auto canonical = CSRGraph::from_edges(vertices, edges);
        // Explicit Fisher-Yates avoids implementation-dependent std::shuffle distributions.
        for (std::size_t size = edges.size(); size > 1; --size) {
            std::swap(edges[size - 1], edges[static_cast<std::size_t>(random()) % size]);
        }
        auto graph = CSRGraph::from_edges(vertices, std::move(edges));
        check_invariants(graph);
        require(graph.edge_count() == oracle.size(), "Randomized graph edge count");
        require(graph.offsets() == canonical.offsets() && graph.destinations() == canonical.destinations() &&
                graph.weights() == canonical.weights(), "Randomized construction must be deterministic");
        std::size_t index = 0;
        std::vector<EdgeOffset> expected_offsets(static_cast<std::size_t>(vertices) + 1, 0);
        for (const auto& entry : oracle) {
            const auto source = entry.first.first;
            const auto destination = entry.first.second;
            require(graph.destinations()[index] == destination && graph.weights()[index] == entry.second,
                    "CSR must match independent ordered-map oracle");
            ++expected_offsets[static_cast<std::size_t>(source) + 1];
            const auto replacement = static_cast<EdgeWeight>(random());
            require(graph.replace_weight(source, destination, replacement) == entry.second,
                    "Randomized update previous value");
            require(graph.weight(source, destination) == replacement, "Randomized update lookup");
            ++index;
        }
        std::partial_sum(expected_offsets.begin(), expected_offsets.end(), expected_offsets.begin());
        require(graph.offsets() == expected_offsets, "Offsets must match independent degree counts");
    }
}

} // namespace

int main() {
    int failures = 0;
    failures += dynagraph::test::run("empty and isolated vertices", empty_and_isolated);
    failures += dynagraph::test::run("CSR ordering and directed semantics", ordering_and_semantics);
    failures += dynagraph::test::run("invalid records and supported limits", invalid_records_and_limits);
    failures += dynagraph::test::run("weight updates and value semantics", updates_and_value_semantics);
    failures += dynagraph::test::run("250 randomized graphs, seed 0xD1A6A123", randomized_graphs);
    return failures == 0 ? 0 : 1;
}
