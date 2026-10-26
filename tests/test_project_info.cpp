#include "dynagraph/project_info.hpp"
#include "test_support.hpp"

int main() {
    return dynagraph::test::run("library metadata", [] {
        dynagraph::test::require(!dynagraph::version().empty(), "Version must be present");
        dynagraph::test::require(dynagraph::openmp_spec_date() == _OPENMP,
                                "Library and consumer must agree on OpenMP support");
    });
}
