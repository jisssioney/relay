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


def cdiv_topo(sb=1, sbd=1, sc=5, scd=5):
    # s -> d has two routes whose LATENCIES are always equal (20) but
    # whose COSTS differ: via b costs sb+sbd (2 by default) and via c
    # costs sc+scd (10 by default); the full-node-sequence tie break
    # picks b on a cost tie. Raising s-b pushes onto c and changes the
    # path and the COST (a cost swing of 8) while the latency stays 20
    # (a latency swing of 0). An isolated n5 -> n6 link carries a
    # stationary flow that only pads total demand.
    return {"nodes": ["s", "b", "c", "d", "n5", "n6"],
            "links": [link("s", "b", sb), link("b", "d", sbd),
                      link("s", "c", sc), link("c", "d", scd),
                      link("n5", "n6")]}


# C_A picks via b (cost 2); C_B raises s-b so via c (cost 10) wins:
# one migration with a COST swing of 8 and a latency swing of 0.
C_A = cdiv_topo()
C_B = cdiv_topo(sb=20)

# Failure of b already forced c at C_A and failure of c keeps b at C_B,
# so neither failure scenario ever migrates and both keep swing 0.
SCENARIOS = [["x", ["b"], []], ["z", ["c"], []]]

FLOWS = [["f1", "s", "d", 1, 1000],
         ["f2", "n5", "n6", 999, 1000]]


# An equal-COST diamond: both routes cost 2 and latency 20, so a forced
# migration onto c swings the cost by exactly 0.
def zcdiv_topo(sb=1):
    return {"nodes": ["s", "b", "c", "d", "n5", "n6"],
            "links": [link("s", "b", sb), link("b", "d"),
                      link("s", "c", 1), link("c", "d", 1),
                      link("n5", "n6")]}


Z_A = zcdiv_topo()
Z_B = zcdiv_topo(sb=9)


# A latency-only diamond: both routes cost 2 but via b is latency 20
# while via c is latency 35; migrating swings latency 15 but cost 0.
def ldiv_topo(sb=1, cdlat=25):
    return {"nodes": ["s", "b", "c", "d", "n5", "n6"],
            "links": [link("s", "b", sb), link("b", "d"),
                      link("s", "c"), link("c", "d", lat=cdlat),
                      link("n5", "n6")]}


L_A = ldiv_topo()
L_B = ldiv_topo(sb=9)


def pack(topo=None, v=0, history=None):
    topo = topo or C_A
    h = history if history is not None else [[0, topo, P]]
    return {"v": v, "t": topo, "p": P, "h": h}


def op41(events, flows_=None, scenarios=None, t=100, g=100, k=10, j=10,
         z=10, y=10, x=10, w=5, q=10, m=0, b=0, h=1000000, u=1000000,
         n=1000000, l=1000000, c=1000000, r=10, d=0):
    flows_ = FLOWS if flows_ is None else flows_
    return [41, m, b, events,
            flows_, SCENARIOS if scenarios is None else scenarios,
            l, c, r, d, w, q, h, u, n, x, y, z, j, k, g, t]


