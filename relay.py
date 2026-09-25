"""relay: single-source lowest-cost routing.

Usage: python relay.py route FILE SOURCE
       python relay.py ecmp FILE SOURCE FLOW
       python relay.py metric FILE SOURCE ORDER

Exit codes: 2 bad args/subcommand, 3 file unreadable, 4 JSON syntax,
5 FLOW/ORDER/schema/topology/unknown-source error. On failure stdout stays
empty and stderr is exactly {"error":N} plus a newline.
"""

import hashlib
import json
import sys

MAX_COST = 2147483647
MAX_METRIC = 2147483647
MAX_FLOW_LEN = 256
MAX_LATENCY = 2147483647
METRIC_NAMES = ("hop", "cost", "bandwidth", "latency")


def fail(code):
    sys.stderr.write('{"error":%d}\n' % code)
    raise SystemExit(code)


def _reject_constant(value):
    # NaN / Infinity / -Infinity are not valid JSON.
    raise ValueError("invalid JSON constant: " + value)


def load_network(path, with_metrics=False):
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        fail(3)
    except UnicodeDecodeError:
        fail(4)

    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        fail(4)

    if not isinstance(data, dict) or set(data) != {"nodes", "links"}:
        fail(5)
    nodes = data["nodes"]
    links = data["links"]

    if not isinstance(nodes, list):
        fail(5)
    node_set = set()
    for n in nodes:
        if type(n) is not str or n == "" or n in node_set:
            fail(5)
        node_set.add(n)

    if with_metrics:
        link_keys = {"from", "to", "cost", "up", "bandwidth", "latency"}
    else:
        link_keys = {"from", "to", "cost", "up"}
    if not isinstance(links, list):
        fail(5)
    seen_pairs = set()
    for link in links:
        if not isinstance(link, dict) or set(link) != link_keys:
            fail(5)
        frm = link["from"]
        to = link["to"]
        cost = link["cost"]
        up = link["up"]
        if type(frm) is not str or type(to) is not str:
            fail(5)
        if frm not in node_set or to not in node_set or frm == to:
            fail(5)
        if type(cost) is not int or not 1 <= cost <= MAX_COST:
            fail(5)
        if type(up) is not bool:
            fail(5)
        if with_metrics:
            bandwidth = link["bandwidth"]
            latency = link["latency"]
            if type(bandwidth) is not int or not 1 <= bandwidth <= MAX_METRIC:
                fail(5)
            if type(latency) is not int or not 0 <= latency <= MAX_LATENCY:
                fail(5)
        pair = (frm, to)
        if pair in seen_pairs:
            fail(5)
        seen_pairs.add(pair)

    return nodes, links, node_set


def parse_order(text):
    # ORDER lists each of hop/cost/bandwidth/latency exactly once; earlier
    # names have higher priority.
    parts = text.split(",")
    if len(parts) != 4 or sorted(parts) != sorted(METRIC_NAMES):
        fail(5)
    return parts


def shortest_paths(nodes, links, source):
    # Directed adjacency over up links only.
    adj = {n: [] for n in nodes}
    for link in links:
        if link["up"]:
            adj[link["from"]].append((link["to"], link["cost"]))

    cost_of = {n: None for n in nodes}
    path_of = {n: None for n in nodes}
    cost_of[source] = 0
    path_of[source] = [source]
    settled = set()

    # Dijkstra with O(V^2) selection. All link costs are >= 1, so every
    # predecessor of a lowest-cost path has a strictly smaller cost and is
    # settled before the node itself; hence only costs are compared during
    # selection, and full path sequences only during relaxation ties.
    while True:
        u = None
        ucost = None
        for n in nodes:
            c = cost_of[n]
            if c is not None and n not in settled and (ucost is None or c < ucost):
                u = n
                ucost = c
        if u is None:
            break
        settled.add(u)
        upath = path_of[u]
        for to, w in adj[u]:
            if to in settled:
                continue
            nc = ucost + w
            cc = cost_of[to]
            if cc is None or nc < cc:
                cost_of[to] = nc
                path_of[to] = upath + [to]
            elif nc == cc:
                cand = upath + [to]
                if cand < path_of[to]:
                    path_of[to] = cand
    return cost_of, path_of


def compute_routes(nodes, links, source):
    cost_of, path_of = shortest_paths(nodes, links, source)

    routes = []
    for n in sorted(nodes):
        if n == source:
            routes.append({"destination": n, "nextHop": source, "cost": 0,
                           "path": [source]})
        elif cost_of[n] is None:
            routes.append({"destination": n, "nextHop": None, "cost": None,
                           "path": []})
        else:
            p = path_of[n]
            routes.append({"destination": n, "nextHop": p[1],
                           "cost": cost_of[n], "path": p})
    return {"source": source, "routes": routes}


