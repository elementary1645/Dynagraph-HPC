#include "dynagraph/project_info.hpp"
#include "test_support.hpp"

#include <omp.h>

#include <iostream>

int main() {
    return dynagraph::test::run("OpenMP compilation, linking, and execution", [] {
        omp_set_dynamic(0);
        int participants = 0;
        int thread_id_sum = 0;
        int team_size = 0;

#pragma omp parallel num_threads(2) default(none) reduction(+ : participants, thread_id_sum) reduction(max : team_size)
        {
            participants += 1;
            thread_id_sum += omp_get_thread_num();
            team_size = omp_get_num_threads();
        }

        dynagraph::test::require(participants == 2, "Expected two participating threads");
        dynagraph::test::require(team_size == 2, "Expected an OpenMP team of two threads");
        dynagraph::test::require(thread_id_sum == 1, "Expected thread IDs zero and one");
        std::cout << "OpenMP " << dynagraph::openmp_spec_date()
                  << "; team_size=" << team_size
                  << "; participants=" << participants
                  << "; thread_id_sum=" << thread_id_sum << '\n';
    });
}
