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


def div_topo(sb=1, cdlat=25):
    # s -> d has two routes that tie on cost 2 via b/c and the
    # full-node-sequence tie break picks b first, but the two routes
    # carry DIFFERENT latencies: via b is 20 while via c is 10+cdlat
    # (35 by default). Raising s-b pushes onto c and changes both the
    # path and the latency (a swing of 15). An isolated n5 -> n6 link
    # carries a stationary flow that only pads total demand.
    return {"nodes": ["s", "b", "c", "d", "n5", "n6"],
            "links": [link("s", "b", sb), link("b", "d"),
                      link("s", "c"), link("c", "d", lat=cdlat),
                      link("n5", "n6")]}


# T_A picks via b (latency 20); T_B raises s-b so via c (latency 35)
# wins: one migration with a 15 latency swing and last/next hop b -> c.
T_A = div_topo()
T_B = div_topo(sb=9)

# Failure of b already forced c at T_A and failure of c keeps b at T_B,
# so neither failure scenario ever migrates and both keep swing 0.
SCENARIOS = [["x", ["b"], []], ["z", ["c"], []]]

FLOWS = [["f1", "s", "d", 1, 1000],
         ["f2", "n5", "n6", 999, 1000]]


# An equal-latency diamond: both routes cost 2 and latency 20, so a
# forced migration swings latency by exactly 0.
def zdiv_topo(sb=1):
    return {"nodes": ["s", "b", "c", "d", "n5", "n6"],
            "links": [link("s", "b", sb), link("b", "d"),
                      link("s", "c"), link("c", "d"),
                      link("n5", "n6")]}


Z_A = zdiv_topo()
Z_B = zdiv_topo(sb=9)


def dtop(crd=1, drlat=10, sdlat=30):
    # Two-hop [s,r,d] (latency 20) competing with a costly direct
    # [s,d] link (latency 30). Raising r-d pushes onto the direct
    # link: last hop r -> s, next hop r -> d, a swing of 10.
    return {"nodes": ["s", "r", "d", "z0", "z1"],
            "links": [link("s", "d", 9, lat=sdlat),
                      link("s", "r", 1), link("r", "d", crd, lat=drlat),
                      link("z0", "z1")]}


D0 = dtop()
D1 = dtop(9)
D_FLOWS = [["g1", "s", "d", 1, 1000],
           ["g2", "z0", "z1", 999, 1000]]
D_SCN = [["g", ["r"], []]]


def pack(topo=None, v=0, history=None):
    topo = topo or T_A
    h = history if history is not None else [[0, topo, P]]
    return {"v": v, "t": topo, "p": P, "h": h}


def op40(events, flows_=None, scenarios=None, g=10, k=10, j=10, z=10,
         y=10, x=10, w=5, q=10, m=0, b=0, h=1000000, u=1000000,
         n=1000000, l=1000000, c=1000000, r=10, d=0):
    flows_ = FLOWS if flows_ is None else flows_
    return [40, m, b, events,
            flows_, SCENARIOS if scenarios is None else scenarios,
            l, c, r, d, w, q, h, u, n, x, y, z, j, k, g]


