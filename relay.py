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
       python relay.py audit FILE A B DATA
       python relay.py drill FILE A B EVENTS DATA
       python relay.py multidrill FILE A B EVENTS DATA
       python relay.py convstat FILE A B EVENTS DATA
       python relay.py slosum FILE A B W EVENTS DATA
       python relay.py sloeval FILE A B W POLICY EVENTS DATA
       python relay.py slocmp FILE A B W OLD NEW EVENTS DATA
       python relay.py slogate FILE A B W CUR NEW EVENTS DATA
       python relay.py hotload FILE STATE A B W BASE OP EVENTS DATA
       python relay.py snapshot STATE OP
       python relay.py config PACK OP
       python relay.py nfail FILE S D W DATA
       python relay.py lfail FILE S D W DATA
       python relay.py impair FILE S D DATA

Exit codes: 2 bad args/subcommand, 3 file unreadable (FILE or STATE),
4 JSON syntax
(for forward also duplicate keys or non-finite numbers in FILE/TABLE,
for queue/reorder/converge/policy/reserve/rebalance also those in
FILE/DATA/EVENTS/RULES, for quality/replay/nfail/lfail/impair/audit
those in DATA, for drill/multidrill/convstat/slosum those in
EVENTS/DATA, for sloeval those in POLICY/EVENTS/DATA, for slocmp
those in OLD/NEW/EVENTS/DATA, for slogate those in
CUR/NEW/EVENTS/DATA, for hotload those in STATE/OP/EVENTS/DATA, for
snapshot those in STATE/OP/IN, for config those in PACK/OP/IN),
5 FLOW/ORDER/DELAY/EVENTS/LIMIT/TABLE/CAP/STEP/BASE/WINDOW/DATA/D/R/
P/C/RULES/A/B/W/POLICY/OLD/CUR/NEW/STATE/OP/schema/topology/
unknown-node/overflow/re-failure error; for hotload code 5 also covers
a STATE whose v/p/h structure, version continuity, or version conflict
is invalid; for snapshot code 5 also covers an invalid OP shape, path,
or BASE, a STATE/IN whose v/p/h structure, key order, or version
continuity is invalid, and a BASE that conflicts with the current v;
for config code 5 also covers an invalid OP shape, path, or BASE, a
PACK/IN whose v/t/p/h structure, key order, topology, version
continuity, or last-entry match is invalid, and a BASE that conflicts
with the current v; for config op 3 code 5 also covers an invalid TS or
Q, a TS version absent from h, a Q endpoint absent from the current t,
and a rollback write whose BASE conflicts with v or whose v is already
MAX_COST; for config op 4 code 5 also covers an invalid LOG shape or
record, a record t/p that is not a valid topology/policy, a BASE absent
from h, a broken seq/pre chain, a gap or duplicate in the appended
versions, an h[seq] conflict on a reused version, and a new version
that would overflow MAX_COST; config op 6 reuses op 4's exact code 5
checks as a read-only preview that never writes; config op 7 reuses
the same checks as a read-only diff audit that never writes;
config op 8 code 5 also covers a mode outside 0/1, an out-of-range
b/e, an invalid event t/p, a b that conflicts with the current v, and
a new version that would overflow MAX_COST; config op 9 code 5 also
covers a mode outside 0/1, an out-of-range b/e/r, an r absent from h,
a b that conflicts with the current v, and a new version that would
overflow MAX_COST; for config op 5 code 5
also covers an invalid F/T or OUT path and an F/T interval outside
0..v; config op 10 code 5 also covers a mode outside 0/1, an
out-of-range B/e/r/o/n, a non-boolean a, an O that is not a non-empty
path (m=0) or not null (m=1), a B absent from h, a decreasing e, a
broken o chain, an r above o, an n/a pair violating the
target-equality rule, a commit reference missing from h or
conflicting with it, and a new version that would overflow MAX_COST.
On failure stdout stays empty and stderr is exactly {"error":N} plus a
newline. A hotload rejection (s=1) is not a failure: it exits 0, leaves
STATE untouched, and reports the slogate gate codes in why.
"""

import hashlib
import json
import math
import os
import sys
from bisect import bisect_left, bisect_right
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

    return _validate_topology(data, metrics)


def _validate_topology(data, metrics=False):
    # Structural checks applied to an already-decoded topology, shared
    # by load_network (FILE mode) and the config pack validator (the t
    # member, which follows metric's FILE mode). With metrics=True the
    # links must also carry bandwidth/latency, as in metric's FILE.
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


def compute_audit(links, a, b, items):
    # Replay audit over the items with a <= t <= b, kept in input order
    # (t is non-decreasing and equal t keeps input order). items hold
    # validated (id, f, t, s, d, path) tuples: s=0 is a delivery with
    # delay d, s=1 is a loss attributed to the path's last edge, s=2 is
    # a no-route loss carrying no delay and no path. Every edge of an
    # s=0/s=1 path counts one traversal on its link. Rates use exactly
    # _format_peak: q = (2x*10^6 + y)//(2y) rendered as q*10^-6 with six
    # fixed decimals, all in integers; a zero denominator is 0.000000.
    index_of = {(link["from"], link["to"]): index
                for index, link in enumerate(links)}
    traversals = [0] * len(links)
    attributed = [0] * len(links)
    total = 0
    delivered = 0
    lost = 0
    noroute = 0
    delays = []
    flow_paths = {}  # f -> paths of its delivered packets, in order
    for _, f, t, s, d, path in items:
        if not a <= t <= b:
            continue
        total += 1
        # A flow seen only through losses is still listed, with c=0.
        flow_paths.setdefault(f, [])
        if s == 0:
            delivered += 1
            delays.append(d)
            flow_paths[f].append(path)
            for x, y in zip(path, path[1:]):
                traversals[index_of[(x, y)]] += 1
        elif s == 1:
            lost += 1
            for x, y in zip(path, path[1:]):
                traversals[index_of[(x, y)]] += 1
            attributed[index_of[(path[-2], path[-1])]] += 1
        else:
            noroute += 1

    rate_den = delivered + lost
    summary = [total, delivered, lost, noroute,
               _format_peak(lost, rate_den) if rate_den else "0.000000"]

    n = delivered
    if n:
        delays.sort()
        # p95 is the ceil(0.95*n)-th smallest, as a 1-based index.
        delay = [n, _format_peak(sum(delays), n),
                 delays[(95 * n + 99) // 100 - 1]]
    else:
        delay = [0, None, None]

    link_rows = [[link["from"], link["to"], traversals[i], attributed[i],
                  _format_peak(attributed[i], traversals[i])
                  if traversals[i] else "0.000000"]
                 for i, link in enumerate(links)]

    reroutes = [[f, sum(1 for x, y in zip(paths, paths[1:]) if x != y)]
                for f, paths in sorted(flow_paths.items())]

    return {"start": a, "end": b, "summary": summary, "delay": delay,
            "links": link_rows, "reroutes": reroutes}


def compute_drill(links, a, b, events, items):
    # Failure-window drill. Nodes start up and every link takes FILE's up
    # flag; events are applied in order (t non-decreasing, equal t kept in
    # order) and atomically, with repeated setting idempotent. The first
    # real down opens one failure period; it closes at the tick on which
    # every object that was ever down is back up. Any real down after the
    # close is a second failure and exits 5. Records with a <= t <= b are
    # bucketed before/during/after relative to that one period: equal-tick
    # events are all applied before a record at the same tick, so the
    # start tick is "during" and the end tick is "after". With no failure
    # every record is "before"; an unrecovered period leaves "after" empty.
    node_up = {}
    link_up = {(link["from"], link["to"]): link["up"] for link in links}
    down_nodes = set()       # nodes down right now
    down_links = set()       # links down right now
    ever_nodes = set()       # nodes down at least once during the period
    ever_links = set()       # links down at least once during the period
    failure_start = None
    failure_end = None

    for t, kind, *rest in events:
        if kind == 0:
            node, up = rest
            current = node_up.get(node, True)
            if current == up:
                continue
            node_up[node] = up
            if up:
                down_nodes.discard(node)
            else:
                if failure_end is not None:
                    fail(5)
                if failure_start is None:
                    failure_start = t
                down_nodes.add(node)
                ever_nodes.add(node)
        else:
            u, v, up = rest
            pair = (u, v)
            current = link_up[pair]
            if current == up:
                continue
            link_up[pair] = up
            if up:
                down_links.discard(pair)
            else:
                if failure_end is not None:
                    fail(5)
                if failure_start is None:
                    failure_start = t
                down_links.add(pair)
                ever_links.add(pair)
        # An event batch closes the period at its own tick once every
        # object ever down is back up; events share the tick in order.
        if (failure_start is not None and failure_end is None
                and not down_nodes and not down_links):
            failure_end = t

    buckets = [[], [], []]
    for item in items:
        t = item[2]
        if not a <= t <= b:
            continue
        if failure_start is None or t < failure_start:
            phase = 0
        elif failure_end is None or t < failure_end:
            phase = 1
        else:
            phase = 2
        buckets[phase].append(item)

    def phase_stats(records):
        # [N, D, X, F(D,N), F(X,N), p95]: D is the audit status-0 count
        # and X the status-1/2 count; both rates use _format_peak with N
        # as the denominator, and N == 0 gives 0.000000. p95 is the
        # ceil(0.95*D)-th smallest delivered delay (1-based), null at 0.
        delivered = 0
        other = 0
        delays = []
        for _, _, _, s, d, _ in records:
            if s == 0:
                delivered += 1
                delays.append(d)
            else:
                other += 1
        total = delivered + other
        if total:
            f_delivered = _format_peak(delivered, total)
            f_other = _format_peak(other, total)
        else:
            f_delivered = f_other = "0.000000"
        if delivered:
            delays.sort()
            p95 = delays[(95 * delivered + 99) // 100 - 1]
        else:
            p95 = None
        return [total, delivered, other, f_delivered, f_other, p95]

    p = [phase_stats(buckets[0]), phase_stats(buckets[1]),
         phase_stats(buckets[2])]

    # An affected edge started up in FILE and was itself down or has at
    # least one endpoint that was ever down, listed in FILE order.
    affected = []
    for link in links:
        pair = (link["from"], link["to"])
        if (link["up"]
                and (pair in ever_links
                     or link["from"] in ever_nodes
                     or link["to"] in ever_nodes)):
            affected.append([link["from"], link["to"]])

    if failure_start is None:
        f = None
        r = [None, None]
    elif failure_end is None:
        f = failure_start
        r = [None, None]
    else:
        f = failure_start
        r = [failure_end, failure_end - failure_start]

    return {"a": a, "b": b, "f": f, "r": r, "p": p, "l": affected}


def compute_multidrill(links, a, b, events, items):
    # Multi-period failure drill, generalising compute_drill. Nodes start
    # up and every link takes FILE's up flag; events apply in order (t
    # non-decreasing, equal t kept in order), repeated setting idempotent.
    # The first real down opens a period; the period closes on the tick at
    # which the nodes and links currently down are all back up (only down
    # objects still outstanding matter, so an object recovered early never
    # delays the close). A real down after a close opens another period; a
    # close and a reopen may share a tick, objects may recur across
    # periods, and the last period may stay open.
    node_up = {}
    link_up = {(link["from"], link["to"]): link["up"] for link in links}
    periods = []
    current = None  # [start, end, down_nodes, down_links,
                    #  ever_nodes, ever_links] while open

    for t, kind, *rest in events:
        if kind == 0:
            node, up = rest
            current_before = node_up.get(node, True)
            if current_before == up:
                continue
            node_up[node] = up
            if up:
                if current is not None:
                    current[2].discard(node)
            else:
                if current is None:
                    current = [t, None, set(), set(), set(), set()]
                    periods.append(current)
                current[2].add(node)
                current[4].add(node)
        else:
            u, v, up = rest
            pair = (u, v)
            current_before = link_up[pair]
            if current_before == up:
                continue
            link_up[pair] = up
            if up:
                if current is not None:
                    current[3].discard(pair)
            else:
                if current is None:
                    current = [t, None, set(), set(), set(), set()]
                    periods.append(current)
                current[3].add(pair)
                current[5].add(pair)
        # The period closes on the tick its current down set empties; a
        # later event at the same tick may reopen a fresh period.
        if current is not None and not current[2] and not current[3]:
            current[1] = t
            current = None

    if not periods:
        return {"a": a, "b": b, "periods": []}

    def phase_stats(records):
        # [N, D, X, F(D,N), F(X,N), p95], exactly drill's per-phase stats:
        # D is the audit status-0 count and X the status-1/2 count; both
        # rates use _format_peak with N as the denominator, and N == 0
        # gives 0.000000. p95 is the ceil(0.95*D)-th smallest delivered
        # delay (1-based), null at 0.
        delivered = 0
        other = 0
        delays = []
        for _, _, _, s, d, _ in records:
            if s == 0:
                delivered += 1
                delays.append(d)
            else:
                other += 1
        total = delivered + other
        if total:
            f_delivered = _format_peak(delivered, total)
            f_other = _format_peak(other, total)
        else:
            f_delivered = f_other = "0.000000"
        if delivered:
            delays.sort()
            p95 = delays[(95 * delivered + 99) // 100 - 1]
        else:
            p95 = None
        return [total, delivered, other, f_delivered, f_other, p95]

    out_periods = []
    for start, end, _down_nodes, _down_links, ever_nodes, ever_links \
            in periods:
        # Records bucket t < start (before), start <= t < end (during),
        # t >= end (after); equal-tick events precede a record at that
        # tick, so the start tick is "during" and the end tick is "after".
        # An open period has an empty after phase.
        buckets = [[], [], []]
        for item in items:
            t = item[2]
            if not a <= t <= b:
                continue
            if t < start:
                phase = 0
            elif end is None or t < end:
                phase = 1
            else:
                phase = 2
            buckets[phase].append(item)
        stats = [phase_stats(buckets[0]), phase_stats(buckets[1]),
                 phase_stats(buckets[2])]

        # An affected edge started up in FILE and, during this period, was
        # itself down or had at least one endpoint ever down, in FILE
        # order.
        affected = []
        for link in links:
            if (link["up"]
                    and ((link["from"], link["to"]) in ever_links
                         or link["from"] in ever_nodes
                         or link["to"] in ever_nodes)):
                affected.append([link["from"], link["to"]])

        out_periods.append([start,
                            None if end is None else end,
                            None if end is None else end - start,
                            stats, affected])

    return {"a": a, "b": b, "periods": out_periods}


def compute_convstat(links, node_set, pair_set, a, b, events, data):
    # Convergence correlation over multidrill failure periods. Periods
    # open and close exactly as in compute_multidrill: nodes start up,
    # links take FILE's up flag, events apply in order (t non-decreasing,
    # equal t kept in order) with repeated setting idempotent, a period
    # closes on the tick its current down set empties, and a close and a
    # reopen may share a tick. Each record (t, f, path) reports flow f's
    # path at tick t, [] meaning unreachable. A record inside a period's
    # [start, end) window ([start, b] while the period is still open)
    # affects its flow when the path is empty or differs from the flow's
    # previous record, except that a flow's first non-empty path never
    # affects. For a closed period, r is the earliest moment in
    # [end, U) — U the next period's start, b + 1 for the last one — at
    # which every affected flow's latest path is non-empty, r = end when
    # that already holds at end; r and d stay null with no affected
    # flows, an open period, or no timely recovery, else d = r - start.
    # c counts adjacent path changes of the affected flows within
    # [start, r], or within [start, U) when r is null.
    node_up = {}
    link_up = {(link["from"], link["to"]): link["up"] for link in links}
    periods = []  # [start, end_or_None] in opening order
    down_nodes = set()
    down_links = set()
    for t, kind, *rest in events:
        if kind == 0:
            node, up = rest
            if node_up.get(node, True) == up:
                continue
            node_up[node] = up
            if up:
                down_nodes.discard(node)
            else:
                if not periods or periods[-1][1] is not None:
                    periods.append([t, None])
                down_nodes.add(node)
        else:
            u, v, up = rest
            pair = (u, v)
            if link_up[pair] == up:
                continue
            link_up[pair] = up
            if up:
                down_links.discard(pair)
            else:
                if not periods or periods[-1][1] is not None:
                    periods.append([t, None])
                down_links.add(pair)
        # The period closes on the tick its current down set empties; a
        # later event at the same tick may reopen a fresh period.
        if (periods and periods[-1][1] is None
                and not down_nodes and not down_links):
            periods[-1][1] = t

    # Record validation: t is a bounded integer inside [a, b] and
    # non-decreasing, f a 1..64 code point UTF-8 string with at most one
    # record per (t, f), and a non-empty path must be a known simple path
    # whose nodes and links are all up once every event has been applied.
    records = []
    seen_marks = set()
    previous_time = None
    for item in data:
        if not isinstance(item, list) or len(item) != 3:
            fail(5)
        t, f, path = item
        if type(t) is not int or not 0 <= t <= MAX_COST:
            fail(5)
        if not a <= t <= b:
            fail(5)
        if previous_time is not None and t < previous_time:
            fail(5)
        previous_time = t
        if type(f) is not str or not 1 <= len(f) <= 64:
            fail(5)
        try:
            f.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if (t, f) in seen_marks:
            fail(5)
        seen_marks.add((t, f))
        if not isinstance(path, list):
            fail(5)
        if path:
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
                if not node_up.get(node, True):
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for x, y in zip(path, path[1:]):
                if (x, y) not in pair_set:
                    fail(5)
                if not link_up[(x, y)]:
                    fail(5)
        records.append((t, f, path))

    # Per-flow history in input (non-decreasing t) order; same-flow
    # same-tick uniqueness makes each flow's ticks strictly increasing.
    flow_times = {}
    flow_paths = {}
    first_nonempty = {}
    for g, (t, f, path) in enumerate(records):
        if f not in flow_times:
            flow_times[f] = []
            flow_paths[f] = []
        flow_times[f].append(t)
        flow_paths[f].append(path)
        if path and f not in first_nonempty:
            first_nonempty[f] = g

    # Single pass over the records marking affected flows. Affecting
    # windows of distinct periods are disjoint, so a period pointer
    # suffices; last_index keeps each flow's previous record globally,
    # including records before the window.
    n_periods = len(periods)
    affected = [set() for _ in periods]
    window_end = [p[1] if p[1] is not None else b + 1 for p in periods]
    last_index = {}
    pidx = 0
    for g, (t, f, path) in enumerate(records):
        while pidx < n_periods and t >= window_end[pidx]:
            pidx += 1
        if pidx < n_periods and periods[pidx][0] <= t:
            prev = last_index.get(f)
            if not path:
                affected[pidx].add(f)
            elif (prev is not None and g != first_nonempty[f]
                    and path != records[prev][2]):
                affected[pidx].add(f)
        last_index[f] = g

    gt = [t for t, _, _ in records]
    out_periods = []
    for i, (start, end) in enumerate(periods):
        flows = affected[i]
        next_u = periods[i + 1][0] if i + 1 < n_periods else b + 1
        r = None
        if end is not None and flows:
            # Latest path per affected flow at the closing tick (records
            # at t == end included); r = end when already all non-empty.
            latest = {}
            empty = 0
            for f in flows:
                j = bisect_right(flow_times[f], end) - 1
                path = flow_paths[f][j] if j >= 0 else []
                latest[f] = path
                if not path:
                    empty += 1
            if empty == 0:
                r = end
            else:
                # Sweep recovery records in (end, U) tick by tick. Only
                # the count of empty-latest affected flows matters and a
                # record changes it by at most one, so the sweep is
                # linear in the records inside the window; recovery
                # windows of distinct periods are disjoint.
                g = bisect_right(gt, end)
                hi = bisect_left(gt, next_u)
                while g < hi and empty:
                    tick = gt[g]
                    while g < hi and gt[g] == tick:
                        _, f, path = records[g]
                        if f in latest:
                            if not latest[f] and path:
                                empty -= 1
                            elif latest[f] and not path:
                                empty += 1
                            latest[f] = path
                        g += 1
                    if empty == 0:
                        r = tick

        # Adjacent path changes of affected flows, both records inside
        # [start, r] when recovered and inside [start, U) otherwise.
        c = 0
        for f in flows:
            ft = flow_times[f]
            lo = bisect_left(ft, start)
            if r is not None:
                hi = bisect_right(ft, r)
            else:
                hi = bisect_left(ft, next_u)
            fp = flow_paths[f]
            for k in range(lo + 1, hi):
                if fp[k] != fp[k - 1]:
                    c += 1

        out_periods.append([start,
                            None if end is None else end,
                            None if r is None else r,
                            None if r is None else r - start,
                            c, sorted(flows)])

    return {"a": a, "b": b, "p": out_periods}


def compute_slosum(links, node_set, pair_set, a, b, width, events, data):
    # Windowed convergence-SLO summary. Periods open and close, records
    # validate, and each period's [start, end, r, d, c, flows] is computed
    # exactly as in compute_convstat (a recovery crossing a window edge
    # still uses every DATA record up to the next period's start or b+1).
    # The closed windows [x, min(b, x+width-1)] tile [a, b] from x = a in
    # steps of width, and each period joins the window its start falls in.
    # Per window: C counts periods with a non-null end, U those of them
    # with r null, O the still-open periods, F the total affected-flow
    # count, S the c sum, and ds summarizes the non-null d values with
    # p50/p95 the ceil(0.50*n)-th / ceil(0.95*n)-th smallest (1-based).
    periods = compute_convstat(links, node_set, pair_set, a, b, events,
                               data)["p"]
    count = (b - a) // width + 1
    buckets = [[] for _ in range(count)]
    for period in periods:
        buckets[(period[0] - a) // width].append(period)
    windows = []
    for i, bucket in enumerate(buckets):
        x = a + i * width
        y = b if x + width - 1 > b else x + width - 1
        closed = 0
        unrecovered = 0
        open_count = 0
        flows_total = 0
        c_total = 0
        delays = []
        for _start, end, r, d, c, flows in bucket:
            if end is None:
                open_count += 1
            else:
                closed += 1
                if r is None:
                    unrecovered += 1
            if d is not None:
                delays.append(d)
            flows_total += len(flows)
            c_total += c
        n = len(delays)
        if n:
            delays.sort()
            ds = [n, delays[0], delays[-1],
                  delays[(n + 1) // 2 - 1],
                  delays[(95 * n + 99) // 100 - 1]]
        else:
            ds = [0, None, None, None, None]
        windows.append([x, y, closed, unrecovered, open_count, ds,
                        flows_total, c_total])
    return {"a": a, "b": b, "width": width, "windows": windows}


def _sloeval_result(summary, policy):
    # Evaluate one policy [u, o, d, f, s, g] against compute_slosum
    # windows: u caps the unrecovered count U, o the still-open count O,
    # d the recovery p95 ds[4], f the affected-flow total F, s the change
    # total S, and g the number of violating windows the budget still
    # tolerates. A window is compliant when every reason list is empty;
    # thresholds are inclusive, so equality never violates. Reason codes,
    # in order: 0 for U > u, 1 for O > o, 2 for a window with periods
    # (C + O > 0) but no recovery delay sample (ds[0] = 0), 3 for
    # ds[0] > 0 with p95 > d, 4 for F > f, 5 for S > s. The excess vector
    # reports q(z) = max(z, 0) of each overshoot, with the p95 slot null
    # when ds[0] = 0. Returns (windows, runs, budget).
    u_lim, o_lim, d_lim, f_lim, s_lim, g = policy
    windows = []
    for x, y, closed, unrecovered, open_count, ds, flows_total, c_total \
            in summary["windows"]:
        reasons = []
        if unrecovered > u_lim:
            reasons.append(0)
        if open_count > o_lim:
            reasons.append(1)
        if closed + open_count > 0 and ds[0] == 0:
            reasons.append(2)
        if ds[0] > 0 and ds[4] > d_lim:
            reasons.append(3)
        if flows_total > f_lim:
            reasons.append(4)
        if c_total > s_lim:
            reasons.append(5)
        excess = [max(unrecovered - u_lim, 0),
                  max(open_count - o_lim, 0),
                  max(ds[4] - d_lim, 0) if ds[0] > 0 else None,
                  max(flows_total - f_lim, 0),
                  max(c_total - s_lim, 0)]
        windows.append([x, y, not reasons, reasons, excess])

    # Maximal runs of adjacent violating windows; the windows tile [a, b]
    # in order, so adjacency is consecutive index.
    runs = []
    violations = 0
    i = 0
    count = len(windows)
    while i < count:
        if windows[i][2]:
            i += 1
            continue
        j = i
        while j + 1 < count and not windows[j + 1][2]:
            j += 1
        runs.append([windows[i][0], windows[j][1], j - i + 1])
        violations += j - i + 1
        i = j + 1

    budget = [g, violations, max(g - violations, 0),
              max(violations - g, 0)]
    return windows, runs, budget


def compute_sloeval(links, node_set, pair_set, a, b, width, policy,
                    events, data):
    # Windowed convergence-SLO evaluation: windows come from
    # compute_slosum and each is checked against the policy exactly as in
    # _sloeval_result.
    summary = compute_slosum(links, node_set, pair_set, a, b, width,
                             events, data)
    windows, runs, budget = _sloeval_result(summary, policy)
    return {"a": a, "b": b, "width": width, "policy": policy,
            "windows": windows, "runs": runs, "budget": budget}


def compute_slocmp(links, node_set, pair_set, a, b, width, old, new,
                   events, data):
    # Side-by-side comparison of two SLO policies over one shared window
    # summary. OLD and NEW each follow sloeval's [u, o, d, f, s, g]
    # contract and are evaluated exactly as in _sloeval_result; every
    # window then reports both verdicts, a transition code t (0 when the
    # ok flags agree, 1 for a true-to-false regression, 2 for a
    # false-to-true improvement), the reason codes NEW adds and removes
    # (ascending), and the per-slot excess delta NEW minus OLD (null when
    # either side is null). runs pairs both maximal violation-run lists
    # with the NEW-minus-OLD differences in run count and violating
    # window count; budget pairs both four-integer budgets with the
    # elementwise difference.
    summary = compute_slosum(links, node_set, pair_set, a, b, width,
                             events, data)
    old_windows, old_runs, old_budget = _sloeval_result(summary, old)
    new_windows, new_runs, new_budget = _sloeval_result(summary, new)

    windows = []
    for old_w, new_w in zip(old_windows, new_windows):
        x, y, old_ok, old_reasons, old_excess = old_w
        _, _, new_ok, new_reasons, new_excess = new_w
        if old_ok == new_ok:
            t = 0
        elif old_ok:
            t = 1
        else:
            t = 2
        add = sorted(set(new_reasons) - set(old_reasons))
        remove = sorted(set(old_reasons) - set(new_reasons))
        delta = [None if o is None or n is None else n - o
                 for o, n in zip(old_excess, new_excess)]
        windows.append([x, y, [old_ok, old_reasons, old_excess],
                        [new_ok, new_reasons, new_excess], t,
                        [add, remove], delta])

    runs = [old_runs, new_runs,
            [len(new_runs) - len(old_runs),
             new_budget[1] - old_budget[1]]]
    budget = [old_budget, new_budget,
              [n - o for o, n in zip(old_budget, new_budget)]]
    return {"a": a, "b": b, "width": width, "old": old, "new": new,
            "windows": windows, "runs": runs, "budget": budget}


def compute_slogate(links, node_set, pair_set, a, b, width, cur, new,
                    events, data):
    # Deterministic atomic gate for an SLO policy change from CUR to NEW.
    # CUR and NEW each follow sloeval's [u, o, d, f, s, g] contract; the
    # windows and budget are byte-for-byte compute_slocmp's under the same
    # inputs, including the per-window add lists and NEW-minus-CUR excess
    # deltas. The change collects ascending, deduplicated rejection codes:
    # 0 when any window's add list is non-empty (NEW violates a window for
    # a reason CUR did not), 1 when any window has a non-null positive
    # excess delta, and 2 when the budget difference's fourth element (the
    # un-tolerated-violating-window overshoot) is positive. Only positive
    # differences reject: a window whose mixed metrics improve somewhere
    # and worsen nowhere passes, and null excess slots never take part in
    # the comparison. An empty code list allows the change, so FINAL is
    # NEW; otherwise FINAL stays CUR. PD is the six-element NEW-minus-CUR
    # policy difference. The gate reports its verdict and changes nothing
    # else; even a rejection exits 0.
    comparison = compute_slocmp(links, node_set, pair_set, a, b, width,
                                cur, new, events, data)
    windows = comparison["windows"]
    budget = comparison["budget"]

    why = set()
    for window in windows:
        # window = [x, y, [CUR...], [NEW...], t, [add, remove], delta].
        if window[5][0]:
            why.add(0)
        if any(d is not None and d > 0 for d in window[6]):
            why.add(1)
    if budget[2][3] > 0:
        why.add(2)
    reasons = sorted(why)

    policy_diff = [n - c for c, n in zip(cur, new)]
    final = new if not reasons else cur
    return {"ok": not reasons, "why": reasons,
            "policy": [cur, new, policy_diff, final],
            "windows": windows, "budget": budget}


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


def compute_nfail(nodes, links, source, destination, wait, items):
    # Node-failure protection switching with a debounced changeover delay.
    # Primary: lowest-cost path in the initial up-graph (every node starts
    # up, up links only), ties going to the node sequence smallest in
    # Unicode code point order (exactly the shortest_paths tie-break).
    # Backup: the same computation after deleting the primary's internal
    # nodes and its directed edges; no primary means no backup. Both are
    # computed once here and never recomputed; node items only flip node
    # up states (repeated setting is idempotent).
    up_links = [link for link in links if link["up"]]
    cost_of, path_of = shortest_paths(nodes, up_links, source)
    primary_path = path_of[destination]
    primary = ((cost_of[destination], primary_path)
               if primary_path is not None else None)
    backup = None
    if primary_path is not None:
        internal = set(primary_path[1:-1])
        removed = set(zip(primary_path, primary_path[1:]))
        bnodes = [n for n in nodes if n not in internal]
        blinks = [link for link in up_links
                  if link["from"] not in internal
                  and link["to"] not in internal
                  and (link["from"], link["to"]) not in removed]
        bcost_of, bpath_of = shortest_paths(bnodes, blinks, source)
        if bpath_of[destination] is not None:
            backup = (bcost_of[destination], bpath_of[destination])

    up_of = {n: True for n in nodes}
    # Down-node counts on each candidate path, kept incrementally so a
    # node flip and the target selection are both O(1).
    primary_nodes = set(primary[1]) if primary is not None else set()
    backup_nodes = set(backup[1]) if backup is not None else set()
    primary_down = 0
    backup_down = 0

    def target():
        # The first all-up of the primary and the backup, else no path.
        if primary is not None and primary_down == 0:
            return primary
        if backup is not None and backup_down == 0:
            return backup
        return None

    active = primary
    timer_start = None
    timer_at = None
    timer_target = None
    switches = []
    packets = []
    i = 0
    n = len(items)
    while i < n or timer_at is not None:
        wakes = []
        if i < n:
            wakes.append(items[i][0])
        if timer_at is not None:
            wakes.append(timer_at)
        now = min(wakes)
        # All items at this tick run in input order before a timer
        # completing on it; a timer due before the next item's tick
        # completes first.
        while i < n and items[i][0] == now:
            item = items[i]
            i += 1
            if len(item) == 3:
                _, node, up = item
                if up_of[node] == up:
                    continue
                up_of[node] = up
                delta = -1 if up else 1
                if node in primary_nodes:
                    primary_down += delta
                if node in backup_nodes:
                    backup_down += delta
                new = target()
                if new != active:
                    # (Re)arm the changeover timer at t+W.
                    timer_start = now
                    timer_at = now + wait
                    timer_target = new
                else:
                    # The active path is already the target: cancel.
                    timer_start = timer_at = timer_target = None
            else:
                _, pid = item
                if not (up_of[source] and up_of[destination]):
                    # An endpoint is down.
                    packets.append([pid, now, 1, None, []])
                elif active is not None and (
                        primary_down if active is primary
                        else backup_down) == 0:
                    packets.append([pid, now, 0, active[0], active[1]])
                else:
                    packets.append([pid, now, 2, None, []])
        if timer_at is not None and timer_at == now:
            active = timer_target
            switches.append([timer_start, now,
                             active[1] if active is not None else []])
            timer_start = timer_at = timer_target = None

    return {"m": [primary[0], primary[1]] if primary is not None
            else [None, []],
            "b": [backup[0], backup[1]] if backup is not None
            else [None, []],
            "s": switches,
            "p": packets}


def compute_lfail(nodes, links, source, destination, wait, items):
    # Link-failure protection switching with a debounced changeover delay.
    # Primary: lowest-cost path in the initial up-graph, ties going to the
    # node sequence smallest in Unicode code point order (exactly the
    # shortest_paths tie-break). Backup: the same computation after
    # deleting the primary's directed edges; no primary means no backup.
    # Both are computed once here and never recomputed; link items only
    # flip link up states (repeated setting is idempotent).
    up_links = [link for link in links if link["up"]]
    cost_of, path_of = shortest_paths(nodes, up_links, source)
    primary_path = path_of[destination]
    primary = ((cost_of[destination], primary_path)
               if primary_path is not None else None)
    backup = None
    if primary_path is not None:
        removed = set(zip(primary_path, primary_path[1:]))
        blinks = [link for link in up_links
                  if (link["from"], link["to"]) not in removed]
        bcost_of, bpath_of = shortest_paths(nodes, blinks, source)
        if bpath_of[destination] is not None:
            backup = (bcost_of[destination], bpath_of[destination])

    state = {(link["from"], link["to"]): link["up"] for link in links}
    # Down-edge counts on each candidate path, kept incrementally so a
    # link flip and the target selection are both O(1). Both paths were
    # computed over up links only, so every edge on them starts up.
    primary_edges = (set(zip(primary[1], primary[1][1:]))
                     if primary is not None else set())
    backup_edges = (set(zip(backup[1], backup[1][1:]))
                    if backup is not None else set())
    primary_down = 0
    backup_down = 0

    def target():
        # The first all-up of the primary and the backup, else no path.
        if primary is not None and primary_down == 0:
            return primary
        if backup is not None and backup_down == 0:
            return backup
        return None

    active = primary
    timer_start = None
    timer_at = None
    timer_target = None
    switches = []
    packets = []
    i = 0
    n = len(items)
    while i < n or timer_at is not None:
        wakes = []
        if i < n:
            wakes.append(items[i][0])
        if timer_at is not None:
            wakes.append(timer_at)
        now = min(wakes)
        # All items at this tick run in input order before a timer
        # completing on it; a timer due before the next item's tick
        # completes first.
        while i < n and items[i][0] == now:
            item = items[i]
            i += 1
            if len(item) == 4:
                _, u, v, up = item
                pair = (u, v)
                if state[pair] == up:
                    continue
                state[pair] = up
                delta = -1 if up else 1
                if pair in primary_edges:
                    primary_down += delta
                if pair in backup_edges:
                    backup_down += delta
                new = target()
                if new != active:
                    # (Re)arm the changeover timer at t+W.
                    timer_start = now
                    timer_at = now + wait
                    timer_target = new
                else:
                    # The active path is already the target: cancel.
                    timer_start = timer_at = timer_target = None
            else:
                _, pid = item
                if active is not None and (
                        primary_down if active is primary
                        else backup_down) == 0:
                    packets.append([pid, now, 0, active[0], active[1]])
                else:
                    packets.append([pid, now, 1, None, []])
        if timer_at is not None and timer_at == now:
            active = timer_target
            switches.append([timer_start, now,
                             active[1] if active is not None else []])
            timer_start = timer_at = timer_target = None

    return {"m": [primary[0], primary[1]] if primary is not None
            else [None, []],
            "b": [backup[0], backup[1]] if backup is not None
            else [None, []],
            "s": switches,
            "p": packets}


def compute_impair(nodes, links, source, destination, items):
    # Impairment replay on a static up-graph. Config items (0, t, u, v,
    # n, j) set the drop modulus n and latency jitter j of the directed
    # link u->v; they never touch its traversal counter, and repeated
    # identical settings are idempotent. Packet items (1, t, pid) are
    # routed at their t over the lowest-cost path in the up-graph, ties
    # going to the node sequence smallest in Unicode code point order
    # (exactly the shortest_paths tie-break). Config items never flip
    # link states, so the up-graph is static and the path is computed
    # once here; each packet then walks it edge by edge, incrementing
    # the edge's counter and accumulating latency+j before judging the
    # drop: a nonzero n drops the packet when the fresh counter value
    # is a multiple of n, and the walk stops at the first such edge.
    _, path_of = shortest_paths(nodes, links, source)
    path = path_of[destination]

    latency_of = {}
    n_of = {}
    j_of = {}
    count_of = {}
    for link in links:
        pair = (link["from"], link["to"])
        latency_of[pair] = link["latency"]
        n_of[pair] = 0
        j_of[pair] = 0
        count_of[pair] = 0

    packets = []
    delivered = 0
    lost = 0
    unreachable = 0
    delay_sum = 0
    for item in items:
        if item[0] == 0:
            _, _, u, v, n, j = item
            pair = (u, v)
            n_of[pair] = n
            j_of[pair] = j
            continue
        _, t, pid = item
        if path is None:
            unreachable += 1
            packets.append([pid, t, 2, None, None, []])
            continue
        delay = 0
        status = 0
        used = path
        for i in range(len(path) - 1):
            pair = (path[i], path[i + 1])
            count_of[pair] += 1
            delay += latency_of[pair] + j_of[pair]
            if t + delay > MAX_TIME:
                fail(5)
            n = n_of[pair]
            if n and count_of[pair] % n == 0:
                # The packet is lost on this edge; later edges are
                # neither counted nor timed.
                status = 1
                used = path[:i + 2]
                break
        if status == 0:
            delivered += 1
            delay_sum += delay
        else:
            lost += 1
        packets.append([pid, t, status, t + delay, delay, used])

    stats = [delivered, lost, unreachable,
             _format_peak(lost, delivered + lost)
             if delivered + lost else "0.000000",
             _format_peak(delay_sum, delivered)
             if delivered else "0.000000"]
    return {"source": source, "destination": destination,
            "packets": packets, "stats": stats}


def _parse_drill_events(raw_events, up_pairs, node_set, a, b):
    # Shared validation for drill/multidrill event lists: t is a bounded
    # integer inside [a, b] and non-decreasing; node events carry a known
    # node plus bool, link events carry an edge that is up in FILE plus
    # bool. A link already down can neither open a failure nor be flipped
    # back. Returns the normalized (t, kind, ...) tuples.
    events = []
    previous_time = None
    for event in raw_events:
        if not isinstance(event, list) or len(event) not in (4, 5):
            fail(5)
        t = event[0]
        kind = event[1]
        if type(t) is not int or not 0 <= t <= MAX_COST:
            fail(5)
        if not a <= t <= b:
            fail(5)
        if previous_time is not None and t < previous_time:
            fail(5)
        previous_time = t
        if type(kind) is not int or kind not in (0, 1):
            fail(5)
        if kind == 0:
            if len(event) != 4:
                fail(5)
            _, _, node, up = event
            if type(node) is not str or node not in node_set:
                fail(5)
            if type(up) is not bool:
                fail(5)
            events.append((t, 0, node, up))
        else:
            if len(event) != 5:
                fail(5)
            _, _, u, v, up = event
            if (type(u) is not str or type(v) is not str
                    or (u, v) not in up_pairs):
                fail(5)
            if type(up) is not bool:
                fail(5)
            events.append((t, 1, u, v, up))
    return events


def _parse_drill_items(data, node_set, pair_set):
    # Shared validation for drill/multidrill records, reusing the audit
    # schema exactly: edges only need to exist in the topology, up or
    # down, since the data is a record of paths already taken. Returns
    # (pid, f, t, s, d, path) tuples in input (non-decreasing t) order.
    items = []
    seen_ids = set()
    previous_time = None
    for item in data:
        if not isinstance(item, list) or len(item) != 6:
            fail(5)
        pid, f, t, s, d, path = item
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
        if type(t) is not int or not 0 <= t <= MAX_COST:
            fail(5)
        if previous_time is not None and t < previous_time:
            fail(5)
        previous_time = t
        if type(s) is not int or s not in (0, 1, 2):
            fail(5)
        if s == 2:
            # A no-route loss carries no delay and no path at all.
            if d is not None or path != []:
                fail(5)
        else:
            if type(d) is not int or not 0 <= d <= MAX_TIME:
                fail(5)
            # A non-empty simple node array walking directed edges
            # (length >= 2 for s=1, so a last edge exists).
            if not isinstance(path, list) or not path:
                fail(5)
            if s == 1 and len(path) < 2:
                fail(5)
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for x, y in zip(path, path[1:]):
                if (x, y) not in pair_set:
                    fail(5)
        items.append((pid, f, t, s, d, path))
    return items


def _is_policy(value):
    # An SLO policy as used by slogate: a six-element list of
    # non-boolean integers in [0, MAX_COST] ([u, o, d, f, s, g]).
    return (isinstance(value, list) and len(value) == 6
            and all(type(x) is int and 0 <= x <= MAX_COST for x in value))


def _load_state(path):
    # Read and strictly decode the hotload state file. JSON syntax
    # errors, duplicate keys, and non-finite numbers are code 4; any
    # read/UTF-8 problem is code 3. Structural/range checks belong to
    # _validate_hotload_state and stay code 5.
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        fail(3)
    except UnicodeDecodeError:
        fail(4)
    try:
        data = json.loads(text, parse_constant=_reject_constant,
                          parse_float=_finite_float,
                          object_pairs_hook=_object_no_dup)
    except (ValueError, RecursionError):
        fail(4)
    return data


def _validate_hotload_state(data):
    # State is {"v": v, "p": p, "h": h} with keys in that order: v is
    # the current version, p the current policy, and h a version-zero
    # continuous history of [version, policy] pairs whose last entry is
    # exactly [v, p]. Returns the normalized (v, p, h).
    if not isinstance(data, dict) or list(data.keys()) != ["v", "p", "h"]:
        fail(5)
    v = data["v"]
    p = data["p"]
    h = data["h"]
    if type(v) is not int or not 0 <= v <= MAX_COST:
        fail(5)
    if not _is_policy(p):
        fail(5)
    if not isinstance(h, list) or len(h) != v + 1:
        fail(5)
    expected_version = 0
    for entry in h:
        if not isinstance(entry, list) or len(entry) != 2:
            fail(5)
        hv, hp = entry
        if type(hv) is not int or hv != expected_version:
            fail(5)
        if not _is_policy(hp):
            fail(5)
        expected_version += 1
    if h[-1][0] != v or h[-1][1] != p:
        fail(5)
    return v, p, [list(entry) for entry in h]


def _validate_config_pack(data):
    # A config pack is {"v": v, "t": t, "p": p, "h": h} with keys in
    # that order: v is the current version, t the current topology
    # (metric's FILE mode), p the current policy (slogate's six-int
    # POLICY), and h a non-empty version-zero continuous history of
    # [version, t, p] triples whose every t/p is valid and whose last
    # entry is exactly [v, t, p]. Returns the normalized (v, t, p, h).
    if not isinstance(data, dict) or list(data.keys()) != ["v", "t", "p", "h"]:
        fail(5)
    v = data["v"]
    t = data["t"]
    p = data["p"]
    h = data["h"]
    if type(v) is not int or not 0 <= v <= MAX_COST:
        fail(5)
    _validate_topology(t, metrics=True)
    if not _is_policy(p):
        fail(5)
    if not isinstance(h, list) or len(h) == 0 or len(h) != v + 1:
        fail(5)
    expected_version = 0
    for entry in h:
        if not isinstance(entry, list) or len(entry) != 3:
            fail(5)
        hv, ht, hp = entry
        if type(hv) is not int or hv != expected_version:
            fail(5)
        _validate_topology(ht, metrics=True)
        if not _is_policy(hp):
            fail(5)
        expected_version += 1
    if h[-1][0] != v or h[-1][1] != t or h[-1][2] != p:
        fail(5)
    return v, t, p, [list(entry) for entry in h]


def _state_payload(state):
    # Canonical on-disk form: top-level key order v,p,h, compact
    # separators, non-ASCII UTF-8, integers in decimal, one trailing LF.
    text = json.dumps(state, ensure_ascii=False,
                      separators=(",", ":")) + "\n"
    return text.encode("utf-8")


def _write_state_atomic(path, state):
    # Replace the state file atomically: serialize, then exclusively
    # create a unique sibling temp file with an incrementing suffix (a
    # collision only retries under the next name), flush+fsync it,
    # os.replace it over the destination, then fsync the directory.
    # Any failure removes only the temp file this call acquired and
    # leaves the destination byte-for-byte untouched.
    payload = _state_payload(state)
    directory = os.path.dirname(os.path.abspath(path))
    suffix = 0
    while True:
        tmp_path = path + ".tmp." + str(suffix)
        try:
            fd = os.open(tmp_path,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError:
            suffix += 1
            continue
        except OSError:
            fail(3)
        break
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except OSError:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        fail(3)


def _config_rollback(pack_path, pack, v, topo, policy, history, base,
                     ts_list, q_pairs):
    # Multi-version safe rollback (config op 3). Every TS version must
    # appear in the history (version-zero continuous over 0..v) and every
    # Q endpoint must be a node of the current topology. For each TS in
    # order, each [s, d] in Q is routed on the current topology and on
    # that version's topology with the route subcommand's lowest-cost
    # path (R = [cost, path], [null, []] when unreachable; a target
    # topology missing an endpoint counts as no route). A version passes
    # when every currently reachable pair stays reachable at no higher
    # cost; the first passing version is selected. No passer is status 2;
    # a selected configuration equal to the current one is status 1 and
    # BASE is ignored; otherwise BASE must equal v with v < MAX_COST, the
    # selected [t, p] is appended to the untruncated history as version
    # v+1 and the pack is replaced atomically (status 0). Runs T*K
    # Dijkstra searches (one per distinct source per trial topology, the
    # current topology's shared across trials), each O(V^2 + E), and
    # keeps the TK trial rows of at most V-node paths: O(TK(V^2 + E) + S)
    # time and O(TKV + S) space with S the total input/output size.
    cur_nodes = topo["nodes"]
    cur_links = topo["links"]
    cur_node_set = set(cur_nodes)
    for ts in ts_list:
        if ts > v:
            fail(5)
    for s, d in q_pairs:
        if s not in cur_node_set or d not in cur_node_set:
            fail(5)

    # Routes on the current topology, computed once per distinct source.
    cur_cost = {}
    cur_path = {}
    for s, _d in q_pairs:
        if s not in cur_cost:
            cur_cost[s], cur_path[s] = shortest_paths(cur_nodes, cur_links,
                                                      s)

    trials = []
    selected = None
    for ts in ts_list:
        target = history[ts][1]
        t_nodes = target["nodes"]
        t_links = target["links"]
        t_node_set = set(t_nodes)
        t_cost = {}
        t_path = {}
        rows = []
        passes = True
        for s, d in q_pairs:
            old_cost = cur_cost[s][d]
            old_r = ([old_cost, cur_path[s][d]] if old_cost is not None
                     else [None, []])
            if s not in t_node_set or d not in t_node_set:
                new_r = [None, []]
            else:
                if s not in t_cost:
                    t_cost[s], t_path[s] = shortest_paths(t_nodes, t_links,
                                                          s)
                new_cost = t_cost[s][d]
                new_r = ([new_cost, t_path[s][d]] if new_cost is not None
                         else [None, []])
            if old_cost is not None \
                    and (new_r[0] is None or new_r[0] > old_cost):
                passes = False
            rows.append([s, d, old_r, new_r])
        trials.append([ts, passes, rows])
        if selected is None and passes:
            selected = ts

    if selected is None:
        return {"op": 3, "status": 2, "selected": None, "trials": trials,
                "config": pack}
    sel_t = history[selected][1]
    sel_p = history[selected][2]
    if sel_t == topo and sel_p == policy:
        # Rolling back to the configuration already current is
        # idempotent; BASE is ignored and nothing is written.
        return {"op": 3, "status": 1, "selected": selected,
                "trials": trials, "config": pack}
    if base != v or v >= MAX_COST:
        fail(5)
    new_pack = {"v": v + 1, "t": sel_t, "p": sel_p,
                "h": history + [[v + 1, sel_t, sel_p]]}
    _write_state_atomic(pack_path, new_pack)
    return {"op": 3, "status": 0, "selected": selected, "trials": trials,
            "config": new_pack}


def _config_replay_sim(pack, v, history, base, log):
    # Shared in-memory replay simulation for config ops 4 and 6. BASE
    # must be a version present in the version-zero continuous history
    # h: the first record's pre is BASE, every seq is pre + 1, and each
    # later pre is the previous seq. A record at seq <= v must equal
    # h[seq] = [seq, t, p] exactly (reused, s=0), and the first record
    # past v must be v+1, after which records append consecutively as
    # [seq, t, p] (s=1), never past MAX_COST. A bad shape or range, a
    # broken chain, a gap, or an h conflict fails with code 5. Nothing
    # is written: the caller decides what to do with the simulated pack.
    # Returns (applied, steps, new_pack); with no new records applied is
    # 0 and new_pack is the current pack. O(S) time and space with S the
    # total input/output size.
    if base > v:
        fail(5)
    new_history = [list(entry) for entry in history]
    steps = []
    applied = 0
    expected_pre = base
    next_new = v + 1
    for record in log:
        if not isinstance(record, list) or len(record) != 4:
            fail(5)
        seq, pre, rec_t, rec_p = record
        if type(seq) is not int or type(pre) is not int \
                or not 0 <= seq <= MAX_COST or not 0 <= pre <= MAX_COST:
            fail(5)
        if pre != expected_pre or seq != pre + 1:
            fail(5)
        _validate_topology(rec_t, metrics=True)
        if not _is_policy(rec_p):
            fail(5)
        if seq <= v:
            if history[seq] != [seq, rec_t, rec_p]:
                fail(5)
            steps.append([seq, pre, 0])
        else:
            if seq != next_new:
                fail(5)
            new_history.append([seq, rec_t, rec_p])
            next_new = seq + 1
            applied += 1
            steps.append([seq, pre, 1])
        expected_pre = seq
    if applied == 0:
        return 0, steps, pack
    new_pack = {"v": v + applied, "t": new_history[-1][1],
                "p": new_history[-1][2], "h": new_history}
    return applied, steps, new_pack


def _config_replay(pack_path, pack, v, history, base, log):
    # Replay a LOG of [seq, pre, t, p] records against the history
    # (config op 4). Validation and simulation are shared with the op 6
    # preview in _config_replay_sim; this wrapper performs the same
    # in-memory pass and, when it adds new records, replaces the pack
    # atomically once (status 0). No new records is status 1
    # (idempotent, no write).
    applied, steps, new_pack = _config_replay_sim(pack, v, history,
                                                  base, log)
    if applied == 0:
        return {"op": 4, "status": 1, "applied": 0, "steps": steps,
                "config": pack}
    _write_state_atomic(pack_path, new_pack)
    return {"op": 4, "status": 0, "applied": applied, "steps": steps,
            "config": new_pack}


def _config_preview(pack, v, history, base, log):
    # Read-only replay preview (config op 6). Runs exactly the op 4
    # validation and in-memory simulation via _config_replay_sim but
    # never writes PACK, any other file, or a temp file: the returned
    # status/applied/steps/config are precisely what op 4 with the same
    # inputs would produce (its config's v,t,p,h byte-identical), so
    # repeated previews emit the same output while PACK stays untouched.
    # Status 0 when the LOG adds new versions, 1 when all are reused.
    applied, steps, new_pack = _config_replay_sim(pack, v, history,
                                                  base, log)
    if applied == 0:
        return {"op": 6, "status": 1, "applied": 0, "steps": steps,
                "config": pack}
    return {"op": 6, "status": 0, "applied": applied, "steps": steps,
            "config": new_pack}


def _config_state_diff(old_t, new_t, old_p, new_p):
    # Difference between two validated [topology, policy] pairs. Node
    # lists are sorted by Unicode code point; edge lists by their
    # (from, to) endpoint pair in code point order. Added/removed edges
    # carry [from, to, cost, up, bandwidth, latency]; a changed edge
    # carries [from, to, old, new] with old/new the [cost, up,
    # bandwidth, latency] vectors. The policy delta is the elementwise
    # new-minus-old six-integer array. O(S) with S the input size.
    old_nodes = set(old_t["nodes"])
    new_nodes = set(new_t["nodes"])
    n = [sorted(new_nodes - old_nodes), sorted(old_nodes - new_nodes)]
    old_links = {(link["from"], link["to"]): link
                 for link in old_t["links"]}
    new_links = {(link["from"], link["to"]): link
                 for link in new_t["links"]}

    def edge_row(link):
        return [link["from"], link["to"], link["cost"], link["up"],
                link["bandwidth"], link["latency"]]

    added = [edge_row(new_links[pair])
             for pair in sorted(new_links.keys() - old_links.keys())]
    removed = [edge_row(old_links[pair])
               for pair in sorted(old_links.keys() - new_links.keys())]
    changed = []
    for pair in sorted(old_links.keys() & new_links.keys()):
        old_vec = edge_row(old_links[pair])[2:]
        new_vec = edge_row(new_links[pair])[2:]
        if old_vec != new_vec:
            changed.append([pair[0], pair[1], old_vec, new_vec])
    p = [new - old for new, old in zip(new_p, old_p)]
    return n, [added, removed, changed], p


def _config_diff_audit(pack, v, history, base, log):
    # Read-only replay diff audit (config op 7). Runs exactly the op 4
    # validation and in-memory simulation via _config_replay_sim and,
    # like op 6, never writes PACK, any other file, or a temp file.
    # Each LOG-order step is [seq, pre, s, n, l, p]: s marks reuse (0)
    # or a new version (1), and n/l/p diff the pre version's [t, p]
    # against the record's [t, p]. final is [old_v, new_v, n, l, p]
    # diffing the original pack against the simulated result; with no
    # differences n/l are empty arrays and p is six zeros. Status 0
    # when the LOG adds new versions, 1 when all are reused.
    applied, sim_steps, new_pack = _config_replay_sim(pack, v, history,
                                                      base, log)
    sim_history = new_pack["h"]
    steps = []
    for record, sim_step in zip(log, sim_steps):
        seq, pre, s = sim_step
        old_t = sim_history[pre][1]
        old_p = sim_history[pre][2]
        n, l, p = _config_state_diff(old_t, record[2], old_p, record[3])
        steps.append([seq, pre, s, n, l, p])
    n, l, p = _config_state_diff(pack["t"], new_pack["t"],
                                 pack["p"], new_pack["p"])
    final = [v, new_pack["v"], n, l, p]
    return {"op": 7, "status": 0 if applied else 1, "applied": applied,
            "steps": steps, "final": final}


def _config_event_clock(pack_path, pack, v, topo, policy, history, mode,
                        base, event, new_t, new_p):
    # Event-clock configuration transaction (config op 8):
    # [8, m, b, e, t, p]. mode 0 previews in memory only — no file, temp
    # file, or other side effect; mode 1 commits via the same atomic
    # pack replace as the other config ops. A target [t, p] equal to the
    # current topology and policy is idempotent: status 1, b is ignored,
    # nothing is written, and old/new both stay at v. Otherwise b must
    # equal the current v and v must be below MAX_COST (else code 5);
    # the candidate appends [v+1, t, p] to the untruncated history as
    # version v+1. applied is true only for a mode-1 change commit; a
    # preview of the same change differs solely by mode and applied and
    # reports the same candidate config. diff is the [n, l, p] delta of
    # the current [t, p] against the target, in op 7's row structure,
    # code-point ordering, and six-integer policy delta. Committing the
    # same target twice adds no second version. O(S) time and space with
    # S the total input/output size.
    n, l, p_delta = _config_state_diff(topo, new_t, policy, new_p)
    diff = [n, l, p_delta]
    if new_t == topo and new_p == policy:
        return {"op": 8, "mode": mode, "status": 1, "event": event,
                "old": v, "new": v, "applied": False, "diff": diff,
                "config": pack}
    if base != v or v >= MAX_COST:
        fail(5)
    new_pack = {"v": v + 1, "t": new_t, "p": new_p,
                "h": history + [[v + 1, new_t, new_p]]}
    if mode == 1:
        _write_state_atomic(pack_path, new_pack)
        applied = True
    else:
        applied = False
    return {"op": 8, "mode": mode, "status": 0, "event": event,
            "old": v, "new": v + 1, "applied": applied, "diff": diff,
            "config": new_pack}


def _config_rollback_tx(pack_path, pack, v, topo, policy, history, mode,
                        base, event, source):
    # Event-clock rollback transaction (config op 9):
    # [9, m, b, e, r]. It follows op 8's contract exactly, except the
    # target [t, p] is the history entry h[r] (r must be a version present
    # in h) rather than an inline t/p. mode 0 previews in memory only — no
    # file, temp file, or other side effect; mode 1 commits via the same
    # atomic pack replace as the other config ops. A target equal to the
    # current topology and policy is idempotent: status 1, b is ignored,
    # nothing is written, and old/new both stay at v. Otherwise b must
    # equal the current v and v must be below MAX_COST (else code 5); the
    # candidate appends [v+1, t, p] to the untruncated history as version
    # v+1. applied is true only for a mode-1 change commit; a preview of
    # the same change differs solely by mode and applied and reports the
    # same candidate config. diff is the [n, l, p] delta of the current
    # [t, p] against h[r], in op 7's row structure, code-point ordering,
    # and six-integer policy delta. Repeatedly rolling back to the same
    # target adds no second version. O(S) time and space with S the total
    # input/output size.
    if source > v:
        fail(5)
    target = history[source]
    new_t, new_p = target[1], target[2]
    n, l, p_delta = _config_state_diff(topo, new_t, policy, new_p)
    diff = [n, l, p_delta]
    if new_t == topo and new_p == policy:
        return {"op": 9, "mode": mode, "status": 1, "event": event,
                "source": source, "old": v, "new": v, "applied": False,
                "diff": diff, "config": pack}
    if base != v or v >= MAX_COST:
        fail(5)
    new_pack = {"v": v + 1, "t": new_t, "p": new_p,
                "h": history + [[v + 1, new_t, new_p]]}
    if mode == 1:
        _write_state_atomic(pack_path, new_pack)
        applied = True
    else:
        applied = False
    return {"op": 9, "mode": mode, "status": 0, "event": event,
            "source": source, "old": v, "new": v + 1, "applied": applied,
            "diff": diff, "config": new_pack}


def _config_export_log(out_path, v, history, from_v, to_v):
    # Export the replay log for versions from_v+1..to_v (config op 5).
    # The interval must satisfy 0 <= from_v < to_v <= v. LOG is the
    # ascending records [i, i-1, h[i][1], h[i][2]] for i in
    # from_v+1..to_v — exactly the LOG that op 4 with BASE=from_v would
    # replay onto the pack truncated at from_v to rebuild the pack
    # truncated at to_v. PACK is never modified; OUT receives only the
    # LOG array in the canonical byte form via one atomic replace, or
    # nothing when OUT already holds those bytes (status 1). O(S) time
    # and space with S the total input/output size.
    if not from_v < to_v <= v:
        fail(5)
    log = [[i, i - 1, history[i][1], history[i][2]]
           for i in range(from_v + 1, to_v + 1)]
    try:
        with open(out_path, "rb") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = None
    except OSError:
        fail(3)
    if existing == _state_payload(log):
        # OUT already holds the canonical bytes: do not write.
        return {"op": 5, "status": 1, "from": from_v, "to": to_v,
                "count": to_v - from_v, "log": log}
    _write_state_atomic(out_path, log)
    return {"op": 5, "status": 0, "from": from_v, "to": to_v,
            "count": to_v - from_v, "log": log}


def _config_rollback_log(pack_path, pack, v, history, mode, base, log,
                         out_path):
    # Rollback log export/replay (config op 10): [10, m, B, L, O]. L is
    # a non-empty list of [e, r, o, n, a] items: e is a non-decreasing
    # event time, r the source version whose h[r] = [r, t, p] is the
    # rollback target, o the version the item is checked against, n the
    # next version, and a the commit flag. B must be a version present
    # in h; the first item's o is B and every later o is the previous
    # item's n when that item committed (a true) else the previous o;
    # r <= o always. A target equal to h[o]'s [t, p] is a no-op and
    # must carry a=false, n=o; any other target must carry n=o+1 with
    # a=false a precheck and a=true a commit. mode 0 (O a non-empty
    # path) only validates the references — a commit's h[n] must equal
    # the target — and writes L to OUT in the canonical byte form via
    # one atomic replace, or nothing when OUT already holds those bytes
    # (status 1); PACK is never touched. mode 1 (O null) validates the
    # same way, ignores the a=false items, and for each commit either
    # verifies h[n] against the target when n is already in h or
    # appends [n, t, p] consecutively from v+1, replacing PACK
    # atomically once; replaying the same L again only verifies, so
    # repeated replays are idempotent (status 1, no write). steps
    # echoes each item as [e, r, o, n, a, s] with s=1 for an appended
    # version else 0; applied counts the appends. O(S) time and space
    # with S the total input/output size.
    if base > v:
        fail(5)
    sim_history = [list(entry) for entry in history]
    steps = []
    applied = 0
    prev_e = None
    prev_o = None
    prev_n = None
    prev_a = None
    for item in log:
        e, r, o, n, a = item
        if prev_e is not None and e < prev_e:
            fail(5)
        expected_o = base if prev_o is None \
            else (prev_n if prev_a else prev_o)
        if o != expected_o or r > o:
            fail(5)
        target_t, target_p = sim_history[r][1], sim_history[r][2]
        if sim_history[o][1] == target_t and sim_history[o][2] == target_p:
            if a or n != o:
                fail(5)
        elif n != o + 1:
            fail(5)
        s = 0
        if a:
            # A commit: the target must already be h[n] (export always,
            # replay when n is a known version) or append consecutively
            # from v+1 (replay only).
            if n < len(sim_history):
                if sim_history[n][1] != target_t \
                        or sim_history[n][2] != target_p:
                    fail(5)
            elif mode == 1 and n == len(sim_history):
                sim_history.append([n, target_t, target_p])
                applied += 1
                s = 1
            else:
                fail(5)
        steps.append([e, r, o, n, a, s])
        prev_e, prev_o, prev_n, prev_a = e, o, n, a
    if mode == 0:
        try:
            with open(out_path, "rb") as f:
                existing = f.read()
        except FileNotFoundError:
            existing = None
        except OSError:
            fail(3)
        if existing == _state_payload(log):
            # OUT already holds the canonical bytes: do not write.
            return {"op": 10, "status": 1, "applied": 0, "steps": steps,
                    "config": pack}
        _write_state_atomic(out_path, log)
        return {"op": 10, "status": 0, "applied": 0, "steps": steps,
                "config": pack}
    if applied == 0:
        # Every commit verified against h: idempotent, no write.
        return {"op": 10, "status": 1, "applied": 0, "steps": steps,
                "config": pack}
    new_pack = {"v": v + applied, "t": sim_history[-1][1],
                "p": sim_history[-1][2], "h": sim_history}
    _write_state_atomic(pack_path, new_pack)
    return {"op": 10, "status": 0, "applied": applied, "steps": steps,
            "config": new_pack}


def _config_rollback_segments(pack_path, pack, v, history, mode, base,
                              segments, out_path):
    # Segmented rollback log export/replay (config op 11):
    # [11, m, B, G, O]. G is a non-empty list of [b, L, c] segments
    # bracketing op 10 record runs: b is the version the segment's
    # first item is checked against, L a non-empty list of
    # [e, r, o, n, a] items validated exactly as in op 10, and c the
    # segment's closing version — the last item's n when that item
    # committed (a true) else the last item's o. B must be a version
    # present in h; the first segment's b is B and every later b is
    # the previous segment's c, so the o chain restarts at each
    # segment head with o = b; e is non-decreasing across the whole
    # G. mode 0 (O a non-empty path) only validates the references —
    # a commit's h[n] must equal the target, a missing n is code 5 —
    # and writes G to OUT in the canonical byte form via one atomic
    # replace, or nothing when OUT already holds those bytes
    # (status 1); PACK is never touched. mode 1 (O null) validates
    # every segment first, ignores the a=false items, and for each
    # commit either verifies h[n] against the target when n is
    # already in h or appends [n, t, p] consecutively from v+1, then
    # replaces PACK atomically once; a broken chain, an overlap
    # conflict, a corrupt PACK, or a write failure leaves PACK
    # byte-for-byte untouched, and replaying the same G again only
    # verifies, so repeated replays are idempotent (status 1, no
    # write). segments echoes each segment as [b, c, steps] in G
    # order with steps the op 10 [e, r, o, n, a, s] rows (s=1 for an
    # appended version else 0); applied counts the appends. O(S)
    # time and space with S the total input/output size.
    if base > v:
        fail(5)
    sim_history = [list(entry) for entry in history]
    out_segments = []
    applied = 0
    prev_e = None
    prev_c = None
    for segment in segments:
        seg_b, seg_log, seg_c = segment
        if prev_c is None:
            if seg_b != base:
                fail(5)
        elif seg_b != prev_c:
            fail(5)
        steps = []
        prev_o = None
        prev_n = None
        prev_a = None
        for item in seg_log:
            e, r, o, n, a = item
            if prev_e is not None and e < prev_e:
                fail(5)
            expected_o = seg_b if prev_o is None \
                else (prev_n if prev_a else prev_o)
            if o != expected_o or r > o:
                fail(5)
            target_t, target_p = sim_history[r][1], sim_history[r][2]
            if sim_history[o][1] == target_t \
                    and sim_history[o][2] == target_p:
                if a or n != o:
                    fail(5)
            elif n != o + 1:
                fail(5)
            s = 0
            if a:
                # A commit: the target must already be h[n] (export
                # always, replay when n is a known version) or append
                # consecutively from v+1 (replay only).
                if n < len(sim_history):
                    if sim_history[n][1] != target_t \
                            or sim_history[n][2] != target_p:
                        fail(5)
                elif mode == 1 and n == len(sim_history):
                    sim_history.append([n, target_t, target_p])
                    applied += 1
                    s = 1
                else:
                    fail(5)
            steps.append([e, r, o, n, a, s])
            prev_e, prev_o, prev_n, prev_a = e, o, n, a
        if seg_c != (prev_n if prev_a else prev_o):
            fail(5)
        out_segments.append([seg_b, seg_c, steps])
        prev_c = seg_c
    if mode == 0:
        try:
            with open(out_path, "rb") as f:
                existing = f.read()
        except FileNotFoundError:
            existing = None
        except OSError:
            fail(3)
        if existing == _state_payload(segments):
            # OUT already holds the canonical bytes: do not write.
            return {"op": 11, "status": 1, "applied": 0,
                    "segments": out_segments, "config": pack}
        _write_state_atomic(out_path, segments)
        return {"op": 11, "status": 0, "applied": 0,
                "segments": out_segments, "config": pack}
    if applied == 0:
        # Every commit verified against h: idempotent, no write.
        return {"op": 11, "status": 1, "applied": 0,
                "segments": out_segments, "config": pack}
    new_pack = {"v": v + applied, "t": sim_history[-1][1],
                "p": sim_history[-1][2], "h": sim_history}
    _write_state_atomic(pack_path, new_pack)
    return {"op": 11, "status": 0, "applied": applied,
            "segments": out_segments, "config": new_pack}


def _validate_hotload_records(links, events, data, node_set, pair_set, a, b):
    # Stream validation matching slogate's data contract (the record
    # checks inside compute_convstat) without running the windowed gate:
    # apply the normalized events to the final up-graph in O(events),
    # then verify every [t, f, path] record in O(records). Every hotload
    # request validates its inputs before the idempotent/base/gate
    # decision, so a rollback stays O(H + J + P) with no gate compute.
    node_up = {}
    link_up = {(link["from"], link["to"]): link["up"] for link in links}
    for _t, kind, *rest in events:
        if kind == 0:
            node, up = rest
            node_up[node] = up
        else:
            u, v, up = rest
            link_up[(u, v)] = up
    previous_time = None
    seen_marks = set()
    for item in data:
        if not isinstance(item, list) or len(item) != 3:
            fail(5)
        t, f, path = item
        if type(t) is not int or not 0 <= t <= MAX_COST:
            fail(5)
        if not a <= t <= b:
            fail(5)
        if previous_time is not None and t < previous_time:
            fail(5)
        previous_time = t
        if type(f) is not str or not 1 <= len(f) <= 64:
            fail(5)
        try:
            f.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if (t, f) in seen_marks:
            fail(5)
        seen_marks.add((t, f))
        if not isinstance(path, list):
            fail(5)
        if path:
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
                if not node_up.get(node, True):
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for x, y in zip(path, path[1:]):
                if (x, y) not in pair_set:
                    fail(5)
                if not link_up[(x, y)]:
                    fail(5)


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
    elif argv[1] == "audit":
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
        # Edges only need to exist in the topology, up or down: the data
        # is a record of paths already taken.
        pair_set = {(link["from"], link["to"]) for link in links}
        items = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) != 6:
                fail(5)
            pid, f, t, s, d, path = item
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
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if type(s) is not int or s not in (0, 1, 2):
                fail(5)
            if s == 2:
                # A no-route loss carries no delay and no path at all.
                if d is not None or path != []:
                    fail(5)
            else:
                if type(d) is not int or not 0 <= d <= MAX_TIME:
                    fail(5)
                # A non-empty simple node array walking directed edges
                # (length >= 2 for s=1, so a last edge exists).
                if not isinstance(path, list) or not path:
                    fail(5)
                if s == 1 and len(path) < 2:
                    fail(5)
                for node in path:
                    if type(node) is not str or node not in node_set:
                        fail(5)
                if len(set(path)) != len(path):
                    fail(5)
                for x, y in zip(path, path[1:]):
                    if (x, y) not in pair_set:
                        fail(5)
            items.append((pid, f, t, s, d, path))
        result = compute_audit(links, a, b, items)
    elif argv[1] == "drill":
        if len(argv) != 7:
            fail(2)
        file_path, a_text, b_text, events_text, data_text = \
            argv[2], argv[3], argv[4], argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        try:
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        # A link event may target only an edge that is up in FILE; a link
        # already down can neither open a failure nor be flipped back.
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        events = []
        previous_time = None
        for event in raw_events:
            if not isinstance(event, list) or len(event) not in (4, 5):
                fail(5)
            t = event[0]
            kind = event[1]
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if not a <= t <= b:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if type(kind) is not int or kind not in (0, 1):
                fail(5)
            if kind == 0:
                if len(event) != 4:
                    fail(5)
                _, _, node, up = event
                if type(node) is not str or node not in node_set:
                    fail(5)
                if type(up) is not bool:
                    fail(5)
                events.append((t, 0, node, up))
            else:
                if len(event) != 5:
                    fail(5)
                _, _, u, v, up = event
                if (type(u) is not str or type(v) is not str
                        or (u, v) not in up_pairs):
                    fail(5)
                if type(up) is not bool:
                    fail(5)
                events.append((t, 1, u, v, up))
        # Records reuse the audit schema exactly: edges only need to exist
        # in the topology, up or down, since the data is a record of paths
        # already taken.
        pair_set = {(link["from"], link["to"]) for link in links}
        items = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) != 6:
                fail(5)
            pid, f, t, s, d, path = item
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
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if type(s) is not int or s not in (0, 1, 2):
                fail(5)
            if s == 2:
                # A no-route loss carries no delay and no path at all.
                if d is not None or path != []:
                    fail(5)
            else:
                if type(d) is not int or not 0 <= d <= MAX_TIME:
                    fail(5)
                # A non-empty simple node array walking directed edges
                # (length >= 2 for s=1, so a last edge exists).
                if not isinstance(path, list) or not path:
                    fail(5)
                if s == 1 and len(path) < 2:
                    fail(5)
                for node in path:
                    if type(node) is not str or node not in node_set:
                        fail(5)
                if len(set(path)) != len(path):
                    fail(5)
                for x, y in zip(path, path[1:]):
                    if (x, y) not in pair_set:
                        fail(5)
            items.append((pid, f, t, s, d, path))
        result = compute_drill(links, a, b, events, items)
    elif argv[1] == "multidrill":
        if len(argv) != 7:
            fail(2)
        file_path, a_text, b_text, events_text, data_text = \
            argv[2], argv[3], argv[4], argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        try:
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        items = _parse_drill_items(data, node_set, pair_set)
        result = compute_multidrill(links, a, b, events, items)
    elif argv[1] == "convstat":
        if len(argv) != 7:
            fail(2)
        file_path, a_text, b_text, events_text, data_text = \
            argv[2], argv[3], argv[4], argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        try:
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        result = compute_convstat(links, node_set, pair_set, a, b,
                                  events, data)
    elif argv[1] == "slosum":
        if len(argv) != 8:
            fail(2)
        file_path, a_text, b_text, width_text, events_text, data_text = \
            argv[2], argv[3], argv[4], argv[5], argv[6], argv[7]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        width = _bounded_int_arg(width_text)
        if width < 1:
            fail(5)
        try:
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        result = compute_slosum(links, node_set, pair_set, a, b, width,
                                events, data)
    elif argv[1] == "sloeval":
        if len(argv) != 9:
            fail(2)
        file_path, a_text, b_text, width_text, policy_text, events_text, \
            data_text = (argv[2], argv[3], argv[4], argv[5], argv[6],
                         argv[7], argv[8])
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        width = _bounded_int_arg(width_text)
        if width < 1:
            fail(5)
        try:
            policy = json.loads(policy_text, parse_constant=_reject_constant,
                                parse_float=_finite_float,
                                object_pairs_hook=_object_no_dup)
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        # POLICY is [u, o, d, f, s, g], six non-boolean integers in
        # [0, MAX_COST].
        if not isinstance(policy, list) or len(policy) != 6:
            fail(5)
        for value in policy:
            if type(value) is not int or not 0 <= value <= MAX_COST:
                fail(5)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        result = compute_sloeval(links, node_set, pair_set, a, b, width,
                                 policy, events, data)
    elif argv[1] == "slocmp":
        if len(argv) != 10:
            fail(2)
        file_path, a_text, b_text, width_text, old_text, new_text, \
            events_text, data_text = (argv[2], argv[3], argv[4], argv[5],
                                      argv[6], argv[7], argv[8], argv[9])
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        width = _bounded_int_arg(width_text)
        if width < 1:
            fail(5)
        try:
            old = json.loads(old_text, parse_constant=_reject_constant,
                             parse_float=_finite_float,
                             object_pairs_hook=_object_no_dup)
            new = json.loads(new_text, parse_constant=_reject_constant,
                             parse_float=_finite_float,
                             object_pairs_hook=_object_no_dup)
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        # OLD and NEW each follow sloeval's POLICY contract: [u, o, d, f,
        # s, g], six non-boolean integers in [0, MAX_COST].
        for policy in (old, new):
            if not isinstance(policy, list) or len(policy) != 6:
                fail(5)
            for value in policy:
                if type(value) is not int or not 0 <= value <= MAX_COST:
                    fail(5)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        result = compute_slocmp(links, node_set, pair_set, a, b, width,
                                old, new, events, data)
    elif argv[1] == "slogate":
        if len(argv) != 10:
            fail(2)
        file_path, a_text, b_text, width_text, cur_text, new_text, \
            events_text, data_text = (argv[2], argv[3], argv[4], argv[5],
                                      argv[6], argv[7], argv[8], argv[9])
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        width = _bounded_int_arg(width_text)
        if width < 1:
            fail(5)
        try:
            cur = json.loads(cur_text, parse_constant=_reject_constant,
                             parse_float=_finite_float,
                             object_pairs_hook=_object_no_dup)
            new = json.loads(new_text, parse_constant=_reject_constant,
                             parse_float=_finite_float,
                             object_pairs_hook=_object_no_dup)
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        # CUR and NEW each follow sloeval's POLICY contract: [u, o, d, f,
        # s, g], six non-boolean integers in [0, MAX_COST].
        for policy in (cur, new):
            if not isinstance(policy, list) or len(policy) != 6:
                fail(5)
            for value in policy:
                if type(value) is not int or not 0 <= value <= MAX_COST:
                    fail(5)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        result = compute_slogate(links, node_set, pair_set, a, b, width,
                                 cur, new, events, data)
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
        items = []
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
                _, n, up = item
                if type(n) is not str or n not in node_set:
                    fail(5)
                if type(up) is not bool:
                    fail(5)
                items.append((t, n, up))
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
                items.append((t, pid))
        result = compute_nfail(nodes, links, source, destination,
                               wait, items)
    elif argv[1] == "lfail":
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
        pair_set = {(link["from"], link["to"]) for link in links}
        items = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) not in (2, 4):
                fail(5)
            t = item[0]
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if len(item) == 4:
                _, u, v, up = item
                if (type(u) is not str or type(v) is not str
                        or (u, v) not in pair_set):
                    fail(5)
                if type(up) is not bool:
                    fail(5)
                items.append((t, u, v, up))
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
                items.append((t, pid))
        result = compute_lfail(nodes, links, source, destination,
                               wait, items)
    elif argv[1] == "impair":
        if len(argv) != 6:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        data_text = argv[5]
        nodes, links, node_set = load_network(file_path, metrics=True)
        if (source not in node_set or destination not in node_set
                or source == destination):
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
        latency_of = {(link["from"], link["to"]): link["latency"]
                      for link in links}
        items = []
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
                if len(item) != 6:
                    fail(5)
                _, _, u, v, n, j = item
                if (type(u) is not str or type(v) is not str
                        or (u, v) not in pair_set):
                    fail(5)
                if type(n) is not int or not 0 <= n <= MAX_COST:
                    fail(5)
                if (type(j) is not int
                        or not 0 <= latency_of[(u, v)] + j <= MAX_COST):
                    fail(5)
                items.append((0, t, u, v, n, j))
            else:
                if len(item) != 3:
                    fail(5)
                _, _, pid = item
                if type(pid) is not str or not 1 <= len(pid) <= 64:
                    fail(5)
                try:
                    pid.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
                if pid in seen_ids:
                    fail(5)
                seen_ids.add(pid)
                items.append((1, t, pid))
        result = compute_impair(nodes, links, source, destination, items)
    elif argv[1] == "hotload":
        if len(argv) != 11:
            fail(2)
        file_path, state_path, a_text, b_text, width_text, base_text, \
            op_text, events_text, data_text = (argv[2], argv[3], argv[4],
                                               argv[5], argv[6], argv[7],
                                               argv[8], argv[9], argv[10])
        # Inputs are validated up front, following slogate's order: both
        # files are read/decoded first (read errors code 3, strict JSON
        # errors code 4), then the integer args, then the inline JSON.
        nodes, links, node_set = load_network(file_path, metrics=True)
        raw_state = _load_state(state_path)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        width = _bounded_int_arg(width_text)
        base = _bounded_int_arg(base_text)
        if a > b or width < 1:
            fail(5)
        try:
            op = json.loads(op_text, parse_constant=_reject_constant,
                            parse_float=_finite_float,
                            object_pairs_hook=_object_no_dup)
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(op, list) or len(op) != 2 or type(op[0]) is not int:
            fail(5)
        kind = op[0]
        if kind not in (0, 1):
            fail(5)
        v, current_policy, history = _validate_hotload_state(raw_state)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        if not isinstance(data, list):
            fail(5)
        _validate_hotload_records(links, events, data, node_set, pair_set,
                                  a, b)

        if kind == 0:
            target_policy = op[1]
            if not _is_policy(target_policy):
                fail(5)
            if target_policy == current_policy:
                # Loading the policy already current is idempotent: no
                # base check, no gate, no new version, no STATE write.
                result = {"s": 2, "v": v, "p": current_policy, "why": []}
            else:
                if base != v:
                    fail(5)
                new_v = v + 1
                if new_v > MAX_COST:
                    fail(5)
                # Reuse the slogate gate with CUR the current policy and
                # NEW the candidate; a rejection writes nothing.
                gate = compute_slogate(links, node_set, pair_set, a, b,
                                       width, current_policy, target_policy,
                                       events, data)
                if gate["why"]:
                    result = {"s": 1, "v": v, "p": current_policy,
                              "why": gate["why"]}
                else:
                    new_history = history + [[new_v, target_policy]]
                    new_state = {"v": new_v, "p": target_policy,
                                 "h": new_history}
                    _write_state_atomic(state_path, new_state)
                    result = {"s": 0, "v": new_v, "p": target_policy,
                              "why": []}
        else:
            target = op[1]
            if type(target) is not int or not 0 <= target <= MAX_COST:
                fail(5)
            if target == v:
                # Rolling back to the current version is idempotent.
                result = {"s": 2, "v": v, "p": current_policy, "why": []}
            else:
                if base != v:
                    fail(5)
                if target >= len(history) or history[target][0] != target:
                    fail(5)
                new_v = v + 1
                if new_v > MAX_COST:
                    fail(5)
                target_policy = history[target][1]
                new_history = history + [[new_v, target_policy]]
                new_state = {"v": new_v, "p": target_policy,
                             "h": new_history}
                _write_state_atomic(state_path, new_state)
                result = {"s": 0, "v": new_v, "p": target_policy, "why": []}
    elif argv[1] == "snapshot":
        if len(argv) != 4:
            fail(2)
        state_path, op_text = argv[2], argv[3]
        # Read/decode STATE first (read errors code 3, strict JSON
        # errors code 4), then parse the inline OP, then check shapes.
        raw_state = _load_state(state_path)
        try:
            op = json.loads(op_text, parse_constant=_reject_constant,
                            parse_float=_finite_float,
                            object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(op, list) or len(op) == 0 \
                or type(op[0]) is not int:
            fail(5)
        kind = op[0]
        if kind == 0:
            # [0, OUT]: export STATE to OUT.
            if len(op) != 2 or type(op[1]) is not str or len(op[1]) == 0:
                fail(5)
            out_path = op[1]
        elif kind == 1:
            # [1, BASE, IN]: import IN into STATE.
            if len(op) != 3 or type(op[1]) is not int \
                    or not 0 <= op[1] <= MAX_COST \
                    or type(op[2]) is not str or len(op[2]) == 0:
                fail(5)
            base, in_path = op[1], op[2]
        elif kind == 2:
            # [2]: audit only, nothing is written.
            if len(op) != 1:
                fail(5)
        else:
            fail(5)
        v, current_policy, history = _validate_hotload_state(raw_state)
        state = {"v": v, "p": current_policy, "h": history}
        if kind == 0:
            try:
                with open(out_path, "rb") as f:
                    existing = f.read()
            except FileNotFoundError:
                existing = None
            except OSError:
                fail(3)
            if existing == _state_payload(state):
                # OUT already holds the canonical bytes: do not write.
                result = {"op": 0, "status": 1, "state": state}
            else:
                _write_state_atomic(out_path, state)
                result = {"op": 0, "status": 0, "state": state}
        elif kind == 1:
            raw_in = _load_state(in_path)
            in_v, in_policy, in_history = _validate_hotload_state(raw_in)
            in_state = {"v": in_v, "p": in_policy, "h": in_history}
            if base != v:
                fail(5)
            if in_state == state:
                # Importing the state already current is idempotent.
                result = {"op": 1, "status": 1, "state": state}
            else:
                _write_state_atomic(state_path, in_state)
                result = {"op": 1, "status": 0, "state": in_state}
        else:
            result = {"op": 2, "status": 2, "state": state}
    elif argv[1] == "config":
        if len(argv) != 4:
            fail(2)
        pack_path, op_text = argv[2], argv[3]
        # Read/decode PACK first (read errors code 3, strict JSON
        # errors code 4), then parse the inline OP, then check shapes.
        raw_pack = _load_state(pack_path)
        try:
            op = json.loads(op_text, parse_constant=_reject_constant,
                            parse_float=_finite_float,
                            object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(op, list) or len(op) == 0 \
                or type(op[0]) is not int:
            fail(5)
        kind = op[0]
        if kind == 0:
            # [0, OUT]: export PACK to OUT.
            if len(op) != 2 or type(op[1]) is not str or len(op[1]) == 0:
                fail(5)
            out_path = op[1]
        elif kind == 1:
            # [1, BASE, IN]: import IN into PACK.
            if len(op) != 3 or type(op[1]) is not int \
                    or not 0 <= op[1] <= MAX_COST \
                    or type(op[2]) is not str or len(op[2]) == 0:
                fail(5)
            base, in_path = op[1], op[2]
        elif kind == 2:
            # [2]: audit only, nothing is written.
            if len(op) != 1:
                fail(5)
        elif kind == 3:
            # [3, BASE, TS, Q]: multi-version safe rollback. BASE is a
            # bounded integer; TS a non-empty list of distinct bounded
            # integers; Q a non-empty list of distinct [s, d] pairs.
            if len(op) != 4 or type(op[1]) is not int \
                    or not 0 <= op[1] <= MAX_COST:
                fail(5)
            base = op[1]
            ts_list = op[2]
            if not isinstance(ts_list, list) or not ts_list:
                fail(5)
            seen_versions = set()
            for ts in ts_list:
                if type(ts) is not int or not 0 <= ts <= MAX_COST \
                        or ts in seen_versions:
                    fail(5)
                seen_versions.add(ts)
            q_pairs = op[3]
            if not isinstance(q_pairs, list) or not q_pairs:
                fail(5)
            seen_queries = set()
            for pair in q_pairs:
                if not isinstance(pair, list) or len(pair) != 2:
                    fail(5)
                s, d = pair
                if type(s) is not str or type(d) is not str \
                        or (s, d) in seen_queries:
                    fail(5)
                seen_queries.add((s, d))
        elif kind == 4 or kind == 6 or kind == 7:
            # [4, BASE, LOG] replay / [6, BASE, LOG] read-only preview /
            # [7, BASE, LOG] read-only diff audit. BASE is a bounded
            # non-boolean integer; LOG a non-empty list of
            # [seq, pre, t, p] records whose seq/pre are bounded
            # non-boolean integers. The chain, topology, policy, and
            # history conflicts are checked after PACK validation in
            # _config_replay_sim. Ops 6 and 7 validate and simulate
            # exactly like op 4 but never write anything.
            if len(op) != 3 or type(op[1]) is not int \
                    or not 0 <= op[1] <= MAX_COST:
                fail(5)
            base = op[1]
            log = op[2]
            if not isinstance(log, list) or not log:
                fail(5)
            for record in log:
                if not isinstance(record, list) or len(record) != 4:
                    fail(5)
                seq, pre = record[0], record[1]
                if type(seq) is not int or type(pre) is not int \
                        or not 0 <= seq <= MAX_COST \
                        or not 0 <= pre <= MAX_COST:
                    fail(5)
        elif kind == 5:
            # [5, F, T, OUT]: export the replay log for versions
            # F+1..T. F and T are bounded non-boolean integers; OUT a
            # non-empty path. The 0 <= F < T <= v interval is checked
            # after PACK validation in _config_export_log.
            if len(op) != 4 or type(op[1]) is not int \
                    or type(op[2]) is not int \
                    or not 0 <= op[1] <= MAX_COST \
                    or not 0 <= op[2] <= MAX_COST \
                    or type(op[3]) is not str or len(op[3]) == 0:
                fail(5)
            from_v, to_v, out_path = op[1], op[2], op[3]
        elif kind == 8:
            # [8, m, b, e, t, p]: event-clock configuration transaction.
            # m is 0 (read-only preview) or 1 (atomic commit); b/e are
            # bounded non-boolean integers (expected version / event
            # time); t follows the metric topology and p the six-integer
            # policy, both validated after PACK validation. The b
            # conflict and MAX_COST overflow are checked in
            # _config_event_clock.
            if len(op) != 6 or type(op[1]) is not int \
                    or op[1] not in (0, 1) \
                    or type(op[2]) is not int \
                    or type(op[3]) is not int \
                    or not 0 <= op[2] <= MAX_COST \
                    or not 0 <= op[3] <= MAX_COST:
                fail(5)
            mode, base, event = op[1], op[2], op[3]
            new_t, new_p = op[4], op[5]
        elif kind == 9:
            # [9, m, b, e, r]: event-clock rollback transaction. m is 0
            # (read-only preview) or 1 (atomic commit); b/e/r are bounded
            # non-boolean integers (expected version, event time, and the
            # source version whose h[r] = [r, t, p] is the rollback
            # target). The r-present-in-h check (r <= v), the b conflict
            # with the current v, and the MAX_COST overflow are checked
            # after PACK validation in _config_rollback_tx.
            if len(op) != 5 or type(op[1]) is not int \
                    or op[1] not in (0, 1) \
                    or type(op[2]) is not int \
                    or type(op[3]) is not int \
                    or type(op[4]) is not int \
                    or not 0 <= op[2] <= MAX_COST \
                    or not 0 <= op[3] <= MAX_COST \
                    or not 0 <= op[4] <= MAX_COST:
                fail(5)
            mode, base, event, source = op[1], op[2], op[3], op[4]
        elif kind == 10:
            # [10, m, B, L, O]: rollback log export (m=0, O a non-empty
            # path) / replay (m=1, O null). m is 0 or 1; B is a bounded
            # non-boolean integer (the base version the first item's o
            # must equal); L a non-empty list of [e, r, o, n, a] items
            # whose e/r/o/n are bounded non-boolean integers and a a
            # boolean. The B-present-in-h check, the non-decreasing e,
            # the o chain, r <= o, the target-equality n/a rule, and
            # the commit reference/append checks run after PACK
            # validation in _config_rollback_log.
            if len(op) != 5 or type(op[1]) is not int \
                    or op[1] not in (0, 1) \
                    or type(op[2]) is not int \
                    or not 0 <= op[2] <= MAX_COST:
                fail(5)
            mode, base = op[1], op[2]
            log = op[3]
            if not isinstance(log, list) or not log:
                fail(5)
            for item in log:
                if not isinstance(item, list) or len(item) != 5:
                    fail(5)
                e, r, o, n, a = item
                if type(e) is not int or type(r) is not int \
                        or type(o) is not int or type(n) is not int \
                        or not 0 <= e <= MAX_COST \
                        or not 0 <= r <= MAX_COST \
                        or not 0 <= o <= MAX_COST \
                        or not 0 <= n <= MAX_COST \
                        or type(a) is not bool:
                    fail(5)
            out_path = op[4]
            if mode == 0:
                if type(out_path) is not str or len(out_path) == 0:
                    fail(5)
            elif out_path is not None:
                fail(5)
        elif kind == 11:
            # [11, m, B, G, O]: segmented rollback log export (m=0, O a
            # non-empty path) / replay (m=1, O null). m is 0 or 1; B is
            # a bounded non-boolean integer (the base version the first
            # segment's b must equal); G a non-empty list of [b, L, c]
            # segments whose b/c are bounded non-boolean integers and L
            # a non-empty list of [e, r, o, n, a] items checked exactly
            # like op 10's. The B-present-in-h check, the b/c segment
            # chain, the per-segment o chain and c closing rule, the
            # non-decreasing e across segments, and the commit
            # reference/append checks run after PACK validation in
            # _config_rollback_segments.
            if len(op) != 5 or type(op[1]) is not int \
                    or op[1] not in (0, 1) \
                    or type(op[2]) is not int \
                    or not 0 <= op[2] <= MAX_COST:
                fail(5)
            mode, base = op[1], op[2]
            segments = op[3]
            if not isinstance(segments, list) or not segments:
                fail(5)
            for segment in segments:
                if not isinstance(segment, list) or len(segment) != 3:
                    fail(5)
                seg_b, seg_log, seg_c = segment
                if type(seg_b) is not int or type(seg_c) is not int \
                        or not 0 <= seg_b <= MAX_COST \
                        or not 0 <= seg_c <= MAX_COST:
                    fail(5)
                if not isinstance(seg_log, list) or not seg_log:
                    fail(5)
                for item in seg_log:
                    if not isinstance(item, list) or len(item) != 5:
                        fail(5)
                    e, r, o, n, a = item
                    if type(e) is not int or type(r) is not int \
                            or type(o) is not int or type(n) is not int \
                            or not 0 <= e <= MAX_COST \
                            or not 0 <= r <= MAX_COST \
                            or not 0 <= o <= MAX_COST \
                            or not 0 <= n <= MAX_COST \
                            or type(a) is not bool:
                        fail(5)
            out_path = op[4]
            if mode == 0:
                if type(out_path) is not str or len(out_path) == 0:
                    fail(5)
            elif out_path is not None:
                fail(5)
        else:
            fail(5)
        v, topo, policy, history = _validate_config_pack(raw_pack)
        pack = {"v": v, "t": topo, "p": policy, "h": history}
        if kind == 8:
            # The event t/p follow the same metric topology and
            # six-integer policy contracts as the pack's own t/p.
            _validate_topology(new_t, metrics=True)
            if not _is_policy(new_p):
                fail(5)
        if kind == 0:
            try:
                with open(out_path, "rb") as f:
                    existing = f.read()
            except FileNotFoundError:
                existing = None
            except OSError:
                fail(3)
            if existing == _state_payload(pack):
                # OUT already holds the canonical bytes: do not write.
                result = {"op": 0, "status": 1, "config": pack}
            else:
                _write_state_atomic(out_path, pack)
                result = {"op": 0, "status": 0, "config": pack}
        elif kind == 1:
            raw_in = _load_state(in_path)
            in_v, in_topo, in_policy, in_history = \
                _validate_config_pack(raw_in)
            in_pack = {"v": in_v, "t": in_topo, "p": in_policy,
                       "h": in_history}
            if base != v:
                fail(5)
            if in_pack == pack:
                # Importing the pack already current is idempotent.
                result = {"op": 1, "status": 1, "config": pack}
            else:
                _write_state_atomic(pack_path, in_pack)
                result = {"op": 1, "status": 0, "config": in_pack}
        elif kind == 2:
            result = {"op": 2, "status": 2, "config": pack}
        elif kind == 3:
            result = _config_rollback(pack_path, pack, v, topo, policy,
                                      history, base, ts_list, q_pairs)
        elif kind == 4:
            result = _config_replay(pack_path, pack, v, history, base, log)
        elif kind == 6:
            result = _config_preview(pack, v, history, base, log)
        elif kind == 7:
            result = _config_diff_audit(pack, v, history, base, log)
        elif kind == 8:
            result = _config_event_clock(pack_path, pack, v, topo, policy,
                                         history, mode, base, event,
                                         new_t, new_p)
        elif kind == 9:
            result = _config_rollback_tx(pack_path, pack, v, topo, policy,
                                         history, mode, base, event, source)
        elif kind == 5:
            result = _config_export_log(out_path, v, history, from_v, to_v)
        elif kind == 10:
            result = _config_rollback_log(pack_path, pack, v, history,
                                          mode, base, log, out_path)
        elif kind == 11:
            result = _config_rollback_segments(pack_path, pack, v,
                                               history, mode, base,
                                               segments, out_path)
    else:
        fail(2)
    # Write raw UTF-8 bytes to the binary stdout buffer: the text layer
    # would apply the locale encoding and newline conversion (e.g. \r\n
    # on Windows), corrupting the required byte-exact output.
    out = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.buffer.write(out.encode("utf-8") + b"\n")


if __name__ == "__main__":
    main()
