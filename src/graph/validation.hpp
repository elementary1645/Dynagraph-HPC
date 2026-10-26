#pragma once

#include "dynagraph/graph/csr_graph.hpp"

#include <limits>
#include <stdexcept>

namespace dynagraph::detail {

template <typename T>
void validate_array_size(std::uint64_t count) {
    // Check byte multiplication, index conversion, and allocator/iterator limits
    // before any count-sized allocation. This does not promise available RAM.
    if (count > std::numeric_limits<std::size_t>::max() / sizeof(T) ||
        count > std::vector<T>{}.max_size()) {
        throw std::length_error("graph array exceeds supported allocation/index range");
    }
}

inline void validate_sizes(std::uint64_t vertices, std::uint64_t edges) {
    if (vertices > CSRGraph::max_vertex_count) {
        throw std::length_error("vertex count exceeds supported maximum (4294967295)");
    }
    // The vertex bound makes vertices+1 safe in uint64_t. Duplicates are
    // diagnosed by the builder even when the input list exceeds V*V records.
    validate_array_size<EdgeOffset>(vertices + 1);
    validate_array_size<VertexId>(edges);
    validate_array_size<EdgeWeight>(edges);
    validate_array_size<InputEdge>(edges);
}

inline EdgeWeight validate_weight(std::int64_t weight) {
    if (weight < 0 || static_cast<std::uint64_t>(weight) > CSRGraph::max_edge_weight) {
        throw std::invalid_argument("edge weight must be in [0, 4294967295]");
    }
    return static_cast<EdgeWeight>(weight);
}

} // namespace dynagraph::detail