class Op40(unittest.TestCase):
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

    def call_raw(self, op_obj=None, pk=None, raw_text=None):
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
    def test_preview_pass_renders_swing_fields(self):
        out, before, after, tmps = self.call(op40([[1, T_B, P]], g=100))
        # Top-level key order unchanged.
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [40, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 0, 0, 1])
        scenarios = row[4][3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row: op 39's 21-element shape with
        # maxWindowLatencySwing inserted after
        # maxWindowDistinctLastHops and before pass (22 elements).
        s0 = scenarios[0]
        self.assertEqual(len(s0), 22)
        self.assertEqual(s0[16], 1)             # maxWindowDistinctNexthops
        self.assertEqual(s0[17], 1)             # maxWindowDistinctLastHops
        self.assertEqual(s0[18], 15)            # maxWindowLatencySwing
        self.assertIs(s0[19], True)             # pass
        # Flow row gains windowMaxLatencySwing / latencySwingPass
        # after lastHopDiversityPass and before nexthopDiversityPass:
        # 28 elements.
        f0 = s0[20][0]
        self.assertEqual(len(f0), 28)
        self.assertEqual(f0,
                         ["f1", 2, 2, 20, 35,
                          ["s", "b", "d"], ["s", "c", "d"], True, True,
                          1, None, None, True, -4, 1, True,
                          1, 2, 1, 1, 1, True,
                          15, True, True, True, True, True])
        # The stationary f2 keeps every window empty: swing 0.
        self.assertEqual(s0[20][1][14:28],
                         [0, True, 0, 0, 0, 0, 0,
                          True, 0, True, True, True, True, True])
        # Failure scenarios do not migrate: their swing windows stay
        # empty and their rows still pass.
        for sx in scenarios[1:]:
            self.assertEqual(sx[17], 0)
            self.assertEqual(sx[18], 0)
            self.assertIs(sx[19], True)
            self.assertIs(sx[20][0][7], False)
            self.assertEqual(sx[20][0][22:28],
                             [0, True, True, True, True, True])

    # ----------------------------------------------------------------
    # G = 0 accepts only zero-swing records / empty windows
    # ----------------------------------------------------------------
    def test_g_zero_rejects_first_swing_keeps_candidate(self):
        out, before, after, tmps = self.call(op40([[1, T_B, P]], g=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[18], 15)            # candidate max swing
        self.assertFalse(s0[19])
        fr = s0[20][0]
        # Candidate post-event values retained: one distinct last hop,
        # the 15 swing, G failed; every other flag still true.
        self.assertEqual(fr[3], 20)
        self.assertEqual(fr[4], 35)
        self.assertEqual(fr[21:28],
                         [True, 15, False, True, True, True, True])
        # Failure scenarios never moved and still pass.
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[19])
            self.assertEqual(sx[18], 0)

    def test_g_is_inclusive_at_the_boundary(self):
        # A 15 swing passes G = 15 but fails G = 14.
        out, _, _, _ = self.call(op40([[1, T_B, P]], g=15))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[18], 15)
        self.assertTrue(s0[19])
        out, _, _, _ = self.call(op40([[1, T_B, P]], g=14))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[18], 15)
        self.assertFalse(s0[19])

    def test_zero_swing_reroute_passes_g_zero(self):
        # A migration between equal-latency paths records swing 0 and
        # so passes G = 0 even though the path, links, first hop, and
        # last hop all change.
        out, _, _, _ = self.call(
            op40([[1, Z_B, P]], g=0), pk=pack(Z_A))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        f0 = s0[20][0]
        self.assertIs(f0[7], True)
        self.assertEqual(f0[3], 20)
        self.assertEqual(f0[4], 20)
        self.assertEqual(f0[20], 1)             # one distinct last hop
        self.assertEqual(f0[22], 0)             # zero swing
        self.assertIs(f0[23], True)             # G = 0 admits it
        self.assertEqual(s0[18], 0)
        self.assertTrue(s0[19])

    # ----------------------------------------------------------------
    # The G gate genuinely diverges from the hop-diversity gates
    # ----------------------------------------------------------------
    def test_swing_gate_independent_of_hop_gates(self):
        # One reroute [s,r,d] -> [s,d]: one distinct next hop and one
        # distinct last hop, so J and K pass with room, but the latency
        # jumps 20 -> 30 and G = 9 rejects the 10 swing.
        op_one = [40, 0, 0, [[1, D1, P]], D_FLOWS, D_SCN,
                  1000000, 1000000, 10, 0, 100, 10, 1000000, 1000000,
                  1000000, 10, 10, 10, 10, 10, 9]
        out, before, after, _ = self.call(op_one, pk=pack(D0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        f0 = s0[20][0]
        self.assertEqual(f0[5], ["s", "r", "d"])
        self.assertEqual(f0[6], ["s", "d"])
        self.assertIs(f0[7], True)
        self.assertEqual(f0[19], 1)             # one distinct next hop
        self.assertEqual(f0[20], 1)             # one distinct last hop
        self.assertEqual(f0[22], 10)            # swing 10
        self.assertIs(f0[21], True)             # K passes
        self.assertIs(f0[23], False)            # G fails
        self.assertEqual(s0[17], 1)
        self.assertEqual(s0[18], 10)
        self.assertFalse(s0[19])
        # Giving G room admits the same event.
        op_pass = list(op_one)
        op_pass[20] = 10
        out, _, _, _ = self.call(op_pass, pk=pack(D0))
        self.assertEqual(out["status"], 0)

    # ----------------------------------------------------------------
    # The window keeps the MAX, never a sum, and slides closed
    # ----------------------------------------------------------------
    def test_window_keeps_max_not_sum(self):
        # A 5 swing at event 1 then a 15 swing at event 2: with W=100
        # both records are retained, so the window maximum grows 5 ->
        # 15 (never their sum 20). G = 14 admits event 1 but stops at
        # event 2; G = 15 admits the whole batch.
        t_c5 = {"nodes": T_A["nodes"],
                "links": [link("s", "b", 9), link("b", "d"),
                          link("s", "c"), link("c", "d", lat=15),
                          link("n5", "n6")]}
        t_b15 = {"nodes": T_A["nodes"],
                 "links": [link("s", "b", 1, lat=30), link("b", "d"),
                           link("s", "c", 9), link("c", "d", lat=15),
                           link("n5", "n6")]}
        events = [[1, t_c5, P], [2, t_b15, P]]
        out, before, after, _ = self.call(op40(events, g=15, w=100))
        self.assertEqual(out["status"], 0)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0)])
        s1 = out["events"][0][4][3][0]
        self.assertEqual(s1[18], 5)             # after event 1
        s2 = out["events"][1][4][3][0]
        f0 = s2[20][0]
        self.assertEqual(f0[14], 2)             # two retained reroutes
        self.assertEqual(s2[18], 15)            # max(5, 15), not 20
        self.assertTrue(s2[19])
        out, _, _, _ = self.call(op40(events, g=14, w=100))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s2 = out["events"][1][4][3][0]
        self.assertEqual(s2[18], 15)
        self.assertFalse(s2[19])

    def test_swing_window_is_closed_when_sliding(self):
        # One reroute (swing 5) at clock 1, then a quiet event at
        # clock 2 that moves nothing. G is permissive enough for event
        # 1 to pass; W = 1 keeps clock 1 on the closed edge e-W so the
        # 5 survives into event 2, while W = 0 drops it and the window
        # is empty at event 2.
        t_c5 = {"nodes": T_A["nodes"],
                "links": [link("s", "b", 9), link("b", "d"),
                          link("s", "c"), link("c", "d", lat=15),
                          link("n5", "n6")]}
        t_quiet = json.loads(json.dumps(t_c5))
        t_quiet["links"][4]["latency"] = 11
        events = [[1, t_c5, P], [2, t_quiet, P]]
        out, _, _, _ = self.call(op40(events, g=5, w=1))
        self.assertEqual(out["status"], 0)
        s1 = out["events"][1][4][3][0]
        self.assertIs(s1[20][0][7], False)
        self.assertEqual(s1[18], 5)
        self.assertTrue(s1[19])
        out, _, _, _ = self.call(op40(events, g=5, w=0))
        self.assertEqual(out["status"], 0)
        s1 = out["events"][1][4][3][0]
        self.assertEqual(s1[18], 0)
        self.assertTrue(s1[19])

    def test_max_queue_front_slides_with_old_maximum(self):
        # Swings 25 @ 1 then 5 @ 2; a quiet event 3 with W = 1 trims
        # clock 1 strictly below 3-1 = 2, so the old maximum 25 leaves
        # and the retained maximum falls to 5 - exercising the
        # monotonic max queue's front eviction, not a stale max.
        m0 = {"nodes": ["s", "b", "c", "d", "n5", "n6"],
              "links": [link("s", "b", 1, lat=0), link("b", "d"),
                        link("s", "c"), link("c", "d", lat=25),
                        link("n5", "n6")]}
        m1 = {"nodes": m0["nodes"],
              "links": [link("s", "b", 9, lat=0), link("b", "d"),
                        link("s", "c"), link("c", "d", lat=25),
                        link("n5", "n6")]}
        m2 = {"nodes": m0["nodes"],
              "links": [link("s", "b", 1, lat=20), link("b", "d"),
                        link("s", "c", 9), link("c", "d", lat=25),
                        link("n5", "n6")]}
        m3 = json.loads(json.dumps(m2))
        m3["links"][4]["latency"] = 11
        events = [[1, m1, P], [2, m2, P], [3, m3, P]]
        out, _, _, _ = self.call(op40(events, g=25, w=1), pk=pack(m0))
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 0)])
        s1 = out["events"][1][4][3][0]
        self.assertEqual(s1[18], 25)            # max(25, 5)
        s2 = out["events"][2][4][3][0]
        self.assertEqual(s2[18], 5)             # 25 slid out, 5 stays
        self.assertTrue(s2[19])

    # ----------------------------------------------------------------
    # Predicate exclusions
    # ----------------------------------------------------------------
    def test_equal_state_and_unchanged_path_add_no_record(self):
        # Event 2 is equal state (status 1, empty impact); event 3
        # changes only the isolated n5->n6 latency, so nothing appends
        # and the earlier swing window still slides normally.
        t_quiet = json.loads(json.dumps(T_B))
        t_quiet["links"][4]["latency"] = 11
        out, _, _, _ = self.call(
            op40([[1, T_B, P], [2, T_B, P], [3, t_quiet, P]],
                 g=100, w=100))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 0)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        s2 = out["events"][2][4][3][0]
        self.assertEqual(s2[18], 15)
        f0 = s2[20][0]
        self.assertIs(f0[7], False)
        self.assertEqual(f0[22:28], [15, True, True, True, True, True])

    def test_unreachable_migration_adds_no_record(self):
        # The candidate side drops both s-branches: f1 is unreachable,
        # no reroute, so no swing record even though the event fails
        # (and the batch stops) on reachability.
        t_dead = {"nodes": T_A["nodes"],
                  "links": [lk for lk in T_A["links"]
                            if (lk["from"], lk["to"])
                            not in (("s", "b"), ("s", "c"))]}
        out, before, after, _ = self.call(op40([[1, t_dead, P]], g=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[19])
        f0 = s0[20][0]
        self.assertEqual(f0[6], [])             # unreachable new side
        self.assertIs(f0[7], False)
        self.assertEqual(f0[22], 0)             # no swing record
        self.assertIs(f0[23], True)             # G itself does not fail

    # ----------------------------------------------------------------
    # No merging across scenarios or flows
    # ----------------------------------------------------------------
    def test_scenarios_never_merge(self):
        # Only the no-failure scenario migrates (b -> c, swing 15); in x
        # b was already failed onto c and in z c failed keeps b, so
        # their swing windows stay empty.
        out, _, _, _ = self.call(op40([[1, T_B, P]], g=0))
        s0, sx, sz = out["events"][0][4][3]
        self.assertFalse(s0[19])
        self.assertEqual(s0[20][0][22:28],
                         [15, False, True, True, True, True])
        for other in (sx, sz):
            self.assertTrue(other[19])
            self.assertEqual(other[18], 0)
            self.assertEqual(other[20][0][22:28],
                             [0, True, True, True, True, True])

    def test_flows_never_merge(self):
        # Two independently migrating flows on disjoint diamonds with
        # swings 15 and 30, plus a stationary demand-999 flow. Over cb
        # then ca each flow keeps its own two equal records; the
        # scenario maxWindowLatencySwing is max(15, 30) = 30, never the
        # merged sum 45 or either flow's sum.
        two = [["f1", "s", "d", 1, 1000],
               ["f3", "n0", "d2", 1, 1000],
               ["f4", "n5", "n6", 999, 1000]]

        def combo(sb=1, n0b=1):
            nodes = ["s", "b", "c", "d",
                     "n0", "b2", "c2", "d2", "n5", "n6"]
            return {"nodes": nodes,
                    "links": [link("s", "b", sb), link("b", "d"),
                              link("s", "c"), link("c", "d", lat=25),
                              link("n0", "b2", n0b), link("b2", "d2"),
                              link("n0", "c2"),
                              link("c2", "d2", lat=40),
                              link("n5", "n6")]}

        ca, cb = combo(), combo(sb=9, n0b=9)
        events = [[1, cb, P], [2, ca, P]]
        out, _, _, _ = self.call(
            op40(events, flows_=two, scenarios=[["x", ["b"], []]],
                 g=30, w=100), pk=pack(ca))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        f1, f3, f4 = s0[20]
        self.assertEqual(f1[22], 15)
        self.assertEqual(f3[22], 30)
        self.assertEqual(f4[22], 0)
        self.assertEqual(s0[18], 30)            # max, not sum/merge
        # G = 29 rejects on f3's 30 at the very first event.
        out, _, _, _ = self.call(
            op40(events, flows_=two, scenarios=[["x", ["b"], []]],
                 g=29, w=100), pk=pack(ca))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[18], 30)
        self.assertFalse(s0[19])

    # ----------------------------------------------------------------
    # Op 39's other gates still reject independently
    # ----------------------------------------------------------------
    def test_k_gate_still_rejects_independently(self):
        # The equal-latency migration has swing 0 (G = 0 passes) but
        # still changes the last hop, so K = 0 rejects on its own.
        out, before, after, _ = self.call(
            op40([[1, Z_B, P]], g=0, k=0), pk=pack(Z_A))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[19])
        f0 = s0[20][0]
        self.assertIs(f0[21], False)            # K fails
        self.assertEqual(f0[22], 0)
        self.assertIs(f0[23], True)             # G passes

    def test_q_gate_still_rejects_independently(self):
        # G admits the 15 swing, but Q = 0 rejects the first reroute.
        out, before, after, _ = self.call(
            op40([[1, T_B, P]], g=100, q=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[19])
        f0 = s0[20][0]
        self.assertIs(f0[15], False)            # windowPass fails
        # Candidate record still appended; swing rendered and all
        # diversity flags read true on the failed row.
        self.assertEqual(f0[16:28],
                         [1, 2, 1, 1, 1, True,
                          15, True, True, True, True, True])

    # ----------------------------------------------------------------
    # Commit / resend / rollback semantics
    # ----------------------------------------------------------------
    def test_commit_resend_and_idempotent(self):
        out, before, after, tmps = self.call(
            op40([[1, T_B, P]], g=100, m=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            op40([[1, T_B, P]], g=100, m=1), pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Equal-state event: status 0, no write even with every cap 0.
        out3, _, after3, _ = self.call(
            op40([[2, T_B, P]], g=0, k=0, j=0, z=0, y=0, x=0, q=0,
                 n=0, m=1, b=1),
            pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(json.loads(after3)["v"], 1)

    def test_failed_batch_does_not_commit(self):
        # Event 1 migrates b -> c with a 5 swing (G = 14 admits); event
        # 2 migrates c -> b with a 15 swing so the retained window max
        # grows to 15 and G = 14 fails the second event - mode 1 leaves
        # PACK untouched and stops at once.
        t_c5 = {"nodes": T_A["nodes"],
                "links": [link("s", "b", 9), link("b", "d"),
                          link("s", "c"), link("c", "d", lat=15),
                          link("n5", "n6")]}
        t_b15 = {"nodes": T_A["nodes"],
                 "links": [link("s", "b", 1, lat=30), link("b", "d"),
                           link("s", "c", 9), link("c", "d", lat=15),
                           link("n5", "n6")]}
        events = [[1, t_c5, P], [2, t_b15, P]]
        out, before, after, tmps = self.call(
            op40(events, g=14, w=100, m=1))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s1 = out["events"][1][4][3][0]
        self.assertEqual(s1[18], 15)
        self.assertFalse(s1[19])
        # A feasible retry (G = 15) commits from the same base.
        out2, _, after2, _ = self.call(
            op40(events, g=15, w=100, m=1))
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_stale_base_conflict_code5(self):
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        other = json.loads(json.dumps(T_A))
        other["links"][4]["latency"] = 7
        self.call(op40([[6, other, P]], g=100, m=1), pk=pk1,
                  expect_rc=5)

    # ----------------------------------------------------------------
    # Determinism / error codes / backward compatibility
    # ----------------------------------------------------------------
    def test_byte_deterministic(self):
        op_obj = op40([[1, T_B, P], [2, T_A, P]], g=15, w=100)
        r1 = self.call_raw(op_obj)
        r2 = self.call_raw(op_obj)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_unparseable_json_code4(self):
        run = self.call_raw(raw_text="{not json")
        self.assertEqual(run.returncode, 4)

    def test_pack_read_error_code3(self):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "absent.json")
            run = subprocess.run(
                [sys.executable, RELAY, "config", missing,
                 json.dumps(op40([[1, T_B, P]]))], capture_output=True)
            self.assertEqual(run.returncode, 3)

    def test_unknown_command_and_argc_code2(self):
        run = subprocess.run([sys.executable, RELAY, "frobnicate"],
                             capture_output=True)
        self.assertEqual(run.returncode, 2)
        # config with a missing OP argument also keeps code 2.
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pack(), f)
            run = subprocess.run(
                [sys.executable, RELAY, "config", pp],
                capture_output=True)
            self.assertEqual(run.returncode, 2)

    def test_shape_and_range_code5(self):
        good = op40([[1, T_B, P]])
        self.assertEqual(len(good), 21)
        tail15 = [1] * 15
        bad = [
            # wrong arity: op 39's 20-element shape and one too many
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 16,
            # op 39 must not accept op 40's 21 elements and vice versa
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 15,
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 13,
            # G negative / boolean / too large / string / float
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2147483648],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, "1"],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5],
            # op 39's K range still enforced inside op 40
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True, 1, 1],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1, 1, 1],
            # bad mode
            [40, 2, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + tail15,
            # empty E / F / S
            [40, 0, 0, [], FLOWS, SCENARIOS] + tail15,
            [40, 0, 0, [[1, T_B, P]], [], SCENARIOS] + tail15,
            [40, 0, 0, [[1, T_B, P]], FLOWS, []] + tail15,
            # clocks decrease
            [40, 0, 0, [[2, T_B, P], [1, T_B, P]], FLOWS,
             SCENARIOS] + tail15,
            # invalid scenario reference at h[b]
            [40, 0, 0, [[1, T_B, P]], FLOWS,
             [["q", ["d"], []]]] + tail15,
            # flow endpoint absent at h[b]
            [40, 0, 0, [[1, T_B, P]],
             [["g", "s", "n9", 1, 1000]], SCENARIOS] + tail15,
        ]
        for op_obj in bad:
            self.call(op_obj, expect_rc=5)
        # G = MAX_COST is accepted.
        self.call(op40([[1, T_B, P]], g=2147483647))

    def test_ops_0_to_39_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        # op 39 keeps its 21-field scenario row and 26-field flow row,
        # with no swing fields.
        out, _, _, _ = self.call(
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10, 10, 10, 10, 10])
        self.assertEqual(out["op"], 39)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(len(s0), 21)
        self.assertEqual(len(s0[19][0]), 26)
        # op 39's 20-arity shape must not parse as op 40 and op 40's
        # 21-arity shape must not parse as op 39.
        self.call(
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            expect_rc=5)
        self.call(
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 15,
            expect_rc=5)


if __name__ == "__main__":
    unittest.main()
