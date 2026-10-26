#pragma once

#include "dynagraph/graph/csr_graph.hpp"

#include <filesystem>
#include <istream>

namespace dynagraph {

// First nonblank line: V E. Exactly E nonblank records: source destination weight.
// Tokens are unsigned decimal integers, IDs are zero-based, comments unsupported.
// Invalid syntax/records: invalid_argument; counts: length_error;
// file/read errors: runtime_error (or ios_base::failure for throwing streams).
[[nodiscard]] CSRGraph load_edge_list(std::istream& input);
[[nodiscard]] CSRGraph load_edge_list_file(const std::filesystem::path& path);

} // namespace dynagraph
