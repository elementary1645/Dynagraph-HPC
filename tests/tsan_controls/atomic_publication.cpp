// Race-free ordinary-thread release/acquire publication of a non-atomic payload.
#include <atomic>
#include <cstddef>
#include <iostream>
#include <omp.h>
#include <thread>
#include <vector>

int main() {
    std::cerr << "D atomic publication; runtime_max_threads=" << omp_get_max_threads() << '\n';
    std::vector<int> payload;
    std::atomic<bool> ready{false};
    std::size_t observed = 0;
    std::thread producer([&] {
        for (int item = 0; item < 32; ++item) { payload.push_back(item); }
        ready.store(true, std::memory_order_release);
    });
    std::thread consumer([&] {
        while (!ready.load(std::memory_order_acquire)) { std::this_thread::yield(); }
        observed = payload.size();
    });
    producer.join(); consumer.join();
    std::cout << "D observed=" << observed << '\n';
    return observed == 32 ? 0 : 3;
}
