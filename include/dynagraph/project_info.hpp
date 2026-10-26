#pragma once

#include <string_view>

namespace dynagraph {

// Build metadata only; no graph processing is implemented in Phase 0.
[[nodiscard]] std::string_view version() noexcept;
[[nodiscard]] int openmp_spec_date() noexcept;

} // namespace dynagraph
