"""relay: single-source lowest-cost routing.

Usage: python relay.py route FILE SOURCE
       python relay.py ecmp FILE SOURCE FLOW
       python relay.py metric FILE SOURCE ORDER
       python relay.py protect FILE SOURCE DESTINATION DELAY EVENTS
       python relay.py forward FILE SOURCE DESTINATION LIMIT TABLE
       python relay.py queue FILE FROM TO CAP STEP DATA
       python relay.py reorder FILE FROM TO BASE WINDOW DATA
       python relay.py converge FILE SRC DST D R EVENTS
       python relay.py policy FILE S D P C RULES
       python relay.py reserve FILE DATA
       python relay.py rebalance FILE DATA LIMIT
       python relay.py quality FILE A B DATA
       python relay.py replay FILE A B DATA
       python relay.py nfail FILE S D W DATA

Exit codes: 2 bad args/subcommand, 3 file unreadable, 4 JSON syntax
(for forward also duplicate keys or non-finite numbers in FILE/TABLE,
for queue/reorder/converge/policy/reserve/rebalance also those in
FILE/DATA/EVENTS/RULES, for quality/replay/nfail those in DATA), 5
FLOW/ORDER/DELAY/EVENTS/LIMIT/TABLE/CAP/STEP/BASE/WINDOW/DATA/D/R/P/C/
RULES/A/B/W/schema/topology/unknown-node/overflow error.
On failure stdout stays empty and stderr is exactly {"error":N} plus a
newline.
"""

import hashlib
import json
import math
import sys
from collections import deque

MAX_COST = 2147483647
MAX_FLOW_LEN = 256
MAX_TIME = 9223372036854775807


def fail(code):
    sys.stderr.write('{"error":%d}\n' % code)
    raise SystemExit(code)


def _reject_constant(value):
    # NaN / Infinity / -Infinity are not valid JSON.
    raise ValueError("invalid JSON constant: " + value)


def _finite_float(text):
    # Reject numbers like 1e999 that parse to a non-finite float.
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("non-finite number: " + text)
    return value


def _object_no_dup(pairs):
    # object_pairs_hook rejecting duplicate keys, which JSON objects
    # must not contain here even though json.loads would allow them.
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate key: " + key)
        obj[key] = value
    return obj