class Op41(unittest.TestCase):
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
    def test_preview_pass_renders_costswing_fields(self):
        out, before, after, tmps = self.call(op41([[1, C_B, P]], t=100))
        # Top-level key order unchanged.
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [41, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 0, 0, 1])
        scenarios = row[4][3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row: op 40's 22-element shape with
        # maxWindowCostSwing inserted after maxWindowLatencySwing and
        # before pass (23 elements).
        s0 = scenarios[0]
        self.assertEqual(len(s0), 23)
        self.assertEqual(s0[16], 1)             # maxWindowDistinctNexthops
        self.assertEqual(s0[17], 1)             # maxWindowDistinctLastHops
        self.assertEqual(s0[18], 0)             # maxWindowLatencySwing
        self.assertEqual(s0[19], 8)             # maxWindowCostSwing
        self.assertIs(s0[20], True)             # pass
        # Flow row gains windowMaxCostSwing / costSwingPass after
        # latencySwingPass and before nexthopDiversityPass: 30 elements.
        f0 = s0[21][0]
        self.assertEqual(len(f0), 30)
        self.assertEqual(f0,
                         ["f1", 2, 10, 20, 20,
                          ["s", "b", "d"], ["s", "c", "d"], True, True,
                          1, None, None, True, -4, 1, True,
                          1, 2, 1, 1, 1, True,
                          0, True, 8, True, True, True, True, True])
        # The stationary f2 keeps every window empty: cost swing 0.
        self.assertEqual(s0[21][1][14:30],
                         [0, True, 0, 0, 0, 0, 0,
                          True, 0, True, 0, True, True, True, True, True])
        # Failure scenarios do not migrate: their swing windows stay
        # empty and their rows still pass.
        for sx in scenarios[1:]:
            self.assertEqual(sx[17], 0)
            self.assertEqual(sx[18], 0)
            self.assertEqual(sx[19], 0)
            self.assertIs(sx[20], True)
            self.assertIs(sx[21][0][7], False)
            self.assertEqual(sx[21][0][24:30],
                             [0, True, True, True, True, True])

    # ----------------------------------------------------------------
    # T = 0 accepts only zero-cost-swing records / empty windows
    # ----------------------------------------------------------------
    def test_t_zero_rejects_first_swing_keeps_candidate(self):
        out, before, after, tmps = self.call(op41([[1, C_B, P]], t=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[19], 8)             # candidate max cost swing
        self.assertFalse(s0[20])
        fr = s0[21][0]
        # Candidate post-event values retained: the cost 2 -> 10 jump,
        # the 8 cost swing, T failed; the latency swing stays 0 and G
        # passes, and every other flag stays true.
        self.assertEqual(fr[1], 2)
        self.assertEqual(fr[2], 10)
        self.assertEqual(fr[24:30],
                         [8, False, True, True, True, True])
        # Failure scenarios never moved and still pass.
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[20])
            self.assertEqual(sx[19], 0)

    def test_t_is_inclusive_at_the_boundary(self):
        # An 8 cost swing passes T = 8 but fails T = 7.
        out, _, _, _ = self.call(op41([[1, C_B, P]], t=8))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[19], 8)
        self.assertTrue(s0[20])
        out, _, _, _ = self.call(op41([[1, C_B, P]], t=7))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[19], 8)
        self.assertFalse(s0[20])

    def test_zero_cost_swing_reroute_passes_t_zero(self):
        # A migration between equal-cost paths records cost swing 0 and
        # so passes T = 0 even though the path, links, first hop, and
        # last hop all change.
        out, _, _, _ = self.call(
            op41([[1, Z_B, P]], t=0), pk=pack(Z_A))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        f0 = s0[21][0]
        self.assertIs(f0[7], True)
        self.assertEqual(f0[1], 2)
        self.assertEqual(f0[2], 2)
        self.assertEqual(f0[20], 1)             # one distinct last hop
        self.assertEqual(f0[24], 0)             # zero cost swing
        self.assertIs(f0[25], True)             # T = 0 admits it
        self.assertEqual(s0[19], 0)
        self.assertTrue(s0[20])

    # ----------------------------------------------------------------
    # The T gate genuinely diverges from the G (latency) gate
    # ----------------------------------------------------------------
    def test_cost_gate_independent_of_latency_gate(self):
        # The C_B migration keeps latency 20 -> 20 (latency swing 0, so
        # G = 0 passes) but jumps cost 2 -> 10 (cost swing 8, T = 7
        # rejects).
        out, before, after, _ = self.call(
            op41([[1, C_B, P]], g=0, t=7))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        f0 = s0[21][0]
        self.assertEqual(f0[5], ["s", "b", "d"])
        self.assertEqual(f0[6], ["s", "c", "d"])
        self.assertIs(f0[7], True)
        self.assertEqual(f0[22], 0)             # latency swing
        self.assertIs(f0[23], True)             # G = 0 passes
        self.assertEqual(f0[24], 8)             # cost swing
        self.assertIs(f0[25], False)            # T fails
        self.assertEqual(s0[18], 0)
        self.assertEqual(s0[19], 8)
        self.assertFalse(s0[20])
        # Giving T room admits the same event.
        out, _, _, _ = self.call(
            op41([[1, C_B, P]], g=0, t=8))
        self.assertEqual(out["status"], 0)

    def test_latency_gate_still_rejects_when_t_passes(self):
        # The L_B migration keeps cost 2 -> 2 (cost swing 0, so T = 0
        # passes) but jumps latency 20 -> 35 (latency swing 15, G = 14
        # rejects): the two gates are independent in both directions.
        out, before, after, _ = self.call(
            op41([[1, L_B, P]], g=14, t=0), pk=pack(L_A))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        f0 = s0[21][0]
        self.assertEqual(f0[22], 15)            # latency swing
        self.assertIs(f0[23], False)            # G fails
        self.assertEqual(f0[24], 0)             # cost swing
        self.assertIs(f0[25], True)             # T = 0 passes
        self.assertFalse(s0[20])
        # G = 15 then admits it even with T = 0.
        out, _, _, _ = self.call(
            op41([[1, L_B, P]], g=15, t=0), pk=pack(L_A))
        self.assertEqual(out["status"], 0)

    # ----------------------------------------------------------------
    # The window keeps the MAX, never a sum, and slides closed
    # ----------------------------------------------------------------
    def test_window_keeps_max_not_sum(self):
        # A 5 cost swing at event 1 then a 15 cost swing at event 2:
        # with W=100 both records are retained, so the window maximum
        # grows 5 -> 15 (never their sum 20). T = 14 admits event 1 but
        # stops at event 2; T = 15 admits the whole batch.
        t_c7 = cdiv_topo(sb=20, sc=1, scd=6)    # c cost 7 wins
        t_b22 = cdiv_topo(sb=21, sc=50, scd=50)  # b cost 22 wins
        events = [[1, t_c7, P], [2, t_b22, P]]
        out, before, after, _ = self.call(op41(events, t=15, w=100))
        self.assertEqual(out["status"], 0)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0)])
        s1 = out["events"][0][4][3][0]
        self.assertEqual(s1[19], 5)             # after event 1
        s2 = out["events"][1][4][3][0]
        f0 = s2[21][0]
        self.assertEqual(f0[14], 2)             # two retained reroutes
        self.assertEqual(s2[19], 15)            # max(5, 15), not 20
        self.assertTrue(s2[20])
        out, _, _, _ = self.call(op41(events, t=14, w=100))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s2 = out["events"][1][4][3][0]
        self.assertEqual(s2[19], 15)
        self.assertFalse(s2[20])

    def test_costswing_window_is_closed_when_sliding(self):
        # One reroute (cost swing 5) at clock 1, then a quiet event at
        # clock 2 that moves nothing. T is permissive enough for event
        # 1 to pass; W = 1 keeps clock 1 on the closed edge e-W so the
        # 5 survives into event 2, while W = 0 drops it and the window
        # is empty at event 2.
        t_c7 = cdiv_topo(sb=20, sc=1, scd=6)
        t_quiet = json.loads(json.dumps(t_c7))
        t_quiet["links"][4]["latency"] = 11
        events = [[1, t_c7, P], [2, t_quiet, P]]
        out, _, _, _ = self.call(op41(events, t=5, w=1))
        self.assertEqual(out["status"], 0)
        s1 = out["events"][1][4][3][0]
        self.assertIs(s1[21][0][7], False)
        self.assertEqual(s1[19], 5)
        self.assertTrue(s1[20])
        out, _, _, _ = self.call(op41(events, t=5, w=0))
        self.assertEqual(out["status"], 0)
        s1 = out["events"][1][4][3][0]
        self.assertEqual(s1[19], 0)
        self.assertTrue(s1[20])

    def test_max_queue_front_slides_with_old_maximum(self):
        # Cost swings 25 @ 1 then 5 @ 2; a quiet event 3 with W = 1
        # trims clock 1 strictly below 3-1 = 2, so the old maximum 25
        # leaves and the retained maximum falls to 5 - exercising the
        # monotonic max queue's front eviction, not a stale max.
        m0 = cdiv_topo()                              # b cost 2
        m1 = cdiv_topo(sb=200, sc=26, scd=1)          # c cost 27 wins
        m2 = cdiv_topo(sb=21, sc=50, scd=1)           # b cost 22 wins
        m3 = json.loads(json.dumps(m2))
        m3["links"][4]["latency"] = 11
        events = [[1, m1, P], [2, m2, P], [3, m3, P]]
        out, _, _, _ = self.call(op41(events, t=25, w=1), pk=pack(m0))
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 0)])
        s1 = out["events"][1][4][3][0]
        self.assertEqual(s1[19], 25)           # max(25, 5)
        s2 = out["events"][2][4][3][0]
        self.assertEqual(s2[19], 5)            # 25 slid out, 5 stays
        self.assertTrue(s2[20])

    # ----------------------------------------------------------------
    # Predicate exclusions
    # ----------------------------------------------------------------
    def test_equal_state_and_unchanged_path_add_no_record(self):
        # Event 2 is equal state (status 1, empty impact); event 3
        # changes only the isolated n5->n6 latency, so nothing appends
        # and the earlier cost-swing window still slides normally.
        t_quiet = json.loads(json.dumps(C_B))
        t_quiet["links"][4]["latency"] = 11
        out, _, _, _ = self.call(
            op41([[1, C_B, P], [2, C_B, P], [3, t_quiet, P]],
                 t=100, w=100))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 0)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        s2 = out["events"][2][4][3][0]
        self.assertEqual(s2[19], 8)
        f0 = s2[21][0]
        self.assertIs(f0[7], False)
        self.assertEqual(f0[24:30], [8, True, True, True, True, True])

    def test_unreachable_migration_adds_no_record(self):
        # The candidate side drops both s-branches: f1 is unreachable,
        # no reroute, so no cost-swing record even though the event
        # fails (and the batch stops) on reachability.
        t_dead = {"nodes": C_A["nodes"],
                  "links": [lk for lk in C_A["links"]
                            if (lk["from"], lk["to"])
                            not in (("s", "b"), ("s", "c"))]}
        out, before, after, _ = self.call(op41([[1, t_dead, P]], t=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[20])
        f0 = s0[21][0]
        self.assertEqual(f0[6], [])             # unreachable new side
        self.assertIs(f0[7], False)
        self.assertEqual(f0[24], 0)             # no cost-swing record
        self.assertIs(f0[25], True)             # T itself does not fail

    # ----------------------------------------------------------------
    # No merging across scenarios or flows
    # ----------------------------------------------------------------
    def test_scenarios_never_merge(self):
        # Only the no-failure scenario migrates (b -> c, cost swing 8);
        # in x b was already failed onto c and in z c failed keeps b,
        # so their cost-swing windows stay empty.
        out, _, _, _ = self.call(op41([[1, C_B, P]], t=0))
        s0, sx, sz = out["events"][0][4][3]
        self.assertFalse(s0[20])
        self.assertEqual(s0[21][0][24:30],
                         [8, False, True, True, True, True])
        for other in (sx, sz):
            self.assertTrue(other[20])
            self.assertEqual(other[19], 0)
            self.assertEqual(other[21][0][24:30],
                             [0, True, True, True, True, True])

    def test_flows_never_merge(self):
        # Two independently migrating flows on disjoint cost diamonds
        # with cost swings 8 and 10, plus a stationary demand-999
        # flow. Over cb then ca each flow keeps its own two equal
        # records; the scenario maxWindowCostSwing is max(8, 10) = 10,
        # never the merged sum 18 or either flow's sum.
        two = [["f1", "s", "d", 1, 1000],
               ["f3", "n0", "d2", 1, 1000],
               ["f4", "n5", "n6", 999, 1000]]

        def combo(sb=1, n0b=1):
            nodes = ["s", "b", "c", "d",
                     "n0", "b2", "c2", "d2", "n5", "n6"]
            return {"nodes": nodes,
                    "links": [link("s", "b", sb), link("b", "d"),
                              link("s", "c", 5), link("c", "d", 5),
                              link("n0", "b2", n0b), link("b2", "d2"),
                              link("n0", "c2", 1),
                              link("c2", "d2", 11),
                              link("n5", "n6")]}

        ca, cb = combo(), combo(sb=20, n0b=20)
        events = [[1, cb, P], [2, ca, P]]
        out, _, _, _ = self.call(
            op41(events, flows_=two, scenarios=[["x", ["b"], []]],
                 g=100, t=10, w=100), pk=pack(ca))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        f1, f3, f4 = s0[21]
        self.assertEqual(f1[24], 8)
        self.assertEqual(f3[24], 10)
        self.assertEqual(f4[24], 0)
        self.assertEqual(s0[19], 10)            # max, not sum/merge
        # T = 9 rejects on f3's 10 at the very first event.
        out, _, _, _ = self.call(
            op41(events, flows_=two, scenarios=[["x", ["b"], []]],
                 g=100, t=9, w=100), pk=pack(ca))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[19], 10)
        self.assertFalse(s0[20])

    # ----------------------------------------------------------------
    # Op 40's other gates still reject independently
    # ----------------------------------------------------------------
    def test_k_gate_still_rejects_independently(self):
        # The equal-cost migration has cost swing 0 (T = 0 passes) but
        # still changes the last hop, so K = 0 rejects on its own.
        out, before, after, _ = self.call(
            op41([[1, Z_B, P]], t=0, k=0), pk=pack(Z_A))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[20])
        f0 = s0[21][0]
        self.assertIs(f0[21], False)            # K fails
        self.assertEqual(f0[24], 0)
        self.assertIs(f0[25], True)             # T passes

    def test_q_gate_still_rejects_independently(self):
        # T admits the 8 cost swing, but Q = 0 rejects the first
        # reroute.
        out, before, after, _ = self.call(
            op41([[1, C_B, P]], t=100, q=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[20])
        f0 = s0[21][0]
        self.assertIs(f0[15], False)            # windowPass fails
        # Candidate record still appended; cost swing rendered and all
        # diversity flags read true on the failed row.
        self.assertEqual(f0[16:30],
                         [1, 2, 1, 1, 1, True,
                          0, True, 8, True, True, True, True, True])

    def test_g_gate_still_rejects_independently(self):
        # The latency-only migration swings cost 0 (T = 0 passes) but
        # latency 15, so G = 0 rejects on its own.
        out, before, after, _ = self.call(
            op41([[1, L_B, P]], g=0, t=0), pk=pack(L_A))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        f0 = s0[21][0]
        self.assertEqual(f0[22], 15)
        self.assertIs(f0[23], False)            # G fails
        self.assertEqual(f0[24], 0)
        self.assertIs(f0[25], True)             # T passes

    # ----------------------------------------------------------------
    # Commit / resend / rollback semantics
    # ----------------------------------------------------------------
    def test_commit_resend_and_idempotent(self):
        out, before, after, tmps = self.call(
            op41([[1, C_B, P]], t=100, m=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(C_B, v=1, history=[[0, C_A, P], [1, C_B, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            op41([[1, C_B, P]], t=100, m=1), pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Equal-state event: status 0, no write even with every cap 0.
        out3, _, after3, _ = self.call(
            op41([[2, C_B, P]], t=0, g=0, k=0, j=0, z=0, y=0, x=0,
                 q=0, n=0, m=1, b=1),
            pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(json.loads(after3)["v"], 1)

    def test_failed_batch_does_not_commit(self):
        # Event 1 migrates b -> c with a 5 cost swing (T = 14 admits);
        # event 2 migrates c -> b with a 15 cost swing so the retained
        # window max grows to 15 and T = 14 fails the second event -
        # mode 1 leaves PACK untouched and stops at once.
        t_c7 = cdiv_topo(sb=20, sc=1, scd=6)
        t_b22 = cdiv_topo(sb=21, sc=50, scd=50)
        events = [[1, t_c7, P], [2, t_b22, P]]
        out, before, after, tmps = self.call(
            op41(events, t=14, w=100, m=1))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s1 = out["events"][1][4][3][0]
        self.assertEqual(s1[19], 15)
        self.assertFalse(s1[20])
        # A feasible retry (T = 15) commits from the same base.
        out2, _, after2, _ = self.call(
            op41(events, t=15, w=100, m=1))
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_stale_base_conflict_code5(self):
        pk1 = pack(C_B, v=1, history=[[0, C_A, P], [1, C_B, P]])
        other = json.loads(json.dumps(C_A))
        other["links"][4]["latency"] = 7
        self.call(op41([[6, other, P]], t=100, m=1), pk=pk1,
                  expect_rc=5)

    # ----------------------------------------------------------------
    # Determinism / error codes / backward compatibility
    # ----------------------------------------------------------------
    def test_byte_deterministic(self):
        op_obj = op41([[1, C_B, P], [2, C_A, P]], t=15, w=100)
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
                 json.dumps(op41([[1, C_B, P]]))], capture_output=True)
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
        good = op41([[1, C_B, P]])
        self.assertEqual(len(good), 22)
        tail16 = [1] * 16
        bad = [
            # wrong arity: op 40's 21-element shape and one too many
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS] + [1] * 15,
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS] + [1] * 17,
            # op 40 must not accept op 41's 22 elements and vice versa
            [40, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS] + [1] * 16,
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            # T negative / boolean / too large / string / float
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True],
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
             9223372036854775808],
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, "1"],
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5],
            # op 40's G range still enforced inside op 41
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1],
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True, 1, 1],
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1, 1, 1],
            # bad mode
            [41, 2, 0, [[1, C_B, P]], FLOWS, SCENARIOS] + tail16,
            # empty E / F / S
            [41, 0, 0, [], FLOWS, SCENARIOS] + tail16,
            [41, 0, 0, [[1, C_B, P]], [], SCENARIOS] + tail16,
            [41, 0, 0, [[1, C_B, P]], FLOWS, []] + tail16,
            # clocks decrease
            [41, 0, 0, [[2, C_B, P], [1, C_B, P]], FLOWS,
             SCENARIOS] + tail16,
            # invalid scenario reference at h[b]
            [41, 0, 0, [[1, C_B, P]], FLOWS,
             [["q", ["d"], []]]] + tail16,
            # flow endpoint absent at h[b]
            [41, 0, 0, [[1, C_B, P]],
             [["g", "s", "n9", 1, 1000]], SCENARIOS] + tail16,
        ]
        for op_obj in bad:
            self.call(op_obj, expect_rc=5)
        # T = MAX_TIME and G = MAX_COST are accepted.
        self.call(op41([[1, C_B, P]], t=9223372036854775807,
                       g=2147483647))

    def test_ops_0_to_40_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        # op 40 keeps its 22-field scenario row and 28-field flow row,
        # with no cost-swing fields.
        out, _, _, _ = self.call(
            [40, 0, 0, [[1, L_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10, 10, 10, 10, 10, 100])
        self.assertEqual(out["op"], 40)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(len(s0), 22)
        self.assertEqual(len(s0[20][0]), 28)
        # op 40's 21-arity shape must not parse as op 41 and op 41's
        # 22-arity shape must not parse as op 40.
        self.call(
            [41, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS] + [1] * 15,
            expect_rc=5)
        self.call(
            [40, 0, 0, [[1, C_B, P]], FLOWS, SCENARIOS] + [1] * 16,
            expect_rc=5)


if __name__ == "__main__":
    unittest.main()
