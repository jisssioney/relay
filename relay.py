"""relay: single-source lowest-cost routing.

Usage: python relay.py route FILE SOURCE
       python relay.py ecmp FILE SOURCE FLOW
       python relay.py metric FILE SOURCE ORDER
       python relay.py protect FILE SOURCE DEST DELAY EVENTS

Exit codes: 2 bad args/subcommand, 3 file unreadable, 4 JSON syntax,
5 FLOW/ORDER/DELAY/EVENTS/schema/topology/unknown-node error. On failure
stdout stays empty and stderr is exactly {"error":N} plus a newline.
"""

import hashlib
import json
import sys

MAX_COST = 2147483647
MAX_FLOW_LEN = 256


def fail(code):
    sys.stderr.write('{"error":%d}\n' % code)
    raise SystemExit(code)


def _reject_constant(value):
    # NaN / Infinity / -Infinity are not valid JSON.
    raise ValueError("invalid JSON constant: " + value)


def load_network(path, metrics=False):
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

    base_keys = {"from", "to", "cost", "up"}
    link_keys = base_keys | {"bandwidth", "latency"} if metrics else base_keys

    if not isinstance(nodes, list):
        fail(5)
    node_set = set()
    for n in nodes:
        if type(n) is not str or n == "" or n in node_set:
            fail(5)
        node_set.add(n)

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
        if metrics:
            bw = link["bandwidth"]
            lat = link["latency"]
            if type(bw) is not int or not 1 <= bw <= MAX_COST:
                fail(5)
            if type(lat) is not int or not 0 <= lat <= MAX_COST:
                fail(5)
        pair = (frm, to)
        if pair in seen_pairs:
            fail(5)
        seen_pairs.add(pair)

    return nodes, links, node_set


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


def compute_metric(nodes, links, source, order_names):
    # Directed adjacency over up links only.
    adj = {n: [] for n in nodes}
    for link in links:
        if link["up"]:
            adj[link["from"]].append(
                (link["to"], link["cost"], link["bandwidth"], link["latency"]))

    # Enumerate every directed simple path from the source via DFS and keep
    # the best one per destination under the ORDER metric hierarchy. Ties on
    # every metric go to the path with the smallest Unicode code point order.
    # best[n] = (comparison_key, (hop, cost, bandwidth, latency), path)
    best = {}

    def metric_key(hop_count, cost, bandwidth, latency):
        m = {"hop": hop_count, "cost": cost, "bandwidth": bandwidth,
             "latency": latency}
        # bandwidth prefers the larger value; the others the smaller.
        return tuple(-m[name] if name == "bandwidth" else m[name]
                     for name in order_names)

    def consider(path, hop_count, cost, bandwidth, latency):
        key = metric_key(hop_count, cost, bandwidth, latency)
        dest = path[-1]
        cur = best.get(dest)
        if cur is None or key < cur[0] or (key == cur[0] and path < cur[2]):
            best[dest] = (key, (hop_count, cost, bandwidth, latency),
                          list(path))

    # Iterative DFS with an explicit stack, so the enumeration depth is
    # bounded by heap, not by the Python recursion limit. metrics[d] holds
    # the accumulated (hop, cost, bandwidth, latency) for path[:d+1].
    path = [source]
    visited = {source}
    metrics = [(0, 0, MAX_COST, 0)]
    consider(path, 0, 0, MAX_COST, 0)
    stack = [iter(adj[source])]
    while stack:
        try:
            to, w, bw, lat = next(stack[-1])
        except StopIteration:
            stack.pop()
            if stack:
                metrics.pop()
                visited.remove(path.pop())
            continue
        if to in visited:
            continue
        visited.add(to)
        path.append(to)
        hop_count, cost, bandwidth, latency = metrics[-1]
        entry = (hop_count + 1, cost + w, min(bandwidth, bw), latency + lat)
        metrics.append(entry)
        consider(path, *entry)
        stack.append(iter(adj[to]))

    routes = []
    for n in sorted(nodes):
        if n == source:
            routes.append({"destination": n, "nextHop": source, "hopCount": 0,
                           "cost": 0, "bandwidth": None, "latency": 0,
                           "path": [source]})
        elif n not in best:
            routes.append({"destination": n, "nextHop": None, "hopCount": None,
                           "cost": None, "bandwidth": None, "latency": None,
                           "path": []})
        else:
            _, (hop_count, cost, bandwidth, latency), path = best[n]
            routes.append({"destination": n, "nextHop": path[1],
                           "hopCount": hop_count, "cost": cost,
                           "bandwidth": bandwidth, "latency": latency,
                           "path": path})
    return {"source": source, "order": order_names, "routes": routes}


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


