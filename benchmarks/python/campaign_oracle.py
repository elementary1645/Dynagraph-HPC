"""Independent bounded pilot final-state oracle; never calls a graph engine."""
from workloads import (graph_bytes, integer, parse_graph, parse_trace, replay, sha256)

METHOD = 'python-synchronous-bellman-ford-v1'


def reconcile(graph_data, trace_data, manifest, result):
    """Replay immutable ordered updates, then compare every distance and weight.

    The synchronous edge-list relaxation follows the existing Python oracle in
    tests/test_workload_loader.py. It uses previous-round distances, independent
    of production CSR, priority queues, delta buckets and reported labels.
    """
    graph = parse_graph(graph_data)
    trace = parse_trace(trace_data)
    integer(graph.vertices, 1, 128, 'pilot oracle vertices')
    integer(len(graph.edges), 0, 4096, 'pilot oracle edges')
    integer(len(trace.updates), 0, 256, 'pilot oracle updates')
    if (sha256(graph_data) != manifest['artifacts']['graph']['sha256'] or
            sha256(trace_data) != manifest['artifacts']['trace']['sha256'] or
            type(result.get('source')) is not int or
            result['source'] != trace.source or manifest['source'] != trace.source):
        raise ValueError('independent pilot oracle input/source mismatch')
    final = replay(graph, trace)
    if sha256(graph_bytes(final)) != manifest['final_graph_sha256']:
        raise ValueError('independent pilot oracle final graph mismatch')
    weights = result.get('final_weights')
    expected_weights = [weight for _, _, weight in final.edges]
    if (type(weights) is not list or any(type(w) is not int for w in weights) or
            weights != expected_weights):
        raise ValueError('independent pilot oracle final weights mismatch')
    distances = [None] * graph.vertices
    distances[trace.source] = 0
    for _ in range(graph.vertices - 1):
        changed = distances.copy()
        for u, v, weight in final.edges:
            if distances[u] is not None:
                candidate = distances[u] + weight
                if changed[v] is None or candidate < changed[v]:
                    changed[v] = candidate
        if changed == distances:
            break
        distances = changed
    reported = result.get('final_distances')
    if (type(reported) is not list or len(reported) != graph.vertices or
            any(d is not None and type(d) is not int for d in reported) or
            reported != distances):
        raise ValueError('independent pilot oracle final distances mismatch')
    # Python None is the protocol's unreachable representation. With <=128
    # vertices and uint32 nonnegative weights finite shortest paths fit uint64.
    return METHOD
