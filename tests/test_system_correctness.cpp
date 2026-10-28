#include "system_validation_support.hpp"

int main(int argc, char** argv) {
    using namespace dynagraph;
    using namespace dynagraph::test::system;
    Options opt;
    try {
        opt = options(argc, argv);
        if (opt.source && *opt.source >= generate(opt, *opt.case_index).vertices) {
            throw std::invalid_argument("source outside generated graph");
        }
    }
    catch (const std::exception& error) { std::cerr << "validation CLI: " << error.what() << '\n'; return 2; }
    return test::run("shared-trace differential validation", [&] {
        Counts counts;
        const auto bound = limits(opt.profile);
        const auto first = opt.case_index.value_or(0);
        const auto last = opt.case_index ? first + 1 : bound.cases;
        for (auto index = first; index < last; ++index) {
            const auto c = generate(opt, index);
            test::require(c.updates.size() == bound.updates, "never shorten a trace");
            case_hash(counts.generation_hash, c);
            if (opt.source) {
                test::require(*opt.source < c.vertices, "source outside generated graph");
                trace(c, *opt.source, opt, index, counts);
            } else {
                for (const VertexId source : {VertexId{0}, static_cast<VertexId>(c.vertices - 1)}) {
                    trace(c, source, opt, index, counts);
                }
            }
        }
        std::cout << "generator=" << generator_version << " profile=" << opt.profile << " seed=" << opt.seed
                  << " cases=" << last - first << " traces=" << counts.traces << " updates=" << counts.updates
                  << " checkpoints=" << counts.checkpoints << " state_comparisons=" << counts.checkpoints * 8 << '\n'
                  << "observed_standalone_delta_workers=" << counts.minimum_workers << ".." << counts.maximum_workers << '\n'
                  << "generation_fingerprint=" << counts.generation_hash << " state_fingerprint=" << counts.state_hash << '\n';
        std::cout << "decision_reason_counts";
        for (const auto count : counts.decisions) { std::cout << ' ' << count; }
        std::cout << '\n';
    });
}
