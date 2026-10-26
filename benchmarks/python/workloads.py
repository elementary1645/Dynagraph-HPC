"""Phase 5B-1 deterministic graph/trace generation, without engine execution."""

from dataclasses import dataclass
import hashlib
import json
import re

from deterministic import EligiblePool, PRNG_VERSION, SplitMix64, UINT64_MAX, sample_ranks

UINT32_MAX = (1 << 32) - 1
MAX_VERTICES = 100_000
MAX_EDGES = 500_000
MAX_UPDATES = 100_000
MAX_GRAPH_BYTES = 32 * 1024 * 1024
MAX_TRACE_BYTES = 16 * 1024 * 1024
MAX_JSON_BYTES = 64 * 1024
GRAPH_VERSION = "dynagraph-graph-v1"
TRACE_VERSION = "dynagraph-trace-v1"
VERSIONS = {"graph": GRAPH_VERSION, "trace": TRACE_VERSION, "prng": PRNG_VERSION}
SEED_NAMES = ("graph", "weight", "source", "trace")
SPLITS = ("development", "calibration", "validation", "test", "ood")


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer in [{low}, {high}]")
    return value


def decimal(value, high, label):
    if (type(value) is not str or len(value) > 20 or
            re.fullmatch(r"0|[1-9][0-9]*", value) is None):
        raise ValueError(f"{label} must be a canonical unsigned decimal string")
    return integer(int(value), 0, high, label)


def object_fields(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError(f"{label} requires exactly these fields: {', '.join(fields)}")


def fingerprint(value, label):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical_json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def parse_json(data):
    if len(data) > MAX_JSON_BYTES:
        raise ValueError("JSON exceeds 64 KiB limit")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"non-finite JSON number: {value}")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=reject_constant)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("invalid JSON encoding/nesting") from error


def seeds_from(spec):
    value = spec["seeds"]
    object_fields(value, SEED_NAMES, "seeds")
    return {name: decimal(value[name], UINT64_MAX, f"{name} seed") for name in SEED_NAMES}


def graph_dimensions(config):
    if type(config) is not dict or type(config.get("family")) is not str:
        raise ValueError("graph requires a family")
    family = config["family"]
    if family == "chain":
        object_fields(config, ("family", "vertices"), "chain graph")
        vertices = integer(config["vertices"], 1, MAX_VERTICES, "vertices")
        edges = vertices - 1
    elif family == "grid":
        object_fields(config, ("family", "rows", "columns", "bidirectional"), "grid graph")
        rows = integer(config["rows"], 1, MAX_VERTICES, "rows")
        columns = integer(config["columns"], 1, MAX_VERTICES, "columns")
        if type(config["bidirectional"]) is not bool:
            raise ValueError("bidirectional must be boolean")
        vertices = rows * columns
        edges = (rows * (columns - 1) + columns * (rows - 1)) * (2 if config["bidirectional"] else 1)
    elif family == "sparse_random":
        object_fields(config, ("family", "vertices", "edges"), "sparse random graph")
        vertices = integer(config["vertices"], 1, MAX_VERTICES, "vertices")
        edges = integer(config["edges"], 0, MAX_EDGES, "edges")
        if edges > vertices * (vertices - 1):
            raise ValueError("edges exceed distinct nonloop directed capacity")
    elif family == "layered":
        object_fields(config, ("family", "layers", "width", "fanout"), "layered graph")
        layers = integer(config["layers"], 1, MAX_VERTICES, "layers")
        width = integer(config["width"], 1, MAX_VERTICES, "width")
        fanout = integer(config["fanout"], 0, width, "fanout")
        vertices = layers * width
        edges = (layers - 1) * width * fanout
    elif family == "disconnected":
        object_fields(config, ("family", "component_sizes", "isolated_vertices"), "disconnected graph")
        sizes = config["component_sizes"]
        if type(sizes) is not list or not 2 <= len(sizes) <= 1024:
            raise ValueError("component_sizes requires 2..1024 components")
        for size in sizes:
            integer(size, 1, MAX_VERTICES, "component size")
        isolated = integer(config["isolated_vertices"], 0, MAX_VERTICES, "isolated vertices")
        vertices = sum(sizes) + isolated
        edges = sum(size - 1 for size in sizes)
    else:
        raise ValueError(f"unsupported graph family: {family}")
    # Python intermediates cannot wrap; enforce tooling quotas before allocation.
    integer(vertices, 1, MAX_VERTICES, "total vertices")
    integer(edges, 0, MAX_EDGES, "total edges")
    return vertices, edges


