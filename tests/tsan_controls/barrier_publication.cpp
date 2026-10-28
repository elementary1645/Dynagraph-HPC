// Race-free vector publication: no nowait access crosses a missing barrier.
#include <array>
#include <cstddef>
#include <iostream>
#include <omp.h>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2 || (std::string(argv[1]) != "implicit" && std::string(argv[1]) != "explicit")) { return 2; }
    const bool implicit = std::string(argv[1]) == "implicit";
    std::vector<int> work;
    std::array<std::size_t, 2> observations{}; // Each participating thread owns its slot.
    std::array<std::size_t, 2> visits{};
    int team = 0;
#pragma omp parallel num_threads(2) default(none) shared(work, observations, visits, team, implicit, std::cerr)
    {
#pragma omp single
        { team = omp_get_num_threads(); std::cerr << "C actual_team=" << team << '\n'; }
        for (int round = 0; round < 8; ++round) {
            if (implicit) {
#pragma omp single
                {
                    work.clear();
                    for (int item = 0; item < 32 + round; ++item) { work.push_back(1); }
                } // Implicit publication barrier.
            } else {
#pragma omp single nowait
                {
                    work.clear();
                    for (int item = 0; item < 32 + round; ++item) { work.push_back(1); }
                }
#pragma omp barrier
            }
            const auto thread = static_cast<std::size_t>(omp_get_thread_num());
            observations[thread] += work.size();
#pragma omp for schedule(dynamic, 1)
            for (std::size_t item = 0; item < work.size(); ++item) { visits[thread] += static_cast<std::size_t>(work[item]); }
            // Implicit completion barrier protects reads from the next growth.
        }
    }
    constexpr std::size_t expected = 284; // sum(32..39).
    std::cout << "C race-free " << (implicit ? "implicit" : "explicit") << " actual_team=" << team
              << " visits=" << visits[0] + visits[1] << '\n';
    if (team < 1 || team > 2 || visits[0] + visits[1] != expected) { return 3; }
    for (int thread = 0; thread < team; ++thread) {
        if (observations[static_cast<std::size_t>(thread)] != expected) { return 3; }
    }
}
