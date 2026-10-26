#include "dynagraph/graph/edge_list_io.hpp"
#include "test_support.hpp"

#include <filesystem>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <streambuf>
#include <string>
#include <vector>

namespace {

using dynagraph::test::require;
using dynagraph::test::require_throws;

dynagraph::CSRGraph parse(const std::string& text) {
    std::istringstream input(text);
    return dynagraph::load_edge_list(input);
}

void valid_input() {
    require(parse("0 0").offsets() == std::vector<dynagraph::EdgeOffset>{0}, "Empty graph file");
    require(parse("1 0\n").vertex_count() == 1, "Single isolated vertex file");
    require(parse("3\v0\f\r\n").vertex_count() == 3, "ASCII whitespace separators");
    const auto graph = parse("\n 6\t5\r\n3 4 9\n0 2 7\n\n1 1 0\n0 1 4\n4 3 4294967295\n \t\r\n");
    require(graph.offsets() == std::vector<dynagraph::EdgeOffset>{0, 2, 3, 3, 4, 5, 5}, "Loaded offsets");
    require(graph.weight(1, 1) == 0, "Loaded zero-weight self-loop");
    require(graph.weight(4, 3) == std::numeric_limits<dynagraph::EdgeWeight>::max(), "Loaded max weight");
    require(graph.degree(5) == 0 && graph.degree(2) == 0, "Loaded isolated vertices");
    require(parse("0002 0001\n00 01 0009").weight(0, 1) == 9, "Leading decimal zeros accepted");
    const auto reordered = parse("6 5\n4 3 4294967295\n0 1 4\n1 1 0\n0 2 7\n3 4 9");
    require(graph.destinations() == reordered.destinations() && graph.weights() == reordered.weights(),
            "Load order must not affect CSR");
}

void malformed_input() {
    for (const auto& text : std::vector<std::string>{
             "", " \n\t", "2", "2 1 0", "2 1\n0 1", "2 1\n0 1 1 extra",
             "2 1\n0 1 1 extra tokens", "2 1\n", "2 0\n0 1 1", "2 2\n0 1 1",
             "2 1\n-1 0 1", "2 1\n0 -1 1", "2 1\n0 1 -1", "2 1\n2 0 1",
             "2 1\n0 2 1", "2 1\n0 1 4294967296", "2 1\n0 1 18446744073709551616",
             "18446744073709551616 0", "2 18446744073709551616", "-1 0", "2 -1",
             "+2 0", "2 +1", "2 1\n+0 1 1", "2 1\n0 1 +1", "2 1\n0x0 1 1",
             "2 1\n0 1 1.0", "2 1\n0 1 1e2", "V E", "2 1\na 1 2", "2 1\n0 1 2#x",
             "2 1\n18446744073709551616 1 1", "2 1\n0 18446744073709551616 1",
             "2 1\n18446744073709551615 1 1", "2 1\n0 1 18446744073709551615",
             "# comment\n2 0", "2 0\n# comment", "2 1\n0 1 3\n2 0"}) {
        require_throws<std::invalid_argument>([&] { (void)parse(text); }, "edge list line");
    }
    std::string embedded_nul = "2 1\n0 1 2";
    embedded_nul.push_back('\0');
    require_throws<std::invalid_argument>([&] { (void)parse(embedded_nul); }, "weight");
    require_throws<std::invalid_argument>([] { (void)parse("\n2 1\n0 1 -1"); }, "line 3");
    require_throws<std::invalid_argument>([] { (void)parse("2 2\n0 1 1\n0 1 9"); },
                                          "duplicate directed edge (0, 1)");
    require_throws<std::length_error>([] { (void)parse("4294967296 0"); }, "vertex count");
    require_throws<std::length_error>([] { (void)parse("0 1"); }, "capacity V*V");
    require_throws<std::length_error>([] { (void)parse("1 2"); }, "capacity V*V");
    require_throws<std::length_error>([] {
        (void)parse("4294967295 18446744073709551615");
    }, "allocation/index range");
    // Count fits size arithmetic, but the file is truncated: do not allocate E upfront.
    require_throws<std::invalid_argument>([] { (void)parse("1000000 1000000000000"); }, "fewer edge records");
}

class BrokenBuffer : public std::streambuf {
    int_type underflow() override { throw std::runtime_error("simulated read failure"); }
};

void stream_and_file_errors() {
    BrokenBuffer buffer;
    std::istream broken(&buffer);
    require_throws<std::runtime_error>([&] { (void)dynagraph::load_edge_list(broken); }, "read failure");
    std::istringstream failed("2 0");
    failed.setstate(std::ios::failbit);
    require_throws<std::runtime_error>([&] { (void)dynagraph::load_edge_list(failed); }, "read failure");

    // Each CTest build has its own working directory; clean up even on failures.
    struct Fixture {
        std::filesystem::path path = "phase1a-edge-list-test.tmp";
        ~Fixture() { std::error_code error; std::filesystem::remove(path, error); }
    } fixture;
    {
        std::ofstream output(fixture.path);
        output << "4 2\n0 1 0\n2 3 7\n";
        require(static_cast<bool>(output), "Test fixture must be writable");
    }
    const auto graph = dynagraph::load_edge_list_file(fixture.path);
    require(graph.vertex_count() == 4 && graph.weight(2, 3) == 7, "File loader must read disconnected graph");
    {
        std::ofstream output(fixture.path);
        output << "2 1\n0 1 -1\n";
    }
    require_throws<std::invalid_argument>([&] { (void)dynagraph::load_edge_list_file(fixture.path); },
                                          fixture.path.string() + ": edge list line 2");
    {
        std::ofstream output(fixture.path);
        output << "4294967296 0\n";
    }
    require_throws<std::length_error>([&] { (void)dynagraph::load_edge_list_file(fixture.path); },
                                      fixture.path.string() + ": edge list line 1");
    std::filesystem::remove(fixture.path);
    require_throws<std::runtime_error>([&] { (void)dynagraph::load_edge_list_file(fixture.path); }, "cannot open");
}

} // namespace

int main() {
    int failures = 0;
    failures += dynagraph::test::run("valid edge-list loading", valid_input);
    failures += dynagraph::test::run("malformed input and numeric limits", malformed_input);
    failures += dynagraph::test::run("file loading and I/O errors", stream_and_file_errors);
    return failures == 0 ? 0 : 1;
}
