#include "dynagraph/graph/csr_graph.hpp"
#include "validation.hpp"

#include <algorithm>
#include <stdexcept>
#include <string>

namespace dynagraph {

CSRGraph::CSRGraph() : offsets_(1, 0) {}

CSRGraph::CSRGraph(CSRGraph&& other) : CSRGraph() {
    swap(other);
}

CSRGraph& CSRGraph::operator=(CSRGraph other) noexcept {
    swap(other);
    return *this;
}

void CSRGraph::swap(CSRGraph& other) noexcept {
    offsets_.swap(other.offsets_);
    destinations_.swap(other.destinations_);
    weights_.swap(other.weights_);
}

CSRGraph CSRGraph::from_edges(std::uint64_t vertices, std::vector<InputEdge> edges) {
    detail::validate_sizes(vertices, static_cast<std::uint64_t>(edges.size()));
    for (const auto& edge : edges) {
        if (edge.source < 0 || static_cast<std::uint64_t>(edge.source) >= vertices ||
            edge.destination < 0 || static_cast<std::uint64_t>(edge.destination) >= vertices) {
            throw std::invalid_argument("edge (" + std::to_string(edge.source) + ", " +
                                        std::to_string(edge.destination) +
                                        ") has a vertex outside [0, V)");
        }
        detail::validate_weight(edge.weight);
    }
    std::sort(edges.begin(), edges.end(), [](const InputEdge& a, const InputEdge& b) {
        return a.source < b.source || (a.source == b.source && a.destination < b.destination);
    });
    for (std::size_t i = 1; i < edges.size(); ++i) {
        if (edges[i - 1].source == edges[i].source &&
            edges[i - 1].destination == edges[i].destination) {
            throw std::invalid_argument("duplicate directed edge (" + std::to_string(edges[i].source) +
                                        ", " + std::to_string(edges[i].destination) + ")");
        }
    }

    CSRGraph graph;
    graph.offsets_.assign(static_cast<std::size_t>(vertices) + 1, 0);
    graph.destinations_.reserve(edges.size());
    graph.weights_.reserve(edges.size());
    for (const auto& edge : edges) {
        ++graph.offsets_[static_cast<std::size_t>(edge.source) + 1];
        graph.destinations_.push_back(static_cast<VertexId>(edge.destination));
        graph.weights_.push_back(static_cast<EdgeWeight>(edge.weight));
    }
    for (std::size_t i = 1; i < graph.offsets_.size(); ++i) {
        graph.offsets_[i] += graph.offsets_[i - 1]; // Every prefix is <= E.
    }
    return graph;
}

std::uint64_t CSRGraph::vertex_count() const noexcept {
    return static_cast<std::uint64_t>(offsets_.size() - 1);
}

EdgeOffset CSRGraph::edge_count() const noexcept {
    return static_cast<EdgeOffset>(destinations_.size());
}

void CSRGraph::validate_vertex(std::uint64_t vertex) const {
    if (vertex >= vertex_count()) {
        throw std::out_of_range("vertex " + std::to_string(vertex) + " outside [0, V)");
    }
}

EdgeOffset CSRGraph::degree(std::uint64_t vertex) const {
    validate_vertex(vertex);
    const auto index = static_cast<std::size_t>(vertex);
    return offsets_[index + 1] - offsets_[index];
}

std::size_t CSRGraph::find_edge(std::uint64_t source, std::uint64_t destination) const {
    validate_vertex(source);
    validate_vertex(destination);
    const auto row = static_cast<std::size_t>(source);
    const auto first = destinations_.begin() + static_cast<std::ptrdiff_t>(offsets_[row]);
    const auto last = destinations_.begin() + static_cast<std::ptrdiff_t>(offsets_[row + 1]);
    const auto found = std::lower_bound(first, last, static_cast<VertexId>(destination));
    if (found == last || *found != destination) {
        throw std::out_of_range("directed edge (" + std::to_string(source) + ", " +
                                std::to_string(destination) + ") does not exist");
    }
    return static_cast<std::size_t>(found - destinations_.begin());
}

EdgeWeight CSRGraph::weight(std::uint64_t source, std::uint64_t destination) const {
    return weights_[find_edge(source, destination)];
}

EdgeWeight CSRGraph::replace_weight(std::uint64_t source, std::uint64_t destination,
                                   std::int64_t new_weight) {
    const auto replacement = detail::validate_weight(new_weight);
    const auto index = find_edge(source, destination);
    const auto previous = weights_[index];
    weights_[index] = replacement;
    return previous;
}

CSRGraph::EdgeIterator::reference CSRGraph::EdgeIterator::operator*() const {
    return {static_cast<EdgeOffset>(index_), graph_->destinations_[index_], graph_->weights_[index_]};
}

CSRGraph::EdgeRange CSRGraph::outgoing_edges(std::uint64_t vertex) const {
    validate_vertex(vertex);
    const auto row = static_cast<std::size_t>(vertex);
    return {EdgeIterator(this, static_cast<std::size_t>(offsets_[row])),
            EdgeIterator(this, static_cast<std::size_t>(offsets_[row + 1])),
            offsets_[row + 1] - offsets_[row]};
}

} // namespace dynagraph