def validate_weights(config):
    if type(config) is not dict:
        raise ValueError("weights must be an object")
    kind = config.get("kind")
    if kind == "positive_uniform":
        object_fields(config, ("kind", "min", "max"), "positive uniform weights")
        low = integer(config["min"], 1, UINT32_MAX, "weight min")
        integer(config["max"], low, UINT32_MAX, "weight max")
    elif kind == "zero_inclusive":
        object_fields(config, ("kind", "max", "zero_numerator", "denominator"), "zero-inclusive weights")
        integer(config["max"], 1, UINT32_MAX, "weight max")
        denominator = integer(config["denominator"], 1, UINT32_MAX, "denominator")
        integer(config["zero_numerator"], 0, denominator, "zero numerator")
    elif kind == "bimodal":
        object_fields(config, ("kind", "low_min", "low_max", "high_min", "high_max",
                               "high_numerator", "denominator"), "bimodal weights")
        low = integer(config["low_min"], 0, UINT32_MAX - 1, "low min")
        low_max = integer(config["low_max"], low, UINT32_MAX - 1, "low max")
        high = integer(config["high_min"], low_max + 1, UINT32_MAX, "high min")
        integer(config["high_max"], high, UINT32_MAX, "high max")
        denominator = integer(config["denominator"], 1, UINT32_MAX, "denominator")
        integer(config["high_numerator"], 0, denominator, "high numerator")
    else:
        raise ValueError("unsupported weight distribution")


