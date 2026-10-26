#include "dynagraph/project_info.hpp"

#ifndef _OPENMP
#error "DynaGraph-HPC requires OpenMP compilation support"
#endif

namespace dynagraph {

std::string_view version() noexcept {
    return DYNAGRAPH_VERSION;
}

int openmp_spec_date() noexcept {
    return _OPENMP;
}

} // namespace dynagraph
