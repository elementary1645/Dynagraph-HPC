// Intentional data race: calibration only, never register in normal CTest/CI.
#include <atomic>
#include <iostream>
#include <omp.h>
#include <thread>

int main() {
    std::cerr << "A intentional ordinary-thread race; runtime_max_threads=" << omp_get_max_threads() << '\n';
    volatile int value = 0; // volatile forces accesses; it does not synchronize.
    std::atomic<bool> start{false};
    const auto race = [&] {
        while (!start.load(std::memory_order_acquire)) { std::this_thread::yield(); }
        for (int step = 0; step < 10000; ++step) { ++value; }
    };
    std::thread first(race), second(race);
    start.store(true, std::memory_order_release);
    first.join(); second.join();
    std::cout << "value=" << value << '\n'; // No particular value is required for a racy program.
}
