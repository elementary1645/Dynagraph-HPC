#include "adversarial_test_support.hpp"

namespace {
using namespace dynagraph;
using namespace dynagraph::test::system;
Case fixture(std::uint32_t index) { return adversarial_fixture(index); }
}
int main(int argc, char** argv) {
    Options opt;
    try {
        opt = options(argc, argv);
        if (opt.profile != "fast" || (opt.case_index && *opt.case_index > 13)) {
            throw std::invalid_argument("adversarial fixtures support fast and cases 0..13 only");
        }
        if (opt.source && *opt.source >= fixture(*opt.case_index).vertices) { throw std::invalid_argument("source outside fixture"); }
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 2; }
    return test::run("14 adversarial fixtures in both no-effect modes", [&] {
        Counts counts;
        for (auto index = opt.case_index.value_or(0); index < (opt.case_index ? *opt.case_index + 1 : 14U); ++index) {
            auto c = fixture(index);
            for (const auto mode : {NoEffectMode::shared_fast_path, NoEffectMode::execute_selected}) {
                c.mode = mode;
                trace(c, opt.source.value_or(0), opt, index, counts);
            }
        }
        std::cout << "traces=" << counts.traces << " updates=" << counts.updates << " checkpoints=" << counts.checkpoints << '\n';
    });
}
