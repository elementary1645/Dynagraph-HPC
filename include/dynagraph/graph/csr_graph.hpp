#pragma once

#include <cstddef>
#include <cstdint>
#include <iterator>
#include <limits>
#include <vector>

namespace dynagraph {

using VertexId = std::uint32_t;
using EdgeWeight = std::uint32_t;
using EdgeOffset = std::uint64_t;

// Wide signed inputs allow validation before conversion into storage types.
struct InputEdge {
    std::int64_t source;
    std::int64_t destination;
    std::int64_t weight;
};

struct OutgoingEdge {
    EdgeOffset id;
    VertexId destination;
    EdgeWeight weight;
};

class CSRGraph {
public:
    static constexpr std::uint64_t max_vertex_count = std::numeric_limits<VertexId>::max();
    static constexpr std::uint64_t max_edge_weight = std::numeric_limits<EdgeWeight>::max();

    CSRGraph(); // Valid empty graph, offsets == {0}.
    CSRGraph(const CSRGraph&) = default;
    CSRGraph(CSRGraph&& other); // Leaves other as a valid empty graph.
    CSRGraph& operator=(CSRGraph other) noexcept;

    // Builder: takes ownership of an rvalue list, or copies an lvalue list.
    // Throws invalid_argument for invalid records/duplicates, length_error for
    // unsupported counts, and bad_alloc if the available memory is insufficient.
    [[nodiscard]] static CSRGraph from_edges(std::uint64_t vertex_count,
                                            std::vector<InputEdge> edges);

    [[nodiscard]] std::uint64_t vertex_count() const noexcept;
    [[nodiscard]] EdgeOffset edge_count() const noexcept;
    [[nodiscard]] EdgeOffset degree(std::uint64_t vertex) const;
    [[nodiscard]] const std::vector<EdgeOffset>& offsets() const noexcept { return offsets_; }
    [[nodiscard]] const std::vector<VertexId>& destinations() const noexcept { return destinations_; }
    [[nodiscard]] const std::vector<EdgeWeight>& weights() const noexcept { return weights_; }

    // Invalid endpoints/nonexistent edges throw out_of_range. Invalid weights
    // throw invalid_argument. Failures leave all weights unchanged.
    [[nodiscard]] EdgeWeight weight(std::uint64_t source, std::uint64_t destination) const;
    EdgeWeight replace_weight(std::uint64_t source, std::uint64_t destination,
                              std::int64_t new_weight);

    class EdgeIterator {
    public:
        using iterator_category = std::input_iterator_tag;
        using value_type = OutgoingEdge;
        using difference_type = std::ptrdiff_t;
        using reference = OutgoingEdge;
        struct ArrowProxy {
            OutgoingEdge value;
            const OutgoingEdge* operator->() const noexcept { return &value; }
        };
        using pointer = ArrowProxy;

        EdgeIterator() = default;
        reference operator*() const;
        pointer operator->() const { return {**this}; }
        EdgeIterator& operator++() { ++index_; return *this; }
        EdgeIterator operator++(int) { auto previous = *this; ++*this; return previous; }
        friend bool operator==(const EdgeIterator& a, const EdgeIterator& b) {
            return a.graph_ == b.graph_ && a.index_ == b.index_;
        }
        friend bool operator!=(const EdgeIterator& a, const EdgeIterator& b) { return !(a == b); }

    private:
        friend class CSRGraph;
        EdgeIterator(const CSRGraph* graph, std::size_t index) : graph_(graph), index_(index) {}
        const CSRGraph* graph_ = nullptr;
        std::size_t index_ = 0;
    };

    class EdgeRange {
    public:
        [[nodiscard]] EdgeIterator begin() const noexcept { return begin_; }
        [[nodiscard]] EdgeIterator end() const noexcept { return end_; }
        [[nodiscard]] EdgeOffset size() const noexcept { return size_; }
    private:
        friend class CSRGraph;
        EdgeRange(EdgeIterator begin, EdgeIterator end, EdgeOffset size)
            : begin_(begin), end_(end), size_(size) {}
        EdgeIterator begin_;
        EdgeIterator end_;
        EdgeOffset size_;
    };

    // Read-only, allocation-free range. Dereference returns values, not mutable
    // references. Graph lifetime must cover iteration; no concurrent mutation.
    [[nodiscard]] EdgeRange outgoing_edges(std::uint64_t vertex) const;

private:
    void swap(CSRGraph& other) noexcept;
    void validate_vertex(std::uint64_t vertex) const;
    [[nodiscard]] std::size_t find_edge(std::uint64_t source, std::uint64_t destination) const;
    std::vector<EdgeOffset> offsets_;
    std::vector<VertexId> destinations_;
    std::vector<EdgeWeight> weights_;
};

} // namespace dynagraph
