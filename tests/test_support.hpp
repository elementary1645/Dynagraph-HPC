#pragma once

#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>

namespace dynagraph::test {

// Checks remain active in Release builds where assert may be disabled.
inline void require(bool condition, std::string_view message) {
    if (!condition) {
        throw std::runtime_error(std::string(message));
    }
}

template <typename Exception, typename Function>
void require_throws(Function function, std::string_view message_fragment) {
    try {
        function();
    } catch (const Exception& error) {
        if (std::string_view(error.what()).find(message_fragment) == std::string_view::npos) {
            throw std::runtime_error("Expected diagnostic containing '" + std::string(message_fragment) +
                                     "', got: " + error.what());
        }
        return;
    }
    throw std::runtime_error("Expected exception was not thrown");
}

template <typename Test>
int run(std::string_view name, Test test) {
    try {
        test();
        std::cout << "PASS: " << name << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << name << ": " << error.what() << '\n';
        return 1;
    } catch (...) {
        std::cerr << "FAIL: " << name << ": unknown exception\n";
        return 1;
    }
}

} // namespace dynagraph::test
