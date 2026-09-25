"""relay: single-source lowest-cost routing.

Usage: python relay.py route FILE SOURCE
       python relay.py ecmp FILE SOURCE FLOW

Exit codes: 2 bad args/subcommand, 3 file unreadable, 4 JSON syntax,
5 schema/topology/FLOW/unknown-SOURCE error. On failure stdout stays
empty and stderr is exactly {"error":N} plus a newline.
"""

import hashlib
import json
import sys

MAX_COST = 2147483647


def fail(code):
    sys.stderr.write('{"error":%d}\n' % code)
    raise SystemExit(code)


def _reject_constant(value):
    # NaN / Infinity / -Infinity are not valid JSON.
    raise ValueError("invalid JSON constant: " + value)


def load_network(path):
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

    if not isinstance(links, list):
        fail(5)
    seen_pairs = set()
    for link in links:
        if not isinstance(link, dict) or set(link) != {"from", "to", "cost", "up"}:
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
        pair = (frm, to)
        if pair in seen_pairs:
            fail(5)
        seen_pairs.add(pair)

    return nodes, links, node_set


def compute_routes(nodes, links, source):
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
    # Directed adjacency over up links only, neighbours sorted by name so
    # the greedy walk below yields the lexicographically smallest path.
    adj = {n: [] for n in nodes}
    index_of = {n: i for i, n in enumerate(nodes)}
    v = len(nodes)
    inf = v * MAX_COST + 1  # exceeds any real path cost

    dist = [[inf] * v for _ in range(v)]
    for i in range(v):
        dist[i][i] = 0
    for link in links:
        if link["up"]:
            frm, to, w = link["from"], link["to"], link["cost"]
            adj[frm].append((to, w))
            i, j = index_of[frm], index_of[to]
            if w < dist[i][j]:
                dist[i][j] = w
    for n in nodes:
        adj[n].sort()

    # Floyd-Warshall all-pairs lowest costs, O(V^3) time and O(V^2) space.
    for k in range(v):
        dk = dist[k]
        for a in range(v):
            da = dist[a]
            ak = da[k]
            if ak == inf:
                continue
            for b in range(v):
                nb = ak + dk[b]
                if nb < da[b]:
                    da[b] = nb

    s = index_of[source]
    ds = dist[s]
    routes = []
    for n in sorted(nodes):
        if n == source:
            routes.append({"destination": n, "nextHops": [source],
                           "selectedNextHop": source, "cost": 0,
                           "path": [source]})
            continue
        d = index_of[n]
        total = ds[d]
        if total == inf:
            routes.append({"destination": n, "nextHops": [],
                           "selectedNextHop": None, "cost": None,
                           "path": []})
            continue
        # First hops of lowest-total-cost paths: up links s->h with
        # w(s,h) + dist(h,d) == dist(s,d). Link validation forbids
        # parallel (from,to) pairs, so the set is already duplicate-free.
        hops = sorted({to for to, w in adj[source]
                       if w + dist[index_of[to]][d] == total})
        payload = json.dumps([flow, source, n], ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
        pick = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        first = hops[pick % len(hops)]
        # Lexicographically smallest equal-cost full path via `first`:
        # greedy on the sorted adjacency, always taking the smallest next
        # hop that still lies on a lowest-cost path to the destination.
        path = [source, first]
        cur = first
        while cur != n:
            cd = dist[index_of[cur]][d]
            for to, w in adj[cur]:
                if w + dist[index_of[to]][d] == cd:
                    path.append(to)
                    cur = to
                    break
        routes.append({"destination": n, "nextHops": hops,
                       "selectedNextHop": first, "cost": total,
                       "path": path})
    return {"source": source, "flow": flow, "routes": routes}


def main():
    argv = sys.argv
    if len(argv) < 2:
        fail(2)
    cmd = argv[1]
    if cmd == "route":
        if len(argv) != 4:
            fail(2)
        file_path = argv[2]
        source = argv[3]
        nodes, links, node_set = load_network(file_path)
        if source not in node_set:
            fail(5)
        result = compute_routes(nodes, links, source)
    elif cmd == "ecmp":
        if len(argv) != 5:
            fail(2)
        file_path = argv[2]
        source = argv[3]
        flow = argv[4]
        nodes, links, node_set = load_network(file_path)
        if not 1 <= len(flow) <= 256:
            fail(5)
        try:
            flow.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if source not in node_set:
            fail(5)
        result = compute_ecmp(nodes, links, source, flow)
    else:
        fail(2)
    sys.stdout.write(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    )


if __name__ == "__main__":
    main()
