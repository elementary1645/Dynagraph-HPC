# Phase 5B-1 workload artifacts, version 1

This is generation and integrity/replay tooling, not a benchmark runner. It uses
Python 3.8+ and its standard library. Production graph/SSSP APIs, algorithms,
heuristic thresholds and instrumentation are unchanged. No timings are collected.

## Commands

From the repository root (the output directory must not exist):

```sh
python3 benchmarks/python/generate.py generate \
  --spec benchmarks/configs/chain-v1.json --output data/generated/chain-v1
python3 benchmarks/python/generate.py verify \
  --manifest data/generated/chain-v1/manifest.json
```

Generation performs semantic validation, replay and reproduction checks before
creating output. Files are exclusively created; no existing directory/file is
overwritten or deleted. Graph and trace are written first, manifest last. An I/O
failure may leave an incomplete directory; it is not a successful bundle. Success
prints a schema-versioned JSON object and exits 0. Invalid input, exhaustion,
integrity failure, allocation or I/O failure produces a stderr diagnostic and
exit 2, with no success object. argparse usage errors also exit 2.

Bundles contain graph.txt, trace.txt and manifest.json. They are relocatable as a
directory. V1 manifest paths must be these fixed sibling filenames, preventing
absolute/traversal paths; artifact symlinks are rejected. Generated artifacts go
under ignored data/ paths; curated specs and small tests remain tracked.

## Specification

All listed keys are required; unknown keys at every schema level are rejected.
JSON input allows ordinary JSON whitespace, but not duplicate keys, non-finite
numbers, trailing objects/data, booleans in integer fields, or numeric fractions.

```json
{
  "schema_version": 1,
  "workload_id": "chain-v1-example",
  "split": "development",
  "seeds": {"graph":"1","weight":"2","source":"3","trace":"4"},
  "graph": {"family":"chain","vertices":8},
  "weights": {"kind":"positive_uniform","min":16,"max":32},
  "source": {"kind":"explicit","vertex":0},
  "trace": {"count":12,"schedule":["strict","repeat","equal"],"max_decrement":2}
}
```

workload_id is 1..64 ASCII letters/digits/underscore/dot/hyphen, starting with a
letter/digit. Split is development, calibration, validation, test, or ood. The
label records an assignment; this phase does not enforce dataset-level split
independence or implement calibration. Source is either the explicit form above
or exactly {"kind":"random"}, using its separate source stream.

All four seeds are canonical decimal **strings** in 0..18446744073709551615,
without signs/leading zeroes. Counts/IDs/weights are JSON integer tokens, bounded
as below; no floating-point conversion occurs. Both ends of the uint64 seed range
are tested. Explicit source leaves the source stream unused. Fixed-topology
families record but do not consume the graph seed.

## Graph families and quotas

All generated graphs have at least one vertex, zero-based IDs and no self-loops.
They are directed; reverse edges occur only when requested. Families have exactly
these graph-object keys in addition to family:

| Family | Parameters | Exact counts/topology |
| --- | --- | --- |
| chain | vertices | V=n, E=n-1; u -> u+1 |
| grid | rows, columns, bidirectional (boolean) | V=rc; forward right/down edges, E=r(c-1)+c(r-1); double E for explicit reverse edges |
| sparse_random | vertices, edges | Exactly E uniformly sampled distinct nonloop ordered pairs; E<=V(V-1) |
| layered | layers, width, fanout | V=Lw; E=(L-1)wk; each row in layers 0..L-2 samples k distinct destinations in the next layer; 0<=k<=w |
| disconnected | component_sizes, isolated_vertices | 2..1024 positive component sizes, each a directed chain; isolated suffix; V=sum sizes+isolates, E=sum(size-1) |

Rows/columns/layers/width and chain/random vertex counts are positive. Fanout,
edge count and isolated count can be zero. One-layer graphs have no edges.
An isolated or edgeless graph permits zero-request traces; a nonempty trace
requires its requested edge eligibility. Source must be in [0,V).

Tooling quotas: V<=100,000; E<=500,000; updates<=100,000; schedule length 1..64;
JSON files<=64 KiB, graph<=32 MiB, trace<=16 MiB. These are implementation resource
bounds, not production graph API limits or guarantees of sufficient RAM. Python
integer intermediates cannot wrap; products/sums and quotas are validated before
count-sized generation allocations. Readers bound file bytes before parsing.