def compute_ecmp(nodes, links, source, flow):
    cost_of, _ = shortest_paths(nodes, links, source)

    # Candidate first hops: targets of up links out of the source.
    first_cost = {}
    for link in links:
        if link["up"] and link["from"] == source:
            first_cost[link["to"]] = link["cost"]

    # Lowest-cost, lexicographically smallest paths from each candidate
    # first hop, so the best equal-cost full path via any of them can be
    # rebuilt as [source] + hop_path.
    hop_cost = {}
    hop_path = {}
    for h in first_cost:
        hop_cost[h], hop_path[h] = shortest_paths(nodes, links, h)

    routes = []
    for n in sorted(nodes):
        if n == source:
            routes.append({"destination": n, "nextHops": [source],
                           "selectedNextHop": source, "cost": 0,
                           "path": [source]})
            continue
        total = cost_of[n]
        if total is None:
            routes.append({"destination": n, "nextHops": [],
                           "selectedNextHop": None, "cost": None, "path": []})
            continue
        # A first hop is usable iff some lowest-cost path to n starts with
        # it; hops are deduplicated and sorted by Unicode code point.
        hops = sorted(
            h for h, w in first_cost.items()
            if hop_cost[h][n] is not None and w + hop_cost[h][n] == total
        )
        key = json.dumps([flow, source, n], ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(key).digest()
        selected = hops[int.from_bytes(digest[:8], "big") % len(hops)]
        routes.append({"destination": n, "nextHops": hops,
                       "selectedNextHop": selected, "cost": total,
                       "path": [source] + hop_path[selected][n]})
    return {"source": source, "flow": flow, "routes": routes}


def metric_routes(nodes, links, source, order):
    # Directed adjacency over up links only, with cost, bandwidth, latency.
    adj = {n: [] for n in nodes}
    for link in links:
        if link["up"]:
            adj[link["from"]].append(
                (link["to"], link["cost"], link["bandwidth"], link["latency"])
            )

    # Enumerate every up-only directed simple path from the source with an
    # iterative depth-first walk. Frame d holds the current node, the next
    # adjacency slot to try, and that path prefix's metrics; the visited
    # set and node stack are shared. Each discovered path is compared
    # immediately against the destination's best path: metrics in ORDER,
    # bandwidth maximized and the rest minimized, then the complete path's
    # Unicode code point order as the final tie-break. Enumeration order is
    # irrelevant because the comparison is a total order.
    def better(cand_metrics, cand_path, best_metrics, best_path):
        for i, name in enumerate(order):
            a = cand_metrics[i]
            b = best_metrics[i]
            if a != b:
                return a > b if name == "bandwidth" else a < b
        return cand_path < best_path

    best_path = {n: None for n in nodes}
    best_metrics = {n: None for n in nodes}
    best_path[source] = [source]
    best_metrics[source] = (0, 0, None, 0)

    visited = {source}
    path = [source]
    # Frame: [node, next-neighbor slot, cost sum, bottleneck bandwidth,
    # latency sum] of the current path prefix.
    frames = [[source, 0, 0, MAX_METRIC, 0]]
    while frames:
        frame = frames[-1]
        u = frame[0]
        neighbors = adj[u]
        if frame[1] == len(neighbors):
            frames.pop()
            visited.discard(u)
            path.pop()
            continue
        to, w, bw, lat = neighbors[frame[1]]
        frame[1] += 1
        if to in visited:
            continue
        hops = len(frames)
        cost_sum = frame[2] + w
        bottleneck = bw if bw < frame[3] else frame[3]
        latency_sum = frame[4] + lat
        cand_metrics = (hops, cost_sum, bottleneck, latency_sum)
        visited.add(to)
        path.append(to)
        if best_path[to] is None or better(cand_metrics, path,
                                           best_metrics[to], best_path[to]):
            best_metrics[to] = cand_metrics
            best_path[to] = list(path)
        frames.append([to, 0, cost_sum, bottleneck, latency_sum])

    routes = []
    for n in sorted(nodes):
        p = best_path[n]
        if n == source:
            routes.append({"destination": n, "nextHop": source, "hopCount": 0,
                           "cost": 0, "bandwidth": None, "latency": 0,
                           "path": [source]})
        elif p is None:
            routes.append({"destination": n, "nextHop": None,
                           "hopCount": None, "cost": None, "bandwidth": None,
                           "latency": None, "path": []})
        else:
            hops, cost_sum, bottleneck, latency_sum = best_metrics[n]
            routes.append({"destination": n, "nextHop": p[1],
                           "hopCount": hops, "cost": cost_sum,
                           "bandwidth": bottleneck, "latency": latency_sum,
                           "path": p})
    return {"source": source, "order": list(order), "routes": routes}


def main():
    argv = sys.argv
    if len(argv) < 2:
        fail(2)
    if argv[1] == "route":
        if len(argv) != 4:
            fail(2)
        file_path, source = argv[2], argv[3]
        nodes, links, node_set = load_network(file_path)
        if source not in node_set:
            fail(5)
        result = compute_routes(nodes, links, source)
    elif argv[1] == "ecmp":
        if len(argv) != 5:
            fail(2)
        file_path, source, flow = argv[2], argv[3], argv[4]
        nodes, links, node_set = load_network(file_path)
        if not 1 <= len(flow) <= MAX_FLOW_LEN:
            fail(5)
        try:
            flow.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if source not in node_set:
            fail(5)
        result = compute_ecmp(nodes, links, source, flow)
    elif argv[1] == "metric":
        if len(argv) != 5:
            fail(2)
        file_path, source, order_text = argv[2], argv[3], argv[4]
        nodes, links, node_set = load_network(file_path, with_metrics=True)
        if source not in node_set:
            fail(5)
        order = parse_order(order_text)
        result = metric_routes(nodes, links, source, order)
    else:
        fail(2)
    payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")


if __name__ == "__main__":
    main()
