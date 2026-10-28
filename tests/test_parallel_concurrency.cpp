#include "concurrency_validation_support.hpp"

namespace {
using namespace dynagraph;
namespace cv = dynagraph::test::concurrency;
namespace sv = dynagraph::test::system;
using dynagraph::test::require;

void direct(const cv::Options& opt) {
    std::vector<Distance> deltas = opt.profile == "fast" ? std::vector<Distance>{1, 16, unreachable_distance} :
        std::vector<Distance>(sv::deltas.begin(), sv::deltas.end());
    if (opt.delta) { deltas = {*opt.delta}; }
    const std::vector<int> workers = opt.workers ? std::vector<int>{*opt.workers} : std::vector<int>{1, 2, 4};
    const std::vector<bool> measured = opt.measured ? std::vector<bool>{*opt.measured} : std::vector<bool>{false, true};
    const auto begin = opt.index.value_or(0), end = opt.index ? begin + 1 : opt.profile == "extended" ? 16U : 8U;
    const auto first_repeat = opt.repetition.value_or(0), last_repeat = opt.repetition ? first_repeat + 1 : cv::repetitions(opt);
    std::uint64_t count = 0, generation = 14695981039346656037ULL, state = generation;
    for (auto index = begin; index < end; ++index) {
        cv::Context ctx; ctx.w = cv::workload(index);
        if (opt.source) { ctx.w.source = *opt.source; }
        const auto graph = CSRGraph::from_edges(ctx.w.c.vertices, ctx.w.c.edges);
        ctx.expected = sv::oracle(ctx.w.c.vertices, ctx.w.c.edges, ctx.w.source);
        sv::case_hash(generation, ctx.w.c); sv::hash(generation, ctx.w.source);
        try {
            for (const auto delta : deltas) {
                for (const auto request : workers) {
                    for (const bool mode : measured) {
                        for (auto repeat = first_repeat; repeat < last_repeat; ++repeat) {
                            ctx.delta = delta; ctx.workers = request; ctx.measured = mode; ctx.repetition = repeat;
                            cv::query(opt, ctx, graph, std::cout);
                            for (const auto value : ctx.observed) { sv::hash(state, value); }
                            ++count;
                        }
                    }
                }
            }
        } catch (...) { cv::diagnostic(std::cerr, opt, ctx); throw; }
    }
    const auto expected = static_cast<std::uint64_t>(end - begin) * deltas.size() * workers.size() * measured.size() * (last_repeat - first_repeat);
    require(count == expected, "never reduce direct matrix count");
    std::cout << "{\"type\":\"direct_summary\",\"version\":" << cv::quote(cv::version)
              << ",\"profile\":" << cv::quote(opt.profile) << ",\"workloads\":" << end - begin
              << ",\"queries\":" << count << ",\"generation_fingerprint\":" << generation
              << ",\"state_fingerprint\":" << state << "}\n";
}

void runtime(const cv::Options& opt) {
    std::uint64_t count = 0; int outer_team = 0;
    if (opt.runtime == "nested") {
        const auto w = cv::workload(4); const auto graph = CSRGraph::from_edges(w.c.vertices, w.c.edges);
        const auto expected = sv::oracle(w.c.vertices, w.c.edges, w.source);
        std::array<cv::Client, 2> clients;
        for (std::size_t i = 0; i < clients.size(); ++i) {
            auto& ctx = clients[i].ctx; ctx.w = w; ctx.suite = "runtime"; ctx.workers = 2;
            ctx.client = static_cast<int>(i); ctx.expected = expected;
        }
#pragma omp parallel num_threads(2) default(none) shared(clients, opt, graph, outer_team)
        {
#pragma omp single
            { outer_team = omp_get_num_threads(); }
            auto& client = clients[static_cast<std::size_t>(omp_get_thread_num())];
            client.ctx.outer_team = outer_team;
            try {
                cv::query(opt, client.ctx, graph, client.output);
                if (outer_team > 1 && omp_get_max_active_levels() == 1) { require(client.ctx.actual_workers == "1", "inactive nested team is serialized"); }
            } catch (...) { client.error = std::current_exception(); }
        }
        for (int i = 0; i < outer_team; ++i) {
            auto& client = clients[static_cast<std::size_t>(i)]; std::cout << client.output.str();
            if (client.error) { cv::diagnostic(std::cerr, opt, client.ctx); std::rethrow_exception(client.error); }
            ++count;
        }
    } else {
        for (const auto index : {3U, 4U}) {
            cv::Context ctx; ctx.w = cv::workload(index); ctx.suite = "runtime";
            const auto graph = CSRGraph::from_edges(ctx.w.c.vertices, ctx.w.c.edges);
            ctx.expected = sv::oracle(ctx.w.c.vertices, ctx.w.c.edges, ctx.w.source);
            try {
                const std::vector<int> requests = opt.runtime == "four" ? std::vector<int>{4} : std::vector<int>{0, 2, 4};
                for (const auto request : requests) { ctx.workers = request; cv::query(opt, ctx, graph, std::cout); ++count; }
            } catch (...) { cv::diagnostic(std::cerr, opt, ctx); throw; }
        }
    }
    std::cout << "{\"type\":\"runtime_summary\",\"mode\":" << cv::quote(opt.runtime) << ",\"queries\":" << count
              << ",\"outer_team\":" << outer_team << ",\"dynamic\":" << omp_get_dynamic()
              << ",\"max_active_levels\":" << omp_get_max_active_levels() << ",\"environment\":";
    cv::environment(std::cout); std::cout << "}\n";
}

cv::Workload seeded(const cv::Options& opt, std::uint32_t index) {
    sv::Options base; base.seed = opt.seed;
    cv::Workload w; w.index = index; w.family = "system-validation-v1_seeded"; w.c = sv::generate(base, index);
    w.source = opt.source.value_or(0); return w;
}
void engine_check(cv::Context& ctx, const AdaptiveSSSPEngine& engine, const std::vector<InputEdge>& ledger) {
    ctx.observed = engine.distances(); ctx.returned = true;
    require(ctx.observed == ctx.expected, "adaptive complete oracle agreement");
    sv::graph_equal(engine.graph(), ctx.w.c.vertices, ledger);
}
void engine_update(const cv::Options& opt, cv::Context& ctx, AdaptiveSSSPEngine& engine,
                   const sv::Update& update, const std::vector<InputEdge>& ledger,
                   std::ostream& out, std::optional<Strategy> forced = std::nullopt) {
    const auto before = engine.distances(); ctx.observed = before; ctx.returned = false; ctx.actual_workers = "unavailable"; ctx.selected = "unavailable_until_return";
    AdaptiveMetrics metrics;
    const auto result = engine.decrease(update.u, update.v, update.weight, ctx.measured ? &metrics : nullptr, forced);
    ctx.observed = engine.distances(); ctx.returned = true;
    ctx.selected = result.decision.selected ? sv::strategy_names[static_cast<std::size_t>(*result.decision.selected)] : "none";
    if (ctx.measured && metrics.parallel.actual_threads) { ctx.actual_workers = std::to_string(*metrics.parallel.actual_threads); }
    sv::outcome(result.update, update, before, ctx.expected);
    engine_check(ctx, engine, ledger);
    if (ctx.measured && metrics.parallel.actual_threads) {
        require(*metrics.parallel.actual_threads >= 1 && *metrics.parallel.actual_threads <= ctx.workers, "adaptive actual team bound");
    }
    cv::observation(out, opt, ctx, nullptr, ctx.measured ? &metrics : nullptr);
}

void traces(const cv::Options& opt) {
    std::uint64_t trace_count = 0, updates = 0, comparisons = 0;
    const std::vector<int> workers = opt.workers ? std::vector<int>{*opt.workers} : std::vector<int>{2, 4};
    for (const auto index : cv::trace_cases) {
        if (opt.index && *opt.index != index) { continue; }
        const auto w = seeded(opt, index);
        // Precompute every expected checkpoint before repeated algorithm calls.
        std::vector<std::vector<InputEdge>> ledgers{w.c.edges};
        std::vector<std::vector<Distance>> expected{sv::oracle(w.c.vertices, w.c.edges, w.source)};
        for (const auto& update : w.c.updates) {
            auto next = ledgers.back(); sv::apply(next, update); ledgers.push_back(next);
            expected.push_back(sv::oracle(w.c.vertices, next, w.source));
        }
        require(w.c.updates.size() == 16, "preserve seeded trace length");
        for (const auto request : workers) {
            cv::Context ctx; ctx.w = w; ctx.suite = "traces"; ctx.workers = request; ctx.delta = opt.delta.value_or(w.c.delta);
            try {
                const auto graph = CSRGraph::from_edges(w.c.vertices, w.c.edges);
                const PolicyConfig p{PolicyKind::always_delta_stepping, NoEffectMode::execute_selected, {ctx.delta, request}, w.c.heuristic};
                auto parallel = AdaptiveSSSPEngine::initialize(graph, w.source, p);
                auto heuristic_config = p; heuristic_config.kind = PolicyKind::heuristic;
                auto heuristic = AdaptiveSSSPEngine::initialize(graph, w.source, heuristic_config);
                auto rotating = AdaptiveSSSPEngine::initialize(graph, w.source, p);
                const std::array<AdaptiveSSSPEngine*, 3> engines{&parallel, &heuristic, &rotating};
                const std::array<const char*, 3> names{"always_delta", "heuristic", "rotating_override"};
                for (std::size_t checkpoint = 0; checkpoint < expected.size(); ++checkpoint) {
                    ctx.expected = expected[checkpoint]; ctx.step = static_cast<std::int64_t>(checkpoint) - 1;
                    ctx.measured = checkpoint % 2 == 0;
                    for (std::size_t policy = 0; policy < engines.size(); ++policy) {
                        ctx.policy = names[policy];
                        if (checkpoint != 0) {
                            const auto forced = policy == 2 ? std::optional<Strategy>{sv::strategies[(checkpoint - 1) % 3]} : std::nullopt;
                            engine_update(opt, ctx, *engines[policy], w.c.updates[checkpoint - 1], ledgers[checkpoint], std::cout, forced);
                        } else { engine_check(ctx, *engines[policy], ledgers[checkpoint]); }
                        ++comparisons;
                    }
                    ctx.policy = "standalone_delta"; ctx.selected = "delta"; auto fresh_context = ctx;
                    fresh_context.w.c.edges = ledgers[checkpoint];
                    const auto fresh = CSRGraph::from_edges(w.c.vertices, ledgers[checkpoint]);
                    try { cv::query(opt, fresh_context, fresh, std::cout); }
                    catch (...) { ctx.observed = fresh_context.observed; ctx.returned = fresh_context.returned; ctx.actual_workers = fresh_context.actual_workers; throw; }
                    ++comparisons;
                    sv::graph_equal(graph, w.c.vertices, w.c.edges);
                    if (checkpoint != 0) { ++updates; }
                }
                ++trace_count;
            } catch (...) { cv::diagnostic(std::cerr, opt, ctx); throw; }
        }
    }
    std::cout << "{\"type\":\"trace_summary\",\"traces\":" << trace_count << ",\"updates\":" << updates
              << ",\"state_comparisons\":" << comparisons << "}\n";
}

void clients(const cv::Options& opt) {
    const auto w = cv::workload(4); const auto graph = CSRGraph::from_edges(w.c.vertices, w.c.edges);
    const auto expected = sv::oracle(w.c.vertices, w.c.edges, w.source);
    std::array<cv::Client, 2> independent;
    for (std::size_t i = 0; i < independent.size(); ++i) {
        auto& ctx = independent[i].ctx; ctx.w = w; ctx.suite = "clients"; ctx.policy = "immutable_clients";
        ctx.client = static_cast<int>(i); ctx.workers = 2; ctx.expected = expected;
    }
    cv::two_clients(opt, independent, [&](std::size_t, cv::Client& client) {
        for (unsigned repeat = 0; repeat < 4; ++repeat) {
            client.ctx.repetition = repeat; client.ctx.measured = repeat % 2 == 0;
            cv::query(opt, client.ctx, graph, client.output);
        }
    });
    std::array<cv::Client, 2> separate;
    for (std::size_t i = 0; i < separate.size(); ++i) {
        auto& ctx = separate[i].ctx; ctx.w = seeded(opt, cv::trace_cases[i]); ctx.suite = "clients";
        ctx.policy = "separate_engines"; ctx.client = static_cast<int>(i); ctx.workers = 2;
        ctx.expected = sv::oracle(ctx.w.c.vertices, ctx.w.c.edges, ctx.w.source);
    }
    cv::two_clients(opt, separate, [&](std::size_t, cv::Client& client) {
        auto& ctx = client.ctx; auto ledger = ctx.w.c.edges;
        const auto input = CSRGraph::from_edges(ctx.w.c.vertices, ledger);
        auto engine = AdaptiveSSSPEngine::initialize(input, ctx.w.source,
            {PolicyKind::always_delta_stepping, NoEffectMode::execute_selected, {16, 2}, ctx.w.c.heuristic});
        engine_check(ctx, engine, ledger);
        for (std::size_t step = 0; step < ctx.w.c.updates.size(); ++step) {
            ctx.step = static_cast<std::int64_t>(step); ctx.measured = step % 2 == 0;
            sv::apply(ledger, ctx.w.c.updates[step]); ctx.expected = sv::oracle(ctx.w.c.vertices, ledger, ctx.w.source);
            engine_update(opt, ctx, engine, ctx.w.c.updates[step], ledger, client.output);
            sv::graph_equal(input, ctx.w.c.vertices, ctx.w.c.edges);
        }
    });
    auto history = sv::history_case();
    auto shared_engine = AdaptiveSSSPEngine::initialize(CSRGraph::from_edges(history.vertices, history.edges), 0,
        {PolicyKind::always_delta_stepping, NoEffectMode::execute_selected, {16, 2}, {0, 1, 1}});
    auto authoritative = history.edges; std::vector<sv::Update> committed; std::mutex access;
    std::array<cv::Client, 2> serialized;
    for (std::size_t i = 0; i < serialized.size(); ++i) {
        auto& ctx = serialized[i].ctx; ctx.w.c = history; ctx.w.c.updates.clear(); ctx.w.family = "serialized_history";
        ctx.suite = "clients"; ctx.policy = "serialized_engine"; ctx.client = static_cast<int>(i); ctx.workers = 2;
    }
    { std::lock_guard<std::mutex> guard(access); sv::checkpoint(shared_engine.graph(), shared_engine.distances(), history.vertices, authoritative, 0); }
    cv::two_clients(opt, serialized, [&](std::size_t id, cv::Client& client) {
        auto& ctx = client.ctx;
        for (unsigned repeat = 0; repeat < 4; ++repeat) {
            ctx.repetition = repeat;
            // The lock covers ALL shared engine access, including inspection,
            // authoritative ledger updates and local snapshots for validation.
            std::lock_guard<std::mutex> guard(access);
            auto ledger = authoritative; const VertexId v = id == 0 ? 1U : 95U;
            const auto old = static_cast<EdgeWeight>(ledger[sv::edge_index(ledger, 0, v)].weight);
            const sv::Update update{0, v, old, static_cast<EdgeWeight>(old - (id == 0 ? 10U : 25U))};
            sv::apply(ledger, update); ctx.expected = sv::oracle(history.vertices, ledger, 0);
            auto next_history = committed; next_history.push_back(update);
            ctx.w.c.updates = next_history; ctx.step = static_cast<std::int64_t>(next_history.size()) - 1;
            engine_update(opt, ctx, shared_engine, update, ledger, client.output);
            authoritative = std::move(ledger); committed = std::move(next_history);
        }
    });
    std::cout << "{\"type\":\"client_summary\",\"immutable_queries\":8,\"separate_engine_updates\":32,\"serialized_updates\":8,\"state_comparisons\":51}\n";
}
} // namespace

