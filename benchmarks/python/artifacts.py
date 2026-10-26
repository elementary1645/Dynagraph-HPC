"""Canonical workload bundles, integrity checking and independent replay."""

from pathlib import Path

from workloads import (MAX_EDGES, MAX_GRAPH_BYTES, MAX_JSON_BYTES, MAX_TRACE_BYTES,
                       MAX_UPDATES, MAX_VERTICES, VERSIONS, canonical_json,
                       fingerprint, generate_graph, generate_trace, graph_bytes,
                       integer, object_fields, parse_graph, parse_json, parse_trace,
                       replay, sha256, trace_bytes, validate_spec)


def generate(spec):
    validate_spec(spec)
    graph = generate_graph(spec)
    trace = generate_trace(spec, graph)
    graph_data = graph_bytes(graph)
    trace_data = trace_bytes(trace)
    final = replay(graph, trace)
    manifest = {
        "schema_version": 1,
        "workload_id": spec["workload_id"],
        "split": spec["split"],
        "generator_versions": dict(VERSIONS),
        "configuration": parse_json(canonical_json(spec)),
        "source": trace.source,
        "counts": {"vertices": graph.vertices, "edges": len(graph.edges), "updates": len(trace.updates)},
        "artifacts": {"graph": {"path": "graph.txt", "sha256": sha256(graph_data)},
                      "trace": {"path": "trace.txt", "sha256": sha256(trace_data)}},
        "final_graph_sha256": sha256(graph_bytes(final)),
    }
    return manifest, graph_data, trace_data


def validate_manifest(manifest):
    object_fields(manifest, ("schema_version", "workload_id", "split", "generator_versions", "configuration",
                             "source", "counts", "artifacts", "final_graph_sha256"), "manifest")
    integer(manifest["schema_version"], 1, 1, "manifest schema version")
    if manifest["generator_versions"] != VERSIONS:
        raise ValueError("unsupported generator versions")
    spec = manifest["configuration"]
    validate_spec(spec)
    if manifest["workload_id"] != spec["workload_id"] or manifest["split"] != spec["split"]:
        raise ValueError("manifest workload ID/split disagrees with configuration")
    integer(manifest["source"], 0, MAX_VERTICES - 1, "manifest source")
    counts = manifest["counts"]
    object_fields(counts, ("vertices", "edges", "updates"), "counts")
    for name, maximum in (("vertices", MAX_VERTICES), ("edges", MAX_EDGES), ("updates", MAX_UPDATES)):
        integer(counts[name], 0, maximum, name)
    object_fields(manifest["artifacts"], ("graph", "trace"), "artifacts")
    for name in ("graph", "trace"):
        artifact = manifest["artifacts"][name]
        object_fields(artifact, ("path", "sha256"), name + " artifact")
        # V1 is a relocatable bundle with fixed sibling names, never arbitrary paths.
        if artifact["path"] != name + ".txt":
            raise ValueError(f"{name} path must be {name}.txt")
        fingerprint(artifact["sha256"], name + " SHA-256")
    fingerprint(manifest["final_graph_sha256"], "final graph SHA-256")


def verify(manifest, graph_data, trace_data):
    validate_manifest(manifest)
    for name, data in (("graph", graph_data), ("trace", trace_data)):
        if sha256(data) != manifest["artifacts"][name]["sha256"]:
            raise ValueError(f"{name} SHA-256 mismatch")
    graph = parse_graph(graph_data)
    trace = parse_trace(trace_data)
    counts = {"vertices": graph.vertices, "edges": len(graph.edges), "updates": len(trace.updates)}
    if counts != manifest["counts"]:
        raise ValueError("manifest counts disagree with artifacts")
    if trace.source != manifest["source"]:
        raise ValueError("manifest source disagrees with trace")
    if trace.seeds != tuple(manifest["configuration"]["seeds"][name]
                            for name in ("graph", "weight", "source", "trace")):
        raise ValueError("trace seeds disagree with configuration")
    final_data = graph_bytes(replay(graph, trace))
    if sha256(final_data) != manifest["final_graph_sha256"]:
        raise ValueError("final graph fingerprint mismatch")
    # Reproduction also checks provenance/config consistency, beyond valid replay.
    expected, expected_graph, expected_trace = generate(manifest["configuration"])
    if (expected_graph != graph_data or expected_trace != trace_data or
            expected != manifest):
        raise ValueError("artifacts do not reproduce declared configuration")
    return {"schema_version": 1, "status": "verified", "workload_id": manifest["workload_id"],
            "source": trace.source, "counts": counts, "final_graph_sha256": sha256(final_data)}


def read_bounded(path, limit):
    with Path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{path}: input exceeds {limit} byte limit")
    return data


def write_bundle(spec, output):
    manifest, graph_data, trace_data = generate(spec)
    # All semantic validation completes before any output directory is created.
    verify(manifest, graph_data, trace_data)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    # Exclusive creation, manifest last. An I/O failure may leave an incomplete
    # directory, which is never a successful bundle. Never overwrite or delete it.
    for name, data in (("graph.txt", graph_data), ("trace.txt", trace_data),
                       ("manifest.json", canonical_json(manifest))):
        with (output / name).open("xb") as stream:
            stream.write(data)
    return output / "manifest.json"


def verify_bundle(path):
    path = Path(path)
    manifest = parse_json(read_bounded(path, MAX_JSON_BYTES))
    validate_manifest(manifest)
    data = {}
    for name, limit in (("graph", MAX_GRAPH_BYTES), ("trace", MAX_TRACE_BYTES)):
        artifact = path.parent / manifest["artifacts"][name]["path"]
        if artifact.is_symlink():
            raise ValueError("artifact symlinks are unsupported")
        data[name] = read_bounded(artifact, limit)
    return verify(manifest, data["graph"], data["trace"])