def load_network(path, metrics=False, strict=False):
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        fail(3)
    except UnicodeDecodeError:
        fail(4)

    try:
        if strict:
            data = json.loads(text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        else:
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


def compute_protect(nodes, links, source, destination, delay, events):
    # Primary: lowest-cost path in the initial up-graph. Backup: lowest-cost
    # path after removing the primary's directed edges. Both are computed
    # once here and never recomputed; events only flip link states.
    up_links = [link for link in links if link["up"]]
    cost_of, path_of = shortest_paths(nodes, up_links, source)
    primary_cost = cost_of[destination]
    primary_path = path_of[destination]
    if primary_path is None:
        backup_cost = None
        backup_path = None
    else:
        removed = set(zip(primary_path, primary_path[1:]))
        backup_links = [link for link in up_links
                        if (link["from"], link["to"]) not in removed]
        bcost_of, bpath_of = shortest_paths(nodes, backup_links, source)
        backup_cost = bcost_of[destination]
        backup_path = bpath_of[destination]

    state = {(link["from"], link["to"]): link["up"] for link in links}

    def usable(path):
        return (path is not None
                and all(state[pair] for pair in zip(path, path[1:])))

    def selected():
        # Prefer an available primary, then the backup, else no path.
        if usable(primary_path):
            return primary_path
        if usable(backup_path):
            return backup_path
        return None

    results = []
    current = selected()
    for event in events:
        before = current if current is not None else []
        pair = (event["from"], event["to"])
        if state[pair] == event["up"]:
            # Repeated setting is idempotent.
            reason = 0
            switch_time = None
            after = before
        else:
            state[pair] = event["up"]
            new = selected()
            after = new if new is not None else []
            if after == before:
                reason = 1
                switch_time = None
            else:
                switch_time = event["time"] + delay
                if new is primary_path:
                    reason = 2
                elif new is None:
                    reason = 5
                elif current is primary_path:
                    reason = 3
                else:
                    reason = 4
            current = new
        results.append({"time": event["time"], "from": event["from"],
                        "to": event["to"], "up": event["up"],
                        "switchTime": switch_time, "reason": reason,
                        "before": before, "after": after})

    return {"source": source, "destination": destination,
            "primary": {"cost": primary_cost, "path": primary_path or []},
            "backup": {"cost": backup_cost, "path": backup_path or []},
            "events": results}


def compute_forward(links, source, destination, limit, table):
    # Hop-by-hop forwarding along the explicit next-hop table, over up
    # links only. seen holds every trace node before the current one, so
    # arriving at a node already departed means the trace has a loop.
    up_pairs = {(link["from"], link["to"]) for link in links if link["up"]}
    trace = [[0, source]]
    seen = set()
    current = source
    time = 0
    hops = 0
    while True:
        if current == destination:
            status = "delivered"
            break
        if current in seen:
            status = "loop"
            break
        if hops == limit:
            status = "hop_limit"
            break
        nxt = table[current]
        if nxt is None or (current, nxt) not in up_pairs:
            status = "unreachable"
            break
        seen.add(current)
        current = nxt
        time += 1
        hops += 1
        trace.append([time, current])
    return {"source": source, "destination": destination, "limit": limit,
            "status": status, "time": time, "trace": trace}


def _bounded_int_arg(text):
    # Decimal command-line integer in [0, MAX_COST]. Leading zeros are
    # stripped before int() so absurdly long digit strings cannot trip
    # Python's integer conversion digit limit.
    if not text or any(c not in "0123456789" for c in text):
        fail(5)
    digits = text.lstrip("0") or "0"
    if len(digits) > 10:
        fail(5)
    value = int(digits)
    if value > MAX_COST:
        fail(5)
    return value


def compute_queue(frm, to, cap, step, packets):
    # Store-and-forward shaper on a single directed link. A packet holds
    # buffer space from its arrival until its departure; starts are never
    # earlier than the previous departure, so departures leave the buffer
    # in FIFO order and a deque gives O(1) amortized release per packet.
    buffer = deque()  # (depart, size) of packets still occupying capacity
    occupancy = 0
    last_depart = 0
    results = []
    for pid, time, size in packets:
        while buffer and buffer[0][0] <= time:
            occupancy -= buffer.popleft()[1]
        if occupancy + size > cap:
            # Dropped packets do not alter the schedule.
            results.append([pid, "drop", None, None, None])
            continue
        start = time if time > last_depart else last_depart
        depart = start + size * step
        if depart > MAX_TIME:
            fail(5)
        last_depart = depart
        occupancy += size
        buffer.append((depart, size))
        results.append([pid, "ok", start, depart, start - time])
    return {"from": frm, "to": to, "cap": cap, "step": step,
            "packets": results}


def compute_reorder(frm, to, base, window, packets):
    # Reorder buffer on a single directed up link. Events are processed in
    # (arrival, seq) order with an explicit clock that jumps to each
    # arrival; a packet too far ahead of the next expected sequence number
    # is dropped, otherwise it is buffered and every contiguous packet
    # from next onward is released at the current clock. Each sequence
    # number arrives once and next never passes an unreleased one, so a
    # dict keyed by seq gives O(1) amortized release per packet.
    events = sorted(packets, key=lambda p: (p[2], p[1]))
    next_seq = 0
    pending = {}  # seq -> index of the packet's entry in results
    results = []
    for pid, seq, arrival in events:
        if seq - next_seq > window:
            # Dropped packets do not alter the buffer.
            results.append([pid, seq, arrival, "over_window", None, None])
            continue
        pending[seq] = len(results)
        results.append([pid, seq, arrival, "buffered", None, None])
        while next_seq in pending:
            entry = results[pending.pop(next_seq)]
            entry[3] = "released"
            entry[4] = arrival
            entry[5] = arrival - entry[2]
            next_seq += 1
    return {"from": frm, "to": to, "base": base, "window": window,
            "packets": results}


def compute_converge(nodes, links, source, destination, delay, run, events):
    # Debounced route recomputation after link changes. The clock starts at
    # 0 with the initial route installed. Events are applied first at each
    # tick; a real change cancels any outstanding cycle and rearms the
    # trigger at t+D and completion at t+D+R. The trigger recomputes the
    # shortest path over the current topology and the completion installs
    # it; a change in between invalidates the pending result and restarts
    # the cycle. Setting a link to its current state changes nothing and
    # leaves the timer untouched.
    state = {(link["from"], link["to"]): link["up"] for link in links}

    def live_links():
        # shortest_paths reads each dict's "up" flag, so mirror the current
        # state there rather than relying on the original link values.
        return [{**link, "up": state[(link["from"], link["to"])]}
                for link in links
                if state[(link["from"], link["to"])]]

    cost_of, path_of = shortest_paths(nodes, live_links(), source)
    installed_cost = cost_of[destination]
    installed_path = path_of[destination]

    def reachable(path):
        return path is not None and all(
            state[pair] for pair in zip(path, path[1:]))

    def entry(now, kind):
        # The last three fields always describe the currently installed
        # route: an installed path keeps its cost and path even while a
        # down edge makes it unreachable; nothing installed means no
        # route at all.
        if installed_path is None:
            return [now, kind, None, [], False]
        return [now, kind, installed_cost, installed_path,
                reachable(installed_path)]

    timeline = [entry(0, 0)]

    trigger_at = None
    complete_at = None
    pending_cost = None
    pending_path = None
    i = 0
    n = len(events)
    while i < n or trigger_at is not None or complete_at is not None:
        wakes = []
        if i < n:
            wakes.append(events[i]["time"])
        if trigger_at is not None:
            wakes.append(trigger_at)
        if complete_at is not None:
            wakes.append(complete_at)
        now = min(wakes)
        # All events at this tick run before either timer, and the trigger
        # at the same tick fires before the completion.
        while i < n and events[i]["time"] == now:
            event = events[i]
            pair = (event["from"], event["to"])
            i += 1
            if state[pair] != event["up"]:
                # Every real change cancels the unfinished cycle (whether
                # or not the trigger has fired) and rearms both timers.
                state[pair] = event["up"]
                trigger_at = now + delay
                complete_at = trigger_at + run
                if complete_at > MAX_TIME:
                    fail(5)
                pending_cost = None
                pending_path = None
            timeline.append(entry(now, 1))
        if trigger_at is not None and trigger_at == now:
            cost_of, path_of = shortest_paths(nodes, live_links(), source)
            pending_cost = cost_of[destination]
            pending_path = path_of[destination]
            trigger_at = None
            timeline.append(entry(now, 2))
        if complete_at is not None and complete_at == now:
            installed_cost = pending_cost
            installed_path = pending_path
            complete_at = None
            pending_cost = None
            pending_path = None
            timeline.append(entry(now, 3))

    return {"timeline": timeline}


def _priority_order(rules):
    # Indices of rules sorted by ascending priority n, ties keeping
    # array order. LSD radix sort over the 32-bit non-negative keys:
    # four stable 256-bucket counting passes give worst-case O(R) time
    # and O(R) space for any rule count R, where a comparison sort
    # would only guarantee O(R log R).
    order = list(range(len(rules)))
    for shift in (0, 8, 16, 24):
        buckets = [[] for _ in range(256)]
        for i in order:
            buckets[(rules[i][0] >> shift) & 0xFF].append(i)
        order = [i for bucket in buckets for i in bucket]
    return order


def compute_policy(nodes, links, source, destination, port, klass, rules):
    # Policy routing with a shortest-path fallback. Rules are considered
    # by ascending priority n (ties keep their array order, which the
    # stable radix sort in _priority_order guarantees); a rule matches when its s/d equal the
    # requested source/destination and its null port/class fields act as
    # wildcards while the rest compare equal. The first matching rule
    # whose path has no down edge supplies the route; with none usable
    # the route falls back to the lowest-cost path over up links.
    up_of = {}
    cost_of_link = {}
    for link in links:
        pair = (link["from"], link["to"])
        up_of[pair] = link["up"]
        cost_of_link[pair] = link["cost"]

    for i in _priority_order(rules):
        _, s, d, p, c, path = rules[i]
        if s != source or d != destination:
            continue
        if p is not None and p != port:
            continue
        if c is not None and c != klass:
            continue
        pairs = list(zip(path, path[1:]))
        if not all(up_of[pair] for pair in pairs):
            # Paths with a down edge are skipped, not fallen back from.
            continue
        return {"source": source, "destination": destination,
                "port": port, "class": klass, "rule": i,
                "cost": sum(cost_of_link[pair] for pair in pairs),
                "path": path}

    cost_of, path_of = shortest_paths(nodes, links, source)
    cost = cost_of[destination]
    path = path_of[destination]
    return {"source": source, "destination": destination,
            "port": port, "class": klass, "rule": None,
            "cost": cost, "path": path if path is not None else []}


def compute_reserve(nodes, links, requests):
    # Bandwidth reservation over up directed simple paths, processed in
    # request order. residual[i] is the remaining capacity of links[i];
    # each accepted request decrements it along its path and rejections
    # leave it untouched. Candidates are ranked by the post-reservation
    # utilization max((C-r+b)/C) — compared as fractions with integer
    # cross-multiplication, never floats — then cost sum, then the
    # path's Unicode code point order.
    adj = {n: [] for n in nodes}
    index_of = {}
    for index, link in enumerate(links):
        index_of[(link["from"], link["to"])] = index
        if link["up"]:
            adj[link["from"]].append((link["to"], link["cost"], index))
    capacity = [link["bandwidth"] for link in links]
    residual = list(capacity)

    allocations = []
    for rid, source, destination, b in requests:
        # Reachability ignores residual capacity: it distinguishes
        # "unreachable" (no up path at all) from "no_capacity".
        seen = {source}
        stack = [source]
        while stack:
            for to, _, _ in adj[stack.pop()]:
                if to not in seen:
                    seen.add(to)
                    stack.append(to)
        if destination not in seen:
            allocations.append([rid, "unreachable", b, None, []])
            continue

        # Enumerate every up simple path whose edges all have residual
        # >= b via iterative DFS, keeping the best candidate. states[d]
        # holds (util_num, util_den, cost) for path[:d+1]: the running
        # maximum utilization fraction and the cost sum.
        best_num = best_den = best_cost = None
        best_path = None
        path = [source]
        visited = {source}
        states = [(0, 1, 0)]
        iters = [iter(adj[source])]
        while iters:
            try:
                to, w, index = next(iters[-1])
            except StopIteration:
                iters.pop()
                if iters:
                    states.pop()
                    visited.remove(path.pop())
                continue
            if to in visited or residual[index] < b:
                continue
            num, den, cost = states[-1]
            e_num = capacity[index] - residual[index] + b
            e_den = capacity[index]
            if e_num * den > num * e_den:
                num, den = e_num, e_den
            cost += w
            visited.add(to)
            path.append(to)
            if to == destination:
                if (best_path is None
                        or num * best_den < best_num * den
                        or (num * best_den == best_num * den
                            and (cost < best_cost
                                 or (cost == best_cost
                                     and path < best_path)))):
                    best_num, best_den, best_cost = num, den, cost
                    best_path = list(path)
                # A simple path cannot pass through the destination and
                # return to it, so nothing extends past it.
                visited.remove(path.pop())
            else:
                states.append((num, den, cost))
                iters.append(iter(adj[to]))

        if best_path is None:
            allocations.append([rid, "no_capacity", b, None, []])
            continue
        if best_cost > MAX_TIME:
            fail(5)
        for a, c in zip(best_path, best_path[1:]):
            residual[index_of[(a, c)]] -= b
        allocations.append([rid, "accepted", b, best_cost, best_path])

    return {"allocations": allocations,
            "links": [[link["from"], link["to"], capacity[i],
                       capacity[i] - residual[i], residual[i]]
                      for i, link in enumerate(links)]}


def _format_peak(num, den):
    # num/den rounded half up to exactly six decimals, computed in
    # integers so no float rounding can leak into the output.
    scaled = (2 * num * 1000000 + den) // (2 * den)
    return "%d.%06d" % (scaled // 1000000, scaled % 1000000)


def compute_rebalance(nodes, links, demands, limit):
    # Joint path reallocation minimizing the peak link utilization. Every
    # demand keeps exactly one up simple path; an assignment is feasible
    # when no link carries more than its bandwidth and at most `limit`
    # demands leave their original path. Feasible assignments are ranked
    # by peak used/bandwidth (fractions compared with integer cross-
    # multiplication, never floats), then by the number of rerouted
    # demands, then by the DATA-order vector of paths in Unicode code
    # point order. The best assignment is committed atomically only when
    # its peak is strictly below the initial one. The search enumerates
    # the Cartesian product of the per-demand simple-path sets with an
    # explicit stack — O((V!)^K (KV+E)) time, O(KV+E) space — pruning
    # branches that already violate capacity or the reroute limit.
    adj = {n: [] for n in nodes}
    index_of = {}
    for index, link in enumerate(links):
        index_of[(link["from"], link["to"])] = index
        if link["up"]:
            adj[link["from"]].append((link["to"], index))
    capacity = [link["bandwidth"] for link in links]

    initial_used = [0] * len(links)
    for _, _, _, b, path in demands:
        for a, c in zip(path, path[1:]):
            initial_used[index_of[(a, c)]] += b
    for index, used_here in enumerate(initial_used):
        if used_here > capacity[index]:
            # The initial placement must already fit every link.
            fail(5)

    def peak_of(used):
        # max(used[i]/capacity[i]) as an exact fraction.
        num, den = 0, 1
        for u, c in zip(used, capacity):
            if u * den > num * c:
                num, den = u, c
        return num, den

    init_num, init_den = peak_of(initial_used)

    def enum_paths(source, destination):
        # Yield (path, edge_indices) for every up simple path from
        # source to destination via iterative DFS, so the enumeration
        # depth is bounded by heap, not by the Python recursion limit.
        path = [source]
        edges = []
        visited = {source}
        iters = [iter(adj[source])]
        while iters:
            try:
                to, index = next(iters[-1])
            except StopIteration:
                iters.pop()
                if iters:
                    visited.remove(path.pop())
                    edges.pop()
                continue
            if to in visited:
                continue
            visited.add(to)
            path.append(to)
            edges.append(index)
            if to == destination:
                yield list(path), list(edges)
                visited.remove(path.pop())
                edges.pop()
            else:
                iters.append(iter(adj[to]))

    best_num = best_den = best_moved = None
    best_paths = best_used = None
    count = len(demands)
    if count:
        used = [0] * len(links)
        current_paths = [None] * count
        current_edges = [None] * count
        generators = [None] * count
        moved = 0
        depth = 0
        generators[0] = enum_paths(demands[0][1], demands[0][2])
        while depth >= 0:
            item = next(generators[depth], None)
            if item is None:
                # The level's paths are exhausted: backtrack and undo
                # the shallower level's assignment.
                generators[depth] = None
                depth -= 1
                if depth >= 0:
                    b = demands[depth][3]
                    for index in current_edges[depth]:
                        used[index] -= b
                    if current_paths[depth] != demands[depth][4]:
                        moved -= 1
                    current_paths[depth] = None
                    current_edges[depth] = None
                continue
            path, edges = item
            b = demands[depth][3]
            if any(used[index] + b > capacity[index] for index in edges):
                continue
            delta = 1 if path != demands[depth][4] else 0
            if moved + delta > limit:
                continue
            for index in edges:
                used[index] += b
            current_paths[depth] = path
            current_edges[depth] = edges
            moved += delta
            if depth + 1 < count:
                depth += 1
                generators[depth] = enum_paths(demands[depth][1],
                                               demands[depth][2])
            else:
                num, den = peak_of(used)
                if (best_paths is None
                        or num * best_den < best_num * den
                        or (num * best_den == best_num * den
                            and (moved < best_moved
                                 or (moved == best_moved
                                     and current_paths < best_paths)))):
                    best_num, best_den = num, den
                    best_moved = moved
                    best_paths = list(current_paths)
                    best_used = list(used)
                for index in edges:
                    used[index] -= b
                moved -= delta
                current_paths[depth] = None
                current_edges[depth] = None

    if best_paths is not None and best_num * init_den < init_num * best_den:
        status = 1
        final_used = best_used
        new_paths = best_paths
        moved_out = best_moved
        out_num, out_den = best_num, best_den
    else:
        status = 0
        final_used = initial_used
        new_paths = [path for _, _, _, _, path in demands]
        moved_out = 0
        out_num, out_den = init_num, init_den

    return {"status": status,
            "peak": [_format_peak(init_num, init_den),
                     _format_peak(out_num, out_den)],
            "moved": moved_out,
            "flows": [[demands[i][0], demands[i][4], new_paths[i]]
                      for i in range(count)],
            "links": [[link["from"], link["to"], capacity[i],
                       final_used[i]]
                      for i, link in enumerate(links)]}


def compute_quality(a, b, items):
    # Per-flow delivery quality over the items with a <= t <= b, kept in
    # input order (t is non-decreasing and equal t keeps input order).
    # items hold validated (id, f, t, d, path) tuples with d None for a
    # lost packet. _format_peak is exactly F: q = (2x*10^6 + y)//(2y)
    # rendered as q*10^-6 with six fixed decimals, all in integers.
    total = 0
    delays = []
    flow_paths = {}  # f -> paths of its delivered packets, in order
    for _, f, t, d, path in items:
        if not a <= t <= b:
            continue
        total += 1
        if d is None:
            # A flow seen only through losses is still listed, with c=0.
            flow_paths.setdefault(f, [])
            continue
        delays.append(d)
        flow_paths.setdefault(f, []).append(path)

    delivered = len(delays)
    lost = total - delivered
    stats = [total, delivered, lost,
             _format_peak(lost, total) if total else "0.000000"]

    n = delivered
    if n:
        delays.sort()
        # p95 is the ceil(0.95*n)-th smallest, as a 1-based index.
        delay = [n, delays[0], delays[-1],
                 _format_peak(sum(delays), n),
                 delays[(95 * n + 99) // 100 - 1]]
    else:
        delay = [0, None, None, None, None]

    changes = [[f, sum(1 for x, y in zip(paths, paths[1:]) if x != y)]
               for f, paths in sorted(flow_paths.items())]

    return {"start": a, "end": b, "stats": stats, "delay": delay,
            "changes": changes}


def compute_replay(nodes, links, a, b, events):
    # Event-driven replay over a mutable up-graph. The clock jumps to each
    # event's t and processes it atomically; equal t keeps input order, so
    # a link item at the same tick before a packet already affects it.
    # Link items only flip their link's "up" flag in place (repeated
    # setting is idempotent); every packet item is routed on the current
    # up-graph over the lowest-cost path, ties going to the complete node
    # sequence smallest in Unicode code point order (exactly the
    # shortest_paths tie-break), and its delay is the latency sum along
    # that path. Only packets with a <= t <= b are collected, in event
    # order; stats/delay/changes reuse compute_quality on those packets.
    index_of = {}
    latency_of = {}
    for index, link in enumerate(links):
        pair = (link["from"], link["to"])
        index_of[pair] = index
        latency_of[pair] = link["latency"]

    packets = []
    items = []
    for event in events:
        if event[0] == 0:
            _, _, u, v, up = event
            links[index_of[(u, v)]]["up"] = up
            continue
        _, t, pid, f, s, d = event
        _, path_of = shortest_paths(nodes, links, s)
        path = path_of[d]
        if path is None:
            delay = None
            out_path = []
        else:
            delay = 0
            for x, y in zip(path, path[1:]):
                delay += latency_of[(x, y)]
            if delay > MAX_TIME:
                fail(5)
            out_path = path
        if a <= t <= b:
            packets.append([pid, f, t, delay, out_path])
            items.append((pid, f, t, delay, out_path))

    summary = compute_quality(a, b, items)
    return {"start": a, "end": b, "packets": packets,
            "stats": summary["stats"], "delay": summary["delay"],
            "changes": summary["changes"]}


def compute_nfail(nodes, links, source, destination, wait, events):
    # 1+1 protection with node failures and a W-tick switch timer. Both
    # routes are fixed once here from the initial all-up graph (events
    # only flip node states): the primary is the lowest-cost up path,
    # ties going to the full node sequence smallest in Unicode code
    # point order; the backup is recomputed on a graph with the
    # primary's internal nodes and directed edges deleted, and is
    # absent whenever the primary is absent. Events share one
    # non-decreasing clock; a node item flips that node's state
    # (repeated setting is idempotent) and a packet item is delivered
    # only on the currently active route when all of its nodes are up.
    up_links = [link for link in links if link["up"]]
    cost_of, path_of = shortest_paths(nodes, up_links, source)
    primary_cost = cost_of[destination]
    primary_path = path_of[destination]
    if primary_path is None:
        backup_cost = None
        backup_path = None
    else:
        removed_nodes = set(primary_path[1:-1])
        removed_edges = set(zip(primary_path, primary_path[1:]))
        backup_nodes = [n for n in nodes if n not in removed_nodes]
        backup_links = [link for link in up_links
                        if (link["from"] not in removed_nodes
                            and link["to"] not in removed_nodes
                            and (link["from"], link["to"]) not in removed_edges)]
        bcost_of, bpath_of = shortest_paths(backup_nodes, backup_links, source)
        backup_cost = bcost_of[destination]
        backup_path = bpath_of[destination]

    primary = [primary_cost, primary_path if primary_path is not None else []]
    backup = [backup_cost, backup_path if backup_path is not None else []]

    up_of = {n: True for n in nodes}
    # Both routes are fixed, so a node flip updates a constant-time
    # "down nodes on the route" counter instead of rescanning paths.
    on_primary = set(primary_path or ())
    on_backup = set(backup_path or ())
    down_on = {1: 0, 2: 0}

    def target():
        # First fully-up candidate in primary, backup, no-route order.
        if primary_path is not None and down_on[1] == 0:
            return 1
        if backup_path is not None and down_on[2] == 0:
            return 2
        return 0

    active = target()
    active_path = (primary_path if active == 1
                   else backup_path if active == 2 else None)
    fire_at = None
    pending_target = active
    segments = []
    segment_start = 0
    results = []

    def close_segment(end):
        nonlocal segment_start
        if active_path is not None:
            segments.append([segment_start, end, active_path])
        segment_start = end

    def fire(now):
        # The timer at `now` wins: install the route captured when it
        # was armed, regardless of where that route currently stands.
        nonlocal active, active_path, fire_at
        close_segment(now)
        active = pending_target
        active_path = (primary_path if active == 1
                       else backup_path if active == 2 else None)
        fire_at = None

    i = 0
    n = len(events)
    while i < n or fire_at is not None:
        if i >= n:
            # Advance after the last item to finish the pending timer.
            fire(fire_at)
            continue
        now = events[i][1]
        if fire_at is not None and fire_at < now:
            # Crossing an input-free deadline finishes the timer first.
            fire(fire_at)
            continue
        # Inputs at this tick run first, in order; a real change cancels
        # or rearms the timer (to now+W) before it could complete here.
        while i < n and events[i][1] == now:
            event = events[i]
            i += 1
            if event[0] == 0:
                _, _, node, is_up = event
                if up_of[node] != is_up:
                    up_of[node] = is_up
                    delta = 1 if not is_up else -1
                    if node in on_primary:
                        down_on[1] += delta
                    if node in on_backup:
                        down_on[2] += delta
                    new_target = target()
                    if new_target != active:
                        pending_target = new_target
                        fire_at = now + wait
                        if fire_at > MAX_TIME:
                            fail(5)
                    else:
                        fire_at = None
            else:
                _, _, pid = event
                delivered = active_path is not None and (
                    (active_path is primary_path and down_on[1] == 0)
                    or (active_path is backup_path and down_on[2] == 0))
                if delivered:
                    cost = primary_cost if active == 1 else backup_cost
                    results.append([pid, now, 0, cost, active_path])
                elif not up_of[source] or not up_of[destination]:
                    results.append([pid, now, 1, None, []])
                else:
                    results.append([pid, now, 2, None, []])
        if fire_at is not None and fire_at == now:
            # Same tick: the timer completes only after every input.
            fire(now)

    return {"m": primary, "b": backup, "s": segments, "p": results}


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
        file_path, source, destination = argv[2], argv[3], argv[4]
        delay_text, events_text = argv[5], argv[6]
        nodes, links, node_set = load_network(file_path)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        if (not delay_text
                or any(c not in "0123456789" for c in delay_text)):
            fail(5)
        delay = int(delay_text)
        if delay > MAX_COST:
            fail(5)
        try:
            events = json.loads(events_text, parse_constant=_reject_constant)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(events, list):
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        previous_time = None
        for event in events:
            if (not isinstance(event, dict)
                    or list(event) != ["time", "from", "to", "up"]):
                fail(5)
            time = event["time"]
            frm = event["from"]
            to = event["to"]
            up = event["up"]
            if type(time) is not int or not 0 <= time <= MAX_COST:
                fail(5)
            if previous_time is not None and time < previous_time:
                fail(5)
            previous_time = time
            if (type(frm) is not str or type(to) is not str
                    or (frm, to) not in pair_set):
                fail(5)
            if type(up) is not bool:
                fail(5)
        result = compute_protect(nodes, links, source, destination,
                                 delay, events)
    elif argv[1] == "forward":
        if len(argv) != 7:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        limit_text, table_text = argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, strict=True)
        if source not in node_set or destination not in node_set:
            fail(5)
        if (not limit_text
                or any(c not in "0123456789" for c in limit_text)):
            fail(5)
        # Strip leading zeros before int() so absurdly long digit strings
        # cannot trip Python's integer conversion digit limit.
        limit_digits = limit_text.lstrip("0") or "0"
        if len(limit_digits) > 10:
            fail(5)
        limit = int(limit_digits)
        if limit > MAX_COST:
            fail(5)
        try:
            table = json.loads(table_text, parse_constant=_reject_constant,
                               parse_float=_finite_float,
                               object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(table, dict) or set(table) != node_set:
            fail(5)
        for value in table.values():
            if (value is not None
                    and (type(value) is not str or value not in node_set)):
                fail(5)
        result = compute_forward(links, source, destination, limit, table)
    elif argv[1] == "queue":
        if len(argv) != 8:
            fail(2)
        file_path, frm, to = argv[2], argv[3], argv[4]
        cap_text, step_text, data_text = argv[5], argv[6], argv[7]
        nodes, links, node_set = load_network(file_path, strict=True)
        if frm not in node_set or to not in node_set:
            fail(5)
        if not any(link["from"] == frm and link["to"] == to and link["up"]
                   for link in links):
            fail(5)
        cap = _bounded_int_arg(cap_text)
        if cap < 1:
            fail(5)
        step = _bounded_int_arg(step_text)
        if step < 1:
            fail(5)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        packets = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if (not isinstance(item, dict)
                    or set(item) != {"id", "time", "size"}):
                fail(5)
            pid = item["id"]
            time = item["time"]
            size = item["size"]
            if type(pid) is not str or pid == "" or pid in seen_ids:
                fail(5)
            try:
                pid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            seen_ids.add(pid)
            if type(time) is not int or not 0 <= time <= MAX_COST:
                fail(5)
            if previous_time is not None and time < previous_time:
                fail(5)
            previous_time = time
            if type(size) is not int or not 1 <= size <= MAX_COST:
                fail(5)
            packets.append((pid, time, size))
        result = compute_queue(frm, to, cap, step, packets)
    elif argv[1] == "reorder":
        if len(argv) != 8:
            fail(2)
        file_path, frm, to = argv[2], argv[3], argv[4]
        base_text, window_text, data_text = argv[5], argv[6], argv[7]
        nodes, links, node_set = load_network(file_path, strict=True)
        if frm not in node_set or to not in node_set:
            fail(5)
        if not any(link["from"] == frm and link["to"] == to and link["up"]
                   for link in links):
            fail(5)
        base = _bounded_int_arg(base_text)
        window = _bounded_int_arg(window_text)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        packets = []
        seen_ids = set()
        previous_time = None
        for seq, item in enumerate(data):
            if not isinstance(item, list) or len(item) != 3:
                fail(5)
            pid, time, jitter = item
            if type(pid) is not str or pid == "" or pid in seen_ids:
                fail(5)
            try:
                pid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            seen_ids.add(pid)
            if type(time) is not int or not 0 <= time <= MAX_COST:
                fail(5)
            if previous_time is not None and time < previous_time:
                fail(5)
            previous_time = time
            if (type(jitter) is not int
                    or not -MAX_COST <= jitter <= MAX_COST):
                fail(5)
            delay = base + jitter
            arrival = time + delay
            if delay < 0 or arrival > MAX_COST:
                fail(5)
            packets.append((pid, seq, arrival))
        result = compute_reorder(frm, to, base, window, packets)
    elif argv[1] == "converge":
        if len(argv) != 8:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        delay_text, run_text, events_text = argv[5], argv[6], argv[7]
        nodes, links, node_set = load_network(file_path, strict=True)
        if source not in node_set or destination not in node_set:
            fail(5)
        delay = _bounded_int_arg(delay_text)
        run = _bounded_int_arg(run_text)
        try:
            events = json.loads(events_text, parse_constant=_reject_constant,
                                parse_float=_finite_float,
                                object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(events, list):
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        previous_time = None
        for event in events:
            if (not isinstance(event, dict)
                    or list(event) != ["time", "from", "to", "up"]):
                fail(5)
            time = event["time"]
            frm = event["from"]
            to = event["to"]
            up = event["up"]
            if type(time) is not int or not 0 <= time <= MAX_COST:
                fail(5)
            if previous_time is not None and time < previous_time:
                fail(5)
            previous_time = time
            if (type(frm) is not str or type(to) is not str
                    or (frm, to) not in pair_set):
                fail(5)
            if type(up) is not bool:
                fail(5)
        result = compute_converge(nodes, links, source, destination,
                                  delay, run, events)
    elif argv[1] == "policy":
        if len(argv) != 8:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        port_text, klass, rules_text = argv[5], argv[6], argv[7]
        nodes, links, node_set = load_network(file_path, strict=True)
        if source not in node_set or destination not in node_set:
            fail(5)
        port = _bounded_int_arg(port_text)
        if port > 65535:
            fail(5)
        if not 1 <= len(klass) <= 32:
            fail(5)
        try:
            klass.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        try:
            rule_items = json.loads(rules_text,
                                    parse_constant=_reject_constant,
                                    parse_float=_finite_float,
                                    object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(rule_items, list):
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        rules = []
        for item in rule_items:
            if not isinstance(item, list) or len(item) != 6:
                fail(5)
            n, s, d, p, c, path = item
            if type(n) is not int or not 0 <= n <= MAX_COST:
                fail(5)
            if (type(s) is not str or type(d) is not str
                    or s not in node_set or d not in node_set):
                fail(5)
            if p is not None and (type(p) is not int
                                  or not 0 <= p <= 65535):
                fail(5)
            if c is not None:
                if type(c) is not str or not 1 <= len(c) <= 32:
                    fail(5)
                try:
                    c.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
            if (not isinstance(path, list) or not path
                    or path[0] != s or path[-1] != d):
                fail(5)
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for a, b in zip(path, path[1:]):
                if (a, b) not in pair_set:
                    fail(5)
            rules.append((n, s, d, p, c, path))
        result = compute_policy(nodes, links, source, destination,
                                port, klass, rules)
    elif argv[1] == "reserve":
        if len(argv) != 4:
            fail(2)
        file_path, data_text = argv[2], argv[3]
        nodes, links, node_set = load_network(file_path, metrics=True,
                                              strict=True)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        requests = []
        seen_ids = set()
        for item in data:
            if not isinstance(item, list) or len(item) != 4:
                fail(5)
            rid, s, d, b = item
            if type(rid) is not str or not 1 <= len(rid) <= 64:
                fail(5)
            try:
                rid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if rid in seen_ids:
                fail(5)
            seen_ids.add(rid)
            if (type(s) is not str or type(d) is not str
                    or s not in node_set or d not in node_set or s == d):
                fail(5)
            if type(b) is not int or not 1 <= b <= MAX_COST:
                fail(5)
            requests.append((rid, s, d, b))
        result = compute_reserve(nodes, links, requests)
    elif argv[1] == "rebalance":
        if len(argv) != 5:
            fail(2)
        file_path, data_text, limit_text = argv[2], argv[3], argv[4]
        nodes, links, node_set = load_network(file_path, metrics=True,
                                              strict=True)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        up_of = {}
        for link in links:
            up_of[(link["from"], link["to"])] = link["up"]
        demands = []
        seen_ids = set()
        for item in data:
            if not isinstance(item, list) or len(item) != 5:
                fail(5)
            rid, s, d, b, path = item
            if type(rid) is not str or not 1 <= len(rid) <= 64:
                fail(5)
            try:
                rid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if rid in seen_ids:
                fail(5)
            seen_ids.add(rid)
            if (type(s) is not str or type(d) is not str
                    or s not in node_set or d not in node_set or s == d):
                fail(5)
            if type(b) is not int or not 1 <= b <= MAX_COST:
                fail(5)
            if (not isinstance(path, list) or not path
                    or path[0] != s or path[-1] != d):
                fail(5)
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for a, c in zip(path, path[1:]):
                pair = (a, c)
                if pair not in up_of or not up_of[pair]:
                    fail(5)
            demands.append((rid, s, d, b, path))
        limit = _bounded_int_arg(limit_text)
        result = compute_rebalance(nodes, links, demands, limit)
    elif argv[1] == "quality":
        if len(argv) != 6:
            fail(2)
        file_path, a_text, b_text, data_text = \
            argv[2], argv[3], argv[4], argv[5]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        items = []
        seen_ids = {}  # id -> (f, t, d, path) of its first occurrence
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) != 5:
                fail(5)
            pid, f, t, d, path = item
            if type(pid) is not str or not 1 <= len(pid) <= 64:
                fail(5)
            try:
                pid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if type(f) is not str or not 1 <= len(f) <= 64:
                fail(5)
            try:
                f.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if d is not None and (type(d) is not int
                                  or not 0 <= d <= MAX_COST):
                fail(5)
            if not isinstance(path, list):
                fail(5)
            if d is None:
                # A lost packet carries no path at all.
                if path:
                    fail(5)
            else:
                # A delivered packet's path is a non-empty simple node
                # array walking up directed edges.
                if not path:
                    fail(5)
                for node in path:
                    if type(node) is not str or node not in node_set:
                        fail(5)
                if len(set(path)) != len(path):
                    fail(5)
                for x, y in zip(path, path[1:]):
                    if (x, y) not in up_pairs:
                        fail(5)
            signature = (f, t, d, path)
            if pid in seen_ids:
                # A repeated id is dropped when the whole item matches;
                # the same id on a different item is an error.
                if seen_ids[pid] != signature:
                    fail(5)
                continue
            seen_ids[pid] = signature
            items.append((pid, f, t, d, path))
        result = compute_quality(a, b, items)
    elif argv[1] == "replay":
        if len(argv) != 6:
            fail(2)
        file_path, a_text, b_text, data_text = \
            argv[2], argv[3], argv[4], argv[5]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        events = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) < 2:
                fail(5)
            t = item[0]
            kind = item[1]
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if type(kind) is not int or kind not in (0, 1):
                fail(5)
            if kind == 0:
                if len(item) != 5:
                    fail(5)
                _, _, u, v, up = item
                if (type(u) is not str or type(v) is not str
                        or (u, v) not in pair_set):
                    fail(5)
                if type(up) is not bool:
                    fail(5)
                events.append((0, t, u, v, up))
            else:
                if len(item) != 6:
                    fail(5)
                _, _, pid, f, s, d = item
                if type(pid) is not str or not 1 <= len(pid) <= 64:
                    fail(5)
                try:
                    pid.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
                if pid in seen_ids:
                    fail(5)
                seen_ids.add(pid)
                if type(f) is not str or not 1 <= len(f) <= 64:
                    fail(5)
                try:
                    f.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
                if (type(s) is not str or type(d) is not str
                        or s not in node_set or d not in node_set):
                    fail(5)
                events.append((1, t, pid, f, s, d))
        result = compute_replay(nodes, links, a, b, events)
    elif argv[1] == "nfail":
        if len(argv) != 7:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        wait_text, data_text = argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        wait = _bounded_int_arg(wait_text)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        events = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) not in (2, 3):
                fail(5)
            t = item[0]
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if len(item) == 3:
                _, node, is_up = item
                if type(node) is not str or node not in node_set:
                    fail(5)
                if type(is_up) is not bool:
                    fail(5)
                events.append((0, t, node, is_up))
            else:
                _, pid = item
                if type(pid) is not str or not 1 <= len(pid) <= 64:
                    fail(5)
                try:
                    pid.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
                if pid in seen_ids:
                    fail(5)
                seen_ids.add(pid)
                events.append((1, t, pid))
        result = compute_nfail(nodes, links, source, destination, wait,
                               events)
    else:
        fail(2)
    # Write raw UTF-8 bytes to the binary stdout buffer: the text layer
    # would apply the locale encoding and newline conversion (e.g. \r\n
    # on Windows), corrupting the required byte-exact output.
    out = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.buffer.write(out.encode("utf-8") + b"\n")


if __name__ == "__main__":
    main()
