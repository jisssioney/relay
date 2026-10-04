import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RELAY = os.path.join(HERE, "relay.py")

P = [0, 0, 0, 0, 0, 0]


def link(frm, to, cost=1, bw=10000, lat=10, up=True):
    return {"from": frm, "to": to, "cost": cost, "bandwidth": bw,
            "latency": lat, "up": up}


def base_topo(c0b=1, c0c=1, c7d=1):
    # n0 -> n4 has two equal-length routes that leave the source by
    # DIFFERENT first hops: [n0,b,n4] and [n0,c,n4]. Raising n0-b
    # pushes the route via c and raising n0-c pushes it back via b, so
    # the source forwarding table really flips between b and c. An
    # isolated n5 -> n6 link carries a flow that never migrates. A
    # second independent diamond n7 -> d/e -> n11 carries f3; raising
    # n7-d pushes f3 via e. At equal cost the full-node-sequence tie
    # break picks b before c (and d before e).
    return {"nodes": ["n0", "b", "c", "n4", "n5", "n6",
                      "n7", "d", "e", "n11"],
            "links": [link("n0", "b", c0b), link("b", "n4"),
                      link("n0", "c", c0c), link("c", "n4"),
                      link("n5", "n6"),
                      link("n7", "d", c7d), link("d", "n11"),
                      link("n7", "e"), link("e", "n11")]}


# tA ties on cost 2 via b/c; tB raises n0-b and n7-d so the c route
# and the e route win; tC raises n0-c instead (still cheap via b),
# leaving f3 on the d route.
T_A = base_topo()
T_B = base_topo(c0b=9, c7d=9)
T_C = base_topo(c0c=9)

P1 = ["n0", "b", "n4"]
P2 = ["n0", "c", "n4"]
P3 = ["n7", "d", "n11"]
P4 = ["n7", "e", "n11"]

# First hops: P1 leaves via b, P2 via c, so a retained P2 then P1
# spans two distinct source table entries {b,c}; the interior transit
# sets are {b} and {c} here as well. f3 flips d to e.

# b failed reroutes tA onto the c route; c failed keeps tA on the b
# route and tB there too, so its window stays empty across the event.
SCENARIOS = [["x", ["b"], []], ["z", ["c"], []]]


def flow(fid="f1", src="n0", dst="n4", demand=1, mlat=1000):
    return [fid, src, dst, demand, mlat]


def pack(topo=None, v=0, history=None):
    topo = topo or T_A
    h = history if history is not None else [[0, topo, P]]
    return {"v": v, "t": topo, "p": P, "h": h}


# f1 (demand 1) is the migrating n0->n4 flow, f2 (demand 999 on
# n5->n6) never moves. Generous defaults except the caller overrides
# J/Z/Y/X.
FLOWS = [flow(), ["f2", "n5", "n6", 999, 1000]]

# Two independently migrating flows on disjoint first-hop sets.
TWO_FLOWS = [flow(), ["f3", "n7", "n11", 1, 1000]]


def op38(events, flows_=None, j=10, z=10, y=10, x=10, w=5, q=10, m=0,
         b=0, h=1000000, u=1000000, n=1000000, l=1000000, c=1000000,
         r=10, d=0, scenarios=None):
    flows_ = FLOWS if flows_ is None else flows_
    return [38, m, b, events, flows_,
            SCENARIOS if scenarios is None else scenarios,
            l, c, r, d, w, q, h, u, n, x, y, z, j]


