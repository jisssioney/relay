#!/usr/bin/env python3
"""Standalone relay routing tool (standard library only).

Usage: python relay.py route FILE SOURCE

Reads a UTF-8 JSON graph description, ignores links with "up" false, and
computes the minimum-cost simple path from SOURCE to every node. Ties are
broken by the lexicographic (Unicode code point) order of the complete node
sequence of the path.
"""

import json
import sys

MAX_COST = 2147483647
LINK_KEYS = frozenset(("from", "to", "cost", "up"))


def fail(code):
    """Emit the canonical error envelope and exit with code."""
    sys.stderr.buffer.write(b'{"error":%d}\n' % code)
    sys.exit(code)


def main(argv):
    # Only `relay.py route FILE SOURCE` is supported.
    if len(argv) != 4 or argv[1] != "route":
        fail(2)

    path = argv[2]
    source = argv[3]

    # Exit 3: the file cannot be read.
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError:
        fail(3)

    # Exit 4: malformed JSON (invalid UTF-8 is also a ValueError here).
    try:
        graph = json.loads(raw)
    except ValueError:
        fail(4)

    # Exit 5: schema/topology violations.
    if not isinstance(graph, dict) or set(graph) != {"nodes", "links"}:
        fail(5)

    nodes = graph["nodes"]
    links = graph["links"]
    if not isinstance(nodes, list) or not isinstance(links, list):
        fail(5)

    names = set()
    for name in nodes:
        if not isinstance(name, str) or not name or name in names:
            fail(5)
        names.add(name)

    adjacency = {name: [] for name in nodes}
    pairs = set()
    for link in links:
        if not isinstance(link, dict) or set(link) != LINK_KEYS:
            fail(5)
        src = link["from"]
        dst = link["to"]
        cost = link["cost"]
        up = link["up"]
        if not isinstance(src, str) or not isinstance(dst, str):
            fail(5)
        if src not in names or dst not in names or src == dst:
            fail(5)
        # bool is a subclass of int: require an exact int in range.
        if type(cost) is not int or not (1 <= cost <= MAX_COST):
            fail(5)
        if type(up) is not bool:
            fail(5)
        if (src, dst) in pairs:
            fail(5)
        pairs.add((src, dst))
        if up:
            adjacency[src].append((dst, cost))

    if source not in names:
        fail(5)

    # O(V^2 + E) array-based Dijkstra. Full predecessor paths are retained so
    # equal-cost ties can be compared as complete node sequences; total path
    # storage is O(V^2). Positive weights guarantee every settled path is
    # simple and that the lexicographically smallest path is final at settle
    # time, so greedy lexicographic comparison on equal-cost relaxation yields
    # the globally smallest sequence.
    infinity = float("inf")
    distance = {name: infinity for name in nodes}
    path = {name: None for name in nodes}
    settled = {name: False for name in nodes}
    distance[source] = 0
    path[source] = [source]

    for _ in nodes:
        current = None
        best = infinity
        for name in nodes:
            if not settled[name] and distance[name] < best:
                best = distance[name]
                current = name
        if current is None:
            # Only unreachable nodes remain.
            break
        settled[current] = True
        current_path = path[current]
        current_dist = distance[current]
        for neighbor, weight in adjacency[current]:
            candidate_dist = current_dist + weight
            if candidate_dist < distance[neighbor]:
                distance[neighbor] = candidate_dist
                path[neighbor] = current_path + [neighbor]
            elif candidate_dist == distance[neighbor]:
                candidate_path = current_path + [neighbor]
                if candidate_path < path[neighbor]:
                    path[neighbor] = candidate_path

    routes = []
    for destination in sorted(nodes):
        if destination == source:
            routes.append({
                "destination": destination,
                "nextHop": source,
                "cost": 0,
                "path": [source],
            })
        elif distance[destination] == infinity:
            routes.append({
                "destination": destination,
                "nextHop": None,
                "cost": None,
                "path": [],
            })
        else:
            node_path = path[destination]
            routes.append({
                "destination": destination,
                "nextHop": node_path[1],
                "cost": distance[destination],
                "path": node_path,
            })

    result = {"source": source, "routes": routes}
    text = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