def validate_spec(spec):
    object_fields(spec, ("schema_version", "workload_id", "split", "seeds", "graph",
                         "weights", "source", "trace"), "workload specification")
    integer(spec["schema_version"], 1, 1, "specification schema version")
    if (type(spec["workload_id"]) is not str or
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", spec["workload_id"]) is None):
        raise ValueError("invalid workload ID")
    if type(spec["split"]) is not str or spec["split"] not in SPLITS:
        raise ValueError("unsupported split label")
    seeds_from(spec)
    vertices, _ = graph_dimensions(spec["graph"])
    validate_weights(spec["weights"])
    source = spec["source"]
    if type(source) is not dict:
        raise ValueError("source must be an object")
    if source.get("kind") == "explicit":
        object_fields(source, ("kind", "vertex"), "explicit source")
        integer(source["vertex"], 0, vertices - 1, "source vertex")
    elif source.get("kind") == "random":
        object_fields(source, ("kind",), "random source")
    else:
        raise ValueError("unsupported source kind")
    trace = spec["trace"]
    object_fields(trace, ("count", "schedule", "max_decrement"), "trace configuration")
    integer(trace["count"], 0, MAX_UPDATES, "update count")
    integer(trace["max_decrement"], 1, UINT32_MAX, "max decrement")
    schedule = trace["schedule"]
    if (type(schedule) is not list or not 1 <= len(schedule) <= 64 or
            any(type(item) is not str or item not in ("strict", "equal", "repeat", "unreachable")
                for item in schedule)):
        raise ValueError("schedule requires 1..64 strict/equal/repeat/unreachable entries")


@dataclass(frozen=True)
class Graph:
    vertices: int
    edges: tuple


@dataclass(frozen=True)
class Trace:
    graph_sha256: str
    seeds: tuple  # graph, weight, source, trace: canonical decimal strings
    source: int
    updates: tuple  # index, u, v, expected_old, new


def graph_bytes(graph):
    integer(graph.vertices, 0, MAX_VERTICES, "graph vertices")
    integer(len(graph.edges), 0, MAX_EDGES, "graph edges")
    previous = None
    lines = [f"{graph.vertices} {len(graph.edges)}\n"]
    for u, v, weight in graph.edges:
        integer(u, 0, graph.vertices - 1, "edge source")
        integer(v, 0, graph.vertices - 1, "edge destination")
        integer(weight, 0, UINT32_MAX, "edge weight")
        if previous is not None and (u, v) <= previous:
            raise ValueError("graph edges must be sorted and unique")
        previous = (u, v)
        lines.append(f"{u} {v} {weight}\n")
    return "".join(lines).encode("ascii")


def canonical_lines(data, limit, label):
    if len(data) > limit or not data.endswith(b"\n"):
        raise ValueError(f"{label} exceeds size limit or lacks final LF")
    try:
        lines = data.decode("ascii").split("\n")[:-1]
    except UnicodeError as error:
        raise ValueError(f"{label} must be ASCII") from error
    if any(not line or "\r" in line for line in lines):
        raise ValueError(f"{label} contains blank lines or CR")
    return lines


def numbers(line, count, limits, label):
    tokens = line.split(" ")
    if len(tokens) != count:
        raise ValueError(f"malformed {label}: expected {count} fields")
    return tuple(decimal(token, high, label) for token, high in zip(tokens, limits))


def parse_graph(data):
    lines = canonical_lines(data, MAX_GRAPH_BYTES, "graph")
    vertices, count = numbers(lines[0], 2, (MAX_VERTICES, MAX_EDGES), "graph header")
    if count > vertices * vertices or len(lines) != count + 1:
        raise ValueError("incorrect graph count or unexpected trailing data")
    records = tuple(numbers(line, 3, (max(0, vertices - 1), max(0, vertices - 1), UINT32_MAX),
                            "graph edge") for line in lines[1:])
    graph = Graph(vertices, records)
    graph_bytes(graph)  # Endpoint, ordering and duplicate validation, including V=0.
    return graph


def draw_weight(config, random):
    kind = config["kind"]
    if kind == "positive_uniform":
        low, high = config["min"], config["max"]
    elif kind == "zero_inclusive":
        if random.below(config["denominator"]) < config["zero_numerator"]:
            return 0
        low, high = 1, config["max"]
    else:
        high_mode = random.below(config["denominator"]) < config["high_numerator"]
        prefix = "high" if high_mode else "low"
        low, high = config[prefix + "_min"], config[prefix + "_max"]
    return low + random.below(high - low + 1)


def generate_graph(spec):
    validate_spec(spec)
    config = spec["graph"]
    vertices, expected_edges = graph_dimensions(config)
    random = SplitMix64(seeds_from(spec)["graph"])
    family = config["family"]
    pairs = []
    if family == "chain":
        pairs = [(u, u + 1) for u in range(vertices - 1)]
    elif family == "grid":
        rows, columns = config["rows"], config["columns"]
        for row in range(rows):
            for column in range(columns):
                u = row * columns + column
                for v in ((u + 1 if column + 1 < columns else None),
                          (u + columns if row + 1 < rows else None)):
                    if v is not None:
                        pairs.append((u, v))
                        if config["bidirectional"]:
                            pairs.append((v, u))
    elif family == "sparse_random":
        for rank in sample_ranks(random, vertices * (vertices - 1), expected_edges):
            u, destination_rank = divmod(rank, vertices - 1)
            pairs.append((u, destination_rank + (destination_rank >= u)))
    elif family == "layered":
        width = config["width"]
        for layer in range(config["layers"] - 1):
            for column in range(width):
                for destination in sample_ranks(random, width, config["fanout"]):
                    pairs.append((layer * width + column, (layer + 1) * width + destination))
    else:
        start = 0
        for size in config["component_sizes"]:
            pairs.extend((u, u + 1) for u in range(start, start + size - 1))
            start += size
    if len(pairs) != expected_edges:
        raise ValueError("generator edge-count invariant failed")
    pairs.sort()  # Never deduplicate: graph_bytes rejects any generator duplicate.
    weights = SplitMix64(seeds_from(spec)["weight"])
    graph = Graph(vertices, tuple((u, v, draw_weight(spec["weights"], weights)) for u, v in pairs))
    graph_bytes(graph)
    return graph


def reachable_vertices(graph, source):
    adjacency = [[] for _ in range(graph.vertices)]
    for u, v, _ in graph.edges:
        adjacency[u].append(v)
    reached = {source}
    pending = [source]
    while pending:
        for v in adjacency[pending.pop()]:
            if v not in reached:
                reached.add(v)
                pending.append(v)
    return reached


def generate_trace(spec, graph):
    validate_spec(spec)
    seeds = seeds_from(spec)
    source = (spec["source"]["vertex"] if spec["source"]["kind"] == "explicit" else
              SplitMix64(seeds["source"]).below(graph.vertices))
    reached = reachable_vertices(graph, source)
    # Independent mutable ledger, never mutating graph records or consulting SSSP.
    ledger = [weight for _, _, weight in graph.edges]
    eligible = EligiblePool(index for index, weight in enumerate(ledger) if weight > 0)
    unreachable = EligiblePool(index for index, (u, _, weight) in enumerate(graph.edges)
                              if weight > 0 and u not in reached)
    random = SplitMix64(seeds["trace"])
    updates = []
    previous = None
    config = spec["trace"]
    for index in range(config["count"]):
        mode = config["schedule"][index % len(config["schedule"])]
        try:
            if mode == "equal":
                if not graph.edges:
                    raise ValueError("no edge available for equal request")
                selected = random.below(len(graph.edges))
            elif mode == "repeat":
                if previous is None or ledger[previous] == 0:
                    raise ValueError("repeat requires a previous edge with remaining decrease budget")
                selected = previous
            else:
                selected = (unreachable if mode == "unreachable" else eligible).choose(random)
            old = ledger[selected]
            new = old if mode == "equal" else old - 1 - random.below(min(old, config["max_decrement"]))
            u, v, _ = graph.edges[selected]
            updates.append((index, u, v, old, new))
            ledger[selected] = new
            if new == 0:
                eligible.discard(selected)
                unreachable.discard(selected)
            previous = selected
        except ValueError as error:
            raise ValueError(f"update {index} ({mode}): {error}") from error
    return Trace(sha256(graph_bytes(graph)), tuple(spec["seeds"][name] for name in SEED_NAMES),
                 source, tuple(updates))


def trace_bytes(trace):
    fingerprint(trace.graph_sha256, "trace graph identity")
    if len(trace.seeds) != 4:
        raise ValueError("trace requires four seeds")
    for name, seed in zip(SEED_NAMES, trace.seeds):
        decimal(seed, UINT64_MAX, name + " seed")
    integer(trace.source, 0, MAX_VERTICES - 1, "trace source")
    integer(len(trace.updates), 0, MAX_UPDATES, "trace updates")
    lines = ["DYNAGRAPH_TRACE 1\n", f"graph_sha256 {trace.graph_sha256}\n",
             f"generator {TRACE_VERSION}\n", f"graph_generator {GRAPH_VERSION}\n",
             f"prng {PRNG_VERSION}\n"]
    lines.extend(f"{name}_seed {seed}\n" for name, seed in zip(SEED_NAMES, trace.seeds))
    lines.extend((f"source {trace.source}\n", f"updates {len(trace.updates)}\n"))
    for expected_index, record in enumerate(trace.updates):
        if len(record) != 5:
            raise ValueError("trace record requires five fields")
        for value, high in zip(record, (MAX_UPDATES - 1, MAX_VERTICES - 1, MAX_VERTICES - 1,
                                       UINT32_MAX, UINT32_MAX)):
            integer(value, 0, high, "trace record")
        if record[0] != expected_index:
            raise ValueError("trace update index is not consecutive")
        lines.append(" ".join(str(value) for value in record) + "\n")
    return "".join(lines).encode("ascii")


def parse_trace(data):
    lines = canonical_lines(data, MAX_TRACE_BYTES, "trace")
    if len(lines) < 11 or lines[0] != "DYNAGRAPH_TRACE 1":
        raise ValueError("unsupported trace format version or incomplete header")

    def header(index, name):
        tokens = lines[index].split(" ")
        if len(tokens) != 2 or tokens[0] != name:
            raise ValueError(f"malformed trace header: {name}")
        return tokens[1]

    digest = fingerprint(header(1, "graph_sha256"), "graph fingerprint")
    for index, name, expected in ((2, "generator", TRACE_VERSION), (3, "graph_generator", GRAPH_VERSION),
                                  (4, "prng", PRNG_VERSION)):
        if header(index, name) != expected:
            raise ValueError(f"unsupported {name} version")
    seeds = tuple(header(5 + index, name + "_seed") for index, name in enumerate(SEED_NAMES))
    source = decimal(header(9, "source"), MAX_VERTICES - 1, "trace source")
    count = decimal(header(10, "updates"), MAX_UPDATES, "trace count")
    if len(lines) != 11 + count:
        raise ValueError("incorrect trace count or unexpected trailing data")
    updates = tuple(numbers(line, 5, (MAX_UPDATES - 1, MAX_VERTICES - 1, MAX_VERTICES - 1,
                                     UINT32_MAX, UINT32_MAX), "trace record") for line in lines[11:])
    trace = Trace(digest, seeds, source, updates)
    trace_bytes(trace)
    return trace


def replay(graph, trace):
    """Independent endpoint-keyed ledger: validates each old weight, no backend."""
    if sha256(graph_bytes(graph)) != trace.graph_sha256:
        raise ValueError("trace graph fingerprint mismatch")
    trace_bytes(trace)
    integer(trace.source, 0, graph.vertices - 1, "replay source")
    ledger = {(u, v): weight for u, v, weight in graph.edges}
    for index, u, v, old, new in trace.updates:
        if not 0 <= u < graph.vertices or not 0 <= v < graph.vertices or (u, v) not in ledger:
            raise ValueError(f"update {index}: invalid endpoints or nonexistent edge")
        if ledger[u, v] != old:
            raise ValueError(f"update {index}: expected old weight mismatch")
        if new > old:
            raise ValueError(f"update {index}: weight increase")
        ledger[u, v] = new
    return Graph(graph.vertices, tuple((u, v, ledger[u, v]) for u, v, _ in graph.edges))