def _shortest_between(nodes, links, source, destination):
    # Cost and lexicographically smallest shortest path from source to
    # destination over up links, or (None, []) when unreachable.
    cost_of, path_of = shortest_paths(nodes, links, source)
    if cost_of[destination] is None:
        return None, []
    return cost_of[destination], path_of[destination]


def compute_protect(nodes, links, source, destination, delay, events):
    # Primary: optimal route on the initially-up graph. Backup: recompute
    # with the directed edges of the primary path removed. A route with no
    # path is {"cost": null, "path": []}.
    primary_cost, primary_path = _shortest_between(
        nodes, links, source, destination)
    primary = {"cost": primary_cost, "path": primary_path}
    if primary_cost is None:
        backup = {"cost": None, "path": []}
    else:
        blocked = set(zip(primary_path, primary_path[1:]))
        backup_links = [l for l in links
                        if (l["from"], l["to"]) not in blocked]
        backup_cost, backup_path = _shortest_between(
            nodes, backup_links, source, destination)
        backup = {"cost": backup_cost, "path": backup_path}

    # Live up-state per directed link pair, seeded from the topology.
    state = {(l["from"], l["to"]): l["up"] for l in links}

    def usable(route):
        p = route["path"]
        return bool(p) and all(
            state[(p[i], p[i + 1])] for i in range(len(p) - 1))

    def active_route():
        return primary if usable(primary) else (
            backup if usable(backup) else None)

    results = []
    for ev in events:
        t, frm, to, up = ev["time"], ev["from"], ev["to"], ev["up"]
        before_route = active_route()
        before = [] if before_route is None else list(before_route["path"])
        pair = (frm, to)
        unchanged = state[pair] == up
        if not unchanged:
            state[pair] = up
        after_route = active_route()
        after = [] if after_route is None else list(after_route["path"])
        choice_changed = after_route is not before_route
        if unchanged:
            reason = 0
        elif not choice_changed:
            reason = 1
        elif after_route is primary:
            reason = 2
        elif after_route is None:
            reason = 5
        elif before_route is None:
            reason = 4
        else:
            reason = 3
        result = {
            "time": t,
            "from": frm,
            "to": to,
            "up": up,
            "switchTime": None if not choice_changed else t + delay,
            "reason": reason,
            "before": before,
            "after": after,
        }
        results.append(result)

    return {"source": source, "destination": destination,
            "primary": primary, "backup": backup, "events": results}


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
        file_path, source, order = argv[2], argv[3], argv[4]
        nodes, links, node_set = load_network(file_path, metrics=True)
        order_names = order.split(",")
        if (len(order_names) != 4
                or set(order_names) != {"hop", "cost", "bandwidth", "latency"}
                or len(set(order_names)) != 4):
            fail(5)
        if source not in node_set:
            fail(5)
        result = compute_metric(nodes, links, source, order_names)
    elif argv[1] == "protect":
        if len(argv) != 7:
            fail(2)
        file_path, source, destination, delay_s, events_s = argv[2:7]
        nodes, links, node_set = load_network(file_path)
        if source not in node_set or destination not in node_set \
                or source == destination:
            fail(5)
        if not delay_s or any(c < "0" or c > "9" for c in delay_s):
            fail(5)
        delay = int(delay_s)
        if delay > MAX_COST:
            fail(5)
        try:
            events = json.loads(events_s, parse_constant=_reject_constant)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(events, list):
            fail(5)
        link_pairs = {(l["from"], l["to"]) for l in links}
        parsed_events = []
        last_time = None
        for ev in events:
            if not isinstance(ev, dict) or list(ev) != ["time", "from",
                                                        "to", "up"]:
                fail(5)
            t, frm, to, up = ev["time"], ev["from"], ev["to"], ev["up"]
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if last_time is not None and t < last_time:
                fail(5)
            last_time = t
            if type(frm) is not str or type(to) is not str:
                fail(5)
            if (frm, to) not in link_pairs:
                fail(5)
            if type(up) is not bool:
                fail(5)
            parsed_events.append({"time": t, "from": frm, "to": to,
                                  "up": up})
        result = compute_protect(nodes, links, source, destination, delay,
                                 parsed_events)
    else:
        fail(2)
    # Write raw UTF-8 bytes to the binary stdout buffer: the text layer
    # would apply the locale encoding and newline conversion (e.g. \r\n
    # on Windows), corrupting the required byte-exact output.
    out = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.buffer.write(out.encode("utf-8") + b"\n")


if __name__ == "__main__":
    main()
