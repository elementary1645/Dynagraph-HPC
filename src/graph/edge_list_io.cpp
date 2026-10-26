#include "dynagraph/graph/edge_list_io.hpp"
#include "validation.hpp"

#include <algorithm>
#include <array>
#include <charconv>
#include <fstream>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>

namespace dynagraph {
namespace {

bool whitespace(char c) {
    return c == ' ' || c == '\t' || c == '\r' || c == '\v' || c == '\f';
}

std::size_t tokenize(std::string_view line, std::array<std::string_view, 4>& tokens) {
    std::size_t count = 0;
    std::size_t position = 0;
    while (position < line.size()) {
        if (whitespace(line[position])) { ++position; continue; }
        const auto start = position;
        while (position < line.size() && !whitespace(line[position])) { ++position; }
        if (count == tokens.size()) { return count; }
        tokens[count++] = line.substr(start, position - start);
    }
    return count;
}

[[noreturn]] void input_error(std::size_t line, const std::string& message) {
    throw std::invalid_argument("edge list line " + std::to_string(line) + ": " + message);
}

std::uint64_t number(std::string_view token, std::size_t line, const char* field) {
    std::uint64_t result = 0;
    const auto parsed = std::from_chars(token.data(), token.data() + token.size(), result, 10);
    if (parsed.ec != std::errc{} || parsed.ptr != token.data() + token.size()) {
        input_error(line, std::string(field) + " must be an unsigned decimal integer in uint64 range");
    }
    return result;
}

} // namespace

CSRGraph load_edge_list(std::istream& input) {
    bool have_header = false;
    std::uint64_t vertices = 0;
    std::uint64_t expected_edges = 0;
    std::vector<InputEdge> edges;
    std::string line;
    std::size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        std::array<std::string_view, 4> tokens{};
        const auto count = tokenize(line, tokens);
        if (count == 0) { continue; }
        if (!have_header) {
            if (count != 2) { input_error(line_number, "expected header: V E"); }
            vertices = number(tokens[0], line_number, "vertex count");
            expected_edges = number(tokens[1], line_number, "edge count");
            try {
                detail::validate_sizes(vertices, expected_edges);
                if (expected_edges > vertices * vertices) {
                    throw std::length_error("edge count exceeds directed simple graph capacity V*V");
                }
            } catch (const std::length_error& error) {
                throw std::length_error("edge list line " + std::to_string(line_number) + ": " + error.what());
            }
            // Do not trust a huge declared E enough to allocate it before reading.
            edges.reserve(static_cast<std::size_t>(std::min<std::uint64_t>(expected_edges, 4096)));
            have_header = true;
            continue;
        }
        if (edges.size() == expected_edges) { input_error(line_number, "more edge records than declared"); }
        if (count != 3) { input_error(line_number, "expected source destination weight"); }
        const auto source = number(tokens[0], line_number, "source");
        const auto destination = number(tokens[1], line_number, "destination");
        const auto weight = number(tokens[2], line_number, "weight");
        if (source >= vertices || destination >= vertices) { input_error(line_number, "vertex outside [0, V)"); }
        if (weight > CSRGraph::max_edge_weight) { input_error(line_number, "weight exceeds 4294967295"); }
        edges.push_back({static_cast<std::int64_t>(source), static_cast<std::int64_t>(destination),
                         static_cast<std::int64_t>(weight)});
    }
    if (input.bad() || (input.fail() && !input.eof())) {
        throw std::runtime_error("edge list read failure after line " + std::to_string(line_number));
    }
    if (!have_header) { input_error(line_number, "missing header: V E"); }
    if (edges.size() != expected_edges) { input_error(line_number, "fewer edge records than declared"); }
    return CSRGraph::from_edges(vertices, std::move(edges));
}

CSRGraph load_edge_list_file(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input.is_open()) { throw std::runtime_error("cannot open edge list file: " + path.string()); }
    try {
        return load_edge_list(input);
    } catch (const std::invalid_argument& error) {
        throw std::invalid_argument(path.string() + ": " + error.what());
    } catch (const std::length_error& error) {
        throw std::length_error(path.string() + ": " + error.what());
    } catch (const std::runtime_error& error) {
        throw std::runtime_error(path.string() + ": " + error.what());
    }
}

} // namespace dynagraph