int main(int argc, char** argv) {
    cv::Options opt;
    try {
        opt = cv::options(argc, argv);
        if (opt.source) {
            const auto w = opt.suite == "traces" ? seeded(opt, *opt.index) : cv::workload(*opt.index);
            if (*opt.source >= w.c.vertices) { throw std::invalid_argument("source outside workload"); }
        }
    } catch (const std::exception& error) { std::cerr << "concurrency CLI: " << error.what() << '\n'; return 2; }
    return dynagraph::test::run("bounded parallel concurrency validation", [&] {
        try {
            if (opt.suite == "all" || opt.suite == "direct") { direct(opt); }
            if (opt.suite == "all" || opt.suite == "runtime") { runtime(opt); }
            if (opt.suite == "all" || opt.suite == "clients") { clients(opt); }
            if (opt.suite == "all" || opt.suite == "traces") { traces(opt); }
        } catch (...) {
            // Also cover setup/allocation failures before a case Context exists.
            // Detailed returned vectors are printed by the case handler when
            // available; never invent a vector/team for a failed acquisition.
            std::cerr << "suite/setup failure version=" << cv::version << " suite=" << opt.suite
                      << " profile=" << opt.profile << " seed=" << opt.seed
                      << " (case/source/delta/workers/client/vectors: see case diagnostic if acquired; otherwise unavailable)\n";
            cv::environment(std::cerr); std::cerr << "\nreproduce full invocation: env";
            for (const auto* name : cv::env_names) {
                const auto* value = std::getenv(name);
                if (value) { std::cerr << ' ' << cv::shell_quote(std::string(name) + '=' + value); }
            }
            for (int i = 0; i < argc; ++i) { std::cerr << ' ' << cv::shell_quote(argv[i]); }
            std::cerr << '\n'; throw;
        }
    });
}
