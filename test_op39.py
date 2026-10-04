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


def div_topo(sb=1):
    # s -> d has two routes that diverge at the source and converge
    # only at the destination: via b (s,b,d) and via c (s,c,d).
    # Raising s-b pushes the route onto c, changing BOTH the first
    # hop (b -> c) and the last hop (b -> c). An isolated n5 -> n6
    # link carries a stationary flow that only pads total demand.
    return {"nodes": ["s", "b", "c", "d", "n5", "n6"],
            "links": [link("s", "b", sb), link("b", "d"),
                      link("s", "c"), link("c", "d"),
                      link("n5", "n6")]}


# tA ties on cost 2 via b/c and the full-node-sequence tie break picks
# b first; tB raises s-b so the c route wins; back to tA restores b.
T_A = div_topo()
T_B = div_topo(sb=9)

# Failure of b already forced c at tA and failure of c keeps b at tB,
# so neither failure scenario ever migrates.
SCENARIOS = [["x", ["b"], []], ["z", ["c"], []]]

# One migrating flow plus a stationary demand-999 flow that only
# enlarges the demand denominator.
FLOWS = [["f1", "s", "d", 1, 1000],
         ["f2", "n5", "n6", 999, 1000]]


def tail_topo(sb=1):
    # A second diamond whose two routes SHARE the tail node a before
    # the destination: s -> {b,c} -> a -> d. Rerouting between the
    # branches changes the complete path, links, transit nodes, and
    # the first hop (b vs c) but never the last hop (always a), so
    # the last-hop gate diverges from op 38's next-hop gate.
    return {"nodes": ["s", "b", "c", "a", "d", "n5", "n6"],
            "links": [link("s", "b", sb), link("b", "a"),
                      link("s", "c"), link("c", "a"),
                      link("a", "d"),
                      link("n5", "n6")]}


H_A = tail_topo()
H_B = tail_topo(sb=9)

HP1 = ["s", "b", "a", "d"]
HP2 = ["s", "c", "a", "d"]
H_FLOWS = [["f1", "s", "d", 1, 1000],
           ["f2", "n5", "n6", 999, 1000]]


def dtop(crd=1):
    # Two-hop [s,r,d] competing with a costly direct [s,d] link.
    return {"nodes": ["s", "r", "d", "z0", "z1"],
            "links": [link("s", "d", 9),
                      link("s", "r", 1), link("r", "d", crd),
                      link("z0", "z1")]}


D0 = dtop(1)
D1 = dtop(9)
D_FLOWS = [["g1", "s", "d", 1, 1000],
           ["g2", "z0", "z1", 999, 1000]]
D_SCN = [["g", ["r"], []]]


def pack(topo=None, v=0, history=None):
    topo = topo or T_A
    h = history if history is not None else [[0, topo, P]]
    return {"v": v, "t": topo, "p": P, "h": h}


def op39(events, flows_=None, scenarios=None, k=10, j=10, z=10, y=10,
         x=10, w=5, q=10, m=0, b=0, h=1000000, u=1000000, n=1000000,
         l=1000000, c=1000000, r=10, d=0):
    flows_ = FLOWS if flows_ is None else flows_
    return [39, m, b, events,
            flows_, SCENARIOS if scenarios is None else scenarios,
            l, c, r, d, w, q, h, u, n, x, y, z, j, k]


