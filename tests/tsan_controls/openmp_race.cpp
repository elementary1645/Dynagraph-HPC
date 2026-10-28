// Intentional data race: calibration only, never register in normal CTest/CI.
#include <iostream>
#include <omp.h>

int main() {
    volatile int value = 0;
#pragma omp parallel num_threads(2) default(none) shared(value, std::cerr)
    {
        if (omp_get_thread_num() == 0) { std::cerr << "B intentional OpenMP race; actual_team=" << omp_get_num_threads() << '\n'; }
#pragma omp barrier
        for (int step = 0; step < 10000; ++step) { ++value; }
    }
    std::cout << "value=" << value << '\n';
}