Pairs are sorted lexicographically before weights are assigned. Duplicates are
errors, including generator bugs; nothing is silently deduplicated. The canonical
parser accepts valid self-loops (matching CSR) but generators do not create them.
The Python artifact parser requires canonical ordering/whitespace; the unchanged
C++ loader continues to accept its broader documented edge-list syntax.

## Randomness and sampling specification

Versions are dynagraph-graph-v1, dynagraph-trace-v1 and splitmix64-v1.
SplitMix64 is specified here, including seed/state interpretation. It is not a
cryptographic random generator. Each independent stream starts with its seed as
the unsigned 64-bit state. For each draw:

```text
state = (state + 0x9E3779B97F4A7C15) mod 2^64
z = ((state XOR (state >> 30)) * 0xBF58476D1CE4E5B9) mod 2^64
z = ((z XOR (z >> 27)) * 0x94D049BB133111EB) mod 2^64
return z XOR (z >> 31)
```

All shifts are logical right shifts. Seed 0 starts with outputs
e220a8397b1dcdaf, 6e789e6aa1b965f4, 06c45d188009454f. below(b), for
1<=b<=2^64, computes t=2^64 mod b, rejects raw outputs x<t, then returns x mod b.
Every call consumes at least one output, including b=1. At most 128 outputs are
attempted; exhaustion fails, with no biased fallback or seed retry.

Sampling K ranks from M uses Floyd's algorithm: an initially empty membership
set; for j=M-K..M-1, draw t=below(j+1), insert j if t is already present, otherwise
insert t. Return sorted ranks. This takes exactly K bounded draws, avoiding
duplicate-edge rejection. No set/hash iteration order chooses edges. For random
graphs rank r maps to u=r div (V-1), q=r mod (V-1), v=q+[q>=u]. For layered graphs,
draw separately for each ascending layer and ascending row, then sort all pairs.

Use only the graph stream for topology, the weight stream for assignment to
ascending pairs, the source stream for random source, and the trace stream for
requests. No platform RNG, floating-point probability, adaptive decision, clock,
environment variable, hash order or filesystem path affects artifact bytes.

## Weight distributions

Ranges are inclusive and bounded by UINT32_MAX=4294967295. Uniform [a,b] is
a+below(b-a+1), consuming a draw even for a constant range.

| kind | Required fields | Draw order |
| --- | --- | --- |
| positive_uniform | min, max | One range draw; 1<=min<=max |
| zero_inclusive | max, zero_numerator, denominator | Coin below(denominator); zero if less than numerator, otherwise uniform 1..max |
| bimodal | low_min, low_max, high_min, high_max, high_numerator, denominator | Coin first; high range if less than numerator, low otherwise; one range draw |

Probability numerators are 0..denominator; denominator is 1..UINT32_MAX. Coin
draws occur even for probability zero/one. Bimodal ranges must be disjoint and
ordered: 0<=low_min<=low_max<high_min<=high_max<=UINT32_MAX.

## Trace construction

The nonempty schedule cycles until count requests have been produced. An initial
ledger is copied from graph weights. Canonical edge index means ascending (u,v).

- strict: uniformly choose from currently positive-weight edges.
- equal: uniformly choose from every edge, including zero-weight edges; new=old.
- repeat: strict decrease of the edge used by the immediately preceding request;
  fail if there is no predecessor or its weight is zero. Predecessor includes
  equal requests; no alternate edge is substituted.
- unreachable: uniformly choose a positive-weight edge whose tail is unreachable
  from the source, using topology-only reachability once before trace generation.

For a strict request, after edge selection draw decrement=1+below(min(old,
max_decrement)), then new=old-decrement. max_decrement is 1..UINT32_MAX. Repeat
does not draw an edge index. No edge is added, increased or reset.

Positive eligibility pools start in canonical edge-index order. Removal at zero
swaps the last pool element into the removed position; future draws index this
specified order. The unreachable pool follows the same rule. Both pools update
on every request that reaches zero. Selection and removal are O(1), with O(V+E)
initial topology/ledger setup; no full scan per request. Empty eligibility, a
missing repeat predecessor, and exhausted repeat budgets fail with request index
and mode. Traces are immutable tuples after construction.