class Op39(unittest.TestCase):
    def call(self, op_obj, pk=None, expect_rc=0):
        pk = pk if pk is not None else pack()
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pk, f)
            with open(pp, "rb") as fh:
                before = fh.read()
            run = subprocess.run([sys.executable, RELAY, "config", pp,
                                  json.dumps(op_obj)], capture_output=True,
                                 text=True)
            self.assertEqual(run.returncode, expect_rc,
                             "rc=%s err=%s out=%s"
                             % (run.returncode, run.stderr, run.stdout))
            out = json.loads(run.stdout) if run.stdout else None
            with open(pp, "rb") as fh:
                after = fh.read()
            tmps = [name for name in os.listdir(d) if ".tmp." in name]
            return out, before, after, tmps

    def call_raw(self, op_obj, pk=None, raw_text=None):
        pk = pk if pk is not None else pack()
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pk, f)
            text = raw_text if raw_text is not None else json.dumps(op_obj)
            return subprocess.run([sys.executable, RELAY, "config", pp,
                                   text], capture_output=True)

    # ----------------------------------------------------------------
    # Rendering / field positions
    # ----------------------------------------------------------------
    def test_preview_pass_renders_lasthop_fields(self):
        out, before, after, tmps = self.call(op39([[1, T_B, P]], k=10))
        # Top-level key order unchanged.
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [39, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 0, 0, 1])
        scenarios = row[4][3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row: op 38's 20-element shape with
        # maxWindowDistinctLastHops inserted after
        # maxWindowDistinctNexthops and before pass (21 elements).
        s0 = scenarios[0]
        self.assertEqual(len(s0), 21)
        self.assertEqual(s0[13], 1)             # maxWindowDistinctPaths
        self.assertEqual(s0[14], 2)             # maxWindowDistinctLinks
        self.assertEqual(s0[15], 1)             # maxWindowDistinctTransitNodes
        self.assertEqual(s0[16], 1)             # maxWindowDistinctNexthops
        self.assertEqual(s0[17], 1)             # maxWindowDistinctLastHops (c)
        self.assertIs(s0[18], True)             # pass
        # Flow row gains windowDistinctLastHopCount /
        # lastHopDiversityPass after windowDistinctNexthopCount and
        # before nexthopDiversityPass: 26 elements.
        f0 = s0[19][0]
        self.assertEqual(len(f0), 26)
        self.assertEqual(f0,
                         ["f1", 2, 2, 20, 20,
                          ["s", "b", "d"], ["s", "c", "d"], True, True,
                          1, None, None, True, -4, 1, True,
                          1, 2, 1, 1, 1, True, True, True, True, True])
        # The stationary f2 keeps every window empty.
        self.assertEqual(s0[19][1][14:26],
                         [0, True, 0, 0, 0, 0, 0,
                          True, True, True, True, True])
        # Failure scenarios do not migrate: their windows stay empty.
        for sx in scenarios[1:]:
            self.assertEqual(sx[16], 0)
            self.assertEqual(sx[17], 0)
            self.assertIs(sx[18], True)
            self.assertEqual(sx[19][0][7], False)
            self.assertEqual(sx[19][0][16:26],
                             [0, 0, 0, 0, 0,
                              True, True, True, True, True])

    # ----------------------------------------------------------------
    # K = 0 accepts only the empty window
    # ----------------------------------------------------------------
    def test_k_zero_rejects_first_retained_hop_keeps_candidate(self):
        out, before, after, tmps = self.call(op39([[1, T_B, P]], k=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[17], 1)
        self.assertFalse(s0[18])
        fr = s0[19][0]
        # Candidate post-event values retained: one distinct next hop
        # and one distinct last hop, K gate failed, j/z/y/x gates fine.
        self.assertEqual(fr[19:26], [1, 1, False, True, True, True, True])
        # Failure scenarios never moved and still pass.
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[18])
            self.assertEqual(sx[17], 0)

    def test_k_one_admits_single_last_hop(self):
        out, _, _, _ = self.call(op39([[1, T_B, P]], k=1))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[17], 1)
        self.assertTrue(s0[18])
        self.assertEqual(s0[19][0][21:26],
                         [True, True, True, True, True])

    # ----------------------------------------------------------------
    # The gate genuinely diverges from the next-hop (J) gate
    # ----------------------------------------------------------------
    def test_shared_tail_hop_counts_once_across_paths(self):
        # H_A -> H_B -> H_A retains HP2 then HP1: two distinct first
        # hops {b,c}, five directed links, and three interior transit
        # nodes {a,b,c}, but both paths reach d through the SAME last
        # hop a, so the last-hop union stays a singleton. K = 1
        # accepts while J = 1 rejects at event 2.
        events = [[1, H_B, P], [2, H_A, P]]
        out, before, after, _ = self.call(
            op39(events, flows_=H_FLOWS, w=100, x=2, y=5, z=3, j=1,
                 k=1),
            pk=pack(H_A))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[16], 2)                    # two first hops
        self.assertEqual(s0[17], 1)                    # one shared last hop
        self.assertFalse(s0[18])                       # J fails, K does not
        f0 = s0[19][0]
        self.assertEqual(f0[19:26],
                         [2, 1, True, False, True, True, True])
        # K = 1 alone admits once J is also given room.
        out, _, _, _ = self.call(
            op39(events, flows_=H_FLOWS, w=100, x=2, y=5, z=3, j=2,
                 k=1),
            pk=pack(H_A))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[16:19], [2, 1, True])
        self.assertEqual(s0[19][0][19:26],
                         [2, 1, True, True, True, True, True])

    def test_direct_link_last_hop_is_source(self):
        # Rerouting [s,r,d] onto the direct [s,d] link contributes the
        # destination d as the next hop but the source s as the last
        # hop: one distinct hop for either window, but the recorded
        # node is different.
        base_pk = pack(D0)
        op_one = [39, 0, 0, [[1, D1, P]], D_FLOWS, D_SCN,
                  1000000, 1000000, 10, 0, 100, 10, 1000000, 1000000,
                  1000000, 10, 10, 10, 0, 0]
        out, before, after, _ = self.call(op_one, pk=base_pk)
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        f0 = s0[19][0]
        self.assertEqual(f0[5], ["s", "r", "d"])
        self.assertEqual(f0[6], ["s", "d"])
        self.assertIs(f0[7], True)
        # Both windows hold one hop; J = 0 and K = 0 both fail but
        # they record different nodes (next d, last s).
        self.assertEqual(f0[19:26], [1, 1, False, False, True, True, True])
        self.assertEqual(s0[16:19], [1, 1, False])
        # Giving K room but not J still fails on the next-hop gate;
        # giving both room admits.
        op_k1 = list(op_one)
        op_k1[19] = 1
        out, _, _, _ = self.call(op_k1, pk=base_pk)
        self.assertEqual(out["status"], 2)
        f0 = out["events"][0][4][3][0][19][0]
        self.assertEqual(f0[19:26], [1, 1, True, False, True, True, True])
        op_k1[18] = 1
        out, _, _, _ = self.call(op_k1, pk=base_pk)
        self.assertEqual(out["status"], 0)

    def test_reroute_back_spans_two_last_hops(self):
        # D1 -> direct (last hop s), then D0 -> via r (last hop r):
        # the window holds two distinct last hops {s, r}; K = 1
        # rejects at event 2 and K = 2 admits.
        events = [[1, D1, P], [2, D0, P]]
        out, before, after, _ = self.call(
            op39(events, flows_=D_FLOWS, scenarios=D_SCN, w=100, k=1),
            pk=pack(D0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[17], 2)
        self.assertFalse(s0[18])
        self.assertEqual(s0[19][0][20:26],
                         [2, False, True, True, True, True])
        out, _, _, _ = self.call(
            op39(events, flows_=D_FLOWS, scenarios=D_SCN, w=100, k=2),
            pk=pack(D0))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[17], 2)
        self.assertTrue(s0[18])

    # ----------------------------------------------------------------
    # Closed-window refcount semantics
    # ----------------------------------------------------------------
    def test_hop_leaves_only_after_last_record_slides_out(self):
        # Records for g1: direct last hop s@1 (D1), hop r@2 (D0),
        # s@3 (D1). Event 4 is a non-moving change to the isolated
        # z0->z1 link, so with W = 1 the window slides to start 3
        # without appending: s@1 drops but s is still referenced by
        # s@3; r@2 drops and r leaves. The retained union is exactly
        # {s} - not a never-shrinking seen-set ({s,r}) and not
        # pop-drops-node.
        t_quiet = json.loads(json.dumps(D1))
        t_quiet["links"][3]["latency"] = 11
        events = [[1, D1, P], [2, D0, P], [3, D1, P], [4, t_quiet, P]]
        out, _, _, _ = self.call(
            op39(events, flows_=D_FLOWS, scenarios=D_SCN, w=1, k=5),
            pk=pack(D0))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 0), (4, 0)])
        s4 = out["events"][3][4][3][0]
        self.assertEqual(s4[17], 1)
        self.assertTrue(s4[18])
        f0 = s4[19][0]
        self.assertIs(f0[7], False)             # event 4 moved nothing
        self.assertEqual(f0[20], 1)
        # Just before the slide (event 3) both hops coexist on the
        # closed edge: windowStart 2 keeps r@2 and adds s@3.
        s3 = out["events"][2][4][3][0]
        self.assertEqual(s3[17], 2)
        self.assertEqual(s3[19][0][20:26],
                         [2, True, True, True, True, True])

    def test_window_is_closed_when_sliding(self):
        # last hops c@1 then b@2. W = 1 keeps clock 1 so both hops
        # {b,c} survive and K = 1 fails at event 2; W = 0 drops @1
        # leaving only b and K = 1 passes.
        events = [[1, T_B, P], [2, T_A, P]]
        out, _, _, _ = self.call(op39(events, w=1, k=1))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[17], 2)
        self.assertFalse(s0[18])
        out, _, _, _ = self.call(op39(events, w=0, k=1))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[17], 1)
        self.assertTrue(s0[18])

    # ----------------------------------------------------------------
    # Predicate exclusions
    # ----------------------------------------------------------------
    def test_equal_state_and_unchanged_path_add_no_record(self):
        # Event 2 is equal state (status 1, empty impact); event 3
        # changes only the isolated n5->n6 latency, so no path changes
        # and nothing is appended. f1 still shows just last hop c.
        t_quiet = json.loads(json.dumps(T_B))
        t_quiet["links"][4]["latency"] = 11
        out, _, _, _ = self.call(
            op39([[1, T_B, P], [2, T_B, P], [3, t_quiet, P]],
                 w=100, k=1))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 0)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[17], 1)
        self.assertTrue(s0[18])
        f0 = s0[19][0]
        self.assertIs(f0[7], False)
        self.assertEqual(f0[20:26], [1, True, True, True, True, True])

    def test_unreachable_migration_adds_no_record(self):
        # The candidate side drops both s-branches: f1 is unreachable,
        # no reroute, so no last-hop record even though the event
        # fails (and the batch stops) on reachability.
        t_dead = {"nodes": T_A["nodes"],
                  "links": [lk for lk in T_A["links"]
                            if (lk["from"], lk["to"])
                            not in (("s", "b"), ("s", "c"))]}
        out, before, after, _ = self.call(op39([[1, t_dead, P]], k=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[18])
        f0 = s0[19][0]
        self.assertEqual(f0[6], [])             # unreachable new side
        self.assertIs(f0[7], False)
        self.assertEqual(f0[20], 0)             # no last-hop record
        self.assertIs(f0[21], True)             # K itself does not fail

    # ----------------------------------------------------------------
    # No merging across scenarios or flows
    # ----------------------------------------------------------------
    def test_scenarios_never_merge(self):
        # Only the no-failure scenario migrates (b -> c); in x b was
        # already failed onto c and in z c failed keeps b, so their
        # last-hop windows stay empty.
        out, _, _, _ = self.call(op39([[1, T_B, P]], k=0))
        s0, sx, sz = out["events"][0][4][3]
        self.assertFalse(s0[18])
        self.assertEqual(s0[19][0][20:26],
                         [1, False, True, True, True, True])
        for other in (sx, sz):
            self.assertTrue(other[18])
            self.assertEqual(other[17], 0)
            self.assertEqual(other[19][0][20:26],
                             [0, True, True, True, True, True])

    def test_flows_never_merge(self):
        # Two independently migrating flows on disjoint branch sets,
        # plus a stationary flow that pads total demand for the window
        # gates. Over cb then ca, f1 retains last hops {c,b} (the
        # source-divergent diamond) while f3 on the tail-shared
        # diamond retains only the shared tail node {a2}. The
        # scenario max is 2, never the merged 3.
        two = [["f1", "s", "d", 1, 1000],
               ["f3", "n0", "n4", 1, 1000],
               ["f4", "n5", "n6", 999, 1000]]

        def combo(sb=1, n0b=1):
            nodes = ["s", "b", "c", "d", "n0", "a2", "n4", "n5", "n6"]
            return {"nodes": nodes,
                    "links": [link("s", "b", sb), link("b", "d"),
                              link("s", "c"), link("c", "d"),
                              link("n0", "b", n0b), link("b", "a2"),
                              link("n0", "c"), link("c", "a2"),
                              link("a2", "n4"),
                              link("n5", "n6")]}

        ca, cb = combo(), combo(sb=9, n0b=9)
        events = [[1, cb, P], [2, ca, P]]
        out, _, _, _ = self.call(
            op39(events, flows_=two, w=100, k=2), pk=pack(ca))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        f1, f3, f4 = s0[19]
        # f1 oscillates b<->c (two last hops); f3 oscillates
        # b<->c at the source but shares tail a2 (one); the
        # stationary f4 keeps an empty last-hop window.
        self.assertEqual(f1[20], 2)
        self.assertEqual(f3[20], 1)
        self.assertEqual(f4[20], 0)
        self.assertEqual(s0[17], 2)             # max, not union

    # ----------------------------------------------------------------
    # Op 38's other gates still reject independently
    # ----------------------------------------------------------------
    def test_q_gate_still_rejects_independently(self):
        # K admits the single hop, but Q = 0 rejects the first reroute.
        out, before, after, _ = self.call(
            op39([[1, T_B, P]], k=10, q=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[18])
        f0 = s0[19][0]
        self.assertIs(f0[15], False)            # windowPass fails
        # Candidate record still appended; all diversity flags read
        # true on the failed row.
        self.assertEqual(f0[16:26],
                         [1, 2, 1, 1, 1,
                          True, True, True, True, True])

    def test_j_gate_still_rejects_independently(self):
        # On the tail-shared diamond the single migration changes the
        # first hop b -> c but keeps the last hop a: K = 10 admits
        # while J = 0 rejects on the next-hop gate.
        out, before, after, _ = self.call(
            op39([[1, H_B, P]], flows_=H_FLOWS, k=10, j=0),
            pk=pack(H_A))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[18])
        f0 = s0[19][0]
        self.assertEqual(f0[5], HP1)
        self.assertEqual(f0[6], HP2)
        # one retained next hop (c, J fails) and one retained last hop
        # (a, K passes).
        self.assertEqual(f0[19:26],
                         [1, 1, True, False, True, True, True])

    # ----------------------------------------------------------------
    # Commit / resend / rollback semantics
    # ----------------------------------------------------------------
    def test_commit_resend_and_idempotent(self):
        out, before, after, tmps = self.call(
            op39([[1, T_B, P]], k=10, m=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            op39([[1, T_B, P]], k=10, m=1), pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Equal-state event: status 0, no write even with every cap 0.
        out3, _, after3, _ = self.call(
            op39([[2, T_B, P]], k=0, j=0, z=0, y=0, x=0, q=0, n=0,
                 m=1, b=1),
            pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(json.loads(after3)["v"], 1)

    def test_failed_batch_does_not_commit(self):
        # Event 1 retains last hop c (K = 1 admits); event 2 brings b
        # back so two last hops are retained - K = 1 fails - mode 1
        # leaves PACK untouched and stops at once.
        events = [[1, T_B, P], [2, T_A, P]]
        out, before, after, tmps = self.call(
            op39(events, w=100, k=1, m=1))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        # A feasible retry (K = 2) commits from the same base.
        out2, _, after2, _ = self.call(
            op39(events, w=100, k=2, m=1))
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_stale_base_conflict_code5(self):
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        other = json.loads(json.dumps(T_A))
        other["links"][4]["latency"] = 7
        self.call(op39([[6, other, P]], k=10, m=1), pk=pk1,
                  expect_rc=5)

    # ----------------------------------------------------------------
    # Determinism / error codes / backward compatibility
    # ----------------------------------------------------------------
    def test_byte_deterministic(self):
        op_obj = op39([[1, T_B, P], [2, T_A, P]], w=100, k=2)
        r1 = self.call_raw(op_obj)
        r2 = self.call_raw(op_obj)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_unparseable_json_code4(self):
        run = self.call_raw(None, raw_text="{not json")
        self.assertEqual(run.returncode, 4)

    def test_shape_and_range_code5(self):
        good = op39([[1, T_B, P]])
        self.assertEqual(len(good), 20)
        tail14 = [1] * 14
        bad = [
            # wrong arity: op 38's 19-element shape and one too many
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 13,
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 15,
            # op 38 must not accept op 39's 20 elements and vice versa
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 12,
            # K negative / boolean / too large / string / float
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True],
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2147483648],
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, "1"],
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5],
            # op 38's J/Z/Y/X ranges still enforced inside op 39
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1],
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True, 1, 1],
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1, 1, 1],
            # bad mode
            [39, 2, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + tail14,
            # empty E / F / S
            [39, 0, 0, [], FLOWS, SCENARIOS] + tail14,
            [39, 0, 0, [[1, T_B, P]], [], SCENARIOS] + tail14,
            [39, 0, 0, [[1, T_B, P]], FLOWS, []] + tail14,
            # clocks decrease
            [39, 0, 0, [[2, T_B, P], [1, T_B, P]], FLOWS,
             SCENARIOS] + tail14,
            # invalid scenario reference at h[b]
            [39, 0, 0, [[1, T_B, P]], FLOWS,
             [["q", ["d"], []]]] + tail14,
            # flow endpoint absent at h[b]
            [39, 0, 0, [[1, T_B, P]],
             [["g", "s", "n9", 1, 1000]], SCENARIOS] + tail14,
        ]
        for op_obj in bad:
            self.call(op_obj, expect_rc=5)
        # K = MAX_COST is accepted.
        self.call(op39([[1, T_B, P]], k=2147483647))

    def test_ops_0_to_38_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        # op 38 keeps its 20-field scenario row and 24-field flow row,
        # with no last-hop fields.
        out, _, _, _ = self.call(
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10, 10, 10, 10])
        self.assertEqual(out["op"], 38)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(len(s0), 20)
        self.assertEqual(len(s0[18][0]), 24)
        # op 38's 19-arity shape must not parse as op 39 and op 39's
        # 20-arity shape must not parse as op 38.
        self.call(
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 13,
            expect_rc=5)
        self.call(
            [38, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            expect_rc=5)


if __name__ == "__main__":
    unittest.main()