class Op38(unittest.TestCase):
    def call(self, op_obj, pk=None, expect_rc=0):
        pk = pk if pk is not None else pack()
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pk, f)
            with open(pp, "rb") as fh:
                before = fh.read()
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                json.dumps(op_obj)], capture_output=True,
                               text=True)
            self.assertEqual(r.returncode, expect_rc,
                             "rc=%s err=%s out=%s"
                             % (r.returncode, r.stderr, r.stdout))
            out = json.loads(r.stdout) if r.stdout else None
            with open(pp, "rb") as fh:
                after = fh.read()
            tmps = [name for name in os.listdir(d) if ".tmp." in name]
            return out, before, after, tmps

    def call_raw(self, op_obj, pk=None):
        pk = pk if pk is not None else pack()
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pk, f)
            return subprocess.run([sys.executable, RELAY, "config", pp,
                                   json.dumps(op_obj)], capture_output=True)

    def test_preview_pass_renders_nexthop_fields(self):
        out, before, after, tmps = self.call(op38([[1, T_B, P]], j=10))
        # Top-level key order stays op 37's exactly.
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [38, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 0, 0, 1])
        scenarios = row[4][3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row: op 37's 19-element shape with
        # maxWindowDistinctNextHops inserted after
        # maxWindowDistinctTransitNodes and before pass (20 elements).
        s0 = scenarios[0]
        self.assertEqual(len(s0), 20)
        self.assertEqual(s0[13], 1)             # maxWindowDistinctPaths
        self.assertEqual(s0[14], 2)             # maxWindowDistinctLinks
        self.assertEqual(s0[15], 1)             # maxWindowDistinctTransitNodes
        self.assertEqual(s0[16], 1)             # maxWindowDistinctNextHops
        self.assertIs(s0[17], True)             # pass
        # Flow row gains windowDistinctNextHopCount/
        # nextHopDiversityPass after windowDistinctTransitNodeCount and
        # before transitNodeDiversityPass: 24 elements. P2 leaves n0
        # via the single next hop c.
        f0 = s0[18][0]
        self.assertEqual(len(f0), 24)
        self.assertEqual(f0,
                         ["f1", 2, 2, 20, 20, P1, P2, True, True, 1,
                          None, None, True, -4, 1, True, 1, 2, 1, 1,
                          True, True, True, True])
        # The stationary f2 keeps empty path, link, transit, and
        # next-hop windows.
        self.assertEqual(s0[18][1][14:24],
                         [0, True, 0, 0, 0, 0, True, True, True, True])
        # In x (b failed) f1 already used the c route at tA; in z
        # (c failed) f1 keeps the b route at tB: neither migrates, so
        # all four windows stay empty and the scenarios pass.
        for sx in scenarios[1:]:
            self.assertEqual(sx[15], 0)
            self.assertEqual(sx[16], 0)
            self.assertIs(sx[17], True)
            self.assertEqual(sx[18][0][7], False)
            self.assertEqual(sx[18][0][16:24],
                             [0, 0, 0, 0, True, True, True, True])

    def test_j_zero_rejects_first_retained_hop_keeps_candidate(self):
        out, before, after, tmps = self.call(op38([[1, T_B, P]], j=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[16], 1)
        self.assertFalse(s0[17])
        fr = s0[18][0]
        # Candidate post-event values are retained on the failed row:
        # one distinct next hop, J gate failed, transit/link/path gates
        # still fine with Z/Y/X generous.
        self.assertEqual(fr[18:24], [1, 1, False, True, True, True])
        # Q, N and the windows of non-moving failure scenarios do not
        # fail.
        self.assertEqual(fr[14:18], [1, True, 1, 2])
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[17])
            self.assertEqual(sx[16], 0)

    def test_single_path_boundary(self):
        # One reroute onto c spans one next hop: J = 0 rejects the very
        # first event while J = 1 admits exactly.
        out, before, after, _ = self.call(op38([[1, T_B, P]], j=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[16], 1)
        self.assertFalse(s0[17])
        self.assertEqual(s0[18][0][19:24], [1, False, True, True, True])
        out, _, _, _ = self.call(op38([[1, T_B, P]], j=1))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[16], 1)
        self.assertTrue(s0[17])
        self.assertEqual(s0[18][0][19:24], [1, True, True, True, True])

    def test_two_hops_spanned_across_events(self):
        # tA -> tB -> tA retains P2 (hop c) then P1 (hop b), two
        # distinct source table entries. J = 1 rejects at event 2 while
        # the path gate (X = 2) and link gate (Y = 4) pass; J = 2
        # admits exactly.
        events = [[1, T_B, P], [2, T_A, P]]
        out, before, after, _ = self.call(
            op38(events, w=100, x=2, y=4, z=10, j=1))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[13], 2)             # two distinct paths
        self.assertEqual(s0[14], 4)             # four distinct links
        self.assertEqual(s0[15], 2)             # two distinct transit nodes
        self.assertEqual(s0[16], 2)             # two distinct next hops
        self.assertFalse(s0[17])
        f0 = s0[18][0]
        self.assertEqual(f0[16:24],
                         [2, 4, 2, 2, False, True, True, True])
        out, _, _, _ = self.call(
            op38(events, w=100, x=2, y=4, z=10, j=2))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[13:18], [2, 4, 2, 2, True])
        self.assertEqual(s0[18][0][16:24],
                         [2, 4, 2, 2, True, True, True, True])

    def test_hop_leaves_only_after_last_record_slides_out(self):
        # Records for f1: P2@1 (tB), P1@2 (tA), P2@3 (tB). Event 4 is a
        # non-moving topology change (only the isolated n5->n6 latency
        # changes), so W=1 slides the window to start 3 without
        # appending: P2@1 drops (c still referenced by P2@3), then
        # P1@2 drops (b leaves), leaving exactly the single hop c -
        # neither a never-shrinking seen-set ({b,c}) nor a
        # pop-drops-hop implementation (c would vanish at event 2).
        t_quiet = json.loads(json.dumps(T_B))
        t_quiet["links"][4]["latency"] = 11
        events = [[1, T_B, P], [2, T_A, P], [3, T_B, P],
                  [4, t_quiet, P]]
        out, _, _, _ = self.call(op38(events, w=1, x=2, y=4, z=10, j=5))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 0), (4, 0)])
        s0 = out["events"][3][4][3][0]
        self.assertEqual(s0[16], 1)
        self.assertTrue(s0[17])
        f0 = s0[18][0]
        self.assertEqual(f0[7], False)          # event 4 moved nothing
        self.assertEqual(f0[16:24],
                         [1, 2, 1, 1, True, True, True, True])
        # Right before the slide (event 3) both records coexist on the
        # closed edge: windowStart 2 keeps P1@2 and adds P2@3, so the
        # source table spans both first hops.
        s3 = out["events"][2][4][3][0]
        self.assertEqual(s3[16], 2)
        self.assertEqual(s3[18][0][16:24],
                         [2, 4, 2, 2, True, True, True, True])

    def test_direct_link_next_hop_is_destination(self):
        # A flow rerouting from the two-hop [s,r,d] onto the direct
        # [s,d] link records the empty transit set (Z = 0 admits) but
        # its next hop IS the destination d, so J = 0 rejects: the two
        # gates genuinely diverge on a direct path. Rerouting back then
        # spans the two hops {d,r} while transit touches only {r}.
        def dtop(crd=1):
            return {"nodes": ["s", "r", "d"],
                    "links": [link("s", "d", 9),
                              link("s", "r", 1), link("r", "d", crd)]}

        t0 = dtop(1)
        t1 = dtop(9)
        scn = [["g", ["r"], []]]
        fl = [["g1", "s", "d", 1, 1000]]
        base_pk = pack(t0)
        op_one = [38, 0, 0, [[1, t1, P]], fl, scn,
                  1000000, 1000000, 10, 0, 100, 10, 1000000, 1000000,
                  1000000, 10, 10, 0, 0]
        out, before, after, _ = self.call(op_one, pk=base_pk)
        self.assertEqual(out["status"], 2)
        s0 = out["events"][0][4][3][0]
        f0 = s0[18][0]
        self.assertEqual(f0[5], ["s", "r", "d"])
        self.assertEqual(f0[6], ["s", "d"])
        self.assertIs(f0[7], True)
        # One path, one (directed) link, zero transit nodes, one next
        # hop (d): only the J gate fails.
        self.assertEqual(f0[16:24], [1, 1, 0, 1, False, True, True, True])
        self.assertEqual(s0[13:18], [1, 1, 0, 1, False])
        # J = 1 admits the same event with Z still 0.
        op_j1 = list(op_one)
        op_j1[18] = 1
        out, _, after2, _ = self.call(op_j1, pk=base_pk)
        self.assertEqual(out["status"], 0)
        self.assertEqual(after2, before)       # preview writes nothing
        f0 = out["events"][0][4][3][0][18][0]
        self.assertEqual(f0[16:24], [1, 1, 0, 1, True, True, True, True])
        # The direct record stays in the window; rerouting back via r
        # adds r as a next hop: two hops but one transit node, so with
        # J = Z = 1 only the J gate fails.
        op_two = [38, 0, 0, [[1, t1, P], [2, t0, P]], fl, scn,
                  1000000, 1000000, 10, 0, 100, 10, 1000000, 1000000,
                  1000000, 10, 10, 1, 1]
        out, _, _, _ = self.call(op_two, pk=base_pk)
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[15], 1)
        self.assertEqual(s0[16], 2)
        self.assertFalse(s0[17])
        f0 = s0[18][0]
        self.assertEqual(f0[16:24], [2, 3, 1, 2, False, True, True, True])

    def test_shared_head_counts_one_hop_many_transit_nodes(self):
        # Opposite divergence: routes [n0,a,b,n4]/[n0,a,c,n4] differ
        # only downstream of the shared head a, so one reroute spans
        # two transit nodes {a,c} but a single source entry {a}: J = 1
        # admits while Z = 1 rejects.
        def htop(cab=1, cac=1):
            return {"nodes": ["n0", "a", "b", "c", "n4"],
                    "links": [link("n0", "a"),
                              link("a", "b", cab), link("b", "n4"),
                              link("a", "c", cac), link("c", "n4")]}

        h_a = htop()
        h_b = htop(cab=9)
        hp = pack(h_a)
        fl = [["h1", "n0", "n4", 1, 1000]]
        op_one = [38, 0, 0, [[1, h_b, P]], fl,
                  [["g", ["b"], []]],
                  1000000, 1000000, 10, 0, 100, 10, 1000000, 1000000,
                  1000000, 10, 10, 2, 1]
        out, _, _, _ = self.call(op_one, pk=hp)
        self.assertEqual(out["status"], 0)
        f0 = out["events"][0][4][3][0][18][0]
        # Two transit nodes {a,c}, one next hop a.
        self.assertEqual(f0[18:24], [2, 1, True, True, True, True])
        op_one[17] = 1            # Z = 1
        op_one[18] = 1            # J = 1
        out, _, _, _ = self.call(op_one, pk=hp)
        self.assertEqual(out["status"], 2)
        f0 = out["events"][0][4][3][0][18][0]
        self.assertEqual(f0[18:24], [2, 1, True, False, True, True])

    def test_window_is_closed_when_sliding(self):
        # P2@1 hop c, P1@2 hop b. W=1 starts the window at 1, so clock
        # 1 stays and the source table spans {b,c}: J=1 fails at event
        # 2. (W=0 drops the @1 record, leaving only hop b.)
        out, _, _, _ = self.call(
            op38([[1, T_B, P], [2, T_A, P]], w=1, y=4, j=1))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[16], 2)
        self.assertFalse(s0[17])
        out, _, _, _ = self.call(
            op38([[1, T_B, P], [2, T_A, P]], w=0, y=4, j=1))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[16], 1)
        self.assertTrue(s0[17])

    def test_equal_state_and_unchanged_path_add_no_record(self):
        # Event 1 moves f1 (P1 -> P2). Event 2 is the same t/p: status
        # 1, an empty impact, no record. Event 3 changes only the
        # isolated n5->n6 link latency, so neither flow's complete path
        # changes: the window slides but nothing is appended and f1
        # still shows P2's single next hop c.
        t_quiet = json.loads(json.dumps(T_B))
        t_quiet["links"][4]["latency"] = 11
        out, _, _, _ = self.call(
            op38([[1, T_B, P], [2, T_B, P], [3, t_quiet, P]],
                 w=100, j=2))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 0)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[16], 1)
        self.assertTrue(s0[17])
        f0 = s0[18][0]
        self.assertEqual(f0[7], False)          # not a migration
        self.assertEqual(f0[16:24],
                         [1, 2, 1, 1, True, True, True, True])

    def test_unreachable_migration_adds_no_record(self):
        # The candidate topology removes both n0-branches: f1 is
        # unreachable on the new side, so it is not a reroute, no
        # next-hop record is appended, and the flow's J row keeps the
        # empty candidate count even though the event fails (and the
        # batch stops) on reachability.
        t_dead = {"nodes": T_A["nodes"],
                  "links": [lk for lk in T_A["links"]
                            if (lk["from"], lk["to"])
                            not in (("n0", "b"), ("n0", "c"))]}
        out, before, after, _ = self.call(op38([[1, t_dead, P]], j=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[17])
        f0 = s0[18][0]
        self.assertEqual(f0[6], [])             # unreachable new side
        self.assertIs(f0[7], False)
        self.assertEqual(f0[19], 0)             # no next-hop record
        self.assertIs(f0[20], True)             # J itself does not fail

    def test_scenarios_never_merge(self):
        # The tA -> tB event moves f1 only in the no-failure scenario
        # (P1 -> P2); in x (b failed) f1 was already on P2 and in z
        # (c failed) f1 keeps P1, so their next-hop windows stay empty.
        out, _, _, _ = self.call(op38([[1, T_B, P]], j=0))
        self.assertEqual(out["status"], 2)
        scenarios = out["events"][0][4][3]
        s0, sx, sz = scenarios
        self.assertFalse(s0[17])
        self.assertEqual(s0[18][0][19:24], [1, False, True, True, True])
        for other in (sx, sz):
            self.assertTrue(other[17])
            self.assertEqual(other[16], 0)
            self.assertEqual(other[18][0][19:24],
                             [0, True, True, True, True])

    def test_flows_never_merge(self):
        # f1 moves onto hop c and f3 onto hop e in the same no-failure
        # scenario; per-flow rows keep their own counts and the
        # scenario max is one, not the merged two. J = 1 admits both;
        # J = 0 fails f1 and f3 on their own rows only.
        events = [[1, T_B, P]]
        out, _, _, _ = self.call(
            op38(events, flows_=TWO_FLOWS, j=1))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[16], 1)
        f1, f3 = s0[18]
        self.assertEqual(f1[19:24], [1, True, True, True, True])
        self.assertEqual(f3[19:24], [1, True, True, True, True])
        out, _, _, _ = self.call(
            op38(events, flows_=TWO_FLOWS, j=0))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[17])
        f1, f3 = s0[18]
        self.assertEqual(f1[19:24], [1, False, True, True, True])
        self.assertEqual(f3[19:24], [1, False, True, True, True])

    def test_z_gate_still_rejects_independently(self):
        # J admits the hop c, but Z = 0 rejects the one retained
        # interior transit node c.
        out, before, after, _ = self.call(
            op38([[1, T_B, P]], z=0, j=10))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[17])
        f0 = s0[18][0]
        self.assertEqual(f0[18:24], [1, 1, True, False, True, True])

    def test_y_gate_still_rejects_independently(self):
        # J admits the one hop, but Y = 1 rejects P2's two directed
        # links (n0-c, c-n4).
        out, before, after, _ = self.call(
            op38([[1, T_B, P]], y=1, j=10))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[17])
        f0 = s0[18][0]
        self.assertEqual(f0[17:24], [2, 1, 1, True, True, False, True])

    def test_x_gate_still_rejects_independently(self):
        # J admits both hops ({b,c} is two), but X = 1 rejects the
        # second distinct path.
        out, before, after, _ = self.call(
            op38([[1, T_B, P], [2, T_A, P]], w=100, x=1, y=4, j=10))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][1][4][3][0]
        self.assertFalse(s0[17])
        f0 = s0[18][0]
        self.assertEqual(f0[16:24],
                         [2, 4, 2, 2, True, True, True, False])

    def test_q_gate_still_rejects_independently(self):
        # J admits everything, but Q=0 rejects the first reroute.
        out, before, after, _ = self.call(
            op38([[1, T_B, P]], j=10, q=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[17])
        f0 = s0[18][0]
        self.assertIs(f0[15], False)        # windowPass fails
        # The candidate record is still appended on the failing row
        # (one path, two links, one transit node, one next hop); the
        # diversity gates themselves all read true.
        self.assertEqual(f0[16:24],
                         [1, 2, 1, 1, True, True, True, True])

    def test_n_gate_still_rejects_independently(self):
        # One of two flows affected: N below one half rejects while J
        # admits the touched hop.
        out, before, after, _ = self.call(
            op38([[1, T_B, P]], j=10, n=499999))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[17])
        self.assertEqual(s0[11:17], [1, "0.500000", 1, 2, 1, 1])
        self.assertIs(s0[18][0][20], True)

    def test_commit_resend_and_idempotent(self):
        out, before, after, tmps = self.call(
            op38([[1, T_B, P]], j=10, m=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            op38([[1, T_B, P]], j=10, m=1), pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Equal-state event: status 0, no write even with
        # J=Z=Y=X=Q=N=0.
        out3, _, after3, _ = self.call(
            op38([[2, T_B, P]], j=0, z=0, y=0, x=0, q=0, n=0, m=1,
                 b=1),
            pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(json.loads(after3)["v"], 1)

    def test_failed_batch_does_not_commit(self):
        # Event 1 retains hop c (J=1 admits); event 2 adds hop b and
        # reaches two source entries - fails - mode 1 must leave PACK
        # untouched.
        events = [[1, T_B, P], [2, T_A, P]]
        out, before, after, tmps = self.call(
            op38(events, w=100, y=4, j=1, m=1))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        # A feasible retry (J=2) commits from the same base.
        out2, _, after2, _ = self.call(
            op38(events, w=100, y=4, j=2, m=1))
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_stale_base_conflict_code5(self):
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        other = json.loads(json.dumps(T_A))
        other["links"][4]["latency"] = 7
        self.call(op38([[6, other, P]], j=10, m=1), pk=pk1,
                  expect_rc=5)

    def test_byte_deterministic(self):
        op_obj = op38([[1, T_B, P], [2, T_A, P]], w=100, y=4, j=2)
        r1 = self.call_raw(op_obj)
        r2 = self.call_raw(op_obj)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_shape_and_range_code5(self):
        good = op38([[1, T_B, P]])
        self.assertEqual(len(good), 19)
        bad = [
            # wrong arity: op 37's 18-element shape and one too many
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 12,
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            # op 37 must not accept op 38's nineteen elements, and op
            # 38 must not accept op 37's eighteen
            [37, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 13,
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 11,
            # J negative / boolean / too large / string / float
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True],
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2147483648],
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, "1"],
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5],
            # op 37's Z/Y/X/N/U/H/W/Q/R/D/C/L ranges still enforced
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1],
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True, 1],
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1, 1],
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, True, 1, 1, 1, 1, 1, 1, 1],
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, -1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1000001, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000001, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # bad mode
            [38, 2, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 13,
            # empty E / F / S
            [38, 0, 0, [], FLOWS, SCENARIOS] + [1] * 13,
            [38, 0, 0, [[1, T_B, P]], [], SCENARIOS] + [1] * 13,
            [38, 0, 0, [[1, T_B, P]], FLOWS, []] + [1] * 13,
            # clocks decrease
            [38, 0, 0, [[2, T_B, P], [1, T_B, P]], FLOWS,
             SCENARIOS] + [1] * 13,
            # invalid scenario reference at h[b]
            [38, 0, 0, [[1, T_B, P]], FLOWS,
             [["q", ["n4"], []]]] + [1] * 13,
            # flow endpoint absent at h[b]
            [38, 0, 0, [[1, T_B, P]],
             [["g", "n0", "n9", 1, 1000]], SCENARIOS] + [1] * 13,
        ]
        for op_obj in bad:
            self.call(op_obj, expect_rc=5)
        # J = MAX_COST is accepted.
        self.call(op38([[1, T_B, P]], j=2147483647))

    def test_ops_0_to_37_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        # op 37 happy path keeps its 19-field scenario row and
        # 22-field flow row, with no
        # maxWindowDistinctNextHops/nextHopDiversityPass.
        out, _, _, _ = self.call(
            [37, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10, 10, 10])
        self.assertEqual(out["op"], 37)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(len(s0), 19)
        self.assertEqual(len(s0[17][0]), 22)
        # op 37's 18-arity shape must not parse as op 38, and op 38's
        # 19-arity shape must not parse as op 37.
        self.call(
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10, 10, 10],
            expect_rc=5)
        self.call(
            [37, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10, 10, 10, 10], expect_rc=5)
        # op 36 keeps its 18-field scenario row and 20-field flow row.
        out, _, _, _ = self.call(
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10, 10])
        self.assertEqual(out["op"], 36)
        self.assertEqual(len(out["events"][0][4][3][0]), 18)
        self.assertEqual(len(out["events"][0][4][3][0][16][0]), 20)

    def test_json_file_and_argc_errors(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w") as f:
                f.write("{not json")
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                "[38,0,0,[[1,{},[0]]],"
                                "[['f','a','b',1,1]],[['s',[],[]]],"
                                "1,1,1,1,1,1,1,1,1,1,1,1,1]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 4)
            r = subprocess.run([sys.executable, RELAY, "config",
                                os.path.join(d, "missing.json"), "[]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 3)
            # Wrong config argument count is still code 2.
            r = subprocess.run([sys.executable, RELAY, "config", pp],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