Decreases cannot change reachability under fixed topology and finite weights.
Unreachable-tail requests therefore have no distance effect. Generation does not
run SSSP or classify broad/localized propagation. Long traces must use sufficient
initial weights/edges or shorter explicit budgets, then restart from the initial
graph for a new trace, never reset mid-trace.

## Canonical graph, trace and manifest

Graph bytes are exactly the existing format, restricted to canonical v1 output:
ASCII decimal V E and exactly E sorted u v weight lines. Single spaces, no signs
or leading zeroes, LF after every line, no blank lines/comments/extra data. Empty
graph 0 0 is parseable, but cannot form a workload with a valid source.

Trace header is exactly these eleven lines in this order, followed by count
records. Example header values below are descriptive; actual SHA-256 is 64
lowercase hexadecimal digits.

```text
DYNAGRAPH_TRACE 1
graph_sha256 <graph.txt SHA-256>
generator dynagraph-trace-v1
graph_generator dynagraph-graph-v1
prng splitmix64-v1
graph_seed 1
weight_seed 2
source_seed 3
trace_seed 4
source 0
updates 12
```

Each record is exactly `index u v expected_old_weight new_weight`, starting with
index zero and consecutive indices. Numeric lexical rules match graph output.
Unknown versions/header keys, wrong counts, missing/extra records, and unexpected
trailing bytes are errors. Graph SHA-256 hashes canonical initial graph bytes.

Manifest schema 1 has exactly these top-level keys:

| Key | Meaning |
| --- | --- |
| schema_version | integer 1 |
| workload_id, split | Repeat exact specification values |
| generator_versions | graph, trace and prng version strings above |
| configuration | Entire validated specification, including family/parameters, distributions, all seeds and trace recipe |
| source | Resolved integer source, including for random selection |
| counts | vertices, edges, updates integers |
| artifacts | graph/trace objects, each with path and lowercase sha256 |
| final_graph_sha256 | SHA-256 of canonical graph bytes after independent replay |

Output JSON sorts keys recursively, uses separators comma/colon without spaces,
ASCII escaping, no non-finite values and one final LF. No timestamps, hostnames,
absolute paths or Python versions enter canonical artifacts. All numeric tokens
other than string seeds are below 2^53, so exact integer IDs are preserved even in
common JSON consumers. Any change to draw order, mapping, topology, trace rules or
serialization must bump the applicable version; existing artifacts must not be
silently reinterpreted. Tests pin graph/trace/final fingerprints for all families.

## Integrity and independent replay

The verifier reads bounded bytes, validates manifest schema/versions, then checks
both artifact SHA-256 values **before replay**. It parses strict graph/trace
formats, checks counts, source and seeds, then uses a fresh endpoint-keyed Python
dictionary to check every old weight and apply requests in order. Invalid
endpoints, absent edges, increases and inconsistent identities fail explicitly.
Final weights are serialized in the original topology order and checked against
final_graph_sha256. It also regenerates declared configuration and compares exact
artifact bytes and manifest fields to detect inconsistent provenance/recipes.
The generation ledger is edge-indexed; replay is independently endpoint-keyed.

This proves artifact/replay consistency, not SSSP algorithm correctness or producer
authenticity. Hashes are not signatures. Cross-language tests load initial and
replayed final graphs through unchanged C++ Dijkstra and compare distances with a
small independent Python Bellman-Ford oracle, across five families and three
weight distributions (30 C++ invocations). No adaptive backend constructs traces.

## Verification and limitations

CTest registers workload_artifacts (Python unit/CLI tests) and workload_loader
(C++ interoperability), alongside all existing tests. Python is discovered only
under BUILD_TESTING; library-only builds need no Python. Workloads remain small
in CI, with no downloaded packages. Python 3.8+ syntax/standard-library APIs are
used; actual interpreter/platform verification is recorded in research-log.md.
Byte reproducibility is a v1 format guarantee for conforming supported Python
platforms; no unexecuted cross-platform test is claimed.

Deferred: hub/dense/zero-cycle/road-like families, oracle-targeted broad/localized
updates, timed engine replay, hardware metadata, repetitions/statistics/plots,
cost calibration and learned policies. Resource quotas bound work/data, not peak
RSS or wall time. Artifact inputs are assumed stable during verification; no
concurrent writer or cryptographic authentication protocol is implemented.
Stop after Phase 5B-1 review; Phase 5B-2 needs separate approval.
